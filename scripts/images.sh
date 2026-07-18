#!/usr/bin/env bash
# Manage externally-released image pins in compose/images.yaml.
#
#   images.sh bump <service> <version>   bump one image pin
#
# `bump` is meant to be committed with a RELEASABLE type (feat:) — see
# docs/superpowers/specs/2026-05-17-unified-release-design.md and
# release-please-config.json: `chore` is hidden there, so a chore-typed pin
# bump never cuts a release and the new image sits on main undeployed. This
# script only edits + validates the file; the git/commit/PR automation is a
# separate concern (task images:bump wraps this; a future task adds the PR
# flow on top).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Override via LDS_IMAGES_FILE for tests.
IMAGES_FILE="${LDS_IMAGES_FILE:-$ROOT/compose/images.yaml}"

# Service names are the *_image keys in compose/images.yaml, minus the
# suffix. Deliberately does NOT include siteapp/flasher/streamer/caddy —
# those are core, repo-built services pinned via *_image_repo in
# compose/pins.yaml, not externally-released images this command touches.
_SERVICES=(jupyter chisel loki grafana studio authelia prometheus node_exporter cadvisor)

_known_service() {
    local svc want="$1"
    for svc in "${_SERVICES[@]}"; do
        [[ "$svc" == "$want" ]] && return 0
    done
    return 1
}

# Verify the target reference is a real, anonymously-pullable image before
# touching the file. Skipped in tests via LDS_SKIP_REGISTRY_CHECK=1 (no
# network access needed there).
#
# Resolves registry + repo path the way `docker pull` would: the first path
# segment is a registry host only when it contains a dot/colon or is
# "localhost" (quay.io/..., ghcr.io/...); a bare name (nginx) is Docker
# Hub's "library/" namespace; anything else with exactly one slash
# (jpillora/chisel, grafana/grafana, authelia/authelia, prom/prometheus) is
# a plain Docker Hub namespace/repo pair and must NOT get a "library/"
# prefix. Docker Hub's registry host (registry-1.docker.io) also delegates
# token auth to a *different* host (auth.docker.io) — unlike quay.io/ghcr.io,
# whose token endpoint lives on the registry host itself.
_verify_pullable() {
    local ref="$1"
    [[ "${LDS_SKIP_REGISTRY_CHECK:-0}" == "1" ]] && return 0
    require_cmd curl
    require_cmd yq

    local repo tag first registry path
    repo="${ref%:*}"; tag="${ref##*:}"
    first="${repo%%/*}"
    if [[ "$first" == "$repo" ]]; then
        registry="registry-1.docker.io"; path="library/$repo"
    elif [[ "$first" == *.* || "$first" == *:* || "$first" == "localhost" ]]; then
        registry="$first"; path="${repo#*/}"
    else
        registry="registry-1.docker.io"; path="$repo"
    fi

    local auth_host="$registry" auth_service="$registry"
    if [[ "$registry" == "registry-1.docker.io" ]]; then
        auth_host="auth.docker.io"; auth_service="registry.docker.io"
    fi

    local token
    token="$(curl -fsSL "https://${auth_host}/token?service=${auth_service}&scope=repository:${path}:pull" 2>/dev/null \
        | yq -p=json -o=yaml '.token // .access_token // ""' 2>/dev/null || true)"
    [[ "$token" == "null" ]] && token=""

    # Always at least the Accept headers, so this array is never empty —
    # `"${headers[@]}"` on a genuinely-empty array is an unbound-variable
    # error under `set -u` on bash < 4.4 (still the default /bin/bash on
    # macOS). Sending an empty `Authorization: Bearer` header (rather than
    # omitting it) also actively breaks anonymous-only registries like
    # quay.io, which 401 on a present-but-empty bearer token.
    local -a headers=(
        -H 'Accept: application/vnd.oci.image.index.v1+json'
        -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json'
        -H 'Accept: application/vnd.oci.image.manifest.v1+json'
        -H 'Accept: application/vnd.docker.distribution.manifest.v2+json'
    )
    [[ -n "$token" ]] && headers+=(-H "Authorization: Bearer ${token}")

    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' \
        "${headers[@]}" \
        "https://${registry}/v2/${path}/manifests/${tag}" || echo 000)"
    [[ "$code" == "200" ]] || die "image not pullable: $ref (registry returned $code)"
}

cmd_bump() {
    local svc="${1:-}" version="${2:-}"
    [[ -n "$svc" && -n "$version" ]] || die "usage: images.sh bump <service> <version>"
    _known_service "$svc" \
        || die "unknown service '$svc' (allowed: ${_SERVICES[*]})"
    [[ -f "$IMAGES_FILE" ]] || die "images file not found: $IMAGES_FILE"
    require_cmd yq

    local key current repo new
    key=".${svc}_image"
    current="$(yq e "$key" "$IMAGES_FILE")"
    [[ -n "$current" && "$current" != "null" ]] || die "no such key in $IMAGES_FILE: ${svc}_image"
    repo="${current%:*}"
    new="${repo}:${version}"
    if [[ "$current" == "$new" ]]; then
        log "already at $new"
        return 0
    fi
    _verify_pullable "$new"
    yq -i "$key = \"$new\"" "$IMAGES_FILE"
    log "bumped $svc: $current -> $new"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        bump) cmd_bump "$@" ;;
        *)    die "usage: images.sh {bump} [args]" ;;
    esac
}

main "$@"

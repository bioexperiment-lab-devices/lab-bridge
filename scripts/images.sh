#!/usr/bin/env bash
# Manage externally-released image pins in compose/images.yaml.
#
#   images.sh bump <service> <version>   bump one image pin, branch + PR it
#   images.sh ship                       cut a release for pins already on main
#
# Both commit with a RELEASABLE type (feat:) — see
# docs/superpowers/specs/2026-05-17-unified-release-design.md and
# release-please-config.json: `chore` is hidden there, so a chore-typed pin
# bump never cuts a release and the new image sits on main undeployed.
# `ship` exists because Renovate lands its grouped bumps as `chore` on
# purpose (no auto-deploy); an empty `feat:` commit is how those pins get
# shipped once someone decides they're ready.
#
# LDS_NO_GIT=1 makes `bump` edit compose/images.yaml only (no branch/commit/
# PR) — used by tests. LDS_REPO_DIR overrides which git repo the git/PR
# helpers act on (defaults to the repo this script lives in) — also test-only.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

# Override via LDS_IMAGES_FILE for tests.
IMAGES_FILE="${LDS_IMAGES_FILE:-$ROOT/compose/images.yaml}"

# Git operations act on this repo. Overridable so tests can use a scratch repo
# instead of the real checkout.
REPO_DIR="${LDS_REPO_DIR:-$ROOT}"

# Service names are the *_image keys in compose/images.yaml, minus the
# suffix. Deliberately does NOT include siteapp/flasher/streamer/caddy —
# those are core, repo-built services pinned via *_image_repo in
# compose/pins.yaml, not externally-released images this command touches.
_SERVICES=(jupyter chisel loki grafana studio authelia redis prometheus node_exporter cadvisor)

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

# Refuse to touch git if the working tree has staged, unstaged, OR untracked
# changes — a bump/ship commit must contain only what this script itself
# adds. `git status --porcelain` (rather than `diff`/`diff --cached` alone)
# is deliberate: it also catches untracked stray files, which the old
# diff-only check let through.
_require_clean_tree() {
    [[ -z "$(git -C "$REPO_DIR" status --porcelain)" ]] \
        || die "git working tree is not clean — commit, stash, or remove untracked files first"
}

# Checkout a new branch, dying with an actionable message if it already
# exists — e.g. a prior bump/ship run's PR hasn't merged (or been deleted)
# yet, so a bare `git checkout -b` would fail with a bare, unhelpful error.
_checkout_new_branch() {
    local branch="$1"
    git -C "$REPO_DIR" show-ref --verify --quiet "refs/heads/$branch" \
        && die "branch '$branch' already exists in $REPO_DIR — delete it (git -C '$REPO_DIR' branch -D $branch) or merge/close its PR before re-running"
    # Also check the remote. A fresh CI checkout never has the local branch,
    # but the remote one survives a closed PR — without this check, `git push`
    # to a stale remote branch of the same name does not fail loudly: it
    # exits 0 and silently fast-forwards the stale branch (and, downstream,
    # the PR reopened against it) instead of dying with an actionable
    # message. A silent overwrite is worse than a rejection.
    # Pass the fully-qualified ref, not the bare branch name: `ls-remote`
    # matches patterns on `/`-boundary suffixes, so a bare name would also
    # false-positive on e.g. "x/images/grafana-13.0.0" when checking for
    # "images/grafana-13.0.0".
    if git -C "$REPO_DIR" ls-remote --exit-code --heads origin "refs/heads/$branch" >/dev/null 2>&1; then
        die "branch '$branch' already exists on origin — delete it (git -C '$REPO_DIR' push origin --delete $branch) or merge/close its PR before re-running"
    fi
    git -C "$REPO_DIR" checkout -b "$branch"
}

# _open_pr <branch> <subject> <body> [pathspec] — branch, commit, push, PR.
# When pathspec is given, the commit is scoped to it (`git commit -- path`
# commits only that path even if other, unrelated changes are staged) so a
# bump commit can never sweep in something else the operator had staged.
# `ship`'s empty commit has no path to scope to and omits it.
_open_pr() {
    local branch="$1" subject="$2" body="$3" pathspec="${4:-}"
    _checkout_new_branch "$branch"
    if [[ -n "$pathspec" ]]; then
        git -C "$REPO_DIR" commit -q -m "$subject" -m "$body" -- "$pathspec"
    else
        git -C "$REPO_DIR" commit -q -m "$subject" -m "$body"
    fi
    git -C "$REPO_DIR" push -u origin "$branch"
    # Capture the PR URL so CI can auto-merge this exact PR rather than
    # re-deriving the branch name and coupling the workflow to the naming
    # scheme here. `gh pr create` prints the URL as its last stdout line.
    local url
    url="$( cd "$REPO_DIR" && gh pr create --title "$subject" --body "$body" --base main --head "$branch" | tail -n1 )"
    printf '%s\n' "$url"
    # `if`, not `[[ ... ]] && printf`: under `set -e` a false condition as the
    # function's last command would make _open_pr return 1 and abort the run
    # whenever GITHUB_OUTPUT is unset (i.e. every laptop invocation).
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        printf 'pr_url=%s\n' "$url" >>"$GITHUB_OUTPUT"
    fi
}

cmd_bump() {
    local svc="${1:-}" version="${2:-}"
    [[ -n "$svc" && -n "$version" ]] || die "usage: images.sh bump <service> <version>"
    _known_service "$svc" \
        || die "unknown service '$svc' (allowed: ${_SERVICES[*]})"
    # Validate before anything touches yq, the registry probe, or git. The
    # version arrives from a cross-repo workflow_dispatch input, so treat it
    # as untrusted: allow exactly what a Docker tag allows (leading
    # alphanumeric, then alphanumerics/dot/dash/underscore, max 128 chars).
    [[ "$version" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] \
        || die "invalid version '$version' — must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\$"
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

    local subject body branch dry_run=0
    [[ "${*: -1}" == "--dry-run" ]] && dry_run=1
    subject="feat: bump ${svc} image to ${version}"
    body="Bumps \`${svc}_image\` from \`${current}\` to \`${new}\` in compose/images.yaml.

Typed \`feat:\` deliberately: release-please marks \`chore\` hidden, so a
chore-typed pin bump never cuts a release and the image would sit on main
undeployed. This single PR both pins and ships the image.

Image verified pullable before commit."

    if (( dry_run )); then
        printf '%s\n' "$subject"
        return 0
    fi

    # Guard before any mutation — including the registry probe's implicit
    # "this file is about to change" — so a dirty tree fails clearly rather
    # than silently sweeping stray staged/untracked content into the bump
    # commit. Skipped under LDS_NO_GIT=1: file-edit-only mode has no git
    # commit to protect, and Task 4's tests rely on it working in a dirty tree.
    [[ "${LDS_NO_GIT:-0}" == "1" ]] || _require_clean_tree

    _verify_pullable "$new"
    yq -i "$key = \"$new\"" "$IMAGES_FILE"
    printf 'bumped %s: %s -> %s\n' "$svc" "$current" "$new"

    [[ "${LDS_NO_GIT:-0}" == "1" ]] && return 0
    branch="images/${svc}-${version}"
    git -C "$REPO_DIR" add "$IMAGES_FILE"
    _open_pr "$branch" "$subject" "$body" "$IMAGES_FILE"
}

cmd_ship() {
    local subject body
    subject="feat: ship pinned images to the stack"
    body="Empty by design — compose/images.yaml already holds the intended pins
on main. Renovate lands image bumps as \`chore\`, which release-please marks
hidden, so those pins never cut a release on their own. This commit carries a
releasable type so release-build deploys them."
    if [[ "${1:-}" == "--dry-run" ]]; then
        _require_clean_tree
        printf '%s\n' "$subject"
        return 0
    fi
    _require_clean_tree
    _checkout_new_branch "images/ship-$(git -C "$REPO_DIR" rev-parse --short HEAD)"
    git -C "$REPO_DIR" commit -q --allow-empty -m "$subject" -m "$body"
    git -C "$REPO_DIR" push -u origin HEAD
    ( cd "$REPO_DIR" && gh pr create --title "$subject" --body "$body" --base main )
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        bump) cmd_bump "$@" ;;
        ship) cmd_ship "$@" ;;
        *)    die "usage: images.sh {bump|ship} [args]" ;;
    esac
}

main "$@"

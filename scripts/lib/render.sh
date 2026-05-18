#!/usr/bin/env bash
# Render the three deploy templates into a staging directory.
# Sourced, not executed. Depends on common.sh + config.sh being sourced and
# load_config having been called.

# _unified_version — print the unified platform version from VERSION.
# Override via LDS_VERSION_FILE for tests. The VERSION file path is
# resolved REPO-ROOT-RELATIVE via this script's location.
_unified_version() {
    local version_file="${LDS_VERSION_FILE:-}"
    if [[ -z "$version_file" ]]; then
        # scripts/lib/render.sh → repo root is two levels up.
        local script_dir
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        version_file="$script_dir/../../VERSION"
    fi
    [[ -f "$version_file" ]] || die "VERSION file not found: $version_file"
    local version
    version="$(awk 'NF { print $1; exit }' "$version_file")"
    [[ -n "$version" ]] || die "VERSION file is empty: $version_file"
    printf '%s' "$version"
}

# _siteapp_image — print ghcr.io/<owner>/lab-bridge-siteapp:<version>
_siteapp_image() {
    local repo="${SITEAPP_IMAGE_REPO:?SITEAPP_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}

# _flasher_image — print ghcr.io/<owner>/lab-bridge-flasher:<version>
_flasher_image() {
    local repo="${FLASHER_IMAGE_REPO:?FLASHER_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}

# _caddy_image — print ghcr.io/<owner>/lab-bridge-caddy:<version>
_caddy_image() {
    local repo="${CADDY_IMAGE_REPO:?CADDY_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}

# render_compose <template_path> <output_path>
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local siteapp_image flasher_image caddy_image
    siteapp_image="$(_siteapp_image)"
    flasher_image="$(_flasher_image)"
    caddy_image="$(_caddy_image)"
    # The password_hash contains $ and : characters but no | (sha1:hex:hex),
    # so | as the sed delimiter is safe.
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__PROMETHEUS_IMAGE__|${PROMETHEUS_IMAGE:?}|g" \
        -e "s|__PROMETHEUS_RETENTION_DAYS__|${PROMETHEUS_RETENTION_DAYS:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__SITEAPP_IMAGE__|${siteapp_image}|g" \
        -e "s|__FLASHER_IMAGE__|${flasher_image}|g" \
        -e "s|__CADDY_IMAGE__|${caddy_image}|g" \
        "$tmpl" \
        > "$out"
}

# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local platform_version
    platform_version="$(_unified_version)"
    sed \
        -e "s|__ACME_EMAIL__|${CADDY_ACME_EMAIL:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__ADMIN_BCRYPT_HASH__|${SITEAPP_ADMIN_PASSWORD_HASH:?}|g" \
        -e "s|__PLATFORM_VERSION__|${platform_version}|g" \
        "$tmpl" > "$out"
}

# render_chisel_users <output_path>
# Builds the chisel users.json from .chisel_clients in CONFIG_PATH.
# Each user is allow-listed for both their reverse port (R:0.0.0.0:<port>)
# and the in-network Loki push endpoint (loki:3100). The forward path lets
# the client tunnel its log stream to Loki without exposing Loki publicly.
render_chisel_users() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name + ":" + .password): ["R:0.0.0.0:" + (.reverse_port | tostring), "loki:3100"]})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}

# render_siteapp_clients <output_path>
# Builds the siteapp clients.json from .chisel_clients in CONFIG_PATH.
# Output shape: {"<name>": {"port": <int>, "password_sha256": "<hex>"}, ...}
# The password itself is never written — only its SHA-256 hash.
# Why SHA-256 (not bcrypt): chisel passwords are 32-byte cryptographic
# random tokens (~256 bits), so preimage resistance of SHA-256 is more
# than enough. Bcrypt's cost factor exists to slow dictionary attacks
# against low-entropy human passwords; that threat doesn't apply here.
# Note: yq v4 lacks @sha256, so we build the JSON via a shell loop using
# openssl for hashing, then merge the entries with yq.
render_siteapp_clients() {
    local out="${1:?}"
    local tmp_entries
    tmp_entries="$(mktemp)"

    # Build one JSON object per client: {"name": {"port": N, "password_sha256": "hex"}}
    printf '[' > "$tmp_entries"
    local first=true
    while IFS=$'\t' read -r name port password; do
        # Skip empty lines (yq emits a bare newline for an empty array)
        [[ -z "$name" ]] && continue
        local hash
        hash="$(printf '%s' "$password" | openssl dgst -sha256 -binary | xxd -p -c 64)"
        "$first" || printf ',' >> "$tmp_entries"
        printf '{"%s":{"port":%s,"password_sha256":"%s"}}' \
            "$name" "$port" "$hash" >> "$tmp_entries"
        first=false
    done < <(yq -o=tsv e '(.chisel_clients // [])[] | [.name, .reverse_port, .password] | @tsv' \
                "${CONFIG_PATH:?}")
    printf ']' >> "$tmp_entries"

    # Merge the array of single-key objects into one object (same as render_chisel_users).
    yq -p=json -o=json e '
        (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "$tmp_entries" > "$out"

    rm -f "$tmp_entries"
}

# render_loki_config <template_path> <output_path>
# Substitutes __LOKI_RETENTION_HOURS__ (computed from LOKI_RETENTION_DAYS).
render_loki_config() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local days="${LOKI_RETENTION_DAYS:?}"
    # Defence in depth: bash arithmetic silently coerces non-numeric to 0,
    # which would render `retention_period: 0h` (= grow forever). config.sh
    # already validates this, but render_loki_config is callable standalone.
    [[ "$days" =~ ^[0-9]+$ ]] || die "LOKI_RETENTION_DAYS must be a positive integer, got: $days"
    local hours=$(( days * 24 ))
    sed -e "s|__LOKI_RETENTION_HOURS__|${hours}|g" "$tmpl" > "$out"
}

#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
# shellcheck source=lib/crypto.sh
source "$SCRIPT_DIR/lib/crypto.sh"

# Path to config.yaml — overridable for tests.
CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"

ensure_config() {
    if [[ ! -f "$CONFIG" ]]; then
        die "config not found: $CONFIG (run: cp config.example.yaml config.yaml)"
    fi
}

prompt_password() {
    # Note: every output here goes to stderr — only the final printf hits
    # stdout, because callers use $(prompt_password ...) to capture the value.
    local label="$1" pw1 pw2
    read -rsp "$label: " pw1
    echo >&2
    read -rsp "$label (again): " pw2
    echo >&2
    [[ "$pw1" == "$pw2" ]] || die "passwords do not match"
    [[ -n "$pw1" ]] || die "empty password"
    printf '%s' "$pw1"
}

cmd_set_jupyter_password() {
    ensure_config

    local pw hash
    pw="$(prompt_password "JupyterLab password (shared by all team members)")"
    hash="$(jupyter_password_hash "$pw")"
    yq -i ".jupyter.password_hash = \"$hash\"" "$CONFIG"
    log "set JupyterLab password (deploy to apply)"
}

cmd_set_grafana_password() {
    # Plaintext on disk; matches the existing trust model on the VPS
    # (caddy_data certs and chisel-users.json are already plaintext under compose/).
    local pwfile="${LDS_GRAFANA_PASSWORD_FILE:-$SCRIPT_DIR/../compose/grafana/admin_password}"
    mkdir -p "$(dirname "$pwfile")"

    local pw
    pw="$(prompt_password "Grafana admin password (used to log in to https://<vps-host>/grafana/)")"

    # Atomic write so a partial file never lingers. The trap removes the temp
    # file (which contains the plaintext password) if mv fails for any reason.
    local tmp
    tmp="$(mktemp "${pwfile}.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT
    printf '%s' "$pw" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$pwfile"
    trap - EXIT
    log "wrote Grafana admin password to $pwfile (deploy to apply)"
}

cmd_rotate_agent_upload_token() {
    require_cmd python3
    local tokfile="${LDS_AGENT_TOKEN_FILE:-$SCRIPT_DIR/../compose/siteapp/agent_upload_token}"
    mkdir -p "$(dirname "$tokfile")"

    local token
    token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

    # Atomic write so a partial file never lingers.
    local tmp
    tmp="$(mktemp "${tokfile}.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT
    printf '%s' "$token" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$tokfile"
    trap - EXIT

    log "wrote new agent upload token to $tokfile"
    cat <<EOF

NEW TOKEN (save this in your CI secret store; it won't be shown again):

  $token

Update CI:
  - GitHub Actions: replace the AGENT_UPLOAD_TOKEN secret value
  - then run: task deploy

EOF
}

cmd_rotate_flasher_upload_token() {
    require_cmd python3
    local tokfile="${LDS_FLASHER_UPLOAD_TOKEN_FILE:-$SCRIPT_DIR/../compose/flasher/upload_token}"
    mkdir -p "$(dirname "$tokfile")"

    local token
    token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

    # Atomic write so a partial file never lingers.
    local tmp
    tmp="$(mktemp "${tokfile}.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT
    printf '%s' "$token" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$tokfile"
    trap - EXIT

    log "wrote new flasher upload token to $tokfile"
    cat <<EOF

NEW TOKEN (save this in your CI secret store; it won't be shown again):

  $token

Update CI:
  - GitHub Actions: replace the FLASHER_UPLOAD_TOKEN secret value
  - then run: task deploy

EOF
}

cmd_add_client() {
    local name="${1:?usage: secrets.sh add-client <name> <reverse_port>}"
    local port="${2:?usage: secrets.sh add-client <name> <reverse_port>}"
    ensure_config

    [[ "$port" =~ ^[0-9]+$ ]] || die "reverse_port must be numeric, got: $port"

    local existing_name existing_port
    existing_name="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -z "$existing_name" ]] || die "client $name already exists"
    existing_port="$(yq e ".chisel_clients[] | select(.reverse_port == $port) | .name" "$CONFIG")"
    [[ -z "$existing_port" ]] || die "reverse_port $port already in use by $existing_port"

    # Need vps.host for the printout; load via validate-only path.
    local host
    host="$(yq e '.vps.host' "$CONFIG")"
    [[ -n "$host" && "$host" != "null" ]] || die "vps.host missing in $CONFIG"

    local pw
    pw="$(gen_password)"
    yq -i ".chisel_clients += [{\"name\": \"$name\", \"reverse_port\": $port, \"password\": \"$pw\"}]" "$CONFIG"

    log "added client $name (port $port)"
    cat <<EOF

Run on the device:
  chisel client https://$host:$(yq e '.chisel.listen_port' "$CONFIG") \\
    $name:$pw \\
    R:0.0.0.0:$port:localhost:80

EOF
}

cmd_show_client() {
    local name="${1:?usage: secrets.sh show-client <name>}"
    ensure_config

    local pw port host listen
    pw="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .password" "$CONFIG")"
    port="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .reverse_port" "$CONFIG")"
    [[ -n "$pw" && "$pw" != "null" ]] || die "client $name not found"

    host="$(yq e '.vps.host' "$CONFIG")"
    listen="$(yq e '.chisel.listen_port' "$CONFIG")"

    cat <<EOF
Run on the device:
  chisel client https://$host:$listen \\
    $name:$pw \\
    R:0.0.0.0:$port:localhost:80

EOF
}

cmd_rm_client() {
    local name="${1:?usage: secrets.sh rm-client <name>}"
    ensure_config

    local existing
    existing="$(yq e ".chisel_clients[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -n "$existing" ]] || die "client $name not found"

    yq -i "del(.chisel_clients[] | select(.name == \"$name\"))" "$CONFIG"
    log "removed client $name"
}

cmd_bootstrap_authelia() {
    require_cmd openssl
    require_cmd yq

    local rotate=0
    [[ "${1:-}" == "--rotate" ]] && rotate=1

    ensure_config

    local secrets_dir="${LDS_AUTHELIA_SECRETS_DIR:-$SCRIPT_DIR/../compose/authelia/secrets}"
    local grafana_oidc_secret_file="${LDS_GRAFANA_OIDC_SECRET_FILE:-$SCRIPT_DIR/../compose/grafana/oidc_secret}"
    mkdir -p "$secrets_dir"
    mkdir -p "$(dirname "$grafana_oidc_secret_file")"

    local existing=0
    for f in jwt_secret session_secret storage_encryption_key oidc_hmac_secret \
             oidc_jwks_key.pem; do
        [[ -f "$secrets_dir/$f" ]] && existing=1
    done
    [[ -f "$grafana_oidc_secret_file" ]] && existing=1

    if (( existing && !rotate )); then
        die "authelia secrets already exist in $secrets_dir; pass --rotate to overwrite"
    fi

    # Four 64-byte hex tokens.
    for f in jwt_secret session_secret storage_encryption_key oidc_hmac_secret; do
        openssl rand -hex 64 > "$secrets_dir/$f"
        chmod 600 "$secrets_dir/$f"
    done

    # RSA 4096 for OIDC JWKS.
    openssl genrsa -out "$secrets_dir/oidc_jwks_key.pem" 4096 2>/dev/null
    chmod 600 "$secrets_dir/oidc_jwks_key.pem"

    # Raw Grafana OIDC client secret + its PBKDF2 hash. The image pin comes
    # from compose/images.yaml via $AUTHELIA_IMAGE, which is exported by config.sh.
    local raw hash
    raw="$(openssl rand -base64 32 | tr -d '+/=' | head -c 48)"
    printf '%s' "$raw" > "$grafana_oidc_secret_file"
    chmod 600 "$grafana_oidc_secret_file"

    # Compute PBKDF2 hash for the Grafana OIDC client.
    if [[ -n "${LDS_PBKDF2_HASH_CMD:-}" ]]; then
        # Test hook: a printf-format-style command that produces a fake hash.
        hash="$(bash -c "$LDS_PBKDF2_HASH_CMD" _ "$raw")"
    else
        require_cmd docker
        # Honour AUTHELIA_IMAGE if the caller already exported it (the bats
        # bootstrap helper sets it to the upstream pin from the *real*
        # compose/images.yaml; the fixture images.yaml under tests/integration/
        # uses an unpullable ghcr.io/test/... tag). Otherwise read straight
        # from compose/images.yaml rather than depending on `load_config`
        # (which validates the full config and is overkill here).
        local authelia_image="${AUTHELIA_IMAGE:-}"
        if [[ -z "$authelia_image" ]]; then
            local images_path="${LDS_IMAGES_FILE:-$SCRIPT_DIR/../compose/images.yaml}"
            authelia_image="$(yq e '.authelia_image' "$images_path")"
            [[ -n "$authelia_image" && "$authelia_image" != "null" ]] \
                || die "authelia_image not set in $images_path"
        fi
        # `authelia crypto hash generate pbkdf2 --password <p>` prints the
        # hash after a label prefix. Older builds used "Password hash: " while
        # 4.38.x uses "Digest: "; match either to be forward-compatible.
        hash="$(docker run --rm "$authelia_image" \
            authelia crypto hash generate pbkdf2 --variant sha512 \
            --password "$raw" 2>/dev/null \
            | awk -F': ' '/Password hash:|Digest:/ {print $2; exit}')"
    fi
    [[ -n "$hash" ]] || die "failed to derive PBKDF2 hash for grafana OIDC secret"

    yq -i ".authelia.grafana_oidc_secret_hash = \"$hash\"" "$CONFIG"
    log "wrote authelia secrets to $secrets_dir"
    log "wrote grafana OIDC secret to $grafana_oidc_secret_file"
    log "wrote PBKDF2 hash to config.yaml under authelia.grafana_oidc_secret_hash"
    log "(deploy to apply)"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        set-jupyter-password) cmd_set_jupyter_password "$@" ;;
        set-grafana-password) cmd_set_grafana_password "$@" ;;
        rotate-agent-upload-token)   cmd_rotate_agent_upload_token "$@" ;;
        rotate-flasher-upload-token) cmd_rotate_flasher_upload_token "$@" ;;
        add-client)           cmd_add_client "$@" ;;
        show-client)          cmd_show_client "$@" ;;
        rm-client)            cmd_rm_client "$@" ;;
        bootstrap-authelia)   cmd_bootstrap_authelia "$@" ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"

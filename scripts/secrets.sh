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

cmd_set_admin_password() {
    ensure_config
    require_cmd docker

    local pw hash
    pw="$(prompt_password "Admin panel password (used at /admin/*)")"
    # Use the official Caddy image's hash-password subcommand to produce a
    # bcrypt hash. We pipe via stdin to avoid the password ever appearing
    # on the process command line.
    hash="$(printf '%s' "$pw" | docker run --rm -i caddy:2 caddy hash-password --plaintext-stdin)"
    [[ "$hash" =~ ^\$2[abxy]\$ ]] || die "hash-password produced unexpected output: $hash"
    yq -i ".siteapp.admin_password_hash = \"$hash\"" "$CONFIG"
    log "set admin panel password (deploy to apply)"
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

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        set-admin-password)   cmd_set_admin_password "$@" ;;
        set-jupyter-password) cmd_set_jupyter_password "$@" ;;
        set-grafana-password) cmd_set_grafana_password "$@" ;;
        add-client)           cmd_add_client "$@" ;;
        show-client)          cmd_show_client "$@" ;;
        rm-client)            cmd_rm_client "$@" ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"

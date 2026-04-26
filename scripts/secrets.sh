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

cmd_add_user() {
    local name="${1:?usage: secrets.sh add-user <name>}"
    ensure_config

    local existing
    existing="$(yq e ".caddy_users[] | select(.name == \"$name\") | .name" "$CONFIG")"
    [[ -z "$existing" ]] || die "user $name already exists (use set-user-password to rotate)"

    local pw hash
    pw="$(prompt_password "Password for $name")"
    hash="$(bcrypt_hash "$pw")"
    yq -i ".caddy_users += [{\"name\": \"$name\", \"password_hash\": \"$hash\"}]" "$CONFIG"
    log "added user $name"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        add-user) cmd_add_user "$@" ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"

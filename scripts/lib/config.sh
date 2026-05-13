#!/usr/bin/env bash
# Load and validate config.yaml + compose/pins.yaml. Sourced, not executed.
# Depends on lib/common.sh being sourced first.
#
# Two-file split:
#   compose/pins.yaml  — image pins, paths, retention, ports, ACME email.
#                        Tracked in git; Renovate-managed; PR-reviewable.
#   config.yaml        — instance-specific values + secrets + roster.
#                        Gitignored; operator-laptop-only.

# Override via LDS_PINS_FILE for tests / CI assembly.
_default_pins_file() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    printf '%s/../../compose/pins.yaml' "$script_dir"
}

# Required fields in config.yaml (post-refactor: shrunk).
_REQUIRED_CONFIG_FIELDS=(
    .vps.host
    .vps.ssh_user
    .jupyter.password_hash
    .siteapp.admin_password_hash
)

# Required fields in pins.yaml.
_REQUIRED_PINS_FIELDS=(
    .jupyter_image
    .chisel_image
    .chisel_listen_port
    .loki_image
    .loki_retention_days
    .grafana_image
    .siteapp_image_repo
    .flasher_image_repo
    .acme_email
    .remote_root
    .notebooks_path
    .ssh_port
)

_yq() { yq "$@" 2>/dev/null; }

# validate_config <config_path> — also validates pins (LDS_PINS_FILE or default).
validate_config() {
    local config_path="${1:?validate_config: missing path arg}"
    local pins_path="${LDS_PINS_FILE:-$(_default_pins_file)}"
    local errors=()

    if [[ ! -f "$config_path" ]]; then
        printf 'config not found: %s\n' "$config_path" >&2
        return 1
    fi
    if [[ ! -f "$pins_path" ]]; then
        printf 'pins file not found: %s (set LDS_PINS_FILE or place at compose/pins.yaml)\n' "$pins_path" >&2
        return 1
    fi

    if ! _yq e '.' "$config_path" >/dev/null; then
        printf 'config is not valid YAML: %s\n' "$config_path" >&2
        return 1
    fi
    if ! _yq e '.' "$pins_path" >/dev/null; then
        printf 'pins is not valid YAML: %s\n' "$pins_path" >&2
        return 1
    fi

    local field val
    for field in "${_REQUIRED_CONFIG_FIELDS[@]}"; do
        val="$(_yq e "$field // \"\"" "$config_path")"
        if [[ -z "$val" || "$val" == "null" ]]; then
            errors+=("config: missing required field: ${field#.}")
        fi
    done
    for field in "${_REQUIRED_PINS_FIELDS[@]}"; do
        val="$(_yq e "$field // \"\"" "$pins_path")"
        if [[ -z "$val" || "$val" == "null" ]]; then
            errors+=("pins: missing required field: ${field#.}")
        fi
    done

    # Password-hash format checks (unchanged).
    local hash
    hash="$(_yq e '.jupyter.password_hash // ""' "$config_path")"
    if [[ -n "$hash" ]] && ! [[ "$hash" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]; then
        errors+=("jupyter.password_hash is not in sha1:<salt>:<digest> format (run: task secrets:set-jupyter-password)")
    fi
    local admin_hash
    admin_hash="$(_yq e '.siteapp.admin_password_hash // ""' "$config_path")"
    if [[ -n "$admin_hash" ]] && ! [[ "$admin_hash" =~ ^\$2[abxy]\$[0-9]{2}\$[A-Za-z0-9./]{53}$ ]]; then
        errors+=("siteapp.admin_password_hash is not a bcrypt hash (run: task secrets:set-admin-password)")
    fi

    # chisel_clients: per-entry validity + duplicate-port check (unchanged).
    local i name count
    count="$(_yq e '.chisel_clients | length' "$config_path")"
    local seen_ports=() port pwd
    for ((i=0; i<count; i++)); do
        name="$(_yq e ".chisel_clients[$i].name" "$config_path")"
        port="$(_yq e ".chisel_clients[$i].reverse_port" "$config_path")"
        pwd="$(_yq e ".chisel_clients[$i].password" "$config_path")"
        [[ -z "$name" || "$name" == "null" ]] && errors+=("chisel_clients[$i].name is empty")
        [[ -z "$port" || "$port" == "null" ]] && errors+=("chisel_clients[$i].reverse_port is empty")
        [[ -z "$pwd"  || "$pwd"  == "null" ]] && errors+=("chisel_clients[$i].password is empty")
        if [[ -n "$port" && "$port" != "null" ]]; then
            for seen in "${seen_ports[@]:-}"; do
                [[ "$seen" == "$port" ]] && errors+=("chisel_clients: duplicate reverse_port $port")
            done
            seen_ports+=("$port")
        fi
    done

    local retention
    retention="$(_yq e '.loki_retention_days // ""' "$pins_path")"
    if [[ -n "$retention" ]] && ! [[ "$retention" =~ ^[0-9]+$ ]]; then
        errors+=("pins.loki_retention_days must be a positive integer, got: $retention")
    fi

    if (( ${#errors[@]} > 0 )); then
        printf 'config validation failed:\n' >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi
    return 0
}

# load_config <config_path> — validate, then export VPS_*, etc. for later use.
load_config() {
    local config_path="${1:?load_config: missing path arg}"
    local pins_path="${LDS_PINS_FILE:-$(_default_pins_file)}"
    validate_config "$config_path" || return 1

    export CONFIG_PATH="$config_path"
    export PINS_PATH="$pins_path"

    # Instance values from config.yaml.
    export VPS_HOST          ; VPS_HOST="$(_yq e '.vps.host' "$config_path")"
    export VPS_SSH_USER      ; VPS_SSH_USER="$(_yq e '.vps.ssh_user' "$config_path")"
    export JUPYTER_PASSWORD_HASH ; JUPYTER_PASSWORD_HASH="$(_yq e '.jupyter.password_hash' "$config_path")"
    export SITEAPP_ADMIN_PASSWORD_HASH ; SITEAPP_ADMIN_PASSWORD_HASH="$(_yq e '.siteapp.admin_password_hash' "$config_path")"

    # Stack pins from pins.yaml.
    export VPS_SSH_PORT      ; VPS_SSH_PORT="$(_yq e '.ssh_port' "$pins_path")"
    export VPS_REMOTE_ROOT   ; VPS_REMOTE_ROOT="$(_yq e '.remote_root' "$pins_path")"
    export VPS_NOTEBOOKS_PATH; VPS_NOTEBOOKS_PATH="$(_yq e '.notebooks_path' "$pins_path")"
    export CADDY_ACME_EMAIL  ; CADDY_ACME_EMAIL="$(_yq e '.acme_email' "$pins_path")"
    export JUPYTER_IMAGE         ; JUPYTER_IMAGE="$(_yq e '.jupyter_image' "$pins_path")"
    export CHISEL_IMAGE          ; CHISEL_IMAGE="$(_yq e '.chisel_image' "$pins_path")"
    export CHISEL_LISTEN_PORT    ; CHISEL_LISTEN_PORT="$(_yq e '.chisel_listen_port' "$pins_path")"
    export LOKI_IMAGE            ; LOKI_IMAGE="$(_yq e '.loki_image' "$pins_path")"
    export LOKI_RETENTION_DAYS   ; LOKI_RETENTION_DAYS="$(_yq e '.loki_retention_days' "$pins_path")"
    export GRAFANA_IMAGE         ; GRAFANA_IMAGE="$(_yq e '.grafana_image' "$pins_path")"
    export SITEAPP_IMAGE_REPO    ; SITEAPP_IMAGE_REPO="$(_yq e '.siteapp_image_repo' "$pins_path")"
    export FLASHER_IMAGE_REPO    ; FLASHER_IMAGE_REPO="$(_yq e '.flasher_image_repo' "$pins_path")"
}

#!/usr/bin/env bash
# Load and validate config.yaml. Sourced, not executed.
# Depends on lib/common.sh being sourced first.

# Required fields (dot-paths in yq syntax). Each must be a non-empty scalar.
_REQUIRED_FIELDS=(
    .vps.host
    .vps.ssh_user
    .vps.ssh_port
    .vps.remote_root
    .vps.notebooks_path
    .caddy.acme_email
    .jupyter.image
    .chisel.image
    .chisel.listen_port
)

_yq() { yq "$@" 2>/dev/null; }

# validate_config <path> — print all problems to stderr, exit non-zero on any.
validate_config() {
    local path="${1:?validate_config: missing path arg}"
    local errors=()

    if [[ ! -f "$path" ]]; then
        printf 'config not found: %s\n' "$path" >&2
        return 1
    fi

    # Parse-ability check.
    if ! _yq e '.' "$path" >/dev/null; then
        printf 'config is not valid YAML: %s\n' "$path" >&2
        return 1
    fi

    # Required scalar fields.
    local field val
    for field in "${_REQUIRED_FIELDS[@]}"; do
        val="$(_yq e "$field // \"\"" "$path")"
        if [[ -z "$val" || "$val" == "null" ]]; then
            errors+=("missing required field: ${field#.}")
        fi
    done

    # caddy_users password_hash format check (bcrypt: $2[aby]$NN$<50 chars>).
    local i name hash
    local count
    count="$(_yq e '.caddy_users | length' "$path")"
    for ((i=0; i<count; i++)); do
        name="$(_yq e ".caddy_users[$i].name" "$path")"
        hash="$(_yq e ".caddy_users[$i].password_hash" "$path")"
        if [[ -z "$name" || "$name" == "null" ]]; then
            errors+=("caddy_users[$i].name is empty")
        fi
        if ! [[ "$hash" =~ ^\$2[aby]\$[0-9]{2}\$.{50}$ ]]; then
            errors+=("caddy_users[$i].password_hash is not a valid bcrypt hash")
        fi
    done

    # chisel_clients: per-entry validity + duplicate-port check.
    count="$(_yq e '.chisel_clients | length' "$path")"
    local seen_ports=() port pwd
    for ((i=0; i<count; i++)); do
        name="$(_yq e ".chisel_clients[$i].name" "$path")"
        port="$(_yq e ".chisel_clients[$i].reverse_port" "$path")"
        pwd="$(_yq e ".chisel_clients[$i].password" "$path")"
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

    if (( ${#errors[@]} > 0 )); then
        printf 'config validation failed:\n' >&2
        printf '  - %s\n' "${errors[@]}" >&2
        return 1
    fi
    return 0
}

# load_config <path> — validate, then export VPS_*, CADDY_*, etc. for later use.
load_config() {
    local path="${1:?load_config: missing path arg}"
    validate_config "$path" || return 1
    export CONFIG_PATH="$path"
    export VPS_HOST          ; VPS_HOST="$(_yq e '.vps.host' "$path")"
    export VPS_SSH_USER      ; VPS_SSH_USER="$(_yq e '.vps.ssh_user' "$path")"
    export VPS_SSH_PORT      ; VPS_SSH_PORT="$(_yq e '.vps.ssh_port' "$path")"
    export VPS_REMOTE_ROOT   ; VPS_REMOTE_ROOT="$(_yq e '.vps.remote_root' "$path")"
    export VPS_NOTEBOOKS_PATH; VPS_NOTEBOOKS_PATH="$(_yq e '.vps.notebooks_path' "$path")"
    export CADDY_ACME_EMAIL  ; CADDY_ACME_EMAIL="$(_yq e '.caddy.acme_email' "$path")"
    export JUPYTER_IMAGE     ; JUPYTER_IMAGE="$(_yq e '.jupyter.image' "$path")"
    export CHISEL_IMAGE      ; CHISEL_IMAGE="$(_yq e '.chisel.image' "$path")"
    export CHISEL_LISTEN_PORT; CHISEL_LISTEN_PORT="$(_yq e '.chisel.listen_port' "$path")"
}

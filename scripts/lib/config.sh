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
# NOTE: .jupyter.password_hash is kept here as a deprecated key for one more
# release. It will be removed once every operator has cleared the value.
_REQUIRED_CONFIG_FIELDS=(
    .vps.host
    .vps.ssh_user
    .jupyter.password_hash
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
    .streamer_image_repo
    .caddy_image_repo
    .authelia_image_repo
    .authelia_image
    .acme_email
    .remote_root
    .notebooks_path
    .ssh_port
    .prometheus_image
    .node_exporter_image
    .cadvisor_image
    .prometheus_retention_days
    .studio_image
)

# Optional-service selection (spec: 2026-07-17-service-selection-design.md).
# The ONLY names an operator may list in config.yaml's disabled_services.
# `monitoring` is a group name expanding to the five observability compose
# services. Core services are deliberately absent — the platform cannot
# run without them.
_OPTIONAL_SERVICES=(jupyter monitoring studio streamer flasher)
_CORE_SERVICES=(caddy authelia siteapp chisel)
_MONITORING_COMPOSE_SERVICES=(grafana loki prometheus node-exporter cadvisor)

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

    # Password-hash format checks.
    # jupyter.password_hash: deprecated — Authelia now gates Jupyter via forward_auth.
    # Allow empty (operators migrating away) but reject a set value in wrong format.
    local hash
    hash="$(_yq e '.jupyter.password_hash // ""' "$config_path")"
    if [[ -n "$hash" ]] && ! [[ "$hash" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]; then
        errors+=("jupyter.password_hash is set but not in sha1 format; clear it or run task secrets:set-jupyter-password")
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

    # disabled_services: every entry must be a known optional service name.
    local ds_count j entry opt known core
    local seen_ds=()
    ds_count="$(_yq e '.disabled_services | length' "$config_path")"
    for ((j=0; j<ds_count; j++)); do
        entry="$(_yq e ".disabled_services[$j]" "$config_path")"
        known=false
        for opt in "${_OPTIONAL_SERVICES[@]}"; do
            [[ "$entry" == "$opt" ]] && known=true
        done
        if ! $known; then
            core=false
            for opt in "${_CORE_SERVICES[@]}"; do
                [[ "$entry" == "$opt" ]] && core=true
            done
            if $core; then
                errors+=("disabled_services: '$entry' is a core service and cannot be disabled")
            else
                errors+=("disabled_services: unknown service '$entry' (allowed: ${_OPTIONAL_SERVICES[*]})")
            fi
        fi
        for seen in "${seen_ds[@]:-}"; do
            [[ "$seen" == "$entry" ]] && errors+=("disabled_services: duplicate entry '$entry'")
        done
        seen_ds+=("$entry")
    done

    local retention
    retention="$(_yq e '.loki_retention_days // ""' "$pins_path")"
    if [[ -n "$retention" ]] && ! [[ "$retention" =~ ^[0-9]+$ ]]; then
        errors+=("pins.loki_retention_days must be a positive integer, got: $retention")
    fi

    local prom_retention
    prom_retention="$(_yq e '.prometheus_retention_days // ""' "$pins_path")"
    if [[ -n "$prom_retention" ]] && ! [[ "$prom_retention" =~ ^[0-9]+$ ]]; then
        errors+=("pins.prometheus_retention_days must be a positive integer, got: $prom_retention")
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
    export VPS_PUBLIC_IP     ; VPS_PUBLIC_IP="$(_yq e '.vps_public_ip // .vps.host' "$config_path")"
    export JUPYTER_PASSWORD_HASH ; JUPYTER_PASSWORD_HASH="$(_yq e '.jupyter.password_hash // ""' "$config_path")"

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
    export STUDIO_IMAGE          ; STUDIO_IMAGE="$(_yq e '.studio_image' "$pins_path")"
    export PROMETHEUS_IMAGE      ; PROMETHEUS_IMAGE="$(_yq e '.prometheus_image' "$pins_path")"
    export NODE_EXPORTER_IMAGE   ; NODE_EXPORTER_IMAGE="$(_yq e '.node_exporter_image' "$pins_path")"
    export CADVISOR_IMAGE        ; CADVISOR_IMAGE="$(_yq e '.cadvisor_image' "$pins_path")"
    export PROMETHEUS_RETENTION_DAYS ; PROMETHEUS_RETENTION_DAYS="$(_yq e '.prometheus_retention_days' "$pins_path")"
    export SITEAPP_IMAGE_REPO    ; SITEAPP_IMAGE_REPO="$(_yq e '.siteapp_image_repo' "$pins_path")"
    export FLASHER_IMAGE_REPO    ; FLASHER_IMAGE_REPO="$(_yq e '.flasher_image_repo' "$pins_path")"
    export STREAMER_IMAGE_REPO   ; STREAMER_IMAGE_REPO="$(_yq e '.streamer_image_repo' "$pins_path")"
    export CADDY_IMAGE_REPO      ; CADDY_IMAGE_REPO="$(_yq e '.caddy_image_repo' "$pins_path")"
    export AUTHELIA_IMAGE_REPO   ; AUTHELIA_IMAGE_REPO="$(_yq e '.authelia_image_repo' "$pins_path")"
    export AUTHELIA_IMAGE        ; AUTHELIA_IMAGE="$(_yq e '.authelia_image' "$pins_path")"
    export AUTHELIA_GRAFANA_OIDC_SECRET_HASH ; AUTHELIA_GRAFANA_OIDC_SECRET_HASH="$(_yq e '.authelia.grafana_oidc_secret_hash // ""' "$config_path")"

    # Optional-service selection. DISABLED_SERVICES carries the raw group
    # names (probe/secret/Caddyfile gating); DISABLED_COMPOSE_SERVICES the
    # compose-level expansion (filter_compose).
    export DISABLED_SERVICES
    DISABLED_SERVICES="$(_yq e '(.disabled_services // [])[]' "$config_path" | tr '\n' ' ' | sed 's/ *$//')"
    local _dcs="" _svc
    for _svc in $DISABLED_SERVICES; do
        if [[ "$_svc" == "monitoring" ]]; then
            _dcs+=" ${_MONITORING_COMPOSE_SERVICES[*]}"
        else
            _dcs+=" $_svc"
        fi
    done
    export DISABLED_COMPOSE_SERVICES
    DISABLED_COMPOSE_SERVICES="${_dcs# }"
}

# service_disabled <name> — succeed when <name> (a GROUP name like
# "monitoring", never a compose-level name like "grafana") is disabled.
# Requires load_config to have run.
service_disabled() {
    local svc
    for svc in ${DISABLED_SERVICES:-}; do
        [[ "$svc" == "$1" ]] && return 0
    done
    return 1
}

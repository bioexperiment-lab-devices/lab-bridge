#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
# shellcheck source=lib/render.sh
source "$SCRIPT_DIR/lib/render.sh"

CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
_STAGE=""

main() {
    [[ -f "$CONFIG" ]] || die "config not found: $CONFIG (cp config.example.yaml config.yaml)"
    load_config "$CONFIG"

    # 1. Render to a staging dir.
    _STAGE="$(mktemp -d)"
    trap 'rm -rf "$_STAGE"' EXIT
    local stage="$_STAGE"

    log "rendering templates..."
    mkdir -p "$stage/chisel"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"

    # 2. Build SSH/rsync.
    local ssh_base rsync_e target
    ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    rsync_e="$ssh_base"
    target="$VPS_SSH_USER@$VPS_HOST"

    # 3. Rsync. --delete with excludes for Caddy's runtime state (issued certs
    # in caddy_data/ and adapter cache in caddy_config/, both owned by root
    # inside the container).
    log "rsyncing to $target:$VPS_REMOTE_ROOT/ ..."
    rsync -az --delete \
        --exclude='caddy_data/' \
        --exclude='caddy_config/' \
        -e "$rsync_e" \
        "$stage/" "$target:$VPS_REMOTE_ROOT/"

    # 4. docker compose up. Always restart caddy because the bind-mounted
    # Caddyfile may have been replaced (atomic rename → new inode → caddy's
    # already-loaded reference goes stale; `up -d` doesn't recreate containers
    # whose compose-config didn't change).
    log "bringing up the stack..."
    $ssh_base "$target" "cd $VPS_REMOTE_ROOT && docker compose pull && docker compose up -d --remove-orphans && docker compose restart caddy"

    # 5. Health check (skippable for tests). JupyterLab serves either 200
    # (login page if no session) or 302 (redirect to /login) when its password
    # auth is configured — anything in 2xx/3xx means TLS + reverse_proxy + jupyter
    # are all up.
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond..."
        local i status
        for ((i=0; i<60; i++)); do
            status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            if [[ "$status" =~ ^[23][0-9][0-9]$ ]]; then
                log "deployed at https://$VPS_HOST/ (HTTP $status)"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (last status: $status). Check: task logs -- caddy"
        return 1
    fi
    log "deployed (healthcheck skipped)"
}

main "$@"

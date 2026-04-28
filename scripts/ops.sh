#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"

CONFIG="${LDS_CONFIG:-$REPO_ROOT/config.yaml}"

# Build SSH command honoring test env vars.
build_ssh() {
    local ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    printf '%s' "$ssh_base"
}

remote_compose() {
    local args="$*"
    local ssh_base
    ssh_base="$(build_ssh)"
    $ssh_base "$VPS_SSH_USER@$VPS_HOST" "cd $VPS_REMOTE_ROOT && docker compose $args"
}

cmd_ps()       { load_config "$CONFIG"; remote_compose ps; }
cmd_restart()  { load_config "$CONFIG"; remote_compose restart; }
cmd_down()     { load_config "$CONFIG"; remote_compose down; }
cmd_destroy()  {
    load_config "$CONFIG"
    warn "this will remove containers AND volumes (caddy_data certs are preserved as a bind mount, but other state is gone)"
    remote_compose down -v
}

cmd_logs() {
    load_config "$CONFIG"
    # No -f: print the recent tail and return. Operators wanting to follow
    # can: task ssh, then `cd /srv/lab-bridge && docker compose logs -f`.
    local svc="${1:-}"
    if [[ -n "$svc" ]]; then
        remote_compose "logs --tail=200 $svc"
    else
        remote_compose "logs --tail=200"
    fi
}

cmd_logs_loki()    { load_config "$CONFIG"; remote_compose "logs --tail=200 loki"; }
cmd_logs_grafana() { load_config "$CONFIG"; remote_compose "logs --tail=200 grafana"; }

cmd_loki_disk() {
    load_config "$CONFIG"
    local ssh_base
    ssh_base="$(build_ssh)"
    # du -sh on the VPS, then echo the configured retention so the operator
    # has both numbers in one place.
    $ssh_base "$VPS_SSH_USER@$VPS_HOST" \
        "du -sh $VPS_REMOTE_ROOT/loki_data 2>/dev/null || echo '0  $VPS_REMOTE_ROOT/loki_data (missing)'"
    log "configured retention: ${LOKI_RETENTION_DAYS} days"
}

cmd_ssh() {
    load_config "$CONFIG"
    local ssh_base
    ssh_base="$(build_ssh)"
    exec $ssh_base "$VPS_SSH_USER@$VPS_HOST"
}

cmd_backup() {
    load_config "$CONFIG"
    local ssh_base ts dest
    ssh_base="$(build_ssh)"
    ts="$(date +%Y%m%d-%H%M%S)"
    dest="./backups/notebooks-$ts"
    mkdir -p "$dest"
    log "rsyncing $VPS_NOTEBOOKS_PATH/ -> $dest/"
    # Use sudo on the remote because /srv/jupyterlab/work is owned by uid 1000.
    rsync -az --rsync-path='sudo rsync' -e "$ssh_base" \
        "$VPS_SSH_USER@$VPS_HOST:$VPS_NOTEBOOKS_PATH/" "$dest/"
    log "backed up to $dest/"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        ps)            cmd_ps ;;
        logs)          cmd_logs "$@" ;;
        logs:loki)     cmd_logs_loki ;;
        logs:grafana)  cmd_logs_grafana ;;
        loki-disk)     cmd_loki_disk ;;
        ssh)           cmd_ssh ;;
        restart)       cmd_restart ;;
        down)          cmd_down ;;
        destroy)       cmd_destroy ;;
        backup)        cmd_backup ;;
        *) die "unknown subcommand: $sub" ;;
    esac
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"

CONFIG="${LDS_CONFIG:-$SCRIPT_DIR/../config.yaml}"

main() {
    load_config "$CONFIG"

    # Build SSH command (allow tests to inject key + opts).
    local ssh_base
    ssh_base="ssh -p $VPS_SSH_PORT"
    [[ -n "${LDS_SSH_KEY:-}" ]] && ssh_base="$ssh_base -i $LDS_SSH_KEY"
    [[ -n "${LDS_SSH_OPTS:-}" ]] && ssh_base="$ssh_base $LDS_SSH_OPTS"
    local target="$VPS_SSH_USER@$VPS_HOST"

    # 1. Reachability.
    log "checking SSH reachability..."
    $ssh_base -o BatchMode=yes -o ConnectTimeout=10 "$target" true \
        || die "cannot SSH to $target — check vps.host / vps.ssh_user / vps.ssh_port"

    # 2. Run remote provisioning script via stdin.
    log "running remote provisioning..."
    local remote_chisel_port="$CHISEL_LISTEN_PORT"
    local remote_root="$VPS_REMOTE_ROOT"
    local notebooks="$VPS_NOTEBOOKS_PATH"

    $ssh_base "$target" \
        "REMOTE_ROOT='$remote_root' NOTEBOOKS_PATH='$notebooks' CHISEL_PORT='$remote_chisel_port' bash -s" <<'REMOTE'
set -euo pipefail

log()  { printf '[remote] %s\n' "$*" >&2; }

# 1. Docker
if ! command -v docker >/dev/null 2>&1; then
    log "installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
fi
docker --version

# Start dockerd if not running (handles non-systemd containers like the fake-VPS).
if ! sudo docker info >/dev/null 2>&1; then
    log "starting dockerd..."
    # Use vfs storage driver in nested container environments where overlayfs
    # is not available (e.g. Docker-in-Docker on macOS Docker Desktop).
    sudo dockerd --host=unix:///var/run/docker.sock \
        --storage-driver=vfs \
        --log-level=error &>/tmp/dockerd.log &
    # Wait up to 30 s for the socket to appear.
    for _i in $(seq 1 30); do
        sudo docker info >/dev/null 2>&1 && break
        sleep 1
    done
    sudo docker info >/dev/null 2>&1 || { cat /tmp/dockerd.log >&2; exit 1; }
    log "dockerd started (vfs storage driver)"
fi

# 2. ufw
if ! command -v ufw >/dev/null 2>&1; then
    log "installing ufw..."
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw
fi
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow "${CHISEL_PORT:?}"/tcp
sudo ufw --force enable

# 3. Directories. JupyterLab containers run as UID 1000 (jovyan).
# Loki and Grafana run as their own non-root UIDs and need to write
# to the bind-mounted state dirs.
sudo mkdir -p \
    "$REMOTE_ROOT" \
    "$REMOTE_ROOT/chisel" \
    "$REMOTE_ROOT/caddy_data" \
    "$REMOTE_ROOT/loki_data" \
    "$REMOTE_ROOT/grafana_data" \
    "$REMOTE_ROOT/site_data" \
    "$NOTEBOOKS_PATH"
sudo chown -R "$USER:$USER" "$REMOTE_ROOT"
sudo chown -R 1000:100 "$NOTEBOOKS_PATH"
sudo chmod 775 "$NOTEBOOKS_PATH"
# Loki uses 10001 (grafana/loki image's "loki" user).
sudo chown -R 10001:10001 "$REMOTE_ROOT/loki_data"
# Grafana uses 472 ("grafana" user in grafana/grafana).
sudo chown -R 472:472   "$REMOTE_ROOT/grafana_data"
# siteapp also uses uid 10001 (matching the Dockerfile's `siteapp` user).
# Distinct directory from loki_data so the two services don't share state.
sudo chown -R 10001:10001 "$REMOTE_ROOT/site_data"
log "ok"
REMOTE

    log "provisioned. next: task deploy"
}

main "$@"

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
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"
    render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"

    # Static Grafana provisioning — datasource + dashboard provider + dashboard JSON.
    cp -R "$REPO_ROOT/compose/grafana/provisioning/." "$stage/grafana/provisioning/"

    # Grafana admin password file (created by `task secrets:set-grafana-password`).
    # Mode 0644 on the staged/deployed file: Docker Compose bind-mounts it to
    # /run/secrets/grafana_admin_password inside the container, where Grafana
    # runs as uid 472 and cannot read a 0600 file owned by the deploy user.
    # The local copy in compose/grafana/admin_password stays 0600 — only the
    # deploy artifact on the private VPS path is loosened.
    local pwfile="${LDS_GRAFANA_PASSWORD_FILE:-$REPO_ROOT/compose/grafana/admin_password}"
    [[ -f "$pwfile" ]] || die "grafana admin password not found at $pwfile — run: task secrets:set-grafana-password"
    install -m 644 "$pwfile" "$stage/grafana/admin_password"

    # Agent upload token — required at deploy time. Like the Grafana password,
    # this lands as a Docker secret on the VPS. Mode 0644 because the secret
    # is bind-mounted into a container that runs as a non-root uid.
    local tokfile="${LDS_AGENT_TOKEN_FILE:-$REPO_ROOT/compose/siteapp/agent_upload_token}"
    [[ -f "$tokfile" ]] || die "agent upload token not found at $tokfile — run: task secrets:rotate-agent-upload-token"
    mkdir -p "$stage/siteapp"
    install -m 644 "$tokfile" "$stage/siteapp/agent_upload_token"

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
        --exclude='loki_data/' \
        --exclude='grafana_data/' \
        -e "$rsync_e" \
        "$stage/" "$target:$VPS_REMOTE_ROOT/"

    # 4. docker compose up. Always restart caddy and chisel because their
    # bind-mounted config files (Caddyfile, chisel/users.json) may have been
    # replaced by rsync (atomic rename → new inode → the already-loaded
    # reference inside the container goes stale; `up -d` doesn't recreate
    # containers whose compose-config didn't change, and a single-file bind
    # mount pins the original inode so even fsnotify-based auto-reload
    # re-reads the same stale contents).
    log "bringing up the stack..."
    $ssh_base "$target" "cd $VPS_REMOTE_ROOT && docker compose pull && docker compose up -d --remove-orphans && docker compose restart caddy chisel siteapp"

    # 5. Health check (skippable for tests). Probe both routed paths:
    # `/` (JupyterLab → 200/302) and `/grafana/login` (Grafana → 200, terminal,
    # no redirect). Probing a terminal page rather than `/grafana/` itself is
    # deliberate: a 3xx-only check passes a redirect loop (e.g. when the proxy
    # is misconfigured to strip the sub-path Grafana expects to receive),
    # which 200-on-login does not.
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond..."
        local i jupyter_status grafana_status docs_status download_status admin_status
        for ((i=0; i<60; i++)); do
            jupyter_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            grafana_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/grafana/login" || true)"
            docs_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/docs/" || true)"
            download_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/download/agent" || true)"
            admin_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/admin/" || true)"
            # /admin/ MUST be 401 without creds. A 200 here is a security regression.
            if [[ "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "200" ]] \
                && [[ "$docs_status" == "200" ]] \
                && [[ "$download_status" == "200" ]] \
                && [[ "$admin_status" == "401" ]]; then
                log "deployed: jupyter $jupyter_status, grafana $grafana_status, docs $docs_status, download $download_status, admin $admin_status"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (jupyter:$jupyter_status grafana:$grafana_status docs:$docs_status download:$download_status admin:$admin_status). Check: task logs"
        return 1
    fi
    log "deployed (healthcheck skipped)"
}

main "$@"

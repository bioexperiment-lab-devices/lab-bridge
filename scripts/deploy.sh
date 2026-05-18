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

    # Stack-only mode: CI deploys do not touch the chisel/siteapp client roster.
    # Guard against roster data leaking into a stack-only config.
    if [[ "${LDS_STACK_ONLY:-}" == "1" && "${LDS_REQUIRE_VAULT:-}" == "1" ]]; then
        local roster_count
        roster_count="$(yq e '.chisel_clients | length' "$CONFIG")"
        if [[ "$roster_count" != "0" ]]; then
            die "LDS_REQUIRE_VAULT=1: chisel_clients must be empty in stack-only mode (got $roster_count entries)"
        fi
    fi

    # 1. Render to a staging dir.
    _STAGE="$(mktemp -d)"
    trap 'rm -rf "$_STAGE"' EXIT
    local stage="$_STAGE"

    log "rendering templates..."
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning" "$stage/siteapp" "$stage/shell" "$stage/prometheus"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    if [[ "${LDS_STACK_ONLY:-}" != "1" ]]; then
        render_chisel_users "$stage/chisel/users.json"
        render_siteapp_clients "$stage/siteapp/clients.json"
    fi
    render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"
    render_prometheus_config "$REPO_ROOT/compose/prometheus/prometheus.yml.tmpl" "$stage/prometheus/prometheus.yml"

    # Static Grafana provisioning — datasource + dashboard provider + dashboard JSON.
    cp -R "$REPO_ROOT/compose/grafana/provisioning/." "$stage/grafana/provisioning/"

    # Platform shell assets — navbar.js, navbar-inner.css. Mounted into the
    # custom Caddy image at /srv/shell so the file_server route /_shared/*
    # can serve them. Fail loud if the directory is missing (would otherwise
    # silently succeed on macOS and fail on Linux — inconsistent).
    [[ -d "$REPO_ROOT/compose/shell" ]] || die "compose/shell/ is missing — platform navbar assets not staged"
    cp -R "$REPO_ROOT/compose/shell/." "$stage/shell/"

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

    # Flasher upload token — required at deploy time. Same pattern as the agent
    # upload token above: bind-mounted Docker secret, mode 0644 on the staged copy.
    local flashertokfile="${LDS_FLASHER_UPLOAD_TOKEN_FILE:-$REPO_ROOT/compose/flasher/upload_token}"
    [[ -f "$flashertokfile" ]] || die "flasher upload token not found at $flashertokfile — run: task secrets:rotate-flasher-upload-token"
    mkdir -p "$stage/flasher"
    install -m 644 "$flashertokfile" "$stage/flasher/upload_token"

    # Public docs — tracked in git at repo root, copied into the staged
    # tree so the existing rsync ships them to ~/lab-bridge/siteapp/docs/
    # on the VPS, where compose mounts them read-only at /srv/docs.
    mkdir -p "$stage/siteapp/docs"
    cp -R "$REPO_ROOT/public_docs/." "$stage/siteapp/docs/"

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
    local rsync_excludes=(
        --exclude='caddy_data/'
        --exclude='caddy_config/'
        --exclude='loki_data/'
        --exclude='grafana_data/'
        --exclude='site_data/'
        --exclude='flasher_data/'
    )
    if [[ "${LDS_STACK_ONLY:-}" == "1" ]]; then
        rsync_excludes+=(--exclude='chisel/users.json' --exclude='siteapp/clients.json')
    fi
    rsync -az --delete "${rsync_excludes[@]}" -e "$rsync_e" "$stage/" "$target:$VPS_REMOTE_ROOT/"

    # Always restart caddy, siteapp, grafana, and (in full mode) chisel
    # because their bind-mounted config files may have been replaced by rsync
    # (atomic rename → new inode → the already-loaded reference inside the
    # container goes stale; `up -d` doesn't recreate containers whose
    # compose-config didn't change, and a single-file bind mount pins the
    # original inode so even fsnotify-based auto-reload re-reads the same
    # stale contents).
    # - caddy: Caddyfile
    # - siteapp: siteapp/agent_upload_token
    # - chisel: chisel/users.json (full mode only)
    # - grafana: grafana/provisioning/{datasources,dashboards}/* — datasource
    #   provisioning runs at startup only, so adding/changing a datasource
    #   (e.g. the Prometheus addition in v0.10.0) requires a bounce. Without
    #   it, dashboards silently load with "No data" because the provisioned
    #   datasource isn't registered in Grafana's in-memory state.
    # Flasher is intentionally excluded: it reads siteapp/clients.json on
    # every request (see services/flasher/app/routes.py), so a roster change
    # is picked up without a restart.
    log "bringing up the stack..."
    local restart_services="caddy siteapp grafana"
    if [[ "${LDS_STACK_ONLY:-}" != "1" ]]; then
        restart_services="caddy chisel siteapp grafana"
    fi
    $ssh_base "$target" "cd $VPS_REMOTE_ROOT && (docker compose pull --ignore-pull-failures || true) && docker compose up -d --remove-orphans && docker compose restart $restart_services"

    # 5. Health check (skippable for tests). Probe both routed paths:
    # `/` (JupyterLab → 200/302) and `/grafana/login` (Grafana → 200, terminal,
    # no redirect). Probing a terminal page rather than `/grafana/` itself is
    # deliberate: a 3xx-only check passes a redirect loop (e.g. when the proxy
    # is misconfigured to strip the sub-path Grafana expects to receive),
    # which 200-on-login does not.
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond..."
        local i jupyter_status grafana_status docs_status download_status flash_status static_status public_status server_info_status
        for ((i=0; i<60; i++)); do
            jupyter_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            grafana_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/grafana/login" || true)"
            docs_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/docs/" || true)"
            download_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/download/agent" || true)"
            flash_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/flash/" || true)"
            # /_static/site.css must reach siteapp (not the jupyter catchall) or
            # every siteapp page renders unstyled. Probe one known asset.
            static_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/_static/site.css" || true)"
            # /api/public/health is unauthenticated and always returns 200; a
            # non-200 means Caddy's /api/public* handle is misconfigured or
            # siteapp didn't restart cleanly. Confirms the new public surface
            # is wired before we declare the deploy successful.
            public_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/api/public/health" || true)"
            # /api/public/server-info publishes the chisel listen port + loki/tunnel
            # topology. A non-200 means SITEAPP_CHISEL_LISTEN_PORT didn't reach
            # siteapp or the router wasn't mounted. Probed alongside /api/public/health
            # so a broken render fails the deploy.
            server_info_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/api/public/server-info" || true)"
            if [[ "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "200" ]] \
                && [[ "$docs_status" == "200" ]] \
                && [[ "$download_status" == "200" ]] \
                && [[ "$flash_status" == "401" ]] \
                && [[ "$static_status" == "200" ]] \
                && [[ "$public_status" == "200" ]] \
                && [[ "$server_info_status" == "200" ]]; then
                log "deployed: jupyter $jupyter_status, grafana $grafana_status, docs $docs_status, download $download_status, flash $flash_status, static $static_status, public $public_status, server_info $server_info_status"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (jupyter:$jupyter_status grafana:$grafana_status docs:$docs_status download:$download_status flash:$flash_status static:$static_status public:$public_status server_info:$server_info_status). Check: task logs"
        return 1
    fi
    log "deployed (healthcheck skipped)"
}

main "$@"

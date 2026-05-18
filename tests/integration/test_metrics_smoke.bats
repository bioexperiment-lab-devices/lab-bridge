#!/usr/bin/env bats
# Metrics-smoke — one fake-VPS bring-up, asserts Prometheus's view of every
# scrape target. The platform-level "everything wires together" tier for the
# metrics stack. Behavior assertions (specific PromQL outputs, dashboard
# panels) are intentionally not here.

load helpers

# Helper — poll Prometheus's /-/ready inside the fake VPS until 200 or timeout.
wait_prometheus_ready() {
    local i status
    for ((i=0; i<60; i++)); do
        status="$(docker exec lds-fake-vps bash -c "cd /srv/lab-bridge && docker compose exec -T prometheus wget -qO- -S http://localhost:9090/-/ready 2>&1 | awk '/HTTP/ {print \$2}' | head -n1")"
        if [[ "$status" == "200" ]]; then
            return 0
        fi
        sleep 1
    done
    echo "prometheus never became ready: last status='$status'"
    return 1
}

# Helper — fetch the Prometheus targets API as JSON.
_targets_json() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T prometheus wget -qO- 'http://localhost:9090/api/v1/targets?state=active'
    "
}

setup_file() {
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi
    bash "$ROOT/tests/integration/fake_vps/start.sh"
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    printf 'flasher-smoke-tok' > "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE" "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    load_siteapp_test_image
    load_flasher_test_image
    load_caddy_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_prometheus_ready
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

@test "prometheus: every expected scrape target reports health=up" {
    json="$(_targets_json)"
    [[ -n "$json" ]] || { echo "no targets JSON returned"; false; }
    # Required jobs that MUST be up. jupyter is asserted separately because
    # the scipy-notebook image's /metrics behavior is image-version-dependent.
    for job in prometheus node-exporter cadvisor caddy; do
        health="$(echo "$json" | jq -r --arg j "$job" '.data.activeTargets[] | select(.labels.job == $j) | .health' | head -n1)"
        [[ "$health" == "up" ]] || { echo "job=$job health=$health"; echo "$json" | jq '.data.activeTargets[] | select(.labels.job == "'$job'") | {scrapeUrl, health, lastError}'; false; }
    done
}

@test "prometheus: caddy /metrics is reachable (admin :2019 directive works)" {
    json="$(_targets_json)"
    last_error="$(echo "$json" | jq -r '.data.activeTargets[] | select(.labels.job == "caddy") | .lastError' | head -n1)"
    [[ -z "$last_error" || "$last_error" == "null" ]] || { echo "caddy lastError=$last_error"; false; }
}

@test "prometheus: jupyter /metrics is either up OR cleanly removed from config" {
    # Best-effort assertion: if the jupyter job is present, it must be up.
    # If it's absent (fallback kicked in), the test passes trivially.
    json="$(_targets_json)"
    jupyter_present="$(echo "$json" | jq -r '.data.activeTargets[] | select(.labels.job == "jupyter") | .health' | head -n1)"
    if [[ -n "$jupyter_present" && "$jupyter_present" != "null" ]]; then
        [[ "$jupyter_present" == "up" ]] || { echo "jupyter scrape job present but health=$jupyter_present"; false; }
    fi
    true
}

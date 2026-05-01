#!/usr/bin/env bats

load helpers

setup_file() {
    bash "$ROOT/tests/fake_vps/start.sh"
}
teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1   # tests don't need full TLS up; just deploy
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
}
teardown() { teardown_tmpdir; }

@test "deploy: rsyncs templates and brings up containers" {
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab-bridge/docker-compose.yml
    docker exec lds-fake-vps test -f /srv/lab-bridge/Caddyfile
    docker exec lds-fake-vps test -f /srv/lab-bridge/chisel/users.json
    # nested docker compose ps shows three services up
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose ps --status running --format "{{.Service}}"
    ' | sort | tr -d "\r" | grep -E "^(caddy|jupyter|chisel)$" | wc -l | grep -q 3
}

@test "deploy: rsync --delete preserves caddy_data" {
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps bash -c 'echo testdata > /srv/lab-bridge/caddy_data/marker'
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps test -f /srv/lab-bridge/caddy_data/marker
}

@test "deploy: rejects config with invalid hash before touching VPS" {
    cp "$ROOT/tests/fixtures/bad_hash_config.yaml" "$LDS_CONFIG"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$LDS_CONFIG"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]]
}

@test "deploy: stages loki config, grafana provisioning, and admin_password" {
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab-bridge/loki/config.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/admin_password
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/datasources/loki.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/dashboards/lab-bridge.yaml
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana/provisioning/dashboards/client-logs.json
    # rendered loki config substitutes retention hours
    run docker exec lds-fake-vps grep -F 'retention_period: 720h' /srv/lab-bridge/loki/config.yaml
    [ "$status" -eq 0 ]
}

@test "deploy: rsync --delete preserves loki_data and grafana_data" {
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps bash -c 'sudo mkdir -p /srv/lab-bridge/loki_data /srv/lab-bridge/grafana_data'
    docker exec lds-fake-vps bash -c 'echo loki-marker | sudo tee /srv/lab-bridge/loki_data/marker > /dev/null'
    docker exec lds-fake-vps bash -c 'echo grafana-marker | sudo tee /srv/lab-bridge/grafana_data/marker > /dev/null'
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps test -f /srv/lab-bridge/loki_data/marker
    docker exec lds-fake-vps test -f /srv/lab-bridge/grafana_data/marker
}

@test "deploy: fails fast when grafana admin_password is missing" {
    # Override shared setup's password file so the lookup fails.
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"set-grafana-password"* ]] || [[ "$output" == *"admin_password"* ]]
}

@test "deploy: loki and grafana come up healthy on the fake VPS" {
    # Password file already provided by shared setup().
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    # All five compose services should be in `running` state.
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose ps --status running --format "{{.Service}}"
    ' | sort | tr -d "\r" | grep -E "^(caddy|jupyter|chisel|loki|grafana)$" | wc -l | tr -d "[:space:]" | grep -q "^5$"

    # Loki readiness: poll for up to 60 s. wget exits 0 when /ready returns 200.
    local i
    for i in $(seq 1 60); do
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T loki wget -q -O - http://localhost:3100/ready
        ' >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose exec -T loki wget -q -O - http://localhost:3100/ready
    ' >/dev/null
}

@test "deploy: fails fast when agent_upload_token is missing" {
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"rotate-agent-upload-token"* ]]
}

@test "deploy: stages siteapp/agent_upload_token" {
    # Gated on `docker compose pull` reaching the configured siteapp.image. The
    # fixture points at ghcr.io/test/lab-bridge-siteapp:0.0.1 (an unpublishable
    # name) so the fake_vps daemon — which has its own image cache, separate
    # from the host — cannot pull it. The end-to-end smoke check in Task 27
    # covers this path against a real GHCR build. See Task 20 step 4.
    skip "siteapp.image fixture is unpullable from fake_vps; covered by Task 27 smoke"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab-bridge/siteapp/agent_upload_token
}

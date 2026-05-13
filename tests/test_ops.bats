#!/usr/bin/env bats

load helpers

setup_file() {
    bash "$ROOT/tests/fake_vps/start.sh"
    # Run the one-time-per-file provisioning and image loading here so each
    # per-test setup() doesn't repeat the expensive Docker install + image build.
    # A shared tmpdir is used for secrets files (loaded into the test env below).
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
    # provision.sh installs Docker inside the fake-VPS; must happen before
    # load_siteapp_test_image (which uses `docker exec ... docker load`).
    bash "$ROOT/scripts/provision.sh"
    load_siteapp_test_image
    load_flasher_test_image
    preload_fake_vps_images
    export _OPS_TMPDIR="$TMPDIR"
}
teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
    if [[ -n "${_OPS_TMPDIR:-}" && -d "$_OPS_TMPDIR" ]]; then
        rm -rf "$_OPS_TMPDIR"
    fi
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    # ssh_port is now a pins.yaml value; create a test-specific pins with port 2222.
    cp "$ROOT/tests/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
    # Docker is already installed and siteapp image pre-loaded by setup_file().
    # provision.sh is idempotent — this is fast on subsequent calls.
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

@test "ops ps: lists running services" {
    run bash "$ROOT/scripts/ops.sh" ps
    [ "$status" -eq 0 ]
    [[ "$output" == *"caddy"* ]]
    [[ "$output" == *"jupyter"* ]]
    [[ "$output" == *"chisel"* ]]
}

@test "ops logs: shows recent log lines from a named service" {
    run bash "$ROOT/scripts/ops.sh" logs jupyter
    [ "$status" -eq 0 ]
}

@test "ops restart: returns success" {
    run bash "$ROOT/scripts/ops.sh" restart
    [ "$status" -eq 0 ]
}

@test "ops down: stops the stack" {
    run bash "$ROOT/scripts/ops.sh" down
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps bash -c '
        cd /srv/lab-bridge && docker compose ps --status running --format "{{.Service}}"
    ' | grep -vE "^$" | wc -l | tr -d "[:space:]" | grep -q "^0$"
}

@test "ops backup: rsyncs notebooks to ./backups" {
    docker exec lds-fake-vps bash -c 'echo hello > /srv/jupyterlab/work/note.txt && chown 1000:100 /srv/jupyterlab/work/note.txt'
    cd "$TMPDIR"
    run bash "$ROOT/scripts/ops.sh" backup
    [ "$status" -eq 0 ]
    found="$(find "$TMPDIR/backups" -name 'note.txt' | head -1)"
    [[ -n "$found" ]]
    [[ "$(cat "$found")" == "hello" ]]
}

@test "ops logs:loki: returns success and shows recent log lines" {
    run bash "$ROOT/scripts/ops.sh" logs:loki
    [ "$status" -eq 0 ]
}

@test "ops logs:grafana: returns success" {
    run bash "$ROOT/scripts/ops.sh" logs:grafana
    [ "$status" -eq 0 ]
}

@test "ops loki-disk: prints loki_data size and configured retention" {
    run bash "$ROOT/scripts/ops.sh" loki-disk
    [ "$status" -eq 0 ]
    [[ "$output" == *"loki_data"* ]]
    [[ "$output" == *"retention"* ]] || [[ "$output" == *"30"* ]]
}

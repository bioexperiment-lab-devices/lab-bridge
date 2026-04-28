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
    export LDS_SKIP_HEALTHCHECK=1
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

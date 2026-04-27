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
    bash "$ROOT/scripts/provision.sh"
}
teardown() { teardown_tmpdir; }

@test "deploy: rsyncs templates and brings up containers" {
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab_devices_server/docker-compose.yml
    docker exec lds-fake-vps test -f /srv/lab_devices_server/Caddyfile
    docker exec lds-fake-vps test -f /srv/lab_devices_server/chisel/users.json
    # nested docker compose ps shows three services up
    docker exec lds-fake-vps bash -c '
        cd /srv/lab_devices_server && docker compose ps --status running --format "{{.Service}}"
    ' | sort | tr -d "\r" | grep -E "^(caddy|jupyter|chisel)$" | wc -l | grep -q 3
}

@test "deploy: rsync --delete preserves caddy_data" {
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps bash -c 'echo testdata > /srv/lab_devices_server/caddy_data/marker'
    bash "$ROOT/scripts/deploy.sh"
    docker exec lds-fake-vps test -f /srv/lab_devices_server/caddy_data/marker
}

@test "deploy: rejects config with invalid hash before touching VPS" {
    cp "$ROOT/tests/fixtures/bad_hash_config.yaml" "$LDS_CONFIG"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$LDS_CONFIG"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]]
}

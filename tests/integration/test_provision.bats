#!/usr/bin/env bats

load helpers

# These tests boot the fake-VPS container and run provision.sh against it.
# They are slow (image build + Docker install). Mark with @tag if you want
# to skip in inner-loop runs.

setup_file() {
    bash "$ROOT/tests/integration/fake_vps/start.sh"
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    # Point config at the fake VPS.
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    # ssh_port is now a pins.yaml value; create a test-specific pins with port 2222.
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
}
teardown() { teardown_tmpdir; }

@test "provision: installs docker, configures ufw, creates dirs" {
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
    # docker present
    docker exec lds-fake-vps bash -c 'command -v docker' >/dev/null
    # ufw enabled with the right ports
    docker exec lds-fake-vps ufw status | grep -q '22/tcp.*ALLOW'
    docker exec lds-fake-vps ufw status | grep -q '443/tcp.*ALLOW'
    docker exec lds-fake-vps ufw status | grep -q '8080/tcp.*ALLOW'
    # dirs exist with right ownership
    docker exec lds-fake-vps stat -c '%U' /srv/lab-bridge | grep -q khamit
    docker exec lds-fake-vps stat -c '%U' /srv/jupyterlab/work     | grep -q khamit
}

@test "provision: re-running is idempotent (no errors)" {
    bash "$ROOT/scripts/provision.sh"
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
}

@test "provision: creates loki_data and grafana_data with correct ownership" {
    run bash "$ROOT/scripts/provision.sh"
    [ "$status" -eq 0 ]
    # Loki container runs as uid 10001
    docker exec lds-fake-vps stat -c '%u' /srv/lab-bridge/loki_data | grep -q '^10001$'
    # Grafana container runs as uid 472
    docker exec lds-fake-vps stat -c '%u' /srv/lab-bridge/grafana_data | grep -q '^472$'
}

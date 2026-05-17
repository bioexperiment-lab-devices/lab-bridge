#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "validate_config: accepts a valid config" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: rejects config missing required fields" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/missing_field_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"siteapp.admin_password_hash"* ]]
}

@test "validate_config: rejects duplicate chisel reverse_ports" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/duplicate_port_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"duplicate"* ]] || [[ "$output" == *"9001"* ]]
}

@test "validate_config: rejects malformed jupyter.password_hash" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/bad_hash_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]]
}

@test "validate_config: missing file gives clear error" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/nope.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"not found"* ]] || [[ "$output" == *"nope.yaml"* ]]
}

@test "load_config: exports VPS_HOST, JUPYTER_PASSWORD_HASH, etc." {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$VPS_HOST \$VPS_SSH_USER \$VPS_SSH_PORT \$JUPYTER_PASSWORD_HASH"
    [ "$status" -eq 0 ]
    [[ "$output" == *"192.0.2.10 khamit 22"* ]]
    [[ "$output" == *"sha1:abcdef012345:"* ]]
}

@test "validate_config: rejects pins.yaml missing loki/grafana fields" {
    cat > "$TMPDIR/cfg.yaml" <<'CFG'
vps: {host: 1.2.3.4, ssh_user: u}
jupyter: {password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"}
siteapp: {admin_password_hash: "$2a$14$HO81PFKmfx2eOcpGyeogN.ct3M9SzgDmvXYHaeNrlTzV66aFbPK2y"}
chisel_clients: []
CFG
    # Pins file is present but missing loki_image, loki_retention_days, grafana_image.
    cat > "$TMPDIR/bad_pins.yaml" <<'PINS'
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
chisel_listen_port: 8080
siteapp_image_repo: ghcr.io/test/lab-bridge-siteapp
acme_email: ops@example.com
remote_root: /srv/lab-bridge
notebooks_path: /srv/jupyterlab/work
ssh_port: 22
PINS
    run bash -c "export LDS_PINS_FILE=$TMPDIR/bad_pins.yaml; source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/cfg.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"loki_image"* ]]
    [[ "$output" == *"loki_retention_days"* ]]
    [[ "$output" == *"grafana_image"* ]]
}

@test "validate_config: rejects non-numeric loki_retention_days in pins.yaml" {
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/bad_pins.yaml"
    yq -i '.loki_retention_days = "abc"' "$TMPDIR/bad_pins.yaml"
    run bash -c "export LDS_PINS_FILE=$TMPDIR/bad_pins.yaml; source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"retention_days"* ]]
}

@test "load_config: exports LOKI_IMAGE, LOKI_RETENTION_DAYS, GRAFANA_IMAGE" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$LOKI_IMAGE \$LOKI_RETENTION_DAYS \$GRAFANA_IMAGE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"grafana/loki:3.2.1 30 grafana/grafana:11.3.0"* ]]
}

@test "validate_config: passes when pins.yaml supplies image pins and paths" {
    # Pins live in compose/pins.yaml; instance values live in config.yaml.
    mkdir -p "$TMPDIR/compose"
    cat > "$TMPDIR/compose/pins.yaml" <<'PINS'
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
chisel_listen_port: 8080
loki_image: grafana/loki:3.2.1
loki_retention_days: 30
grafana_image: grafana/grafana:11.3.0
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
caddy_image_repo: ghcr.io/example/lab-bridge-caddy
acme_email: ops@example.com
remote_root: /srv/lab-bridge
notebooks_path: /srv/jupyterlab/work
ssh_port: 22
PINS
    cat > "$TMPDIR/config.yaml" <<'CFG'
vps:
  host: 1.2.3.4
  ssh_user: deploy
jupyter:
  password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567
siteapp:
  admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa
chisel_clients: []
CFG

    run bash -c "export LDS_PINS_FILE=$TMPDIR/compose/pins.yaml; source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: fails when pins.yaml is missing" {
    cat > "$TMPDIR/config.yaml" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567 }
siteapp: { admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa }
chisel_clients: []
CFG

    run bash -c "export LDS_PINS_FILE=$TMPDIR/compose/pins.yaml; source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"pins file not found"* ]]
}

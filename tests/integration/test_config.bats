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
    [[ "$output" == *"vps.ssh_user"* ]]
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
    # loki_retention_days is a pins field; loki_image/grafana_image moved to
    # images.yaml in the pins/images split — exercise both files' validation.
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/bad_pins.yaml"
    yq -i 'del(.loki_retention_days)' "$TMPDIR/bad_pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/bad_images.yaml"
    yq -i 'del(.loki_image, .grafana_image)' "$TMPDIR/bad_images.yaml"
    run bash -c "export LDS_PINS_FILE=$TMPDIR/bad_pins.yaml LDS_IMAGES_FILE=$TMPDIR/bad_images.yaml; source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"loki_image"* ]] || false
    [[ "$output" == *"loki_retention_days"* ]] || false
    [[ "$output" == *"grafana_image"* ]]
}

@test "validate_config: rejects pins.yaml missing prometheus stack fields" {
    # prometheus_retention_days is a pins field; prometheus_image/
    # node_exporter_image/cadvisor_image moved to images.yaml in the split.
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/bad_pins.yaml"
    yq -i 'del(.prometheus_retention_days)' "$TMPDIR/bad_pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/bad_images.yaml"
    yq -i 'del(.prometheus_image, .node_exporter_image, .cadvisor_image)' "$TMPDIR/bad_images.yaml"
    run bash -c "export LDS_PINS_FILE=$TMPDIR/bad_pins.yaml LDS_IMAGES_FILE=$TMPDIR/bad_images.yaml; source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"prometheus_image"* ]] || false
    [[ "$output" == *"node_exporter_image"* ]] || false
    [[ "$output" == *"cadvisor_image"* ]] || false
    [[ "$output" == *"prometheus_retention_days"* ]]
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

@test "load_config: exports PROMETHEUS_IMAGE, NODE_EXPORTER_IMAGE, CADVISOR_IMAGE, PROMETHEUS_RETENTION_DAYS" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$PROMETHEUS_IMAGE \$NODE_EXPORTER_IMAGE \$CADVISOR_IMAGE \$PROMETHEUS_RETENTION_DAYS"
    [ "$status" -eq 0 ]
    [[ "$output" == *"prom/prometheus:v3.0.1"* ]]
    [[ "$output" == *"quay.io/prometheus/node-exporter:v1.8.2"* ]]
    [[ "$output" == *"ghcr.io/google/cadvisor:v0.57.0"* ]]
    [[ "$output" == *"30"* ]]
}

@test "validate_config: passes when pins.yaml supplies image pins and paths" {
    # Pins live in compose/pins.yaml; instance values live in config.yaml.
    mkdir -p "$TMPDIR/compose"
    cat > "$TMPDIR/compose/pins.yaml" <<'PINS'
chisel_listen_port: 8080
loki_retention_days: 30
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
streamer_image_repo: ghcr.io/example/lab-bridge-streamer
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
caddy_image_repo: ghcr.io/example/lab-bridge-caddy
authelia_image_repo: ghcr.io/example/lab-bridge-authelia
acme_email: ops@example.com
remote_root: /srv/lab-bridge
notebooks_path: /srv/jupyterlab/work
ssh_port: 22
prometheus_retention_days: 30
PINS
    # Externally-released image pins moved to images.yaml in the split; keep
    # them here so this test stays isolated from the repo's real images.yaml.
    cat > "$TMPDIR/compose/images.yaml" <<'IMAGES'
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
loki_image: grafana/loki:3.2.1
grafana_image: grafana/grafana:11.3.0
studio_image: ghcr.io/example/experiment-studio:0.3.0
authelia_image: ghcr.io/example/lab-bridge-authelia:latest
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1
IMAGES
    cat > "$TMPDIR/config.yaml" <<'CFG'
vps:
  host: 1.2.3.4
  ssh_user: deploy
jupyter:
  password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567
chisel_clients: []
CFG

    run bash -c "export LDS_PINS_FILE=$TMPDIR/compose/pins.yaml LDS_IMAGES_FILE=$TMPDIR/compose/images.yaml; source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
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

@test "validate_config: accepts valid config with split images file" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: missing images file gives clear error" {
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; LDS_PINS_FILE=$TMPDIR/pins.yaml LDS_IMAGES_FILE=$TMPDIR/nope.yaml validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"images file not found"* ]]
}

@test "validate_config: rejects images file missing a required image key" {
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    yq -i 'del(.studio_image)' "$TMPDIR/images.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; LDS_PINS_FILE=$TMPDIR/pins.yaml LDS_IMAGES_FILE=$TMPDIR/images.yaml validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"studio_image"* ]]
}

@test "load_config: exports image vars sourced from images.yaml" {
    # A substring check on the default fixture can't distinguish reading from
    # images.yaml vs (accidentally) pins.yaml. Use a distinct sentinel tag and
    # assert exact equality so the test actually proves the file redirect.
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    yq -i '.studio_image = "sentinel/studio:9.9.9"' "$TMPDIR/images.yaml"
    run bash -c "export LDS_IMAGES_FILE=$TMPDIR/images.yaml; source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$STUDIO_IMAGE"
    [ "$status" -eq 0 ]
    [ "$output" = "sentinel/studio:9.9.9" ]
}

@test "pins.yaml no longer carries external image keys" {
    run yq e '.studio_image // "absent"' "$ROOT/compose/pins.yaml"
    [ "$output" = "absent" ]
    run yq e '.siteapp_image_repo' "$ROOT/compose/pins.yaml"
    [[ "$output" == *"lab-bridge-siteapp"* ]]
}

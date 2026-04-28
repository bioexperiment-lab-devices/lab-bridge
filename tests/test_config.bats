#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "validate_config: accepts a valid config" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/valid_config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: rejects config missing required fields" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/missing_field_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"vps.remote_root"* ]]
    [[ "$output" == *"vps.notebooks_path"* ]]
}

@test "validate_config: rejects duplicate chisel reverse_ports" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/duplicate_port_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"duplicate"* ]] || [[ "$output" == *"9001"* ]]
}

@test "validate_config: rejects malformed jupyter.password_hash" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/fixtures/bad_hash_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]]
}

@test "validate_config: missing file gives clear error" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/nope.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"not found"* ]] || [[ "$output" == *"nope.yaml"* ]]
}

@test "load_config: exports VPS_HOST, JUPYTER_PASSWORD_HASH, etc." {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \$VPS_HOST \$VPS_SSH_USER \$VPS_SSH_PORT \$JUPYTER_PASSWORD_HASH"
    [ "$status" -eq 0 ]
    [[ "$output" == *"192.0.2.10 khamit 22"* ]]
    [[ "$output" == *"sha1:abcdef012345:"* ]]
}

@test "validate_config: rejects config missing loki/grafana fields" {
    cat > "$TMPDIR/bad.yaml" <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
  password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
chisel_clients: []
EOF
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/bad.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"loki.image"* ]]
    [[ "$output" == *"loki.retention_days"* ]]
    [[ "$output" == *"grafana.image"* ]]
}

@test "validate_config: rejects non-numeric loki.retention_days" {
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/cfg.yaml"
    yq -i '.loki.retention_days = "abc"' "$TMPDIR/cfg.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/cfg.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"retention_days"* ]]
}

@test "load_config: exports LOKI_IMAGE, LOKI_RETENTION_DAYS, GRAFANA_IMAGE" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \$LOKI_IMAGE \$LOKI_RETENTION_DAYS \$GRAFANA_IMAGE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"grafana/loki:3.2.1 30 grafana/grafana:11.3.0"* ]]
}

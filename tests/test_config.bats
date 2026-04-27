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

@test "load_config: exports VPS_HOST etc." {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \$VPS_HOST \$VPS_SSH_USER \$VPS_SSH_PORT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"192.0.2.10 khamit 22"* ]]
}

@test "load_config: exports JUPYTER_PASSWORD_HASH" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/fixtures/valid_config.yaml; echo \"\$JUPYTER_PASSWORD_HASH\""
    [ "$status" -eq 0 ]
    [[ "$output" == *"sha1:abc123def456:0123456789abcdef"* ]]
}

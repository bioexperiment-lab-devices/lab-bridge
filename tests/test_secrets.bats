#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
}
teardown() { teardown_tmpdir; }

@test "secrets set-jupyter-password: writes a sha1 hash to jupyter.password_hash" {
    old_hash="$(yq e '.jupyter.password_hash' "$LDS_CONFIG")"
    run bash -c "echo -e 'sekret\nsekret' | $ROOT/scripts/secrets.sh set-jupyter-password"
    [ "$status" -eq 0 ]
    new_hash="$(yq e '.jupyter.password_hash' "$LDS_CONFIG")"
    [[ "$new_hash" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]
    [[ "$new_hash" != "$old_hash" ]]
}

@test "secrets set-jupyter-password: refuses mismatched password confirmation" {
    run bash -c "echo -e 'one\ntwo' | $ROOT/scripts/secrets.sh set-jupyter-password"
    [ "$status" -ne 0 ]
    [[ "$output" == *"match"* ]] || [[ "$output" == *"mismatch"* ]]
}

@test "secrets add-client: appends entry with random password and prints client invocation" {
    run bash "$ROOT/scripts/secrets.sh" add-client thermometer-7 9007
    [ "$status" -eq 0 ]
    name="$(yq e '.chisel_clients[] | select(.name == "thermometer-7") | .name' "$LDS_CONFIG")"
    port="$(yq e '.chisel_clients[] | select(.name == "thermometer-7") | .reverse_port' "$LDS_CONFIG")"
    pwd="$(yq e '.chisel_clients[] | select(.name == "thermometer-7") | .password' "$LDS_CONFIG")"
    [[ "$name" == "thermometer-7" ]]
    [[ "$port" == "9007" ]]
    [[ "${#pwd}" -eq 32 ]]
    [[ "$output" == *"thermometer-7:$pwd"* ]]
    [[ "$output" == *"R:0.0.0.0:9007:localhost:80"* ]]
}

@test "secrets add-client: refuses duplicate name" {
    run bash "$ROOT/scripts/secrets.sh" add-client microscope-1 9099
    [ "$status" -ne 0 ]
    [[ "$output" == *"microscope-1"* ]]
}

@test "secrets add-client: refuses port already in use" {
    run bash "$ROOT/scripts/secrets.sh" add-client newdevice 9001
    [ "$status" -ne 0 ]
    [[ "$output" == *"9001"* ]]
}

@test "secrets show-client: re-prints invocation for existing client" {
    pwd="$(yq e ".chisel_clients[] | select(.name == \"microscope-1\") | .password" "$LDS_CONFIG")"
    run bash "$ROOT/scripts/secrets.sh" show-client microscope-1
    [ "$status" -eq 0 ]
    [[ "$output" == *"microscope-1:$pwd"* ]]
    [[ "$output" == *"R:0.0.0.0:9001:localhost:80"* ]]
}

@test "secrets show-client: refuses unknown client" {
    run bash "$ROOT/scripts/secrets.sh" show-client ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}

@test "secrets rm-client: removes existing client" {
    run bash "$ROOT/scripts/secrets.sh" rm-client microscope-1
    [ "$status" -eq 0 ]
    count="$(yq e '.chisel_clients | map(select(.name == "microscope-1")) | length' "$LDS_CONFIG")"
    [[ "$count" == "0" ]]
}

@test "secrets rm-client: refuses unknown client" {
    run bash "$ROOT/scripts/secrets.sh" rm-client ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}

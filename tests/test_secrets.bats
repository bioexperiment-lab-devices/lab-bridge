#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
}
teardown() { teardown_tmpdir; }

@test "secrets add-user: appends entry with a bcrypt hash" {
    run bash -c "echo -e 'sekret\nsekret' | $ROOT/scripts/secrets.sh add-user bob"
    [ "$status" -eq 0 ]
    name="$(yq e ".caddy_users[] | select(.name == \"bob\") | .name" "$LDS_CONFIG")"
    hash="$(yq e ".caddy_users[] | select(.name == \"bob\") | .password_hash" "$LDS_CONFIG")"
    [[ "$name" == "bob" ]]
    [[ "$hash" =~ ^\$2y\$14\$.{53}$ ]]
}

@test "secrets add-user: refuses duplicate username" {
    # alice already exists in the fixture
    run bash -c "echo -e 'sekret\nsekret' | $ROOT/scripts/secrets.sh add-user alice"
    [ "$status" -ne 0 ]
    [[ "$output" == *"alice"* ]]
    [[ "$output" == *"exists"* ]] || [[ "$output" == *"already"* ]]
}

@test "secrets add-user: refuses mismatched password confirmation" {
    run bash -c "echo -e 'one\ntwo' | $ROOT/scripts/secrets.sh add-user carol"
    [ "$status" -ne 0 ]
    [[ "$output" == *"match"* ]] || [[ "$output" == *"mismatch"* ]]
}

@test "secrets set-user-password: replaces hash for existing user" {
    old_hash=$(yq e '.caddy_users[] | select(.name == "alice") | .password_hash' "$LDS_CONFIG")
    run bash -c "echo -e 'newpw\nnewpw' | $ROOT/scripts/secrets.sh set-user-password alice"
    [ "$status" -eq 0 ]
    new_hash=$(yq e '.caddy_users[] | select(.name == "alice") | .password_hash' "$LDS_CONFIG")
    [[ "$new_hash" =~ ^\$2y\$14\$.{53}$ ]]
    [[ "$old_hash" != "$new_hash" ]]
}

@test "secrets set-user-password: refuses unknown user" {
    run bash -c "echo -e 'pw\npw' | $ROOT/scripts/secrets.sh set-user-password ghost"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
}

@test "secrets rm-user: removes existing user" {
    run bash "$ROOT/scripts/secrets.sh" rm-user alice
    [ "$status" -eq 0 ]
    count=$(yq e '.caddy_users | map(select(.name == "alice")) | length' "$LDS_CONFIG")
    [[ "$count" == "0" ]]
}

@test "secrets rm-user: refuses unknown user" {
    run bash "$ROOT/scripts/secrets.sh" rm-user ghost
    [ "$status" -ne 0 ]
    [[ "$output" == *"ghost"* ]]
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

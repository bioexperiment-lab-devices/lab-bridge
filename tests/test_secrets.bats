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

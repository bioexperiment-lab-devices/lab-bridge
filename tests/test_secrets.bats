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

#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    mkdir -p "$TMPDIR/compose/authelia"
    cp -r "$ROOT/scripts" "$TMPDIR/scripts"
    export LDS_USERS_DB="$TMPDIR/compose/authelia/users_database.yml"
    # Test hook: when `bash -c "$LDS_USERS_HASH_CMD" _ "secret"` runs,
    # output should contain the literal string `argon2id$test$secret`.
    export LDS_USERS_HASH_CMD='echo "\$argon2id\$test\$$1"'
}

teardown() { teardown_tmpdir; }

@test "users:add creates the file and adds a user with given group" {
    PASSWORD=secret bash "$TMPDIR/scripts/users.sh" add alice admins
    yq e '.users.alice.groups[0]' "$LDS_USERS_DB" | grep -q admins
    yq e '.users.alice.password' "$LDS_USERS_DB" | grep -q 'argon2id'
}

@test "users:add refuses unknown group" {
    PASSWORD=secret run bash "$TMPDIR/scripts/users.sh" add alice marketing
    [ "$status" -ne 0 ]
    [[ "$output" =~ unknown.group ]]
}

@test "users:rm removes the user" {
    PASSWORD=secret bash "$TMPDIR/scripts/users.sh" add alice admins
    bash "$TMPDIR/scripts/users.sh" rm alice
    run yq e '.users.alice' "$LDS_USERS_DB"
    [[ "$output" == "null" ]]
}

@test "users:set-password updates the hash" {
    PASSWORD=old bash "$TMPDIR/scripts/users.sh" add alice admins
    old_hash="$(yq e '.users.alice.password' "$LDS_USERS_DB")"
    PASSWORD=new bash "$TMPDIR/scripts/users.sh" set-password alice
    new_hash="$(yq e '.users.alice.password' "$LDS_USERS_DB")"
    [ "$old_hash" != "$new_hash" ]
}

@test "users:set-groups replaces the group list" {
    PASSWORD=secret bash "$TMPDIR/scripts/users.sh" add alice researchers
    bash "$TMPDIR/scripts/users.sh" set-groups alice admins,researchers
    yq e '.users.alice.groups | length' "$LDS_USERS_DB" | grep -q 2
}

@test "users:list prints a header and each user row" {
    PASSWORD=secret bash "$TMPDIR/scripts/users.sh" add alice admins
    PASSWORD=secret bash "$TMPDIR/scripts/users.sh" add bob researchers
    run bash "$TMPDIR/scripts/users.sh" list
    [[ "$output" =~ alice ]]
    [[ "$output" =~ bob ]]
    [[ "$output" =~ admins ]]
    [[ "$output" =~ researchers ]]
}

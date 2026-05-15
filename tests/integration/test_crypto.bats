#!/usr/bin/env bats

load helpers

@test "gen_password: produces 32 base64 characters (no padding)" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password"
    [ "$status" -eq 0 ]
    [[ "${#output}" -eq 32 ]]
    [[ "$output" =~ ^[A-Za-z0-9+/]+$ ]]
}

@test "gen_password: two consecutive calls yield different output" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; gen_password")"
    [[ "$a" != "$b" ]]
}

@test "jupyter_password_hash: produces sha1:<salt>:<digest> shape" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_password_hash hunter2"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]
}

@test "jupyter_password_hash: same plaintext, different runs yield different salts" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_password_hash hunter2")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_password_hash hunter2")"
    [[ "$a" != "$b" ]]
}

@test "jupyter_password_hash: digest matches sha1(plaintext || salt) — JupyterLab passwd_check format" {
    out="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_password_hash hunter2")"
    salt="$(echo "$out" | cut -d: -f2)"
    digest="$(echo "$out" | cut -d: -f3)"
    expected="$(printf '%s' "hunter2${salt}" | openssl sha1 | awk '{print $NF}')"
    [[ "$digest" == "$expected" ]]
}

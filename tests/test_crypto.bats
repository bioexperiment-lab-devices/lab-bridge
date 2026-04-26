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

@test "bcrypt_hash: produces a \$2y\$14\$ hash" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^\$2y\$14\$.{53}$ ]]
}

@test "bcrypt_hash: same plaintext, different runs produce different hashes (random salt)" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; bcrypt_hash hunter2")"
    [[ "$a" != "$b" ]]
}

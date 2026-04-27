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

@test "jupyter_sha1_hash: emits sha1:<hex_salt>:<40-char-hex>" {
    run bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_sha1_hash hunter2"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]
}

@test "jupyter_sha1_hash: same plaintext, different runs produce different hashes (random salt)" {
    a="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_sha1_hash hunter2")"
    b="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_sha1_hash hunter2")"
    [[ "$a" != "$b" ]]
}

@test "jupyter_sha1_hash: matches jupyter_server's algorithm (sha1(passphrase || salt))" {
    # Decompose the produced hash and recompute with python to confirm format compat.
    out="$(bash -c "source $ROOT/scripts/lib/crypto.sh; jupyter_sha1_hash myPa55")"
    salt="${out#sha1:}"; salt="${salt%:*}"
    hash="${out##*:}"
    expected="$(python3 -c "import hashlib,sys; print(hashlib.sha1((sys.argv[1]+sys.argv[2]).encode()).hexdigest())" myPa55 "$salt")"
    [[ "$hash" == "$expected" ]]
}

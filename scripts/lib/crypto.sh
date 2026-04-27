#!/usr/bin/env bash
# Crypto helpers for secrets management. Sourced, not executed.

# gen_password — print a 32-char base64 password (24 random bytes), no padding.
gen_password() {
    # `tr -d '='` strips base64 padding; `head -c 32` makes it length-stable
    # in case base64 produces a longer line (it shouldn't, but be defensive).
    openssl rand -base64 24 | tr -d '\n=' | head -c 32
    echo
}

# jupyter_sha1_hash <plaintext> — print a JupyterLab-format password hash:
#   sha1:<hex_salt_12>:<hex_sha1(passphrase || salt)>
# This matches what `jupyter_server.auth.passwd(..., algorithm='sha1')` emits
# and is accepted by ServerApp.password.
jupyter_sha1_hash() {
    local plaintext="${1:?jupyter_sha1_hash: missing plaintext}"
    local salt hash
    salt="$(openssl rand -hex 6)"
    hash="$(printf '%s' "${plaintext}${salt}" | openssl dgst -sha1 | awk '{print $NF}')"
    printf 'sha1:%s:%s\n' "$salt" "$hash"
}

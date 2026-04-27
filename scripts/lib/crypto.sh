#!/usr/bin/env bash
# Crypto helpers for secrets management. Sourced, not executed.

# gen_password — print a 32-char base64 password (24 random bytes), no padding.
gen_password() {
    # `tr -d '='` strips base64 padding; `head -c 32` makes it length-stable
    # in case base64 produces a longer line (it shouldn't, but be defensive).
    openssl rand -base64 24 | tr -d '\n=' | head -c 32
    echo
}

# jupyter_password_hash <plaintext> — print "sha1:<salt>:<digest>" matching
# JupyterLab's passwd_check (digest = sha1(plaintext || salt)).
# Uses only openssl, which is already a prerequisite.
jupyter_password_hash() {
    local plaintext="${1:?jupyter_password_hash: missing plaintext}"
    local salt digest
    salt="$(openssl rand -hex 6)"
    digest="$(printf '%s' "${plaintext}${salt}" | openssl sha1 | awk '{print $NF}')"
    printf 'sha1:%s:%s\n' "$salt" "$digest"
}

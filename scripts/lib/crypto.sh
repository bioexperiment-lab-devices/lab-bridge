#!/usr/bin/env bash
# Crypto helpers for secrets management. Sourced, not executed.

# gen_password — print a 32-char base64 password (24 random bytes), no padding.
gen_password() {
    # `tr -d '='` strips base64 padding; `head -c 32` makes it length-stable
    # in case base64 produces a longer line (it shouldn't, but be defensive).
    openssl rand -base64 24 | tr -d '\n=' | head -c 32
    echo
}

# bcrypt_hash <plaintext> — print a bcrypt hash with cost 14 ($2y$ flavor).
bcrypt_hash() {
    local plaintext="${1:?bcrypt_hash: missing plaintext}"
    # htpasswd -nbB <user> <password> emits "user:hash". We use a dummy user
    # and strip the prefix. -B selects bcrypt, -C 14 sets the cost.
    htpasswd -nbBC 14 _ "$plaintext" | sed -e 's/^_://' -e 's/[[:space:]]*$//'
}

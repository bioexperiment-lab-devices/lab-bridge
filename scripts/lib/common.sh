#!/usr/bin/env bash
# Common helpers: logging, error handling, SSH wrappers.
# Sourced (not executed) by other scripts. Always set strict mode in callers.

if [[ -t 2 ]]; then
    _C_RESET=$'\033[0m'
    _C_GREEN=$'\033[32m'
    _C_YELLOW=$'\033[33m'
    _C_RED=$'\033[31m'
else
    _C_RESET="" _C_GREEN="" _C_YELLOW="" _C_RED=""
fi

log()  { printf '%s[lab]%s %s\n' "$_C_GREEN" "$_C_RESET" "$*" >&2; }
warn() { printf '%s[warn]%s %s\n' "$_C_YELLOW" "$_C_RESET" "$*" >&2; }
die()  { printf '%s[fail]%s %s\n' "$_C_RED" "$_C_RESET" "$*" >&2; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

# Build the SSH command for the configured VPS. Reads VPS_HOST, VPS_SSH_USER,
# VPS_SSH_PORT from the environment (set by config.sh::load_config).
ssh_cmd() {
    printf 'ssh -p %s -o BatchMode=yes -o ConnectTimeout=10 %s@%s' \
        "${VPS_SSH_PORT:?}" "${VPS_SSH_USER:?}" "${VPS_HOST:?}"
}

# Run a command on the VPS over SSH. Args become a single shell string.
ssh_run() {
    local cmd
    cmd="$(ssh_cmd)"
    # shellcheck disable=SC2086
    $cmd "$@"
}

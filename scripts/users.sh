#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

VALID_GROUPS=(admins researchers)
DEFAULT_DB="$SCRIPT_DIR/../compose/authelia/users_database.yml"
USERS_DB="${LDS_USERS_DB:-$DEFAULT_DB}"

ensure_db() {
    mkdir -p "$(dirname "$USERS_DB")"
    if [[ ! -f "$USERS_DB" ]]; then
        echo "users: {}" > "$USERS_DB"
        chmod 600 "$USERS_DB"
    fi
}

validate_groups() {
    local IFS=','
    local g
    for g in $1; do
        local ok=0
        local v
        for v in "${VALID_GROUPS[@]}"; do
            [[ "$g" == "$v" ]] && ok=1
        done
        (( ok )) || die "unknown group: $g (allowed: ${VALID_GROUPS[*]})"
    done
}

hash_password() {
    local plain="$1"
    if [[ -n "${LDS_USERS_HASH_CMD:-}" ]]; then
        # Test hook: a command that produces a deterministic fake hash.
        bash -c "$LDS_USERS_HASH_CMD" _ "$plain"
        return
    fi
    require_cmd docker
    # Use the same Authelia image pin as the running container.
    local image="${AUTHELIA_IMAGE:-authelia/authelia:4.38.10}"
    # `authelia hash-password` was deprecated/removed in 4.38.x; use the new
    # `crypto hash generate argon2` subcommand (variant defaults to argon2id).
    # Older builds prefix the hash with "Password hash: ", newer ones use
    # "Digest: "; match both to be forward-compatible.
    docker run --rm "$image" authelia crypto hash generate argon2 \
        --password "$plain" --no-confirm 2>/dev/null \
        | awk -F': ' '/Password hash:|Digest:/ {print $2; exit}'
}

prompt_or_env() {
    local label="$1" varname="$2" value
    if [[ -n "${!varname:-}" ]]; then
        printf '%s' "${!varname}"
        return
    fi
    read -rsp "$label: " value
    echo >&2
    printf '%s' "$value"
}

groups_yaml() {
    local IFS=','
    local g
    local first=1
    printf '['
    for g in $1; do
        (( first )) || printf ','
        printf '"%s"' "$g"
        first=0
    done
    printf ']'
}

cmd_add() {
    local user="${1:?usage: users.sh add <user> <group[,group]>}"
    local groups="${2:?usage: users.sh add <user> <group[,group]>}"
    ensure_db
    validate_groups "$groups"

    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -z "$existing" ]] || die "user $user already exists"

    local pw hash
    pw="$(prompt_or_env "password for $user" PASSWORD)"
    [[ -n "$pw" ]] || die "empty password"
    hash="$(hash_password "$pw")"

    local gyaml
    gyaml="$(groups_yaml "$groups")"
    yq -i ".users.$user.displayname = \"$user\" | .users.$user.password = \"$hash\" | .users.$user.email = \"$user@lab.local\" | .users.$user.groups = $gyaml" "$USERS_DB"
    log "added user $user with groups $groups"
}

cmd_rm() {
    local user="${1:?usage: users.sh rm <user>}"
    ensure_db
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"
    yq -i "del(.users.$user)" "$USERS_DB"
    log "removed user $user"
}

cmd_set_password() {
    local user="${1:?usage: users.sh set-password <user>}"
    ensure_db
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"

    local pw hash
    pw="$(prompt_or_env "new password for $user" PASSWORD)"
    [[ -n "$pw" ]] || die "empty password"
    hash="$(hash_password "$pw")"
    yq -i ".users.$user.password = \"$hash\"" "$USERS_DB"
    log "updated password for $user"
}

cmd_set_groups() {
    local user="${1:?usage: users.sh set-groups <user> <group[,group]>}"
    local groups="${2:?usage: users.sh set-groups <user> <group[,group]>}"
    ensure_db
    validate_groups "$groups"
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"
    yq -i ".users.$user.groups = $(groups_yaml "$groups")" "$USERS_DB"
    log "set groups for $user to $groups"
}

cmd_list() {
    ensure_db
    printf '%-20s %s\n' "USER" "GROUPS"
    yq e '.users | to_entries[] | .key + " " + (.value.groups | join(","))' \
        "$USERS_DB" \
        | while read -r user groups; do
            printf '%-20s %s\n' "$user" "${groups:-—}"
        done
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        add)            cmd_add "$@" ;;
        rm)             cmd_rm "$@" ;;
        set-password)   cmd_set_password "$@" ;;
        set-groups)     cmd_set_groups "$@" ;;
        list)           cmd_list "$@" ;;
        *) die "unknown subcommand: $sub (allowed: add, rm, set-password, set-groups, list)" ;;
    esac
}

main "$@"

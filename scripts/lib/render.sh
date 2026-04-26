#!/usr/bin/env bash
# Render the three deploy templates into a staging directory.
# Sourced, not executed. Depends on common.sh + config.sh being sourced and
# load_config having been called.

# render_compose <template_path> <output_path>
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        "$tmpl" > "$out"
}

# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"

    local block name hash count i
    block=""
    count="$(yq e '.caddy_users | length' "${CONFIG_PATH:?}")"
    for ((i=0; i<count; i++)); do
        name="$(yq e ".caddy_users[$i].name" "$CONFIG_PATH")"
        hash="$(yq e ".caddy_users[$i].password_hash" "$CONFIG_PATH")"
        block+="        $name $hash"$'\n'
    done
    # Strip trailing newline so the output stays tidy.
    block="${block%$'\n'}"

    awk -v acme="$CADDY_ACME_EMAIL" \
        -v host="$VPS_HOST" \
        -v block="$block" '
        {
            gsub(/__ACME_EMAIL__/, acme)
            gsub(/__VPS_HOST__/, host)
            if ($0 == "__BASIC_AUTH_BLOCK__") {
                print block
                next
            }
            print
        }
    ' "$tmpl" > "$out"
}

# render_chisel_users <output_path>
# Builds the chisel users.json from .chisel_clients in CONFIG_PATH.
render_chisel_users() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name + ":" + .password): ["R:0.0.0.0:" + (.reverse_port | tostring)]})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}

#!/usr/bin/env bash
# Render the three deploy templates into a staging directory.
# Sourced, not executed. Depends on common.sh + config.sh being sourced and
# load_config having been called.

# render_compose <template_path> <output_path>
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    # Use awk for the password hash because it can contain ':' characters that
    # collide with sed's `s|||` if the user picks an unusual delimiter.
    awk \
        -v jimg="${JUPYTER_IMAGE:?}" \
        -v cimg="${CHISEL_IMAGE:?}" \
        -v clp="${CHISEL_LISTEN_PORT:?}" \
        -v nb="${VPS_NOTEBOOKS_PATH:?}" \
        -v jpw="${JUPYTER_PASSWORD_HASH:?}" '
        {
            gsub(/__JUPYTER_IMAGE__/, jimg)
            gsub(/__CHISEL_IMAGE__/, cimg)
            gsub(/__CHISEL_LISTEN_PORT__/, clp)
            gsub(/__NOTEBOOKS_PATH__/, nb)
            gsub(/__JUPYTER_PASSWORD_HASH__/, jpw)
            print
        }
    ' "$tmpl" > "$out"
}

# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    awk -v acme="$CADDY_ACME_EMAIL" \
        -v host="$VPS_HOST" '
        {
            gsub(/__ACME_EMAIL__/, acme)
            gsub(/__VPS_HOST__/, host)
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

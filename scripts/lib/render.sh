#!/usr/bin/env bash
# Render the three deploy templates into a staging directory.
# Sourced, not executed. Depends on common.sh + config.sh being sourced and
# load_config having been called.

# render_compose <template_path> <output_path>
render_compose() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    # The password_hash contains $ and : characters but no | (sha1:hex:hex),
    # so | as the sed delimiter is safe.
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        "$tmpl" > "$out"
}

# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__ACME_EMAIL__|${CADDY_ACME_EMAIL:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        "$tmpl" > "$out"
}

# render_chisel_users <output_path>
# Builds the chisel users.json from .chisel_clients in CONFIG_PATH.
# Each user is allow-listed for both their reverse port (R:0.0.0.0:<port>)
# and the in-network Loki push endpoint (loki:3100). The forward path lets
# the client tunnel its log stream to Loki without exposing Loki publicly.
render_chisel_users() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name + ":" + .password): ["R:0.0.0.0:" + (.reverse_port | tostring), "loki:3100"]})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}

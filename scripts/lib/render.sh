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

#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "render_compose: substitutes image, paths, and chisel port" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: quay.io/jupyter/scipy-notebook:2026-04-20"* ]]
    [[ "$output" == *"image: jpillora/chisel:1.10.1"* ]]
    [[ "$output" == *"/srv/jupyterlab/work:/home/jovyan/work"* ]]
    [[ "$output" == *"--port=8080"* ]]
    [[ "$output" == *'"8080:8080"'* ]]
    [[ "$output" != *"__"*"__"* ]]   # no leftover placeholders
}

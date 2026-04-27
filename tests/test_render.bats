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

@test "render_caddyfile: includes IP, email, basic_auth, and reverse_proxy" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"https://192.0.2.10"* ]]
    [[ "$output" == *"email ops@example.com"* ]]
    [[ "$output" == *"alice "*'$2y$14$abcdefghij'* ]]
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
    [[ "$output" == *"profile shortlived"* ]]
    [[ "$output" == *"default_sni 192.0.2.10"* ]]
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_caddyfile: empty caddy_users yields valid empty basic_auth block" {
    cat > $TMPDIR/empty_users.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users: []
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty_users.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    # basic_auth block exists but is empty — no users will be able to log in.
    grep -q 'basic_auth {' $TMPDIR/Caddyfile
}

@test "render_chisel_users: emits one entry per chisel_clients with route restriction" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    # Valid JSON?
    echo "$output" | yq -p json e '.' >/dev/null
    [[ "$output" == *'"microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"'* ]]
    [[ "$output" == *'R:0.0.0.0:9001'* ]]
}

@test "render_chisel_users: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter: {image: quay.io/jupyter/scipy-notebook:2026-04-20}
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
caddy_users: []
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    [[ "$(echo "$output" | tr -d '[:space:]')" == "{}" ]]
}

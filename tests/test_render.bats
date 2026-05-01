#!/usr/bin/env bats

load helpers

setup() { setup_tmpdir; }
teardown() { teardown_tmpdir; }

@test "render_compose: substitutes image, paths, password_hash, and chisel port" {
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
    [[ "$output" == *"--ServerApp.password=sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"* ]]
    # No leftover placeholders. Match `__NAME__` (bracketed both sides) to
    # avoid false positives on Docker secret env var suffixes like `__FILE`.
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_caddyfile: contains TLS, default_sni, reverse_proxy, no basic_auth" {
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
    [[ "$output" == *"profile shortlived"* ]]
    [[ "$output" == *"default_sni 192.0.2.10"* ]]
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
    [[ "$output" != *"basic_auth"* ]]
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_chisel_users: emits one entry per chisel_clients with R: and loki:3100" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    echo "$output" | yq -p json e '.' >/dev/null
    [[ "$output" == *'"microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"'* ]]
    [[ "$output" == *'R:0.0.0.0:9001'* ]]
    [[ "$output" == *'loki:3100'* ]]
}

@test "render_chisel_users: each user gets exactly two allow-list entries" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    run yq e '."microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6" | length' "$TMPDIR/users.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "2" ]]
}

@test "render_chisel_users: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
  password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
loki: {image: grafana/loki:3.2.1, retention_days: 30}
grafana: {image: grafana/grafana:11.3.0}
siteapp:
  image: ghcr.io/test/lab-bridge-siteapp:0.0.1
  admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
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

@test "render_compose: emits loki and grafana services with correct images" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: grafana/loki:3.2.1"* ]]
    [[ "$output" == *"image: grafana/grafana:11.3.0"* ]]
    [[ "$output" == *"GF_SERVER_ROOT_URL: https://192.0.2.10/grafana/"* ]]
    [[ "$output" == *"./loki/config.yaml:/etc/loki/config.yaml:ro"* ]]
    [[ "$output" == *"./loki_data:/loki"* ]]
    [[ "$output" == *"./grafana_data:/var/lib/grafana"* ]]
    [[ "$output" == *"./grafana/admin_password"* ]]
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_compose: loki has no published ports (only labnet)" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
    run yq e '.services.loki | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}

@test "render_caddyfile: routes /grafana/* to grafana:3000 and falls through to jupyter" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"handle /grafana/*"* ]]
    [[ "$output" == *"reverse_proxy grafana:3000"* ]]
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
}

@test "render_loki_config: substitutes retention hours (days * 24)" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
        cat $TMPDIR/loki.yaml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"retention_period: 720h"* ]]
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_loki_config: parses as valid YAML with the expected schema" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
    "
    [ "$status" -eq 0 ]
    run yq e '.compactor.retention_enabled' "$TMPDIR/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "true" ]]
    run yq e '.schema_config.configs[0].schema' "$TMPDIR/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "v13" ]]
}

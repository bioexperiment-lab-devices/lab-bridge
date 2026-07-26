#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    export LDS_PINS_FILE="$ROOT/tests/integration/fixtures/valid_pins.yaml"
    export LDS_IMAGES_FILE="$ROOT/tests/integration/fixtures/valid_images.yaml"
}
teardown() { teardown_tmpdir; }

@test "render_compose: substitutes image, paths, password_hash, and chisel port" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # jupyter_image/chisel_image live in images.yaml; derive expected values
    # from the fixture under test rather than hardcoding upstream versions
    # (a routine Renovate bump must not break this cheap-tier test).
    local jupyter_image chisel_image
    jupyter_image="$(yq e '.jupyter_image' "$LDS_IMAGES_FILE")"
    chisel_image="$(yq e '.chisel_image' "$LDS_IMAGES_FILE")"
    [[ "$output" == *"image: $jupyter_image"* ]] || false
    [[ "$output" == *"image: $chisel_image"* ]] || false
    [[ "$output" == *"/srv/jupyterlab/work:/home/jovyan/work"* ]] || false
    [[ "$output" == *"--port=8080"* ]] || false
    [[ "$output" == *'"8080:8080"'* ]] || false
    # grep (not [[ ]]) so a missing env var actually fails the test;
    # bats does not reliably enforce mid-test [[ ]] failures (see bats-assert).
    grep -q "SITEAPP_CHISEL_LISTEN_PORT: 8080" <<< "$output"
    # Jupyter password auth is disabled — Authelia handles auth via forward_auth.
    [[ "$output" == *"--ServerApp.password="* ]] || false
    ! grep -q -- "--ServerApp.password=sha1" <<< "$output"
    [[ "$output" == *"--ServerApp.disable_check_xsrf=true"* ]] || false
    # No leftover placeholders. Match `__NAME__` (bracketed both sides) to
    # avoid false positives on Docker secret env var suffixes like `__FILE`.
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_caddyfile: contains TLS, default_sni, reverse_proxy, no basic_auth" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"https://192.0.2.10"* ]] || false
    [[ "$output" == *"email ops@example.com"* ]] || false
    [[ "$output" == *"profile shortlived"* ]] || false
    [[ "$output" == *"default_sni 192.0.2.10"* ]] || false
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]] || false
    # basic_auth is no longer present — Authelia handles auth via forward_auth.
    ! grep -q 'basic_auth' <<< "$output"
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_chisel_users: emits one entry per chisel_clients with R: and loki:3100" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        cat $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    echo "$output" | yq -p json e '.' >/dev/null
    [[ "$output" == *'"microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"'* ]] || false
    [[ "$output" == *'R:0.0.0.0:9001'* ]] || false
    [[ "$output" == *'loki:3100'* ]]
}

@test "render_chisel_users: each user gets exactly two allow-list entries" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
    "
    [ "$status" -eq 0 ]
    run yq e '."microscope-1:k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6" | length' "$TMPDIR/users.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "2" ]]
}

@test "render_chisel_users: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u}
jupyter: {password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"}
siteapp: {admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345"}
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
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # loki_image/grafana_image live in images.yaml; derive from the fixture
    # under test instead of hardcoding upstream versions.
    local loki_image grafana_image
    loki_image="$(yq e '.loki_image' "$LDS_IMAGES_FILE")"
    grafana_image="$(yq e '.grafana_image' "$LDS_IMAGES_FILE")"
    [[ "$output" == *"image: $loki_image"* ]] || false
    [[ "$output" == *"image: $grafana_image"* ]] || false
    [[ "$output" == *"GF_SERVER_ROOT_URL: https://192.0.2.10/grafana/"* ]] || false
    [[ "$output" == *"./loki/config.yaml:/etc/loki/config.yaml:ro"* ]] || false
    [[ "$output" == *"./loki_data:/loki"* ]] || false
    [[ "$output" == *"./grafana_data:/var/lib/grafana"* ]] || false
    [[ "$output" == *"./grafana/admin_password"* ]] || false
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

# Sessions must outlive the authelia container: deploy.sh bounces authelia on
# every full deploy, and Authelia's default in-memory session provider dropped
# every session — "keep me signed in" included — on each bounce. Wiring only;
# the behaviour test is services/authelia/tests/e2e/test_session_persistence.py.
# Spec: docs/superpowers/specs/2026-07-26-authelia-session-persistence-design.md
@test "render_compose: emits the redis session store and gates authelia on it" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # redis_image lives in images.yaml; derive it so a Renovate bump can't
    # break this cheap-tier test.
    local redis_image
    redis_image="$(yq e '.redis_image' "$LDS_IMAGES_FILE")"
    # grep, not [[ ]] — a bare [[ ]] failing mid-test does not fail a bats test.
    grep -q "image: $redis_image" <<< "$output"
    grep -q -- "--appendonly" <<< "$output"
    grep -q "./redis_data:/data" <<< "$output"
    # authelia must wait for a healthy redis: it exits at startup when its
    # session provider is unreachable.
    yq e '.services.authelia.depends_on.redis.condition' "$TMPDIR/docker-compose.yml" \
        | grep -qx 'service_healthy'
    # Session store stays on labnet — no published port, no password needed.
    [ "$(yq e '.services.redis.ports // "none"' "$TMPDIR/docker-compose.yml")" = "none" ]
    [ "$(yq e '.services.redis.networks[0]' "$TMPDIR/docker-compose.yml")" = "labnet" ]
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_authelia_config: session state is stored in redis, not process memory" {
    # valid_config.yaml carries no .authelia.grafana_oidc_secret_hash, and
    # render_authelia_config hard-fails on an empty one — supply it the same
    # way the __GRAFANA_OIDC_SECRET_HASH__ test below does.
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        export AUTHELIA_GRAFANA_OIDC_SECRET_HASH='\$pbkdf2-sha512\$test\$hash'
        render_authelia_config $ROOT/services/authelia/config/configuration.yml.tmpl $TMPDIR/configuration.yml
        cat $TMPDIR/configuration.yml
    "
    [ "$status" -eq 0 ]
    [ "$(yq e '.session.redis.host' "$TMPDIR/configuration.yml")" = "redis" ]
    [ "$(yq e '.session.redis.port' "$TMPDIR/configuration.yml")" = "6379" ]
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

# Authelia 4.38 auto-maps its deprecated keys and warns that the mapping goes
# away in 5.0 — and for the OIDC client keys it says outright that the warnings
# become errors. A silent regression here would only surface as a total auth
# outage on the next authelia_image bump, so assert the shape directly.
@test "render_authelia_config: uses 4.38 key names, no deprecated ones" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        export AUTHELIA_GRAFANA_OIDC_SECRET_HASH='\$pbkdf2-sha512\$test\$hash'
        render_authelia_config $ROOT/services/authelia/config/configuration.yml.tmpl $TMPDIR/configuration.yml
        cat $TMPDIR/configuration.yml
    "
    [ "$status" -eq 0 ]
    local out="$TMPDIR/configuration.yml"

    # New names present.
    [ "$(yq e '.server.address' "$out")" = "tcp://0.0.0.0:9091/" ]
    [ "$(yq e '.session.cookies[0].domain' "$out")" = "192.0.2.10" ]
    [ "$(yq e '.session.cookies[0].authelia_url' "$out")" = "https://192.0.2.10/auth" ]
    [ "$(yq e '.session.cookies[0].name' "$out")" = "authelia_session" ]
    [ "$(yq e '.session.cookies[0].remember_me' "$out")" = "2160h" ]
    [ "$(yq e '.identity_providers.oidc.clients[0].client_id' "$out")" = "grafana" ]
    [ "$(yq e '.identity_providers.oidc.clients[0].userinfo_signed_response_alg' "$out")" = "none" ]
    # refresh_token grant requires the offline_access scope.
    yq e '.identity_providers.oidc.clients[0].scopes[]' "$out" | grep -qx 'offline_access'
    # OIDC signing key comes from the docker secret via the template filter,
    # never inlined into the rendered file.
    yq e '.identity_providers.oidc.jwks[0].key' "$out" | grep -q 'secret "/run/secrets/authelia_oidc_jwks_key"'
    ! grep -q 'BEGIN .*PRIVATE KEY' "$out"

    # Deprecated names absent. grep on the rendered YAML, not yq — a key that
    # yq reports as null reads the same as one that is simply missing.
    ! grep -qE '^\s*(host|port): (0\.0\.0\.0|9091)\s*$' "$out"
    ! grep -qE '^default_redirection_url:' "$out"
    ! grep -qE '^\s*remember_me_duration:' "$out"
    ! grep -qE '^\s*issuer_private_key:' "$out"
    ! grep -qE '^\s*userinfo_signing_algorithm:' "$out"
    ! grep -qE '^\s+- id: grafana\s*$' "$out"
}

@test "render_compose: loki has no published ports (only labnet)" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
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
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"handle /grafana/*"* ]] || false
    [[ "$output" == *"reverse_proxy grafana:3000"* ]] || false
    [[ "$output" == *"reverse_proxy jupyter:8888"* ]]
}

@test "render_loki_config: substitutes retention hours (days * 24)" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
        cat $TMPDIR/loki.yaml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"retention_period: 720h"* ]] || false
    [[ "$output" != *"__"*"__"* ]]
}

@test "render_loki_config: parses as valid YAML with the expected schema" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_loki_config $ROOT/compose/loki/config.yaml.tmpl $TMPDIR/loki.yaml
    "
    [ "$status" -eq 0 ]
    run yq e '.compactor.retention_enabled' "$TMPDIR/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "true" ]] || false
    run yq e '.schema_config.configs[0].schema' "$TMPDIR/loki.yaml"
    [ "$status" -eq 0 ]
    [[ "$output" == "v13" ]]
}

@test "render_siteapp_clients: emits {port, password_sha256} per entry" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    echo "$output" | yq -p json e '.' >/dev/null

    run yq -p json -o json e '."microscope-1".port' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "9001" ]] || false

    run yq -p json -o json e '."bench-2".port' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "9002" ]] || false

    # Hash is 64 lowercase hex chars
    # Suppress yq's compatibility warning (yq v4.50+ warns when -p json is
    # used without an explicit -o flag because the default output changed).
    run bash -c "yq -p json -o yaml e '.\"microscope-1\".password_sha256' '$TMPDIR/clients.json' 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9a-f]{64}$ ]] || false

    # Verify exactly two top-level keys
    run yq -p json -o json e 'keys | length' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "2" ]]
}

@test "render_siteapp_clients: password_sha256 matches sha256(password)" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
    "
    expected="$(printf '%s' 'k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6' | openssl dgst -sha256 -hex | awk '{print $NF}')"
    actual="$(yq -p json e '."microscope-1".password_sha256' "$TMPDIR/clients.json")"
    [[ "$expected" == "$actual" ]]
}

@test "render_siteapp_clients: never leaks passwords; hash field present" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    # The fixture's password is k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6
    [[ "$output" != *"k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"* ]] || false
    # Hash field IS expected — this is the positive shape check
    [[ "$output" == *'"password_sha256"'* ]]
}

@test "render_siteapp_clients: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u}
jupyter: {password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"}
siteapp: {admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345"}
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    [[ "$(echo "$output" | tr -d '[:space:]')" == "{}" ]]
}

@test "render_siteapp_clients: roster names mirror render_chisel_users" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        render_siteapp_clients $TMPDIR/clients.json
    "
    # Names from chisel users.json keys are 'name:password'; strip the suffix.
    chisel_names="$(yq -p json -oy e 'keys | .[]' $TMPDIR/users.json | sed 's/:.*//' | sort)"
    siteapp_names="$(yq -p json -oy e 'keys | .[]' $TMPDIR/clients.json | sort)"
    [[ "$chisel_names" == "$siteapp_names" ]]
}

@test "render_compose: siteapp service mounts clients.json read-only and sets SITEAPP_CLIENTS_FILE" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
    run yq e '.services.siteapp.volumes[]' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == *"./siteapp/clients.json:/etc/siteapp/clients.json:ro"* ]] || false

    run yq e '.services.siteapp.environment.SITEAPP_CLIENTS_FILE' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "/etc/siteapp/clients.json" ]]
}

@test "render_caddyfile: handles /api/public* by reverse-proxying to siteapp" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"handle /api/public*"* ]] || false
    # The handle block must reverse-proxy to siteapp (not jupyter).
    # Grep for the line within ~5 lines after the handle directive.
    [[ "$(grep -A 5 'handle /api/public\*' <<< "$output")" == *"reverse_proxy siteapp:8000"* ]]
}

@test "render_caddyfile: /api/clients/ has NO handle (stays internal)" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    # The internal endpoint at /api/clients/ must NOT have its own
    # Caddy handle; it stays unreachable from the public side via the
    # jupyter catch-all. (The /api/public* handle is unrelated.)
    ! grep -qE 'handle /api/clients' <<< "$output"
}

@test "render_compose: SITEAPP_IMAGE is composed from pins.yaml + root VERSION" {
    mkdir -p "$BATS_TEST_TMPDIR/compose"
    cat > "$BATS_TEST_TMPDIR/compose/pins.yaml" <<'PINS'
chisel_listen_port: 8080
loki_retention_days: 30
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
streamer_image_repo: ghcr.io/example/lab-bridge-streamer
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
caddy_image_repo: ghcr.io/example/lab-bridge-caddy
authelia_image_repo: ghcr.io/example/lab-bridge-authelia
acme_email: x@example.com
remote_root: /srv/lb
notebooks_path: /srv/lb/nb
ssh_port: 22
prometheus_retention_days: 30
PINS
    # Externally-released image pins moved to images.yaml in the split; keep
    # them here so this test stays isolated from the repo's real images.yaml.
    cat > "$BATS_TEST_TMPDIR/compose/images.yaml" <<'IMAGES'
jupyter_image: jup:1
chisel_image: chi:1
loki_image: lok:1
grafana_image: gra:1
studio_image: stu:1
authelia_image: ghcr.io/example/lab-bridge-authelia:latest
redis_image: docker.io/library/redis:7.4-alpine
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1
IMAGES
    echo "1.2.3 # x-release-please-version" > "$BATS_TEST_TMPDIR/VERSION"
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567 }
siteapp: { admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa }
chisel_clients: []
CFG
    # Minimal compose template that references __SITEAPP_IMAGE__.
    echo "image: __SITEAPP_IMAGE__" > "$BATS_TEST_TMPDIR/compose.tmpl"

    # Use the LDS_VERSION_FILE override so render.sh reads the test VERSION,
    # not the real repo's root VERSION.
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        export LDS_PINS_FILE='$BATS_TEST_TMPDIR/compose/pins.yaml'
        export LDS_IMAGES_FILE='$BATS_TEST_TMPDIR/compose/images.yaml'
        export LDS_VERSION_FILE='$BATS_TEST_TMPDIR/VERSION'
        load_config '$BATS_TEST_TMPDIR/config.yaml'
        render_compose '$BATS_TEST_TMPDIR/compose.tmpl' '$BATS_TEST_TMPDIR/out'
        cat '$BATS_TEST_TMPDIR/out'
    "
    [ "$status" -eq 0 ]
    [ "$output" = "image: ghcr.io/example/lab-bridge-siteapp:1.2.3" ]
}

@test "render_compose: FLASHER_IMAGE is composed from pins.yaml + root VERSION" {
    mkdir -p "$BATS_TEST_TMPDIR/compose"
    cat > "$BATS_TEST_TMPDIR/compose/pins.yaml" <<'PINS'
chisel_listen_port: 8080
loki_retention_days: 30
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
streamer_image_repo: ghcr.io/example/lab-bridge-streamer
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
caddy_image_repo: ghcr.io/example/lab-bridge-caddy
authelia_image_repo: ghcr.io/example/lab-bridge-authelia
acme_email: x@example.com
remote_root: /srv/lb
notebooks_path: /srv/lb/nb
ssh_port: 22
prometheus_retention_days: 30
PINS
    # Externally-released image pins moved to images.yaml in the split; keep
    # them here so this test stays isolated from the repo's real images.yaml.
    cat > "$BATS_TEST_TMPDIR/compose/images.yaml" <<'IMAGES'
jupyter_image: jup:1
chisel_image: chi:1
loki_image: lok:1
grafana_image: gra:1
studio_image: stu:1
authelia_image: ghcr.io/example/lab-bridge-authelia:latest
redis_image: docker.io/library/redis:7.4-alpine
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1
IMAGES
    echo "1.2.3 # x-release-please-version" > "$BATS_TEST_TMPDIR/VERSION"
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567 }
siteapp: { admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa }
chisel_clients: []
CFG
    echo "image: __FLASHER_IMAGE__" > "$BATS_TEST_TMPDIR/compose.tmpl"

    # Use the LDS_VERSION_FILE override so render.sh reads the test VERSION,
    # not the real repo's root VERSION.
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        export LDS_PINS_FILE='$BATS_TEST_TMPDIR/compose/pins.yaml'
        export LDS_IMAGES_FILE='$BATS_TEST_TMPDIR/compose/images.yaml'
        export LDS_VERSION_FILE='$BATS_TEST_TMPDIR/VERSION'
        load_config '$BATS_TEST_TMPDIR/config.yaml'
        render_compose '$BATS_TEST_TMPDIR/compose.tmpl' '$BATS_TEST_TMPDIR/out'
        cat '$BATS_TEST_TMPDIR/out'
    "
    [ "$status" -eq 0 ]
    [ "$output" = "image: ghcr.io/example/lab-bridge-flasher:1.2.3" ]
}

@test "render_compose: emits prometheus service with correct image and retention arg" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # prometheus_image lives in images.yaml; derive from the fixture under
    # test instead of hardcoding an upstream version.
    local prometheus_image
    prometheus_image="$(yq e '.prometheus_image' "$LDS_IMAGES_FILE")"
    [[ "$output" == *"image: $prometheus_image"* ]] || false
    [[ "$output" == *"--storage.tsdb.retention.time=30d"* ]] || false
    [[ "$output" == *"./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"* ]] || false
    [[ "$output" == *"./prometheus_data:/prometheus"* ]] || false
    run yq e '.services.prometheus | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]] || false
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}

@test "render_compose: emits node-exporter service with host /proc and /sys mounts" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # node_exporter_image lives in images.yaml; derive from the fixture under
    # test instead of hardcoding an upstream version.
    local node_exporter_image
    node_exporter_image="$(yq e '.node_exporter_image' "$LDS_IMAGES_FILE")"
    [[ "$output" == *"image: $node_exporter_image"* ]] || false
    [[ "$output" == *"--path.procfs=/host/proc"* ]] || false
    [[ "$output" == *"--path.sysfs=/host/sys"* ]] || false
    [[ "$output" == *"--path.rootfs=/host/root"* ]] || false
    [[ "$output" == *"/proc:/host/proc:ro"* ]] || false
    [[ "$output" == *"/sys:/host/sys:ro"* ]] || false
    [[ "$output" == *"/:/host/root:ro"* ]] || false
    run yq e '.services."node-exporter" | has("network_mode")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]] || false
    run yq e '.services."node-exporter" | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]] || false
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}

@test "render_compose: emits cadvisor service mounting docker.sock read-only" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    # cadvisor_image lives in images.yaml; derive from the fixture under
    # test instead of hardcoding an upstream version.
    local cadvisor_image
    cadvisor_image="$(yq e '.cadvisor_image' "$LDS_IMAGES_FILE")"
    [[ "$output" == *"image: $cadvisor_image"* ]] || false
    [[ "$output" == *"/var/run/docker.sock:/var/run/docker.sock:ro"* ]] || false
    [[ "$output" == *"/:/rootfs:ro"* ]] || false
    [[ "$output" == *"/var/lib/docker:/var/lib/docker:ro"* ]] || false
    run yq e '.services.cadvisor | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]] || false
    # cadvisor needs privileged + /dev/kmsg to read container cgroups and OOM
    # events under the systemd cgroup driver — see compose/docker-compose.yml.tmpl.
    run yq e '.services.cadvisor.privileged // false' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "true" ]] || false
    run yq e '.services.cadvisor.devices[0]' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "/dev/kmsg" ]] || false
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}

@test "render_authelia_config substitutes __VPS_HOST__ and __GRAFANA_OIDC_SECRET_HASH__" {
    export VPS_HOST="vps.example"
    export AUTHELIA_GRAFANA_OIDC_SECRET_HASH='$pbkdf2-sha512$test$hash'

    local tmpl="$BATS_TEST_TMPDIR/configuration.yml.tmpl"
    local out="$BATS_TEST_TMPDIR/configuration.yml"
    cat > "$tmpl" <<'EOF'
session:
  domain: __VPS_HOST__
identity_providers:
  oidc:
    clients:
      - id: grafana
        secret: '__GRAFANA_OIDC_SECRET_HASH__'
EOF

    source "$ROOT/scripts/lib/common.sh"
    source "$ROOT/scripts/lib/render.sh"
    render_authelia_config "$tmpl" "$out"

    grep -q "domain: vps.example" "$out"
    grep -q 'secret: ..pbkdf2-sha512.test.hash.' "$out"
}

@test "render_compose substitutes __AUTHELIA_IMAGE__" {
    source "$ROOT/scripts/lib/common.sh"
    source "$ROOT/scripts/lib/config.sh"
    source "$ROOT/scripts/lib/render.sh"

    # Minimal pins with authelia fields.
    mkdir -p "$BATS_TEST_TMPDIR/compose"
    cat > "$BATS_TEST_TMPDIR/compose/pins.yaml" <<'PINS'
chisel_listen_port: 8080
loki_retention_days: 30
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
streamer_image_repo: ghcr.io/example/lab-bridge-streamer
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
caddy_image_repo: ghcr.io/example/lab-bridge-caddy
authelia_image_repo: ghcr.io/test/authelia
acme_email: x@example.com
remote_root: /srv/lb
notebooks_path: /srv/lb/nb
ssh_port: 22
prometheus_retention_days: 30
PINS
    # Externally-released image pins moved to images.yaml in the split; keep
    # them here so this test stays isolated from the repo's real images.yaml.
    cat > "$BATS_TEST_TMPDIR/compose/images.yaml" <<'IMAGES'
jupyter_image: jup:1
chisel_image: chi:1
loki_image: lok:1
grafana_image: gra:1
studio_image: stu:1
authelia_image: ghcr.io/test/authelia:latest
redis_image: docker.io/library/redis:7.4-alpine
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1
IMAGES
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'EOF'
vps: { host: vps.example, ssh_user: root }
jupyter: { password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" }
siteapp: { admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345" }
chisel_clients: []
EOF
    LDS_VERSION_FILE="$BATS_TEST_TMPDIR/VERSION"
    echo "9.9.9" > "$LDS_VERSION_FILE"
    export LDS_VERSION_FILE
    export LDS_PINS_FILE="$BATS_TEST_TMPDIR/compose/pins.yaml"
    export LDS_IMAGES_FILE="$BATS_TEST_TMPDIR/compose/images.yaml"
    export AUTHELIA_IMAGE_REPO="ghcr.io/test/authelia"

    CONFIG_PATH="$BATS_TEST_TMPDIR/config.yaml" load_config "$BATS_TEST_TMPDIR/config.yaml"

    local tmpl="$BATS_TEST_TMPDIR/compose.yml.tmpl"
    local out="$BATS_TEST_TMPDIR/compose.yml"
    echo "image: __AUTHELIA_IMAGE__" > "$tmpl"
    render_compose "$tmpl" "$out"

    grep -q "image: ghcr.io/test/authelia:9.9.9" "$out"
}

@test "render_caddyfile: emits admin :2019 directive so Prometheus can scrape /metrics" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"admin :2019"* ]]
}

@test "render_prometheus_config: substitutes vps host and emits expected scrape jobs" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_prometheus_config $ROOT/compose/prometheus/prometheus.yml.tmpl $TMPDIR/prometheus.yml
        cat $TMPDIR/prometheus.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"host: 192.0.2.10"* ]] || false
    [[ "$output" == *"env: prod"* ]] || false
    [[ "$output" == *"job_name: prometheus"* ]] || false
    [[ "$output" == *"job_name: node-exporter"* ]] || false
    [[ "$output" == *"job_name: cadvisor"* ]] || false
    [[ "$output" == *"job_name: caddy"* ]] || false
    [[ "$output" == *"targets: ['caddy:2019']"* ]] || false
    [[ "$output" == *"targets: ['node-exporter:9100']"* ]] || false
    [[ "$output" == *"targets: ['cadvisor:8080']"* ]] || false
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/prometheus.yml"
    [ "$status" -eq 1 ]
    yq e '.' "$TMPDIR/prometheus.yml" >/dev/null
}

@test "render_compose: emits studio service with data volume and discovery env" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0"* ]] || false
    [[ "$output" == *"./studio_data:/data"* ]] || false
    grep -q "LAB_DEVICES_DISCOVERY_URL: http://siteapp:8000/api/clients/" <<< "$output"
    # No published ports — studio is only reachable through Caddy.
    run yq e '.services.studio | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}

@test "render_caddyfile: routes /studio/* to studio:8000 with prefix strip behind forward_auth" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    # Exact-path redirect adds the trailing slash the SPA needs to resolve
    # relative URLs (see compose/Caddyfile.tmpl).
    [[ "$output" == *"redir /studio /studio/ 308"* ]] || false
    [[ "$output" == *"handle /studio/*"* ]] || false
    studio_block="$(grep -A 14 'handle /studio/\*' <<< "$output")"
    [[ "$studio_block" == *"import authelia_required"* ]] || false
    # The strip must live inside a `route` wrapper so forward_auth sees the
    # un-stripped /studio path (Caddy otherwise sorts `uri` before
    # forward_auth and Authelia default-denies) — see compose/Caddyfile.tmpl.
    [[ "$studio_block" == *"route {"* ]] || false
    [[ "$studio_block" == *"uri strip_prefix /studio"* ]] || false
    [[ "$studio_block" == *"reverse_proxy studio:8000"* ]]
}


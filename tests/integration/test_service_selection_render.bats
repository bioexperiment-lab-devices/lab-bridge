#!/usr/bin/env bats
# Validation + render tier for optional-service selection. No containers.
# Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md

load helpers

setup() {
    setup_tmpdir
    export LDS_PINS_FILE="$ROOT/tests/integration/fixtures/valid_pins.yaml"
    export LDS_IMAGES_FILE="$ROOT/tests/integration/fixtures/valid_images.yaml"
}
teardown() { teardown_tmpdir; }

# Write a minimal valid config with the given disabled_services YAML list.
# Usage: write_config '[jupyter, monitoring]'   — or '' to omit the key.
write_config() {
    cat > "$TMPDIR/config.yaml" <<'CFG'
vps: { host: 192.0.2.10, ssh_user: khamit }
jupyter: { password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" }
chisel_clients: []
CFG
    if [[ -n "$1" ]]; then
        printf 'disabled_services: %s\n' "$1" >> "$TMPDIR/config.yaml"
    fi
}

@test "validate_config: accepts every optional name" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: rejects an unknown service name" {
    write_config '[jupyterlab]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"jupyterlab"* ]]
    [[ "$output" == *"allowed"* ]]
}

@test "validate_config: rejects disabling a core service" {
    write_config '[caddy]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"core service"* ]]
}

@test "validate_config: rejects duplicate entries" {
    write_config '[jupyter, jupyter]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"duplicate"* ]]
}

@test "load_config: absent key exports empty DISABLED_* vars" {
    write_config ''
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $TMPDIR/config.yaml; echo \"[\$DISABLED_SERVICES][\$DISABLED_COMPOSE_SERVICES]\""
    [ "$status" -eq 0 ]
    [[ "$output" == *"[][]"* ]]
}

@test "load_config: monitoring expands to the five compose services" {
    write_config '[monitoring, flasher]'
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $TMPDIR/config.yaml; echo \"[\$DISABLED_SERVICES]\"; echo \"[\$DISABLED_COMPOSE_SERVICES]\""
    [ "$status" -eq 0 ]
    [[ "$output" == *"[monitoring flasher]"* ]]
    [[ "$output" == *"[grafana loki prometheus node-exporter cadvisor flasher]"* ]]
}

@test "service_disabled: matches group names only" {
    write_config '[monitoring]'
    run bash -c "
        source $ROOT/scripts/lib/config.sh
        load_config $TMPDIR/config.yaml
        service_disabled monitoring && echo yes-monitoring
        service_disabled jupyter || echo no-jupyter
        service_disabled grafana || echo no-grafana
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"yes-monitoring"* ]]
    [[ "$output" == *"no-jupyter"* ]]
    [[ "$output" == *"no-grafana"* ]]
}

# Render the full compose template honoring $TMPDIR/config.yaml's
# disabled_services, into $TMPDIR/docker-compose.yml.
render_full_compose() {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
}

@test "filter_compose: disabled services are removed, core stays" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    render_full_compose
    local gone
    for gone in jupyter grafana loki prometheus node-exporter cadvisor studio streamer flasher; do
        run yq e ".services | has(\"$gone\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "false" ]] || { echo "service '$gone' still present"; false; }
    done
    local kept
    for kept in caddy authelia siteapp chisel; do
        run yq e ".services | has(\"$kept\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "true" ]] || { echo "service '$kept' missing"; false; }
    done
}

@test "filter_compose: caddy depends_on is pruned to remaining services" {
    write_config '[jupyter, monitoring]'
    render_full_compose
    run yq e -o=json -I=0 '.services.caddy.depends_on' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == '["siteapp","flasher","streamer","studio","authelia"]' ]]
}

@test "filter_compose: unreferenced top-level secrets are pruned" {
    write_config '[monitoring, flasher]'
    render_full_compose
    local gone
    for gone in grafana_admin_password grafana_oidc_secret flasher_upload_token; do
        run yq e ".secrets | has(\"$gone\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "false" ]] || { echo "secret '$gone' still present"; false; }
    done
    local kept
    for kept in agent_upload_token authelia_jwt_secret authelia_session_secret authelia_storage_encryption_key authelia_oidc_hmac_secret authelia_oidc_jwks_key; do
        run yq e ".secrets | has(\"$kept\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "true" ]] || { echo "secret '$kept' missing"; false; }
    done
}

@test "filter_compose: empty disabled list keeps all 14 services and 9 secrets" {
    write_config ''
    render_full_compose
    # 14 since redis joined as Authelia's session store. grep, not a bare
    # [[ ]] — a failing [[ ]] mid-test does not reliably fail a bats test
    # (this very assertion passed locally at 13 while CI caught it).
    run yq e '.services | length' "$TMPDIR/docker-compose.yml"
    grep -qx '14' <<< "$output"
    run yq e '.secrets | length' "$TMPDIR/docker-compose.yml"
    grep -qx '9' <<< "$output"
}

# redis is core: it must survive every disabled_services combination, or
# authelia comes up with no session provider and refuses to start.
@test "filter_compose: redis is never stripped, whatever is disabled" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    render_full_compose
    run yq e '.services | has("redis")' "$TMPDIR/docker-compose.yml"
    grep -qx 'true' <<< "$output"
    run yq e '.services.authelia.depends_on.redis.condition' "$TMPDIR/docker-compose.yml"
    grep -qx 'service_healthy' <<< "$output"
}

render_full_caddyfile() {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
    "
}

@test "render_caddyfile: disabled routes are stripped, core routes stay" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    render_full_caddyfile
    run cat "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy siteapp:8000'  <<< "$output"
    grep -q 'reverse_proxy authelia:9091' <<< "$output"
    grep -q 'handle_errors'               <<< "$output"
    # Negated checks use the run + status-1 idiom (test_render.bats:449-450):
    # `! grep ... <<< "$output"` is silently exempt from bats' errexit
    # handling (bash never traps a failing command prefixed with `!`), so it
    # can't actually fail the test. Asserting on $status makes it enforce.
    run grep -q 'reverse_proxy jupyter:8888' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'reverse_proxy grafana:3000' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'reverse_proxy flasher:8000' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'reverse_proxy streamer:8000' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'reverse_proxy studio:8000' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'redir /studio' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -q 'redir @old_jupyter' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/Caddyfile"
    [ "$status" -eq 1 ]
}

@test "render_caddyfile: data-disabled maps monitoring to grafana and omits streamer" {
    write_config '[jupyter, monitoring, streamer]'
    render_full_caddyfile
    grep -q 'data-disabled="jupyter,grafana"' "$TMPDIR/Caddyfile"
}

@test "render_caddyfile: nothing disabled renders empty data-disabled and all routes" {
    write_config ''
    render_full_caddyfile
    grep -q 'data-disabled=""' "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy jupyter:8888'  "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy grafana:3000'  "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy streamer:8000' "$TMPDIR/Caddyfile"
}

@test "Caddyfile.tmpl: svc markers are balanced" {
    local begins ends
    begins="$(grep -c 'BEGIN svc:' "$ROOT/compose/Caddyfile.tmpl")"
    ends="$(grep -c 'END svc:' "$ROOT/compose/Caddyfile.tmpl")"
    [ "$begins" -eq "$ends" ]
    [ "$begins" -ge 6 ]
}

# rsync/ssh spies that LOG their args (helpers' setup_fake_rsync_spy
# swallows ssh args; we need them to assert the restart list).
setup_logging_spies() {
    mkdir -p "$BATS_TEST_TMPDIR/spy_bin"
    cat > "$BATS_TEST_TMPDIR/spy_bin/rsync" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >> "$BATS_TEST_TMPDIR/rsync.log"
EOF
    cat > "$BATS_TEST_TMPDIR/spy_bin/ssh" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >> "$BATS_TEST_TMPDIR/ssh.log"
EOF
    chmod +x "$BATS_TEST_TMPDIR/spy_bin/rsync" "$BATS_TEST_TMPDIR/spy_bin/ssh"
    export PATH="$BATS_TEST_TMPDIR/spy_bin:$PATH"
}

@test "deploy.sh: disabled monitoring/flasher/streamer need no secrets and are not restarted" {
    write_config '[monitoring, flasher, streamer]'
    export LDS_CONFIG="$TMPDIR/config.yaml"
    stub_authelia_for_tests
    # Agent token is core (siteapp) — still required.
    printf 'tok' > "$TMPDIR/agent_upload_token"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    # Point the gated secrets at NONEXISTENT paths: with the gating in
    # place deploy.sh must not require them.
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/absent_grafana_pw"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/absent_flasher_tok"
    setup_logging_spies

    LDS_SKIP_HEALTHCHECK=1 run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]

    # rsync ran (stage was fully assembled without the gated secrets).
    [ -s "$BATS_TEST_TMPDIR/rsync.log" ]

    # The remote command restarts only enabled services.
    run cat "$BATS_TEST_TMPDIR/ssh.log"
    [[ "$output" == *"docker compose restart"* ]]
    restart_line="$(grep -o 'docker compose restart.*' "$BATS_TEST_TMPDIR/ssh.log")"
    [[ "$restart_line" == *"caddy"* ]]
    [[ "$restart_line" == *"siteapp"* ]]
    # Negated checks use the run + status-1 idiom (test_render.bats:449-450):
    # a bare `[[ ... != ... ]]` or `! grep` can be exempted from bats'
    # errexit-based failure propagation, so it can't reliably fail the test.
    run grep -q 'grafana' <<< "$restart_line"
    [ "$status" -eq 1 ]
    run grep -q 'streamer' <<< "$restart_line"
    [ "$status" -eq 1 ]
}

@test "config.ci.yaml.tmpl: empty LDS_DISABLED_SERVICES renders [] and validates" {
    command -v envsubst >/dev/null || skip "envsubst not installed"
    VPS_HOST=1.2.3.4 VPS_SSH_USER=u \
    JUPYTER_PASSWORD_HASH="sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" \
    ADMIN_PASSWORD_HASH='$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa' \
    LDS_DISABLED_SERVICES= \
        envsubst < "$ROOT/compose/config.ci.yaml.tmpl" > "$TMPDIR/ci.yaml"
    grep -q 'disabled_services: \[\]' "$TMPDIR/ci.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/ci.yaml"
    [ "$status" -eq 0 ]
}

@test "config.ci.yaml.tmpl: comma list renders a flow list that validates" {
    command -v envsubst >/dev/null || skip "envsubst not installed"
    VPS_HOST=1.2.3.4 VPS_SSH_USER=u \
    JUPYTER_PASSWORD_HASH="sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" \
    ADMIN_PASSWORD_HASH='$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa' \
    LDS_DISABLED_SERVICES='jupyter, monitoring' \
        envsubst < "$ROOT/compose/config.ci.yaml.tmpl" > "$TMPDIR/ci.yaml"
    run yq e '.disabled_services | length' "$TMPDIR/ci.yaml"
    [ "$status" -eq 0 ]
    [ "$output" = "2" ]
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/ci.yaml"
    [ "$status" -eq 0 ]
}

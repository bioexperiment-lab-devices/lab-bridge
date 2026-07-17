#!/usr/bin/env bats
# Validation + render tier for optional-service selection. No containers.
# Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md

load helpers

setup() {
    setup_tmpdir
    export LDS_PINS_FILE="$ROOT/tests/integration/fixtures/valid_pins.yaml"
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

@test "filter_compose: empty disabled list keeps all 13 services and 9 secrets" {
    write_config ''
    render_full_compose
    run yq e '.services | length' "$TMPDIR/docker-compose.yml"
    [[ "$output" == "13" ]]
    run yq e '.secrets | length' "$TMPDIR/docker-compose.yml"
    [[ "$output" == "9" ]]
}

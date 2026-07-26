#!/usr/bin/env bats
# Optional-service selection wiring: ONE fake-VPS bring-up with all five
# optional services disabled. Asserts the trimmed stack deploys healthy,
# disabled routes 404, and disabled containers do not exist. Thin wiring
# tier only — service behavior lives in services/<name>/tests/e2e/.
# Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md

load helpers

setup_file() {
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi
    bash "$ROOT/tests/integration/fake_vps/start.sh"
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    yq -i '.disabled_services = ["jupyter", "monitoring", "studio", "streamer", "flasher"]' "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    bootstrap_authelia_for_tests
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    # Gated secrets point at NONEXISTENT paths on purpose: with monitoring
    # and flasher disabled, deploy.sh must not require them.
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/absent_grafana_pw"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/absent_flasher_tok"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    # Only the CORE custom images — flasher/streamer aren't in the trimmed stack.
    load_siteapp_test_image
    load_caddy_test_image
    load_authelia_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_siteapp_ready
    wait_authelia_ready
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -k -s -o /dev/null -w \"%{http_code}\" --max-redirs 0 \"$1\"
        '
    "
}

_body_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -k -s --max-redirs 0 \"$1\"
        '
    "
}

@test "core routes respond on the trimmed stack" {
    code="$(_through_caddy 'https://127.0.0.1/')"
    [[ "$code" == "200" ]] || { echo "home got: $code"; false; }
    code="$(_through_caddy 'https://127.0.0.1/docs/')"
    [[ "$code" == "200" || "$code" == "308" ]] || { echo "docs got: $code"; false; }
    code="$(_through_caddy 'https://127.0.0.1/auth/api/health')"
    [[ "$code" == "200" ]] || { echo "authelia got: $code"; false; }
}

@test "disabled routes fall through to 404" {
    local p code
    for p in /jupyter/ /grafana/api/health /flash/ /streamer/labs /studio/; do
        code="$(_through_caddy "https://127.0.0.1$p")"
        [[ "$code" == "404" ]] || { echo "$p got: $code (want 404)"; false; }
    done
}

@test "/studio exact-path redirect is stripped too" {
    code="$(_through_caddy 'https://127.0.0.1/studio')"
    [[ "$code" == "404" ]] || { echo "got: $code"; false; }
}

@test "disabled containers do not exist; core containers do" {
    run docker exec lds-fake-vps bash -c 'cd /srv/lab-bridge && docker compose ps --services'
    [ "$status" -eq 0 ]
    local svc
    for svc in caddy siteapp authelia chisel; do
        grep -qx "$svc" <<< "$output" || { echo "core '$svc' missing: $output"; false; }
    done
    for svc in jupyter grafana loki prometheus node-exporter cadvisor studio streamer flasher; do
        ! grep -qx "$svc" <<< "$output" || { echo "disabled '$svc' present: $output"; false; }
    done
}

@test "navbar injection carries the disabled ids" {
    body="$(_body_through_caddy 'https://127.0.0.1/')"
    [[ "$body" == *'data-disabled="jupyter,grafana,studio,flasher"'* ]] \ || false
        || { echo "tag not found; got: $(grep -o 'data-disabled=\"[^\"]*\"' <<< "$body" || echo NONE)"; false; }
}

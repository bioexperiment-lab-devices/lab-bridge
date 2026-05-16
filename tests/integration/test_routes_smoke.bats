#!/usr/bin/env bats
# Caddy routing smoke test — one fake-VPS bring-up, all curl assertions.
#
# Asserts only the *route map* (which public path reaches which backend
# service) and the *Caddy-edge auth gate* (/flash/ basic_auth).
# Behavior assertions live in services/<name>/tests/e2e/.

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
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    printf 'flasher-smoke-tok' > "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE" "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    load_siteapp_test_image
    load_flasher_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_siteapp_ready
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

# Helper: curl through Caddy (TLS internal) from inside the caddy container.
_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -O /dev/null -S \"$1\" 2>&1 | awk \"/HTTP/ {print \\\$2}\" | head -n1
        '
    "
}

@test "/docs/ routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/docs/')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/download/agent routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/download/agent')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/_static/site.css routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/_static/site.css')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/api/public/health routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/api/public/health')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/api/public/server-info routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/api/public/server-info')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/flash/ is gated by basic_auth (401)" {
    code="$(_through_caddy 'https://127.0.0.1/flash/')"
    [[ "$code" == "401" ]] || { echo "got: $code"; false; }
}

@test "/grafana/login routes to grafana (200)" {
    code="$(_through_caddy 'https://127.0.0.1/grafana/login')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/ (root) routes to jupyter (302 or 200)" {
    code="$(_through_caddy 'https://127.0.0.1/')"
    [[ "$code" == "200" || "$code" == "302" ]] || { echo "got: $code"; false; }
}

@test "unknown path routes to jupyter (200/302/404 — not 502)" {
    # Just verify the fall-through path reaches a backend, not a Caddy error.
    code="$(_through_caddy 'https://127.0.0.1/some/random/path')"
    [[ "$code" != "502" && "$code" != "503" ]] || { echo "got: $code"; false; }
}

# Helper: dump full response headers through Caddy. Caddy v2's basic_auth
# directive does NOT emit WWW-Authenticate by design (to avoid browser
# auto-popups), so we discriminate via Content-Type: only the flasher app's
# JSONResponse-based 401 sets `Content-Type: application/json`; Caddy's
# basic_auth 401 returns an empty body with no JSON content-type.
_caddy_headers() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -S -O /dev/null \"$1\" 2>&1
        '
    " || true
}

@test "/flash/api/v1/firmware reaches flasher (JSON 401 — Caddy bypassed)" {
    # Bearer-auth endpoint: Caddy passes through; flasher returns 401 with
    # application/json content-type. If Caddy intercepted with basic_auth,
    # the response would lack a JSON content-type.
    headers="$(_caddy_headers 'https://127.0.0.1/flash/api/v1/firmware?sha256=deadbeef')"
    [[ "$headers" == *"Content-Type: application/json"* ]] || { echo "$headers"; false; }
}

@test "/flash/ is still gated by basic_auth (Caddy 401, no JSON body)" {
    # Operator UI: Caddy returns 401 with an empty body before the request
    # reaches flasher. A reverse of the JSON content-type assertion above.
    headers="$(_caddy_headers 'https://127.0.0.1/flash/')"
    [[ "$headers" != *"Content-Type: application/json"* ]] || { echo "$headers"; false; }
}

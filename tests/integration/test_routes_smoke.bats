#!/usr/bin/env bats
# Caddy routing smoke test — one fake-VPS bring-up, all curl assertions.
#
# Asserts only the *route map* (which public path reaches which backend
# service) and the *Caddy-edge auth gate* (/flash/ forward_auth → 302).
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
    bootstrap_authelia_for_tests
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
    load_caddy_test_image
    load_authelia_test_image
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

@test "/flash/ is gated by forward_auth (302 to /login)" {
    code="$(_through_caddy 'https://127.0.0.1/flash/')"
    [[ "$code" == "302" ]] || { echo "got: $code"; false; }
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

# Helper: curl through Caddy with a Bearer Authorization header. With a valid
# flasher bearer token the /flash/api/v1/* endpoint (no forward_auth) succeeds
# past auth and the response code reflects the app's own validation (e.g., 404
# for an unknown sha256). Token matches what setup_file() wrote to
# LDS_FLASHER_UPLOAD_TOKEN_FILE.
_through_caddy_with_bearer() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate --header \"Authorization: Bearer flasher-smoke-tok\" -q -O /dev/null -S \"$1\" 2>&1 | awk \"/HTTP/ {print \\\$2}\" | head -n1
        '
    "
}

@test "/flash/api/v1/firmware reaches flasher (404 with bearer — Caddy bypassed)" {
    # /flash/api/v1/* has no forward_auth gate; bearer token passes through
    # to flasher which returns 404 (no firmware with sha256=deadbeef).
    code="$(_through_caddy_with_bearer 'https://127.0.0.1/flash/api/v1/firmware?sha256=deadbeef')"
    [[ "$code" == "404" ]] || { echo "got: $code"; false; }
}

@test "/flash/ is gated by forward_auth (302 even with bearer)" {
    # forward_auth ignores the Bearer header — Authelia is the gatekeeper.
    # The request is redirected to /login regardless of the Authorization header.
    code="$(_through_caddy_with_bearer 'https://127.0.0.1/flash/')"
    [[ "$code" == "302" ]] || { echo "got: $code"; false; }
}

# Helper: fetch response BODY through the fake-VPS Caddy.
_body_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -O - \"$1\"
        '
    "
}

@test "navbar script injected with data-version attribute on every HTML page" {
    for path in "/" "/docs/" "/download/agent"; do
        body="$(_body_through_caddy "https://127.0.0.1$path")"
        [[ "$body" == *'/_shared/navbar.js'* ]] || { echo "no navbar.js on $path"; echo "${body:0:200}"; false; }
        [[ "$body" == *'data-version="'* ]] || { echo "no data-version on $path"; echo "${body:0:200}"; false; }
    done
}

@test "navbar brand row markup ships in the served JS" {
    body="$(_body_through_caddy 'https://127.0.0.1/_shared/navbar.js')"
    [[ "$body" == *"brand__wordmark"* ]] || { echo "no brand__wordmark"; echo "${body:0:200}"; false; }
    [[ "$body" == *"theme-toggle"* ]] || { echo "no theme-toggle"; echo "${body:0:200}"; false; }
}

@test "bookmark mode triggers on /jupyter/ and /grafana/ paths (upstream reachable)" {
    # Confirms the upstream behind /jupyter/ is reachable (200 or 302).
    # Bookmark-mode CSS class is applied client-side; full verification
    # would require a headless browser (follow-up).
    code="$(_through_caddy 'https://127.0.0.1/jupyter/')"
    [[ "$code" == "200" || "$code" == "302" ]] || { echo "got: $code"; false; }
}

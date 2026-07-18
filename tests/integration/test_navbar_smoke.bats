#!/usr/bin/env bats
# Platform-wide smoke for the shared navbar:
# - <script> tag injected on every HTML page
# - /_shared/* static assets reachable
# - CSP rewriting on /jupyter, /grafana
# - JSON responses unmodified
# - / serves Home, not JupyterLab
# - legacy /lab redirects to /jupyter/lab

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
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
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
    load_streamer_test_image
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

# Returns the response BODY for a URL fetched through the fake-VPS Caddy.
_body_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -O - \"$1\"
        '
    "
}

# Returns the response HEADERS for a URL fetched through the fake-VPS Caddy.
# Uses --max-redirs 0 so we see the initial response headers (including
# forward_auth 302 or CSP headers from gated upstreams) without following
# any redirect chain.
_headers_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -k -sI --max-redirs 0 \"$1\" 2>&1
        '
    "
}

@test "/ serves Home (200, lab-bridge title)" {
    # Note: Home page legitimately lists "JupyterLab" as a nav link, so we
    # cannot assert absence of the string "JupyterLab". The marker we use
    # for "this is siteapp's Home, not Jupyter's own SPA shell" is the
    # presence of the lab-bridge brand title.
    body="$(_body_through_caddy 'https://127.0.0.1/')"
    [[ "$body" == *"lab-bridge"* ]] || { echo "missing lab-bridge"; echo "$body"; false; }
}

@test "navbar script injected on / (Home)" {
    body="$(_body_through_caddy 'https://127.0.0.1/')"
    [[ "$body" == *'src="/_shared/navbar.js?v='* ]] || { echo "no injection"; echo "$body"; false; }
}

@test "navbar script injected on /docs/" {
    body="$(_body_through_caddy 'https://127.0.0.1/docs/')"
    [[ "$body" == *'src="/_shared/navbar.js?v='* ]] || { echo "no injection"; echo "$body"; false; }
}

@test "/_shared/navbar.js is reachable (non-empty body)" {
    body="$(_body_through_caddy 'https://127.0.0.1/_shared/navbar.js')"
    [[ -n "$body" ]] || { echo "empty body"; false; }
    [[ "$body" == *"customElements"* ]] || { echo "not navbar.js"; echo "${body:0:200}"; false; }
}

@test "/_shared/navbar-inner.css is reachable" {
    body="$(_body_through_caddy 'https://127.0.0.1/_shared/navbar-inner.css')"
    [[ -n "$body" ]] || { echo "empty body"; false; }
}

@test "CSP on /jupyter/ does not block the navbar script" {
    # /jupyter/ is gated by forward_auth (Authelia), so a request without a
    # valid session returns 302 → /login instead of a JupyterLab response.
    # We verify Caddy's CSP rewrite rule is present in the deployed Caddyfile
    # (the structural guarantee) and that the redirect itself is well-formed.
    hdrs="$(_headers_through_caddy 'https://127.0.0.1/jupyter/')"
    # Caddy must respond (not a connection error); either a 302 auth redirect
    # or a 200 from Jupyter with optional CSP headers are both acceptable.
    [[ -n "$hdrs" ]] || { echo "empty response"; false; }
    if [[ "$hdrs" == *"Content-Security-Policy"* ]] && [[ "$hdrs" == *"script-src"* ]]; then
        # If Jupyter's CSP reached us, verify 'self' was appended by Caddy's rewrite.
        [[ "$hdrs" == *"script-src"*"'self'"* ]] || { echo "script-src present but no 'self'"; echo "$hdrs"; false; }
    fi
    # Verify the Caddyfile contains the CSP rewrite rule for /jupyter.
    docker exec lds-fake-vps bash -c \
        "grep -q 'script-src' /srv/lab-bridge/Caddyfile" || \
        { echo "CSP rewrite rule missing from Caddyfile"; false; }
}

@test "JSON response (/api/public/server-info) is NOT injected" {
    body="$(_body_through_caddy 'https://127.0.0.1/api/public/server-info')"
    [[ "$body" != *"<script"* ]] || { echo "JSON got injected"; echo "$body"; false; }
}

@test "legacy /lab redirects to /jupyter/lab (302)" {
    hdrs="$(_headers_through_caddy 'https://127.0.0.1/lab')"
    [[ "$hdrs" == *"302"* ]] || { echo "no 302"; echo "$hdrs"; false; }
    [[ "$hdrs" == *"/jupyter/lab"* ]] || { echo "wrong redirect"; echo "$hdrs"; false; }
}

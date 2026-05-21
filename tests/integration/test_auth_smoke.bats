#!/usr/bin/env bats
# Auth smoke — one fake-VPS bring-up, Authelia-gated route assertions.
#
# Exercises the full auth stack end-to-end: Authelia firstfactor login,
# forward_auth gating on /flash and /jupyter, group-based 403, session
# logout, and the /api/auth/whoami siteapp endpoint.
#
# Behavior-level tests live in services/siteapp/tests/e2e/ and
# services/authelia/tests/e2e/; this tier only verifies the *wiring*
# across the real Caddy + Authelia + siteapp stack.

load helpers

setup_file() {
    fake_vps_up_with_users \
        admin:secret:admins \
        researcher:secret:researchers
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

@test "anonymous GET /flash redirects to /login?rd=/flash" {
    run curl -ksSI "https://$FAKE_VPS_HOST/flash"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    # HTTP/2 headers are lower-case; rd= target is URL-encoded so match flash
    # without a literal slash prefix.
    [[ "$output" =~ [Ll]ocation:.*/login ]]
    [[ "$output" =~ flash ]]
}

@test "anonymous GET /jupyter/ redirects to /login" {
    run curl -ksSI "https://$FAKE_VPS_HOST/jupyter/"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    [[ "$output" =~ [Ll]ocation:.*/login ]]
}

@test "anonymous GET /grafana/ redirects to /login (forward_auth gate)" {
    # Grafana is gated by Authelia's forward_auth in front of its own OIDC.
    # That way anonymous users see siteapp's custom /login form, not the
    # half-broken Authelia React portal (which has no working assets under
    # the /auth/ sub-path).
    run curl -ksSI "https://$FAKE_VPS_HOST/grafana/"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    [[ "$output" =~ [Ll]ocation:.*/login ]]
}

@test "/grafana/api/health stays public (deploy probe relies on it)" {
    # scripts/deploy.sh polls this endpoint expecting 200. The forward_auth
    # gate on /grafana/* must NOT cover it, otherwise every deploy fails.
    # The fake-VPS setup waits for siteapp+authelia but not Grafana, so
    # poll for up to ~60s (matching deploy.sh's own readiness window).
    local code=""
    local i
    for i in $(seq 1 60); do
        code="$(curl -ksS -o /dev/null -w '%{http_code}' \
            "https://$FAKE_VPS_HOST/grafana/api/health" || true)"
        [[ "$code" == "200" ]] && return 0
        sleep 1
    done
    echo "timeout: /grafana/api/health = $code (expected 200)"
    return 1
}

@test "OIDC authorization endpoint via /auth/ returns 30x (not portal HTML)" {
    # Regression guard: Caddy must strip /auth/ before proxying to Authelia,
    # otherwise Authelia falls through to its SPA catch-all and returns the
    # React portal as 200 HTML, breaking Grafana's OIDC handshake entirely.
    # Use GET (-D - dumps headers only) — Authelia's OIDC handler doesn't
    # respond to HEAD.
    run curl -ksS -o /dev/null -D - \
        "https://$FAKE_VPS_HOST/auth/api/oidc/authorization?client_id=grafana&response_type=code&redirect_uri=https://$FAKE_VPS_HOST/grafana/login/generic_oauth&scope=openid&state=abcdefghij1234567890&nonce=xyz123"
    [[ "$output" =~ HTTP/.*\ 30[0-9] ]]
}

@test "OIDC discovery is reachable at /auth/.well-known/openid-configuration" {
    run curl -ksS \
        "https://$FAKE_VPS_HOST/auth/.well-known/openid-configuration"
    [[ "$output" =~ \"issuer\" ]]
    [[ "$output" =~ authorization_endpoint ]]
}

@test "admin login round-trip grants /flash" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/flash/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    # Use -w to capture only the HTTP status code; -o /dev/null discards the
    # body.  Use /flash/ (with trailing slash) to avoid the flasher's internal
    # trailing-slash redirect which goes to http:// (wrong scheme for the
    # host-mapped port).
    run curl -kssS -o /dev/null -w '%{http_code}' -b "$jar" "https://$FAKE_VPS_HOST/flash/"
    [[ "$output" == "200" ]]
}

@test "researcher /flash returns 403 Forbidden page" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"researcher","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    local body
    body="$(curl -ksS -b "$jar" "https://$FAKE_VPS_HOST/flash/")"
    [[ "$body" =~ 403 ]]
    [[ "$body" =~ [Ff]orbidden ]]
}

@test "logout clears cookie and re-redirects" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    curl -ksS -b "$jar" -c "$jar" "https://$FAKE_VPS_HOST/logout" >/dev/null
    run curl -ksSI -b "$jar" "https://$FAKE_VPS_HOST/flash"
    [[ "$output" =~ HTTP/.*\ 302 ]]
}

@test "logout also bounces /grafana/ back to /login" {
    # Grafana keeps its own session cookie independent of authelia_session,
    # so /logout must both invalidate the Authelia session AND expire the
    # grafana_session cookie. The forward_auth gate is the belt-and-braces
    # check: even if a stale grafana_session leaked through, the gate would
    # still 302 to /login.
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    curl -ksS -b "$jar" -c "$jar" "https://$FAKE_VPS_HOST/logout" >/dev/null
    run curl -ksSI -b "$jar" "https://$FAKE_VPS_HOST/grafana/"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    [[ "$output" =~ [Ll]ocation:.*/login ]]
}

@test "whoami reflects session state on every handle" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    local body
    body="$(curl -ksS -b "$jar" "https://$FAKE_VPS_HOST/api/auth/whoami")"
    [[ "$body" =~ \"user\":\ ?\"admin\" ]]
    [[ "$body" =~ \"groups\":.*admins ]]
}

@test "task users round-trip works against fake-VPS" {
    # The users DB is seeded locally by fake_vps_up_with_users and LDS_USERS_DB
    # points at that file; exercise the task CLI against the same file.
    run task users:list
    [ "$status" -eq 0 ]
    [[ "$output" =~ admin ]]
    [[ "$output" =~ researcher ]]
}

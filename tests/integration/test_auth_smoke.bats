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

@test "anonymous GET /grafana/ is redirected towards auth (Grafana OIDC flow)" {
    # Grafana handles OIDC internally; it redirects to the Authelia OIDC
    # authorization endpoint (/auth/api/oidc/…).  We just verify the first
    # hop is a redirect rather than a 200 plain-text page.
    run curl -ksSI "https://$FAKE_VPS_HOST/grafana/"
    [[ "$output" =~ HTTP/.*\ 30[0-9] ]]
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

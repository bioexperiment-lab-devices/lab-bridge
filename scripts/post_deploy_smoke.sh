#!/usr/bin/env bash
# Authenticated post-deploy smoke test for the lab-bridge stack.
#
# scripts/deploy.sh's redirect probe (lines 222-269) only confirms that Caddy
# + Authelia forward_auth are wired: /jupyter and /flash return 302 to /login
# whether the backend behind them is healthy or in a crash loop. This script
# fills that gap by logging into Authelia as a dedicated CI admin user and
# hitting an authenticated JSON endpoint on each protected service.
#
# Pattern adapted from tests/integration/test_auth_smoke.bats (cookie-jar
# login via /api/auth/firstfactor) and scripts/deploy.sh (status-capture
# retry loop). Intended to be invoked from .github/actions/deploy-stack.
#
# Required env:
#   VPS_HOST           - host the deploy targets, e.g. lab.example.com
#   CI_SMOKE_USER      - Authelia username (group: admins)
#   CI_SMOKE_PASSWORD  - plaintext password matching the user's argon2id hash
#                        in compose/authelia/users_database.yml on the VPS

set -euo pipefail

: "${VPS_HOST:?VPS_HOST must be set}"
: "${CI_SMOKE_USER:?CI_SMOKE_USER must be set}"
: "${CI_SMOKE_PASSWORD:?CI_SMOKE_PASSWORD must be set}"

LOGIN_TIMEOUT_S="${LDS_SMOKE_LOGIN_TIMEOUT_S:-30}"
PROBE_TIMEOUT_S="${LDS_SMOKE_PROBE_TIMEOUT_S:-30}"

JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

log()  { printf '%s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Retry an authenticated probe until it both returns the expected HTTP status
# and the body passes a jq predicate. On final failure, prints last status +
# truncated body and returns non-zero. Never echoes the cookie jar contents.
#
# Usage: probe <label> <url> <expected_status> <jq_predicate>
probe() {
    local label="$1" url="$2" want_status="$3" jq_pred="$4"
    local deadline=$(($(date +%s) + PROBE_TIMEOUT_S))
    local body_file status body
    body_file="$(mktemp)"
    while :; do
        status="$(curl -sk -b "$JAR" -o "$body_file" -w '%{http_code}' "$url" || true)"
        if [[ "$status" == "$want_status" ]] && jq -e "$jq_pred" "$body_file" >/dev/null 2>&1; then
            log "  $label: $status OK"
            rm -f "$body_file"
            return 0
        fi
        if (( $(date +%s) >= deadline )); then
            warn "$label: last status=$status, want=$want_status, jq=$jq_pred"
            body="$(head -c 200 "$body_file" 2>/dev/null || true)"
            warn "$label body (first 200 chars): $body"
            rm -f "$body_file"
            return 1
        fi
        sleep 2
    done
}

login() {
    local deadline=$(($(date +%s) + LOGIN_TIMEOUT_S))
    local payload status
    payload="$(jq -nc \
        --arg u "$CI_SMOKE_USER" \
        --arg p "$CI_SMOKE_PASSWORD" \
        '{username: $u, password: $p, targetURL: "/", keepMeLoggedIn: true}')"
    while :; do
        status="$(curl -sk -c "$JAR" -o /dev/null -w '%{http_code}' \
            -X POST -H 'Content-Type: application/json' \
            --data-binary "$payload" \
            "https://$VPS_HOST/api/auth/firstfactor" || true)"
        if [[ "$status" == "200" ]]; then
            log "Authelia login OK (user=$CI_SMOKE_USER)"
            return 0
        fi
        if (( $(date +%s) >= deadline )); then
            fail "Authelia login failed for user $CI_SMOKE_USER (last status=$status). Check that the user exists in /srv/lab-bridge/authelia/users_database.yml on the VPS and that CI_SMOKE_PASSWORD matches its argon2id hash."
        fi
        sleep 2
    done
}

main() {
    log "post-deploy authenticated smoke against https://$VPS_HOST"
    login

    local failed=0
    # 1. Authelia session is valid via siteapp's whoami (proves the cookie was
    #    issued, the forward_auth handshake works, and siteapp reads the
    #    Remote-User header).
    probe "whoami" \
        "https://$VPS_HOST/api/auth/whoami" \
        200 \
        ".user == \"$CI_SMOKE_USER\"" || failed=1

    # 2. JupyterLab: status endpoint returns the standard Jupyter Server payload.
    probe "jupyter" \
        "https://$VPS_HOST/jupyter/api/status" \
        200 \
        'has("started")' || failed=1

    # 3. Grafana: /api/user returns the OIDC-provisioned user record. Don't
    #    assert on .login (OIDC username mapping is config-dependent) — just
    #    require a non-empty email, which proves the OIDC handshake produced a
    #    real Grafana user, not an anonymous session.
    probe "grafana" \
        "https://$VPS_HOST/grafana/api/user" \
        200 \
        '.email != null and (.email | length) > 0' || failed=1

    # 4. Flasher: /flash/api/clients returns the roster envelope. Always 200 +
    #    {"clients":[...]} regardless of roster size, so it works on CI deploys
    #    (roster file is preserved on the VPS by the rsync --exclude).
    probe "flasher" \
        "https://$VPS_HOST/flash/api/clients" \
        200 \
        'has("clients")' || failed=1

    if (( failed )); then
        fail "one or more services failed the authenticated smoke check (see warnings above)"
    fi
    log "all services responded to authenticated requests"
}

main "$@"

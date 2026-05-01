#!/usr/bin/env bats

load helpers

# All bring-up runs ONCE per file. Probing through Caddy doesn't mutate
# server state, so per-test isolation isn't worth the cost (each deploy
# pulls 6 images and would tip Docker Hub into rate-limiting on a CI box).
setup_file() {
    # Bail early — and gate every test in this file with skip — when the
    # host docker can't reach all the compose-service images. Most common
    # cause is a Docker Hub anonymous-pull rate limit on a shared CI box.
    # Bats doesn't reliably propagate `export` from setup_file across the
    # subshell boundary into per-test setup(), so we use a marker file
    # under BATS_FILE_TMPDIR (which both phases share).
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi
    bash "$ROOT/tests/fake_vps/start.sh"
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'integration-token' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    # Provision installs/starts dockerd inside the fake-VPS; only after that
    # can we `docker load` the locally-built siteapp image into the DinD.
    load_siteapp_test_image
    # Pre-seed any images already cached on the host so deploy.sh's
    # `docker compose pull --ignore-pull-failures` doesn't hit Docker Hub
    # rate limits across repeated test runs.
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    # Caddy can't ACME-issue for 127.0.0.1; swap to `tls internal` so HTTPS
    # probes return real handler responses instead of TLS errors.
    patch_caddyfile_tls_internal
    # Seed minimal docs + agent fixtures so /docs/ and /download/agent
    # return 200 instead of 404. Owned by uid 10001 (siteapp's user).
    docker exec lds-fake-vps bash -c '
        sudo mkdir -p /srv/lab-bridge/site_data/docs /srv/lab-bridge/site_data/agent/windows
        echo "# Welcome" | sudo tee /srv/lab-bridge/site_data/docs/index.md >/dev/null
        printf "stub" | sudo tee /srv/lab-bridge/site_data/agent/windows/agent.exe >/dev/null
        printf "{\"version\":\"0.0.1\",\"size\":4,\"sha256\":\"abc\",\"uploaded_at\":\"2026-01-01T00:00:00Z\"}" \
            | sudo tee /srv/lab-bridge/site_data/agent/meta.json >/dev/null
        sudo chown -R 10001:10001 /srv/lab-bridge/site_data
    '
    # Wait for siteapp /healthz before probes — deploy.sh's restart of
    # siteapp races test execution otherwise (a probe at T+0 sees 502).
    wait_siteapp_ready
    # Hand the cleanup path the same TMPDIR so teardown_file can delete it.
    export _SITEAPP_TMPDIR="$TMPDIR"
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
    if [[ -n "${_SITEAPP_TMPDIR:-}" && -d "$_SITEAPP_TMPDIR" ]]; then
        rm -rf "$_SITEAPP_TMPDIR"
    fi
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

# Probe a path against the in-container caddy. Returns the response line that
# contains the HTTP status (the second non-blank line of wget -S output).
probe() {
    local path="$1"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            wget --no-check-certificate -S -O - 'https://127.0.0.1/$path' 2>&1 | grep -E '^\s*HTTP/' | head -1
    "
}

@test "siteapp: /docs/ returns 200" {
    run probe "docs/"
    [[ "$output" == *"200"* ]]
}

@test "siteapp: /download/agent returns 200" {
    run probe "download/agent"
    [[ "$output" == *"200"* ]]
}

@test "siteapp: /admin/ requires auth (401 without creds)" {
    run probe "admin/"
    [[ "$output" == *"401"* ]]
}

@test "siteapp: jupyter still serves on /" {
    run probe ""
    [[ "$output" == *"200"* || "$output" == *"302"* ]]
}

@test "siteapp: grafana still serves on /grafana/login" {
    run probe "grafana/login"
    [[ "$output" == *"200"* ]]
}

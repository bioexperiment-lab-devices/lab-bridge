#!/usr/bin/env bats

load helpers

setup_file() {
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
    printf 'auth-tok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    # Same rationale as test_siteapp_routing.bats — provision must run first
    # so dockerd is up inside the fake-VPS before we `docker load` the image.
    load_siteapp_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_siteapp_ready
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

probe_admin() {
    local creds="$1"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            wget --no-check-certificate -S -O /dev/null --header='Authorization: Basic $creds' 'https://127.0.0.1/admin/' 2>&1 | grep -E '^\s*HTTP/' | head -1
    "
}

@test "siteapp: admin requires correct basic_auth" {
    local wrong; wrong="$(printf 'admin:wrong' | base64)"
    run probe_admin "$wrong"
    [[ "$output" == *"401"* ]]
}

@test "siteapp: api/agent/upload rejects missing bearer token" {
    # Post a complete multipart body (version + binary) but NO Authorization
    # header. The endpoint's _check_token() returns 401 before any work.
    # curl runs on the fake-VPS host (caddy:2 only has busybox wget, which
    # doesn't support -F multipart uploads); the published 443 maps to caddy.
    run docker exec lds-fake-vps bash -c "
        curl -sk -o /dev/null -w '%{http_code}' \
            --form-string version=1.2.3 \
            -F binary=@/etc/hostname \
            https://127.0.0.1/api/agent/upload
    "
    [[ "$output" == *"401"* ]]
}

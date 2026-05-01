#!/usr/bin/env bats

load helpers

# CI agent upload token used by this file. Written into LDS_AGENT_TOKEN_FILE
# in setup_file so deploy.sh renders it into the running siteapp.
TOKEN="upload-test-tok"

# Mirrors the setup_file/skip-marker pattern from test_siteapp_routing.bats and
# test_siteapp_auth.bats: bring the stack up ONCE per file (a per-test deploy
# would pull 6 images on every test and quickly trip Docker Hub anonymous-pull
# rate limits). The skip marker survives the bats subshell boundary that
# `export` from setup_file does not.
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
    printf '%s' "$TOKEN" > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
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

@test "siteapp: CI agent upload publishes binary; download round-trips" {
    # The fake-VPS Ubuntu image has curl; caddy:2 is alpine-based and only
    # ships busybox wget which lacks `-F` multipart support, so we drive the
    # request from the fake-VPS host against caddy's published 443. `tls
    # internal` is wired by patch_caddyfile_tls_internal in setup_file.
    local body="agent-bytes-$(date +%s)"
    docker exec lds-fake-vps bash -c "printf '%s' '$body' > /tmp/agent.exe"

    # Upload via the bearer-token CI endpoint.
    run docker exec lds-fake-vps bash -c "
        curl -sk -o /dev/null -w '%{http_code}' \
            -H 'Authorization: Bearer $TOKEN' \
            --form-string version=1.2.3 \
            -F binary=@/tmp/agent.exe \
            https://127.0.0.1/api/agent/upload
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"200"* ]]

    # Round-trip: pull the published binary back and byte-compare.
    run docker exec lds-fake-vps bash -c "
        curl -sk -o /tmp/back.exe https://127.0.0.1/download/agent/windows/agent.exe \
            && cmp /tmp/agent.exe /tmp/back.exe \
            && echo OK
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

@test "siteapp: admin docs upload appears at /docs" {
    # `admin-fixture` is the plaintext for the bcrypt hash baked into
    # tests/fixtures/valid_config.yaml (admin_password_hash). Caddy gates
    # /admin* with basic_auth using that hash.
    local creds
    creds="$(printf 'admin:admin-fixture' | base64)"

    # GET /admin/docs through caddy to harvest a valid CSRF token, then POST
    # the upload with the same creds + token; finally confirm the doc renders
    # at /docs/up.
    run docker exec lds-fake-vps bash -c "
        set -e
        curl -sk -H 'Authorization: Basic $creds' https://127.0.0.1/admin/docs \
            -o /tmp/admin.html
        csrf=\$(grep -oE 'name=\"csrf\" value=\"[^\"]+\"' /tmp/admin.html \
            | head -1 | sed -E 's/.*value=\"([^\"]+)\".*/\\1/')
        test -n \"\$csrf\"
        printf '# Hello\n\nworld\n' > /tmp/up.md
        upload_status=\$(curl -sk -o /dev/null -w '%{http_code}' \
            -H 'Authorization: Basic $creds' \
            -F csrf=\"\$csrf\" -F target= -F files=@/tmp/up.md \
            https://127.0.0.1/admin/docs/upload)
        # 303 redirect on success per admin.upload handler.
        case \"\$upload_status\" in 200|303) ;; *) echo \"upload http \$upload_status\" >&2; exit 1 ;; esac
        curl -sk https://127.0.0.1/docs/up | grep -q Hello && echo OK
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"OK"* ]]
}

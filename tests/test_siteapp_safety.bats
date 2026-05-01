#!/usr/bin/env bats

load helpers

# Two end-to-end safety properties of the siteapp + caddy stack:
#   1. Path-traversal in admin docs upload (target=../escape) returns 400.
#   2. Raw HTML inside an uploaded markdown file is rendered escaped on the
#      public /docs page (so an admin uploading user-supplied .md cannot
#      inject live <script> into a viewer's browser).
#
# Mirrors the per-file bring-up from test_siteapp_routing.bats /
# test_siteapp_uploads.bats: one stack for the file (each deploy.sh pulls 6
# images and would trip Docker Hub anonymous-pull rate limits in CI). The
# skip marker survives the bats subshell boundary that `export` from
# setup_file does not.
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
    printf 'safety-tok' > "$LDS_AGENT_TOKEN_FILE"
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

@test "siteapp: path traversal in admin docs upload is rejected (400)" {
    # admin.upload calls _resolve_target() which raises 400 for any target
    # that resolves outside the docs root. caddy gates /admin* with basic_auth
    # using the bcrypt hash baked into tests/fixtures/valid_config.yaml
    # (plaintext: admin-fixture).
    local creds
    creds="$(printf 'admin:admin-fixture' | base64)"

    run docker exec lds-fake-vps bash -c "
        set -e
        curl -sk -H 'Authorization: Basic $creds' https://127.0.0.1/admin/docs \
            -o /tmp/admin.html
        csrf=\$(grep -oE 'name=\"csrf\" value=\"[^\"]+\"' /tmp/admin.html \
            | head -1 | sed -E 's/.*value=\"([^\"]+)\".*/\\1/')
        test -n \"\$csrf\"
        printf 'x' > /tmp/x.md
        curl -sk -o /dev/null -w '%{http_code}' \
            -H 'Authorization: Basic $creds' \
            -F csrf=\"\$csrf\" -F target=../escape -F files=@/tmp/x.md \
            https://127.0.0.1/admin/docs/upload
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"400"* ]]
}

@test "siteapp: raw HTML in markdown upload renders escaped on /docs" {
    # Markdown renderer must escape any raw HTML in uploaded .md (otherwise
    # an admin uploading attacker-supplied content could inject a live
    # <script> into the public docs page). We upload a file containing a
    # <script> tag, then fetch the rendered page and assert the tag appears
    # only in escaped form.
    local creds
    creds="$(printf 'admin:admin-fixture' | base64)"

    run docker exec lds-fake-vps bash -c "
        set -e
        curl -sk -H 'Authorization: Basic $creds' https://127.0.0.1/admin/docs \
            -o /tmp/admin.html
        csrf=\$(grep -oE 'name=\"csrf\" value=\"[^\"]+\"' /tmp/admin.html \
            | head -1 | sed -E 's/.*value=\"([^\"]+)\".*/\\1/')
        test -n \"\$csrf\"
        printf '<script>alert(1)</script>\n' > /tmp/evil.md
        upload_status=\$(curl -sk -o /dev/null -w '%{http_code}' \
            -H 'Authorization: Basic $creds' \
            -F csrf=\"\$csrf\" -F target= -F files=@/tmp/evil.md \
            https://127.0.0.1/admin/docs/upload)
        case \"\$upload_status\" in 200|303) ;; *) echo \"upload http \$upload_status\" >&2; exit 1 ;; esac
        curl -sk https://127.0.0.1/docs/evil
    "
    [ "$status" -eq 0 ]
    # Escaped form must be present...
    [[ "$output" == *"&lt;script&gt;"* ]]
    # ...and the raw tag must not appear in the rendered output.
    [[ "$output" != *"<script>alert(1)</script>"* ]]
}

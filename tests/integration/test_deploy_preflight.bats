#!/usr/bin/env bats
#
# Pre-flight deploy validation: every test here asserts deploy.sh fails during
# validation BEFORE it touches the VPS. No fake-VPS bringup, no Docker — this
# file runs in the cheap tier. Tests that need a live stack stay in
# test_deploy.bats.

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    # render_authelia_config (called for every deploy.sh run, before any of
    # the gates under test) dies on a missing OIDC hash / Authelia secret
    # files. stub_authelia_for_tests is helpers.bash's no-Docker stub for
    # exactly this (used by test_deploy_stack_only.bats): it writes
    # placeholder secret files + a fake OIDC hash into $LDS_CONFIG, no
    # Docker/Authelia CLI involved.
    stub_authelia_for_tests
    # Override the stub's users DB with the static fixture (a literal
    # argon2id hash — see Task 1/7 notes) so every test starts from a known-
    # valid, non-empty users database; individual tests below break it.
    cp "$ROOT/tests/integration/fixtures/valid_users_database.yml" "$TMPDIR/users_database.yml"
    export LDS_USERS_DB="$TMPDIR/users_database.yml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    printf 'flashertok' > "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE" "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
}
teardown() { teardown_tmpdir; }

@test "deploy: rejects config with invalid hash before touching VPS" {
    cp "$ROOT/tests/integration/fixtures/bad_hash_config.yaml" "$LDS_CONFIG"
    yq -i ".vps.host = \"127.0.0.1\"" "$LDS_CONFIG"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]] || false
}

@test "deploy: fails fast when grafana admin_password is missing" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"set-grafana-password"* ]] || [[ "$output" == *"admin_password"* ]] || false
}

@test "deploy: fails fast when authelia users_database.yml is missing" {
    export LDS_USERS_DB="$TMPDIR/does-not-exist-users.yml"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"users:add"* ]] || false
}

@test "deploy: fails fast when authelia users_database.yml has zero users" {
    printf 'users: {}\n' > "$LDS_USERS_DB"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"users:add"* ]] || false
}

@test "deploy: fails fast when agent_upload_token is missing" {
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"rotate-agent-upload-token"* ]] || false
}

# Every host-side data dir bind-mounted by the compose template must be
# excluded from the deploy rsync. Without the exclude, `rsync -az --delete`
# removes the directory out from under the running container: redis lost its
# AOF this way, went unhealthy, and dragged authelia down with it (authelia
# depends_on redis with condition: service_healthy). Asserted generically so
# the next service that adds a data volume cannot reintroduce the bug.
@test "deploy: every compose data volume has a matching rsync --delete exclude" {
    local dir missing=()
    while IFS= read -r dir; do
        grep -q -- "--exclude='$dir/'" "$ROOT/scripts/deploy.sh" || missing+=("$dir")
    done < <(grep -oE '\./[a-z_]+_(data|config):' "$ROOT/compose/docker-compose.yml.tmpl" \
             | sed -E 's#^\./##; s#:$##' | sort -u)
    if [ "${#missing[@]}" -ne 0 ]; then
        echo "compose bind-mounts these host dirs but deploy.sh does not exclude them"
        echo "from rsync --delete: ${missing[*]}"
        false
    fi
}

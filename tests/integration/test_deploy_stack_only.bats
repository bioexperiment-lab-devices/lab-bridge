#!/usr/bin/env bats
# Lightweight (no-Docker) tests for LDS_STACK_ONLY / LDS_REQUIRE_VAULT.
# Uses rsync + ssh spies on PATH instead of a real fake-VPS container.

load helpers

setup() {
    setup_tmpdir
    # Shared secret files required by deploy.sh regardless of mode.
    printf 'testpw' > "$TMPDIR/admin_password"
    chmod 600 "$TMPDIR/admin_password"
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testtok' > "$TMPDIR/agent_upload_token"
    chmod 600 "$TMPDIR/agent_upload_token"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'flashertok' > "$TMPDIR/flasher_upload_token"
    chmod 600 "$TMPDIR/flasher_upload_token"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    # Stub Authelia secrets so render_authelia_config doesn't fail on missing
    # AUTHELIA_GRAFANA_OIDC_SECRET_HASH. Use a throw-away config for the yq -i
    # call; each test overrides LDS_CONFIG inline on its own `run` invocation.
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/stub_config.yaml"
    export LDS_CONFIG="$TMPDIR/stub_config.yaml"
    stub_authelia_for_tests
}
teardown() { teardown_tmpdir; }

@test "deploy.sh: with LDS_STACK_ONLY=1, rsync excludes chisel/users.json and siteapp/clients.json" {
    local rsync_log="$BATS_TEST_TMPDIR/rsync.log"

    # Minimal config with no chisel clients — stack-only mode is valid here.
    local spy_config="$BATS_TEST_TMPDIR/stack_config.yaml"
    cat > "$spy_config" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" }
siteapp: { admin_password_hash: "$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa" }
chisel_clients: []
CFG
    # load_config (sourced by deploy.sh) reads .authelia.grafana_oidc_secret_hash
    # from the config file and overwrites the env var; inject the stub hash so
    # render_authelia_config gets a non-empty value.
    yq -i ".authelia.grafana_oidc_secret_hash = \"${AUTHELIA_GRAFANA_OIDC_SECRET_HASH}\"" "$spy_config"

    local spy_pins="$BATS_TEST_TMPDIR/stack_pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$spy_pins"

    setup_fake_rsync_spy "$rsync_log"

    LDS_STACK_ONLY=1 \
    LDS_SKIP_HEALTHCHECK=1 \
    LDS_PINS_FILE="$spy_pins" \
    LDS_CONFIG="$spy_config" \
        run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]

    run cat "$rsync_log"
    [[ "$output" == *"--exclude=chisel/users.json"* ]]
    [[ "$output" == *"--exclude=siteapp/clients.json"* ]]
}

@test "deploy.sh: with LDS_STACK_ONLY=1 + LDS_REQUIRE_VAULT=1, fails if chisel_clients is non-empty" {
    local spy_config="$BATS_TEST_TMPDIR/leaked_config.yaml"
    cat > "$spy_config" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" }
siteapp: { admin_password_hash: "$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa" }
chisel_clients:
  - name: leaked
    reverse_port: 9001
    password: "should-not-be-here"
CFG

    local spy_pins="$BATS_TEST_TMPDIR/stack_pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$spy_pins"

    LDS_STACK_ONLY=1 \
    LDS_REQUIRE_VAULT=1 \
    LDS_SKIP_HEALTHCHECK=1 \
    LDS_PINS_FILE="$spy_pins" \
    LDS_CONFIG="$spy_config" \
        run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"LDS_REQUIRE_VAULT"* ]]
    [[ "$output" == *"chisel_clients must be empty"* ]]
}

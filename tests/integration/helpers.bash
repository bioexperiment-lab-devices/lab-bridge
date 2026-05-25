# Source from the repo root regardless of where bats was invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Create a fake rsync shim that logs its arguments to a file and exits 0.
# Also creates a fake ssh shim that exits 0 (for the compose up step).
# Usage: setup_fake_rsync_spy <logfile>
# After calling this, prepend "$BATS_TEST_TMPDIR/spy_bin" to PATH.
setup_fake_rsync_spy() {
    local logfile="$1"
    local spy_bin="$BATS_TEST_TMPDIR/spy_bin"
    mkdir -p "$spy_bin"

    # rsync spy: log all args to logfile, exit 0
    cat > "$spy_bin/rsync" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >> "$logfile"
EOF
    chmod +x "$spy_bin/rsync"

    # ssh spy: exit 0 silently (swallows docker compose up/restart calls)
    cat > "$spy_bin/ssh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$spy_bin/ssh"

    export PATH="$spy_bin:$PATH"
}

setup_tmpdir() {
    TMPDIR="$(mktemp -d)"
    export TMPDIR
}

teardown_tmpdir() {
    [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]] && rm -rf "$TMPDIR"
}

fixture() {
    cat "$ROOT/tests/integration/fixtures/$1"
}

# Build the siteapp image on the host and load it into the fake-VPS DinD
# under the tag the test fixture's siteapp.image points at, so deploy.sh's
# `docker compose pull` (now tolerant of pull failures) can be followed by
# a successful `up` against the local image. Idempotent — safe to call
# repeatedly. Must run AFTER provision.sh has installed docker inside the
# fake-VPS (otherwise `docker exec lds-fake-vps docker load` fails because
# nested dockerd isn't installed yet).
load_siteapp_test_image() {
    local fixture_tag
    local repo version
    repo="$(yq -e '.siteapp_image_repo' "$ROOT/tests/integration/fixtures/valid_pins.yaml")"
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
    fixture_tag="${repo}:${version}"
    docker build --load -q -t "$fixture_tag" "$ROOT/services/siteapp" >&2 || return 1
    _save_and_load_into_fake_vps "$fixture_tag"
}

# Mirror of load_siteapp_test_image for the streamer image. Same rationale:
# the fixture's streamer tag (ghcr.io/test/lab-bridge-streamer:VERSION) is
# not pullable, so we build it locally and side-load it into fake-VPS so
# `docker compose up` finds it after `pull --ignore-pull-failures` no-ops.
load_streamer_test_image() {
    local fixture_tag
    local repo version
    repo="$(yq -e '.streamer_image_repo' "$ROOT/tests/integration/fixtures/valid_pins.yaml")"
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
    fixture_tag="${repo}:${version}"
    docker build --load -q -t "$fixture_tag" "$ROOT/services/streamer" >&2 || return 1
    _save_and_load_into_fake_vps "$fixture_tag"
}

# Mirror of load_siteapp_test_image for the flasher image. Same rationale:
# the fixture's flasher tag (ghcr.io/test/lab-bridge-flasher:VERSION) is
# not pullable, so we build it locally and side-load it into fake-VPS so
# `docker compose up` finds it after `pull --ignore-pull-failures` no-ops.
load_flasher_test_image() {
    local fixture_tag
    local repo version
    repo="$(yq -e '.flasher_image_repo' "$ROOT/tests/integration/fixtures/valid_pins.yaml")"
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
    fixture_tag="${repo}:${version}"
    docker build --load -q -t "$fixture_tag" "$ROOT/services/flasher" >&2 || return 1
    _save_and_load_into_fake_vps "$fixture_tag"
}

# Mirror of load_siteapp_test_image for the caddy image. Same rationale:
# the fixture's caddy tag (ghcr.io/test/lab-bridge-caddy:VERSION) is not
# pullable, so we build it locally and side-load it into fake-VPS so
# `docker compose up` finds it after `pull --ignore-pull-failures` no-ops.
load_caddy_test_image() {
    local fixture_tag
    local repo version
    repo="$(yq -e '.caddy_image_repo' "$ROOT/tests/integration/fixtures/valid_pins.yaml")"
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
    fixture_tag="${repo}:${version}"
    docker build --load -q -t "$fixture_tag" "$ROOT/services/caddy" >&2 || return 1
    _save_and_load_into_fake_vps "$fixture_tag"
}

# Pipe an image from the host docker daemon into the fake-VPS DinD via a
# tarball. Caller is responsible for the tag existing on the host first.
_save_and_load_into_fake_vps() {
    local tag="$1"
    local tar
    tar="$(mktemp -t lds-img.XXXXXX.tar)"
    docker save "$tag" -o "$tar"
    docker cp "$tar" lds-fake-vps:/tmp/img.tar
    docker exec lds-fake-vps sudo docker load -i /tmp/img.tar >/dev/null
    rm -f "$tar"
}

# Pre-load any images already cached on the host into the fake-VPS. This
# sidesteps Docker Hub anonymous-pull rate limits during repeated test runs:
# `docker compose pull --ignore-pull-failures` then no-ops when the image is
# already present in the DinD's cache. Skips any image that isn't on the host.
preload_fake_vps_images() {
    local imgs=(
        caddy:2
        jpillora/chisel:1.10.1
        grafana/loki:3.2.1
        grafana/grafana:11.3.0
        quay.io/jupyter/scipy-notebook:2026-04-20
        authelia/authelia:4.38.10
    )
    local img
    for img in "${imgs[@]}"; do
        if docker image inspect "$img" >/dev/null 2>&1; then
            _save_and_load_into_fake_vps "$img" || true
        fi
    done
}

# Returns 0 when every compose-service image listed in the fixture is either
# present on the host (and therefore preload-able into fake-VPS) or builds
# locally. Returns 1 when the host environment can't satisfy the test —
# typically a Docker Hub anonymous-pull rate limit on the CI runner. Use as
# `compose_images_available || skip "host docker can't reach all images"`.
compose_images_available() {
    local imgs=(
        caddy:2
        jpillora/chisel:1.10.1
        grafana/loki:3.2.1
        grafana/grafana:11.3.0
        quay.io/jupyter/scipy-notebook:2026-04-20
        authelia/authelia:4.38.10
    )
    local img
    for img in "${imgs[@]}"; do
        if ! docker image inspect "$img" >/dev/null 2>&1; then
            if ! docker pull "$img" >/dev/null 2>&1; then
                return 1
            fi
        fi
    done
    return 0
}

# Patch the deployed Caddyfile inside the fake-VPS to use `tls internal`
# instead of the real ACME issuer (Let's Encrypt cannot issue a cert for
# 127.0.0.1, so the production Caddyfile fails TLS in the test container).
# Restarts caddy so the new config takes effect. After this runs,
# `wget --no-check-certificate https://127.0.0.1/...` from inside any
# container on the labnet returns the actual handler response (200/302/401).
patch_caddyfile_tls_internal() {
    docker exec lds-fake-vps bash -c '
        sed -i "s|issuer acme {|issuer internal {|; /profile shortlived/d" \
            /srv/lab-bridge/Caddyfile
        cd /srv/lab-bridge && docker compose restart caddy >/dev/null
    '
    # Give caddy a moment to come back up.
    local i
    for i in $(seq 1 30); do
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T caddy \
                wget --no-check-certificate -q -O - "https://127.0.0.1/" >/dev/null 2>&1
        '; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Mirror of load_siteapp_test_image for the Authelia image. The fixture's
# authelia tag (ghcr.io/test/lab-bridge-authelia:VERSION) is not pullable, so
# we build it locally (it's a thin FROM authelia/authelia:... passthrough) and
# side-load it into fake-VPS so `docker compose up` finds it after `pull
# --ignore-pull-failures` no-ops.
load_authelia_test_image() {
    local fixture_tag
    local repo version
    repo="$(yq -e '.authelia_image_repo' "$ROOT/tests/integration/fixtures/valid_pins.yaml")"
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
    fixture_tag="${repo}:${version}"
    docker build --load -q -t "$fixture_tag" "$ROOT/services/authelia" >&2 || return 1
    _save_and_load_into_fake_vps "$fixture_tag"
}

# Wait for Authelia's /api/health to return 200 inside the fake-VPS network.
# Returns non-zero on timeout. Call after deploy + patch_caddyfile_tls_internal.
wait_authelia_ready() {
    local i
    local deadline=$(( $(date +%s) + 120 ))
    for i in $(seq 1 60); do
        if [[ $(date +%s) -ge $deadline ]]; then
            echo "wait_authelia_ready: timed out after 120s" >&2
            return 1
        fi
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T authelia \
                wget -q -O- http://127.0.0.1:9091/api/health >/dev/null 2>&1
        '; then
            return 0
        fi
        sleep 2
    done
    return 1
}

# Bootstrap Authelia secrets with REAL cryptographic material via the authelia
# CLI. Required for tests that bring up the real Authelia container.
# Prerequisite: $LDS_CONFIG must point to a writable config.yaml; $TMPDIR must exist.
bootstrap_authelia_for_tests() {
    export LDS_AUTHELIA_SECRETS_DIR="$TMPDIR/authelia_secrets"
    export LDS_GRAFANA_OIDC_SECRET_FILE="$TMPDIR/grafana_oidc_secret"
    export AUTHELIA_IMAGE
    AUTHELIA_IMAGE="$(yq e '.authelia_image' "$ROOT/compose/pins.yaml")"
    bash "$ROOT/scripts/secrets.sh" bootstrap-authelia
    export AUTHELIA_GRAFANA_OIDC_SECRET_HASH
    AUTHELIA_GRAFANA_OIDC_SECRET_HASH="$(yq e '.authelia.grafana_oidc_secret_hash' "$LDS_CONFIG")"
    # Stage the users database file alongside secrets so the deploy rsyncs
    # an empty-but-present file rather than fabricating one inline.
    # Authelia 4.38 rejects an empty users map (users: {}), so we include a
    # disabled stub account that satisfies the schema without granting access.
    export LDS_USERS_DB="$TMPDIR/authelia_users_database.yml"
    cat > "$LDS_USERS_DB" <<'USERSEOF'
users:
  _stub:
    displayname: Stub
    password: '$argon2id$v=19$m=65536,t=3,p=4$iNzLZUasKgeeGpEP6ugJBA$59JMNV5RK+f4FPe/XZh+pljt5iEuzt8P4CcLBKp/izQ'
    email: stub@example.invalid
    disabled: true
    groups: []
USERSEOF
}

# Lightweight stub: create placeholder Authelia secret files and write a fake
# hash to the config. For tests that DON'T bring up a real Authelia container
# (spy/no-Docker tests like test_deploy_stack_only.bats).
# Prerequisite: $LDS_CONFIG must point to a writable config.yaml; $TMPDIR exists.
stub_authelia_for_tests() {
    export LDS_AUTHELIA_SECRETS_DIR="$TMPDIR/authelia_secrets"
    export LDS_GRAFANA_OIDC_SECRET_FILE="$TMPDIR/grafana_oidc_secret"
    mkdir -p "$LDS_AUTHELIA_SECRETS_DIR"
    for f in jwt_secret session_secret storage_encryption_key oidc_hmac_secret oidc_jwks_key.pem; do
        printf 'stub' > "$LDS_AUTHELIA_SECRETS_DIR/$f"
    done
    printf 'stub' > "$LDS_GRAFANA_OIDC_SECRET_FILE"
    export AUTHELIA_GRAFANA_OIDC_SECRET_HASH='$pbkdf2-sha512$310000$c3R1Yg$c3R1Yg'
    yq -i ".authelia.grafana_oidc_secret_hash = \"\$pbkdf2-sha512\$310000\$c3R1Yg\$c3R1Yg\"" "$LDS_CONFIG"
    export LDS_USERS_DB="$TMPDIR/authelia_users_database.yml"
    cat > "$LDS_USERS_DB" <<'USERSEOF'
users:
  _stub:
    displayname: Stub
    password: '$argon2id$v=19$m=65536,t=3,p=4$iNzLZUasKgeeGpEP6ugJBA$59JMNV5RK+f4FPe/XZh+pljt5iEuzt8P4CcLBKp/izQ'
    email: stub@example.invalid
    disabled: true
    groups: []
USERSEOF
}

# Bring up the fake-VPS with a full Authelia-enabled stack and seed user
# accounts. Intended for setup_file() in auth smoke tests.
#
# Usage: fake_vps_up_with_users user1:password1:group1 [user2:password2:group2 ...]
#
# Skips (writes a skip file) if compose images are unavailable. Call setup()
# at the start of each test to honour the skip file.
#
# After this returns, the following variables are exported:
#   TMPDIR            — scratch directory for this file's run
#   FAKE_VPS_HOST     — host:port for curl (127.0.0.1:2443)
#   LDS_CONFIG        — path to the rendered config.yaml
#   LDS_PINS_FILE     — path to the rendered pins.yaml
#   LDS_USERS_DB      — path to the populated users_database.yml
fake_vps_up_with_users() {
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi

    bash "$ROOT/tests/integration/fake_vps/start.sh"
    setup_tmpdir

    # ── Config + pins ──────────────────────────────────────────────────────
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"

    # ── Bootstrap Authelia secrets ─────────────────────────────────────────
    # Use the real Authelia image for PBKDF2 hashing so the rendered
    # configuration.yml contains a hash that Authelia's config parser accepts.
    # authelia/authelia:4.38.10 is guaranteed present (compose_images_available
    # checked for it above). One docker run here, no LDS_PBKDF2_HASH_CMD bypass.
    bootstrap_authelia_for_tests

    # ── Seed users (before deploy so rsync ships the populated DB) ─────────
    # Real argon2id hashing via `docker run authelia/authelia hash-password`
    # is required so Authelia can actually verify the test passwords at
    # login time. The authelia/authelia image is guaranteed present on the
    # host because compose_images_available() checks for it above.
    local triple user password group
    for triple in "$@"; do
        user="${triple%%:*}"
        password="${triple#*:}"
        group="${password##*:}"
        password="${password%%:*}"
        PASSWORD="$password" bash "$ROOT/scripts/users.sh" add "$user" "$group"
    done

    # ── SSH / deploy env ───────────────────────────────────────────────────
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

    # ── Provision + load images + deploy ──────────────────────────────────
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
    wait_authelia_ready

    # ── Export host-side address for curl ─────────────────────────────────
    # Caddy's HTTPS is exposed on host port 2443 (start.sh: -p 2443:443).
    export FAKE_VPS_HOST="127.0.0.1:2443"
}

# Wait for siteapp's /healthz to return 200 inside the fake-VPS network,
# AND for Caddy to successfully reach siteapp on a public route. The second
# gate matters because patch_caddyfile_tls_internal restarts caddy, and
# caddy's upstream resolution to siteapp races with test probes — without
# this, the first probe through Caddy's HTTPS sometimes hits an upstream
# that hasn't resolved yet, manifesting as a flaky 502/connection-error.
# Returns non-zero on timeout.
wait_siteapp_ready() {
    local i
    # Hard wallclock cap: the bats step in pr.yml has a 12-min timeout, but a
    # per-helper cap gives faster diagnostic failure and prevents the job from
    # hanging until cancellation.
    local deadline=$(( $(date +%s) + 120 ))
    # Gate 1: siteapp's own /healthz inside the container.
    for i in $(seq 1 60); do
        if [[ $(date +%s) -ge $deadline ]]; then
            echo "wait_siteapp_ready: gate 1 timed out after 120s" >&2
            return 1
        fi
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T siteapp \
                python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen(\"http://127.0.0.1:8000/healthz\").status==200 else 1)" \
                >/dev/null 2>&1
        '; then
            break
        fi
        sleep 1
    done
    # Gate 2: Caddy can reach siteapp on a public route. After patch_caddyfile_tls_internal
    # restarts caddy, the caddy→siteapp upstream resolution races test probes; this loop
    # waits until /docs/ and /download/agent both return 200 through HTTPS.
    for i in $(seq 1 30); do
        if [[ $(date +%s) -ge $deadline ]]; then
            echo "wait_siteapp_ready: gate 2 timed out after 120s" >&2
            return 1
        fi
        if docker exec lds-fake-vps bash -c '
            cd /srv/lab-bridge && docker compose exec -T caddy sh -c "
                wget --no-check-certificate -q -O /dev/null https://127.0.0.1/docs/ &&
                wget --no-check-certificate -q -O /dev/null https://127.0.0.1/download/agent
            " >/dev/null 2>&1
        '; then
            return 0
        fi
        sleep 1
    done
    return 1
}

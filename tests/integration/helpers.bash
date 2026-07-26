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
    # Remember what we created so teardown_tmpdir removes only that. See the
    # warning there.
    _LDS_OWNED_TMPDIR="$TMPDIR"
}

teardown_tmpdir() {
    # Removes only the directory setup_tmpdir created — NOT whatever $TMPDIR
    # currently points at.
    #
    # This used to be `[[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]] && rm -rf
    # "$TMPDIR"`, which has two faults. bats runs teardown even for SKIPPED
    # tests, and the heavy suites call `skip` from setup() *before*
    # setup_tmpdir runs — so on that path $TMPDIR is still the ambient system
    # temp directory (/tmp, or /var/folders/…/T/ on macOS), and it is a
    # directory, so the guard passed and the `rm -rf` targeted the whole
    # system temp dir. Second, as the last statement of the function a bare &&
    # list makes its own status the function's, so a failed or skipped cleanup
    # returned 1 and bats reported `not ok … # skip` — a red required check
    # for a suite that deliberately ran nothing. That is what the ops cell hit
    # the first time it was rate-limited.
    if [[ -n "${_LDS_OWNED_TMPDIR:-}" && -d "$_LDS_OWNED_TMPDIR" ]]; then
        rm -rf "$_LDS_OWNED_TMPDIR"
    fi
    unset _LDS_OWNED_TMPDIR
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

# Read a single scalar field from a YAML file. Wraps `yq -e` (which already
# fails on a missing/null/false result) so a caller can chain `|| return 1`
# instead of getting yq's default behaviour of printing the literal string
# "null" and exiting 0 — the exact failure mode that let a renamed/missing
# fixture key silently masquerade as a real (bogus) image name.
_yq_field() {
    local val
    val="$(yq -e "$1" "$2")" || return 1
    printf '%s\n' "$val"
}

# Image set the active suite profile needs, derived from the test fixture so
# a fixture bump can never silently desync the preload list.
#
#   full (default) — the whole stack, including the multi-GB scipy-notebook
#                    and the studio image
#   core           — caddy/chisel/authelia only
#
# Every fixture read below goes through _yq_field (`yq -e`) and returns
# non-zero on failure instead of emitting the literal string "null" for a
# missing/renamed key. See preload_fake_vps_images/compose_images_available
# below for how that failure propagates to callers.
#
# CONTRACT — what `core` does and does NOT do: it trims the PRELOAD set and
# the compose_images_available SKIP-GUARD coverage only. It has NO effect on
# scripts/lib/config.sh's `disabled_services`, so by itself it does NOT stop
# deploy.sh from bringing jupyter/studio/monitoring up. `core` is only safe
# for a suite that additionally satisfies one of:
#   (a) it brings the stack up via fake_vps_up_with_users() below, which
#       applies its own disabled_services override for this profile;
#   (b) it sets `disabled_services` itself in its own inline bring-up;
#   (c) it never deploys the stack at all.
# See the `profile` comment block in .github/workflows/pr-platform.yml for
# which of the current 8 heavy suites satisfy which condition. A suite that
# wires bring-up inline without (b) or a deploy step gets NO free pass from
# `core`: deploy.sh would still bring the trimmed-out services up, just
# without preload or skip-guard coverage for them — trading a graceful
# rate-limit skip for a hard mid-deploy pull failure.
#
# authelia_image is deliberately read from the PRODUCTION images file
# (compose/images.yaml), NOT the fixture: the fixture's authelia_image
# (fixtures/valid_images.yaml) is a placeholder tag
# (ghcr.io/test/lab-bridge-authelia:0.0.0) that only satisfies config
# validation and is never pulled or built — the real upstream
# authelia/authelia:<version> pin (compose/images.yaml) is what
# bootstrap_authelia_for_tests / scripts/users.sh actually need on the host to
# build the local authelia test image FROM. Probing the fixture's fake tag
# here would 404 every run and make compose_images_available skip every
# heavy suite unconditionally.
#
# $1 (optional): override the fixture path. Production callers
# (preload_fake_vps_images, compose_images_available) always call this with
# no arguments; the override exists only so tests can point at a
# deliberately-broken fixture copy without touching the tracked one.
#
# SC2120: shellcheck sees no caller passing $1 because the only ones that do
# live in test_common.bats, a different file. The parameter is deliberate —
# see the paragraph above.
# shellcheck disable=SC2120
_profile_images() {
    local fixture="${1:-$ROOT/tests/integration/fixtures/valid_images.yaml}"
    local profile="${LDS_SUITE_PROFILE:-full}"
    printf '%s\n' caddy:2
    _yq_field '.chisel_image' "$fixture" || return 1
    _yq_field '.authelia_image' "$ROOT/compose/images.yaml" || return 1
    # redis backs Authelia's session store and authelia depends_on it with
    # condition: service_healthy, so it sits above the `core` cut-off: a
    # core-profile bring-up would otherwise stall on an image it never
    # preloaded and got no skip-guard coverage for.
    _yq_field '.redis_image' "$fixture" || return 1
    [[ "$profile" == "core" ]] && return 0
    _yq_field '.loki_image' "$fixture" || return 1
    _yq_field '.grafana_image' "$fixture" || return 1
    _yq_field '.jupyter_image' "$fixture" || return 1
    _yq_field '.studio_image' "$fixture" || return 1
}

# Pre-load any images already cached on the host into the fake-VPS. This
# sidesteps Docker Hub anonymous-pull rate limits during repeated test runs:
# `docker compose pull --ignore-pull-failures` then no-ops when the image is
# already present in the DinD's cache. Skips any image that isn't on the host.
#
# _profile_images's output is captured into a variable rather than fed
# straight into `while ... < <(_profile_images)`: process substitution
# discards the producer's exit status, so a failed read would otherwise
# silently preload a short/null list instead of failing. See
# compose_images_available below for why that failure aborts the process
# instead of just returning 1.
preload_fake_vps_images() {
    local images img
    if ! images="$(_profile_images)"; then
        echo "preload_fake_vps_images: _profile_images failed — likely a missing/renamed fixture key (see yq error above); aborting rather than silently preloading a short/null list" >&2
        exit 1
    fi
    while IFS= read -r img; do
        [[ -z "$img" ]] && continue
        if docker image inspect "$img" >/dev/null 2>&1; then
            _save_and_load_into_fake_vps "$img" || true
        fi
    done <<< "$images"
}

# Returns 0 when every compose-service image listed in the fixture is either
# present on the host (and therefore preload-able into fake-VPS) or builds
# locally. Returns 1 when the host environment can't satisfy the test —
# typically a Docker Hub anonymous-pull rate limit on the CI runner. Use as
# `compose_images_available || skip "host docker can't reach all images"`.
#
# A `_profile_images` failure (broken fixture) is deliberately NOT reported
# via this function's ordinary `return 1`: every caller treats `return 1` as
# "rate limited, skip gracefully", which would turn a fixture-desync bug into
# a permanently silent skip — green CI, heavy suite never actually runs. So
# that failure mode aborts the whole process instead of returning, and can't
# be swallowed by an `if ! compose_images_available; then skip; fi` guard.
#
# LDS_REQUIRE_IMAGES=1 extends that same reasoning to the rate-limit path.
# pr-platform.yml sets it on release-please PRs, which are the integration
# gate in front of the production deploy: there, "couldn't pull anything, so
# I tested nothing" has to be a red check rather than a green one. Observed
# on the 0.41.1 release PR, where routes-smoke reported success with all 18
# of its tests skipped. Mirrors deploy.sh's LDS_REQUIRE_VAULT=1 idiom.
compose_images_available() {
    local images img
    if ! images="$(_profile_images)"; then
        echo "compose_images_available: _profile_images failed — likely a missing/renamed fixture key (see yq error above); this is a test-infra bug, not a rate limit, so failing hard instead of returning the ordinary skip-worthy 1" >&2
        exit 1
    fi
    while IFS= read -r img; do
        [[ -z "$img" ]] && continue
        if ! docker image inspect "$img" >/dev/null 2>&1; then
            if ! _docker_pull_retry "$img"; then
                if [[ "${LDS_REQUIRE_IMAGES:-}" == "1" ]]; then
                    echo "compose_images_available: LDS_REQUIRE_IMAGES=1 and '$img' could not be pulled. This suite must not report success having tested nothing — failing hard instead of skipping gracefully." >&2
                    exit 1
                fi
                return 1
            fi
        fi
    done <<< "$images"
    return 0
}

# docker pull with a short backoff. Docker Hub throttles anonymous pulls per
# IP, and a release PR fires every heavy matrix cell at once — that burst is
# what trips the limit, and it clears within seconds. Retrying turns most of
# those transient 429s into a real run instead of a silent skip.
# LDS_PULL_RETRY_DELAYS exists so tests can drive this without sleeping.
_docker_pull_retry() {
    local img="${1:?}" delay
    for delay in ${LDS_PULL_RETRY_DELAYS-0 5 15}; do
        if [[ "$delay" != "0" ]]; then
            sleep "$delay"
        fi
        if docker pull "$img" >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
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
    for _ in $(seq 1 30); do
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
    local deadline=$(( $(date +%s) + 120 ))
    for _ in $(seq 1 60); do
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
    AUTHELIA_IMAGE="$(yq e '.authelia_image' "$ROOT/compose/images.yaml")"
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
#   LDS_IMAGES_FILE   — path to the rendered images.yaml
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
    # This is mechanism (a) from the CONTRACT note above _profile_images:
    # a `core` profile suite that brings the stack up via THIS helper gets
    # jupyter/studio/monitoring disabled here, so deploy.sh skips both their
    # preload and their startup. Suites that wire bring-up inline instead of
    # calling this helper do NOT get this override for free — see the
    # CONTRACT note for the other two ways a suite can safely use `core`.
    if [[ "${LDS_SUITE_PROFILE:-full}" == "core" ]]; then
        yq -i '.disabled_services = ["jupyter", "studio", "monitoring"]' "$TMPDIR/config.yaml"
    fi
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"

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
    # Hard wallclock cap: the bats step in pr.yml has a 12-min timeout, but a
    # per-helper cap gives faster diagnostic failure and prevents the job from
    # hanging until cancellation.
    local deadline=$(( $(date +%s) + 120 ))
    # Gate 1: siteapp's own /healthz inside the container.
    # `_`, not `i`: the counter is unused — $deadline above is the real bound.
    for _ in $(seq 1 60); do
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
    # `_`, not `i`: the counter is unused — $deadline below is the real bound.
    for _ in $(seq 1 30); do
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

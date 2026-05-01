# Source from the repo root regardless of where bats was invoked.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_tmpdir() {
    TMPDIR="$(mktemp -d)"
    export TMPDIR
}

teardown_tmpdir() {
    [[ -n "${TMPDIR:-}" && -d "$TMPDIR" ]] && rm -rf "$TMPDIR"
}

fixture() {
    cat "$ROOT/tests/fixtures/$1"
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
    fixture_tag="$(yq -e '.siteapp.image' "$ROOT/tests/fixtures/valid_config.yaml")"
    docker build --load -q -t "$fixture_tag" "$ROOT/compose/siteapp" >&2 || return 1
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

# Wait for siteapp's /healthz to return 200 inside the fake-VPS network,
# AND for Caddy to successfully reach siteapp on a public route. The second
# gate matters because patch_caddyfile_tls_internal restarts caddy, and
# caddy's upstream resolution to siteapp races with test probes — without
# this, the first probe through Caddy's HTTPS sometimes hits an upstream
# that hasn't resolved yet, manifesting as a flaky 502/connection-error.
# Returns non-zero on timeout.
wait_siteapp_ready() {
    local i
    # Gate 1: siteapp's own /healthz inside the container.
    for i in $(seq 1 60); do
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

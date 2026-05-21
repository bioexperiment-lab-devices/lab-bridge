# Unified Authelia Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-service shared passwords (Jupyter, Flasher, Grafana) with a single Authelia identity provider gating those services by group, surfaced through a custom login form, 403, and 404 pages in siteapp's navbar shell, with task-automated user management.

**Architecture:** A new `services/authelia/` containerised IdP joins the stack on `labnet`. Caddy exposes `/auth/*` publicly for OIDC redirects + JWKS; everything else stays internal. Flasher and JupyterLab go behind Caddy's `forward_auth`. Grafana uses native OIDC against Authelia. Siteapp owns `/login`, `/logout`, `/api/auth/*`, and `/_errors/*` routes — all extend `base.html` so the global navbar (Caddy `replace-response` injection) wraps them. The navbar JS gains an `.auth-slot` that calls `/api/auth/whoami` on boot and renders an avatar or login link. User management runs through `scripts/users.sh` + a new `task users:*` group; Authelia secrets bootstrap through `task secrets:bootstrap-authelia`.

**Tech Stack:** Authelia 4.38.x (file-backed users, SQLite storage, argon2id hashes, OIDC issuer), Caddy 2 with `forward_auth`, Grafana generic OAuth, FastAPI + Jinja2 (siteapp), Bash + `yq` + `docker run` (tooling), bats-core (integration), pytest + httpx (service e2e).

**Spec:** `docs/superpowers/specs/2026-05-20-unified-authelia-auth-design.md`

---

## File Structure

**New files:**
- `services/authelia/Dockerfile`
- `services/authelia/build.sh`
- `services/authelia/README.md`
- `services/authelia/config/configuration.yml.tmpl`
- `services/authelia/tests/e2e/conftest.py`
- `services/authelia/tests/e2e/compose.yaml`
- `services/authelia/tests/e2e/fixtures/users_database.yml`
- `services/authelia/tests/e2e/fixtures/configuration.yml`
- `services/authelia/tests/e2e/test_firstfactor.py`
- `services/authelia/tests/e2e/test_forward_auth.py`
- `services/authelia/tests/e2e/test_oidc_discovery.py`
- `services/authelia/tests/e2e/test_group_gating.py`
- `.github/workflows/pr-authelia.yml`
- `scripts/users.sh`
- `services/siteapp/app/auth.py`
- `services/siteapp/app/templates/login.html`
- `services/siteapp/app/templates/error_403.html`
- `services/siteapp/app/templates/error_404.html`
- `services/siteapp/tests/e2e/fixtures/authelia_users.yml`
- `services/siteapp/tests/e2e/fixtures/authelia_config.yml`
- `services/siteapp/tests/e2e/test_login_page.py`
- `services/siteapp/tests/e2e/test_login_flow.py`
- `services/siteapp/tests/e2e/test_whoami.py`
- `services/siteapp/tests/e2e/test_logout.py`
- `services/siteapp/tests/e2e/test_error_pages.py`
- `tests/integration/test_auth_smoke.bats`
- `docs/adding-a-user.md`

**Modified files:**
- `compose/pins.yaml`
- `scripts/lib/render.sh`
- `scripts/secrets.sh`
- `Taskfile.yml`
- `compose/docker-compose.yml.tmpl`
- `compose/Caddyfile.tmpl`
- `services/siteapp/app/main.py`
- `services/siteapp/tests/e2e/compose.yaml`
- `services/siteapp/pyproject.toml` (if `httpx` is not already a runtime dep — it's already in test deps; add to deps)
- `compose/shell/navbar.js`
- `tests/integration/test_render.bats`
- `.github/workflows/pr-platform.yml`
- `config.example.yaml`
- `README.md`

---

## Task 1: Authelia container scaffold

**Files:**
- Create: `services/authelia/Dockerfile`
- Create: `services/authelia/build.sh`
- Create: `services/authelia/README.md`
- Modify: `compose/pins.yaml`

- [ ] **Step 1: Add Authelia image pin to `compose/pins.yaml`**

Append after `flasher_image_repo`:

```yaml
# Authelia identity provider. Renovate-managed.
authelia_image: authelia/authelia:4.38.10

# GHCR repository for the (currently passthrough) authelia image.
# We rebuild upstream Authelia under our own GHCR namespace to keep image
# provenance + Sigstore attestation uniform across the stack. The image
# *tag* lives in the root VERSION (release-please-managed); the full
# reference is "${authelia_image_repo}:$(cat VERSION)".
authelia_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-authelia
```

- [ ] **Step 2: Create `services/authelia/Dockerfile`**

```dockerfile
# Re-publishes upstream authelia/authelia under our GHCR namespace so the
# image carries the same Sigstore attestation chain as siteapp / flasher / caddy.
# The tag (root VERSION, release-please-managed) is what gets bumped; the base
# pin lives in compose/pins.yaml and is Renovate-managed.
ARG AUTHELIA_VERSION=4.38.10
FROM authelia/authelia:${AUTHELIA_VERSION}
```

- [ ] **Step 3: Create `services/authelia/build.sh`**

Copy `services/flasher/build.sh` verbatim, then edit:
- Replace every `flasher` token with `authelia`.
- Replace `FLASHER_IMAGE_REPO` with `AUTHELIA_IMAGE_REPO`.

(The script reads VERSION + the `*_image_repo` field from `compose/pins.yaml` to compute the full image reference and pushes it.)

- [ ] **Step 4: Create `services/authelia/README.md`**

```markdown
# services/authelia

Authelia identity provider for lab-bridge. Single-factor (username + password),
file-backed users, two fixed groups (`admins`, `researchers`).

See `docs/superpowers/specs/2026-05-20-unified-authelia-auth-design.md` for the
overall design.

## Building locally

```bash
bash services/authelia/build.sh
```

Pushes `${AUTHELIA_IMAGE_REPO}:$(cat VERSION)` to GHCR.

## E2E tests

```bash
cd services/authelia && uv run pytest tests/e2e/
```

The fixture compose file spins up an Authelia container with a seeded users
file. Each test hits the container directly over HTTP.

## User management

Out-of-band, via the platform:

```bash
task users:add USER
task users:rm USER
task users:set-password USER
task users:set-groups USER
task users:list
```
```

- [ ] **Step 5: Commit**

```bash
git add services/authelia/ compose/pins.yaml
git commit -m "feat(authelia): scaffold service directory and pin image"
```

---

## Task 2: Authelia configuration template

**Files:**
- Create: `services/authelia/config/configuration.yml.tmpl`

- [ ] **Step 1: Create the configuration template**

`services/authelia/config/configuration.yml.tmpl`:

```yaml
# Rendered at deploy time by scripts/lib/render.sh::render_authelia_config.
# Tokens substituted: __VPS_HOST__, __GRAFANA_OIDC_SECRET_HASH__.
# Secret material (JWT, session, storage encryption, OIDC HMAC, OIDC JWKS key)
# is injected via *_FILE env vars from docker secrets — see
# compose/docker-compose.yml.tmpl.

theme: light
default_redirection_url: https://__VPS_HOST__/

server:
  host: 0.0.0.0
  port: 9091

log:
  level: info
  format: text

totp:
  issuer: lab-bridge

authentication_backend:
  password_reset:
    disable: true
  refresh_interval: 30s
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2id

access_control:
  default_policy: deny
  rules:
    - domain: __VPS_HOST__
      resources:
        - '^/flash.*'
      policy: one_factor
      subject: 'group:admins'
    - domain: __VPS_HOST__
      resources:
        - '^/jupyter.*'
      policy: one_factor
      subject:
        - 'group:admins'
        - 'group:researchers'
    - domain: __VPS_HOST__
      resources:
        - '^/grafana/.*'
      policy: one_factor
      subject:
        - 'group:admins'
        - 'group:researchers'

session:
  name: authelia_session
  domain: __VPS_HOST__
  same_site: lax
  expiration: 1h
  inactivity: 5m
  remember_me_duration: 2160h    # 90 days

regulation:
  max_retries: 3
  find_time: 2m
  ban_time: 5m

storage:
  local:
    path: /data/db.sqlite3

notifier:
  disable_startup_check: true
  filesystem:
    filename: /data/notification.txt

identity_providers:
  oidc:
    cors:
      endpoints:
        - authorization
        - token
        - revocation
        - introspection
        - userinfo
    clients:
      - id: grafana
        description: Grafana
        secret: '__GRAFANA_OIDC_SECRET_HASH__'
        public: false
        authorization_policy: one_factor
        redirect_uris:
          - https://__VPS_HOST__/grafana/login/generic_oauth
        scopes:
          - openid
          - profile
          - email
          - groups
        grant_types:
          - authorization_code
          - refresh_token
        response_types:
          - code
        userinfo_signing_algorithm: none
```

- [ ] **Step 2: Commit**

```bash
git add services/authelia/config/configuration.yml.tmpl
git commit -m "feat(authelia): add configuration template"
```

---

## Task 3: Authelia e2e test suite

**Files:**
- Create: `services/authelia/tests/e2e/conftest.py`
- Create: `services/authelia/tests/e2e/compose.yaml`
- Create: `services/authelia/tests/e2e/fixtures/users_database.yml`
- Create: `services/authelia/tests/e2e/fixtures/configuration.yml`
- Create: `services/authelia/tests/e2e/fixtures/secrets/` (5 files, see below)
- Create: `services/authelia/tests/e2e/test_firstfactor.py`
- Create: `services/authelia/tests/e2e/test_forward_auth.py`
- Create: `services/authelia/tests/e2e/test_oidc_discovery.py`
- Create: `services/authelia/tests/e2e/test_group_gating.py`
- Create: `services/authelia/pyproject.toml`

- [ ] **Step 1: Create `services/authelia/pyproject.toml`**

Mirror `services/siteapp/pyproject.toml`:

```toml
[project]
name = "lab-bridge-authelia-tests"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "pytest>=8",
]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create test fixtures**

`services/authelia/tests/e2e/fixtures/users_database.yml`:

```yaml
users:
  alice:
    displayname: Alice
    # Hash of "alice-password" (argon2id, default parameters).
    # Generate via: docker run --rm authelia/authelia:4.38.10 \
    #   authelia hash-password 'alice-password' --no-confirm
    password: '<paste hash here at task execution time>'
    email: alice@example.test
    groups: [admins]
  bob:
    displayname: Bob
    # Hash of "bob-password" (argon2id).
    password: '<paste hash here at task execution time>'
    email: bob@example.test
    groups: [researchers]
```

`services/authelia/tests/e2e/fixtures/configuration.yml`: a rendered copy of
`services/authelia/config/configuration.yml.tmpl` with `__VPS_HOST__` set to
`test.local` and `__GRAFANA_OIDC_SECRET_HASH__` set to the PBKDF2 hash of a
known test secret. Generate the hash at task execution time:

```bash
docker run --rm authelia/authelia:4.38.10 \
  authelia crypto hash generate pbkdf2 --variant sha512 \
  --password 'grafana-test-secret'
```

Generate the five fixture secret files under
`services/authelia/tests/e2e/fixtures/secrets/`:

```bash
mkdir -p services/authelia/tests/e2e/fixtures/secrets
cd services/authelia/tests/e2e/fixtures/secrets
openssl rand -hex 64 > jwt_secret
openssl rand -hex 64 > session_secret
openssl rand -hex 64 > storage_encryption_key
openssl rand -hex 64 > oidc_hmac_secret
openssl genrsa -out oidc_jwks_key.pem 4096
chmod 600 *
```

These are test-only secrets; they live under git and never touch production.

- [ ] **Step 3: Create `services/authelia/tests/e2e/compose.yaml`**

```yaml
services:
  authelia:
    image: ${AUTHELIA_TEST_IMAGE:-authelia/authelia:4.38.10}
    ports:
      - "127.0.0.1:9091:9091"
    volumes:
      - ./fixtures/configuration.yml:/config/configuration.yml:ro
      - ./fixtures/users_database.yml:/config/users_database.yml:ro
      - ./fixtures/secrets/jwt_secret:/run/secrets/jwt_secret:ro
      - ./fixtures/secrets/session_secret:/run/secrets/session_secret:ro
      - ./fixtures/secrets/storage_encryption_key:/run/secrets/storage_encryption_key:ro
      - ./fixtures/secrets/oidc_hmac_secret:/run/secrets/oidc_hmac_secret:ro
      - ./fixtures/secrets/oidc_jwks_key.pem:/run/secrets/oidc_jwks_key.pem:ro
      - authelia_data:/data
    environment:
      AUTHELIA_JWT_SECRET_FILE: /run/secrets/jwt_secret
      AUTHELIA_SESSION_SECRET_FILE: /run/secrets/session_secret
      AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE: /run/secrets/storage_encryption_key
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_HMAC_SECRET_FILE: /run/secrets/oidc_hmac_secret
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_ISSUER_PRIVATE_KEY_FILE: /run/secrets/oidc_jwks_key.pem
    command:
      - --config=/config/configuration.yml
    healthcheck:
      test: ["CMD", "wget", "-q", "-O-", "http://127.0.0.1:9091/api/health"]
      interval: 1s
      timeout: 2s
      retries: 30

volumes:
  authelia_data:
```

- [ ] **Step 4: Create `services/authelia/tests/e2e/conftest.py`**

```python
"""Session-scoped fixture: bring Authelia up via docker compose, tear it down."""

from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent
COMPOSE_FILE = HERE / "compose.yaml"


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=check,
        cwd=str(HERE),
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def authelia_url() -> str:
    _compose("up", "-d", "--wait")
    try:
        yield "http://127.0.0.1:9091"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(authelia_url: str) -> httpx.Client:
    with httpx.Client(base_url=authelia_url, timeout=10.0) as client:
        yield client
```

- [ ] **Step 5: Write the failing `test_firstfactor.py`**

```python
"""POST /api/firstfactor returns 200 + Set-Cookie for valid credentials,
401 for invalid."""

from __future__ import annotations

import httpx


def test_firstfactor_valid_credentials_returns_200_with_cookie(http: httpx.Client) -> None:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "https://test.local/flash",
            "requestMethod": "GET",
            "keepMeLoggedIn": True,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200, r.text
    set_cookie = r.headers.get("set-cookie", "")
    assert "authelia_session=" in set_cookie


def test_firstfactor_invalid_credentials_returns_401(http: httpx.Client) -> None:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": "alice",
            "password": "wrong",
            "targetURL": "https://test.local/flash",
            "requestMethod": "GET",
            "keepMeLoggedIn": False,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401
```

- [ ] **Step 6: Verify the test fails**

Run: `cd services/authelia && uv run pytest tests/e2e/test_firstfactor.py -v`
Expected: FAIL — image / fixtures may not be wired yet, or hash placeholders not filled in. Fix any plumbing until the test passes against the fixture container.

- [ ] **Step 7: Write `test_forward_auth.py`**

```python
"""/api/verify enforces session presence and group rules."""

from __future__ import annotations

import httpx


def _login(http: httpx.Client, username: str, password: str) -> str:
    r = http.post(
        "/api/firstfactor",
        json={
            "username": username,
            "password": password,
            "targetURL": "https://test.local/",
            "requestMethod": "GET",
            "keepMeLoggedIn": True,
        },
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/",
            "X-Forwarded-Method": "GET",
        },
    )
    r.raise_for_status()
    return r.headers["set-cookie"].split(";", 1)[0]


def test_verify_without_cookie_returns_401(http: httpx.Client) -> None:
    r = http.get(
        "/api/verify",
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401


def test_verify_with_admin_session_returns_200_and_remote_headers(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("remote-user") == "alice"
    assert "admins" in r.headers.get("remote-groups", "")
```

- [ ] **Step 8: Write `test_oidc_discovery.py`**

```python
"""OIDC well-known endpoint advertises the expected shape."""

from __future__ import annotations

import httpx


def test_openid_configuration_returns_expected_endpoints(http: httpx.Client) -> None:
    r = http.get("/.well-known/openid-configuration")
    assert r.status_code == 200
    doc = r.json()
    for key in ("issuer", "authorization_endpoint", "token_endpoint",
                "userinfo_endpoint", "jwks_uri"):
        assert key in doc, f"missing {key}: {doc}"
    assert doc["issuer"].endswith(":9091")  # local fixture issuer


def test_jwks_endpoint_returns_keys(http: httpx.Client) -> None:
    r = http.get("/jwks.json")
    assert r.status_code == 200
    assert "keys" in r.json()
```

- [ ] **Step 9: Write `test_group_gating.py`**

```python
"""researcher cannot pass admins-only verify; admin can pass both."""

from __future__ import annotations

import httpx

from .test_forward_auth import _login


def test_researcher_denied_on_flash(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/flash",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 403


def test_researcher_allowed_on_jupyter(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/jupyter/lab",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
```

- [ ] **Step 10: Run the full suite**

```bash
cd services/authelia && uv run pytest tests/e2e/ -v
```

Expected: 8 tests pass.

- [ ] **Step 11: Commit**

```bash
git add services/authelia/pyproject.toml services/authelia/tests/
git commit -m "test(authelia): e2e suite for firstfactor, verify, OIDC, group gating"
```

---

## Task 4: pr-authelia.yml workflow + branch-protection stub

**Files:**
- Create: `.github/workflows/pr-authelia.yml`

- [ ] **Step 1: Create the workflow**

Copy `.github/workflows/pr-flasher.yml` as a starting point, then edit so that:
- The workflow's name is `pr-authelia` and the final aggregator job is named `authelia`. The required-check name will be `pr-authelia / authelia`.
- The `dorny/paths-filter@v3` step gates on `services/authelia/**`, `compose/Caddyfile.tmpl`, and `compose/docker-compose.yml.tmpl`.
- The build step builds and pushes
  `ghcr.io/bioexperiment-lab-devices/lab-bridge-authelia:${{ github.sha }}`
  for PR runs and the release tag on release-please tag pushes.
- The e2e step runs `cd services/authelia && uv run pytest tests/e2e/` with
  `AUTHELIA_TEST_IMAGE` exported to the PR-tagged image.

Mirror the Sigstore attestation step from `pr-flasher.yml`.

- [ ] **Step 2: Add the required check to branch protection (manual)**

Use the `verify`-stub transitional pattern from `CLAUDE.md` if necessary:
1. Add `pr-authelia / authelia` to the protected-branch required-checks list **after** the workflow is merged to `main`.
2. If you need a no-op transition, add a `pr-authelia-verify` stub job that always passes, gate it as required, then promote the real check.

Document the action taken in the PR description.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pr-authelia.yml
git commit -m "ci(authelia): per-service workflow with build, e2e, and attestation"
```

---

## Task 5: Render-layer extensions

**Files:**
- Modify: `scripts/lib/render.sh`
- Modify: `tests/integration/test_render.bats`

- [ ] **Step 1: Write a failing bats test**

Add to `tests/integration/test_render.bats`:

```bash
@test "render_authelia_config substitutes __VPS_HOST__ and __GRAFANA_OIDC_SECRET_HASH__" {
    export VPS_HOST="vps.example"
    export AUTHELIA_GRAFANA_OIDC_SECRET_HASH='$pbkdf2-sha512$test$hash'

    local tmpl="$BATS_TEST_TMPDIR/configuration.yml.tmpl"
    local out="$BATS_TEST_TMPDIR/configuration.yml"
    cat > "$tmpl" <<'EOF'
session:
  domain: __VPS_HOST__
identity_providers:
  oidc:
    clients:
      - id: grafana
        secret: '__GRAFANA_OIDC_SECRET_HASH__'
EOF

    source "$REPO_ROOT/scripts/lib/common.sh"
    source "$REPO_ROOT/scripts/lib/render.sh"
    render_authelia_config "$tmpl" "$out"

    grep -q "domain: vps.example" "$out"
    grep -q 'secret: ..pbkdf2-sha512.test.hash.' "$out"
}

@test "render_compose substitutes __AUTHELIA_IMAGE__" {
    source "$REPO_ROOT/scripts/lib/common.sh"
    source "$REPO_ROOT/scripts/lib/config.sh"
    source "$REPO_ROOT/scripts/lib/render.sh"

    # Minimal config to load.
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'EOF'
vps: { host: vps.example, ssh_user: root }
jupyter: { password_hash: "x" }
siteapp: { admin_password_hash: "y" }
chisel_clients: []
EOF
    LDS_VERSION_FILE="$BATS_TEST_TMPDIR/VERSION"
    echo "9.9.9" > "$LDS_VERSION_FILE"
    export LDS_VERSION_FILE
    export AUTHELIA_IMAGE_REPO="ghcr.io/test/authelia"

    CONFIG_PATH="$BATS_TEST_TMPDIR/config.yaml" load_config

    local tmpl="$BATS_TEST_TMPDIR/compose.yml.tmpl"
    local out="$BATS_TEST_TMPDIR/compose.yml"
    echo "image: __AUTHELIA_IMAGE__" > "$tmpl"
    render_compose "$tmpl" "$out"

    grep -q "image: ghcr.io/test/authelia:9.9.9" "$out"
}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
bats tests/integration/test_render.bats -f "authelia"
```

Expected: FAIL (`render_authelia_config: command not found`, or `__AUTHELIA_IMAGE__` not substituted).

- [ ] **Step 3: Extend `scripts/lib/render.sh`**

Add `_authelia_image` helper next to `_caddy_image`:

```bash
# _authelia_image — print ghcr.io/<owner>/lab-bridge-authelia:<version>
_authelia_image() {
    local repo="${AUTHELIA_IMAGE_REPO:?AUTHELIA_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}
```

Extend `render_compose` with one additional sed expression and one local var:

```bash
    local siteapp_image flasher_image caddy_image authelia_image
    siteapp_image="$(_siteapp_image)"
    flasher_image="$(_flasher_image)"
    caddy_image="$(_caddy_image)"
    authelia_image="$(_authelia_image)"
```

And inside the `sed -e ...` chain (next to the other `__*_IMAGE__` lines):

```bash
        -e "s|__AUTHELIA_IMAGE__|${authelia_image}|g" \
```

Remove the `__ADMIN_BCRYPT_HASH__` substitution from `render_caddyfile` (the
new Caddyfile no longer references it):

```bash
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local platform_version
    platform_version="$(_unified_version)"
    sed \
        -e "s|__ACME_EMAIL__|${CADDY_ACME_EMAIL:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__PLATFORM_VERSION__|${platform_version}|g" \
        "$tmpl" > "$out"
}
```

Add the new `render_authelia_config` function next to `render_loki_config`:

```bash
# render_authelia_config <template_path> <output_path>
# Substitutes __VPS_HOST__ and __GRAFANA_OIDC_SECRET_HASH__. The grafana
# OIDC secret hash is PBKDF2-derived from a raw secret in the laptop's
# config.yaml (.authelia.grafana_oidc_secret_hash), set by
# `task secrets:bootstrap-authelia`.
render_authelia_config() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__GRAFANA_OIDC_SECRET_HASH__|${AUTHELIA_GRAFANA_OIDC_SECRET_HASH:?}|g" \
        "$tmpl" > "$out"
}
```

- [ ] **Step 4: Wire `AUTHELIA_IMAGE_REPO` + `AUTHELIA_GRAFANA_OIDC_SECRET_HASH` through `scripts/lib/config.sh`**

In `scripts/lib/config.sh`:

1. Add `.authelia_image` and `.authelia_image_repo` to `_REQUIRED_PINS_FIELDS`
   (next to `.siteapp_image_repo` / `.flasher_image_repo` / `.caddy_image_repo`).

2. In `load_config()`, add the pins exports next to the existing
   `SITEAPP_IMAGE_REPO` / `FLASHER_IMAGE_REPO` lines:

   ```bash
   export AUTHELIA_IMAGE_REPO    ; AUTHELIA_IMAGE_REPO="$(_yq e '.authelia_image_repo' "$pins_path")"
   export AUTHELIA_IMAGE         ; AUTHELIA_IMAGE="$(_yq e '.authelia_image' "$pins_path")"
   ```

3. Also in `load_config()`, add (after the existing `JUPYTER_PASSWORD_HASH` /
   `SITEAPP_ADMIN_PASSWORD_HASH` lines):

   ```bash
   export AUTHELIA_GRAFANA_OIDC_SECRET_HASH ; AUTHELIA_GRAFANA_OIDC_SECRET_HASH="$(_yq e '.authelia.grafana_oidc_secret_hash // ""' "$config_path")"
   ```

Do **not** add `.authelia.grafana_oidc_secret_hash` to `_REQUIRED_CONFIG_FIELDS`
— it's bootstrapped lazily by `task secrets:bootstrap-authelia`, and a missing
hash should only fail at render time (via the `${VAR:?}` expansion in
`render_authelia_config`), not at general `load_config` time.

- [ ] **Step 5: Re-run the bats test**

```bash
bats tests/integration/test_render.bats -f "authelia"
```

Expected: PASS.

- [ ] **Step 6: Run the full render suite to catch regressions**

```bash
bats tests/integration/test_render.bats
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/lib/render.sh scripts/lib/config.sh tests/integration/test_render.bats
git commit -m "feat(render): authelia image + config rendering, drop admin bcrypt"
```

---

## Task 6: `task secrets:bootstrap-authelia`

**Files:**
- Modify: `scripts/secrets.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/integration/test_secrets.bats`

- [ ] **Step 1: Write a failing bats test**

Add to `tests/integration/test_secrets.bats` (mirrors the existing
`setup_tmpdir` / `LDS_CONFIG` / `$ROOT` style at the top of the file):

```bash
@test "secrets:bootstrap-authelia generates five secrets + grafana oidc secret and hash" {
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_AUTHELIA_SECRETS_DIR="$TMPDIR/authelia_secrets"
    export LDS_GRAFANA_OIDC_SECRET_FILE="$TMPDIR/grafana_oidc_secret"
    # Test hook: skip the docker-run PBKDF2 derivation and emit a fake hash.
    # The real bootstrap path is exercised by the auth bats smoke matrix cell
    # against the actual Authelia image (see test_auth_smoke.bats).
    export LDS_PBKDF2_HASH_CMD='printf "$pbkdf2-sha512$fake$%s" "$1"'

    run bash "$ROOT/scripts/secrets.sh" bootstrap-authelia
    [ "$status" -eq 0 ]
    [ -s "$LDS_AUTHELIA_SECRETS_DIR/jwt_secret" ]
    [ -s "$LDS_AUTHELIA_SECRETS_DIR/session_secret" ]
    [ -s "$LDS_AUTHELIA_SECRETS_DIR/storage_encryption_key" ]
    [ -s "$LDS_AUTHELIA_SECRETS_DIR/oidc_hmac_secret" ]
    [ -s "$LDS_AUTHELIA_SECRETS_DIR/oidc_jwks_key.pem" ]
    [ -s "$LDS_GRAFANA_OIDC_SECRET_FILE" ]
    hash="$(yq e '.authelia.grafana_oidc_secret_hash' "$LDS_CONFIG")"
    [[ "$hash" =~ ^\$pbkdf2-sha512\$ ]]
}

@test "secrets:bootstrap-authelia refuses to overwrite without --rotate" {
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_AUTHELIA_SECRETS_DIR="$TMPDIR/authelia_secrets"
    export LDS_GRAFANA_OIDC_SECRET_FILE="$TMPDIR/grafana_oidc_secret"
    export LDS_PBKDF2_HASH_CMD='printf "$pbkdf2-sha512$fake$%s" "$1"'

    bash "$ROOT/scripts/secrets.sh" bootstrap-authelia
    run bash "$ROOT/scripts/secrets.sh" bootstrap-authelia
    [ "$status" -ne 0 ]
    [[ "$output" == *"already exist"* ]] || [[ "$output" == *"--rotate"* ]]
}
```

Extend `cmd_bootstrap_authelia` in Step 3 below to honour
`LDS_PBKDF2_HASH_CMD` as a test hook (mirrors `LDS_USERS_HASH_CMD` from
Task 7). If the env var is set, the function uses it via
`bash -c "$LDS_PBKDF2_HASH_CMD" _ "$raw"` instead of `docker run …`.

- [ ] **Step 2: Verify the test fails**

```bash
bats tests/integration/test_secrets.bats -f "bootstrap-authelia"
```

Expected: FAIL — unknown subcommand `bootstrap-authelia`.

- [ ] **Step 3: Add `cmd_bootstrap_authelia` to `scripts/secrets.sh`**

Append near the other `cmd_*` functions:

```bash
cmd_bootstrap_authelia() {
    require_cmd openssl
    require_cmd docker
    require_cmd yq

    local rotate=0
    [[ "${1:-}" == "--rotate" ]] && rotate=1

    ensure_config

    local secrets_dir="${LDS_AUTHELIA_SECRETS_DIR:-$SCRIPT_DIR/../compose/authelia/secrets}"
    local grafana_oidc_secret_file="${LDS_GRAFANA_OIDC_SECRET_FILE:-$SCRIPT_DIR/../compose/grafana/oidc_secret}"
    mkdir -p "$secrets_dir"
    mkdir -p "$(dirname "$grafana_oidc_secret_file")"

    local existing=0
    for f in jwt_secret session_secret storage_encryption_key oidc_hmac_secret \
             oidc_jwks_key.pem; do
        [[ -f "$secrets_dir/$f" ]] && existing=1
    done
    [[ -f "$grafana_oidc_secret_file" ]] && existing=1

    if (( existing && !rotate )); then
        die "authelia secrets already exist in $secrets_dir; pass --rotate to overwrite"
    fi

    # Four 64-byte hex tokens.
    for f in jwt_secret session_secret storage_encryption_key oidc_hmac_secret; do
        openssl rand -hex 64 > "$secrets_dir/$f"
        chmod 600 "$secrets_dir/$f"
    done

    # RSA 4096 for OIDC JWKS.
    openssl genrsa -out "$secrets_dir/oidc_jwks_key.pem" 4096 2>/dev/null
    chmod 600 "$secrets_dir/oidc_jwks_key.pem"

    # Raw Grafana OIDC client secret + its PBKDF2 hash. The image pin comes
    # from compose/pins.yaml via $AUTHELIA_IMAGE, which is exported by config.sh.
    local raw hash
    raw="$(openssl rand -base64 32 | tr -d '+/=' | head -c 48)"
    printf '%s' "$raw" > "$grafana_oidc_secret_file"
    chmod 600 "$grafana_oidc_secret_file"

    # Compute PBKDF2 hash for the Grafana OIDC client.
    if [[ -n "${LDS_PBKDF2_HASH_CMD:-}" ]]; then
        # Test hook: a printf-format-style command that produces a fake hash.
        hash="$(bash -c "$LDS_PBKDF2_HASH_CMD" _ "$raw")"
    else
        # `authelia crypto hash generate pbkdf2 --password <p>` prints
        # "Password hash: $pbkdf2-sha512$...". Strip the prefix.
        hash="$(docker run --rm "$AUTHELIA_IMAGE" \
            authelia crypto hash generate pbkdf2 --variant sha512 \
            --password "$raw" 2>/dev/null \
            | awk -F': ' '/Password hash:/ {print $2; exit}')"
    fi
    [[ -n "$hash" ]] || die "failed to derive PBKDF2 hash for grafana OIDC secret"

    yq -i ".authelia.grafana_oidc_secret_hash = \"$hash\"" "$CONFIG"
    log "wrote authelia secrets to $secrets_dir"
    log "wrote grafana OIDC secret to $grafana_oidc_secret_file"
    log "wrote PBKDF2 hash to config.yaml under authelia.grafana_oidc_secret_hash"
    log "(deploy to apply)"
}
```

Wire the subcommand in `main()`:

```bash
    case "$sub" in
        # ... existing cases ...
        bootstrap-authelia) cmd_bootstrap_authelia "$@" ;;
        # ... rest unchanged ...
    esac
```

- [ ] **Step 4: Add the task to `Taskfile.yml`**

Insert under the `# --- Secrets ---` section, near the other `secrets:*`
entries:

```yaml
  "secrets:bootstrap-authelia":
    desc: Generate Authelia secrets (JWT, session, storage encryption, OIDC HMAC, RSA JWKS key) and the Grafana OIDC client secret + its PBKDF2 hash. Pass --rotate to overwrite.
    cmd: bash scripts/secrets.sh bootstrap-authelia {{.CLI_ARGS}}
```

`config.sh` must export `AUTHELIA_IMAGE` (from Task 5 step 4) so the
bootstrap can call `docker run "$AUTHELIA_IMAGE" authelia crypto …`.

- [ ] **Step 5: Run the bats tests**

```bash
bats tests/integration/test_secrets.bats -f "bootstrap-authelia"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/integration/test_secrets.bats
git commit -m "feat(secrets): task secrets:bootstrap-authelia"
```

---

## Task 7: `task users:*` + user management script

**Files:**
- Create: `scripts/users.sh`
- Modify: `Taskfile.yml`
- Create: `tests/integration/test_users.bats`

- [ ] **Step 1: Write a failing bats test**

Create `tests/integration/test_users.bats`:

```bash
#!/usr/bin/env bats

load helpers.bash

setup() {
    REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
    cd "$BATS_TEST_TMPDIR"
    mkdir -p compose/authelia
    cp -r "$REPO_ROOT"/scripts ./scripts
    # Stub AUTHELIA_IMAGE so the script doesn't try to pull a real image.
    # The argon2id hashing path is mocked via LDS_USERS_HASH_CMD below.
    export LDS_USERS_DB="$BATS_TEST_TMPDIR/compose/authelia/users_database.yml"
    export LDS_USERS_HASH_CMD="printf 'argon2id\$test\$%s' \"\$1\""
}

@test "users:add creates the file and adds a user with given group" {
    PASSWORD=secret bash ./scripts/users.sh add alice admins
    yq e '.users.alice.groups[0]' "$LDS_USERS_DB" | grep -q admins
    yq e '.users.alice.password' "$LDS_USERS_DB" | grep -q 'argon2id'
}

@test "users:add refuses unknown group" {
    PASSWORD=secret run bash ./scripts/users.sh add alice marketing
    [ "$status" -ne 0 ]
    [[ "$output" =~ unknown.group ]]
}

@test "users:rm removes the user" {
    PASSWORD=secret bash ./scripts/users.sh add alice admins
    bash ./scripts/users.sh rm alice
    run yq e '.users.alice' "$LDS_USERS_DB"
    [[ "$output" == "null" ]]
}

@test "users:set-password updates the hash" {
    PASSWORD=old bash ./scripts/users.sh add alice admins
    local old_hash; old_hash="$(yq e '.users.alice.password' "$LDS_USERS_DB")"
    PASSWORD=new bash ./scripts/users.sh set-password alice
    local new_hash; new_hash="$(yq e '.users.alice.password' "$LDS_USERS_DB")"
    [ "$old_hash" != "$new_hash" ]
}

@test "users:set-groups replaces the group list" {
    PASSWORD=secret bash ./scripts/users.sh add alice researchers
    bash ./scripts/users.sh set-groups alice admins,researchers
    yq e '.users.alice.groups | length' "$LDS_USERS_DB" | grep -q 2
}

@test "users:list prints a header and each user row" {
    PASSWORD=secret bash ./scripts/users.sh add alice admins
    PASSWORD=secret bash ./scripts/users.sh add bob researchers
    run bash ./scripts/users.sh list
    [[ "$output" =~ alice ]]
    [[ "$output" =~ bob ]]
    [[ "$output" =~ admins ]]
    [[ "$output" =~ researchers ]]
}
```

- [ ] **Step 2: Verify the test fails**

```bash
bats tests/integration/test_users.bats
```

Expected: FAIL — `scripts/users.sh` does not exist.

- [ ] **Step 3: Create `scripts/users.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

VALID_GROUPS=(admins researchers)
DEFAULT_DB="$SCRIPT_DIR/../compose/authelia/users_database.yml"
USERS_DB="${LDS_USERS_DB:-$DEFAULT_DB}"

ensure_db() {
    mkdir -p "$(dirname "$USERS_DB")"
    if [[ ! -f "$USERS_DB" ]]; then
        echo "users: {}" > "$USERS_DB"
        chmod 600 "$USERS_DB"
    fi
}

validate_groups() {
    local IFS=','
    local g
    for g in $1; do
        local ok=0
        local v
        for v in "${VALID_GROUPS[@]}"; do
            [[ "$g" == "$v" ]] && ok=1
        done
        (( ok )) || die "unknown group: $g (allowed: ${VALID_GROUPS[*]})"
    done
}

hash_password() {
    local plain="$1"
    if [[ -n "${LDS_USERS_HASH_CMD:-}" ]]; then
        # Test hook: a printf-format-style command that produces a fake hash.
        bash -c "$LDS_USERS_HASH_CMD" _ "$plain"
        return
    fi
    require_cmd docker
    # Use the same Authelia image pin as the running container.
    local image="${AUTHELIA_IMAGE:-authelia/authelia:4.38.10}"
    docker run --rm "$image" authelia hash-password --no-confirm "$plain" \
        | awk -F': ' '/Password hash:/ {print $2; exit}'
}

prompt_or_env() {
    local label="$1" varname="$2" value
    if [[ -n "${!varname:-}" ]]; then
        printf '%s' "${!varname}"
        return
    fi
    read -rsp "$label: " value
    echo >&2
    printf '%s' "$value"
}

groups_yaml() {
    local IFS=','
    local g
    local first=1
    printf '['
    for g in $1; do
        (( first )) || printf ','
        printf '%s' "$g"
        first=0
    done
    printf ']'
}

cmd_add() {
    local user="${1:?usage: users.sh add <user> <group[,group]>}"
    local groups="${2:?usage: users.sh add <user> <group[,group]>}"
    ensure_db
    validate_groups "$groups"

    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -z "$existing" ]] || die "user $user already exists"

    local pw hash
    pw="$(prompt_or_env "password for $user" PASSWORD)"
    [[ -n "$pw" ]] || die "empty password"
    hash="$(hash_password "$pw")"

    yq -i "
        .users.$user.displayname = \"$user\"
        | .users.$user.password = \"$hash\"
        | .users.$user.email = \"$user@lab.local\"
        | .users.$user.groups = $(groups_yaml "$groups")
    " "$USERS_DB"
    log "added user $user with groups $groups"
}

cmd_rm() {
    local user="${1:?usage: users.sh rm <user>}"
    ensure_db
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"
    yq -i "del(.users.$user)" "$USERS_DB"
    log "removed user $user"
}

cmd_set_password() {
    local user="${1:?usage: users.sh set-password <user>}"
    ensure_db
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"

    local pw hash
    pw="$(prompt_or_env "new password for $user" PASSWORD)"
    [[ -n "$pw" ]] || die "empty password"
    hash="$(hash_password "$pw")"
    yq -i ".users.$user.password = \"$hash\"" "$USERS_DB"
    log "updated password for $user"
}

cmd_set_groups() {
    local user="${1:?usage: users.sh set-groups <user> <group[,group]>}"
    local groups="${2:?usage: users.sh set-groups <user> <group[,group]>}"
    ensure_db
    validate_groups "$groups"
    local existing
    existing="$(yq e ".users.$user // \"\"" "$USERS_DB")"
    [[ -n "$existing" ]] || die "user $user not found"
    yq -i ".users.$user.groups = $(groups_yaml "$groups")" "$USERS_DB"
    log "set groups for $user to $groups"
}

cmd_list() {
    ensure_db
    printf '%-20s %s\n' "USER" "GROUPS"
    yq e '.users | to_entries[] | .key + " " + (.value.groups | join(","))' \
        "$USERS_DB" \
        | while read -r user groups; do
            printf '%-20s %s\n' "$user" "${groups:-—}"
        done
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        add)            cmd_add "$@" ;;
        rm)             cmd_rm "$@" ;;
        set-password)   cmd_set_password "$@" ;;
        set-groups)     cmd_set_groups "$@" ;;
        list)           cmd_list "$@" ;;
        *) die "unknown subcommand: $sub (allowed: add, rm, set-password, set-groups, list)" ;;
    esac
}

main "$@"
```

- [ ] **Step 4: Add tasks to `Taskfile.yml`**

Insert a new section after `# --- Secrets ---`:

```yaml
  # --- Users (Authelia identities) ---
  "users:add":
    desc: Add a user (prompts for password). Usage: task users:add -- USER GROUP[,GROUP]
    cmd: bash scripts/users.sh add {{.CLI_ARGS}}
  "users:rm":
    desc: Remove a user. Usage: task users:rm -- USER
    cmd: bash scripts/users.sh rm {{.CLI_ARGS}}
  "users:set-password":
    desc: Set a new password for a user (prompts). Usage: task users:set-password -- USER
    cmd: bash scripts/users.sh set-password {{.CLI_ARGS}}
  "users:set-groups":
    desc: Set the group list for a user. Usage: task users:set-groups -- USER GROUP[,GROUP]
    cmd: bash scripts/users.sh set-groups {{.CLI_ARGS}}
  "users:list":
    desc: Print all users with their groups
    cmd: bash scripts/users.sh list
```

- [ ] **Step 5: Run the bats tests**

```bash
bats tests/integration/test_users.bats
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
chmod +x scripts/users.sh
git add scripts/users.sh Taskfile.yml tests/integration/test_users.bats
git commit -m "feat(users): task users:* and user management script"
```

---

## Task 8: docker-compose template changes

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`

- [ ] **Step 1: Add the Authelia service block**

Insert before the `chisel:` block in `compose/docker-compose.yml.tmpl`:

```yaml
  authelia:
    image: __AUTHELIA_IMAGE__
    restart: unless-stopped
    command: ["--config=/config/configuration.yml"]
    volumes:
      - ./authelia/configuration.yml:/config/configuration.yml:ro
      - ./authelia/users_database.yml:/config/users_database.yml:ro
      - ./authelia_data:/data
    secrets:
      - authelia_jwt_secret
      - authelia_session_secret
      - authelia_storage_encryption_key
      - authelia_oidc_hmac_secret
      - authelia_oidc_jwks_key
    environment:
      AUTHELIA_JWT_SECRET_FILE: /run/secrets/authelia_jwt_secret
      AUTHELIA_SESSION_SECRET_FILE: /run/secrets/authelia_session_secret
      AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE: /run/secrets/authelia_storage_encryption_key
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_HMAC_SECRET_FILE: /run/secrets/authelia_oidc_hmac_secret
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_ISSUER_PRIVATE_KEY_FILE: /run/secrets/authelia_oidc_jwks_key
    networks: [labnet]
```

Add `authelia` to `caddy.depends_on`:

```yaml
  caddy:
    # ... existing ...
    depends_on: [jupyter, siteapp, flasher, grafana, authelia]
```

- [ ] **Step 2: Strip the Jupyter shared-password lines**

Edit the `jupyter.command` block — remove the `--ServerApp.token=…` line if
populated and the `--ServerApp.password=__JUPYTER_PASSWORD_HASH__` line.
Replace with empty values to disable both:

```yaml
  jupyter:
    image: __JUPYTER_IMAGE__
    restart: unless-stopped
    command:
      - start-notebook.sh
      - --ServerApp.token=
      - --ServerApp.password=
      - --ServerApp.allow_origin=*
      - --ServerApp.base_url=/jupyter
      - --ServerApp.root_dir=/home/jovyan/work
      - --ServerApp.disable_check_xsrf=true
    volumes:
      - __NOTEBOOKS_PATH__:/home/jovyan/work
    networks: [labnet]
```

- [ ] **Step 3: Add OIDC env vars to Grafana**

Edit the `grafana.environment` block (keep existing keys, add the OIDC ones):

```yaml
  grafana:
    image: __GRAFANA_IMAGE__
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password
      GF_SERVER_ROOT_URL: https://__VPS_HOST__/grafana/
      GF_SERVER_SERVE_FROM_SUB_PATH: "true"
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
      GF_AUTH_GENERIC_OAUTH_ENABLED: "true"
      GF_AUTH_GENERIC_OAUTH_NAME: Authelia
      GF_AUTH_GENERIC_OAUTH_CLIENT_ID: grafana
      GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET__FILE: /run/secrets/grafana_oidc_secret
      GF_AUTH_GENERIC_OAUTH_SCOPES: "openid profile email groups"
      GF_AUTH_GENERIC_OAUTH_AUTH_URL: https://__VPS_HOST__/auth/api/oidc/authorization
      GF_AUTH_GENERIC_OAUTH_TOKEN_URL: https://__VPS_HOST__/auth/api/oidc/token
      GF_AUTH_GENERIC_OAUTH_API_URL: https://__VPS_HOST__/auth/api/oidc/userinfo
      GF_AUTH_GENERIC_OAUTH_USE_PKCE: "true"
      GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH: "contains(groups[*], 'admins') && 'Admin' || contains(groups[*], 'researchers') && 'Viewer'"
      GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN: "true"
      GF_AUTH_DISABLE_LOGIN_FORM: "true"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana_data:/var/lib/grafana
    secrets:
      - grafana_admin_password
      - grafana_oidc_secret
    networks: [labnet]
    depends_on: [loki, prometheus]
```

- [ ] **Step 4: Add the new secret entries at the bottom of the file**

```yaml
secrets:
  grafana_admin_password:
    file: ./grafana/admin_password
  agent_upload_token:
    file: ./siteapp/agent_upload_token
  flasher_upload_token:
    file: ./flasher/upload_token
  authelia_jwt_secret:
    file: ./authelia/secrets/jwt_secret
  authelia_session_secret:
    file: ./authelia/secrets/session_secret
  authelia_storage_encryption_key:
    file: ./authelia/secrets/storage_encryption_key
  authelia_oidc_hmac_secret:
    file: ./authelia/secrets/oidc_hmac_secret
  authelia_oidc_jwks_key:
    file: ./authelia/secrets/oidc_jwks_key.pem
  grafana_oidc_secret:
    file: ./grafana/oidc_secret
```

- [ ] **Step 5: Commit**

```bash
git add compose/docker-compose.yml.tmpl
git commit -m "feat(compose): wire Authelia, OIDC for Grafana, edge auth for Jupyter"
```

---

## Task 9: siteapp `auth.py` module — `/login` + `whoami` + `firstfactor` + `logout` + error routes

**Files:**
- Create: `services/siteapp/app/auth.py`
- Modify: `services/siteapp/app/main.py`
- Modify: `services/siteapp/app/config.py`
- Modify: `services/siteapp/pyproject.toml`

- [ ] **Step 1: Ensure `httpx` is a runtime dep**

Read `services/siteapp/pyproject.toml`. If `httpx` is missing from the
`dependencies` list, add it:

```toml
dependencies = [
  # ... existing ...
  "httpx>=0.27",
]
```

If it's already there, skip this step.

Run `cd services/siteapp && uv lock` to refresh `uv.lock`.

- [ ] **Step 2: Add Authelia URL to settings**

Edit `services/siteapp/app/config.py`:

In the `Settings` dataclass, add (next to `chisel_listen_port`):

```python
    authelia_url: str = "http://authelia:9091"
```

In `load_settings()`, add (next to the other env reads):

```python
    authelia_url = os.environ.get("SITEAPP_AUTHELIA_URL", "http://authelia:9091").strip()
```

And include it in the `Settings(...)` constructor call.

- [ ] **Step 3: Create `services/siteapp/app/auth.py`**

```python
"""Auth-related routes for siteapp.

Hosts /login, /logout, /api/auth/firstfactor, /api/auth/whoami, and the
shared /_errors/{403,404} pages. All HTML routes extend base.html so the
global navbar (Caddy replace-response injection) shows up.

The firstfactor handler proxies to Authelia server-to-server. Authelia
treats the inbound headers (Host, X-Forwarded-*) as the source of truth for
the access-control resource match, so we forward them faithfully.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Cookie, Header, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.templates import templates


def _forwarded_headers(request: Request, target_uri: str) -> dict[str, str]:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return {
        "X-Forwarded-Host": host,
        "X-Forwarded-Proto": proto,
        "X-Forwarded-Uri": target_uri,
        "X-Forwarded-Method": "GET",
    }


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    base = settings.authelia_url.rstrip("/")
    client = httpx.AsyncClient(base_url=base, timeout=5.0)

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(request: Request, rd: str = "/") -> HTMLResponse:
        return templates.TemplateResponse(request, "login.html", {"rd": rd})

    @router.post("/api/auth/firstfactor")
    async def firstfactor(request: Request) -> Response:
        payload: dict[str, Any] = await request.json()
        target = payload.get("targetURL") or "/"
        body = {
            "username": payload.get("username", ""),
            "password": payload.get("password", ""),
            "targetURL": target,
            "requestMethod": "GET",
            "keepMeLoggedIn": bool(payload.get("keepMeLoggedIn", True)),
        }
        headers = _forwarded_headers(request, target)
        try:
            r = await client.post("/api/firstfactor", json=body, headers=headers)
        except httpx.RequestError as exc:
            return JSONResponse(
                {"error": f"authelia unreachable: {exc.__class__.__name__}"},
                status_code=502,
            )
        resp = JSONResponse(
            {"redirect": target} if r.status_code == 200 else r.json(),
            status_code=r.status_code,
        )
        # Pipe Set-Cookie through (FastAPI strips it from the constructor).
        for key, value in r.headers.multi_items():
            if key.lower() == "set-cookie":
                resp.raw_headers.append((b"set-cookie", value.encode("latin-1")))
        return resp

    @router.get("/api/auth/whoami")
    async def whoami(
        request: Request,
        authelia_session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        if not authelia_session:
            return JSONResponse({"user": None})
        try:
            r = await client.get(
                "/api/verify",
                headers={
                    "Cookie": f"authelia_session={authelia_session}",
                    **_forwarded_headers(request, "/"),
                },
            )
        except httpx.RequestError:
            return JSONResponse({"user": None})
        if r.status_code != 200:
            return JSONResponse({"user": None})
        user = r.headers.get("remote-user")
        groups_header = r.headers.get("remote-groups", "")
        groups = [g.strip() for g in groups_header.split(",") if g.strip()]
        return JSONResponse(
            {
                "user": user,
                "groups": groups,
                "display_name": r.headers.get("remote-name"),
                "email": r.headers.get("remote-email"),
            }
        )

    @router.get("/logout")
    async def logout(request: Request) -> Response:
        cookie = request.headers.get("cookie", "")
        try:
            r = await client.get("/api/logout", headers={"Cookie": cookie})
        except httpx.RequestError:
            r = None
        resp = RedirectResponse("/", status_code=302)
        if r is not None:
            for key, value in r.headers.multi_items():
                if key.lower() == "set-cookie":
                    resp.raw_headers.append((b"set-cookie", value.encode("latin-1")))
        return resp

    @router.get("/_errors/403", response_class=HTMLResponse, include_in_schema=False)
    async def error_403(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "error_403.html", {})

    @router.get("/_errors/404", response_class=HTMLResponse, include_in_schema=False)
    async def error_404(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "error_404.html", {})

    return router
```

- [ ] **Step 4: Register the router in `services/siteapp/app/main.py`**

Add the import at the top with the other route imports:

```python
from app.auth import make_router as make_auth_router
```

Add the include below the existing `app.include_router(...)` calls:

```python
app.include_router(make_auth_router(settings))
```

- [ ] **Step 5: Commit**

```bash
git add services/siteapp/app/auth.py services/siteapp/app/main.py \
        services/siteapp/app/config.py services/siteapp/pyproject.toml \
        services/siteapp/uv.lock
git commit -m "feat(siteapp): /login, /logout, /api/auth/*, /_errors/*"
```

---

## Task 10: siteapp templates

**Files:**
- Create: `services/siteapp/app/templates/login.html`
- Create: `services/siteapp/app/templates/error_403.html`
- Create: `services/siteapp/app/templates/error_404.html`

- [ ] **Step 1: Create `services/siteapp/app/templates/login.html`**

```html
{% extends "base.html" %}
{% block title %}Sign in — lab-bridge{% endblock %}
{% block main %}
  <section class="lb-login">
    <h1>Sign in</h1>
    <form id="login-form">
      <label>
        <span>Username</span>
        <input type="text" name="username" autocomplete="username" autofocus required>
      </label>
      <label>
        <span>Password</span>
        <input type="password" name="password" autocomplete="current-password" required>
      </label>
      <label class="lb-login-remember">
        <input type="checkbox" name="remember" checked>
        Remember me
      </label>
      <button type="submit">Sign in</button>
      <p class="lb-login-error" hidden></p>
    </form>
  </section>

  <script>
    (function () {
      const params = new URLSearchParams(location.search);
      const rd = params.get('rd') || {{ rd|tojson }};
      const form = document.getElementById('login-form');
      const errEl = form.querySelector('.lb-login-error');

      form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        errEl.hidden = true;
        const data = new FormData(form);
        try {
          const r = await fetch('/api/auth/firstfactor', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: data.get('username'),
              password: data.get('password'),
              targetURL: rd,
              keepMeLoggedIn: data.get('remember') === 'on',
            }),
          });
          if (r.status === 200) {
            const body = await r.json();
            location.href = body.redirect || '/';
            return;
          }
          errEl.textContent = r.status === 401
            ? 'Incorrect username or password.'
            : 'Sign-in failed (' + r.status + ').';
          errEl.hidden = false;
        } catch (e) {
          errEl.textContent = 'Network error.';
          errEl.hidden = false;
        }
      });
    })();
  </script>
{% endblock %}
```

- [ ] **Step 2: Create `services/siteapp/app/templates/error_403.html`**

```html
{% extends "base.html" %}
{% block title %}Forbidden — lab-bridge{% endblock %}
{% block main %}
  <section class="lb-error">
    <h1>403 — Forbidden</h1>
    <p>You're signed in, but your account doesn't have permission to view this page.</p>
    <p><a href="/">Go home</a></p>
  </section>
{% endblock %}
```

- [ ] **Step 3: Create `services/siteapp/app/templates/error_404.html`**

```html
{% extends "base.html" %}
{% block title %}Not found — lab-bridge{% endblock %}
{% block main %}
  <section class="lb-error">
    <h1>404 — Not found</h1>
    <p>The page you're looking for doesn't exist on this server.</p>
    <p><a href="/">Go home</a></p>
  </section>
{% endblock %}
```

- [ ] **Step 4: Commit**

```bash
git add services/siteapp/app/templates/login.html \
        services/siteapp/app/templates/error_403.html \
        services/siteapp/app/templates/error_404.html
git commit -m "feat(siteapp): templates for /login and /_errors/*"
```

---

## Task 11: siteapp e2e compose — add Authelia + fixture users

**Files:**
- Create: `services/siteapp/tests/e2e/fixtures/authelia_users.yml`
- Create: `services/siteapp/tests/e2e/fixtures/authelia_config.yml`
- Create: `services/siteapp/tests/e2e/fixtures/authelia_secrets/` (5 files)
- Modify: `services/siteapp/tests/e2e/compose.yaml`

- [ ] **Step 1: Copy the Authelia fixtures from Task 3**

Copy `services/authelia/tests/e2e/fixtures/users_database.yml` to
`services/siteapp/tests/e2e/fixtures/authelia_users.yml`.

Copy `services/authelia/tests/e2e/fixtures/configuration.yml` to
`services/siteapp/tests/e2e/fixtures/authelia_config.yml`. Edit the file:

- Set `default_redirection_url` to `http://siteapp:8000/`.
- Replace every `__VPS_HOST__` placeholder in the access-control rules with
  `siteapp`.
- Replace `session.domain: __VPS_HOST__` with `session.domain: siteapp`
  (or, if the running Authelia version has migrated to the
  `session.cookies` array form, use `name: authelia_session`,
  `domain: siteapp`, `authelia_url: http://authelia:9091`).
- Test-stub the OIDC issuer key path so Authelia boots even without a
  configured Grafana client (or leave the grafana client config in — the
  fixture PBKDF2 hash from Task 3 is valid).

Then in the siteapp e2e tests, override the `Host` header on the httpx
client to `siteapp` so siteapp's `/api/auth/firstfactor` forwards
`X-Forwarded-Host: siteapp` to Authelia, matching `session.domain`:

```python
# in conftest.py, replace the existing http fixture:
@pytest.fixture(scope="session")
def http(siteapp_url: str) -> httpx.Client:
    with httpx.Client(
        base_url=siteapp_url,
        timeout=10.0,
        headers={"Host": "siteapp"},
    ) as client:
        yield client
```

Copy `services/authelia/tests/e2e/fixtures/secrets/` to
`services/siteapp/tests/e2e/fixtures/authelia_secrets/` (5 files).

- [ ] **Step 2: Update `services/siteapp/tests/e2e/compose.yaml`**

Replace the file with:

```yaml
services:
  siteapp:
    image: ${SITEAPP_TEST_IMAGE:-lab-bridge-siteapp:e2e}
    ports:
      - "127.0.0.1:8001:8000"
    environment:
      LAB_BRIDGE_VERSION: "e2e-test"
      LAB_BRIDGE_GIT_SHA: "test"
      SITEAPP_CHISEL_LISTEN_PORT: "7000"
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_DOCS_DIR: /srv/docs
      SITEAPP_AUTHELIA_URL: http://authelia:9091
      SITE_DATA: /data
    volumes:
      - ./fixtures/clients.json:/etc/siteapp/clients.json:ro
      - ./fixtures/agent_upload_token:/run/secrets/agent_upload_token:ro
      - ./fixtures/docs:/srv/docs:ro
      - siteapp_data:/data
    depends_on:
      authelia:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)\""]
      interval: 1s
      timeout: 2s
      retries: 30

  authelia:
    image: ${AUTHELIA_TEST_IMAGE:-authelia/authelia:4.38.10}
    volumes:
      - ./fixtures/authelia_config.yml:/config/configuration.yml:ro
      - ./fixtures/authelia_users.yml:/config/users_database.yml:ro
      - ./fixtures/authelia_secrets/jwt_secret:/run/secrets/jwt_secret:ro
      - ./fixtures/authelia_secrets/session_secret:/run/secrets/session_secret:ro
      - ./fixtures/authelia_secrets/storage_encryption_key:/run/secrets/storage_encryption_key:ro
      - ./fixtures/authelia_secrets/oidc_hmac_secret:/run/secrets/oidc_hmac_secret:ro
      - ./fixtures/authelia_secrets/oidc_jwks_key.pem:/run/secrets/oidc_jwks_key.pem:ro
      - authelia_data:/data
    environment:
      AUTHELIA_JWT_SECRET_FILE: /run/secrets/jwt_secret
      AUTHELIA_SESSION_SECRET_FILE: /run/secrets/session_secret
      AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE: /run/secrets/storage_encryption_key
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_HMAC_SECRET_FILE: /run/secrets/oidc_hmac_secret
      AUTHELIA_IDENTITY_PROVIDERS_OIDC_ISSUER_PRIVATE_KEY_FILE: /run/secrets/oidc_jwks_key.pem
    command: ["--config=/config/configuration.yml"]
    healthcheck:
      test: ["CMD", "wget", "-q", "-O-", "http://127.0.0.1:9091/api/health"]
      interval: 1s
      timeout: 2s
      retries: 30

volumes:
  siteapp_data:
  authelia_data:
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/fixtures/ services/siteapp/tests/e2e/compose.yaml
git commit -m "test(siteapp): e2e compose adds Authelia sidecar"
```

---

## Task 12: siteapp e2e — login page renders, navbar present, rd preserved

**Files:**
- Create: `services/siteapp/tests/e2e/test_login_page.py`

- [ ] **Step 1: Write the failing test**

```python
"""GET /login renders the form and preserves ?rd= in the markup."""

from __future__ import annotations

import httpx


def test_login_page_returns_200_and_has_form(http: httpx.Client) -> None:
    r = http.get("/login", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert '<form id="login-form"' in body
    assert 'name="username"' in body
    assert 'name="password"' in body


def test_login_page_includes_navbar_marker(http: httpx.Client) -> None:
    # The Caddy navbar injection happens at the edge; in the e2e harness siteapp
    # is hit directly so we instead verify that base.html is the host template
    # (presence of the /_static asset references that base.html owns).
    r = http.get("/login")
    body = r.text
    assert "/_static/site.css" in body or "/_static/tokens.css" in body


def test_login_page_carries_rd_into_inline_script(http: httpx.Client) -> None:
    r = http.get("/login?rd=/flash")
    assert "/flash" in r.text
```

- [ ] **Step 2: Build siteapp image + run test**

```bash
cd services/siteapp
docker build -t lab-bridge-siteapp:e2e .
uv run pytest tests/e2e/test_login_page.py -v
```

Expected: PASS (Task 9 + 10 already implemented the route + template).

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_login_page.py
git commit -m "test(siteapp): /login renders form and preserves rd"
```

---

## Task 13: siteapp e2e — `/api/auth/firstfactor` end-to-end

**Files:**
- Create: `services/siteapp/tests/e2e/test_login_flow.py`

- [ ] **Step 1: Write the failing test**

```python
"""POST /api/auth/firstfactor authenticates against Authelia and pipes the
Set-Cookie back."""

from __future__ import annotations

import httpx


def test_valid_login_returns_200_and_sets_authelia_cookie(http: httpx.Client) -> None:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": "alice",
            "password": "alice-password",
            "targetURL": "/flash",
            "keepMeLoggedIn": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["redirect"] == "/flash"
    set_cookies = r.headers.get_list("set-cookie")
    assert any("authelia_session=" in c for c in set_cookies)


def test_invalid_password_returns_401(http: httpx.Client) -> None:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": "alice",
            "password": "wrong",
            "targetURL": "/flash",
            "keepMeLoggedIn": False,
        },
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run the test**

```bash
cd services/siteapp && uv run pytest tests/e2e/test_login_flow.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_login_flow.py
git commit -m "test(siteapp): /api/auth/firstfactor end-to-end"
```

---

## Task 14: siteapp e2e — `/api/auth/whoami` and `/logout`

**Files:**
- Create: `services/siteapp/tests/e2e/test_whoami.py`
- Create: `services/siteapp/tests/e2e/test_logout.py`

- [ ] **Step 1: Write `test_whoami.py`**

```python
"""GET /api/auth/whoami reflects session state."""

from __future__ import annotations

import httpx


def _login(http: httpx.Client, username: str, password: str) -> str:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": username,
            "password": password,
            "targetURL": "/",
            "keepMeLoggedIn": True,
        },
    )
    r.raise_for_status()
    return r.headers.get_list("set-cookie")[0].split(";", 1)[0]


def test_whoami_returns_null_when_anonymous(http: httpx.Client) -> None:
    r = http.get("/api/auth/whoami")
    assert r.status_code == 200
    assert r.json() == {"user": None}


def test_whoami_returns_user_and_groups_when_authenticated(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    body = r.json()
    assert body["user"] == "alice"
    assert "admins" in body["groups"]
```

- [ ] **Step 2: Write `test_logout.py`**

```python
"""GET /logout returns 302 with an expiring authelia_session cookie."""

from __future__ import annotations

import httpx

from .test_whoami import _login


def test_logout_returns_302_and_expires_cookie(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/"
    set_cookies = r.headers.get_list("set-cookie")
    assert any("authelia_session=" in c and ("Max-Age=0" in c or "expires" in c.lower())
               for c in set_cookies)
```

- [ ] **Step 3: Run the tests**

```bash
cd services/siteapp && uv run pytest tests/e2e/test_whoami.py tests/e2e/test_logout.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add services/siteapp/tests/e2e/test_whoami.py services/siteapp/tests/e2e/test_logout.py
git commit -m "test(siteapp): /api/auth/whoami and /logout"
```

---

## Task 15: siteapp e2e — error pages

**Files:**
- Create: `services/siteapp/tests/e2e/test_error_pages.py`

- [ ] **Step 1: Write the failing test**

```python
"""GET /_errors/403 and /_errors/404 render templates extending base.html."""

from __future__ import annotations

import httpx


def test_error_403_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/403")
    assert r.status_code == 200
    body = r.text
    assert "403" in body
    # Base template marker.
    assert "/_static/site.css" in body or "/_static/tokens.css" in body


def test_error_404_renders_with_base_template(http: httpx.Client) -> None:
    r = http.get("/_errors/404")
    assert r.status_code == 200
    body = r.text
    assert "404" in body
    assert "/_static/site.css" in body or "/_static/tokens.css" in body
```

- [ ] **Step 2: Run**

```bash
cd services/siteapp && uv run pytest tests/e2e/test_error_pages.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_error_pages.py
git commit -m "test(siteapp): /_errors/{403,404} render with base template"
```

---

## Task 16: Caddyfile changes — forward_auth, /auth/*, error handlers

**Files:**
- Modify: `compose/Caddyfile.tmpl`

- [ ] **Step 1: Update `compose/Caddyfile.tmpl`**

Replace the entire `https://__VPS_HOST__ { ... }` block with:

```caddyfile
{
    email __ACME_EMAIL__
    default_sni __VPS_HOST__
    admin :2019

    servers {
        metrics
    }

    order replace after encode
}

(authelia_required) {
    forward_auth authelia:9091 {
        uri /api/verify?rd=https://__VPS_HOST__/login
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
}

https://__VPS_HOST__ {
    tls {
        issuer acme {
            profile shortlived
        }
    }

    # ─── Platform shell assets ───────────────────────────────────────────
    handle /_shared/* {
        uri strip_prefix /_shared
        root * /srv/shell
        file_server {
            precompressed gzip
        }
        header Cache-Control "public, max-age=60, must-revalidate"
    }

    # ─── Authelia (public — OIDC discovery + redirects) ──────────────────
    handle /auth/* {
        reverse_proxy authelia:9091 {
            header_up -Accept-Encoding
        }
    }

    # ─── siteapp public routes (unchanged) ───────────────────────────────
    handle /_static/* {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /docs* {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /download* {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /api/agent/upload {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /api/public* {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }

    # ─── siteapp auth surface (login form, API, error pages) ─────────────
    handle /login {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /logout {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /api/auth/* {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }

    # ─── Flasher (admins only — forward_auth replaces basic_auth) ────────
    handle /flash/api/v1/* {
        reverse_proxy flasher:8000 {
            header_up -Accept-Encoding
        }
    }
    handle /flash* {
        import authelia_required
        reverse_proxy flasher:8000 {
            header_up -Accept-Encoding
        }
    }

    # ─── Grafana (OIDC handled inside Grafana; Caddy stays as proxy) ─────
    handle /grafana/* {
        header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
        header Content-Security-Policy "(style-src[^;]*)" "${1} 'self'"
        reverse_proxy grafana:3000 {
            header_up -Accept-Encoding
        }
    }

    # ─── JupyterLab (forward_auth replaces shared password) ──────────────
    handle /jupyter* {
        import authelia_required
        header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
        header Content-Security-Policy "(style-src[^;]*)" "${1} 'self'"
        reverse_proxy jupyter:8888 {
            header_up -Accept-Encoding
        }
    }

    # ─── Temporary redirect for old Jupyter bookmarks ────────────────────
    @old_jupyter {
        path /lab* /tree*
    }
    redir @old_jupyter /jupyter{uri} 302

    # ─── Home — siteapp serves / ─────────────────────────────────────────
    handle / {
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }

    # ─── Global HTML rewrite — navbar injection ──────────────────────────
    replace {
        match {
            header Content-Type *text/html*
        }
        "</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" data-version="__PLATFORM_VERSION__" defer></script></head>`
    }

    # ─── Error pages → siteapp templates ─────────────────────────────────
    handle_errors {
        @e403 expression {http.error.status_code} == 403
        @e404 expression {http.error.status_code} == 404
        @e401 expression {http.error.status_code} == 401
        rewrite @e403 /_errors/403
        rewrite @e404 /_errors/404
        # 401 from forward_auth is already turned into a 302 to /login by the
        # snippet's rd= parameter. If we still see a 401 here, treat it as a
        # 403 so the user sees a useful page instead of Caddy's raw error.
        rewrite @e401 /_errors/403
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
}
```

Note: the previous redirect rule included `/login` in the `@old_jupyter` list
(the old shared-password Jupyter exposed `/login`). That overlaps with our new
siteapp `/login` and is removed.

- [ ] **Step 2: Update `tests/integration/test_routes_smoke.bats` if it references the basic_auth challenge**

Search the file:

```bash
grep -n "basic_auth\|/flash" tests/integration/test_routes_smoke.bats
```

If any existing test asserts a 401 with `WWW-Authenticate: Basic` for `/flash`,
update it to assert a 302 to `/login?rd=/flash` (the new forward_auth
behaviour). Leave the rest of `test_routes_smoke.bats` alone — the full
auth-flow test lives in `test_auth_smoke.bats` (Task 17).

- [ ] **Step 3: Commit**

```bash
git add compose/Caddyfile.tmpl tests/integration/test_routes_smoke.bats
git commit -m "feat(caddy): forward_auth, /auth/*, /api/auth/*, error rewrites"
```

---

## Task 17: Navbar auth slot

**Files:**
- Modify: `compose/shell/navbar.js`

- [ ] **Step 1: Find the rail-rendering function and add an auth slot**

Read `compose/shell/navbar.js` to locate the function that builds the rail's
inner HTML (look for a `nav` element template literal). Add an
`<aside class="auth-slot"></aside>` placeholder right after the closing `</nav>`
tag of the SERVICES list, in both the persistent rail and the bookmark overlay.

- [ ] **Step 2: Add the whoami fetch + renderer**

Append the following block after the existing mount/append logic (where the
custom element finishes its initial render):

```js
async function renderAuthSlot(root) {
  const slot = root.querySelector('.auth-slot');
  if (!slot) return;
  let data = { user: null };
  try {
    const r = await fetch('/api/auth/whoami', { credentials: 'include' });
    if (r.ok) data = await r.json();
  } catch (_) {
    // Network error — render as logged-out, no surprises.
  }
  if (data.user) {
    const initial = data.user[0].toUpperCase();
    const label = `Sign out (${data.user})`;
    slot.innerHTML = `
      <a class="lds-avatar" href="/logout" aria-label="${label}" title="${label}">
        <span class="lds-avatar-initial">${initial}</span>
      </a>`;
  } else {
    const rd = encodeURIComponent(location.pathname + location.search);
    slot.innerHTML = `
      <a class="lds-login-btn" href="/login?rd=${rd}" aria-label="Sign in">
        Sign in
      </a>`;
  }
}
```

Invoke it once after the element is mounted (regardless of mode), e.g. in the
same place where `detectActiveId()` runs:

```js
renderAuthSlot(this.shadowRoot);
```

- [ ] **Step 3: Add minimal styles**

Search for the existing style block (probably a tagged template literal
inlined in `navbar.js`, or a separate `navbar-inner.css`). Append:

```css
.auth-slot {
  margin-top: auto;
  padding: 12px 8px;
  display: flex;
  justify-content: center;
}
.lds-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent, currentColor);
  color: var(--accent-on, white);
  font-weight: 600;
  text-decoration: none;
}
.lds-login-btn {
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  text-decoration: none;
  color: inherit;
  border: 1px solid currentColor;
}
```

These are placeholders the user will polish later.

- [ ] **Step 4: Commit**

```bash
git add compose/shell/navbar.js
git commit -m "feat(navbar): auth slot with avatar / Sign in button"
```

---

## Task 18: Platform integration — `test_auth_smoke.bats` + pr-platform matrix

**Files:**
- Create: `tests/integration/test_auth_smoke.bats`
- Modify: `.github/workflows/pr-platform.yml`

- [ ] **Step 1: Create `tests/integration/test_auth_smoke.bats`**

```bash
#!/usr/bin/env bats

load helpers.bash

setup_file() {
    compose_images_available || skip "compose images unavailable"
    fake_vps_up_with_users \
        admin:secret:admins \
        researcher:secret:researchers
}

teardown_file() {
    fake_vps_down
}

@test "anonymous GET /flash redirects to /login?rd=/flash" {
    run curl -ksSI "https://$FAKE_VPS_HOST/flash"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    [[ "$output" =~ Location:.*\/login\?rd=.*\/flash ]]
}

@test "anonymous GET /jupyter/ redirects to /login?rd=/jupyter" {
    run curl -ksSI "https://$FAKE_VPS_HOST/jupyter/"
    [[ "$output" =~ HTTP/.*\ 302 ]]
    [[ "$output" =~ Location:.*\/login ]]
}

@test "anonymous GET /grafana/ ends at /login after Authelia redirect" {
    run curl -ksSL -o /dev/null -w '%{url_effective}' "https://$FAKE_VPS_HOST/grafana/"
    [[ "$output" =~ /login ]]
}

@test "admin login round-trip grants /flash" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/flash","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    run curl -ksSI -b "$jar" "https://$FAKE_VPS_HOST/flash"
    [[ "$output" =~ HTTP/.*\ 200 ]]
}

@test "researcher /flash returns 403 page with navbar marker" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"researcher","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    local body
    body="$(curl -ksS -b "$jar" "https://$FAKE_VPS_HOST/flash")"
    [[ "$body" =~ 403 ]]
    [[ "$body" =~ /_shared/navbar.js ]]
}

@test "logout clears cookie and re-redirects" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    curl -ksS -b "$jar" -c "$jar" "https://$FAKE_VPS_HOST/logout" >/dev/null
    run curl -ksSI -b "$jar" "https://$FAKE_VPS_HOST/flash"
    [[ "$output" =~ HTTP/.*\ 302 ]]
}

@test "whoami reflects session state on every handle" {
    local jar="$BATS_TEST_TMPDIR/cookies.jar"
    curl -ksS -c "$jar" \
        -X POST -H "Content-Type: application/json" \
        -d '{"username":"admin","password":"secret","targetURL":"/","keepMeLoggedIn":true}' \
        "https://$FAKE_VPS_HOST/api/auth/firstfactor" >/dev/null
    local body
    body="$(curl -ksS -b "$jar" "https://$FAKE_VPS_HOST/api/auth/whoami")"
    [[ "$body" =~ \"user\":\ ?\"admin\" ]]
    [[ "$body" =~ \"groups\":.*admins ]]
}

@test "task users round-trip works against fake-VPS" {
    # In the fake-VPS harness, the users db is on the host. Exercise the
    # script through the harness.
    run task users:list
    [ "$status" -eq 0 ]
    [[ "$output" =~ admin ]]
    [[ "$output" =~ researcher ]]
}
```

`fake_vps_up_with_users` is a new helper — add it to
`tests/integration/helpers.bash` next to the existing `fake_vps_up` helper.
The helper:
1. Calls the existing `fake_vps_up` to provision Caddy/siteapp/flasher/etc.
2. For each `user:password:group` triple in `$@`, runs
   `PASSWORD=password bash scripts/users.sh add user group`.
3. Restarts the Authelia container so it reloads the file.

(Implement the helper in the same step; mirror the style of the existing
`fake_vps_up` helper in `helpers.bash`. Read that helper first.)

- [ ] **Step 2: Add the `auth` matrix cell to `pr-platform.yml`**

Edit `.github/workflows/pr-platform.yml`. Find the bats matrix (currently has
cells `cheap`, `deploy`, `ops`, `provision`, `routes-smoke`, `navbar` — see
the spec from 2026-05-17-shared-navbar). Add `auth`:

```yaml
        bats-cell:
          - cheap
          - deploy
          - ops
          - provision
          - routes-smoke
          - navbar
          - auth
```

And ensure the step that selects the bats file by cell name maps `auth` →
`tests/integration/test_auth_smoke.bats`.

- [ ] **Step 3: Run locally**

```bash
bats tests/integration/test_auth_smoke.bats
```

Expected: PASS (or `skip` if compose images are unavailable locally — the CI
matrix is the authoritative gate).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_auth_smoke.bats tests/integration/helpers.bash \
        .github/workflows/pr-platform.yml
git commit -m "test(platform): auth smoke bats + pr-platform matrix cell"
```

---

## Task 19: Migration cleanup + user docs

**Files:**
- Modify: `config.example.yaml`
- Modify: `Taskfile.yml`
- Modify: `README.md`
- Modify: `scripts/lib/config.sh`
- Modify: `scripts/secrets.sh`
- Create: `docs/adding-a-user.md`

- [ ] **Step 1: Remove the old admin-password task**

Delete from `Taskfile.yml`:

```yaml
  "secrets:set-admin-password":
    desc: ...
    cmd: bash scripts/secrets.sh set-admin-password
```

Delete `cmd_set_admin_password()` and its `set-admin-password` case from
`scripts/secrets.sh`.

Delete the corresponding bats coverage from
`tests/integration/test_secrets.bats` (the test that exercises
`set-admin-password`).

- [ ] **Step 2: Deprecate the now-unused config keys**

Edit `config.example.yaml`. Remove:

```yaml
siteapp:
  admin_password_hash: "<run task secrets:set-admin-password>"
```

Edit `scripts/lib/config.sh`:

1. Remove `.siteapp.admin_password_hash` from `_REQUIRED_CONFIG_FIELDS`.
2. Remove the `SITEAPP_ADMIN_PASSWORD_HASH` export from `load_config()`.
3. Remove the bcrypt-format validation block in `validate_config()` that
   checks `siteapp.admin_password_hash`.

Keep `.jupyter.password_hash` in `_REQUIRED_CONFIG_FIELDS` for one more
release as a deprecated key, but relax the format check to allow an empty
value (the new Jupyter command line clears the password, but a present hash
should not break the deploy). Replace the `validate_config` block that
checks the sha1 format with:

```bash
local hash
hash="$(_yq e '.jupyter.password_hash // ""' "$config_path")"
if [[ -n "$hash" ]] && ! [[ "$hash" =~ ^sha1:[0-9a-f]+:[0-9a-f]{40}$ ]]; then
    errors+=("jupyter.password_hash is set but not in sha1 format; clear it or run task secrets:set-jupyter-password")
fi
```

Add a comment in `config.example.yaml` next to the field:

```yaml
jupyter:
  # Deprecated: Authelia gates Jupyter via Caddy forward_auth. The notebook
  # itself runs token-less inside the labnet. This field is ignored at deploy
  # time and will be removed in the release after this one.
  password_hash: ""
```

Update the matching `render_compose` substitution to tolerate an empty value.
Edit `render.sh`:

```bash
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:-}|g" \
```

- [ ] **Step 3: Write `docs/adding-a-user.md`**

```markdown
# Adding a user

Lab-bridge uses Authelia for authentication. Users live in
`compose/authelia/users_database.yml`. Managed via `task users:*`.

## First-time bootstrap

1. Generate Authelia's runtime secrets (once per VPS):
   ```bash
   task secrets:bootstrap-authelia
   ```
2. Add the bootstrap admin:
   ```bash
   task users:add -- you admins
   # Prompts for password.
   ```
3. Deploy:
   ```bash
   task deploy
   ```

## Adding a researcher

```bash
task users:add -- jane researchers
task deploy
```

`researchers` can sign in to JupyterLab and view Grafana dashboards.

## Adding an admin

```bash
task users:add -- jane admins
task deploy
```

`admins` get full access — JupyterLab, Grafana (as Grafana `Admin` role),
and Flasher.

## Other operations

```bash
task users:list                                  # show all users
task users:set-password -- jane                  # rotate jane's password
task users:set-groups -- jane admins,researchers # change membership
task users:rm -- jane                            # remove jane (immediate effect on next request)
```

## Forgotten password recovery

There is no self-service reset (no SMTP). An admin runs:

```bash
task users:set-password -- jane
```

…and tells Jane the new password out-of-band.

## Loss of bootstrap admin

If every admin has lost their password:

1. SSH to the VPS.
2. Generate an argon2id hash:
   ```bash
   docker run --rm authelia/authelia:4.38.10 \
     authelia hash-password --no-confirm 'newpassword'
   ```
3. Paste the hash into `/srv/lab-bridge/authelia/users_database.yml` under
   the relevant user's `password:` field.
4. `docker compose restart authelia`.
```

- [ ] **Step 4: Update `README.md`**

Add a short pointer to the new docs, near the existing "Operations" section.
Don't overwrite the README — just append the auth pointer:

```markdown
## Users & authentication

See [docs/adding-a-user.md](docs/adding-a-user.md). Users are managed via
`task users:*`; the first one is the bootstrap admin.
```

- [ ] **Step 5: Commit**

```bash
git add config.example.yaml Taskfile.yml scripts/lib/config.sh scripts/secrets.sh \
        scripts/lib/render.sh tests/integration/test_secrets.bats \
        docs/adding-a-user.md README.md
git commit -m "chore(auth): retire admin-password task, add users docs"
```

---

## Final verification

After all 19 tasks land on the branch:

- [ ] **All service-level e2e suites pass**

```bash
cd services/authelia && uv run pytest tests/e2e/ -v
cd services/siteapp && uv run pytest tests/e2e/ -v
```

- [ ] **All bats integration suites pass**

```bash
bats tests/integration/test_render.bats
bats tests/integration/test_secrets.bats
bats tests/integration/test_users.bats
bats tests/integration/test_routes_smoke.bats
bats tests/integration/test_auth_smoke.bats
```

- [ ] **PR title for squash-merge**

`feat(platform): unified Authelia auth with groups and custom login`
(minor bump under release-please).

- [ ] **Required-check list updated in branch protection**

Add `pr-authelia / authelia` to the list before the workflow becomes blocking.

- [ ] **Migration on a running VPS** (post-merge, manual)

1. `task secrets:bootstrap-authelia`
2. `task users:add -- <name> admins` for the bootstrap admin
3. `task users:add -- <name> <group>` for each existing teammate
4. `task deploy`
5. Verify `/flash`, `/jupyter`, `/grafana` all bounce through `/login` for
   anonymous browsers, and that admin/researcher group rules behave as
   expected.

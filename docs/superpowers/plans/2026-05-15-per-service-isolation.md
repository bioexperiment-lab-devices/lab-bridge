# Per-service Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the monorepo so each service has independent versioning, independent CI, and a fast service-level e2e layer — while keeping a thin platform-integration test that proves the whole stack wires up.

**Architecture:** Move `compose/{siteapp,flasher}/` to `services/{siteapp,flasher}/`. Switch release-please from one shared component to three (`siteapp`, `flasher`, `platform`) with independent tags. Replace one big `pr.yml` `verify` job with three parallel workflows (`pr-siteapp.yml`, `pr-flasher.yml`, `pr-platform.yml`), each path-gated internally. Add per-service pytest e2e harnesses (one container + minimal stubs, no fake-VPS). Slim the bats fake-VPS suite to a single `test_routes_smoke.bats` that asserts only Caddy routing.

**Tech Stack:** Python 3.13 + FastAPI + uv + ruff + pytest (services); bats + Docker (platform integration); release-please-action v5 (multi-component manifest mode); GitHub Actions with `dorny/paths-filter@v3`; renovate.

**Spec:** `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md`

---

## Pre-flight setup

Run once before starting any task.

- [ ] **Step 0.1: Verify clean working tree on `main`**

Run: `git status && git rev-parse --abbrev-ref HEAD`
Expected: working tree clean (modulo `.claude/` untracked dir), branch `main`.

- [ ] **Step 0.2: Create feature branch**

Run:
```bash
git checkout -b chore/per-service-isolation
```
Expected: switched to a new branch.

- [ ] **Step 0.3: Confirm bats + uv + Task + docker are installed**

Run:
```bash
which bats yq task docker uv && uv --version
```
Expected: all commands resolved, uv version >=0.4.

---

## PR 1 — Full restructure

### Task 1: Relocate `compose/{siteapp,flasher}/` → `services/{siteapp,flasher}/`

**Goal:** Pure path move. CI still green using the existing `pr.yml`. No semantic change.

**Files:**
- Move: `compose/siteapp/` → `services/siteapp/` (entire tree, ~25 files)
- Move: `compose/flasher/` → `services/flasher/` (entire tree, ~30 files)
- Modify: `scripts/lib/render.sh` (lines 6-41, VERSION path references)
- Modify: `Taskfile.yml` (lines 81, 86, build.sh paths)
- Modify: `services/siteapp/build.sh` (line 22, error message path string)
- Modify: `services/flasher/build.sh` (line 22, error message path string)
- Modify: `tests/helpers.bash` (lines 54-70, `compose/<svc>/VERSION` and `compose/<svc>` build context)
- Modify: `release-please-config.json` (lines 8-9, `extra-files` paths)
- Modify: `.github/workflows/pr.yml` (lines 60-67, path filters; lines 127, 136, 141, 146, 151, 162, 176, 185, 191, 195, 200, 213, 218, 223, 234 — paths and working-directory)
- Modify: `.github/workflows/release-please.yml` (lines 91, 115, build contexts)
- Modify: `renovate.json` (no path change needed — no per-service paths referenced; verify)
- Modify: `CLAUDE.md` (line 50, bats path examples — `tests/test_siteapp_*.bats` references remain valid until Task 5)

- [ ] **Step 1.1: Move siteapp tree**

Run:
```bash
git mv compose/siteapp services/siteapp
git status
```
Expected: `renamed: compose/siteapp/... -> services/siteapp/...` for ~25 files (rename detection should pick all up).

- [ ] **Step 1.2: Move flasher tree**

Run:
```bash
git mv compose/flasher services/flasher
git status
```
Expected: rename detection for ~30 files.

- [ ] **Step 1.3: Update `scripts/lib/render.sh` paths**

Edit `scripts/lib/render.sh`:

Replace lines 7-8:
```bash
# Reads compose/siteapp/VERSION (override via LDS_SITEAPP_VERSION_FILE for tests).
# VERSION path is resolved REPO-ROOT-RELATIVE via this script's location,
```
with:
```bash
# Reads services/siteapp/VERSION (override via LDS_SITEAPP_VERSION_FILE for tests).
# VERSION path is resolved REPO-ROOT-RELATIVE via this script's location,
```

Replace line 17:
```bash
        version_file="$script_dir/../../compose/siteapp/VERSION"
```
with:
```bash
        version_file="$script_dir/../../services/siteapp/VERSION"
```

Replace line 27:
```bash
# Reads compose/flasher/VERSION (override via LDS_FLASHER_VERSION_FILE for tests).
```
with:
```bash
# Reads services/flasher/VERSION (override via LDS_FLASHER_VERSION_FILE for tests).
```

Replace line 34:
```bash
        version_file="$script_dir/../../compose/flasher/VERSION"
```
with:
```bash
        version_file="$script_dir/../../services/flasher/VERSION"
```

- [ ] **Step 1.4: Update `Taskfile.yml` build.sh paths**

Edit `Taskfile.yml`:

Replace line 80:
```yaml
    desc: Build and push the siteapp image. Reads version from compose/siteapp/VERSION; reads SITEAPP_IMAGE_REPO from compose/pins.yaml (or env override).
```
with:
```yaml
    desc: Build and push the siteapp image. Reads version from services/siteapp/VERSION; reads SITEAPP_IMAGE_REPO from compose/pins.yaml (or env override).
```

Replace line 81:
```yaml
    cmd: bash compose/siteapp/build.sh
```
with:
```yaml
    cmd: bash services/siteapp/build.sh
```

Replace line 85:
```yaml
    desc: Build and push the flasher image. Reads version from compose/flasher/VERSION; reads FLASHER_IMAGE_REPO from compose/pins.yaml (or env override).
```
with:
```yaml
    desc: Build and push the flasher image. Reads version from services/flasher/VERSION; reads FLASHER_IMAGE_REPO from compose/pins.yaml (or env override).
```

Replace line 86:
```yaml
    cmd: bash compose/flasher/build.sh
```
with:
```yaml
    cmd: bash services/flasher/build.sh
```

- [ ] **Step 1.5: Update `services/siteapp/build.sh` and `services/flasher/build.sh`**

Both scripts use `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` and `REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"`. After the move, `services/<svc>/build.sh` still resolves `REPO_ROOT` correctly via `../..` (just like `compose/<svc>/build.sh` did). The only change is the closing `echo` message.

Edit `services/siteapp/build.sh`, replace line 22:
```bash
echo "Bump compose/siteapp/VERSION and commit to pin this tag."
```
with:
```bash
echo "Bump services/siteapp/VERSION and commit to pin this tag."
```

Edit `services/flasher/build.sh`, replace line 22:
```bash
echo "Bump compose/flasher/VERSION and commit to pin this tag."
```
with:
```bash
echo "Bump services/flasher/VERSION and commit to pin this tag."
```

- [ ] **Step 1.6: Update `tests/helpers.bash` to load images from new paths**

Edit `tests/helpers.bash`:

Replace line 54:
```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/compose/siteapp/VERSION")"
```
with:
```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/services/siteapp/VERSION")"
```

Replace line 56:
```bash
    docker build --load -q -t "$fixture_tag" "$ROOT/compose/siteapp" >&2 || return 1
```
with:
```bash
    docker build --load -q -t "$fixture_tag" "$ROOT/services/siteapp" >&2 || return 1
```

Replace line 68:
```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/compose/flasher/VERSION")"
```
with:
```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/services/flasher/VERSION")"
```

Replace line 70:
```bash
    docker build --load -q -t "$fixture_tag" "$ROOT/compose/flasher" >&2 || return 1
```
with:
```bash
    docker build --load -q -t "$fixture_tag" "$ROOT/services/flasher" >&2 || return 1
```

- [ ] **Step 1.7: Update `release-please-config.json` extra-files paths**

Edit `release-please-config.json`. Replace the entire `extra-files` block (lines 7-10):
```json
      "extra-files": [
        { "type": "generic", "path": "compose/siteapp/VERSION" },
        { "type": "generic", "path": "compose/flasher/VERSION" }
      ]
```
with:
```json
      "extra-files": [
        { "type": "generic", "path": "services/siteapp/VERSION" },
        { "type": "generic", "path": "services/flasher/VERSION" }
      ]
```

(This is temporary — the whole file gets rewritten in Task 7. But we keep it valid for this commit so release-please doesn't error on `main`.)

- [ ] **Step 1.8: Update `.github/workflows/pr.yml` paths**

Edit `.github/workflows/pr.yml`:

Replace `compose/siteapp/**` (line 64) with `services/siteapp/**`.
Replace `compose/flasher/**` (line 66) with `services/flasher/**`.
Replace each `working-directory: compose/siteapp` (lines 136, 141, 146, 151) with `working-directory: services/siteapp`.
Replace each `working-directory: compose/flasher` (lines 185, 190, 195, 200) with `working-directory: services/flasher`.
Replace `python-version-file: compose/siteapp/.python-version` (line 127) with `python-version-file: services/siteapp/.python-version`.
Replace `python-version-file: compose/flasher/.python-version` (line 176) with `python-version-file: services/flasher/.python-version`.
Replace `cache-dependency-path: compose/flasher/web/package-lock.json` (line 209) with `cache-dependency-path: services/flasher/web/package-lock.json`.
Replace each `working-directory: compose/flasher/web` (lines 213, 218, 223) with `working-directory: services/flasher/web`.
Replace `context: compose/siteapp` (line 162) with `context: services/siteapp`.
Replace `context: compose/flasher` (line 234) with `context: services/flasher`.

- [ ] **Step 1.9: Update `.github/workflows/release-please.yml` build contexts**

Edit `.github/workflows/release-please.yml`:

Replace `context: compose/siteapp` (line 91) with `context: services/siteapp`.
Replace `context: compose/flasher` (line 115) with `context: services/flasher`.

- [ ] **Step 1.10: Verify renovate.json**

Run: `grep -n 'compose/siteapp\|compose/flasher' renovate.json`
Expected: no output (renovate.json only pattern-matches against `compose/pins.yaml`, which doesn't move). No change needed.

- [ ] **Step 1.11: Update CLAUDE.md path references**

Edit `CLAUDE.md`. Update only the `compose/siteapp/VERSION` reference for now; the bats example will be updated in Task 5 when the bats files actually move.

Line 18-19, replace:
```
- **Don't bump versions by hand.** release-please owns `compose/siteapp/VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
```
with:
```
- **Don't bump versions by hand.** release-please owns `services/siteapp/VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
```

- [ ] **Step 1.12: Sanity-check the codebase still builds locally**

Run:
```bash
cd services/siteapp && uv sync --frozen && uv run pytest -v && cd ../..
cd services/flasher && uv sync --frozen && uv run pytest -v && cd ../..
```
Expected: both test suites pass.

- [ ] **Step 1.13: Sanity-check that bats still resolves paths**

Run the cheap bats tests (no fake-VPS bring-up):
```bash
bats tests/test_render.bats tests/test_config.bats tests/test_crypto.bats tests/test_secrets.bats tests/test_deploy_stack_only.bats
```
Expected: all pass.

- [ ] **Step 1.14: Commit Task 1**

Run:
```bash
git add -A
git status   # review the rename detection and edits
git commit -m "$(cat <<'EOF'
chore(repo): move services to services/<name>/

compose/{siteapp,flasher}/ → services/{siteapp,flasher}/. Mechanical
move with path updates in render.sh, Taskfile, build.sh, helpers.bash,
release-please-config.json, pr.yml, release-please.yml.

Source-tree only — runtime VPS layout (compose/siteapp/agent_upload_token,
compose/siteapp/clients.json) unchanged; deploy.sh untouched.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: one commit with rename + edits.

---

### Task 2: Add siteapp e2e harness

**Goal:** Create a pytest e2e suite that spins up the siteapp container directly via `docker compose` and exercises its HTTP endpoints. No Caddy, no chisel, no fake-VPS.

**Files:**
- Create: `services/siteapp/tests/e2e/__init__.py`
- Create: `services/siteapp/tests/e2e/conftest.py`
- Create: `services/siteapp/tests/e2e/compose.yaml`
- Create: `services/siteapp/tests/e2e/fixtures/clients.json`
- Create: `services/siteapp/tests/e2e/fixtures/agent_upload_token`
- Create: `services/siteapp/tests/e2e/test_server_info.py`
- Create: `services/siteapp/tests/e2e/test_health.py`
- Create: `services/siteapp/tests/e2e/test_public_clients.py`
- Create: `services/siteapp/tests/e2e/test_admin_upload.py`
- Create: `services/siteapp/tests/e2e/test_safety.py`
- Modify: `services/siteapp/pyproject.toml` (exclude e2e from default pytest collection)

- [ ] **Step 2.1: Add e2e __init__.py marker**

Create `services/siteapp/tests/e2e/__init__.py` (empty file).

- [ ] **Step 2.2: Exclude `tests/e2e` from default pytest run**

The unit-test workflow runs `uv run pytest -v` from the service dir; the e2e suite is invoked separately. Configure pytest to ignore `tests/e2e/` by default.

Edit `services/siteapp/pyproject.toml`. Replace:
```toml
[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
```
with:
```toml
[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
# E2E tests have their own setup (docker compose) and are invoked
# explicitly via `pytest tests/e2e/`. Exclude from default collection.
norecursedirs = ["tests/e2e"]
```

- [ ] **Step 2.3: Create test fixtures**

Create `services/siteapp/tests/e2e/fixtures/clients.json`:
```json
{
  "alice_machine": {
    "port": 9001,
    "password_sha256": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
  }
}
```
(The hash is sha256 of `"password"` — a deterministic, well-known test value. Tests using this fixture know the plaintext.)

Create `services/siteapp/tests/e2e/fixtures/agent_upload_token`:
```
e2e-test-token
```
(no trailing newline)

- [ ] **Step 2.4: Create harness compose.yaml**

Create `services/siteapp/tests/e2e/compose.yaml`:
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
      SITE_DATA: /data
    volumes:
      - ./fixtures/clients.json:/etc/siteapp/clients.json:ro
      - ./fixtures/agent_upload_token:/run/secrets/agent_upload_token:ro
      - siteapp_data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"]
      interval: 1s
      timeout: 2s
      retries: 30

volumes:
  siteapp_data:
```

- [ ] **Step 2.5: Create conftest.py with session fixture**

Create `services/siteapp/tests/e2e/conftest.py`:
```python
"""Session-scoped fixture: bring siteapp up via docker compose, tear it down.

The image to run is selected via SITEAPP_TEST_IMAGE env var (default
``lab-bridge-siteapp:e2e``). CI builds the image in the workflow's
image-build step and exports the tag; local runs should
``docker build -t lab-bridge-siteapp:e2e services/siteapp`` first.
"""
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
def siteapp_url() -> str:
    _compose("up", "-d", "--wait")
    try:
        yield "http://127.0.0.1:8001"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(siteapp_url: str) -> httpx.Client:
    with httpx.Client(base_url=siteapp_url, timeout=5.0) as client:
        yield client
```

- [ ] **Step 2.6: Write the first e2e test (server-info)**

Create `services/siteapp/tests/e2e/test_server_info.py`:
```python
def test_server_info_returns_expected_shape(http) -> None:
    r = http.get("/api/public/server-info")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == {"listen_port": 7000}
    assert body["version"] == "e2e-test"
    assert body["git_sha"] == "test"
    assert isinstance(body["forward_tunnels"], list)
    assert any(t["name"] == "loki" for t in body["forward_tunnels"])
```

- [ ] **Step 2.7: Build the image and verify the harness works**

Run:
```bash
docker build -t lab-bridge-siteapp:e2e services/siteapp
cd services/siteapp
uv run pytest tests/e2e/test_server_info.py -v
cd ../..
```
Expected: 1 passed. (The harness spins the container up, hits the endpoint, tears it down.)

- [ ] **Step 2.8: Write `test_health.py`**

Create `services/siteapp/tests/e2e/test_health.py`:
```python
def test_health_returns_chisel_status(http) -> None:
    """/api/public/health probes chisel:7000/health. In the harness chisel
    is not running, so we accept either ok (unlikely) or down (expected).
    What we're testing: the route exists, is unauthenticated, returns 200.
    """
    r = http.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert "chisel" in body
    assert body["chisel"] in {"ok", "down"}


def test_healthz_returns_200(http) -> None:
    r = http.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2.9: Write `test_public_clients.py`**

Create `services/siteapp/tests/e2e/test_public_clients.py`:
```python
"""Tests for /api/public/clients/<username>. The fixture roster has
``alice_machine`` with port 9001 and password 'password' (sha256 of
'password' is in the fixture).
"""
from __future__ import annotations


VALID_USER = "alice_machine"
VALID_PASSWORD = "password"  # plaintext for which the fixture stores sha256


def test_public_clients_happy_path(http) -> None:
    r = http.get(
        f"/api/public/clients/{VALID_USER}",
        headers={"Authorization": f"Bearer {VALID_PASSWORD}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["port"] == 9001
    # chisel isn't running in the harness, so connected is False
    assert body["connected"] is False


def test_public_clients_wrong_password_returns_401(http) -> None:
    r = http.get(
        f"/api/public/clients/{VALID_USER}",
        headers={"Authorization": "Bearer wrong-password"},
    )
    assert r.status_code == 401


def test_public_clients_unknown_user_returns_401(http) -> None:
    r = http.get(
        "/api/public/clients/nobody",
        headers={"Authorization": f"Bearer {VALID_PASSWORD}"},
    )
    assert r.status_code == 401


def test_public_clients_no_auth_header_returns_401(http) -> None:
    r = http.get(f"/api/public/clients/{VALID_USER}")
    assert r.status_code == 401
```

- [ ] **Step 2.10: Write `test_admin_upload.py`**

The agent-upload endpoint is bearer-token gated by siteapp itself (api.py:_check_token), so this is testable in the e2e layer.

Create `services/siteapp/tests/e2e/test_admin_upload.py`:
```python
"""Tests for POST /api/agent/upload — the CI agent-upload endpoint.

Bearer token is read from /run/secrets/agent_upload_token inside the
container (mounted from fixtures/agent_upload_token == 'e2e-test-token').
"""
from __future__ import annotations

import io


TOKEN = "e2e-test-token"


def test_upload_succeeds_with_valid_token(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"\x00\x01\x02FAKE_EXE"), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.2.3"
    assert body["size"] == 9
    # sha256 of b"\x00\x01\x02FAKE_EXE"
    assert len(body["sha256"]) == 64


def test_upload_rejects_invalid_version(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "not.semver"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert r.status_code == 400


def test_upload_no_auth_returns_401(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post("/api/agent/upload", files=files, data=data)
    assert r.status_code == 401


def test_upload_wrong_token_returns_401(http) -> None:
    files = {"binary": ("agent.exe", io.BytesIO(b"AAA"), "application/octet-stream")}
    data = {"version": "1.2.3"}
    r = http.post(
        "/api/agent/upload",
        headers={"Authorization": "Bearer wrong"},
        files=files,
        data=data,
    )
    assert r.status_code == 401


def test_uploaded_agent_is_downloadable(http) -> None:
    """After upload, the binary is served back via GET /download/agent."""
    payload = b"DOWNLOADABLE_EXE_BYTES"
    files = {"binary": ("agent.exe", io.BytesIO(payload), "application/octet-stream")}
    data = {"version": "9.9.9"}
    up = http.post(
        "/api/agent/upload",
        headers={"Authorization": f"Bearer {TOKEN}"},
        files=files,
        data=data,
    )
    assert up.status_code == 200

    dl = http.get("/download/agent.exe")
    assert dl.status_code == 200
    assert dl.content == payload
```

- [ ] **Step 2.11: Write `test_safety.py`**

Create `services/siteapp/tests/e2e/test_safety.py`:
```python
"""Path-traversal in admin upload + HTML-escape on rendered markdown.

These are siteapp-behaviour assertions formerly in test_siteapp_safety.bats.
The /admin/* docs upload endpoints are operator-authenticated at the Caddy
edge in production — in the harness there's no Caddy, so we hit the routes
on the siteapp port directly. (Siteapp itself enforces request-shape
validation independent of who's authenticated.)
"""
from __future__ import annotations

import io


# These tests assume admin docs upload accepts a `target` form field and
# writes to <site_data>/docs/<target>. Path traversal in `target` must be
# rejected (400) before any disk write.

def test_admin_docs_upload_rejects_traversal_target(http) -> None:
    files = {"file": ("test.md", io.BytesIO(b"# hi"), "text/markdown")}
    data = {"target": "../escape.md"}
    # /admin/ endpoints normally sit behind Caddy basic_auth in prod.
    # We hit siteapp directly; the route should still validate `target`.
    r = http.post("/admin/docs/upload", files=files, data=data)
    # Expect 400 (traversal rejected) — NOT 200/302 (would mean traversal accepted).
    assert r.status_code == 400, (
        f"path traversal not rejected: got {r.status_code} body={r.text!r}"
    )


def test_uploaded_markdown_with_raw_html_is_escaped(http) -> None:
    """An admin-uploaded .md containing raw <script> renders escaped, so a
    viewer's browser doesn't execute it (defence against an admin
    uploading user-supplied markdown)."""
    payload = b"# Title\n\n<script>alert('xss')</script>\n"
    files = {"file": ("xss-test.md", io.BytesIO(payload), "text/markdown")}
    data = {"target": "xss-test.md"}
    up = http.post("/admin/docs/upload", files=files, data=data)
    assert up.status_code == 200, f"upload failed: {up.status_code} {up.text}"

    rendered = http.get("/docs/xss-test")
    assert rendered.status_code == 200
    body = rendered.text
    # The raw <script> must be escaped — &lt;script&gt; or removed by bleach.
    assert "<script>" not in body, "raw <script> tag leaked into rendered HTML"
    assert "alert('xss')" not in body or "&lt;script&gt;" in body or "&amp;lt;" in body
```

- [ ] **Step 2.12: Run the full siteapp e2e suite**

Run:
```bash
cd services/siteapp
uv run pytest tests/e2e/ -v
cd ../..
```
Expected: all tests pass. If a test fails, **read the failure carefully** — the harness may need adjustment for production siteapp behavior. Adjust assertions to match what siteapp actually does (don't relax the safety tests — they're load-bearing).

- [ ] **Step 2.13: Confirm unit tests still pass and aren't including e2e**

Run:
```bash
cd services/siteapp
uv run pytest -v   # no path = default collection; norecursedirs excludes tests/e2e
cd ../..
```
Expected: existing ~80 unit tests pass; no e2e tests collected.

- [ ] **Step 2.14: Commit Task 2**

Run:
```bash
git add -A
git commit -m "$(cat <<'EOF'
test(siteapp): add e2e harness

Pytest-based end-to-end suite for siteapp. Spins up the siteapp container
directly via docker compose with stub fixtures (clients.json, agent token);
exercises /api/public/{server-info,health,clients/<u>}, /api/agent/upload
auth + happy path, /admin/docs/upload path-traversal + HTML-escape.

No Caddy, no chisel, no fake-VPS. Runs in <60s once the image is built.
Invoked via `pytest tests/e2e/`; excluded from default collection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add flasher e2e harness + stub-serialhop

**Goal:** End-to-end pytest harness for flasher that exercises the full HTTP/job path against a stub SerialHop responder. No real AVR, no real chisel.

**Files:**
- Create: `services/flasher/tests/e2e/__init__.py`
- Create: `services/flasher/tests/e2e/conftest.py`
- Create: `services/flasher/tests/e2e/compose.yaml`
- Create: `services/flasher/tests/e2e/fixtures/clients.json`
- Create: `services/flasher/tests/e2e/stub_serialhop/__init__.py`
- Create: `services/flasher/tests/e2e/stub_serialhop/main.py`
- Create: `services/flasher/tests/e2e/stub_serialhop/Dockerfile`
- Create: `services/flasher/tests/e2e/stub_serialhop/pyproject.toml`
- Create: `services/flasher/tests/e2e/test_clients.py`
- Create: `services/flasher/tests/e2e/test_flash_success.py`
- Create: `services/flasher/tests/e2e/test_flash_rolled_back.py`
- Create: `services/flasher/tests/e2e/test_spa.py`
- Modify: `services/flasher/pyproject.toml` (exclude e2e from default collection)

- [ ] **Step 3.1: Add `__init__.py` and exclude e2e from default pytest**

Create `services/flasher/tests/e2e/__init__.py` (empty).

Edit `services/flasher/pyproject.toml`. Replace:
```toml
[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
```
with:
```toml
[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"
norecursedirs = ["tests/e2e"]
```

- [ ] **Step 3.2: Build the stub-SerialHop responder**

The stub must implement the subset of SerialHop's API that flasher's `SerialHopClient` uses: `GET /serial/ports/detailed`, `POST /devices/disconnect`, `POST /flash/{port}`. Behavior is controlled via env vars so individual tests can switch outcomes.

Create `services/flasher/tests/e2e/stub_serialhop/main.py`:
```python
"""Tiny FastAPI app that pretends to be SerialHop for flasher e2e tests.

Behavior is controlled via env vars set on the compose service:
- STUB_FLASH_OUTCOME: one of "success", "rolled_back_test_failed",
  "rolled_back_verify_failed", "failed_backup", "failed_preflight",
  "failed_no_recovery". Default "success".
- STUB_PORTS_JSON: JSON for GET /serial/ports/detailed response.
  Default returns one Arduino-shaped port.
"""
from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI

app = FastAPI()


DEFAULT_PORTS = {
    "ports": [
        {
            "name": "COM3",
            "is_usb": True,
            "vid": "2341",
            "pid": "0043",
            "serial_number": "TEST-SERIAL",
            "product": "Arduino Uno (stub)",
            "discovered": False,
            "device_id": "",
        }
    ]
}


def _flash_response(port: str, outcome: str) -> dict[str, Any]:
    base = {
        "outcome": outcome,
        "port": port,
        "stages": {
            "preflight": {"status": "ok", "duration_ms": 12},
            "backup": {"status": "ok", "duration_ms": 100},
            "erase": {"status": "ok", "duration_ms": 50},
            "program": {"status": "ok", "duration_ms": 200},
            "verify": {"status": "ok", "duration_ms": 100},
            "test": {"status": "n/a"},
            "rollback": {"status": "n/a"},
        },
        "backup": {
            "hex": ":00000001FF\n",
            "saved_path": "/tmp/stub.hex",
            "sha256": "0" * 64,
            "size_bytes": 12,
            "scope": "flash_only",
        },
    }
    if outcome == "rolled_back_test_failed":
        base["stages"]["test"] = {"status": "failed", "duration_ms": 50, "error": "mismatch"}
        base["stages"]["rollback"] = {"status": "ok", "duration_ms": 200, "verify_status": "ok"}
        base["test_result"] = {"sent": "010203", "expected": "aabbcc", "received": "0000", "match": False}
    elif outcome == "rolled_back_verify_failed":
        base["stages"]["verify"] = {"status": "failed", "duration_ms": 100, "first_mismatch_offset": "0x010"}
        base["stages"]["rollback"] = {"status": "ok", "duration_ms": 200, "verify_status": "ok"}
    elif outcome == "failed_backup":
        base["stages"]["backup"] = {"status": "failed", "duration_ms": 50, "error": "no device"}
        base["stages"]["erase"] = {"status": "skipped"}
        base["stages"]["program"] = {"status": "skipped"}
        base["stages"]["verify"] = {"status": "skipped"}
        base["backup"] = None
    elif outcome == "failed_no_recovery":
        base["stages"]["verify"] = {"status": "failed", "duration_ms": 100}
        base["stages"]["rollback"] = {"status": "failed", "duration_ms": 200, "verify_status": "failed"}
        base["recovery_hint"] = "use an ISP programmer; backup preserved with -LOCKED- marker"
    elif outcome != "success":
        # success: include test=ok with positive result
        base["stages"]["test"] = {"status": "ok", "duration_ms": 50}
        base["test_result"] = {"sent": "010203", "expected": "aabbcc", "received": "aabbcc", "match": True}
    return base


@app.get("/serial/ports/detailed")
def get_ports() -> dict:
    raw = os.environ.get("STUB_PORTS_JSON")
    if raw:
        return json.loads(raw)
    return DEFAULT_PORTS


@app.post("/devices/disconnect")
def disconnect() -> dict:
    return {"released": 0}


@app.post("/flash/{port}")
def flash(port: str) -> dict:
    outcome = os.environ.get("STUB_FLASH_OUTCOME", "success")
    return _flash_response(port, outcome)
```

Create `services/flasher/tests/e2e/stub_serialhop/__init__.py` (empty).

Create `services/flasher/tests/e2e/stub_serialhop/pyproject.toml`:
```toml
[project]
name = "stub-serialhop"
version = "0.0.1"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
]
```

Create `services/flasher/tests/e2e/stub_serialhop/Dockerfile`:
```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir 'fastapi>=0.115,<0.116' 'uvicorn[standard]>=0.30,<0.31'
COPY main.py /app/main.py
EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
```

- [ ] **Step 3.3: Create harness fixtures**

Create `services/flasher/tests/e2e/fixtures/clients.json`:
```json
{
  "alice_machine": {
    "port": 9000,
    "password_sha256": "ignored-by-flasher"
  }
}
```
(Flasher's `load_roster` reads only `port`; password hash is irrelevant inside this service.)

- [ ] **Step 3.4: Create harness compose.yaml**

Create `services/flasher/tests/e2e/compose.yaml`:
```yaml
services:
  stub-serialhop:
    build: ./stub_serialhop
    expose:
      - "9000"
    environment:
      STUB_FLASH_OUTCOME: "${STUB_FLASH_OUTCOME:-success}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9000/serial/ports/detailed').status==200 else 1)"]
      interval: 1s
      timeout: 2s
      retries: 30

  flasher:
    image: ${FLASHER_TEST_IMAGE:-lab-bridge-flasher:e2e}
    ports:
      - "127.0.0.1:8002:8000"
    environment:
      LAB_BRIDGE_VERSION: "e2e-test"
      LAB_BRIDGE_GIT_SHA: "test"
      FLASHER_CLIENTS_FILE: /etc/flasher/clients.json
      # Point flasher's SerialHop client at the stub instead of `chisel`.
      FLASHER_CHISEL_HOST: stub-serialhop
    volumes:
      - ./fixtures/clients.json:/etc/flasher/clients.json:ro
    depends_on:
      stub-serialhop:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)"]
      interval: 1s
      timeout: 2s
      retries: 30
```

Note: the stub roster's port is 9000, and `FLASHER_CHISEL_HOST=stub-serialhop`, so flasher's `SerialHopClient` connects to `http://stub-serialhop:9000/...` — that's the docker DNS name for the stub. The stub binds 9000 inside its container.

- [ ] **Step 3.5: Create conftest.py with session fixture**

Create `services/flasher/tests/e2e/conftest.py`:
```python
"""Bring flasher + stub-serialhop up via docker compose for the test session."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).parent
COMPOSE_FILE = HERE / "compose.yaml"


def _compose(*args: str, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=check,
        cwd=str(HERE),
        env=proc_env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def flasher_url() -> str:
    _compose("up", "-d", "--build", "--wait")
    try:
        yield "http://127.0.0.1:8002"
    finally:
        _compose("down", "-v", check=False)


@pytest.fixture(scope="session")
def http(flasher_url: str) -> httpx.Client:
    with httpx.Client(base_url=flasher_url, timeout=10.0) as client:
        yield client


@pytest.fixture
def set_stub_outcome():
    """Restart stub-serialhop with a different STUB_FLASH_OUTCOME.

    Usage:
        def test_x(http, set_stub_outcome):
            set_stub_outcome("rolled_back_test_failed")
            ...
    """
    def _set(outcome: str) -> None:
        _compose("stop", "stub-serialhop", check=False)
        _compose("rm", "-f", "stub-serialhop", check=False)
        _compose("up", "-d", "--wait", "stub-serialhop", env={"STUB_FLASH_OUTCOME": outcome})
    return _set
```

- [ ] **Step 3.6: Write `test_clients.py`**

Create `services/flasher/tests/e2e/test_clients.py`:
```python
def test_clients_lists_online_clients(http) -> None:
    """GET /flash/api/clients probes each rostered client via probe_tcp.
    With stub-serialhop running on its port-9000 alias, the probe to
    chisel_host=stub-serialhop:9000 succeeds → client appears online.
    """
    r = http.get("/flash/api/clients")
    assert r.status_code == 200
    body = r.json()
    names = [c["name"] for c in body["clients"]]
    assert "alice_machine" in names


def test_ports_returns_stub_ports(http) -> None:
    r = http.get("/flash/api/clients/alice_machine/ports")
    assert r.status_code == 200
    body = r.json()
    assert "ports" in body
    assert body["ports"][0]["name"] == "COM3"
    assert body["ports"][0]["product"] == "Arduino Uno (stub)"


def test_unknown_client_returns_404(http) -> None:
    r = http.get("/flash/api/clients/nobody/ports")
    assert r.status_code == 404
```

- [ ] **Step 3.7: Write `test_flash_success.py`**

Create `services/flasher/tests/e2e/test_flash_success.py`:
```python
import time


VALID_FIRMWARE_HEX = ":100000000C9461000C947E000C947E000C947E0099\n:00000001FF\n"


def test_flash_happy_path_returns_success_outcome(http) -> None:
    """POST /flash/api/flash returns a job_id; polling /api/flash/<id>
    eventually returns a record whose result.outcome is 'success'.
    """
    r = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "firmware": VALID_FIRMWARE_HEX,
            "test": {"command": "010203", "expected_response": "aabbcc"},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    assert job_id

    # Poll for completion (stub responds quickly, but flasher's state
    # machine has its own bookkeeping).
    for _ in range(30):
        time.sleep(0.5)
        rec = http.get(f"/flash/api/flash/{job_id}")
        assert rec.status_code == 200
        body = rec.json()
        if body.get("state") in {"done", "error"}:
            break
    assert body["state"] == "done", body
    assert body["result"]["outcome"] == "success"


def test_flash_rejects_empty_firmware(http) -> None:
    r = http.post(
        "/flash/api/flash",
        json={"client": "alice_machine", "port": "COM3", "firmware": ""},
    )
    assert r.status_code == 400


def test_flash_rejects_unknown_client(http) -> None:
    r = http.post(
        "/flash/api/flash",
        json={"client": "nobody", "port": "COM3", "firmware": VALID_FIRMWARE_HEX},
    )
    assert r.status_code == 400
```

Note: this test's exact `state`/`outcome` shape may need adjusting to match flasher's actual `JobStore.get()` response. The first run will surface any mismatch — update assertions to match what flasher returns. Don't relax the "outcome must be success" claim.

- [ ] **Step 3.8: Write `test_flash_rolled_back.py`**

Create `services/flasher/tests/e2e/test_flash_rolled_back.py`:
```python
import time


VALID_FIRMWARE_HEX = ":100000000C9461000C947E000C947E000C947E0099\n:00000001FF\n"


def test_flash_returns_rolled_back_outcome_when_stub_rolls_back(http, set_stub_outcome) -> None:
    set_stub_outcome("rolled_back_test_failed")

    r = http.post(
        "/flash/api/flash",
        json={
            "client": "alice_machine",
            "port": "COM3",
            "firmware": VALID_FIRMWARE_HEX,
            "test": {"command": "010203", "expected_response": "aabbcc"},
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    for _ in range(30):
        time.sleep(0.5)
        rec = http.get(f"/flash/api/flash/{job_id}")
        body = rec.json()
        if body.get("state") in {"done", "error"}:
            break
    assert body["result"]["outcome"] == "rolled_back_test_failed"
    assert body["result"]["test_result"]["match"] is False
```

- [ ] **Step 3.9: Write `test_spa.py`**

Create `services/flasher/tests/e2e/test_spa.py`:
```python
def test_spa_index_served_at_flash_root(http) -> None:
    r = http.get("/flash/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_spa_fallback_serves_index_for_unknown_path(http) -> None:
    """Any /flash/<anything> path that isn't a static asset returns index.html
    (standard SPA fallback). Lets the SPA own client-side routing.
    """
    r = http.get("/flash/some/deep/route")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
```

- [ ] **Step 3.10: Build flasher image (including SPA) and run e2e**

The flasher image build needs the SPA. The web build runs inside the Dockerfile.

Run:
```bash
docker build -t lab-bridge-flasher:e2e services/flasher
cd services/flasher
uv run pytest tests/e2e/ -v
cd ../..
```
Expected: all tests pass. The first run may surface assertion-shape mismatches against flasher's actual job-record shape; adjust assertions (not the production code) to match.

- [ ] **Step 3.11: Confirm unit tests still pass and aren't including e2e**

Run:
```bash
cd services/flasher
uv run pytest -v
cd ../..
```
Expected: existing flasher unit tests pass; no e2e collected.

- [ ] **Step 3.12: Commit Task 3**

Run:
```bash
git add -A
git commit -m "$(cat <<'EOF'
test(flasher): add e2e harness + stub-serialhop

Pytest-based end-to-end suite for flasher. Brings up flasher + a tiny
FastAPI stub-SerialHop via docker compose; exercises /api/clients,
/api/clients/<name>/ports, the full /api/flash → poll flow, the SPA
fallback. Stub outcome is parameterised via STUB_FLASH_OUTCOME env var
so tests cover success, rolled_back_test_failed, etc.

No real chisel, no real AVR. Runs in <90s once images are built.
Invoked via `pytest tests/e2e/`; excluded from default collection.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Add per-service workflows `pr-siteapp.yml` and `pr-flasher.yml`

**Goal:** Two new workflows running alongside the existing `verify` job. Each is always-triggered on PR, uses `dorny/paths-filter@v3` internally so docs-only PRs fast-skip. Branch protection is NOT changed yet — these run in *observation mode* until Task 7.

**Files:**
- Create: `.github/workflows/pr-siteapp.yml`
- Create: `.github/workflows/pr-flasher.yml`

- [ ] **Step 4.1: Create `pr-siteapp.yml`**

Create `.github/workflows/pr-siteapp.yml`:
```yaml
name: pr-siteapp

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: pr-siteapp-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  siteapp:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - '.github/workflows/pr-siteapp.yml'

      - if: steps.changed.outputs.src != 'true'
        run: echo "no siteapp changes; skipping all steps"

      - if: steps.changed.outputs.src == 'true'
        uses: actions/setup-python@v5
        with:
          python-version-file: services/siteapp/.python-version
          cache: pip

      - name: install uv
        if: steps.changed.outputs.src == 'true'
        run: pip install uv

      - name: deps
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv sync --frozen

      - name: ruff check
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv run ruff check app tests

      - name: ruff format check
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv run ruff format --check app tests

      - name: pytest (unit)
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv run pytest -v

      - name: docker buildx setup
        if: steps.changed.outputs.src == 'true'
        uses: docker/setup-buildx-action@v3

      - name: image build (no push)
        if: steps.changed.outputs.src == 'true'
        uses: docker/build-push-action@v6
        with:
          context: services/siteapp
          platforms: linux/amd64
          push: false
          load: true
          tags: lab-bridge-siteapp:pr-${{ github.event.pull_request.number }}

      - name: pytest (e2e)
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        env:
          SITEAPP_TEST_IMAGE: lab-bridge-siteapp:pr-${{ github.event.pull_request.number }}
        run: uv run pytest tests/e2e/ -v
```

- [ ] **Step 4.2: Create `pr-flasher.yml`**

Create `.github/workflows/pr-flasher.yml`:
```yaml
name: pr-flasher

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: pr-flasher-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  flasher:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/flasher/**'
              - '.github/workflows/pr-flasher.yml'

      - if: steps.changed.outputs.src != 'true'
        run: echo "no flasher changes; skipping all steps"

      - if: steps.changed.outputs.src == 'true'
        uses: actions/setup-python@v5
        with:
          python-version-file: services/flasher/.python-version
          cache: pip

      - name: install uv
        if: steps.changed.outputs.src == 'true'
        run: pip install uv

      - name: deps
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher
        run: uv sync --frozen

      - name: ruff check
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher
        run: uv run ruff check app tests

      - name: ruff format check
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher
        run: uv run ruff format --check app tests

      - name: pytest (unit)
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher
        run: uv run pytest -v

      - name: setup Node
        if: steps.changed.outputs.src == 'true'
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: npm
          cache-dependency-path: services/flasher/web/package-lock.json

      - name: SPA install
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher/web
        run: npm ci --no-audit --no-fund

      - name: SPA type-check
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher/web
        run: npx tsc --noEmit

      - name: SPA build
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher/web
        run: npm run build

      - name: docker buildx setup
        if: steps.changed.outputs.src == 'true'
        uses: docker/setup-buildx-action@v3

      - name: image build (no push)
        if: steps.changed.outputs.src == 'true'
        uses: docker/build-push-action@v6
        with:
          context: services/flasher
          platforms: linux/amd64
          push: false
          load: true
          tags: lab-bridge-flasher:pr-${{ github.event.pull_request.number }}

      - name: pytest (e2e)
        if: steps.changed.outputs.src == 'true'
        working-directory: services/flasher
        env:
          FLASHER_TEST_IMAGE: lab-bridge-flasher:pr-${{ github.event.pull_request.number }}
        run: uv run pytest tests/e2e/ -v
```

- [ ] **Step 4.3: YAML syntax sanity check**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-siteapp.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-flasher.yml'))"
```
Expected: both succeed with no output.

- [ ] **Step 4.4: Commit Task 4**

Run:
```bash
git add .github/workflows/pr-siteapp.yml .github/workflows/pr-flasher.yml
git commit -m "$(cat <<'EOF'
ci: add pr-siteapp.yml and pr-flasher.yml

Per-service PR workflows. Always trigger on pull_request; gate steps
via dorny/paths-filter@v3 so docs-only PRs fast-skip in <30s. Each
workflow runs lint + unit + image build + e2e suite for its service,
in parallel with the legacy verify job and with the other per-service
workflow.

Not yet required by branch protection — run in observation mode until
the verify job is replaced (see Task 6 / Task 7).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Slim platform integration bats + add `test_routes_smoke.bats`

**Goal:** Move bats files into `tests/integration/`. Delete the four `test_siteapp_*.bats` files. Add a single `test_routes_smoke.bats` that asserts only Caddy routing (one fake-VPS bring-up shared across ~10 curl assertions).

**Files:**
- Move: `tests/test_*.bats` → `tests/integration/test_*.bats`
- Move: `tests/helpers.bash` → `tests/integration/helpers.bash`
- Move: `tests/fake_vps/` → `tests/integration/fake_vps/`
- Move: `tests/fixtures/` → `tests/integration/fixtures/`
- Delete: `tests/integration/test_siteapp_auth.bats`
- Delete: `tests/integration/test_siteapp_routing.bats`
- Delete: `tests/integration/test_siteapp_safety.bats`
- Delete: `tests/integration/test_siteapp_uploads.bats`
- Create: `tests/integration/test_routes_smoke.bats`
- Modify: `.github/workflows/pr.yml` (path update + skip logic update)
- Modify: `CLAUDE.md` (bats path examples)

- [ ] **Step 5.1: Move bats tree into `tests/integration/`**

Run:
```bash
mkdir -p tests/integration
git mv tests/test_*.bats tests/integration/
git mv tests/helpers.bash tests/integration/
git mv tests/fake_vps tests/integration/
git mv tests/fixtures tests/integration/
git status
```
Expected: renames detected for all files.

- [ ] **Step 5.2: Update `tests/integration/helpers.bash` ROOT resolution**

Edit `tests/integration/helpers.bash`. Line 2 currently has:
```bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```
After the move, `helpers.bash` is one level deeper. Change to:
```bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
```

And update lines 40-41:
```bash
fixture() {
    cat "$ROOT/tests/fixtures/$1"
}
```
to:
```bash
fixture() {
    cat "$ROOT/tests/integration/fixtures/$1"
}
```

- [ ] **Step 5.3: Update bats files that reference `tests/fixtures/` directly**

Run:
```bash
grep -rln 'tests/fixtures' tests/integration/
```
Expected: a handful of `.bats` files reference `$ROOT/tests/fixtures/...` (siteapp_routing.bats, etc.) — those four will be deleted in Step 5.5. Update any *surviving* references in `test_deploy.bats`, `test_ops.bats`, `test_provision.bats`, `test_config.bats`, `test_render.bats` if any are found.

For each match, replace `$ROOT/tests/fixtures/` with `$ROOT/tests/integration/fixtures/`. Use sed:
```bash
for f in tests/integration/test_deploy.bats tests/integration/test_ops.bats \
         tests/integration/test_provision.bats tests/integration/test_config.bats \
         tests/integration/test_render.bats tests/integration/test_grafana_provisioning.bats \
         tests/integration/test_deploy_stack_only.bats tests/integration/test_secrets.bats; do
    [[ -f "$f" ]] && sed -i.bak 's|tests/fixtures/|tests/integration/fixtures/|g' "$f" && rm "$f.bak"
done
```

- [ ] **Step 5.4: Update `tests/integration/fake_vps/start.sh` if it references parent paths**

Run:
```bash
grep -n 'tests/' tests/integration/fake_vps/*.sh 2>/dev/null
```
If matches exist, update them similarly. (Most fake_vps scripts resolve their own dir; check before assuming changes are needed.)

- [ ] **Step 5.5: Delete the four siteapp_*.bats files**

Run:
```bash
git rm tests/integration/test_siteapp_auth.bats
git rm tests/integration/test_siteapp_routing.bats
git rm tests/integration/test_siteapp_safety.bats
git rm tests/integration/test_siteapp_uploads.bats
```

- [ ] **Step 5.6: Create `tests/integration/test_routes_smoke.bats`**

This file consolidates Caddy-routing assertions only. Behavior assertions (HTML escape, path traversal, upload semantics) live in siteapp e2e (Task 2).

Create `tests/integration/test_routes_smoke.bats`:
```bash
#!/usr/bin/env bats
# Caddy routing smoke test — one fake-VPS bring-up, all curl assertions.
#
# Asserts only the *route map* (which public path reaches which backend
# service) and the *Caddy-edge auth gates* (/admin/ and /flash/ basic_auth).
# Behavior assertions live in services/<name>/tests/e2e/.

load helpers

setup_file() {
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi
    bash "$ROOT/tests/integration/fake_vps/start.sh"
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    load_siteapp_test_image
    load_flasher_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_siteapp_ready
}

teardown_file() {
    bash "$ROOT/tests/integration/fake_vps/stop.sh" 2>/dev/null || true
}

setup() {
    [[ -f "$BATS_FILE_TMPDIR/skip" ]] && skip "$(cat "$BATS_FILE_TMPDIR/skip")"
}

# Helper: curl through Caddy (TLS internal) from inside the caddy container.
_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -O /dev/null -S \"$1\" 2>&1 | awk \"/HTTP/ {print \\\$2}\" | head -n1
        '
    "
}

@test "/docs/ routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/docs/')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/download/agent routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/download/agent')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/_static/site.css routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/_static/site.css')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/api/public/health routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/api/public/health')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/api/public/server-info routes to siteapp (200)" {
    code="$(_through_caddy 'https://127.0.0.1/api/public/server-info')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/admin/ is gated by basic_auth (401)" {
    code="$(_through_caddy 'https://127.0.0.1/admin/')"
    [[ "$code" == "401" ]] || { echo "got: $code"; false; }
}

@test "/flash/ is gated by basic_auth (401)" {
    code="$(_through_caddy 'https://127.0.0.1/flash/')"
    [[ "$code" == "401" ]] || { echo "got: $code"; false; }
}

@test "/grafana/login routes to grafana (200)" {
    code="$(_through_caddy 'https://127.0.0.1/grafana/login')"
    [[ "$code" == "200" ]] || { echo "got: $code"; false; }
}

@test "/ (root) routes to jupyter (302 or 200)" {
    code="$(_through_caddy 'https://127.0.0.1/')"
    [[ "$code" == "200" || "$code" == "302" ]] || { echo "got: $code"; false; }
}

@test "unknown path routes to jupyter (200/302/404 — not 502)" {
    # Just verify the fall-through path reaches a backend, not a Caddy error.
    code="$(_through_caddy 'https://127.0.0.1/some/random/path')"
    [[ "$code" != "502" && "$code" != "503" ]] || { echo "got: $code"; false; }
}
```

Note: the `_through_caddy` helper uses `wget --no-check-certificate` via `docker compose exec caddy` because `patch_caddyfile_tls_internal` replaces ACME with internal certs. The pattern matches existing siteapp_*.bats files (now deleted). If the existing helpers `wait_siteapp_ready` / `patch_caddyfile_tls_internal` reference paths that changed, those would have been updated in Steps 5.2-5.4.

- [ ] **Step 5.7: Update `.github/workflows/pr.yml` to point at `tests/integration/`**

Edit `.github/workflows/pr.yml`:

Replace the bats filter (around lines 56-60):
```yaml
            bats:
              - 'scripts/**'
              - 'tests/**'
              - 'compose/**'
              - 'config.example.yaml'
              - 'Taskfile.yml'
```
with:
```yaml
            bats:
              - 'scripts/**'
              - 'tests/integration/**'
              - 'compose/**'
              - 'config.example.yaml'
              - 'Taskfile.yml'
```

Replace the bats step's file loop (lines 109-122):
```yaml
        run: |
          set -euo pipefail
          shopt -s nullglob
          files=()
          for f in tests/*.bats; do
              case "$(basename "$f")" in
                  test_siteapp_*.bats)
                      echo "::notice::skipping $f in CI (run locally: bats tests/$(basename "$f"))"
                      continue
                      ;;
              esac
              files+=("$f")
          done
          bats "${files[@]}"
```
with:
```yaml
        run: bats tests/integration/
```

(All four siteapp_*.bats are now deleted, so the skip-loop is obsolete. The smoke test will run in CI as part of the integration suite — slightly longer wall-clock than the old CI which skipped them entirely, but bounded to ~12 min by the single shared fake-VPS bring-up in `test_routes_smoke.bats`.)

- [ ] **Step 5.8: Update CLAUDE.md bats command examples**

Edit `CLAUDE.md`. Replace lines 49-51:
```
bats tests/test_siteapp_auth.bats tests/test_siteapp_routing.bats \
       tests/test_siteapp_safety.bats tests/test_siteapp_uploads.bats
```
with:
```
bats tests/integration/test_routes_smoke.bats   # Caddy routing smoke
# For siteapp behavior tests (auth, safety, uploads), run service e2e:
cd services/siteapp && uv run pytest tests/e2e/
```

Also update lines 30-31 (siteapp routing/auth/upload/safety) to mention the new e2e location:
```
- **siteapp behavior tests (`services/siteapp/tests/e2e/`) are NOT run in CI's siteapp workflow unless `services/siteapp/**` changed.** If you touch siteapp routing/auth/upload/safety, the pr-siteapp workflow exercises them automatically.
```

- [ ] **Step 5.9: Run the local bats integration suite**

Run:
```bash
bats tests/integration/
```
Expected: all surviving bats files pass (including the new `test_routes_smoke.bats`). Total wall-clock ~12-15 min if Docker Hub is responsive. If any bats file fails because of a missed path update, fix it.

- [ ] **Step 5.10: Commit Task 5**

Run:
```bash
git add -A
git commit -m "$(cat <<'EOF'
test(integration): consolidate routing/auth/safety bats into routes-smoke

Move tests/ → tests/integration/. Delete the four test_siteapp_*.bats files
(auth, routing, safety, uploads): routing and Caddy-edge auth gates now live
in tests/integration/test_routes_smoke.bats (single fake-VPS bring-up,
~10 assertions); behavior tests (HTML escape, path traversal, upload
semantics) moved to services/siteapp/tests/e2e/.

CI's verify job and the new pr-siteapp/pr-flasher workflows all updated for
the new paths. CLAUDE.md updated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Add `pr-platform.yml` + reduce `pr.yml` to stub

**Goal:** Move platform integration testing from `pr.yml`'s `verify` job to a dedicated `pr-platform.yml` with label-gating for release PRs. Replace `pr.yml`'s `verify` with a no-op stub so branch protection's existing required check stays satisfied until the operator updates it (post-merge).

**Files:**
- Create: `.github/workflows/pr-platform.yml`
- Modify: `.github/workflows/pr.yml` (gut down to a single no-op `verify` job)

- [ ] **Step 6.1: Create `pr-platform.yml`**

Create `.github/workflows/pr-platform.yml`:
```yaml
name: pr-platform

on:
  pull_request:
    types: [opened, synchronize, reopened, labeled]

concurrency:
  group: pr-platform-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  platform:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4

      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'compose/**'
              - 'scripts/**'
              - 'tests/integration/**'
              - 'config.example.yaml'
              - 'Taskfile.yml'
              - '.github/workflows/pr-platform.yml'
            shell:
              - 'scripts/**/*.sh'

      - id: gate
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            if ${{ contains(github.event.pull_request.labels.*.name, 'run-integration') }}; then
              echo "run=true" >> "$GITHUB_OUTPUT"
              echo "::notice::release-please PR with 'run-integration' label — running full bats integration"
            else
              echo "run=false" >> "$GITHUB_OUTPUT"
              echo "::notice::release-please PR — bats integration skipped. Apply 'run-integration' to opt in."
            fi
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi

      - name: shellcheck
        if: steps.gate.outputs.run == 'true' && steps.changed.outputs.shell == 'true'
        run: |
          sudo apt-get update
          sudo apt-get install -y shellcheck
          shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh

      - name: install Task
        if: steps.gate.outputs.run == 'true'
        uses: arduino/setup-task@v2
        with:
          version: 3.x
          repo-token: ${{ secrets.GITHUB_TOKEN }}

      - name: install yq v4
        if: steps.gate.outputs.run == 'true'
        run: |
          sudo wget -q https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq
          sudo chmod +x /usr/local/bin/yq
          yq --version

      - name: install bats
        if: steps.gate.outputs.run == 'true'
        uses: bats-core/bats-action@3.0.1

      - name: bats integration
        if: steps.gate.outputs.run == 'true'
        timeout-minutes: 20
        run: bats tests/integration/
```

- [ ] **Step 6.2: Reduce `pr.yml` to a stub `verify` job**

Replace `.github/workflows/pr.yml` entirely with:
```yaml
name: PR

# Stub workflow preserving the legacy `verify` required check while branch
# protection points at it. Real CI work moved to pr-{siteapp,flasher,platform}.yml.
#
# Removal sequence:
#   1. Operator updates branch protection: remove `verify`, add
#      `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`.
#   2. PR 2 of the per-service-isolation migration deletes this file.

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

concurrency:
  group: pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  pr-title:
    name: Semantic Pull Request
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v6
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            chore
            docs
            refactor
            test
            perf
            build
            ci
            revert
          requireScope: false
          subjectPattern: ^.+$

  verify:
    name: verify
    runs-on: ubuntu-latest
    steps:
      - run: echo "verify is a stub — real CI runs in pr-siteapp / pr-flasher / pr-platform"
```

Note: `pr-title` stays in this file because branch protection requires it and it's cheap to keep here rather than spawn a new workflow file just for it. (Could be extracted into its own `pr-title.yml`, but it isn't load-bearing for the migration.)

- [ ] **Step 6.3: YAML syntax sanity check**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-platform.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr.yml'))"
```
Expected: both succeed.

- [ ] **Step 6.4: Commit Task 6**

Run:
```bash
git add .github/workflows/pr-platform.yml .github/workflows/pr.yml
git commit -m "$(cat <<'EOF'
ci: add pr-platform.yml, reduce pr.yml to stub

pr-platform.yml owns the slimmed fake-VPS bats integration suite. Path-
gated by dorny/paths-filter@v3; release-please PRs default to skip (opt
in via 'run-integration' label) — the real integration is the actual VPS
deploy in release-please.yml.

pr.yml is now a stub keeping the legacy 'verify' required check alive
until the operator updates branch protection. PR 2 of this migration
deletes pr.yml entirely.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Multi-component release-please manifest

**Goal:** Switch release-please from one shared component (`lab-bridge` at version `0.3.1` covering both apps) to three independent components (`siteapp`, `flasher`, `platform`), each with its own tag and changelog. Update `release-please.yml` to build/deploy per component.

**Files:**
- Modify: `release-please-config.json` (full rewrite)
- Modify: `.release-please-manifest.json` (full rewrite)
- Create: `compose/VERSION`
- Create: `services/siteapp/CHANGELOG.md` (empty stub)
- Create: `services/flasher/CHANGELOG.md` (empty stub)
- Modify: `.github/workflows/release-please.yml` (full restructure)

- [ ] **Step 7.1: Create `compose/VERSION`**

Create `compose/VERSION`:
```
0.3.1 # x-release-please-version
```
(Single line, with the annotation comment that release-please's `generic` updater recognises.)

- [ ] **Step 7.2: Create empty CHANGELOG files per service**

Create `services/siteapp/CHANGELOG.md`:
```markdown
# Changelog
```

Create `services/flasher/CHANGELOG.md`:
```markdown
# Changelog
```

(release-please appends release entries on subsequent releases.)

- [ ] **Step 7.3: Replace `release-please-config.json`**

Overwrite `release-please-config.json` with:
```json
{
  "packages": {
    "services/siteapp": {
      "package-name": "siteapp",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [
        { "type": "generic", "path": "VERSION" }
      ]
    },
    "services/flasher": {
      "package-name": "flasher",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [
        { "type": "generic", "path": "VERSION" }
      ]
    },
    ".": {
      "package-name": "platform",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [
        { "type": "generic", "path": "compose/VERSION" }
      ],
      "exclude-paths": ["services/siteapp", "services/flasher"]
    }
  },
  "changelog-sections": [
    { "type": "feat",     "section": "Features"      },
    { "type": "fix",      "section": "Bug Fixes"     },
    { "type": "perf",     "section": "Performance"   },
    { "type": "revert",   "section": "Reverts"       },
    { "type": "chore",    "section": "Chores",        "hidden": true },
    { "type": "docs",     "section": "Documentation", "hidden": true },
    { "type": "refactor", "section": "Refactoring",   "hidden": true },
    { "type": "test",     "section": "Tests",         "hidden": true },
    { "type": "build",    "section": "Build",         "hidden": true },
    { "type": "ci",       "section": "CI",            "hidden": true }
  ]
}
```

- [ ] **Step 7.4: Replace `.release-please-manifest.json`**

Overwrite `.release-please-manifest.json` with:
```json
{
  "services/siteapp": "0.3.1",
  "services/flasher": "0.3.1",
  ".": "0.3.1"
}
```

- [ ] **Step 7.5: Rewrite `.github/workflows/release-please.yml`**

The new workflow has four jobs:
1. `release-please` — runs the multi-component release-please action.
2. `release-build-siteapp` — if siteapp released, build/push siteapp image + deploy.
3. `release-build-flasher` — if flasher released, build/push flasher image + deploy.
4. `release-platform` — if platform released, deploy without rebuilding images.

A multi-component release may trigger 1, 2, or 3 of jobs 2-4 in parallel. Each runs `deploy.sh` on the VPS — idempotent.

Replace `.github/workflows/release-please.yml` entirely with:
```yaml
name: release-please

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      rollback_to:
        description: 'Component-prefixed tag to redeploy (e.g. siteapp-v0.4.1 or platform-v0.5.0). Leave empty for a normal release-please run.'
        required: false

concurrency:
  group: release-please-main
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write
  id-token: write
  attestations: write
  packages: write

jobs:
  release-please:
    name: release-please
    if: github.event_name == 'push' || github.event.inputs.rollback_to == ''
    runs-on: ubuntu-latest
    outputs:
      siteapp_released: ${{ steps.rp.outputs['services/siteapp--release_created'] }}
      siteapp_tag:      ${{ steps.rp.outputs['services/siteapp--tag_name'] }}
      siteapp_version:  ${{ steps.rp.outputs['services/siteapp--version'] }}
      flasher_released: ${{ steps.rp.outputs['services/flasher--release_created'] }}
      flasher_tag:      ${{ steps.rp.outputs['services/flasher--tag_name'] }}
      flasher_version:  ${{ steps.rp.outputs['services/flasher--version'] }}
      platform_released: ${{ steps.rp.outputs['.--release_created'] }}
      platform_tag:      ${{ steps.rp.outputs['.--tag_name'] }}
      platform_version:  ${{ steps.rp.outputs['.--version'] }}
    steps:
      - id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}

      - id: rp
        uses: googleapis/release-please-action@v5
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
          token: ${{ steps.app-token.outputs.token }}

  release-build-siteapp:
    name: release-build-siteapp
    needs: release-please
    if: |
      (github.event_name == 'push' && needs.release-please.outputs.siteapp_released == 'true')
      || (github.event_name == 'workflow_dispatch' && startsWith(github.event.inputs.rollback_to, 'siteapp-v'))
    runs-on: ubuntu-latest
    steps:
      - name: resolve ref
        id: ref
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            tag="${{ github.event.inputs.rollback_to }}"
            mode=rollback
          else
            tag="${{ needs.release-please.outputs.siteapp_tag }}"
            mode=release
          fi
          version="${tag#siteapp-v}"
          echo "tag=$tag"           >> "$GITHUB_OUTPUT"
          echo "version=$version"   >> "$GITHUB_OUTPUT"
          echo "mode=$mode"         >> "$GITHUB_OUTPUT"
          echo "image=ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp:$version" >> "$GITHUB_OUTPUT"

      - uses: actions/checkout@v4
        with:
          ref: ${{ steps.ref.outputs.tag }}

      - name: log in to GHCR
        if: steps.ref.outputs.mode == 'release'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: set up buildx
        if: steps.ref.outputs.mode == 'release'
        uses: docker/setup-buildx-action@v3

      - name: build & push siteapp image
        if: steps.ref.outputs.mode == 'release'
        id: build
        uses: docker/build-push-action@v6
        with:
          context: services/siteapp
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ${{ steps.ref.outputs.image }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: attest siteapp build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true

      - name: deploy + verify
        uses: ./.github/actions/deploy-stack
        with:
          vps_host:              ${{ vars.VPS_HOST }}
          vps_ssh_user:          ${{ vars.VPS_SSH_USER }}
          vps_ssh_key:           ${{ secrets.VPS_SSH_KEY }}
          jupyter_password_hash: ${{ secrets.JUPYTER_PASSWORD_HASH }}
          admin_password_hash:   ${{ secrets.ADMIN_PASSWORD_HASH }}
          grafana_password:      ${{ secrets.GRAFANA_ADMIN_PASSWORD }}
          agent_upload_token:    ${{ secrets.AGENT_UPLOAD_TOKEN }}
          verify_siteapp_version: ${{ steps.ref.outputs.version }}

  release-build-flasher:
    name: release-build-flasher
    needs: release-please
    if: |
      (github.event_name == 'push' && needs.release-please.outputs.flasher_released == 'true')
      || (github.event_name == 'workflow_dispatch' && startsWith(github.event.inputs.rollback_to, 'flasher-v'))
    runs-on: ubuntu-latest
    steps:
      - name: resolve ref
        id: ref
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            tag="${{ github.event.inputs.rollback_to }}"
            mode=rollback
          else
            tag="${{ needs.release-please.outputs.flasher_tag }}"
            mode=release
          fi
          version="${tag#flasher-v}"
          echo "tag=$tag"           >> "$GITHUB_OUTPUT"
          echo "version=$version"   >> "$GITHUB_OUTPUT"
          echo "mode=$mode"         >> "$GITHUB_OUTPUT"
          echo "image=ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher:$version" >> "$GITHUB_OUTPUT"

      - uses: actions/checkout@v4
        with:
          ref: ${{ steps.ref.outputs.tag }}

      - name: log in to GHCR
        if: steps.ref.outputs.mode == 'release'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: set up buildx
        if: steps.ref.outputs.mode == 'release'
        uses: docker/setup-buildx-action@v3

      - name: build & push flasher image
        if: steps.ref.outputs.mode == 'release'
        id: build
        uses: docker/build-push-action@v6
        with:
          context: services/flasher
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ${{ steps.ref.outputs.image }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: attest flasher build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true

      - name: deploy + verify
        uses: ./.github/actions/deploy-stack
        with:
          vps_host:              ${{ vars.VPS_HOST }}
          vps_ssh_user:          ${{ vars.VPS_SSH_USER }}
          vps_ssh_key:           ${{ secrets.VPS_SSH_KEY }}
          jupyter_password_hash: ${{ secrets.JUPYTER_PASSWORD_HASH }}
          admin_password_hash:   ${{ secrets.ADMIN_PASSWORD_HASH }}
          grafana_password:      ${{ secrets.GRAFANA_ADMIN_PASSWORD }}
          agent_upload_token:    ${{ secrets.AGENT_UPLOAD_TOKEN }}

  release-platform:
    name: release-platform
    needs: release-please
    if: |
      (github.event_name == 'push' && needs.release-please.outputs.platform_released == 'true')
      || (github.event_name == 'workflow_dispatch' && startsWith(github.event.inputs.rollback_to, 'platform-v'))
    runs-on: ubuntu-latest
    steps:
      - name: resolve ref
        id: ref
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            tag="${{ github.event.inputs.rollback_to }}"
          else
            tag="${{ needs.release-please.outputs.platform_tag }}"
          fi
          echo "tag=$tag" >> "$GITHUB_OUTPUT"

      - uses: actions/checkout@v4
        with:
          ref: ${{ steps.ref.outputs.tag }}

      - name: deploy
        uses: ./.github/actions/deploy-stack
        with:
          vps_host:              ${{ vars.VPS_HOST }}
          vps_ssh_user:          ${{ vars.VPS_SSH_USER }}
          vps_ssh_key:           ${{ secrets.VPS_SSH_KEY }}
          jupyter_password_hash: ${{ secrets.JUPYTER_PASSWORD_HASH }}
          admin_password_hash:   ${{ secrets.ADMIN_PASSWORD_HASH }}
          grafana_password:      ${{ secrets.GRAFANA_ADMIN_PASSWORD }}
          agent_upload_token:    ${{ secrets.AGENT_UPLOAD_TOKEN }}
```

Note: the three `release-*` jobs share a deploy sub-step. Rather than duplicate ~30 lines of rsync/SSH/healthcheck, extract a composite action.

- [ ] **Step 7.6: Create composite action `.github/actions/deploy-stack/action.yml`**

Create `.github/actions/deploy-stack/action.yml`:
```yaml
name: 'Deploy stack to VPS'
description: 'rsync + docker compose up on the VPS, with optional version-equality healthcheck'

inputs:
  vps_host:              { required: true }
  vps_ssh_user:          { required: true }
  vps_ssh_key:           { required: true }
  jupyter_password_hash: { required: true }
  admin_password_hash:   { required: true }
  grafana_password:      { required: true }
  agent_upload_token:    { required: true }
  verify_siteapp_version:
    description: "When set, assert server-info.version == this value after deploy. Omit for platform/flasher releases."
    required: false
    default: ""

runs:
  using: composite
  steps:
    - name: install rsync, envsubst, yq
      shell: bash
      run: |
        sudo apt-get update
        sudo apt-get install -y rsync gettext-base
        sudo wget -q https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq
        sudo chmod +x /usr/local/bin/yq

    - name: load SSH key
      uses: webfactory/ssh-agent@v0.9.0
      with:
        ssh-private-key: ${{ inputs.vps_ssh_key }}

    - name: render CI config.yaml
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
        VPS_SSH_USER: ${{ inputs.vps_ssh_user }}
        JUPYTER_PASSWORD_HASH: ${{ inputs.jupyter_password_hash }}
        ADMIN_PASSWORD_HASH: ${{ inputs.admin_password_hash }}
      run: |
        mkdir -p compose/grafana compose/siteapp
        envsubst < compose/config.ci.yaml.tmpl > config.ci.rendered.yaml
        printf '%s' "${{ inputs.grafana_password }}" > compose/grafana/admin_password
        printf '%s' "${{ inputs.agent_upload_token }}" > compose/siteapp/agent_upload_token
        chmod 0600 compose/grafana/admin_password compose/siteapp/agent_upload_token

    - name: deploy to VPS (stack-only)
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
        VPS_SSH_USER: ${{ inputs.vps_ssh_user }}
        LDS_CONFIG: ${{ github.workspace }}/config.ci.rendered.yaml
        LDS_STACK_ONLY: '1'
        LDS_REQUIRE_VAULT: '1'
        LDS_SSH_OPTS: '-o StrictHostKeyChecking=accept-new'
      run: bash scripts/deploy.sh

    - name: verify deployed version
      if: inputs.verify_siteapp_version != ''
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
      run: |
        set -euo pipefail
        for i in $(seq 1 30); do
          body="$(curl -sk "https://$VPS_HOST/api/public/server-info")" || true
          if echo "$body" | jq -e --arg v "${{ inputs.verify_siteapp_version }}" '.version == $v' >/dev/null; then
            echo "verified: server reports siteapp version ${{ inputs.verify_siteapp_version }}"
            exit 0
          fi
          sleep 2
        done
        echo "::error::server-info did not report expected version ${{ inputs.verify_siteapp_version }} after 60s"
        echo "last body: $body"
        exit 1
```

For flasher and platform releases, `verify_siteapp_version` is omitted (defaults to `""`) → the version-equality assertion is skipped. The deploy.sh internal healthcheck loop still asserts the stack came up cleanly (200/401 on all expected routes).

- [ ] **Step 7.7: YAML syntax sanity check**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/release-please.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/actions/deploy-stack/action.yml'))"
python -c "import json; json.load(open('release-please-config.json'))"
python -c "import json; json.load(open('.release-please-manifest.json'))"
```
Expected: all succeed.

- [ ] **Step 7.8: Commit Task 7**

Run:
```bash
git add -A
git commit -m "$(cat <<'EOF'
chore(release-please): switch to multi-component manifest

Three components now release independently:
  - siteapp     (services/siteapp/), tags siteapp-v<X.Y.Z>
  - flasher     (services/flasher/), tags flasher-v<X.Y.Z>
  - platform    (everything else),   tags platform-v<X.Y.Z>

release-please.yml split into three sibling release-build-* jobs gated on
the matching component's outputs[...--release_created]. Shared deploy
logic extracted into .github/actions/deploy-stack (composite action).
Version-equality healthcheck runs only for siteapp releases (server-info
exposes siteapp's version; flasher/platform releases use deploy.sh's
own route-reachability healthcheck).

Starting versions: all three at 0.3.1 for continuity; they diverge
naturally from the next release.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Open PR 1 with operator checklist

**Goal:** Push the branch, open PR 1, watch the new workflows go green.

- [ ] **Step 8.1: Push branch**

Run:
```bash
git push -u origin chore/per-service-isolation
```

- [ ] **Step 8.2: Open PR 1 via gh CLI**

Run:
```bash
gh pr create --title "chore: per-service isolation (services/, multi-component release-please, parallel CI)" --body "$(cat <<'EOF'
## Summary
Restructures the repo for per-service isolation as more services land:

- `compose/{siteapp,flasher}/` → `services/{siteapp,flasher}/`
- release-please switched from 1 shared component to 3 independent components (siteapp, flasher, platform); independent tags like `siteapp-v0.3.2`.
- `pr.yml`'s single `verify` job → three parallel workflows: `pr-siteapp.yml`, `pr-flasher.yml`, `pr-platform.yml`. Each always-triggers, gates internally via `dorny/paths-filter@v3`.
- New per-service pytest e2e harnesses (`services/<name>/tests/e2e/`) — siteapp + stub fixtures; flasher + stub-SerialHop.
- Four `test_siteapp_*.bats` consolidated into `tests/integration/test_routes_smoke.bats` (Caddy routing only, one fake-VPS bring-up).
- Release-PR opt-in: `pr-platform` skips bats for `release-please--*` head refs unless labelled `run-integration`.

See `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` for full design.

## Test plan

- [ ] PR CI green: `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`, `verify` (stub).
- [ ] Inspect `pr-siteapp` log — confirms e2e harness spins siteapp container and runs ~12 tests.
- [ ] Inspect `pr-flasher` log — confirms stub-SerialHop builds, flasher container starts, ~6 tests pass.
- [ ] Inspect `pr-platform` log — confirms `tests/integration/` bats run including new `test_routes_smoke.bats`.
- [ ] Locally re-run `bats tests/integration/` to confirm bats still works.

## **Operator action required immediately after merge**

Update branch protection on `main` in the GitHub UI:

1. Repo settings → Branches → `main` → Branch protection rule.
2. **Remove required check:** `verify`
3. **Add required checks:** `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`
4. Save.

Until this is done, `verify` continues to pass (stub job) and the new workflows run in observation mode. PR 2 then deletes the stub `verify` (`pr.yml`).

## First release-please run after merge

The first `release-please` run after this PR merges scans commits since `v0.3.1` and may open multiple release PRs at once (one per component with new commits since the cut-over). Read carefully; revert this PR if anything looks wrong (no images are shipped until a release PR is squash-merged).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR URL printed; the new workflows trigger.

- [ ] **Step 8.3: Watch CI**

Run:
```bash
gh pr checks --watch
```
Expected: all three new workflows + `verify` (stub) + `pr-title` pass within ~15 min. If anything fails, read the log and fix in a follow-up commit on this branch.

**Do not merge yet — wait for human review of the spec and plan completion.**

---

## PR 2 — Cleanup

### Task 9: Delete the stub `pr.yml`

**Goal:** After PR 1 is merged AND the operator has updated branch protection, delete the stub `verify` job entirely.

**Files:**
- Delete: `.github/workflows/pr.yml`
- Modify: nothing else

**Pre-requisite:** PR 1 merged. Operator confirmed branch protection updated: required checks are `pr-title / Semantic Pull Request`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`. **Verify this before starting Task 9.**

If `pr-title` was kept inside `pr.yml` (per Step 6.2 note), it must be extracted before `pr.yml` can be deleted. The branch protection still requires `pr-title / Semantic Pull Request`, so the action must continue to run somewhere.

- [ ] **Step 9.1: Confirm pre-requisite**

Ask the operator to confirm branch protection's required check list. If `pr-title / Semantic Pull Request` is among them, proceed. Stop if not.

- [ ] **Step 9.2: Create branch + extract `pr-title` into its own workflow**

Run:
```bash
git checkout main && git pull
git checkout -b chore/remove-pr-yml-stub
```

Create `.github/workflows/pr-title.yml`:
```yaml
name: pr-title

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  contents: read
  pull-requests: read

jobs:
  pr-title:
    name: Semantic Pull Request
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v6
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            chore
            docs
            refactor
            test
            perf
            build
            ci
            revert
          requireScope: false
          subjectPattern: ^.+$
```

Note: the required check name remains `pr-title / Semantic Pull Request` (workflow name `pr-title`, job display name `Semantic Pull Request`) — matches the previous configuration verbatim, so branch protection doesn't need to be touched again.

- [ ] **Step 9.3: Delete `pr.yml`**

Run:
```bash
git rm .github/workflows/pr.yml
```

- [ ] **Step 9.4: Commit Task 9**

Run:
```bash
git add .github/workflows/pr-title.yml
git commit -m "$(cat <<'EOF'
ci: remove pr.yml stub, extract pr-title into its own workflow

PR 1 of the per-service-isolation migration left pr.yml as a no-op
'verify' stub so branch protection could be updated without a merge-
blocked window. With branch protection now pointing at the three new
required checks, pr.yml is no longer needed.

pr-title (Semantic Pull Request) extracted into pr-title.yml so the
required check 'pr-title / Semantic Pull Request' continues to run.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 9.5: Push and open PR 2**

Run:
```bash
git push -u origin chore/remove-pr-yml-stub
gh pr create --title "ci: remove pr.yml stub" --body "$(cat <<'EOF'
## Summary
Cleanup after PR 1 of the per-service-isolation migration. The stub `verify` job in `pr.yml` is no longer needed now that branch protection points at `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`.

`pr-title` extracted into its own workflow so the required check `pr-title / Semantic Pull Request` continues to run.

## Test plan

- [ ] Required checks on this PR's status include `pr-title / Semantic Pull Request` + the three per-service checks. No `verify` check.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 9.6: Watch CI and merge**

Run: `gh pr checks --watch`
Expected: all required checks pass. Then squash-merge.

---

## Post-migration verification

After both PRs are merged:

- [ ] **V.1: Open a trivial docs-only PR** (e.g., typo fix in README.md). All three workflows run; each completes in <30s with success. Total wall-clock to "ready to merge": ~1 min.
- [ ] **V.2: Open a siteapp-only PR** (e.g., edit a route handler comment). `pr-siteapp` runs in full (~5 min); `pr-flasher` and `pr-platform` fast-skip.
- [ ] **V.3: Wait for release-please to open release PRs** for accumulated commits since `v0.3.1`. Expect 1-3 PRs (one per component with new commits).
- [ ] **V.4: On a release-please PR, confirm `pr-platform` shows the skip-with-notice message**. Apply label `run-integration`; verify bats integration runs.
- [ ] **V.5: Squash-merge a release PR**; confirm only the matching `release-build-*` job runs and deploys to VPS.

---

## Self-review checklist (for plan author)

- [x] Every spec section maps to at least one task (1→Task 1; 2→Task 7; 3→Tasks 4, 6; 4→Tasks 2, 3, 5; 5→Tasks 1-9).
- [x] Coverage translation table from spec → matched by Task 2 (siteapp e2e covers safety/uploads), Task 5 (routes-smoke covers routing/auth).
- [x] Type/name consistency: `STUB_FLASH_OUTCOME`, `SITEAPP_TEST_IMAGE`, `FLASHER_TEST_IMAGE`, label name `run-integration`, tag formats `<component>-v<X.Y.Z>` — used consistently.
- [x] No placeholders. Concrete code in every code step; concrete commands in every command step.

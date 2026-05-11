# `/api/public/server-info` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unauthenticated `GET /api/public/server-info` HTTPS route on siteapp that returns the chisel listen port, loki push URL, and forward-tunnel topology, so a chisel-client agent can drop `chisel_listen_port` from its local config.

**Architecture:** One new router module (`compose/siteapp/app/server_info.py`) mounted by `app/main.py`. Reads `chisel.listen_port` from a new `SITEAPP_CHISEL_LISTEN_PORT` env var (threaded through `docker-compose.yml.tmpl` from the existing `__CHISEL_LISTEN_PORT__` substitution). The loki push URL and forward-tunnel entry are module-level constants for now (the deployment topology pins them; promote to data later when a second forward target appears).

**Tech Stack:** Python 3 / FastAPI / pytest / bats-core / Docker Compose / Caddy (no Caddyfile change needed — existing `handle /api/public*` already routes).

**Spec:** `docs/superpowers/specs/2026-05-11-server-info-design.md`

---

## File Map

- **Create:**
  - `compose/siteapp/app/server_info.py` — module constants + `make_router(settings)`.
  - `compose/siteapp/tests/test_server_info.py` — pytest for the route.
  - `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` — companion client-side contract.
- **Modify:**
  - `compose/siteapp/app/config.py` — add `chisel_listen_port: int` to `Settings`, load + validate.
  - `compose/siteapp/app/main.py` — import + mount the new router.
  - `compose/siteapp/tests/conftest.py` — autouse fixture sets `SITEAPP_CHISEL_LISTEN_PORT` so existing tests still boot the app.
  - `compose/siteapp/tests/test_config.py` — boot-guard tests for the new env var.
  - `compose/docker-compose.yml.tmpl` — pass `SITEAPP_CHISEL_LISTEN_PORT` into siteapp.
  - `tests/test_render.bats` — assert the env var renders into `docker-compose.yml`.
  - `scripts/deploy.sh` — extend post-deploy probe to include `/api/public/server-info`.
  - `docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md` — one-line cross-link to the new client spec.

---

## Task 1: Thread `SITEAPP_CHISEL_LISTEN_PORT` through tests (so later tasks don't break the suite)

**Files:**
- Modify: `compose/siteapp/tests/conftest.py`

The existing tests call `load_settings()` directly or via app reload. Once Task 2 makes `SITEAPP_CHISEL_LISTEN_PORT` a required env var, every test in the suite will start failing at boot. Add an autouse fixture *before* changing `Settings`, so the suite stays green throughout the change.

- [ ] **Step 1: Add the autouse fixture**

Edit `compose/siteapp/tests/conftest.py`. Append (after the existing `_clients_file_default` fixture):

```python
@pytest.fixture(autouse=True)
def _chisel_listen_port_default(monkeypatch) -> int:
    """Set SITEAPP_CHISEL_LISTEN_PORT to a fixed test value.

    Tests that *intentionally* assert the env var is absent
    (e.g. test_chisel_listen_port_required) must call
    ``monkeypatch.delenv("SITEAPP_CHISEL_LISTEN_PORT", raising=False)``
    themselves — this autouse fixture sets it on every test.
    """
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "8080")
    return 8080
```

- [ ] **Step 2: Run the full test suite and confirm no regression**

Run: `cd compose/siteapp && pytest -q`
Expected: same count as before (currently 169/169 per recent PR), all passing — the new fixture sets an env var nothing reads yet, so it's a no-op.

- [ ] **Step 3: Commit**

```bash
git add compose/siteapp/tests/conftest.py
git commit -m "test(siteapp): autouse fixture pre-sets SITEAPP_CHISEL_LISTEN_PORT"
```

---

## Task 2: Add `chisel_listen_port` to `Settings` (boot guard first, then implementation)

**Files:**
- Modify: `compose/siteapp/app/config.py`
- Modify: `compose/siteapp/tests/test_config.py`

- [ ] **Step 1: Write the failing boot-guard test**

Append to `compose/siteapp/tests/test_config.py`:

```python
def test_chisel_listen_port_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_CHISEL_LISTEN_PORT", raising=False)
    with pytest.raises(RuntimeError, match="SITEAPP_CHISEL_LISTEN_PORT"):
        load_settings()


def test_chisel_listen_port_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "9090")
    settings = load_settings()
    assert settings.chisel_listen_port == 9090


def test_chisel_listen_port_non_integer_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "not-a-number")
    with pytest.raises(ValueError):
        load_settings()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `cd compose/siteapp && pytest tests/test_config.py::test_chisel_listen_port_required tests/test_config.py::test_chisel_listen_port_stored tests/test_config.py::test_chisel_listen_port_non_integer_raises -v`
Expected: FAIL (`AttributeError: 'Settings' object has no attribute 'chisel_listen_port'` or similar).

- [ ] **Step 3: Implement the Settings change**

Edit `compose/siteapp/app/config.py`. In the `Settings` dataclass (currently `compose/siteapp/app/config.py:9-15`), add the new field. The dataclass is `frozen=True` and uses field-default ordering, so place it after the other required fields and before defaulted ones:

```python
@dataclass(frozen=True)
class Settings:
    site_data: Path
    agent_upload_token: str
    clients_file: Path
    chisel_listen_port: int
    max_upload_mb_doc: int = 10
    max_upload_mb_agent: int = 100
    csrf_secret: str = ""
```

In `load_settings()`, after the existing `clients_file` loading block (around `compose/siteapp/app/config.py:36-41`), insert:

```python
    port_env = os.environ.get("SITEAPP_CHISEL_LISTEN_PORT")
    if not port_env:
        raise RuntimeError("SITEAPP_CHISEL_LISTEN_PORT env var is required")
    # int() raises ValueError on garbage like "abc"; surface as a boot crash —
    # a misrendered template should never produce a "port 0" runtime fallback.
    chisel_listen_port = int(port_env)
```

Then pass it into the `Settings(...)` constructor at the bottom of `load_settings()`:

```python
    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        clients_file=clients_file,
        chisel_listen_port=chisel_listen_port,
        csrf_secret=csrf,
    )
```

- [ ] **Step 4: Run the new tests and the full suite**

Run: `cd compose/siteapp && pytest tests/test_config.py -v && pytest -q`
Expected: the three new tests pass; full suite stays green (the autouse fixture from Task 1 sets `SITEAPP_CHISEL_LISTEN_PORT=8080` for every other test).

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/config.py compose/siteapp/tests/test_config.py
git commit -m "feat(siteapp): Settings.chisel_listen_port from env, fail-fast at boot"
```

---

## Task 3: Add the `server_info` module + route (TDD)

**Files:**
- Create: `compose/siteapp/app/server_info.py`
- Create: `compose/siteapp/tests/test_server_info.py`

- [ ] **Step 1: Write the failing route test**

Create `compose/siteapp/tests/test_server_info.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch) -> TestClient:
    """Boot the FastAPI app with the standard test env."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    # SITEAPP_CHISEL_LISTEN_PORT + SITEAPP_CLIENTS_FILE come from autouse fixtures.
    from importlib import reload

    import app.main
    reload(app.main)
    return TestClient(app.main.app)


def test_server_info_returns_expected_shape(app_client: TestClient) -> None:
    r = app_client.get("/api/public/server-info")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "chisel": {"listen_port": 8080},
        "loki": {"push_url": "http://127.0.0.1:3100/loki/api/v1/push"},
        "forward_tunnels": [
            {"name": "loki", "local": "127.0.0.1:3100", "remote": "loki:3100"}
        ],
    }


def test_server_info_reflects_configured_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The listen_port in the response tracks SITEAPP_CHISEL_LISTEN_PORT, not a constant."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "9090")
    from importlib import reload

    import app.main
    reload(app.main)
    client = TestClient(app.main.app)

    r = client.get("/api/public/server-info")
    assert r.status_code == 200
    assert r.json()["chisel"] == {"listen_port": 9090}


def test_server_info_requires_no_auth(app_client: TestClient) -> None:
    """Regression guard: an accidental Depends(...) on the route would break the
    'agent can fetch this before holding any credential' guarantee."""
    r = app_client.get("/api/public/server-info")  # no Authorization header
    assert r.status_code == 200
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run: `cd compose/siteapp && pytest tests/test_server_info.py -v`
Expected: FAIL — route is unmounted, so the request returns 404 (or the test setup fails on the import path).

- [ ] **Step 3: Implement `server_info.py`**

Create `compose/siteapp/app/server_info.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from app.config import Settings

# Forward-tunnel topology is pinned by the compose stack today:
# - chisel-users.json grants every client `loki:3100` as a forward target
#   (see compose/chisel-users.json.tmpl and scripts/lib/render.sh:41).
# - The agent opens a `-L 127.0.0.1:3100:loki:3100` tunnel and POSTs to
#   the local end of it.
# If you change EITHER the chisel allow-list OR the loki service name/port,
# update these constants in lockstep. Promote to config.yaml when a second
# forward target appears.
LOKI_PUSH_URL = "http://127.0.0.1:3100/loki/api/v1/push"
FORWARD_TUNNELS: list[dict[str, str]] = [
    {"name": "loki", "local": "127.0.0.1:3100", "remote": "loki:3100"},
]


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/public/server-info")
    def get_server_info() -> dict:
        return {
            "chisel": {"listen_port": settings.chisel_listen_port},
            "loki": {"push_url": LOKI_PUSH_URL},
            "forward_tunnels": FORWARD_TUNNELS,
        }

    return router
```

- [ ] **Step 4: Mount the router in `main.py`**

Edit `compose/siteapp/app/main.py`. Add the import (alphabetical with the others, after the `public_clients` import on line 11):

```python
from app.public_clients import make_router as make_public_clients_router
from app.server_info import make_router as make_server_info_router
```

Mount it next to the other routers (after `make_public_clients_router(settings)` on line 26):

```python
app.include_router(make_public_clients_router(settings))
app.include_router(make_server_info_router(settings))
```

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `cd compose/siteapp && pytest tests/test_server_info.py -v`
Expected: all three tests PASS.

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `cd compose/siteapp && pytest -q`
Expected: all tests pass (count = previous total + 3 new).

- [ ] **Step 7: Commit**

```bash
git add compose/siteapp/app/server_info.py compose/siteapp/app/main.py compose/siteapp/tests/test_server_info.py
git commit -m "feat(siteapp): GET /api/public/server-info — chisel port + loki/tunnel topology"
```

---

## Task 4: Thread `__CHISEL_LISTEN_PORT__` into the siteapp compose service (bats first)

**Files:**
- Modify: `tests/test_render.bats`
- Modify: `compose/docker-compose.yml.tmpl`

- [ ] **Step 1: Write the failing bats assertion**

Edit `tests/test_render.bats`. The existing test at line 8, `"render_compose: substitutes image, paths, password_hash, and chisel port"`, already renders the full compose file. Add one assertion to it (insert after the `__port=8080__` assertion around line 22):

```bash
    [[ "$output" == *"SITEAPP_CHISEL_LISTEN_PORT: 8080"* ]]
```

The final block of that test should read:

```bash
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: quay.io/jupyter/scipy-notebook:2026-04-20"* ]]
    [[ "$output" == *"image: jpillora/chisel:1.10.1"* ]]
    [[ "$output" == *"/srv/jupyterlab/work:/home/jovyan/work"* ]]
    [[ "$output" == *"--port=8080"* ]]
    [[ "$output" == *'"8080:8080"'* ]]
    [[ "$output" == *"SITEAPP_CHISEL_LISTEN_PORT: 8080"* ]]
    [[ "$output" == *"--ServerApp.password=sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"* ]]
    # No leftover placeholders. Match `__NAME__` (bracketed both sides) to
    # avoid false positives on Docker secret env var suffixes like `__FILE`.
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
```

- [ ] **Step 2: Run the bats test to confirm it fails**

Run: `bats tests/test_render.bats -f "render_compose: substitutes"`
Expected: FAIL — the rendered compose file does not yet contain `SITEAPP_CHISEL_LISTEN_PORT: 8080`.

- [ ] **Step 3: Add the env var to the compose template**

Edit `compose/docker-compose.yml.tmpl`. In the `siteapp.environment` block (currently lines 72-74):

```yaml
  siteapp:
    image: __SITEAPP_IMAGE__
    restart: unless-stopped
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_CHISEL_LISTEN_PORT: __CHISEL_LISTEN_PORT__
```

No changes to `scripts/lib/render.sh` are needed — `render_compose` already substitutes `__CHISEL_LISTEN_PORT__` (see `scripts/lib/render.sh:16`).

- [ ] **Step 4: Run the bats test to confirm it passes**

Run: `bats tests/test_render.bats -f "render_compose: substitutes"`
Expected: PASS.

- [ ] **Step 5: Run the full bats suite to confirm no regression**

Run: `bats tests/test_render.bats`
Expected: all tests in the file pass.

- [ ] **Step 6: Commit**

```bash
git add compose/docker-compose.yml.tmpl tests/test_render.bats
git commit -m "feat(compose): pass SITEAPP_CHISEL_LISTEN_PORT into siteapp service"
```

---

## Task 5: Include `/api/public/server-info` in the post-deploy health check

**Files:**
- Modify: `scripts/deploy.sh`

- [ ] **Step 1: Add the new probe**

Edit `scripts/deploy.sh`. The existing health-check loop runs from line 90 to line 121. Two edits:

1. Add a local variable to the declaration on line 92:

```bash
        local i jupyter_status grafana_status docs_status download_status admin_status static_status public_status server_info_status
```

2. Inside the `for` loop, after the existing `public_status=` line (around line 106), add:

```bash
            # /api/public/server-info publishes the chisel listen port + loki/tunnel
            # topology. A non-200 means the env var didn't reach siteapp or the
            # router wasn't mounted. Probed alongside /api/public/health so a
            # broken render of SITEAPP_CHISEL_LISTEN_PORT fails the deploy.
            server_info_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/api/public/server-info" || true)"
```

3. Add the new status to the success condition (the `if [[ ... ]]; then` block on lines 108-114). The full updated block should read:

```bash
            if [[ "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "200" ]] \
                && [[ "$docs_status" == "200" ]] \
                && [[ "$download_status" == "200" ]] \
                && [[ "$admin_status" == "401" ]] \
                && [[ "$static_status" == "200" ]] \
                && [[ "$public_status" == "200" ]] \
                && [[ "$server_info_status" == "200" ]]; then
                log "deployed: jupyter $jupyter_status, grafana $grafana_status, docs $docs_status, download $download_status, admin $admin_status, static $static_status, public $public_status, server_info $server_info_status"
                return 0
            fi
```

4. Update the timeout warning on line 120 to include the new field:

```bash
        warn "health check timed out (jupyter:$jupyter_status grafana:$grafana_status docs:$docs_status download:$download_status admin:$admin_status static:$static_status public:$public_status server_info:$server_info_status). Check: task logs"
```

- [ ] **Step 2: Sanity-check syntax**

Run: `bash -n scripts/deploy.sh`
Expected: exit 0, no output.

- [ ] **Step 3: Run the bats deploy suite**

Run: `bats tests/test_deploy.bats`
Expected: all tests pass (the deploy suite either mocks curl or skips network — no real VPS needed). If a test asserts the exact form of the health-check log line, update its expected string to include `server_info $server_info_status`.

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): include /api/public/server-info in post-deploy health check"
```

---

## Task 6: Write the client-side spec

**Files:**
- Create: `docs/superpowers/specs/2026-05-11-server-info-client-spec.md`
- Modify: `docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md`

- [ ] **Step 1: Create the client spec**

Create `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` with this content:

````markdown
# Lab-bridge `/api/public/server-info` — client contract

Status: stable
Date: 2026-05-11
Audience: developers of the lab-device agent (chisel client).
Pairs with: `2026-05-11-server-info-design.md` (server-side design — out of scope here).
Companion: `2026-04-28-chisel-client-logs-client-spec.md` (the log-shipping contract this design's `forward_tunnels[]` and `loki.push_url` feed into).

One unauthenticated HTTPS endpoint on the lab-bridge VPS. Called once at agent startup; lets the agent stop carrying `chisel_listen_port` in its local config.

## `GET /api/public/server-info`

No auth. No path or query params.

### Request

```
GET /api/public/server-info HTTP/1.1
Host: <vps-host>
```

### 200 — success

```json
{
  "chisel": {
    "listen_port": 8080
  },
  "loki": {
    "push_url": "http://127.0.0.1:3100/loki/api/v1/push"
  },
  "forward_tunnels": [
    {
      "name": "loki",
      "local": "127.0.0.1:3100",
      "remote": "loki:3100"
    }
  ]
}
```

- `chisel.listen_port` (int): the public TCP port `chisel server` listens on. Use as `<vps-host>:<chisel.listen_port>` in the `chisel client` invocation.
- `loki.push_url` (string): the application-level URL the log shipper POSTs to. Replaces the previously-hardcoded `http://127.0.0.1:3100/loki/api/v1/push`.
- `forward_tunnels` (list): one entry per chisel `-L` arg the agent should open. Today the list has exactly one entry (the loki forward tunnel). Construct the chisel arg as `<local>:<remote>` for each entry.

Future schema additions:

- `chisel.fingerprint` may appear — when present, pass to `chisel client` as `--fingerprint <value>` (host-key pinning).
- A top-level `agent` object (`{version, sha256, url, size}`) may appear — describes the currently-published Windows agent.

Both additions are purely additive; treat unknown fields permissively.

### Errors

`500` only on a server programmer error. Retry with backoff. No 4xx path.

## Agent bootstrap flow

1. Read the agent's local config: `{host, username, password, local_device_port}`. (Note: `chisel_listen_port` is **no longer** in the local config — it comes from the server.)
2. `GET https://<host>/api/public/server-info`. Cache the response for the lifetime of this chisel session.
3. `GET https://<host>/api/public/clients/{username}` with `Authorization: Bearer <password>` to get the assigned `port` and `connected` (existing endpoint, unchanged — see `2026-05-11-public-client-status-client-spec.md`).
4. Build the chisel invocation:

   ```sh
   chisel client \
       --auth <username>:<password> \
       <host>:<chisel.listen_port> \
       R:0.0.0.0:<reverse_port>:127.0.0.1:<local_device_port> \
       <forward_tunnels[0].local>:<forward_tunnels[0].remote>
   ```

5. Once chisel is up, the log shipper POSTs to `loki.push_url`.
6. On chisel reconnect after a failed dial (e.g. operator changed `chisel.listen_port`), re-fetch `/api/public/server-info` before retrying.

## Local-config migration

Remove `chisel_listen_port` from the agent's local config schema. If a stale value is present in an existing install, **prefer the server's value** and log one WARN line of the shape:

```
WARN: local config 'chisel_listen_port' is deprecated and ignored — server publishes 8080 at /api/public/server-info
```

This gives operators a clear signal that the local field can be removed without breaking anything.

## Notes

- `forward_tunnels` is a list because future deployments may add a second forward target (e.g. a metrics push gateway). Iterate it; don't index `[0]` in production code. (The example above does `[0]` only for readability.)
- The endpoint is cheap and idempotent. There's no reason to call it on every chisel poll — once at startup + once on reconnect-after-failure is enough.
- Caching headers are not set today; the agent should manage its own cache as described above.
````

- [ ] **Step 2: Add cross-link in the log-shipping client spec**

Edit `docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md`. Find the "Companion doc:" line near the top (line 6) and add a second companion reference. The block that currently reads:

```markdown
**Companion doc:** [2026-04-28-chisel-client-logs-design.md](./2026-04-28-chisel-client-logs-design.md) — server-side design and rationale. This file is the contract the client must honor.
```

becomes:

```markdown
**Companion doc:** [2026-04-28-chisel-client-logs-design.md](./2026-04-28-chisel-client-logs-design.md) — server-side design and rationale. This file is the contract the client must honor.
**See also:** [2026-05-11-server-info-client-spec.md](./2026-05-11-server-info-client-spec.md) — at startup, the agent now fetches `loki.push_url` and the forward-tunnel arg from `/api/public/server-info` instead of hardcoding them. The values match what this spec describes; the source of truth has moved.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-05-11-server-info-client-spec.md docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md
git commit -m "docs(siteapp): client-side contract for /api/public/server-info"
```

---

## Task 7: Final verification

- [ ] **Step 1: Run the full pytest suite**

Run: `cd compose/siteapp && pytest -q`
Expected: all tests pass. The count should be the previous total + 6 new (3 in `test_config.py`, 3 in `test_server_info.py`).

- [ ] **Step 2: Run the full bats suite**

Run: `bats tests/`
Expected: all tests pass.

- [ ] **Step 3: Render a compose locally and eyeball the siteapp env block**

Run:

```bash
bash -c '
    source scripts/lib/common.sh
    source scripts/lib/config.sh
    source scripts/lib/render.sh
    load_config tests/fixtures/valid_config.yaml
    TMP="$(mktemp -d)"
    render_compose compose/docker-compose.yml.tmpl "$TMP/docker-compose.yml"
    grep -A 4 "siteapp:" "$TMP/docker-compose.yml" | head -20
    rm -rf "$TMP"
'
```

Expected output includes:

```
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_CHISEL_LISTEN_PORT: 8080
```

(No leftover `__CHISEL_LISTEN_PORT__` placeholder.)

- [ ] **Step 4: Confirm the commit graph**

Run: `git log --oneline -8`
Expected (top to bottom):

```
docs(siteapp): client-side contract for /api/public/server-info
feat(deploy): include /api/public/server-info in post-deploy health check
feat(compose): pass SITEAPP_CHISEL_LISTEN_PORT into siteapp service
feat(siteapp): GET /api/public/server-info — chisel port + loki/tunnel topology
feat(siteapp): Settings.chisel_listen_port from env, fail-fast at boot
test(siteapp): autouse fixture pre-sets SITEAPP_CHISEL_LISTEN_PORT
docs(siteapp): design /api/public/server-info for agent bootstrap
…
```

- [ ] **Step 5: Open the PR (operator action; not part of the agent's autonomous work)**

Branch the work, push, and open a PR. Manual post-merge verification (operator):

1. Bump `siteapp.image` tag in `config.yaml` to the freshly-published image.
2. `task deploy` — the health-check line should include `server_info 200`.
3. `curl -sk https://<vps>/api/public/server-info | jq` — confirm the shape matches the client spec.

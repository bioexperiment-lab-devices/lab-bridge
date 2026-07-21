# Remote admin update — server-side reachability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the SerialHop agent's `POST /agent/update` and `GET /agent/update/status` reachable per lab for admins, via a siteapp proxy behind an Authelia admin-gate and a Caddy route — mirroring `/flash`.

**Architecture:** A new siteapp router (`app/agent_update.py`) resolves a lab name → its chisel port (reusing `app.clients.load_roster`) and forwards to `http://chisel:<port>/agent/update[/status]`, returning the agent's status + body verbatim (with two explicit deviations: clarified disabled-404, and 503 on tunnel-down). Caddy routes `^/api/admin/*` to siteapp behind `forward_auth`; Authelia restricts `^/api/admin/.*` to `group:admins`.

**Tech Stack:** FastAPI, httpx (async), Caddy `forward_auth`, Authelia access-control, pytest, bats.

## Global Constraints

- Edge path: `POST /api/admin/labs/{name}/update`, `GET /api/admin/labs/{name}/update/status`. Authelia rule `^/api/admin/.*` → `group:admins`, copying `^/flash.*` policy/subject verbatim.
- Default behavior: pass the agent's status code + body bytes through verbatim. Exactly two deviations (agent-404 → clarified body, keep 404; tunnel-down → 503 `agent unreachable`).
- Unknown lab (name not in roster) → 404 `{"error":"unknown lab","detail":name}` (never reaches the tunnel).
- No app-layer group check (edge-only, matching every existing service).
- No UI, no navbar entry, no new workflow/required-check in this PR.
- Constants: `CHISEL_HOST="chisel"`, `UPDATE_POST_TIMEOUT_S=30.0`, `STATUS_TIMEOUT_S=5.0`.
- **Runnable locally:** siteapp unit tests only (`uv run pytest`, pure Python). The Authelia e2e and bats tiers require Docker (absent on this laptop) and are verified in CI (`pr-authelia`, `pr-platform`).

---

### Task 1: siteapp proxy handler + unit tests

**Files:**
- Create: `services/siteapp/app/agent_update.py`
- Create: `services/siteapp/tests/test_agent_update.py`
- Modify: `services/siteapp/app/main.py` (register the router)

**Interfaces:**
- Consumes: `app.clients.load_roster(path) -> dict[str, dict[str, object]]` (entry has `"port"`); `app.config.Settings` (`.clients_file`).
- Produces: `make_router(settings: Settings, *, host: str = "chisel") -> APIRouter` mounting the two routes above.

- [ ] **Step 1: Write the failing tests**

Create `services/siteapp/tests/test_agent_update.py`:

```python
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

SHA = "a" * 64


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch, _clients_file_default: Path):
    """Reload app.main with a TestClient; return (client, roster_file)."""
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    from importlib import reload
    import app.main

    reload(app.main)
    return TestClient(app.main.app, raise_server_exceptions=False), _clients_file_default


def _write_roster(path: Path, *, name: str = "pc-1", port: int = 9001) -> None:
    path.write_text(
        '{"' + name + '": {"port": ' + str(port) + ', "password_sha256": "' + "0" * 64 + '"}}',
        encoding="utf-8",
    )


def _install_fake_request(monkeypatch, *, response: httpx.Response | None = None,
                          exc: Exception | None = None) -> list[dict]:
    """Patch httpx.AsyncClient.request; return a list that records each call."""
    calls: list[dict] = []

    async def fake_request(self, method, url, **kwargs):  # noqa: ANN001
        calls.append({"method": method, "url": url, **kwargs})
        if exc is not None:
            raise exc
        return response

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return calls


# ---- verbatim passthrough ------------------------------------------------

@pytest.mark.parametrize(
    "status,body",
    [
        (202, {"accepted": True, "to": "2.3.0"}),
        (200, {"outcome": "noop", "reason": "already at 2.3.0"}),
        (400, {"error": "bad url", "detail": "not https"}),
        (409, {"error": "update in progress"}),
        (502, {"error": "release lookup failed", "detail": "rate limited"}),
    ],
)
def test_post_passes_agent_status_and_body_through(app_client, monkeypatch, status, body) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(status, json=body))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == status
    assert r.json() == body


def test_post_forwards_to_correct_chisel_port_and_path(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9042)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "http://chisel:9042/agent/update"


def test_post_forwards_raw_body_unchanged(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    raw = b'{"url":"https://mirror/SerialHop-v2.3.0.exe","sha256":"' + SHA.encode() + b'"}'
    client.post("/api/admin/labs/pc-1/update", content=raw)
    assert calls[0]["content"] == raw


def test_post_empty_body_defaults_to_latest_release(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(
        monkeypatch, response=httpx.Response(202, json={"accepted": True, "to": "2.3.0"})
    )

    client.post("/api/admin/labs/pc-1/update")  # no body
    assert calls[0]["content"] == b"{}"


# ---- explicit deviations -------------------------------------------------

def test_unknown_lab_returns_404_unknown_lab(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    calls = _install_fake_request(monkeypatch, response=httpx.Response(202, json={}))

    r = client.post("/api/admin/labs/ghost/update", content=b"{}")
    assert r.status_code == 404
    assert r.json() == {"error": "unknown lab", "detail": "ghost"}
    assert calls == []  # never reached the tunnel


def test_agent_404_is_clarified_as_disabled(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(404, json={"error": "not found"}))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "remote update disabled"
    assert "turned off" in body["detail"].lower()
    assert body["upstream"] == {"error": "not found"}


def test_agent_unreachable_returns_503(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, exc=httpx.ConnectError("tunnel down"))

    r = client.post("/api/admin/labs/pc-1/update", content=b"{}")
    assert r.status_code == 503
    assert r.json()["error"] == "agent unreachable"


def test_status_passes_body_through(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    status_body = {"state": "succeeded", "from": "2.2.0", "to": "2.3.0",
                   "started_at": 1, "finished_at": 2}
    calls = _install_fake_request(monkeypatch, response=httpx.Response(200, json=status_body))

    r = client.get("/api/admin/labs/pc-1/update/status")
    assert r.status_code == 200
    assert r.json() == status_body
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"] == "http://chisel:9001/agent/update/status"


def test_status_unreachable_returns_503(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, exc=httpx.ConnectTimeout("restarting"))

    r = client.get("/api/admin/labs/pc-1/update/status")
    assert r.status_code == 503
    assert r.json()["error"] == "agent unreachable"


def test_status_unknown_lab_returns_404(app_client, monkeypatch) -> None:
    client, roster = app_client
    _write_roster(roster, name="pc-1", port=9001)
    _install_fake_request(monkeypatch, response=httpx.Response(200, json={"state": "none"}))

    r = client.get("/api/admin/labs/ghost/update/status")
    assert r.status_code == 404
    assert r.json() == {"error": "unknown lab", "detail": "ghost"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd services/siteapp && uv run pytest tests/test_agent_update.py -q`
Expected: FAIL/errors — `app.agent_update` does not exist / 404 from unrouted paths.

- [ ] **Step 3: Write the handler**

Create `services/siteapp/app/agent_update.py`:

```python
"""Admin-only proxy to a lab agent's remote-update endpoints.

Resolves a lab name to its chisel port (reusing the siteapp roster) and
forwards POST /agent/update and GET /agent/update/status to
http://chisel:<port>. The agent's status code and body are returned
verbatim, with two deliberate deviations documented in
docs/superpowers/specs/2026-07-21-remote-admin-update-server-design.md §6:

  * an agent 404 (feature disabled) is re-worded to a clear message, and
  * an unreachable agent (tunnel down, incl. the expected post-install
    restart) becomes a retryable 503 rather than an error.

The gate itself is at the edge (Authelia rule + Caddy forward_auth), matching
every other admin surface in this repo; there is no app-layer group check.
"""

from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Path as PathParam, Request, Response

from app.clients import load_roster
from app.config import Settings

CHISEL_HOST = "chisel"
UPDATE_POST_TIMEOUT_S = 30.0  # agent may do a synchronous GitHub lookup before 202/502
STATUS_TIMEOUT_S = 5.0  # local read on the agent

AGENT_UPDATE_PATH = "/agent/update"
AGENT_UPDATE_STATUS_PATH = "/agent/update/status"


def _json(payload: dict, status_code: int) -> Response:
    return Response(
        content=json.dumps(payload).encode("utf-8"),
        status_code=status_code,
        media_type="application/json",
    )


def _resolve_port(settings: Settings, name: str) -> int | None:
    """Return the lab's chisel port, or None if the name is unknown.

    Lets load_roster's OSError/ValueError propagate (→ 500) — a broken roster
    is a server fault, distinct from an unknown lab name.
    """
    roster = load_roster(settings.clients_file)
    entry = roster.get(name)
    return int(entry["port"]) if entry is not None else None


async def _forward(
    method: str,
    port: int,
    agent_path: str,
    *,
    body: bytes | None,
    timeout_s: float,
    host: str,
) -> Response:
    url = f"http://{host}:{port}{agent_path}"
    headers = {"content-type": "application/json"} if body is not None else None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, url, content=body, headers=headers, timeout=timeout_s
            )
    except (httpx.HTTPError, OSError) as exc:
        # Tunnel down / agent restarting mid-install — expected, retryable.
        return _json(
            {"error": "agent unreachable", "detail": str(exc) or type(exc).__name__},
            status_code=503,
        )

    if resp.status_code == 404:
        # We reached the agent and it returned 404 → remote update is disabled
        # on that PC. The raw {"error":"not found"} is ambiguous; clarify it.
        try:
            upstream = resp.json()
        except ValueError:
            upstream = {"body": resp.text[:200]}
        return _json(
            {
                "error": "remote update disabled",
                "detail": "Remote update is turned off on this agent.",
                "upstream": upstream,
            },
            status_code=404,
        )

    # Verbatim passthrough of everything else (202/200/400/409/502/...).
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


def make_router(settings: Settings, *, host: str = CHISEL_HOST) -> APIRouter:
    router = APIRouter()

    @router.post("/api/admin/labs/{name}/update")
    async def trigger_update(
        request: Request,
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> Response:
        port = _resolve_port(settings, name)
        if port is None:
            return _json({"error": "unknown lab", "detail": name}, status_code=404)
        # Empty body → {} → "latest release" per the agent contract.
        body = await request.body() or b"{}"
        return await _forward(
            "POST", port, AGENT_UPDATE_PATH,
            body=body, timeout_s=UPDATE_POST_TIMEOUT_S, host=host,
        )

    @router.get("/api/admin/labs/{name}/update/status")
    async def update_status(
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> Response:
        port = _resolve_port(settings, name)
        if port is None:
            return _json({"error": "unknown lab", "detail": name}, status_code=404)
        return await _forward(
            "GET", port, AGENT_UPDATE_STATUS_PATH,
            body=None, timeout_s=STATUS_TIMEOUT_S, host=host,
        )

    return router
```

- [ ] **Step 4: Register the router in `services/siteapp/app/main.py`**

Add the import next to the other router imports:

```python
from app.agent_update import make_router as make_agent_update_router
```

Add the include next to the other `include_router` calls (e.g. after `make_labs_router`):

```python
app.include_router(make_agent_update_router(settings))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd services/siteapp && uv run pytest tests/test_agent_update.py -q`
Expected: PASS (all cases).

- [ ] **Step 6: Run the full siteapp suite (no regressions) + lint**

Run: `cd services/siteapp && uv run pytest -q && uv run ruff check app tests`
Expected: PASS / no lint errors.

- [ ] **Step 7: Commit**

```bash
git add services/siteapp/app/agent_update.py services/siteapp/app/main.py services/siteapp/tests/test_agent_update.py
git commit -m "feat: add admin-gated remote agent-update proxy in siteapp"
```

---

### Task 2: Authelia admin-gate + e2e gating tests

**Files:**
- Modify: `services/authelia/config/configuration.yml.tmpl` (add rule after `^/flash.*`)
- Modify: `services/authelia/tests/e2e/fixtures/configuration.yml` (same rule, `test.local`)
- Modify: `services/authelia/tests/e2e/test_forward_auth.py`
- Modify: `services/authelia/tests/e2e/test_group_gating.py`

**Interfaces:**
- Consumes: existing `_login(http, username, password)` helper in `test_forward_auth.py`; users `alice` (admins), `bob` (researchers) from the e2e users fixture.
- Produces: an admins-only gate on `^/api/admin/.*`.

- [ ] **Step 1: Write the failing e2e assertions**

Append to `services/authelia/tests/e2e/test_forward_auth.py`:

```python
def test_verify_admin_allowed_on_api_admin(http: httpx.Client) -> None:
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert "admins" in r.headers.get("remote-groups", "")


def test_verify_without_cookie_denied_on_api_admin(http: httpx.Client) -> None:
    r = http.get(
        "/api/verify",
        headers={
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 401
```

Append to `services/authelia/tests/e2e/test_group_gating.py`:

```python
def test_researcher_denied_on_api_admin(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    r = http.get(
        "/api/verify",
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/admin/labs/pc-1/update",
            "X-Forwarded-Method": "GET",
        },
    )
    assert r.status_code == 403
```

- [ ] **Step 2: (CI) note expected failure**

These run under Docker in `pr-authelia`. Locally there is no Docker, so do not run them here. Before adding the rule, `test_verify_admin_allowed_on_api_admin` would fail (default_policy deny → 403 for alice). Confirmed by inspection; the rule in Step 3 fixes it.

- [ ] **Step 3: Add the rule to the fixture**

In `services/authelia/tests/e2e/fixtures/configuration.yml`, immediately after the `^/flash.*` rule block (the one with `subject: 'group:admins'`), insert:

```yaml
    - domain: test.local
      resources:
        - '^/api/admin/.*'
      policy: one_factor
      subject: 'group:admins'
```

- [ ] **Step 4: Add the rule to the production template**

In `services/authelia/config/configuration.yml.tmpl`, immediately after the `^/flash.*` rule block, insert:

```yaml
    - domain: __VPS_HOST__
      resources:
        - '^/api/admin/.*'
      policy: one_factor
      subject: 'group:admins'
```

- [ ] **Step 5: Sanity-check YAML renders**

Run: `python -c "import yaml,sys; yaml.safe_load(open('services/authelia/tests/e2e/fixtures/configuration.yml')); print('fixture ok')"`
Expected: `fixture ok` (tmpl has `__VPS_HOST__` tokens so it is not valid YAML until rendered — do not yaml-load the tmpl).

- [ ] **Step 6: Commit**

```bash
git add services/authelia/config/configuration.yml.tmpl services/authelia/tests/e2e/fixtures/configuration.yml services/authelia/tests/e2e/test_forward_auth.py services/authelia/tests/e2e/test_group_gating.py
git commit -m "feat: gate /api/admin behind group:admins in authelia"
```

---

### Task 3: Caddy route + routing smoke test

**Files:**
- Modify: `compose/Caddyfile.tmpl` (new `handle /api/admin/*` block)
- Modify: `tests/integration/test_routes_smoke.bats` (unauth → 302 assertion)

**Interfaces:**
- Consumes: the `authelia_required` Caddy snippet; the siteapp upstream `siteapp:8000`.
- Produces: edge routing for `/api/admin/*`.

- [ ] **Step 1: Add the Caddy handle**

In `compose/Caddyfile.tmpl`, in the siteapp region (e.g. immediately after the `handle /api/auth/* { … }` block, before the `# --- BEGIN svc:flasher ---` marker), insert:

```
    # ─── siteapp admin surface (admins only — forward_auth gate) ─────────
    handle /api/admin/* {
        import authelia_required
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
```

- [ ] **Step 2: Add the routing smoke assertion**

In `tests/integration/test_routes_smoke.bats`, after the `@test "/flash/ is gated by forward_auth (302 to /login)"` test, add:

```bash
@test "/api/admin/ is gated by forward_auth (302 to /login)" {
    code="$(_through_caddy 'https://127.0.0.1/api/admin/labs/pc-1/update')"
    [[ "$code" == "302" ]] || { echo "got: $code"; false; }
}
```

- [ ] **Step 3: Validate the Caddyfile block by inspection**

The `.tmpl` contains `__VPS_HOST__` etc., so it can't be `caddy fmt`'d directly. Verify by inspection that the new block sits inside the `https://__VPS_HOST__ { … }` server body, before the catch-all `handle { error 404 }`, and mirrors the `/flash*` block's structure (`import authelia_required` + `reverse_proxy siteapp:8000` with `header_up -Accept-Encoding`).

- [ ] **Step 4: (CI) note verification tier**

The bats smoke runs under Docker in `pr-platform` (fake-VPS). No local Docker — do not run bats here; rely on CI.

- [ ] **Step 5: Commit**

```bash
git add compose/Caddyfile.tmpl tests/integration/test_routes_smoke.bats
git commit -m "feat: route /api/admin/* to siteapp behind authelia in caddy"
```

---

## Self-Review

**Spec coverage:**
- §5.1 Authelia rule → Task 2 (tmpl + fixture). ✓
- §5.2 Caddy route → Task 3. ✓
- §5.3 siteapp proxy handler + registration → Task 1. ✓
- §6 semantics (verbatim; unknown-lab 404; disabled-404 clarified; unreachable 503) → Task 1 tests + handler. ✓
- §7 tests: Authelia e2e → Task 2; siteapp unit → Task 1; bats smoke → Task 3. ✓
- §8 files touched: all nine mapped across the three tasks. ✓
- §9 follow-up: out of scope — no task, correctly. ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `make_router(settings, *, host="chisel")`, `_resolve_port(settings, name) -> int | None`, `_forward(method, port, agent_path, *, body, timeout_s, host)`, `_json(payload, status_code)` used consistently between the handler and the tests. Routes and forwarded URLs (`http://chisel:<port>/agent/update[/status]`) match between tests and handler.

## Execution note

Executed inline in this session (executing-plans), per the standing autonomous-flow instruction: commit per task, then push, open the PR, wait for CI, and squash-merge. Local verification is the siteapp unit suite (Task 1, Step 5–6); the Authelia e2e and bats tiers are verified by CI.

# Client discovery by username — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal-only `GET /api/clients/` endpoint to siteapp returning the chisel-tunnel roster as `{name: {host, port}}`, so callers on `labnet` can resolve a lab machine's tunnel by username instead of hardcoding a port.

**Architecture:** The renderer (`scripts/lib/render.sh`) drops a passwords-stripped `clients.json` next to `chisel/users.json` at deploy time. A new module in siteapp (`app/clients.py`) reads it on each request and reshapes it; a new route in `app/api.py` serves it. Caddy has no `handle` block for `/api/clients*`, so the public side 404s via the existing jupyter catch-all. The siteapp container is already in the explicit `docker compose restart` list, so the inode-pinning trap that breaks single-file bind-mounts is already handled.

**Tech Stack:** bash + `yq` (renderer), Python 3 + FastAPI (siteapp), pytest (siteapp tests), bats (renderer tests), Docker Compose.

**Reference spec:** `docs/superpowers/specs/2026-05-04-client-discovery-by-username-design.md`

---

## File map

**Create:**
- `compose/siteapp/app/clients.py` — `load_roster(path) -> dict` reshaping the rendered file into the response payload.

**Modify:**
- `scripts/lib/render.sh` — add `render_siteapp_clients`.
- `scripts/deploy.sh` — call new renderer; ensure `$stage/siteapp/` exists before the call.
- `compose/docker-compose.yml.tmpl` — add `SITEAPP_CLIENTS_FILE` env var and `clients.json` mount on the siteapp service.
- `compose/siteapp/app/config.py` — add `clients_file: Path` to `Settings`; read `SITEAPP_CLIENTS_FILE` in `load_settings()`.
- `compose/siteapp/app/api.py` — register `/api/clients/` route.
- `compose/siteapp/tests/test_routes_api.py` — extend `client` fixture to set `SITEAPP_CLIENTS_FILE`; add cases for the new endpoint.
- `tests/test_render.bats` — add cases for `render_siteapp_clients`.

**Not changed (but worth knowing):**
- `compose/Caddyfile.tmpl` — no `handle /api/clients*` block; endpoint stays internal-only.
- `scripts/deploy.sh` line 81 — siteapp is already in `docker compose restart caddy chisel siteapp`.
- `scripts/lib/config.sh` — already validates `chisel_clients[].name`/`reverse_port`/`password`; no schema work needed.

---

## Task 1: Renderer — `render_siteapp_clients`

**Files:**
- Modify: `scripts/lib/render.sh` (append a new function below `render_chisel_users`)
- Test: `tests/test_render.bats` (append new bats blocks)

The renderer mirrors `render_chisel_users` but emits a flat `name → reverse_port` map with no passwords. Same `yq` reduce trick that the existing renderer uses, so the empty-roster behavior is identical.

- [ ] **Step 1: Add failing bats tests for the new renderer**

Append these blocks to `tests/test_render.bats` (after the existing `render_chisel_users` blocks):

```bash
@test "render_siteapp_clients: emits flat name→reverse_port map" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    echo "$output" | yq -p json e '.' >/dev/null
    run yq -p json e '."microscope-1"' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "9001" ]]
}

@test "render_siteapp_clients: never leaks passwords" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    # The fixture's password is k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6
    [[ "$output" != *"k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6"* ]]
    [[ "$output" != *"password"* ]]
}

@test "render_siteapp_clients: empty chisel_clients yields empty object" {
    cat > $TMPDIR/empty.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u, ssh_port: 22, remote_root: /srv/x, notebooks_path: /srv/y}
caddy: {acme_email: o@x.io}
jupyter:
  image: quay.io/jupyter/scipy-notebook:2026-04-20
  password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"
chisel: {image: jpillora/chisel:1.10.1, listen_port: 8080}
loki: {image: grafana/loki:3.2.1, retention_days: 30}
grafana: {image: grafana/grafana:11.3.0}
siteapp:
  image: ghcr.io/test/lab-bridge-siteapp:0.0.1
  admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/empty.yaml
        render_siteapp_clients $TMPDIR/clients.json
        cat $TMPDIR/clients.json
    "
    [ "$status" -eq 0 ]
    [[ "$(echo "$output" | tr -d '[:space:]')" == "{}" ]]
}

@test "render_siteapp_clients: roster names mirror render_chisel_users" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_chisel_users $TMPDIR/users.json
        render_siteapp_clients $TMPDIR/clients.json
    "
    # Names from chisel users.json keys are 'name:password'; strip the suffix.
    chisel_names="$(yq -p json e 'keys | .[]' $TMPDIR/users.json | sed 's/:.*//' | sort)"
    siteapp_names="$(yq -p json e 'keys | .[]' $TMPDIR/clients.json | sort)"
    [[ "$chisel_names" == "$siteapp_names" ]]
}
```

- [ ] **Step 2: Run the new bats tests and verify they fail**

Run:
```bash
cd /Users/khamitovdr/lab_devices_server
bats tests/test_render.bats -f "render_siteapp_clients"
```

Expected: 4 tests, all FAIL (function `render_siteapp_clients` not defined → bash exit 127 → `[ "$status" -eq 0 ]` fails).

- [ ] **Step 3: Implement `render_siteapp_clients`**

Append this function to `scripts/lib/render.sh` after `render_chisel_users` (and before `render_loki_config`):

```bash
# render_siteapp_clients <output_path>
# Builds the siteapp clients.json from .chisel_clients in CONFIG_PATH.
# Output is a flat name → reverse_port map. Passwords are deliberately
# omitted: siteapp's clients endpoint is internal-only and never needs
# to authenticate as a chisel client.
render_siteapp_clients() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({(.name): .reverse_port})
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}
```

- [ ] **Step 4: Run the bats tests and verify they pass**

Run:
```bash
bats tests/test_render.bats -f "render_siteapp_clients"
```

Expected: 4 tests, all PASS.

- [ ] **Step 5: Run the full bats suite to confirm no regressions**

Run:
```bash
bats tests/
```

Expected: every existing test still passes plus the 4 new ones.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/render.sh tests/test_render.bats
git commit -m "feat(render): emit siteapp clients.json from chisel_clients"
```

---

## Task 2: Wire renderer into deploy.sh

**Files:**
- Modify: `scripts/deploy.sh:21-23` (initial mkdir line) and `scripts/deploy.sh:28` (call site)

The new renderer needs `$stage/siteapp/` to exist before it writes there. The existing flow creates that directory later, when `agent_upload_token` gets installed; we move the mkdir up to keep the renderer-call block self-contained. The redundant later `mkdir -p "$stage/siteapp"` stays (it's idempotent and explicit at the install site).

- [ ] **Step 1: Add `siteapp` to the upfront mkdir and call the new renderer**

Edit `scripts/deploy.sh`. Find this block:

```bash
    log "rendering templates..."
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"
    render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"
```

Replace with:

```bash
    log "rendering templates..."
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning" "$stage/siteapp"
    render_compose     "$REPO_ROOT/compose/docker-compose.yml.tmpl" "$stage/docker-compose.yml"
    render_caddyfile   "$REPO_ROOT/compose/Caddyfile.tmpl"           "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"
    render_siteapp_clients "$stage/siteapp/clients.json"
    render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"
```

- [ ] **Step 2: Smoke-test deploy rendering locally (no rsync)**

Run a render-only invocation by sourcing the libs directly (avoids the SSH path):

```bash
bash -c '
    set -e
    cd /Users/khamitovdr/lab_devices_server
    source scripts/lib/common.sh
    source scripts/lib/config.sh
    source scripts/lib/render.sh
    load_config tests/fixtures/valid_config.yaml
    stage="$(mktemp -d)"
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning" "$stage/siteapp"
    render_compose compose/docker-compose.yml.tmpl "$stage/docker-compose.yml"
    render_caddyfile compose/Caddyfile.tmpl "$stage/Caddyfile"
    render_chisel_users "$stage/chisel/users.json"
    render_siteapp_clients "$stage/siteapp/clients.json"
    render_loki_config compose/loki/config.yaml.tmpl "$stage/loki/config.yaml"
    echo "--- chisel/users.json ---"
    cat "$stage/chisel/users.json"
    echo "--- siteapp/clients.json ---"
    cat "$stage/siteapp/clients.json"
    rm -rf "$stage"
'
```

Expected: both files printed, both valid JSON; `siteapp/clients.json` is `{"microscope-1":9001}` (the fixture's single client).

- [ ] **Step 3: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): render siteapp/clients.json into the staging dir"
```

---

## Task 3: Settings — add `clients_file`

**Files:**
- Modify: `compose/siteapp/app/config.py`
- Test: `compose/siteapp/tests/test_config.py` (append)

`Settings` gains `clients_file: Path`. `load_settings()` reads `SITEAPP_CLIENTS_FILE` and treats it as required (parallel to `SITE_DATA`). No existence check at load time — the route reads it on each request, which is where any failure should surface.

- [ ] **Step 1: Inspect existing test_config.py to follow its style**

Run:
```bash
cat compose/siteapp/tests/test_config.py
```

Read what's there so the new tests match the existing pytest patterns (monkeypatch env vars, call `load_settings()`, assert on the returned `Settings`).

- [ ] **Step 2: Write failing test cases**

Append to `compose/siteapp/tests/test_config.py`:

```python
def test_clients_file_required(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_CLIENTS_FILE", raising=False)
    from app.config import load_settings

    with pytest.raises(RuntimeError, match="SITEAPP_CLIENTS_FILE"):
        load_settings()


def test_clients_file_path_stored(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", "/etc/siteapp/clients.json")
    from app.config import load_settings

    settings = load_settings()
    assert settings.clients_file == Path("/etc/siteapp/clients.json")
```

If the existing file has top-of-module imports (`Path`, `pytest`), don't duplicate; otherwise add them at the top.

- [ ] **Step 3: Run tests and verify they fail**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_config.py::test_clients_file_required tests/test_config.py::test_clients_file_path_stored -v
```

Expected: 2 tests FAIL — `Settings` has no `clients_file` field, or the env var read isn't there yet.

- [ ] **Step 4: Update `Settings` and `load_settings`**

Edit `compose/siteapp/app/config.py`. Update the dataclass:

```python
@dataclass(frozen=True)
class Settings:
    site_data: Path
    agent_upload_token: str
    clients_file: Path
    max_upload_mb_doc: int = 10
    max_upload_mb_agent: int = 100
    csrf_secret: str = ""
```

In `load_settings()`, after the `SITE_DATA` block (around the existing `if not data: raise RuntimeError(...)`), add:

```python
    clients_env = os.environ.get("SITEAPP_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("SITEAPP_CLIENTS_FILE env var is required")
    clients_file = Path(clients_env)
```

Then update the final `return Settings(...)` call to include the new field:

```python
    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        clients_file=clients_file,
        csrf_secret=csrf,
    )
```

- [ ] **Step 5: Run the new tests and verify they pass**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_config.py::test_clients_file_required tests/test_config.py::test_clients_file_path_stored -v
```

Expected: 2 tests PASS.

- [ ] **Step 6: Run the full siteapp test suite — expect breakage**

Run:
```bash
cd compose/siteapp
uv run pytest tests/ -v
```

Expected: every test that calls `load_settings()` without setting `SITEAPP_CLIENTS_FILE` now fails with `RuntimeError`. This is intentional — the next task fixes the shared fixture. Note which tests fail; you'll re-run after Task 5.

- [ ] **Step 7: Commit**

```bash
git add compose/siteapp/app/config.py compose/siteapp/tests/test_config.py
git commit -m "feat(siteapp): add SITEAPP_CLIENTS_FILE to Settings"
```

---

## Task 4: `app/clients.py` — `load_roster`

**Files:**
- Create: `compose/siteapp/app/clients.py`
- Test: `compose/siteapp/tests/test_clients.py`

Pure function, easy to TDD in isolation. The reshape happens here so the route is a one-liner. Rejecting `bool` explicitly because `isinstance(True, int)` is `True` in Python and we don't want a config typo to slip through.

- [ ] **Step 1: Write failing tests**

Create `compose/siteapp/tests/test_clients.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import CHISEL_HOST, load_roster


def test_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"khamit_desktop": 8089, "another_lab": 8090}', encoding="utf-8")

    assert load_roster(f) == {
        "khamit_desktop": {"host": CHISEL_HOST, "port": 8089},
        "another_lab": {"host": CHISEL_HOST, "port": 8090},
    }


def test_empty_roster(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("{}", encoding="utf-8")

    assert load_roster(f) == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        load_roster(tmp_path / "nope.json")


def test_malformed_json_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("not-json", encoding="utf-8")

    with pytest.raises(ValueError):  # json.JSONDecodeError is a ValueError
        load_roster(f)


def test_top_level_not_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_non_int_value_raises(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": "not-a-port"}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_bool_value_rejected(tmp_path: Path) -> None:
    # YAML "yes"/"no" can render as true/false; reject those explicitly
    # because isinstance(True, int) is True in Python.
    f = tmp_path / "clients.json"
    f.write_text('{"x": true}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_clients.py -v
```

Expected: all 7 tests FAIL with `ModuleNotFoundError: No module named 'app.clients'`.

- [ ] **Step 3: Create `app/clients.py`**

Create `compose/siteapp/app/clients.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

CHISEL_HOST = "chisel"  # docker compose service name on labnet


def load_roster(path: Path) -> dict[str, dict[str, object]]:
    """Read and reshape the rendered roster file.

    Returns the response-ready map: {name: {"host": ..., "port": int}}.
    Raises OSError on missing/unreadable file, ValueError on malformed
    JSON or wrong shape. The route layer lets these propagate so
    FastAPI returns a 500 and uvicorn logs the traceback.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, object]] = {}
    for name, port in raw.items():
        if not isinstance(name, str):
            raise ValueError(f"roster key must be string, got: {name!r}")
        # bool is a subclass of int in Python; exclude it explicitly.
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster value must be int, got: {name}={port!r}")
        out[name] = {"host": CHISEL_HOST, "port": port}
    return out
```

- [ ] **Step 4: Run tests and verify they pass**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_clients.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/clients.py compose/siteapp/tests/test_clients.py
git commit -m "feat(siteapp): add load_roster for chisel client discovery"
```

---

## Task 5: `/api/clients/` route + fixture rewire

**Files:**
- Modify: `compose/siteapp/app/api.py`
- Modify: `compose/siteapp/tests/test_routes_api.py` (extend `client` fixture, append new tests)

Route is a one-liner: `return load_roster(settings.clients_file)`. Exceptions propagate to FastAPI's default handler (`500 Internal Server Error`). The existing `client` fixture has to learn about `SITEAPP_CLIENTS_FILE` so the agent-upload tests also keep passing — Task 3 made that env var required.

- [ ] **Step 1: Extend the `client` fixture to set `SITEAPP_CLIENTS_FILE`**

Edit `compose/siteapp/tests/test_routes_api.py`. Find the `client` fixture:

```python
@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", TOKEN)
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)
```

Replace with:

```python
@pytest.fixture
def clients_file(tmp_path: Path) -> Path:
    """Default empty roster file. Tests that need entries write to it."""
    p = tmp_path / "clients.json"
    p.write_text("{}", encoding="utf-8")
    return p


@pytest.fixture
def client(tmp_path: Path, clients_file: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", TOKEN)
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", str(clients_file))
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)
```

- [ ] **Step 2: Run existing agent-upload tests — they should pass again**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_routes_api.py -v
```

Expected: every existing test in this file passes (the fixture now provides `SITEAPP_CLIENTS_FILE` as required by Task 3).

- [ ] **Step 3: Add failing tests for `/api/clients/`**

Append to `compose/siteapp/tests/test_routes_api.py`:

```python
def test_clients_endpoint_happy_path(client: TestClient, clients_file: Path) -> None:
    clients_file.write_text(
        '{"khamit_desktop": 8089, "another_lab": 8090}', encoding="utf-8"
    )

    r = client.get("/api/clients/")
    assert r.status_code == 200
    assert r.json() == {
        "khamit_desktop": {"host": "chisel", "port": 8089},
        "another_lab":    {"host": "chisel", "port": 8090},
    }


def test_clients_endpoint_empty_roster(client: TestClient) -> None:
    # clients_file fixture wrote {} by default
    r = client.get("/api/clients/")
    assert r.status_code == 200
    assert r.json() == {}


def test_clients_endpoint_rereads_on_each_request(
    client: TestClient, clients_file: Path
) -> None:
    clients_file.write_text('{"a": 1}', encoding="utf-8")
    r1 = client.get("/api/clients/")
    assert r1.status_code == 200
    assert r1.json() == {"a": {"host": "chisel", "port": 1}}

    clients_file.write_text('{"a": 1, "b": 2}', encoding="utf-8")
    r2 = client.get("/api/clients/")
    assert r2.status_code == 200
    assert r2.json() == {
        "a": {"host": "chisel", "port": 1},
        "b": {"host": "chisel", "port": 2},
    }


def test_clients_endpoint_missing_file_returns_500(
    client: TestClient, clients_file: Path
) -> None:
    clients_file.unlink()
    r = client.get("/api/clients/")
    assert r.status_code == 500


def test_clients_endpoint_malformed_returns_500(
    client: TestClient, clients_file: Path
) -> None:
    clients_file.write_text("not-json", encoding="utf-8")
    r = client.get("/api/clients/")
    assert r.status_code == 500


def test_clients_endpoint_wrong_shape_returns_500(
    client: TestClient, clients_file: Path
) -> None:
    clients_file.write_text("[1, 2, 3]", encoding="utf-8")
    r = client.get("/api/clients/")
    assert r.status_code == 500
```

- [ ] **Step 4: Run the new tests and verify they fail**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_routes_api.py -k "clients_endpoint" -v
```

Expected: all 6 tests FAIL with 404 (the route doesn't exist yet).

- [ ] **Step 5: Add the route**

Edit `compose/siteapp/app/api.py`. Add this import near the top, alongside the existing `from app.config import Settings`:

```python
from app.clients import load_roster
```

Inside `make_router`, after the existing `upload_endpoint` definition (before `return router`), add:

```python
    @router.get("/api/clients/")
    def list_clients() -> dict[str, dict[str, object]]:
        return load_roster(settings.clients_file)
```

- [ ] **Step 6: Run the new tests and verify they pass**

Run:
```bash
cd compose/siteapp
uv run pytest tests/test_routes_api.py -k "clients_endpoint" -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Run the full siteapp suite**

Run:
```bash
cd compose/siteapp
uv run pytest tests/ -v
```

Expected: every test passes — including the previously-broken ones from Task 3 step 6, because the fixture now provides `SITEAPP_CLIENTS_FILE`.

If any test outside `test_routes_api.py` still fails because it builds its own `Settings` without `clients_file`, fix it the same way the `client` fixture was fixed (inject env var or pass `clients_file=tmp_path / "x.json"` directly).

- [ ] **Step 8: Commit**

```bash
git add compose/siteapp/app/api.py compose/siteapp/tests/test_routes_api.py
git commit -m "feat(siteapp): GET /api/clients/ returns chisel client roster"
```

---

## Task 6: Compose template — mount clients.json into siteapp

**Files:**
- Modify: `compose/docker-compose.yml.tmpl` (siteapp service block)
- Test: `tests/test_render.bats` (one new bats block)

The mount path and env var are static (no `__VAR__` substitution), so the template change is two added lines.

- [ ] **Step 1: Add a failing bats test for the new compose lines**

Append to `tests/test_render.bats`:

```bash
@test "render_compose: siteapp service mounts clients.json read-only and sets SITEAPP_CLIENTS_FILE" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
    run yq e '.services.siteapp.volumes[]' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == *"./siteapp/clients.json:/etc/siteapp/clients.json:ro"* ]]

    run yq e '.services.siteapp.environment.SITEAPP_CLIENTS_FILE' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "/etc/siteapp/clients.json" ]]
}
```

- [ ] **Step 2: Run the test and verify it fails**

Run:
```bash
bats tests/test_render.bats -f "siteapp service mounts clients.json"
```

Expected: FAIL — neither the volume nor the env var is in the rendered output.

- [ ] **Step 3: Update the compose template**

Edit `compose/docker-compose.yml.tmpl`. Find the siteapp service block:

```yaml
  siteapp:
    image: __SITEAPP_IMAGE__
    restart: unless-stopped
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
    volumes:
      - ./site_data:/data
    secrets:
      - agent_upload_token
    networks: [labnet]
```

Replace with:

```yaml
  siteapp:
    image: __SITEAPP_IMAGE__
    restart: unless-stopped
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
    volumes:
      - ./site_data:/data
      - ./siteapp/clients.json:/etc/siteapp/clients.json:ro
    secrets:
      - agent_upload_token
    networks: [labnet]
```

- [ ] **Step 4: Run the test and verify it passes**

Run:
```bash
bats tests/test_render.bats -f "siteapp service mounts clients.json"
```

Expected: PASS.

- [ ] **Step 5: Run the full bats suite and full pytest suite**

Run:
```bash
cd /Users/khamitovdr/lab_devices_server
bats tests/
cd compose/siteapp && uv run pytest tests/ -v
```

Expected: every test passes (no regressions).

- [ ] **Step 6: Commit**

```bash
git add compose/docker-compose.yml.tmpl tests/test_render.bats
git commit -m "feat(compose): mount siteapp clients.json and set SITEAPP_CLIENTS_FILE"
```

---

## Task 7: Manual end-to-end smoke test (local docker, no VPS)

**Files:** none modified — verification step only.

This runs the rendered stack locally to confirm the new endpoint is reachable from another container on `labnet` and not from the host. Skip if you don't have docker available; otherwise this is the most direct way to catch wiring mistakes.

- [ ] **Step 1: Render to a temp staging dir**

```bash
cd /Users/khamitovdr/lab_devices_server
stage="$(mktemp -d)"
LDS_SKIP_HEALTHCHECK=1 LDS_CONFIG=tests/fixtures/valid_config.yaml \
    bash -c '
        source scripts/lib/common.sh
        source scripts/lib/config.sh
        source scripts/lib/render.sh
        load_config "$LDS_CONFIG"
        mkdir -p "'"$stage"'/chisel" "'"$stage"'/loki" "'"$stage"'/grafana/provisioning" "'"$stage"'/siteapp"
        render_compose compose/docker-compose.yml.tmpl "'"$stage"'/docker-compose.yml"
        render_caddyfile compose/Caddyfile.tmpl "'"$stage"'/Caddyfile"
        render_chisel_users "'"$stage"'/chisel/users.json"
        render_siteapp_clients "'"$stage"'/siteapp/clients.json"
        render_loki_config compose/loki/config.yaml.tmpl "'"$stage"'/loki/config.yaml"
    '
echo "$stage"
cat "$stage/siteapp/clients.json"
```

Expected: `{"microscope-1":9001}`.

- [ ] **Step 2: Verify the public side cannot reach `/api/clients/`**

The Caddy config has no `handle /api/clients*` block; the catch-all sends those to jupyter, which 404s. You don't need a running stack to verify this — `grep` is enough:

```bash
grep -n "api/clients" compose/Caddyfile.tmpl || echo "no Caddy handler for /api/clients — public side will 404"
```

Expected: no match; the echo prints.

- [ ] **Step 3: (Optional) Bring up the stack and `curl` from inside labnet**

If you want a live verification:

```bash
cd "$stage"
docker compose up -d siteapp
docker compose run --rm --network "$(basename $stage)_labnet" alpine \
    sh -c 'apk add --no-cache curl >/dev/null && curl -s http://siteapp:8000/api/clients/'
docker compose down -v
rm -rf "$stage"
```

Expected JSON: `{"microscope-1":{"host":"chisel","port":9001}}`.

(If `apk add` is too heavy, swap in `curlimages/curl` or any container with curl installed and on the same network.)

- [ ] **Step 4: No commit needed; this is verification only.**

---

## Self-review against spec

| Spec section | Implementing task |
|---|---|
| Goal: `GET /api/clients/` returns `{name: {host, port}}` | Task 5 |
| Internal-only via Caddy omission | Inherent (no Caddy change); Task 7 step 2 verifies |
| Passwords stay out of siteapp | Task 1 (renderer drops only name + reverse_port) |
| Render → mount → restart workflow | Tasks 1, 2, 6 (deploy.sh restart already in place) |
| Renderer (`render_siteapp_clients`) | Task 1 |
| Compose mount + env var | Task 6 |
| `Settings.clients_file` | Task 3 |
| `app/clients.py` `load_roster` | Task 4 |
| Route in `app/api.py` | Task 5 |
| Re-read on each request | Task 4 reads fresh; Task 5 step 3 covers re-read test |
| 200 happy path / empty / 500 missing / 500 malformed / 500 wrong shape | Task 5 (all 6 endpoint tests) |
| Renderer tests: happy / empty / no-password-leak / mirror | Task 1 (all 4 bats tests) |
| Test file location: extend `test_routes_api.py` | Task 5 |

No gaps detected.

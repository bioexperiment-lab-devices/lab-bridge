# Public client status & discovery — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three public HTTPS routes on siteapp — port lookup by username (bearer-auth'd with the chisel password), TCP-probe-based connected status, and chisel server health — backed by a renderer that emits `{port, password_sha256}` so siteapp never holds plaintext passwords.

**Architecture:** Reshape the existing `render_siteapp_clients` output from `{name: int}` to `{name: {port, password_sha256}}`. Add a new siteapp module `app/public_clients.py` with a `/api/public/clients/{username}` route (bearer = chisel password, constant-time compare against the stored hash, all auth failures return byte-identical 401), a `/api/public/health` route (proxies chisel's own `/health`), and helpers for a TCP probe to `chisel:<port>` and an HTTP probe to `chisel:7000/health`. Wire one new `handle /api/public*` block in the Caddyfile.

**Tech Stack:** Python 3.13, FastAPI, httpx (added to runtime deps), stdlib `socket`/`hashlib`/`secrets`/`json`. Bash + yq for the renderer. Bats for renderer tests, pytest for siteapp tests.

**Reference spec:** `docs/superpowers/specs/2026-05-11-public-client-status-design.md`

---

## Pre-flight

The plan touches these files; useful to keep this map open while working:

| File | Action | What it owns after this plan |
|---|---|---|
| `scripts/lib/render.sh` | modify | Renderer emits `{name: {port, password_sha256}}` |
| `compose/siteapp/app/clients.py` | modify | Internal loader tolerates the new entry shape; response unchanged |
| `compose/siteapp/app/public_clients.py` | create | New module: roster load, bearer verify, TCP/HTTP probes, two routes |
| `compose/siteapp/app/main.py` | modify | Register the new router |
| `compose/siteapp/pyproject.toml` | modify | Add `httpx` to runtime deps |
| `compose/Caddyfile.tmpl` | modify | Add `handle /api/public*` block |
| `compose/siteapp/tests/test_clients.py` | modify | Update fixtures to new entry shape |
| `compose/siteapp/tests/test_routes_api.py` | modify | Update fixtures for the internal `/api/clients/` tests to new entry shape |
| `compose/siteapp/tests/test_routes_public_clients.py` | create | Pytest cases for the new routes |
| `tests/test_render.bats` | modify | Update existing `render_siteapp_clients` cases, add hash-shape cases |

Each task below ends with a commit. Tests are written first.

---

## Task 1: Internal loader tolerates the new entry shape

**Goal:** Before the renderer is changed, teach the existing internal loader to read `{port, password_sha256}` entries (ignoring the hash). This keeps `/api/clients/` working through the cutover and isolates one concern per commit.

**Files:**
- Modify: `compose/siteapp/app/clients.py`
- Modify: `compose/siteapp/tests/test_clients.py`
- Modify: `compose/siteapp/tests/test_routes_api.py`

- [ ] **Step 1.1: Update `test_clients.py` happy path to feed the new shape**

Replace the body of `test_happy_path` and `test_non_int_value_raises`, add a `test_rejects_old_flat_shape` so the old integer-valued shape is now a deploy bug:

```python
# compose/siteapp/tests/test_clients.py

def test_happy_path(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text(
        '{"khamit_desktop": {"port": 8089, "password_sha256": "aa"},'
        ' "another_lab": {"port": 8090, "password_sha256": "bb"}}',
        encoding="utf-8",
    )

    assert load_roster(f) == {
        "khamit_desktop": {"host": CHISEL_HOST, "port": 8089},
        "another_lab": {"host": CHISEL_HOST, "port": 8090},
    }


def test_rejects_old_flat_shape(tmp_path: Path) -> None:
    # The flat {name: int} shape was the pre-2026-05-11 format. After the
    # renderer change, an int value means a stale clients.json on the VPS.
    f = tmp_path / "clients.json"
    f.write_text('{"x": 8089}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_entry_missing_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_non_int_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": "not-a-port", "password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)


def test_rejects_bool_port(tmp_path: Path) -> None:
    f = tmp_path / "clients.json"
    f.write_text('{"x": {"port": true, "password_sha256": "aa"}}', encoding="utf-8")

    with pytest.raises(ValueError):
        load_roster(f)
```

Delete the now-obsolete `test_non_int_value_raises` and `test_bool_value_rejected` (their new equivalents are `test_rejects_non_int_port` and `test_rejects_bool_port`).

- [ ] **Step 1.2: Run the tests; verify they fail**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_clients.py -v
```
Expected: the new tests fail because `load_roster` still expects `int` values.

- [ ] **Step 1.3: Update `load_roster` to read the new shape**

```python
# compose/siteapp/app/clients.py

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

    Entry shape on disk is {"port": int, "password_sha256": str};
    the hash is used by the public-clients endpoint and ignored here.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, object]] = {}
    for name, entry in raw.items():
        if not isinstance(name, str):
            raise ValueError(f"roster key must be string, got: {name!r}")
        if not isinstance(entry, dict):
            raise ValueError(f"roster value must be object, got: {name}={entry!r}")
        port = entry.get("port")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError(f"roster port must be int, got: {name}.port={port!r}")
        out[name] = {"host": CHISEL_HOST, "port": port}
    return out
```

- [ ] **Step 1.4: Run the loader tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_clients.py -v
```
Expected: all pass.

- [ ] **Step 1.5: Update `test_routes_api.py` fixtures to feed the new shape**

Three test functions write the old flat shape via `clients_file.write_text(...)`. Rewrite them to the new shape:

```python
# compose/siteapp/tests/test_routes_api.py

def test_clients_endpoint_happy_path(client: TestClient, clients_file: Path) -> None:
    clients_file.write_text(
        '{"khamit_desktop": {"port": 8089, "password_sha256": "aa"},'
        ' "another_lab": {"port": 8090, "password_sha256": "bb"}}',
        encoding="utf-8",
    )

    r = client.get("/api/clients/")
    assert r.status_code == 200
    assert r.json() == {
        "khamit_desktop": {"host": "chisel", "port": 8089},
        "another_lab":    {"host": "chisel", "port": 8090},
    }


def test_clients_endpoint_rereads_on_each_request(
    client: TestClient, clients_file: Path
) -> None:
    clients_file.write_text(
        '{"a": {"port": 1, "password_sha256": "aa"}}', encoding="utf-8"
    )
    r1 = client.get("/api/clients/")
    assert r1.status_code == 200
    assert r1.json() == {"a": {"host": "chisel", "port": 1}}

    clients_file.write_text(
        '{"a": {"port": 1, "password_sha256": "aa"},'
        ' "b": {"port": 2, "password_sha256": "bb"}}',
        encoding="utf-8",
    )
    r2 = client.get("/api/clients/")
    assert r2.status_code == 200
    assert r2.json() == {
        "a": {"host": "chisel", "port": 1},
        "b": {"host": "chisel", "port": 2},
    }
```

`test_clients_endpoint_empty_roster`, `test_clients_endpoint_missing_file_returns_500`, `test_clients_endpoint_malformed_returns_500`, and `test_clients_endpoint_wrong_shape_returns_500` keep their bodies — `{}`, missing file, `not-json`, and `[1,2,3]` are all still appropriate inputs.

- [ ] **Step 1.6: Run the route tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_api.py -v
```
Expected: all pass.

- [ ] **Step 1.7: Run the whole siteapp suite to make sure nothing else regressed**

Run:
```bash
cd compose/siteapp && uv run pytest -v
```
Expected: all pass.

- [ ] **Step 1.8: Commit**

```bash
git add compose/siteapp/app/clients.py compose/siteapp/tests/test_clients.py compose/siteapp/tests/test_routes_api.py
git commit -m "$(cat <<'EOF'
refactor(siteapp): internal loader reads {port, password_sha256} entries

Reshapes load_roster to expect the per-entry dict that the renderer
will emit next. Response shape (name → {host, port}) is unchanged;
the password_sha256 field is read by a separate module and ignored
here. Tests now feed the new on-disk shape; the old flat int-valued
shape is treated as a deploy bug.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Renderer emits `{port, password_sha256}` and bats tests cover the new shape

**Files:**
- Modify: `scripts/lib/render.sh:51-64`
- Modify: `tests/test_render.bats`

- [ ] **Step 2.1: Update the existing `render_siteapp_clients` bats tests to expect the new shape**

In `tests/test_render.bats`, replace the body of `render_siteapp_clients: emits flat name→reverse_port map` with a new shape check, and add two new tests for hash format and no-leak. The fixture's known password is `k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6` (microscope-1).

Replace the existing `render_siteapp_clients: emits flat name→reverse_port map` test (around line 184) with:

```bash
@test "render_siteapp_clients: emits {port, password_sha256} per entry" {
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

    run yq -p json -o json e '."microscope-1".port' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "9001" ]]

    run yq -p json -o json e '."bench-2".port' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "9002" ]]

    # Hash is 64 lowercase hex chars
    run yq -p json e '."microscope-1".password_sha256' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" =~ ^[0-9a-f]{64}$ ]]

    # Verify exactly two top-level keys
    run yq -p json -o json e 'keys | length' "$TMPDIR/clients.json"
    [ "$status" -eq 0 ]
    [[ "$output" == "2" ]]
}

@test "render_siteapp_clients: password_sha256 matches sha256(password)" {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_siteapp_clients $TMPDIR/clients.json
    "
    expected="$(printf '%s' 'k7HfLpNqRsT3uVwX1yZ2aB3cD4eF5gH6' | openssl dgst -sha256 -hex | awk '{print $NF}')"
    actual="$(yq -p json e '."microscope-1".password_sha256' "$TMPDIR/clients.json")"
    [[ "$expected" == "$actual" ]]
}
```

Replace the existing `render_siteapp_clients: never leaks passwords` test with one that also greps for the literal `password_sha256` key (positive assertion the hash field exists) but still rejects any password substring:

```bash
@test "render_siteapp_clients: never leaks passwords; hash field present" {
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
    # Hash field IS expected — this is the positive shape check
    [[ "$output" == *'"password_sha256"'* ]]
}
```

Keep the existing `render_siteapp_clients: empty chisel_clients yields empty object` and `render_siteapp_clients: roster names mirror render_chisel_users` tests unchanged.

- [ ] **Step 2.2: Run the bats tests; verify they fail**

Run:
```bash
bats tests/test_render.bats -f render_siteapp_clients
```
Expected: the new shape assertions fail because the renderer still emits the flat shape.

- [ ] **Step 2.3: Update `render_siteapp_clients` to emit the new shape**

In `scripts/lib/render.sh`, replace the current `render_siteapp_clients` (lines 51-64) with:

```sh
# render_siteapp_clients <output_path>
# Builds the siteapp clients.json from .chisel_clients in CONFIG_PATH.
# Output shape: {"<name>": {"port": <int>, "password_sha256": "<hex>"}, ...}
# The password itself is never written — only its SHA-256 hash.
# Why SHA-256 (not bcrypt): chisel passwords are 32-byte cryptographic
# random tokens (~256 bits), so preimage resistance of SHA-256 is more
# than enough. Bcrypt's cost factor exists to slow dictionary attacks
# against low-entropy human passwords; that threat doesn't apply here.
render_siteapp_clients() {
    local out="${1:?}"
    yq -o=json e '
        .chisel_clients
        | map({
            (.name): {
                "port": .reverse_port,
                "password_sha256": (.password | @sha256)
            }
        })
        | (. // [{}])
        | .[] as $item ireduce ({}; . * $item)
    ' "${CONFIG_PATH:?}" > "$out"
}
```

- [ ] **Step 2.4: Run the bats tests; verify they pass**

Run:
```bash
bats tests/test_render.bats -f render_siteapp_clients
```
Expected: all `render_siteapp_clients` tests pass.

If `@sha256` is unavailable on the target yq version, the run will fail with `unknown function: @sha256`. Fallback: a shell loop using `openssl dgst -sha256 -binary | xxd -p -c 64`. Decision: ship the yq variant; only swap if CI rejects it. The codebase already pins yq v4+ (`mikefarah/yq`), which has `@sha256`.

- [ ] **Step 2.5: Run the whole bats suite to catch unrelated breakage**

Run:
```bash
bats tests/
```
Expected: all pass (or the integration suites cleanly skip if Docker Hub is unreachable, per the existing README note).

- [ ] **Step 2.6: Commit**

```bash
git add scripts/lib/render.sh tests/test_render.bats
git commit -m "$(cat <<'EOF'
feat(render): siteapp clients.json emits {port, password_sha256}

The new per-entry shape replaces the flat name→port map and lets the
upcoming public client status endpoint verify bearer tokens against
stored SHA-256 hashes without ever holding plaintext passwords in
siteapp. Hash is sha256(password) computed by yq's @sha256 operator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add httpx to siteapp runtime dependencies

**Why:** The chisel-server health route in Task 7 issues an outbound HTTP request from siteapp to `chisel:7000/health`. httpx is already a dev dependency (transitive via FastAPI's TestClient); promoting it to a runtime dep makes the import in `public_clients.py` legitimate.

**Files:**
- Modify: `compose/siteapp/pyproject.toml`

- [ ] **Step 3.1: Add `httpx` to the `[project] dependencies` array**

```toml
# compose/siteapp/pyproject.toml

[project]
name = "siteapp"
version = "0.1.0"
description = "Public docs + agent downloads + admin for lab-bridge."
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "jinja2>=3.1,<4",
    "markdown-it-py[linkify]>=3.0,<4",
    "mdit-py-plugins>=0.4,<0.5",
    "pygments>=2.18,<3",
    "python-multipart>=0.0.9,<0.1",
    "itsdangerous>=2.2,<3",
    "bleach>=6,<7",
    "httpx>=0.27,<0.29",
]
```

The `dev` group can keep its existing `httpx` pin (uv collapses overlapping constraints).

- [ ] **Step 3.2: Refresh the lockfile**

Run:
```bash
cd compose/siteapp && uv sync
```
Expected: lockfile updated; `httpx` now appears under `[project]` resolution.

- [ ] **Step 3.3: Smoke-test imports**

Run:
```bash
cd compose/siteapp && uv run python -c "import httpx; print(httpx.__version__)"
```
Expected: prints a version like `0.27.x`.

- [ ] **Step 3.4: Commit**

```bash
git add compose/siteapp/pyproject.toml compose/siteapp/uv.lock
git commit -m "$(cat <<'EOF'
chore(siteapp): promote httpx to runtime dependency

The upcoming public client status endpoint issues an outbound HTTP
request to chisel:7000/health; httpx already ships via dev deps for
TestClient, this just acknowledges the runtime use.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `public_clients` module — roster load, bearer parse, constant-time verify

**Goal:** Build the verification primitives first, before any routes. Tests-first.

**Files:**
- Create: `compose/siteapp/app/public_clients.py`
- Create: `compose/siteapp/tests/test_routes_public_clients.py` (helpers-only; routes added in Task 6)

- [ ] **Step 4.1: Write the failing helper tests**

```python
# compose/siteapp/tests/test_routes_public_clients.py
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.public_clients import (
    _load_roster,
    _parse_bearer,
    _verify,
)


# ----- _parse_bearer ------------------------------------------------------

def test_parse_bearer_returns_token() -> None:
    assert _parse_bearer("Bearer abc123") == "abc123"


def test_parse_bearer_is_case_insensitive_for_scheme() -> None:
    assert _parse_bearer("bearer abc123") == "abc123"
    assert _parse_bearer("BEARER abc123") == "abc123"


def test_parse_bearer_strips_trailing_whitespace() -> None:
    assert _parse_bearer("Bearer abc123   ") == "abc123"


def test_parse_bearer_none_returns_empty() -> None:
    assert _parse_bearer(None) == ""


def test_parse_bearer_wrong_scheme_returns_empty() -> None:
    assert _parse_bearer("Basic abc123") == ""


def test_parse_bearer_empty_string_returns_empty() -> None:
    assert _parse_bearer("") == ""


# ----- _load_roster -------------------------------------------------------

def test_load_roster_returns_raw_dict(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text('{"a": {"port": 1, "password_sha256": "aa"}}', encoding="utf-8")
    assert _load_roster(f) == {"a": {"port": 1, "password_sha256": "aa"}}


def test_load_roster_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        _load_roster(tmp_path / "nope.json")


def test_load_roster_malformed_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


def test_load_roster_non_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


# ----- _verify ------------------------------------------------------------

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_verify_hit_returns_entry() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "s3cret", roster) == roster["alice"]


def test_verify_wrong_password_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "wrong", roster) is None


def test_verify_unknown_user_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("eve", "anything", roster) is None


def test_verify_empty_bearer_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "", roster) is None


def test_verify_entry_missing_hash_returns_none() -> None:
    # Malformed roster: entry has no password_sha256. Should fail closed.
    roster = {"alice": {"port": 8089}}
    assert _verify("alice", "anything", roster) is None


def test_verify_entry_malformed_hash_returns_none() -> None:
    # Non-hex hash. Should fail closed without raising.
    roster = {"alice": {"port": 8089, "password_sha256": "not-hex!"}}
    assert _verify("alice", "anything", roster) is None
```

- [ ] **Step 4.2: Run the tests; verify they fail**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -v
```
Expected: ImportError — module `app.public_clients` does not exist.

- [ ] **Step 4.3: Create `public_clients.py` with just the helpers**

```python
# compose/siteapp/app/public_clients.py
from __future__ import annotations

import hashlib
import json
import secrets as secrets_mod
from pathlib import Path

DUMMY_HASH = b"\x00" * 32  # used for constant-time miss-branch compare


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def _load_roster(path: Path) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    return raw


def _verify(username: str, bearer: str, roster: dict) -> dict | None:
    """Return the roster entry on success, None on any failure.

    Constant-time across hit/miss branches: both paths compute a single
    SHA-256 over the bearer and a single secrets.compare_digest, so the
    response time does not leak whether the username exists.
    """
    entry = roster.get(username)
    bearer_hash = hashlib.sha256(bearer.encode("utf-8")).digest()
    if entry is None:
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    try:
        expected = bytes.fromhex(entry["password_sha256"])
    except (KeyError, TypeError, ValueError):
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    if not secrets_mod.compare_digest(expected, bearer_hash):
        return None
    return entry
```

- [ ] **Step 4.4: Run the helper tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -v
```
Expected: all pass.

- [ ] **Step 4.5: Commit**

```bash
git add compose/siteapp/app/public_clients.py compose/siteapp/tests/test_routes_public_clients.py
git commit -m "$(cat <<'EOF'
feat(siteapp): public_clients helpers — roster load, bearer parse, verify

Adds the verification primitives for the upcoming /api/public/clients/
endpoint. _verify uses constant-time compare across hit/miss branches
so the response time does not leak whether a username exists. Routes
are added in a follow-up commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: TCP probe to `chisel:<port>`

**Files:**
- Modify: `compose/siteapp/app/public_clients.py`
- Modify: `compose/siteapp/tests/test_routes_public_clients.py`

- [ ] **Step 5.1: Write failing tests for `_probe_tunnel`**

Append to `test_routes_public_clients.py`:

```python
# ----- _probe_tunnel ------------------------------------------------------

import socket
from unittest.mock import patch, MagicMock


def test_probe_tunnel_open_port_returns_true() -> None:
    from app.public_clients import _probe_tunnel

    mock_sock = MagicMock()
    mock_sock.__enter__ = MagicMock(return_value=mock_sock)
    mock_sock.__exit__ = MagicMock(return_value=False)

    with patch("app.public_clients.socket.create_connection", return_value=mock_sock) as m:
        assert _probe_tunnel(8089) is True
    m.assert_called_once()
    args, kwargs = m.call_args
    assert args[0] == ("chisel", 8089)


def test_probe_tunnel_closed_port_returns_false() -> None:
    from app.public_clients import _probe_tunnel

    with patch("app.public_clients.socket.create_connection", side_effect=OSError("refused")):
        assert _probe_tunnel(8089) is False


def test_probe_tunnel_timeout_returns_false() -> None:
    from app.public_clients import _probe_tunnel

    with patch("app.public_clients.socket.create_connection", side_effect=socket.timeout):
        assert _probe_tunnel(8089) is False
```

- [ ] **Step 5.2: Run the tests; verify they fail**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -k probe_tunnel -v
```
Expected: ImportError / AttributeError — `_probe_tunnel` not defined.

- [ ] **Step 5.3: Add `_probe_tunnel` to `public_clients.py`**

Add the `socket` import and probe function to `compose/siteapp/app/public_clients.py`:

```python
# Add to the top of the file (alongside the other imports):
import socket

# Constants (alongside DUMMY_HASH):
CHISEL_HOST = "chisel"
TCP_PROBE_TIMEOUT = 0.3  # seconds; per-request, sub-millisecond on a healthy labnet


def _probe_tunnel(port: int) -> bool:
    """Return True iff TCP dial to chisel:<port> succeeded within timeout.

    chisel-server tears down the reverse listener when a client
    disconnects, so a successful connect implies an active session.
    """
    try:
        with socket.create_connection((CHISEL_HOST, port), TCP_PROBE_TIMEOUT):
            return True
    except OSError:
        return False
```

`socket.timeout` is a subclass of `OSError` in Python 3.10+, so the single `except OSError` covers both connection refused and timeout. The test asserts both paths.

- [ ] **Step 5.4: Run the tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -k probe_tunnel -v
```
Expected: all pass.

- [ ] **Step 5.5: Commit**

```bash
git add compose/siteapp/app/public_clients.py compose/siteapp/tests/test_routes_public_clients.py
git commit -m "$(cat <<'EOF'
feat(siteapp): TCP probe helper for chisel reverse port liveness

_probe_tunnel dials chisel:<port> with a 300ms timeout. chisel-server
drops the reverse listener on client disconnect, so a successful
connect is a sufficient signal that the client's tunnel is active.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `/api/public/clients/{username}` route + wire into main.py

**Files:**
- Modify: `compose/siteapp/app/public_clients.py`
- Modify: `compose/siteapp/app/main.py`
- Modify: `compose/siteapp/tests/test_routes_public_clients.py`

- [ ] **Step 6.1: Write failing route tests**

Append to `test_routes_public_clients.py`:

```python
# ----- /api/public/clients/{username} -------------------------------------

import hashlib as _hashlib_for_routes
from fastapi.testclient import TestClient


PASSWORD = "ccTMYfkmJmIQCg-ApvdjV5l4IBqZT0dD"
USERNAME = "khamit_desktop"


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch, _clients_file_default: Path):
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "irrelevant-for-this-suite")
    from importlib import reload
    import app.main
    reload(app.main)
    # raise_server_exceptions=False so 500-path tests see HTTP 500
    return TestClient(app.main.app, raise_server_exceptions=False), _clients_file_default


def _write_roster(path: Path, *, username: str = USERNAME, password: str = PASSWORD, port: int = 8089) -> None:
    pwhash = _hashlib_for_routes.sha256(password.encode("utf-8")).hexdigest()
    path.write_text(
        '{"' + username + '": {"port": ' + str(port) + ', "password_sha256": "' + pwhash + '"}}',
        encoding="utf-8",
    )


def test_public_clients_happy_path_returns_port_and_connected(app_client, monkeypatch) -> None:
    client, roster_file = app_client
    _write_roster(roster_file, port=8089)
    monkeypatch.setattr("app.public_clients._probe_tunnel", lambda port: True)

    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 200
    assert r.json() == {"port": 8089, "connected": True}


def test_public_clients_returns_connected_false_when_probe_fails(app_client, monkeypatch) -> None:
    client, roster_file = app_client
    _write_roster(roster_file, port=8089)
    monkeypatch.setattr("app.public_clients._probe_tunnel", lambda port: False)

    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 200
    assert r.json() == {"port": 8089, "connected": False}


# The enumeration-resistance cases. All must return byte-identical 401s.

def _do_401(client, roster_file, *, username: str, headers: dict) -> tuple[int, bytes, dict]:
    if username == "VALID":
        username = USERNAME
    r = client.get(f"/api/public/clients/{username}", headers=headers)
    return r.status_code, r.content, dict(r.headers)


def test_public_clients_401_responses_are_byte_identical(app_client) -> None:
    client, roster_file = app_client
    _write_roster(roster_file)

    cases = {
        "wrong_token": (USERNAME, {"Authorization": "Bearer wrong-password-zzz"}),
        "unknown_user": ("does-not-exist", {"Authorization": f"Bearer {PASSWORD}"}),
        "missing_header": (USERNAME, {}),
        "wrong_scheme": (USERNAME, {"Authorization": f"Basic {PASSWORD}"}),
    }

    results = {}
    for name, (username, headers) in cases.items():
        r = client.get(f"/api/public/clients/{username}", headers=headers)
        # Filter out headers that legitimately vary across requests.
        body = r.content
        status = r.status_code
        ignored = {"date", "server", "content-length"}
        hdrs = {k.lower(): v for k, v in r.headers.items() if k.lower() not in ignored}
        results[name] = (status, body, hdrs)

    statuses = {v[0] for v in results.values()}
    bodies = {v[1] for v in results.values()}
    headerses = [v[2] for v in results.values()]
    assert statuses == {401}, f"non-401 in {results}"
    assert len(bodies) == 1, f"non-identical bodies: {bodies}"
    assert all(h == headerses[0] for h in headerses), f"non-identical headers: {headerses}"


def test_public_clients_missing_roster_returns_500(app_client) -> None:
    client, roster_file = app_client
    roster_file.unlink()
    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 500


def test_public_clients_malformed_roster_returns_500(app_client) -> None:
    client, roster_file = app_client
    roster_file.write_text("not-json", encoding="utf-8")
    r = client.get(
        f"/api/public/clients/{USERNAME}",
        headers={"Authorization": f"Bearer {PASSWORD}"},
    )
    assert r.status_code == 500
```

- [ ] **Step 6.2: Run the tests; verify they fail**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -k public_clients -v
```
Expected: 404s on the route (no router registered yet) or import errors.

- [ ] **Step 6.3: Add the route and `make_router` to `public_clients.py`**

Append to `compose/siteapp/app/public_clients.py`:

```python
from fastapi import APIRouter, Header, HTTPException, Path as PathParam

from app.config import Settings


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/public/clients/{username}")
    def get_client(
        username: str = PathParam(..., min_length=1, max_length=128),
        authorization: str | None = Header(default=None),
    ) -> dict:
        bearer = _parse_bearer(authorization)
        roster = _load_roster(settings.clients_file)
        entry = _verify(username, bearer, roster)
        if entry is None:
            raise HTTPException(status_code=401, detail="unauthorized")
        port = int(entry["port"])
        return {"port": port, "connected": _probe_tunnel(port)}

    return router
```

- [ ] **Step 6.4: Wire the router into `app/main.py`**

```python
# compose/siteapp/app/main.py

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin import make_router as make_admin_router
from app.agent import make_router as make_agent_router
from app.api import make_router as make_api_router
from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.public_clients import make_router as make_public_clients_router
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_docs_router(settings))
app.include_router(make_agent_router(settings))
app.include_router(make_api_router(settings))
app.include_router(make_admin_router(settings))
app.include_router(make_public_clients_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6.5: Run the tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -v
```
Expected: all pass.

- [ ] **Step 6.6: Full siteapp suite — nothing else regressed**

Run:
```bash
cd compose/siteapp && uv run pytest -v
```
Expected: all pass.

- [ ] **Step 6.7: Commit**

```bash
git add compose/siteapp/app/public_clients.py compose/siteapp/app/main.py compose/siteapp/tests/test_routes_public_clients.py
git commit -m "$(cat <<'EOF'
feat(siteapp): /api/public/clients/{username} with bearer auth

Adds the public per-client lookup. Bearer token is the chisel password
the agent already holds; verified via constant-time SHA-256 compare
against the rendered roster's stored hash. All four auth-failure modes
(unknown user, wrong token, missing header, wrong scheme) return
byte-identical 401 responses to close the enumeration channel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `/api/public/health` chisel-server health route

**Files:**
- Modify: `compose/siteapp/app/public_clients.py`
- Modify: `compose/siteapp/tests/test_routes_public_clients.py`

- [ ] **Step 7.1: Write failing tests**

Append to `test_routes_public_clients.py`:

```python
# ----- /api/public/health -------------------------------------------------

import httpx


class _FakeResp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://chisel:7000/health")
            raise httpx.HTTPStatusError(
                f"http {self.status_code}", request=req, response=httpx.Response(self.status_code, request=req)
            )


def test_health_ok_when_chisel_returns_200(app_client, monkeypatch) -> None:
    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", lambda *a, **kw: _FakeResp(200))

    r = client.get("/api/public/health")
    assert r.status_code == 200
    assert r.json() == {"chisel": "ok"}


def test_health_down_when_chisel_returns_5xx(app_client, monkeypatch) -> None:
    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", lambda *a, **kw: _FakeResp(502))

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "http 502"


def test_health_down_on_timeout(app_client, monkeypatch) -> None:
    def _raise(*a, **kw):
        raise httpx.TimeoutException("slow")

    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", _raise)

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "timeout"


def test_health_down_on_connect_error(app_client, monkeypatch) -> None:
    def _raise(*a, **kw):
        raise httpx.ConnectError("refused")

    client, _ = app_client
    monkeypatch.setattr("app.public_clients.httpx.get", _raise)

    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["chisel"] == "down"
    assert body["error"] == "connecterror"


def test_health_route_does_not_require_auth(app_client) -> None:
    # No mocking — let the real httpx call fail (chisel is not running
    # in the unit-test process). What we're asserting is that the lack
    # of an Authorization header does NOT short-circuit the request.
    client, _ = app_client
    r = client.get("/api/public/health")
    assert r.status_code == 200
    # Either "ok" or "down" is fine; we're checking the route is reachable
    # without credentials.
    assert r.json()["chisel"] in {"ok", "down"}
```

- [ ] **Step 7.2: Run the tests; verify they fail**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -k health -v
```
Expected: 404 (route not registered).

- [ ] **Step 7.3: Add `httpx` import, constants, and the `/api/public/health` route**

Update `compose/siteapp/app/public_clients.py`. Add `httpx` to the imports, the URL/timeout constants, and register the new route inside `make_router`:

```python
# Add to imports:
import httpx

# Add to constants section:
CHISEL_HEALTH_URL = "http://chisel:7000/health"
HEALTH_PROBE_TIMEOUT = 1.0  # seconds
```

Inside `make_router(settings)`, add this route alongside `get_client`:

```python
    @router.get("/api/public/health")
    def get_health() -> dict:
        try:
            r = httpx.get(CHISEL_HEALTH_URL, timeout=HEALTH_PROBE_TIMEOUT)
            r.raise_for_status()
            return {"chisel": "ok"}
        except httpx.HTTPStatusError as e:
            return {"chisel": "down", "error": f"http {e.response.status_code}"}
        except httpx.TimeoutException:
            return {"chisel": "down", "error": "timeout"}
        except httpx.HTTPError as e:
            return {"chisel": "down", "error": type(e).__name__.lower()}
```

The `httpx.HTTPError` clause is the catch-all base class; it must come last because both `HTTPStatusError` and `TimeoutException` inherit from it.

- [ ] **Step 7.4: Run the tests; verify they pass**

Run:
```bash
cd compose/siteapp && uv run pytest tests/test_routes_public_clients.py -k health -v
```
Expected: all pass.

- [ ] **Step 7.5: Full siteapp suite**

Run:
```bash
cd compose/siteapp && uv run pytest -v
```
Expected: all pass.

- [ ] **Step 7.6: Commit**

```bash
git add compose/siteapp/app/public_clients.py compose/siteapp/tests/test_routes_public_clients.py
git commit -m "$(cat <<'EOF'
feat(siteapp): /api/public/health proxies chisel server health

Unauthenticated. Issues a 1s GET to chisel:7000/health and returns
{chisel: ok} on 2xx, {chisel: down, error: <reason>} on any failure.
Always returns HTTP 200 — the JSON is the signal, not the status code
— so monitoring tools don't conflate "siteapp is broken" with
"chisel is broken".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Caddy `/api/public*` handle + bats assertion

**Files:**
- Modify: `compose/Caddyfile.tmpl`
- Modify: `tests/test_render.bats`

- [ ] **Step 8.1: Write a failing bats test**

Add to `tests/test_render.bats`:

```bash
@test "render_caddyfile: handles /api/public* by reverse-proxying to siteapp" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"handle /api/public*"* ]]
    # The handle block must reverse-proxy to siteapp (not jupyter).
    # Grep for the line within ~5 lines after the handle directive.
    [[ "$(grep -A 5 'handle /api/public\*' <<< "$output")" == *"reverse_proxy siteapp:8000"* ]]
}

@test "render_caddyfile: /api/clients/ has NO handle (stays internal)" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    # The internal endpoint at /api/clients/ must NOT have its own
    # Caddy handle; it stays unreachable from the public side via the
    # jupyter catch-all. (The /api/public* handle is unrelated.)
    ! grep -qE 'handle /api/clients' <<< "$output"
}
```

- [ ] **Step 8.2: Run the bats tests; verify they fail**

Run:
```bash
bats tests/test_render.bats -f "handles /api/public\*|/api/clients/ has NO handle"
```
Expected: the `/api/public*` test fails because the handle is not yet present. The "no handle" test passes already.

- [ ] **Step 8.3: Add the `handle /api/public*` block to the Caddyfile template**

Insert into `compose/Caddyfile.tmpl` just before the `# Existing routes (unchanged).` comment / `handle /grafana/*` block:

```caddy
    # Public agent API — port lookup, connected status, chisel health.
    # Auth is enforced inside siteapp (bearer = chisel password);
    # enumeration resistance and brute-force defense live there too.
    handle /api/public* {
        reverse_proxy siteapp:8000
    }
```

- [ ] **Step 8.4: Run the bats tests; verify they pass**

Run:
```bash
bats tests/test_render.bats -f "handles /api/public\*|/api/clients/ has NO handle"
```
Expected: both pass.

- [ ] **Step 8.5: Full bats suite**

Run:
```bash
bats tests/
```
Expected: all pass (or the Docker-Hub-dependent integration suites skip cleanly).

- [ ] **Step 8.6: Commit**

```bash
git add compose/Caddyfile.tmpl tests/test_render.bats
git commit -m "$(cat <<'EOF'
feat(caddy): proxy /api/public/* to siteapp

The new public client status routes (port lookup, connected, chisel
health) live under /api/public/. Caddy delegates the whole prefix to
siteapp, which handles bearer auth itself. The existing internal
/api/clients/ stays without a Caddy handle and remains unreachable
from the public side via the jupyter catch-all.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] **Run the full siteapp pytest suite once more**

```bash
cd compose/siteapp && uv run pytest -v
```

- [ ] **Run the full bats suite once more**

```bash
bats tests/
```

- [ ] **Verify a clean working tree and a sensible commit graph**

```bash
git status
git log --oneline -8
```

Expected: working tree clean; eight new commits (one per task) on top of `bf175a8`.

---

## Out-of-scope cleanups (deferred)

- End-to-end "agent installs → fetches port → connects" integration test (crosses repo boundary).
- Caddy `/api/clients/` reachability test from the public side (the catch-all behavior is structurally enforced by existing render tests; would require spinning the fake-VPS stack).
- Replacing `httpx` with `urllib.request` to avoid the runtime dep (negligible image-size cost; httpx is the ergonomic choice for the handful of error-class branches `get_health` needs).
- Surfacing the public URL in `task secrets:add-client` output as a copy-pasteable hint for the operator.

These do not gate shipping; revisit if traffic, packaging, or operator UX feedback indicates a need.

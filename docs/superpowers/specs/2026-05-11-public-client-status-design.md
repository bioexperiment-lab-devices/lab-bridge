# Public client status & discovery — design

Status: approved (brainstorm complete; implementation plan to follow)
Date: 2026-05-11
Scope: expose three new public HTTPS routes on siteapp so a Windows lab
agent can look up its assigned chisel reverse port, check whether the
chisel server currently sees its tunnel, and probe chisel server health
for external monitoring. Bearer auth reuses the agent's existing chisel
password; siteapp stores SHA-256 hashes only.

## Problem

The Windows lab agent (in a separate repo) connects to the VPS chisel
server with a per-client username and password configured at install
time. Two things still come from outside the agent:

- **The reverse port number.** The operator hand-copies it from
  `config.yaml` into the agent installer. Every roster edit risks a
  desync between `chisel_clients[].reverse_port` and the value baked
  into the agent.
- **The connected indicator.** The agent's UI today can show its own
  local socket state, but the *server's* view of the session is the
  one that matters — a NAT or firewall flap can make the agent
  believe it's connected while chisel has dropped the session.

Plus, external monitoring would benefit from a stable HTTPS healthcheck
for the chisel server. Chisel itself exposes `GET /health` on port 7000,
but on a non-standard port that some monitoring tools refuse.

The existing internal `GET /api/clients/` endpoint
(`docs/superpowers/specs/2026-05-04-client-discovery-by-username-design.md`)
solves a related but different problem: jupyter-side library code
inside labnet looks up port-by-name with no auth. That endpoint is
internal-only and stays untouched.

## Goals

- Expose three new **public** HTTPS routes on siteapp:
  1. `GET /api/public/clients/{username}` — given username + bearer
     token = chisel password, return `{port, connected}`.
  2. `GET /api/public/health` — unauthenticated chisel-server health.
  3. (Implicit) routing under `/api/public/*` so future public,
     siteapp-served APIs have a clear namespace.
- Reuse the agent's existing chisel password as the bearer credential.
  No new secret to distribute, store, or rotate.
- Preserve the existing invariant from the internal-clients design:
  **siteapp holds no chisel passwords in plaintext** — only SHA-256
  hashes, which are not reversible and not replayable against chisel.
- Resist username enumeration: all 401 responses are byte-identical and
  produced in constant time relative to the hit/miss branches.
- Reuse the existing render → mount → restart deploy flow. No new
  operator commands.

## Non-goals

- Changes to the Windows agent itself. The agent lives in a separate
  repo and updates independently; this spec defines only the server
  contract.
- Credential issuance or rotation flows. The chisel password is already
  the credential; nothing about how it's created or rotated changes.
- Per-client metadata beyond `port` and `connected` (labels, last-seen,
  version, etc.). The response shape leaves room; this change does not
  add fields.
- Touching the internal `/api/clients/` endpoint or its consumer in
  `bioexperiment_suite`.
- Rate limiting. Bearer tokens are 256-bit random; the 401-for-everything
  rule closes the enumeration channel. Rate limiting would add
  operational state for no marginal defense. Reconsider if logs show
  abuse.
- IP allowlisting, mutual TLS, request signing. Bearer-over-TLS is
  sufficient at this stake level.

## Architecture

Four files change. No new services, no new secrets, no new operator
commands.

### Data flow

```
config.yaml                                 (operator's local machine)
  chisel_clients:
    - name: khamit_desktop
      reverse_port: 8089
      password: ccTMYfkmJmIQCg/...          (32-byte random, ~144 bits effective)
        │
        │  task render  ───►  scripts/lib/render.sh
        │                       ├─ render_chisel_users      → compose/chisel/users.json
        │                       │                             (name:password → tunnel specs)
        │                       └─ render_siteapp_clients   → compose/siteapp/clients.json
        │                                                     {name: {port, password_sha256}}
        │                                                     (passwords NEVER appear; hashes only)
        │
        │  task deploy ───►  rsync → VPS, docker compose up -d, restart siteapp
        ▼
VPS docker (labnet):
  caddy ──── handles /api/public/* ──── siteapp:8000
                                          │
                                          │  per request:
                                          │    read clients.json  (fresh each call)
                                          │    if /api/public/clients/{name}:
                                          │      verify Authorization: Bearer <password>
                                          │        via constant-time sha256 compare
                                          │      TCP dial chisel:<port>, 300 ms timeout
                                          │      → return {port, connected}
                                          │    if /api/public/health:
                                          │      GET http://chisel:7000/health
                                          │      → return {chisel: "ok"|"down"}
                                          ▼
                                       chisel:7000  (also still exposed on host:7000;
                                                     unchanged)
```

### Files touched

- `scripts/lib/render.sh` — `render_siteapp_clients` reshape (now emits
  `{port, password_sha256}` per entry instead of just an integer).
- `compose/Caddyfile.tmpl` — one new `handle /api/public*` block.
- `compose/siteapp/app/clients.py` — internal loader tolerates the new
  entry shape; response unchanged.
- `compose/siteapp/app/public_clients.py` — new module with the two
  routes, bearer verification, TCP probe, chisel health probe.
- `compose/siteapp/app/main.py` — register the new router.
- `compose/siteapp/tests/test_routes_public_clients.py` — new tests.
- `tests/test_render.bats` — extended with hash-shape and no-leak cases.

No changes to `compose/docker-compose.yml.tmpl`. The existing
`siteapp/clients.json` bind mount and `SITEAPP_CLIENTS_FILE` env var
from the prior spec are reused. The existing `docker compose restart
siteapp` already runs on every `task deploy`, so file replacements take
effect on the next deploy automatically.

## API contract

### `GET /api/public/clients/{username}`

**Request**

```
GET /api/public/clients/khamit_desktop HTTP/1.1
Host: <vps-host>
Authorization: Bearer ccTMYfkmJmIQCg/ApvdjV5l4IBqZT0dD
```

`{username}` is the `chisel_clients[].name` from `config.yaml`. The
bearer token is the matching `password`.

**200 — known user, correct token**

```json
{"port": 8089, "connected": true}
```

- `port` (int): the `reverse_port` from `config.yaml`.
- `connected` (bool): TCP dial to `chisel:<port>` from inside labnet
  succeeded within 300 ms.

**401 — anything else**

```json
{"detail": "unauthorized"}
```

Returned for all of:

- Unknown username.
- Known username, wrong token.
- Missing `Authorization` header.
- Malformed `Authorization` header (not `Bearer …`).

All four failure modes return byte-identical 401 responses (same body,
same headers). On the unknown-username path, siteapp still performs a
SHA-256 of the bearer and a constant-time compare against a fixed
all-zeros hash, so wall-clock time matches the known-user-wrong-token
path within noise. This is the enumeration defense — see "Security
model".

**500 — roster file missing or malformed**

Uncaught exception → FastAPI default 500 → uvicorn logs traceback to
stderr. These are deploy bugs, not runtime conditions the agent can
recover from. Failure mode mirrors the existing internal endpoint.

### `GET /api/public/health`

**Request** — no auth, no headers required.

**200**

```json
{"chisel": "ok"}
```

Returned when `GET http://chisel:7000/health` from inside labnet
returned a 2xx within ~1 s.

**200 with `"down"`**

```json
{"chisel": "down", "error": "connection refused"}
```

Still 200, not 5xx — this endpoint reports *information about chisel*,
not a siteapp failure. Monitoring tools should key off the `chisel`
field, not the HTTP status code. The `error` field is a short,
sanitized exception summary (`"connection refused"`, `"timeout"`,
`"http 502"`, etc.). Safe to expose: chisel's listening status is
already public knowledge because port 7000 is bound on the host.

### Headers

Standard `application/json; charset=utf-8`. No `Cache-Control` — agent
and monitoring callers set their own poll cadence.

### Caddy routing

```caddy
handle /api/public* {
    reverse_proxy siteapp:8000
}
```

Placed before the existing `/grafana/*` handle in
`compose/Caddyfile.tmpl`. The internal `/api/clients/` (no leading
`public`) is not matched by `/api/public*`; it stays internal as
before.

## Security model

Threat model: public internet attacker. Chisel passwords are assumed
unknown to the attacker; everything else (username conventions, port
ranges, deployment shape) is assumed knowable from reconnaissance.

### Authentication

Bearer token = the agent's chisel password. Verification (sketch; see
`app/public_clients.py` for the implementation):

```python
def _verify(username: str, bearer: str, roster: dict) -> dict | None:
    entry = roster.get(username)
    bearer_hash = hashlib.sha256(bearer.encode("utf-8")).digest()
    if entry is None:
        # Constant-time miss: hash bearer anyway, compare against a fixed
        # dummy. Closes the timing channel that would otherwise
        # distinguish "unknown user" from "known user, wrong token".
        secrets.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    try:
        expected = bytes.fromhex(entry["password_sha256"])
    except (KeyError, ValueError):
        secrets.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    if not secrets.compare_digest(expected, bearer_hash):
        return None
    return entry
```

- `secrets.compare_digest` for constant-time compare against the stored
  hash.
- The miss branch executes the same SHA-256 + compare so total
  wall-clock is indistinguishable.
- All 401 responses share one body (`{"detail":"unauthorized"}`) and
  identical headers — no leak via response shape either.

### Why SHA-256 (not bcrypt) is correct here

Chisel passwords are 32-byte (256-bit) cryptographic random tokens
written as 24 base64 chars in `config.yaml`. The cost to brute-force a
SHA-256 preimage of a 256-bit random input is not feasible with any
current or projected hardware.

Bcrypt's cost factor exists to slow down dictionary attacks against
low-entropy human-chosen passwords; that threat doesn't apply here.
SHA-256 also avoids per-request CPU cost that would tempt us to add
caching.

### Enumeration resistance

The 401-for-everything rule means an attacker cannot tell which
usernames exist:

| Attempt                                             | Response |
|-----------------------------------------------------|----------|
| `khamit_desktop` + wrong token                      | 401      |
| `does_not_exist` + any token                        | 401      |
| `khamit_desktop` + no Authorization header          | 401      |
| `khamit_desktop` + `Authorization: Basic …`         | 401      |

All four are byte-identical from the network. Combined with the
unguessable bearer, enumeration provides no useful signal.

### Defense in depth

- **No passwords in siteapp.** Roster file holds SHA-256 hashes only. A
  siteapp RCE leaks hashes; the hashes are not replayable against
  chisel (chisel uses plaintext compare against its own `users.json`)
  and not reversible.
- **No new public surface on chisel.** Chisel server is already public
  on `:7000`. This change does not enlarge its attack surface.
- **Internal endpoint still internal.** `/api/clients/` is unchanged
  and unreachable from the internet via the existing Caddy catch-all
  (404 from jupyter).
- **Failure-mode 500s** carry no per-user information (default FastAPI
  body, traceback to stderr only). No leak on the error path.

### What we explicitly do not do

- **No rate limiting.** With unguessable bearers and indistinguishable
  401s, an attacker has no observable to anchor a brute-force loop
  against. Rate limiting would add operational state for no marginal
  defense. If logs ever show abuse, add Caddy's built-in rate limiter
  then.
- **No IP allowlisting.** Agents run on arbitrary lab networks; we
  can't enumerate their source IPs.
- **No mutual TLS.** Bearer-over-TLS is sufficient at this stake
  level.
- **No request signing or nonces.** Bearer-over-TLS again; HMAC-signing
  every request doesn't buy anything once you have TLS + constant-time
  compare.

## Implementation

### 1. Renderer — `scripts/lib/render.sh`

`render_siteapp_clients` exists from the previous spec, currently
emitting `{name: port}`. Reshape it to:

```sh
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

yq's `@sha256` operator hashes in pure yq with no shell loop. If it
turns out unavailable on the target yq version, fall back to a shell
loop that pipes each password through `openssl dgst -sha256 -binary |
xxd -p -c 64`. Decide in the implementation plan; both produce
identical output.

### 2. Compose — no changes

The existing `siteapp/clients.json` bind mount and
`SITEAPP_CLIENTS_FILE` env var are reused. The existing
`docker compose restart siteapp` on every `task deploy` already covers
file replacements.

### 3. Caddy — `compose/Caddyfile.tmpl`

One new block, placed before the `/grafana/` handle:

```caddy
# Public agent API — port lookup, connected status, chisel health.
# Auth is enforced inside siteapp (bearer = chisel password);
# enumeration resistance and brute-force defense live there too.
handle /api/public* {
    reverse_proxy siteapp:8000
}
```

The existing internal `/api/clients/` has no Caddy handle and stays
unreachable from the public side via the jupyter catch-all (404).

### 4. Siteapp internal loader — `app/clients.py`

Tolerate the new entry shape: each value is now `{port, password_sha256}`
instead of a bare integer. The loader for the internal endpoint reads
`port` and ignores the hash field. Response shape unchanged
(`{name: {host, port}}`).

### 5. Siteapp public routes — `app/public_clients.py` (new)

```python
from __future__ import annotations
import hashlib
import json
import socket
import secrets as secrets_mod
from pathlib import Path
import httpx
from fastapi import APIRouter, Header, HTTPException, Path as PathParam

from app.config import Settings

CHISEL_HOST = "chisel"
CHISEL_HEALTH_URL = "http://chisel:7000/health"
TCP_PROBE_TIMEOUT = 0.3       # seconds
HEALTH_PROBE_TIMEOUT = 1.0    # seconds
DUMMY_HASH = b"\x00" * 32


def _load_roster(path: Path) -> dict[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    return raw


def _verify(username: str, bearer: str, roster: dict) -> dict | None:
    """Return the roster entry on success, None on any failure.
    Constant-time across hit/miss branches."""
    entry = roster.get(username)
    bearer_hash = hashlib.sha256(bearer.encode("utf-8")).digest()
    if entry is None:
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    try:
        expected = bytes.fromhex(entry["password_sha256"])
    except (KeyError, ValueError):
        secrets_mod.compare_digest(DUMMY_HASH, bearer_hash)
        return None
    if not secrets_mod.compare_digest(expected, bearer_hash):
        return None
    return entry


def _parse_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        return ""
    return authorization.split(None, 1)[1].strip()


def _probe_tunnel(port: int) -> bool:
    try:
        with socket.create_connection((CHISEL_HOST, port), TCP_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


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

    return router
```

### 6. Siteapp wiring — `app/main.py`

Register the new router alongside the existing one:

```python
from app import api, public_clients
app.include_router(api.make_router(settings))
app.include_router(public_clients.make_router(settings))
```

If `httpx` is not already in siteapp's `pyproject.toml`, add it.

## Testing

### Renderer (bats — extend `tests/test_render.bats`)

- **Hash shape** — fixture with two `chisel_clients` entries → output
  is `{name: {port, password_sha256}}`, the hash is 64 lowercase hex
  chars, and matches `sha256(password)` computed independently with
  `openssl dgst`.
- **No plaintext leak** — grep the rendered file for any password
  substring from the fixture → no match. Cheap, load-bearing
  defense-in-depth check.
- **Empty roster** — `chisel_clients: []` → output `{}`.
- **Roster mirroring** — every name in `chisel/users.json` appears in
  `siteapp/clients.json`. Catches drift if one renderer is edited and
  the other is not.

### Siteapp — auth & response shape (pytest — `compose/siteapp/tests/test_routes_public_clients.py`)

Use FastAPI's `TestClient` with a temp `clients.json` pointed at by
`Settings.clients_file`.

- **Happy path** — write roster with one entry; GET with correct
  bearer → 200, body `{port, connected}` with correct port. Stub
  `_probe_tunnel` to a known value.
- **Wrong bearer** → 401 with `{"detail":"unauthorized"}`.
- **Unknown username** → 401 with byte-identical body and headers as
  the wrong-bearer case (asserted via direct response comparison, not
  just status code).
- **Missing Authorization header** → 401, same body.
- **Malformed Authorization header** (`Authorization: Basic foo`) →
  401, same body.
- **Roster file missing / malformed / wrong shape** → 500.

### Siteapp — TCP probe (mocked socket)

`_probe_tunnel` tested directly:

- Patch `socket.create_connection` to return a context manager →
  returns `True`.
- Patch it to raise `OSError` → returns `False`.
- Patch it to raise `socket.timeout` → returns `False`.

No real network. The probe's correctness against a real chisel session
is structural (chisel tears down the listener on disconnect) and
verified by the deploy-time smoke test, not unit tests.

### Siteapp — chisel health (mocked httpx)

`/api/public/health` with `httpx.get` patched:

- 200 response → `{"chisel": "ok"}`.
- 502 response → `{"chisel": "down", "error": "http 502"}`.
- `httpx.TimeoutException` → `{"chisel": "down", "error": "timeout"}`.
- `httpx.ConnectError` → `{"chisel": "down", "error": "connecterror"}`.
- Endpoint returns 200 in all cases.

### Constant-time verification — code review, not CI

Python timing assertions are flaky and the goal is "no over-the-network
signal", not "literal cycle parity". Covered structurally: both miss
and hit branches execute one SHA-256 + one `compare_digest`. Reviewed
in PR, not asserted in CI.

### Out of scope

- End-to-end "agent installs → fetches port → connects" integration
  test. Crosses repo boundary into the Windows agent project.
- Caddy 401-leak test from the public side. Bearer-checking lives in
  siteapp; Caddy is a transparent proxy and adds no auth observable.
- Load / abuse simulation. No rate limiter to test.

## Update lifecycle

1. Operator runs `task secrets:add-client -- <name> <port>` (existing)
   — appends `{name, reverse_port, password}` to `config.yaml`.
2. Operator runs `task deploy` (existing) — re-renders
   `chisel/users.json` and `siteapp/clients.json`, rsyncs to the VPS,
   runs `docker compose up -d` followed by the existing
   `docker compose restart caddy chisel siteapp`.
3. Siteapp restarts and serves the new roster on the next request.
4. Operator hands the agent installer two values: the username and the
   chisel password. The agent fetches the port from
   `/api/public/clients/{username}` itself.
5. Removing a client is symmetric: delete from `config.yaml`, re-deploy,
   the entry stops appearing in the response (401 from then on).

## Risks and mitigations

- **Renderer drift between `chisel/users.json` and `siteapp/clients.json`.**
  The "roster mirroring" bats test catches missing names. Hash-shape
  test catches malformed entries.
- **`@sha256` operator unavailable on the target yq version.** Fall
  back to an `openssl dgst -sha256 -binary | xxd -p -c 64` shell loop.
  Both produce identical output; decision deferred to the
  implementation plan.
- **Constant-time compare regression.** If a future refactor short-
  circuits the miss branch (e.g. `if not entry: return None` without
  the dummy compare), enumeration becomes observable. Mitigation: a
  comment in `_verify` explaining why the dummy work exists, plus the
  pytest case asserting byte-identical 401 bodies across hit/miss.
- **Roster file IO per request.** Same trade-off as the internal
  endpoint: file is small, endpoint is low-traffic, simplicity wins
  over caching. Revisit if traffic patterns change.
- **Unhandled `httpx` errors in `get_health`.** Every error path from
  `httpx.get` must be caught and mapped to `{"chisel": "down"}`; an
  unhandled exception turns the health endpoint into a 500, which
  would falsely indicate siteapp itself is broken. The
  `except httpx.HTTPError` final clause is the catch-all.
- **Bearer leaked in access logs.** Uvicorn's default access log does
  not log request headers, so the bearer should not appear. Confirm
  during implementation that no middleware adds header logging.
- **Hardcoded chisel port 7000 in `CHISEL_HEALTH_URL`.** The
  `chisel.listen_port` in `config.yaml` is technically configurable
  (default 7000). Same rationale as `CHISEL_HOST` in the prior spec:
  changing the chisel port is a rare, deliberate operation that
  already requires multi-file edits; a single constant in siteapp is
  fine. Revisit only if the port becomes per-deployment-variable.

# Client discovery by username — design

Status: approved (brainstorm complete; implementation plan to follow)
Date: 2026-05-04
Scope: add an internal-only HTTP endpoint on siteapp that returns the
roster of `chisel_clients` as a `name → {host, port}` map, so callers
inside the docker network can resolve a lab machine's chisel-tunnel
endpoint by username instead of hardcoding a port.

## Problem

`bioexperiment_suite` (a Python library used inside the `jupyter`
container to drive lab devices) currently reaches each lab machine
through the chisel reverse tunnel, addressed as `chisel:<port>` on
`labnet`. The port is wired into notebooks as a constant:

```python
LAB_DEVICES_PORT = 8089  # khamit_desktop's reverse port
client = LabDevicesClient(port=LAB_DEVICES_PORT)
```

The mapping of lab machine to port lives in `config.yaml` under
`chisel_clients[]` and is rendered into `compose/chisel/users.json` at
deploy time. The library has no way to look up that mapping at
runtime, so notebook authors must (a) know the port number and (b)
keep it in sync with `config.yaml` by hand. As soon as a second client
exists, this gets brittle.

The goal is a runtime API:

```python
LAB_DEVICES_USERNAME = "khamit_desktop"
client = LabDevicesClient(user=LAB_DEVICES_USERNAME)
```

This spec covers the *server-side capability* only — the JSON endpoint
and the data flow that feeds it. The matching `LabDevicesClient(user=…)`
constructor in `bioexperiment_suite` is explicitly out of scope; that
package is updated separately and can be planned once this endpoint
exists.

## Goals

- Expose `GET /api/clients/` on siteapp returning a JSON map of
  every configured `chisel_clients` entry to its tunnel endpoint:
  `{"<name>": {"host": "chisel", "port": <int>}, …}`.
- Keep the endpoint reachable only from the docker network. Public
  HTTPS callers must not be able to enumerate the roster.
- Keep chisel client passwords out of the siteapp container.
- Reflect roster edits without rebuilding the siteapp image — a
  `task deploy` (or even a manual file replacement) is enough.
- Mirror the existing render → mount → restart workflow used for
  `chisel/users.json`. No new operator commands.

## Non-goals

- Updating `bioexperiment_suite` to consume the endpoint. Out of scope;
  separate package, separate plan.
- Per-client metadata beyond `host` and `port` (labels, last-seen,
  health, etc.). The structured response shape leaves room for these
  but they are not added in this change.
- A single-client endpoint (`GET /api/clients/<name>`). Callers do
  `roster[name]` themselves; if the name is missing they get a
  `KeyError` at their layer, which is the right place for that error
  to surface.
- Authentication/authorization on the endpoint. The boundary is the
  docker network — see "Security model" below.
- Hot reload signalling. Roster changes take effect on the next
  request because siteapp re-reads the file each time.

## Architecture

Three layers change. No new services, no new auth, no new public
surface area.

### 1. Renderer

`scripts/lib/render.sh` gains a sibling to `render_chisel_users`:

```sh
# render_siteapp_clients <output_path>
# Builds the siteapp clients.json from .chisel_clients in CONFIG_PATH.
# Output is a flat name → port map. Passwords are deliberately omitted.
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

The function is invoked from `scripts/deploy.sh` immediately after
the existing `render_chisel_users` call (currently line 28). Output
path: `<staging>/siteapp/clients.json`.

The `chisel` hostname is **not** rendered into this file. It is a
deployment constant (the docker compose service name) and lives in
siteapp code instead. Rationale: storing a constant once in code beats
repeating it per entry, and it isolates renderer changes from app
changes.

### 2. Compose

`compose/docker-compose.yml.tmpl` — siteapp service gets one extra
read-only volume entry:

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

Mount path is outside the existing `/data` volume so runtime data
(docs, agent binaries) and read-only config (the roster) stay
separated. The path is passed via `SITEAPP_CLIENTS_FILE` rather than
hardcoded so tests can point the app at a temp file.

No change to `compose/Caddyfile.tmpl`. The Caddy config has no
`handle /api/clients*` block, so the catch-all `reverse_proxy
jupyter:8888` receives any public request and 404s. Internal
containers on `labnet` reach `siteapp:8000` directly.

`scripts/deploy.sh` adds `siteapp` to the explicit `docker compose
restart` list (currently `caddy chisel`, becomes `caddy chisel
siteapp`). Reasoning: single-file bind-mounts pin the host-side
inode at mount time. When `task deploy` rsyncs a new
`siteapp/clients.json`, it lands at a new inode; the original mount
still resolves to the old inode, so the container would read stale
content forever without an explicit restart. This is the same
problem `chisel/users.json` solves with the existing restart, and the
fix is symmetric.

### 3. Siteapp

A new module `compose/siteapp/app/clients.py` and a route in
`compose/siteapp/app/api.py`.

**`Settings`** (`compose/siteapp/app/config.py`) gains:

```python
clients_file: Path  # path to read-only roster JSON
```

`load_settings()` reads `SITEAPP_CLIENTS_FILE` and stores it as a
`Path`. No existence check at startup — see error handling.

**`app/clients.py`**:

```python
from pathlib import Path
import json

CHISEL_HOST = "chisel"  # docker compose service name on labnet

def load_roster(path: Path) -> dict[str, dict[str, object]]:
    """Read and reshape the rendered roster file.

    Returns the response-ready map: {name: {"host": ..., "port": int}}.
    Raises on missing file or malformed JSON; the route layer turns
    those into 500s.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("clients.json must be a JSON object")
    out: dict[str, dict[str, object]] = {}
    for name, port in raw.items():
        if not isinstance(name, str) or not isinstance(port, int):
            raise ValueError(f"invalid roster entry: {name!r} -> {port!r}")
        out[name] = {"host": CHISEL_HOST, "port": port}
    return out
```

**`app/api.py`** gains a route:

```python
@router.get("/api/clients/")
def list_clients() -> dict[str, dict[str, object]]:
    return load_roster(settings.clients_file)
```

Exceptions (missing file, malformed JSON, wrong shape) propagate.
FastAPI converts uncaught exceptions to `500 Internal Server Error`
and uvicorn writes the traceback to stderr — same handling pattern
the existing `upload_agent` flow relies on. The endpoint is
internal-only, so the default response body is acceptable; no custom
detail string is needed.

The roster is re-read on every request. The file is small (one
integer per client) and the endpoint is internal/low-traffic, so the
IO cost is negligible. The benefit isn't live-edit-without-restart
(single-file bind mounts pin the inode — see "Compose" above), it's
**implementation simplicity and testability**: no startup hook, no
cache invalidation logic, and tests can mutate the file between
requests without restarting the app.

## Data flow

```
config.yaml                                 (operator's local machine)
  chisel_clients:
    - name: khamit_desktop
      reverse_port: 8089
      password: <secret>                    (passwords stay here only)
        │
        │  task render  ───►  scripts/lib/render.sh
        │                       ├─ render_chisel_users   → compose/chisel/users.json
        │                       │                          (with passwords)
        │                       └─ render_siteapp_clients → compose/siteapp/clients.json
        │                                                  (no passwords)
        │
        │  task deploy ───►  rsync staging dir → VPS:/srv/lab-bridge/
        │                    docker compose up -d
        ▼
VPS docker (labnet):
  siteapp container
    /etc/siteapp/clients.json   (read-only mount)
        │
        │  GET /api/clients/   (only reachable from labnet)
        │   reads file each request
        ▼
  caller (e.g. jupyter)  ──►  http://siteapp:8000/api/clients/
                              ◄── {"khamit_desktop": {"host": "chisel", "port": 8089}}
```

## API contract

### Request

```
GET /api/clients/
Host: siteapp:8000
```

No request body, no parameters, no required headers. No auth — see
"Security model".

### 200 — full roster

```json
{
  "khamit_desktop": {"host": "chisel", "port": 8089},
  "another_lab":    {"host": "chisel", "port": 8090}
}
```

Keys are the `chisel_clients[].name` strings exactly as they appear
in `config.yaml`. Values are objects with two fields:

- `host` (string) — always `"chisel"` in the current deployment;
  callers should treat it as opaque, not assume the literal value.
- `port` (integer) — the `reverse_port` from `config.yaml`.

The structured value shape (rather than a `"chisel:8089"` string) lets
us add fields later (labels, last-seen, etc.) without breaking
callers.

### 200 — empty roster

```json
{}
```

Returned when `chisel_clients` is absent or empty. This is a valid
state for a fresh deployment with no lab machines yet.

### 500 — file missing, unreadable, or malformed

The mount is required infrastructure. Missing file, JSON parse error,
or shape mismatch (top-level not a dict, entry value not an int,
etc.) all propagate as uncaught exceptions. FastAPI returns the
default `500 Internal Server Error` body; uvicorn logs the traceback
to stderr. These are deploy bugs, not runtime conditions the caller
can recover from — failing loudly is the right behavior.

### Siteapp test layer

Tests assert *status code* 500 for the failure cases; the response
body is not contractual.

### Headers

Standard `application/json; charset=utf-8`. No `Cache-Control` —
server already re-reads per request, and callers shouldn't cache
either.

## Security model

The endpoint has no in-app authentication. The boundary is the docker
network:

- `compose/Caddyfile.tmpl` does not have a `handle /api/clients*`
  block. The catch-all `reverse_proxy jupyter:8888` receives any
  public request to that path; jupyter responds 404. So the endpoint
  is unreachable from the public internet.
- siteapp's port 8000 is not published to the host (the service has
  no `ports:` entry, only `networks: [labnet]`). Other compose
  services on `labnet` (jupyter, chisel, grafana, loki, caddy) can
  reach it directly.
- Anything inside `labnet` already has more direct paths to chisel
  than any token check could meaningfully gate. Adding bearer auth
  would be theatre.

The roster file inside the container does **not** contain passwords.
Even if siteapp were compromised, it cannot disclose chisel
credentials it never received.

## Testing

### Renderer (bats — `tests/test_render.bats`)

- **Happy path** — fixture `config.yaml` with two `chisel_clients`
  entries → `render_siteapp_clients` writes JSON equal to
  `{"khamit_desktop": 8089, "another_lab": 8090}`. Compared with `jq`
  equality, not string match, to keep the test independent of key
  order and whitespace.
- **Empty roster** — fixture with `chisel_clients: []` → output is
  `{}` (not `null`, not missing).
- **No password leak** — output JSON, grep'd for any password
  substring from the fixture, returns no match. Cheap defense-in-depth
  check that the renderer never accidentally projects more fields.
- **Roster mirroring** — for every name in `chisel/users.json`, the
  same name appears in `siteapp/clients.json`. Catches drift if
  someone edits one renderer and forgets the other.

### Siteapp (pytest — `compose/siteapp/tests/`)

- **Happy path** — write a temp `clients.json`, point
  `Settings.clients_file` at it, hit the endpoint via FastAPI's
  `TestClient`, assert response equals the structured map with
  `host: "chisel"` injected.
- **Empty roster** — file contains `{}` → response `{}`, status 200.
- **Re-read on each request** — write file, hit endpoint, mutate file
  on disk, hit endpoint again, assert second response reflects the
  mutation. Load-bearing test for the "no cache" decision.
- **Missing file** — `Settings.clients_file` points at nonexistent
  path → 500.
- **Malformed JSON** — file contains `not-json` → 500.
- **Wrong shape** — file contains `[1,2,3]` (not an object) → 500.

The siteapp test file `compose/siteapp/tests/test_routes_api.py`
already exists for the agent-upload endpoint; new cases attach there
rather than spawning a parallel file.

### Out of scope

- End-to-end "jupyter container hits siteapp" integration test. The
  two test layers above cover the contract; the wiring (Caddy doesn't
  proxy this path, siteapp is on labnet) is structurally enforced by
  files already covered by existing deploy tests.
- Caddy 404 verification for `/api/clients/` from the public side.
  The catch-all behaviour is already verified by the existing
  Caddyfile tests.

## Update lifecycle

1. Operator runs `task secrets:add-client` (existing) — appends a new
   entry under `chisel_clients` in `config.yaml`.
2. Operator runs `task deploy` (existing) — re-renders both
   `chisel/users.json` and `siteapp/clients.json`, rsyncs them to
   the VPS, runs `docker compose up -d` followed by an explicit
   `docker compose restart caddy chisel siteapp`.
3. siteapp restarts and serves the new roster on the next request.
   The restart is required because single-file bind mounts pin the
   inode (the container would otherwise keep reading the pre-rsync
   content); the per-request file read alone is not sufficient.
4. Removing a client is symmetric: delete from `config.yaml`,
   re-deploy, the entry stops appearing in the response.

## Risks and mitigations

- **Renderer drift** — chisel users.json and siteapp clients.json
  could disagree if one renderer is edited and the other isn't. The
  "roster mirroring" bats test catches this.
- **Public exposure regression** — someone could later add a
  `handle /api/*` block to Caddy that incidentally proxies
  `/api/clients/`. Mitigation: a Caddyfile test asserting that
  `/api/clients/` is *not* proxied to siteapp from the public side.
  (Deferred to the implementation plan to decide whether to add this
  test now or rely on review.)
- **Per-request file IO** — if the endpoint becomes high-traffic
  later, the no-cache decision may need revisiting. Today it's used
  by a handful of notebooks; not a concern.
- **Hostname constant in code** — if the chisel service is ever
  renamed in compose, `CHISEL_HOST` in `app/clients.py` must be
  updated in lockstep. Acceptable: renaming compose services is a
  rare, deliberate operation and would already require multi-file
  edits.

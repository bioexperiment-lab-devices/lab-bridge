# `/api/public/server-info` — server-as-source-of-truth for agent bootstrap

**Date:** 2026-05-11
**Status:** Approved
**Audience:** Maintainers of `lab-bridge` (this repo) and `lab_devices_client` (separate repo).
**Companion (client-side):** `2026-05-11-server-info-client-spec.md` (to be authored alongside this design).
**Pairs with:**
- `2026-05-04-client-discovery-by-username-design.md` — internal `/api/clients/`.
- `2026-05-11-public-client-status-design.md` — the public `/api/public/clients/{username}` and `/api/public/health` routes this design extends.

## Purpose

Today, a chisel-client agent has to be configured with several pieces of data the server already owns: the chisel listen port (e.g. `8080`), the loki push URL (`http://127.0.0.1:3100/loki/api/v1/push`), and the chisel forward-tunnel arg (`127.0.0.1:3100:loki:3100`). When the server changes any of those — operator bumps `chisel.listen_port`, or we re-wire the loki tunnel — every agent must be reconfigured by hand.

This design adds one unauthenticated HTTPS endpoint, `GET /api/public/server-info`, that returns those server-known values as a single JSON document. The agent fetches it once at startup, uses the values to construct its chisel invocation and log-shipper, and stops carrying that data in its local config.

This is part one of a three-part program (per brainstorming notes 2026-05-11):

1. **Shrink the agent's local config** — this design.
2. Agent self-update metadata (`agent.{version,sha256,url}`) — follow-up; drops into this same response under a new top-level `agent` object.
3. Chisel host-key fingerprint pinning (`chisel.fingerprint`) — follow-up; drops into the existing `chisel` object.

The endpoint shape is chosen so (2) and (3) are purely additive.

## Goals

- Expose the server-known values an agent needs to bootstrap a chisel + log-shipping session, from one HTTPS endpoint, with no per-user auth.
- Keep the existing `/api/public/clients/{username}` endpoint unchanged; agents poll *that* for per-user state (`port`, `connected`). `server-info` is the orthogonal "config the server publishes" channel.
- Leave room in the schema for the host-key-fingerprint and agent-update follow-ups without a schema break.

## Non-goals

- Authenticating `server-info`. The values it exposes have the same exposure profile as `/api/public/health` — see "Auth posture" below.
- Making the forward-tunnel wiring (`loki:3100`) operator-configurable via `config.yaml`. Today it's a wired-in feature of the compose stack and chisel allow-list; moving it to data is a separate piece of work that does not serve the "shrink agent config" goal. See "Forward-tunnel constants" below.
- Removing `chisel_listen_port` from the client-side config schema in this repo. That change lives in `lab_devices_client`; this repo only ships the server-side endpoint and the client-spec doc that authorizes it.

## Endpoint

### Route

```
GET /api/public/server-info
```

- **Auth:** none.
- **Caddy:** no changes — already routed by the existing `handle /api/public*` block in `compose/Caddyfile.tmpl`.
- **Body:** see below. Stable across users; cacheable.

### 200 response

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

Field rationale:

- **`chisel.listen_port`** (int): the public port `chisel server` listens on, from `config.yaml.chisel.listen_port`. The agent uses this as `<vps-host>:<chisel_listen_port>` in `chisel client`. Today the agent carries this in its own config; after this change, it's discovered.
- **`chisel.*`** is an object (not a flat `chisel_listen_port`) so that `chisel.fingerprint` lands cleanly later.
- **`loki.push_url`** (string): the application-level URL the log shipper POSTs to. Already hardcoded in `2026-04-28-chisel-client-logs-client-spec.md` as `http://127.0.0.1:3100/loki/api/v1/push`. Moving it server-side means the path component (`/loki/api/v1/push`) can later change in lockstep with a Loki upgrade without re-publishing the agent.
- **`forward_tunnels`** (list of objects): the data the chisel `client` invocation literally needs as `-L` args. Each entry has `name` (free-form, for client logging only), `local` (the lab-machine side, `host:port`), and `remote` (the labnet side, `service:port`). Today the list has exactly one entry (`loki`); leaving it a list makes a future second forward target an additive change.

### Error responses

- `500` only on a server programmer error (e.g. a future code path mis-shapes the response). The values are read from a module-level constant + env-var at boot, so a misconfigured deploy fails siteapp startup, not this request.
- No 4xx path — the endpoint takes no input to validate.

## Server-side wiring

Two sources feed the response:

### `chisel.listen_port` — from `config.yaml` via env var

The value already exists in `config.yaml.chisel.listen_port` and is exported by `scripts/lib/config.sh:113` as `$CHISEL_LISTEN_PORT`. Thread it into the siteapp container:

1. **`compose/docker-compose.yml.tmpl`** — add to the `siteapp.environment` block:

   ```yaml
   environment:
     SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
     SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
     SITEAPP_CHISEL_LISTEN_PORT: __CHISEL_LISTEN_PORT__
   ```

2. **`scripts/lib/render.sh`** — the existing template substitution already handles `__CHISEL_LISTEN_PORT__` for the `chisel` service block (see `compose/docker-compose.yml.tmpl:38`). Confirm the same substitution applies to the new line; no new render helper is needed.

3. **`compose/siteapp/app/config.py`** — read into `Settings`:

   ```python
   chisel_listen_port: int

   # in load_settings():
   port_env = os.environ.get("SITEAPP_CHISEL_LISTEN_PORT")
   if not port_env:
       raise RuntimeError("SITEAPP_CHISEL_LISTEN_PORT env var is required")
   chisel_listen_port = int(port_env)  # ValueError surfaces as boot crash, which is correct
   ```

   Fail-fast at boot, same posture as `SITEAPP_CLIENTS_FILE`.

### Forward-tunnel constants — hardcoded in siteapp

The `loki.push_url` and the single `forward_tunnels` entry are constants of the current deployment topology. They are wired into the chisel server's allow-list (`compose/chisel-users.json.tmpl`) and into the compose service definition (`loki` service name + port). None of those values vary per-deploy today.

Define them as module-level constants in a new file:

```python
# compose/siteapp/app/server_info.py

LOKI_PUSH_URL = "http://127.0.0.1:3100/loki/api/v1/push"
FORWARD_TUNNELS = [
    {"name": "loki", "local": "127.0.0.1:3100", "remote": "loki:3100"},
]
```

When (and only when) the forward-tunnel topology becomes operator-configurable (e.g. a metrics push gateway is added), promote these to `config.yaml` and render them in. Until then, the constants live next to the route that serves them, with a comment that says "if you change the chisel forward-target wiring in `compose/chisel-users.json.tmpl` or the loki service, update these too."

### Route registration

New file `compose/siteapp/app/server_info.py` exports a `make_router(settings)` returning an `APIRouter` with `GET /api/public/server-info`. Mount it in `compose/siteapp/app/main.py` next to the existing `public_clients` mount.

```python
# server_info.py
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

## Auth posture

Unauthenticated, deliberately.

- **`chisel.listen_port`** is bound on a public TCP port. A port scan reveals it in seconds.
- **`loki.push_url`** points at `127.0.0.1:3100` — the lab machine's local end of a forward tunnel. Outside a chisel session, the URL is unreachable; learning the string buys an attacker nothing.
- **`forward_tunnels[].remote`** (`loki:3100`) is an internal Docker service name on `labnet`. It's discoverable only by callers who already have chisel auth (in which case they already know it).
- The endpoint has **no per-caller branching** — it can't be an enumeration oracle the way `/api/public/clients/{username}` is, so the elaborate constant-time-compare gymnastics in `public_clients.py` are not needed here.

The exposure profile matches `/api/public/health`. We accept the same posture for the same reasons.

## Client contract changes

A companion document, `docs/superpowers/specs/2026-05-11-server-info-client-spec.md`, will be authored alongside this design and committed in the same change. It tells `lab_devices_client` how to consume the endpoint:

- **At startup**, before any `chisel client` invocation: GET `https://<vps-host>/api/public/server-info`. Cache the response for the lifetime of the chisel session.
- **On chisel reconnect after a failed dial**, re-fetch — the server's wiring may have changed.
- **Use** `chisel.listen_port` as the chisel server port. **Use** `forward_tunnels[].{local,remote}` to construct chisel `-L` args. **Use** `loki.push_url` as the log-shipper POST target.
- **Local-config migration**: remove `chisel_listen_port` from the agent's local config schema. If a stale value is present, prefer the server's value and log one WARN line so operators get a clean signal to remove it.
- **Cross-link**: the existing `2026-04-28-chisel-client-logs-client-spec.md` will gain a short note pointing to this new spec so anyone reading the log-shipping contract finds the bootstrap step.

The companion doc is the authoritative client-side contract; this design only summarizes it for self-containedness.

## Testing

### siteapp pytest

New file `compose/siteapp/tests/test_server_info.py`:

- **Happy path** — GET returns 200 with the configured shape; the `chisel.listen_port` value equals what `SITEAPP_CHISEL_LISTEN_PORT` was set to in the test fixture; `loki.push_url` and `forward_tunnels` match the module constants.
- **Boot guard** — `load_settings()` raises `RuntimeError` when `SITEAPP_CHISEL_LISTEN_PORT` is unset, matching the pattern for `SITEAPP_CLIENTS_FILE`.
- **No auth** — the request succeeds with no `Authorization` header (regression guard: catches an accidental `Depends(...)` on the route in a future refactor).

### Bats (render layer)

Add one bats assertion to the existing `compose/docker-compose.yml.tmpl` render suite: after `render_compose`, the siteapp service's environment contains `SITEAPP_CHISEL_LISTEN_PORT: <expected>` where `<expected>` matches `config.yaml.chisel.listen_port`.

### Caddyfile

No new assertion strictly required — the existing `handle /api/public*` block routes the new path. As cheap insurance, the existing Caddyfile bats suite can grep for the absence of a `/api/public/server-info` *override* block (any deploy that adds one is suspect).

### Deploy health check

The existing `task deploy` post-deploy probe already hits `/api/public/health`. Extend it (in `scripts/deploy.sh`) to also hit `/api/public/server-info` and assert the body parses as JSON containing `.chisel.listen_port`. A misrouted Caddy handle or a missing env var fails the deploy.

## Forward compatibility

The two parked follow-ups slot in additively:

- **Chisel host-key fingerprint pinning** — add `chisel.fingerprint` (string) alongside `chisel.listen_port`. Compute or read at boot from chisel's host key file; expose. The client spec then says: pass `--fingerprint <value>` to `chisel client`. No schema break.
- **Agent self-update metadata** — add a top-level `agent` object: `{"version": "1.4.2", "sha256": "...", "url": "https://<vps>/download/agent/windows/agent.exe", "size": 12345}`. Source is the existing `agent_root/meta.json` (already populated by `POST /api/agent/upload`); the route handler calls `load_meta(settings.agent_root)` and serializes it. No schema break.

Neither follow-up forces a rewrite of fields landed in this design.

## Out of scope

- Caching headers on the response. Clients control their own caching; the body is ~150 bytes and a Caddy keep-alive call is cheap.
- Rate limiting beyond what Caddy already applies globally. The endpoint is read-only and constant-time.
- A websocket / push channel for server-info changes. Operators run `task deploy` to change any of these values; agents re-fetch on reconnect.
- Operator-driven configuration of forward tunnels (the deferred "(b)" from brainstorming). Open this work when a second forward target appears.

## Summary of changes

| File | Change |
|---|---|
| `compose/docker-compose.yml.tmpl` | Add `SITEAPP_CHISEL_LISTEN_PORT: __CHISEL_LISTEN_PORT__` to siteapp env. |
| `compose/siteapp/app/config.py` | Add `chisel_listen_port: int` to `Settings`; read + validate at boot. |
| `compose/siteapp/app/server_info.py` | New file: route + module constants. |
| `compose/siteapp/app/main.py` | Mount the new router. |
| `compose/siteapp/tests/test_server_info.py` | New pytest file. |
| `compose/siteapp/tests/conftest.py` | Set `SITEAPP_CHISEL_LISTEN_PORT` for app-boot test fixtures, alongside the existing `SITEAPP_CLIENTS_FILE` setup. |
| `tests/...` (bats) | Assert the new env-var line renders into `docker-compose.yml`. |
| `scripts/deploy.sh` | Extend post-deploy health probe to also GET `/api/public/server-info`. |
| `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` | New companion client-side contract. |
| `docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md` | One-line cross-link to the new spec. |

Net: one new endpoint, one new env var, one new module, two new test files, one doc update, one new doc, one deploy-script line.

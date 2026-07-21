# Remote admin update — server-side reachability (design)

Date: 2026-07-21
Status: approved (brainstorm)
Related: SerialHop agent v2.4.0 `docs/superpowers/specs/2026-07-21-remote-admin-update-design.md`
(agent repo `bioexperiment-lab-devices/serialhop`, §4 API / §7 security / §8 this prerequisite)

## 1. Problem

The SerialHop agent (Windows client) shipped admin-pushed remote updates in
v2.4.0. Each agent now exposes two new REST endpoints on its `/agent/*`
management surface, reverse-tunneled to the `chisel` service and reachable per
lab at `http://chisel:<port>`:

- `POST /agent/update` — trigger an update (async).
- `GET  /agent/update/status` — last outcome; survives the install restart.

Nothing on the server makes these reachable to an operator. This work adds the
**server-side prerequisite**: an Authelia admin-gate plus a dispatch route that
proxies the two endpoints to a chosen lab's agent over the tunnel. It mirrors
exactly how `/flash` is gated and routed today.

## 2. Scope

**In scope (this PR):**
- Authelia access-control rule restricting the update path to `group:admins`.
- A siteapp proxy handler that forwards `POST /agent/update` and
  `GET /agent/update/status` to the selected lab's `chisel:<port>`, passing the
  agent's status code and body back through faithfully.
- Caddy route wiring the edge path to siteapp behind `forward_auth`.
- Tests across the three tiers (Authelia e2e gating, siteapp unit, Caddy smoke).

**Out of scope (follow-up PR):**
- A web UI (lab picker → trigger → poll status), flasher-style.
- The navbar entry for that UI. **When built, it must be admin-only and placed
  _above_ the flasher entry** (user requirement, recorded here so it isn't lost).

## 3. Decisions

### 3.1 Owner service: **siteapp**

The update endpoints belong to the agent's `/agent/*` *management* surface — the
same namespace as `/agent/info`, which siteapp already fans out to
(`app/labs.py:_probe_one` → `http://chisel:<port>/agent/info`). siteapp already
owns roster→chisel-port resolution (`app/clients.py:load_roster`) and a thin
httpx passthrough style that fits "return the agent's status/body verbatim."

The flasher reaches the *same* agent but on a different surface (`/serial/*`,
`/flash/{port}`), and its `SerialHopClient` deliberately transforms non-200
responses into typed exceptions — the opposite of faithful passthrough. Its only
edge over siteapp (an existing admin gate + a future UI) does not apply to an
API-only scope, where the gate is a single Authelia rule attachable anywhere.

### 3.2 Edge path: `/api/admin/labs/{name}/update`

- `POST /api/admin/labs/{name}/update`        → agent `POST /agent/update`
- `GET  /api/admin/labs/{name}/update/status` → agent `GET  /agent/update/status`

Matches siteapp's established `/api/*` JSON-API convention (`/api/public/*`,
`/api/auth/*`), signals admin + JSON (not an HTML page), keeps the resource
hierarchy explicit (a lab has an `update` sub-resource with a `status`), and
leaves room for a future `/api/admin/*` family. The whole family is gated
`^/api/admin/.*` → `group:admins`.

### 3.3 Auth model: edge-only, mirroring `/flash`

Gating is enforced at the edge exactly as `/flash*` is: an Authelia
access-control rule + Caddy `forward_auth`. Neither siteapp nor flasher performs
an app-layer group re-check today, so this design adds none — introducing one
here would be novel and inconsistent. (Defense-in-depth via an app-layer check
is noted as a possible future hardening, not built now.)

## 4. Agent contract being proxied (reference)

`POST /agent/update` — JSON body selects the source:

| Body                                                        | Meaning                        |
|-------------------------------------------------------------|--------------------------------|
| `{}`                                                        | latest GitHub release          |
| `{"version":"v2.3.0"}`                                      | that GitHub release tag        |
| `{"url":"https://…/SerialHop-v2.3.0.exe","sha256":"<hex>"}` | custom mirror                  |

Responses:

| Code | Body                                                | Meaning                                   |
|------|-----------------------------------------------------|-------------------------------------------|
| 202  | `{"accepted":true,"to":"2.3.0"}`                    | job started (async)                       |
| 200  | `{"outcome":"noop","reason":"already at 2.3.0"}`   | already current                           |
| 400  | `{"error":…,"detail":…}`                            | bad body / url / sha / version            |
| 404  | `{"error":"not found"}`                             | feature **disabled** on that agent        |
| 409  | `{"error":"update in progress"}`                    | a job is already running                  |
| 502  | `{"error":"release lookup failed",…}`              | GitHub lookup failed                      |

`GET /agent/update/status` → `{"state":…,"from":…,"to":…,"started_at":…,"finished_at":…}`
where `state ∈ none | downloading | verifying | installing | succeeded |
rolled_back | failed`. `downloading` may carry `pct`; `failed`/`rolled_back`
carry `error`.

Behavioral note: the install **restarts** the agent service. The triggering POST
is answered (202) *before* the restart, so it does not hang. Progress is observed
by **polling** status afterward; a brief tunnel drop during the restart window is
expected, not an error.

## 5. Components

### 5.1 Authelia rule (`services/authelia/config/configuration.yml.tmpl`)

Add, copying the `^/flash.*` rule's policy/subject verbatim:

```yaml
    - domain: __VPS_HOST__
      resources:
        - '^/api/admin/.*'
      policy: one_factor
      subject: 'group:admins'
```

The same rule is added to the Authelia e2e fixture
(`services/authelia/tests/e2e/fixtures/configuration.yml`, `domain: test.local`)
so the gating tests exercise it. (The fixture is a hand-maintained rendered copy,
already divergent from the tmpl — no render-sync test asserts equality; verified
during implementation.)

### 5.2 Caddy route (`compose/Caddyfile.tmpl`)

New `handle` block mirroring `/flash*`, placed with the other siteapp routes:

```
    handle /api/admin/* {
        import authelia_required
        reverse_proxy siteapp:8000 {
            header_up -Accept-Encoding
        }
    }
```

`forward_auth` verifies with a pinned `GET` sub-request against the un-stripped
URI, so a researcher POST resolves to 403 and an admin POST proceeds with its
body intact to siteapp (identical to how gated `/flash` POSTs already work). The
block must precede the catch-all; ordering relative to the public `/api/public*`
and `/api/auth/*` handles is irrelevant (Caddy matches the most specific `handle`).

### 5.3 siteapp proxy handler (`services/siteapp/app/agent_update.py`, new)

`make_router(settings, *, host="chisel") -> APIRouter`, registered in
`app/main.py`. Constants mirror `labs.py` (`CHISEL_HOST`, timeouts).

Resolve `name` → port via `load_roster(settings.clients_file)` (reused from
`app.clients`). Forward with `httpx.AsyncClient`.

**`POST /api/admin/labs/{name}/update`:**
1. Load roster. Unknown `name` → `404 {"error":"unknown lab","detail":name}`
   (distinct body from the agent's own 404).
2. Forward the **raw request body bytes** (content-type `application/json`) to
   `http://chisel:<port>/agent/update`. Do not re-parse or re-validate — the
   agent owns body validation, so its `400`s pass straight through.
3. Return the agent's **status code + body bytes verbatim** (see §6 for the
   single exception, the disabled-404).

**`GET /api/admin/labs/{name}/update/status`:**
1. Load roster; unknown `name` → `404 {"error":"unknown lab",…}`.
2. Forward to `http://chisel:<port>/agent/update/status`; return status + body
   verbatim.

Timeouts: POST uses a generous timeout (the agent may do a synchronous GitHub
release lookup before returning 202/502) — `UPDATE_POST_TIMEOUT_S = 30.0`. GET
status is a fast local read — `STATUS_TIMEOUT_S = 5.0`.

## 6. Proxy response semantics

The default is **verbatim passthrough** of the agent's status code and body
bytes (preserving 202 / 200 / 400 / 409 / 502 exactly). Three cases are handled
explicitly:

1. **Unknown lab** (name not in roster) → `404 {"error":"unknown lab","detail":name}`.
   This never reaches the tunnel.
2. **Agent-disabled 404** (we reached the agent and it returned HTTP 404) → keep
   status **404**, but replace the ambiguous `{"error":"not found"}` body with a
   clear one:
   ```json
   {"error":"remote update disabled",
    "detail":"Remote update is turned off on this agent.",
    "upstream":{"error":"not found"}}
   ```
   This is the **only** place the body is not passed verbatim; the status code is
   still faithful. Rationale: the contract says an agent 404 specifically means
   `remote_update.enabled=false`, and the raw body doesn't say so.
3. **Agent unreachable** (httpx connect error / timeout — tunnel down, including
   the expected post-install restart window) → `503 {"error":"agent
   unreachable","detail":<reason>}`. `503` (retryable) is chosen over `502` so it
   never collides with the agent's *own* `502` ("release lookup failed"), and so
   a poller reads it as "keep polling," not a hard failure. The triggering POST
   returns the agent's `202` before the restart, so it never observes the drop.

## 7. Testing

TDD across the repo's three tiers:

1. **Authelia e2e** (`services/authelia/tests/e2e/`) — mirror the `/flash`
   gating tests for `X-Forwarded-Uri: /api/admin/labs/pc-1/update`:
   - `test_forward_auth.py`: no cookie → 401; admin (`alice`) session → 200 with
     `remote-groups` containing `admins`.
   - `test_group_gating.py`: researcher (`bob`) → 403.
   - Requires the rule in the e2e fixture (§5.1).

2. **siteapp unit** (`services/siteapp/tests/test_agent_update.py`, httpx mocked
   like `test_labs.py`):
   - Each agent status (202/200/400/409/502) passes through verbatim (code + body).
   - Unknown lab → 404 `unknown lab`.
   - Agent 404 → 404 with the clear `remote update disabled` body + `upstream`.
   - httpx connect error / timeout → 503 `agent unreachable`.
   - Raw body forwarded unchanged (assert the agent received the exact bytes,
     incl. `{}`, `{"version":…}`, `{"url":…,"sha256":…}`).
   - `GET .../status` passes a sample status body through verbatim.

3. **Caddy routing smoke** (`tests/integration/test_routes_smoke.bats`) — add an
   assertion mirroring `/flash/`: unauthenticated `/api/admin/labs/x/update` →
   `302` (forward_auth redirect to `/login`).

Existing per-service CI: siteapp unit tests run in `pr-siteapp.yml`; the Authelia
e2e run in `pr-authelia.yml`; the bats smoke runs in `pr-platform.yml`. No new
workflow, no new required check, no branch-protection change.

## 8. Files touched

| File | Change |
|------|--------|
| `services/authelia/config/configuration.yml.tmpl` | add `^/api/admin/.*` admins rule |
| `services/authelia/tests/e2e/fixtures/configuration.yml` | same rule (test.local) |
| `services/authelia/tests/e2e/test_forward_auth.py` | admin/no-cookie assertions on `/api/admin/…` |
| `services/authelia/tests/e2e/test_group_gating.py` | researcher-denied assertion on `/api/admin/…` |
| `compose/Caddyfile.tmpl` | `handle /api/admin/*` → siteapp behind `authelia_required` |
| `services/siteapp/app/agent_update.py` | **new** proxy handler |
| `services/siteapp/app/main.py` | register the new router |
| `services/siteapp/tests/test_agent_update.py` | **new** unit tests |
| `tests/integration/test_routes_smoke.bats` | unauth `/api/admin/…` → 302 |

## 9. Follow-up (not this PR)

- Admin SPA: pick a lab, trigger an update, poll `GET .../status`, surface the
  disabled/unreachable states from §6.
- Navbar entry for it: **admin-only, positioned above the flasher entry.**
- Optional hardening: app-layer `Remote-Groups` re-check (defense in depth).

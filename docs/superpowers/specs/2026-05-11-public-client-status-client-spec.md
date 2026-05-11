# Lab-bridge public API — client contract

Status: stable
Date: 2026-05-11
Audience: developers of the lab-device agent (chisel client) and any
other consumer that needs to look up a username's reverse-tunnel port
or monitor chisel-server health.
Pairs with: `2026-05-11-public-client-status-design.md` (server-side
design and security model — out of scope for this document).

Two HTTPS endpoints on the lab-bridge VPS that a chisel client (lab
device agent) can call. The VPS host is the same host the agent
already connects to over chisel.

## Auth

`GET /api/public/clients/{username}` requires a bearer token. The
token is the **chisel password the agent is already configured with**
— the same `password` operators issue with `task secrets:add-client`
and that the agent passes to `chisel client`. No new credential.

`GET /api/public/health` is unauthenticated.

## `GET /api/public/clients/{username}`

Look up the agent's reverse-tunnel port and whether the server
currently sees its tunnel as connected.

### Request

```
GET /api/public/clients/<username> HTTP/1.1
Host: <vps-host>
Authorization: Bearer <chisel_password>
```

`<username>` is the same string the agent uses when authenticating to
chisel.

### 200 — success

```json
{ "port": 8089, "connected": true }
```

- `port` (int): the reverse-tunnel port assigned to this agent.
  Stable across restarts; only changes if the operator re-runs
  `task secrets:add-client` with a different `reverse_port`. Safe to
  cache locally after first fetch.
- `connected` (bool): does the chisel server currently have an active
  reverse-tunnel session for this username? The server probes
  `chisel:<port>` over TCP with a 300 ms timeout. This is the
  *server's* view of the tunnel — it can disagree with the agent's
  local socket state when NAT/firewall sessions silently drop.

### 401 — auth failure

```json
{ "detail": "unauthorized" }
```

Returned for unknown username, wrong token, missing Authorization
header, or non-`Bearer` scheme. **All four are intentionally
indistinguishable** — do not try to detect "unknown username" vs
"wrong password" from the response; both look identical.

### 500 — server misconfiguration

The roster file on the server is missing, corrupt, or malformed.
Not a client-side problem; retry after a short backoff.

## `GET /api/public/health`

Lightweight chisel-server liveness probe, for status pages and
external monitoring. No auth.

### Request

```
GET /api/public/health HTTP/1.1
Host: <vps-host>
```

### 200 — always 200

```json
{ "chisel": "ok" }
```

or

```json
{ "chisel": "down", "error": "connection refused" }
```

The JSON is the signal, not the HTTP status. Status is 200 even when
chisel is unreachable — this endpoint reports *information about
chisel*, not its own health. Key off `body.chisel == "ok"`.

## Suggested agent usage

- **At startup**, before launching the chisel client, GET
  `/api/public/clients/{username}`. If 401, surface a config error
  (username/password mismatch) and stop. If 200, use the returned
  `port` as the `-R <port>:…` argument to `chisel client`.
- **Periodically** (e.g. every 10–30 s) re-issue the same request to
  refresh `connected` for the UI. The endpoint is cheap; no caching
  needed on the client side.
- **Don't** treat `connected: false` as "stop and reconnect"
  automatically — chisel-client owns reconnection. Just display it.

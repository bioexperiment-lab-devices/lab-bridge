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

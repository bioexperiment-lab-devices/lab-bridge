# Chisel client log forwarding — design

Status: approved (brainstorm complete; implementation plan to follow)
Date: 2026-04-28
Scope: server-side only. The client (`lab_devices_client`, separate repo)
will get its own follow-up spec to migrate to the contract defined here.

## Problem

When something misbehaves in a remote lab, the operator currently has to
ask lab staff to ZIP and email two log files
(`lab_devices_client.log`, `lab_devices_client_stderr.log`). This is slow,
error-prone, and provides no historical or cross-client view.

We want continuous, queryable access to client logs from the VPS, so the
operator can debug incidents without involving lab staff.

## Goals

- Always-on ingest: logs flow to the VPS continuously while the chisel
  session is up.
- Browser-based search and live tail, behind one well-known URL.
- Per-client identity in the UI (filter by client name, stream, version).
- 30-day retention, age-based eviction, filesystem storage.
- Reuse existing chisel auth — no new secrets exposed to the public
  internet.
- Server-side stack remains minimal: containerized, declarative, fits the
  existing `task deploy` flow.

## Non-goals

- High-availability log storage (single-node Loki on filesystem is fine).
- Multi-tenant log isolation between clients (small trusted lab; mislabeling
  is treated as an integrity issue, not a confidentiality breach).
- Alerting / paging (out of scope; operator looks at the dashboard).
- Client-side implementation details beyond the contract in this doc.

## Architecture

```
                          VPS (lab-bridge)
 ┌──────────────────────────────────────────────────────────┐
 │  Caddy ─┬─► jupyter:8888                                 │
 │         └─► grafana:3000  (subpath /grafana/, own login) │
 │                                                          │
 │  chisel:8080 (public)                                    │
 │     ▲                                                    │
 │     │  reverse: R:0.0.0.0:9001 → exposes device port     │
 │     │  forward: loki:3100      → tunneled push path      │
 │                                                          │
 │  loki:3100 ◄── pushed log streams                        │
 │     │                                                    │
 │     └─► loki_data/  (filesystem, 30-day retention)       │
 │                                                          │
 │  grafana:3000  ──► reads from loki:3100                  │
 │     │                                                    │
 │     └─► grafana_data/  (sqlite, dashboards, users)       │
 └──────────────────────────────────────────────────────────┘

 Lab machine (Windows service)
 ┌──────────────────────────────────────────────────────────┐
 │  lab_devices_client.exe                                  │
 │     │                                                    │
 │     ├─► writes lab_devices_client.log + ..._stderr.log   │
 │     ├─► chisel session: reverse + forward                │
 │     └─► POSTs log batches → http://127.0.0.1:3100/...    │
 └──────────────────────────────────────────────────────────┘
```

Key invariants:

- Loki has no published port. Reachable from Grafana over `labnet`, and
  from clients only via a chisel-forwarded TCP path.
- Chisel auth gates network reachability. An unauthenticated client cannot
  open the forward, so cannot reach Loki at all.
- Stream identity (`client`, `stream`, `version`) is self-asserted by the
  client. Cardinality is bounded; mislabeling is acceptable for a small
  trusted lab.
- The on-disk rotated log files on the client remain the durable record;
  Loki is the queryable mirror.

## Approaches considered

| Approach | Verdict |
|---|---|
| Flat per-client log files on disk + grep/tail | Rejected — no UI. |
| Public Loki push endpoint behind Caddy `basic_auth` | Rejected — extra public attack surface and a duplicate auth surface to manage. |
| **Internal Loki + Grafana, push via chisel forward tunnel** | **Chosen** — reuses existing chisel auth, keeps Loki off the public internet, single UI, two extra containers. |

Within the chosen path, two sub-decisions worth recording:

- **Loki + Grafana over Parseable / Vector+DIY.** Two well-known Grafana
  Labs containers cost a bit more memory than a single-binary alternative
  but give us search, live tail, dashboards, and auth without bespoke
  code.
- **Subpath (`/grafana/`) over subdomain.** `vps.host` may be an IP, and
  IPs cannot host wildcard subdomains for ACME. Subpath works in both
  IP-only and DNS-name deployments.

## Server-side changes

### `compose/docker-compose.yml.tmpl`

Add two services on `labnet` (no published ports for Loki):

```yaml
loki:
  image: __LOKI_IMAGE__
  restart: unless-stopped
  command: ["-config.file=/etc/loki/config.yaml"]
  volumes:
    - ./loki/config.yaml:/etc/loki/config.yaml:ro
    - ./loki_data:/loki
  networks: [labnet]

grafana:
  image: __GRAFANA_IMAGE__
  restart: unless-stopped
  environment:
    GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password
    GF_SERVER_ROOT_URL: https://__VPS_HOST__/grafana/
    GF_SERVER_SERVE_FROM_SUB_PATH: "true"
    GF_USERS_ALLOW_SIGN_UP: "false"
    GF_AUTH_ANONYMOUS_ENABLED: "false"
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning:ro
    - ./grafana_data:/var/lib/grafana
  secrets:
    - grafana_admin_password
  networks: [labnet]
  depends_on: [loki]

secrets:
  grafana_admin_password:
    file: ./grafana/admin_password
```

### `compose/Caddyfile.tmpl`

One new route inside the existing `https://__VPS_HOST__` block, before the
default `reverse_proxy jupyter:8888`:

```caddy
handle_path /grafana/* {
    reverse_proxy grafana:3000
}
reverse_proxy jupyter:8888
```

`handle_path` strips the `/grafana` prefix before forwarding, which pairs
with `GF_SERVER_SERVE_FROM_SUB_PATH=true`.

### `compose/chisel-users.json.tmpl` and `scripts/lib/render.sh`

Each chisel user's allow-list grows by one entry:

```jsonc
// before
"microscope-1:<pw>": ["R:0.0.0.0:9001"]
// after
"microscope-1:<pw>": ["R:0.0.0.0:9001", "loki:3100"]
```

The `loki:3100` entry (no `R:` prefix) authorizes a *forward* tunnel from
the client to `loki:3100` over the existing chisel session. The
`render_chisel_users` function in `scripts/lib/render.sh` appends this
entry for every client.

### `provision.sh`

Additive changes, idempotent like the existing `caddy_data` setup:

- `mkdir -p $REMOTE_ROOT/loki_data $REMOTE_ROOT/grafana_data`
- `chown 10001:10001 loki_data` (Loki container's uid)
- `chown 472:472 grafana_data` (Grafana container's uid)

## Loki configuration

`compose/loki/config.yaml.tmpl` — templated (the retention value is
substituted at deploy time), rendered to `compose/loki/config.yaml` and
rsynced to the VPS alongside the rendered `docker-compose.yml`. Same
templating pattern as `Caddyfile.tmpl`. Single-binary, filesystem-backed:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9095
  log_level: warn

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore: { store: inmemory }

schema_config:
  configs:
    - from: 2026-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: __LOKI_RETENTION_HOURS__h    # rendered from config.yaml
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 8
  max_label_name_length: 128
  max_label_value_length: 1024
  max_label_names_per_series: 15

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
  delete_request_store: filesystem

ruler:
  storage:
    type: local
    local: { directory: /loki/rules }
```

Notes:

- `auth_enabled: false` — single-tenant deployment. Network reachability is
  gated by chisel; a Loki-level auth token would be a second password to
  manage with no real isolation gain.
- `tsdb` + `schema v13` — current Loki recommended schema (BoltDB-shipper
  is legacy).
- `compactor.retention_enabled: true` — without this, `retention_period`
  is advisory and disk grows unbounded.
- `reject_old_samples_max_age: 168h` — if a client's local buffer gets
  stuck for more than a week, drop the backfill rather than polluting
  recent indexes.
- Loki only evicts by age, not by disk usage. Disk safety is handled by
  the `task ops:loki-disk` check (see Operator interface).

## Grafana provisioning

Goal: operator opens `https://<vps-host>/grafana/`, logs in once, sees a
working "Lab client logs" dashboard with no clickops.

All Grafana provisioning files below are **static** (no template
substitution); they ship to the VPS via the existing rsync step in
`deploy.sh`.

`compose/grafana/provisioning/datasources/loki.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    editable: false
```

`compose/grafana/provisioning/dashboards/lab-bridge.yaml`:

```yaml
apiVersion: 1
providers:
  - name: lab-bridge
    folder: ''
    type: file
    disableDeletion: true
    editable: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

`compose/grafana/provisioning/dashboards/client-logs.json` — one bundled
dashboard with these panels:

- **Live tail** — `{client=~"$client", stream=~"$stream", version=~"$version"}`,
  default tail of the last 1k lines, version visible in the legend.
- **Log volume by client** — `sum by (client) (rate({client=~".+"}[5m]))`.
- **Errors** — `{client=~"$client"} |= "ERROR"`.
- **Current versions** —
  `topk(1, max by (client, version) (max_over_time({client=~".+"}[1h])))`,
  shown as a small table of "what version is each client running right now".

Dashboard variables:

- `$client` from `label_values(client)`, default `All`.
- `$stream` — `stdout` / `stderr` / `All`.
- `$version` from `label_values(version)`, default `All`.

Auth shape:

- Single admin account, Grafana built-in login.
- Password set via `task secrets:set-grafana-password`, written to
  `compose/grafana/admin_password` (mode 0600, gitignored). `provision.sh`
  ensures the file exists with correct perms before `compose up`.
- `GF_USERS_ALLOW_SIGN_UP=false`, `GF_AUTH_ANONYMOUS_ENABLED=false`.
- Grafana receives the admin password in plaintext via `__FILE` env. This
  matches the existing trust model on the VPS — `chisel-users.json` and
  `caddy_data` already hold plaintext secrets under `compose/`.

No alerting in v1.

## Operator interface

`config.yaml` — additive section:

```yaml
loki:
  image: grafana/loki:3.2.1
  retention_days: 30

grafana:
  image: grafana/grafana:11.3.0
```

The Grafana admin password is not in `config.yaml`; it lives in
`compose/grafana/admin_password` and is set by `task secrets:set-grafana-password`,
mirroring the JupyterLab password flow.

New `task` commands in `Taskfile.yml`:

- `task secrets:set-grafana-password` — prompts, writes
  `compose/grafana/admin_password` (mode 0600).
- `task ops:logs:loki` — tails the loki container's stderr.
- `task ops:logs:grafana` — tails the grafana container's stderr.
- `task ops:loki-disk` — `du -sh` of `loki_data/`, plus the configured
  retention so the operator can sanity-check disk growth.

`scripts/lib/render.sh` — extended to:

- Substitute `__LOKI_IMAGE__`, `__GRAFANA_IMAGE__`, `__LOKI_RETENTION_HOURS__`
  (computed: `loki.retention_days * 24`).
- Render `compose/loki/config.yaml` from a template alongside the existing
  rendered files.
- Append `"loki:3100"` to each chisel user's allow-list in
  `chisel-users.json`.

`README.md` — one new line in Quick start
(`task secrets:set-grafana-password`) and a short section pointing the
operator at `https://<vps-host>/grafana/` for the "Lab client logs"
dashboard.

`task deploy` already renders configs and runs `compose up -d`; adding two
services is transparent to the operator's day-to-day flow.

## Client contract

This section is the source of truth for the follow-up client-repo spec.

### Chisel session

Extend the existing reverse with one forward in the same chisel client
invocation:

```
chisel client \
    --auth <name>:<password> \
    <vps-host>:<chisel_port> \
    R:0.0.0.0:<reverse_port>:127.0.0.1:<local_device_port> \
    127.0.0.1:3100:loki:3100
```

The forward gives the client a local `127.0.0.1:3100` that maps to the
in-VPS `loki:3100`.

### Push protocol

`POST http://127.0.0.1:3100/loki/api/v1/push`,
`Content-Type: application/json`, payload per Loki's push API:

```json
{
  "streams": [
    {
      "stream": {
        "client":  "microscope-1",
        "stream":  "stdout",
        "service": "lab_devices_client",
        "version": "1.4.2"
      },
      "values": [
        ["1714329600000000000", "<line>"]
      ]
    }
  ]
}
```

Required labels:

- `client` — must match the chisel auth username.
- `stream` — `stdout` or `stderr`.
- `service` — constant `lab_devices_client`.
- `version` — the client binary's semver string. Reported once at session
  start and reused for the lifetime of the process.

The line body carries everything else (timestamp formatting, level,
structured fields, error messages). Free-form fields MUST NOT be added as
labels — that would explode the Loki index.

`Content-Encoding: gzip` is allowed.

### Batching, buffering, loss

- Send every ≤2 s or ≤500 lines, whichever comes first.
- On push failure (chisel down, Loki 5xx), buffer in memory up to ~10k
  lines, then drop oldest.
- Server makes no dedup or ordering guarantees — best effort.
- The on-disk rotated log files remain the durable record; Loki is the
  queryable mirror.

### Identity

The client trusts itself to set the `client` label correctly. Mislabeling
is an integrity issue (wrong panel attribution), not a confidentiality
breach. A future per-client auth proxy could harden this without changing
the client.

## Failure modes

| Failure | Effect | Mitigation |
|---|---|---|
| Loki container down | Pushes fail; clients buffer locally | `restart: unless-stopped`; gap visible in Grafana |
| Disk full | Loki refuses writes, then panics | `task ops:loki-disk`; age-based retention; future cron disk-check |
| Grafana container down | UI unreachable; ingest unaffected | `restart: unless-stopped` |
| Chisel disconnect | Forward tunnel drops; client buffers | Existing chisel client reconnect loop |
| Client clock skew >7 days | Push rejected (`reject_old_samples_max_age`) | Documented; gap visible in dashboard |
| Client mislabels itself | Wrong panel attribution | Out of scope for v1 (small trusted lab) |
| Client cardinality bug (free-form labels) | Loki index bloats | `max_label_names_per_series: 15`, `max_label_value_length: 1024` cap blast radius |

## Testing strategy

Follows the existing fake-VPS pattern in `tests/`.

Unit (bats-core):

- `render.sh` produces correct chisel `users.json` with `loki:3100`
  appended for each client.
- `render.sh` substitutes retention hours correctly into
  `compose/loki/config.yaml`.
- `secrets:set-grafana-password` writes `compose/grafana/admin_password`
  with mode 0600.

Integration (existing fake-VPS container):

- After `task deploy`, both `loki` and `grafana` containers are healthy.
- From inside the chisel container, `curl http://loki:3100/ready`
  returns 200.
- A fake chisel client (sidecar in the test) opens a session with the new
  forward, POSTs one labeled log line, then querying Loki
  `/loki/api/v1/query_range` returns the line.
- Caddy routes `/grafana/` correctly (HTTP 302 to the Grafana login
  page).

Out of scope: load testing, chaos testing, real client integration (lives
in the client repo).

## Future work (not in this spec)

- Cron-driven disk-usage check that pages the operator before Loki fills
  the disk.
- Per-client auth proxy in front of Loki to enforce label identity at the
  network layer.
- Alertmanager / Slack integration for error-rate spikes.
- Multi-user Grafana with role-based access.
- Migration of the client to push directly to this contract (separate
  spec, separate repo).

# Technical Overview

## Components

| Component | Role | Stack |
|---|---|---|
| [`lab-bridge`](https://github.com/bioexperiment-lab-devices/lab-bridge) | VPS-side Docker Compose stack: public entrypoint, notebook environment, tunnel server, observability. | Docker Compose, Caddy, JupyterLab, chisel, Loki, Grafana. |
| [`serialhop`](https://github.com/bioexperiment-lab-devices/serialhop) | Lab-machine agent: exposes serial devices over HTTP, dials VPS via chisel. | Single Go binary (Windows service). |
| [`bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite) | Python library used in notebooks; HTTP client to `serialhop`. | Python, `httpx`, `loguru`. |

Live endpoints: [JupyterLab](https://111.88.145.138/lab) · [Grafana](https://111.88.145.138/grafana/).

## Topology

The lab PC opens an outbound chisel connection to the VPS. The same chisel session carries:

- **Reverse tunnels** — each lab agent's local REST API is published into the docker `labnet` network, reachable from the notebook environment as `http://chisel:<port>`.
- **Forward tunnel** — `lab_pc:127.0.0.1:3100 → loki:3100`, used to push agent logs into Loki.

No inbound ports on the lab network. Chisel auth uses a per-client user/password allowlist managed on the VPS.

## `lab-bridge`

Single Docker Compose stack on `labnet`:

- **caddy** — public on 80/443; TLS via Let's Encrypt; proxies `/grafana/*` → grafana, everything else → jupyter.
- **jupyter** — JupyterLab; cookie-based shared-password auth.
- **chisel** — public on configured listen port; per-client allowlist.
- **loki** — internal only, no published port.
- **grafana** — internal only, reached via caddy at `/grafana/`. Provisioned Loki datasource and "Lab client logs" dashboard (live tail, log volume by client, errors, current versions).

**Operator surface**:

- `Taskfile.yml` wraps `scripts/{provision,deploy,secrets,ops,doctor}.sh`.
- `config.yaml` (gitignored, copy of `config.example.yaml`) holds VPS details, chisel listen port, retention, etc.
- Templates in `compose/` rendered via `yq` (mikefarah build).
- Secrets managed via `task secrets:*`: jupyter password, grafana admin password, per-client chisel credentials.
- Tests: `bats-core` suites in `tests/`, run against a fake-VPS Docker container; `task test`.

**One-time bring-up**:

```bash
cp config.example.yaml config.yaml      # edit
task secrets:set-jupyter-password
task secrets:set-grafana-password
task secrets:add-client -- <name> <port>
task provision
task deploy
```

**Ops entrypoints**: `task ops:logs:loki`, `task ops:logs:grafana`, `task ops:loki-disk`.

## `serialhop`

Single static Go binary, default target Windows/amd64; output `dist/SerialHop.exe`.

**Run modes** (auto-detected from launch context):

| Launched via | Mode |
|---|---|
| SCM | Service worker |
| Double-click | Control panel (lxn/walk GUI) |
| `--admin-action=...` | Internal SCM op (UAC re-entry) |
| `--foreground` | Console developer mode (JSON logs to stdout) |

**Service**: registered as `SerialHop`, auto-start at boot, runs as `LocalSystem`. Install / uninstall / restart from the control panel.

**REST API** — bound to `127.0.0.1`, reachable from the VPS only through the reverse tunnel:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/discover` | Fresh enumeration; destructive. |
| `GET` | `/devices` | Cached device list. |
| `POST` | `/devices/{id}/command` | Send raw bytes; optional reply read. Query params: `wait_for_response`, `expected_response_bytes`, `timeout_ms`, `inter_byte_ms`. |

**Device types**: `pump` (type code 10), `valve` (30), `densitometer` (70). Discovery probes ports with the universal probe `[1, 2, 3, 4, 0]`.

**Files** (next to the `.exe`):

- `SerialHop_config.yaml` — config (chisel host/port/user/pass, etc.).
- `SerialHop.log` — slog JSON, rotated 10 MB × 3.
- `SerialHop_stderr.log` — chisel state and panic traces, same rotation.

**Log streaming to Loki** (service mode only; gated on `chisel.user` being set):

- Tails both on-disk log files. On-disk files remain the durable record; Loki is a queryable mirror.
- In-memory ring buffer: 10 000 records, drop-oldest on overflow.
- Pushes gzipped JSON, batched ≤ 500 records or 2 s; backoff on 5xx, drop-batch on 4xx.
- Labels: `client` (chisel user), `stream` (`stdout`/`stderr`), `service=serialhop`, `version`.

**Build**: `task build`. Embeds icon, UAC manifest (`asInvoker`), and version metadata via `goversioninfo`. Auto-bumps minor version on dirty tree; version baked in via `-ldflags -X` and shown in panel title.

**Per-machine install**:

1. Copy `SerialHop.exe` to install dir (e.g. `C:\Tools\SerialHop\`).
2. Run; edit `SerialHop_config.yaml` (`chisel.remote_port`, `chisel.user`, `chisel.pass`).
3. Click **Install** in the panel; approve UAC.

## `bioexperiment_suite`

Python package. Post-migration state on the HTTP-transport branch — see the [HTTP client design spec](https://github.com/khamitovdr/bio_tools/blob/main/docs/superpowers/specs/2026-04-27-lab-devices-http-client-design.md) for the full contract. `main` still carries the legacy direct-serial implementation; the two branches diverge with no runtime switch.

**Layout**:

```
src/bioexperiment_suite/
├── interfaces/
│   ├── lab_devices_client.py   # LabDevicesClient, DiscoveredDevices, exceptions
│   ├── pump.py
│   ├── densitometer.py
│   └── valve.py                # placeholder, no methods
├── experiment/                 # transport-agnostic, unchanged
├── device_interfaces.json      # client-side byte vocabulary
└── loader.py
```

**Public API** (`bioexperiment_suite.interfaces`):

- `LabDevicesClient(port, host="chisel", request_timeout_sec=5.0)` — owns one `httpx.Client`; context manager.
- Methods: `discover()`, `list_devices()`, `send_command(...)`, `close()`.
- Returns `DiscoveredDevices(pumps, densitometers, valves, discovered_at)`.
- Device classes (`Pump`, `Densitometer`, `Valve`) are constructed by `discover()` / `list_devices()`, not directly.

**Exception hierarchy**:

| Exception | HTTP | Server `error` code |
|---|---|---|
| `InvalidRequest` | 400 | invalid request body / query param |
| `DeviceNotFound` | 404 | device not found |
| `DeviceBusy` | 409 | device busy |
| `DiscoveryInProgress` | 409 | discovery in progress |
| `DiscoveryFailed` | 500 | discovery failed |
| `DeviceUnreachable` | 503 | device unreachable |
| `DeviceIOFailed` | 503 | device i/o failed |
| `DeviceIdentityChanged` | 503 | device identity changed |
| `TransportError` | 0 | `connection error` / `read timeout` / `invalid response` |

All inherit `LabDevicesError(status, code, detail)`. No automatic retry, no silent fallbacks.

**Behavior notes**:

- `Pump.__init__` performs one calibration round-trip per pump on every `discover()` / `list_devices()` call.
- `Densitometer.measure_optical_density` issues start, sleeps client-side 3 s, reads.
- `send_command` query-param policy: `expected_response_bytes` is omitted when `wait_for_response=False`; `timeout_ms` / `inter_byte_ms` are omitted unless explicitly passed (server defaults apply).
- No client-side caching of `/devices` (server already caches).
- No async API; sync `httpx.Client` only.

**Dependencies**: `httpx ^0.28`, `loguru`. Tests: `pytest` with `httpx.MockTransport` (unit), fakes for device-class tests, manual integration against a real lab agent.

**Notebook usage**:

```python
client = LabDevicesClient(port=9001)   # host defaults to "chisel"
devices = client.discover()
for pump in devices.pumps:
    pump.pour_in_volume(5.0)
od = devices.densitometers[0].measure_optical_density()
```

## Repositories and endpoints

- `lab-bridge`: <https://github.com/bioexperiment-lab-devices/lab-bridge>
- `serialhop`: <https://github.com/bioexperiment-lab-devices/serialhop>
- `bioexperiment_suite`: <https://github.com/khamitovdr/bioexperiment_suite>
- Migration spec: <https://github.com/khamitovdr/bio_tools/blob/main/docs/superpowers/specs/2026-04-27-lab-devices-http-client-design.md>
- JupyterLab: <https://111.88.145.138/lab>
- Grafana: <https://111.88.145.138/grafana/>

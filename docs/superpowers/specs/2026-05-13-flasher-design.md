# Flasher service — design

A new operator-only web UI for flashing firmware onto AVR/optiboot devices
attached to lab machines. It ships as a separate container in the existing
Docker Compose stack and talks to the per-lab-machine SerialHop HTTP API
(see `docs/flashing-server-brief.md`) over the existing chisel reverse
tunnels.

The flow the operator should be able to run end-to-end:

1. Pick which lab machine to target from a list of currently-online machines.
2. See every serial port that machine reports, with USB descriptors, and
   pick one.
3. Choose a compiled firmware file (`.hex`) from local disk.
4. Optionally provide a `test_command` / `expected_response` pair as hex
   strings, or flip a switch to skip the post-flash test.
5. Once all the above is valid, click a single "Disconnect devices and
   flash" button. Behind the scenes the flasher calls SerialHop's
   `/devices/disconnect`, then `POST /flash/{port}`.
6. Watch a running view (elapsed timer, indeterminate progress) and then
   read the result in a stage-by-stage breakdown coloured by outcome.

## Goals & non-goals

In scope:

- A single-page React+TS SPA + FastAPI backend, packaged as one container.
- Targeting any currently-online chisel client from the runtime
  `siteapp/clients.json` file that `task secrets:add-client` already
  produces.
- Pass-through of SerialHop's full `POST /flash/{port}` response so the
  operator can see backup metadata, stage outcomes, test diffs, and
  rollback status.
- Survival of a browser refresh while a flash is in flight (background job
  + polling).

Out of scope (deliberately, for this first cut):

- Multi-port batch flashing.
- A firmware library or upload history on the server.
- Scheduled / unattended flashing.
- A role system beyond the existing single `admin` basic_auth user.
- EEPROM operations (SerialHop itself doesn't support these).
- Streaming per-stage progress events (SerialHop returns its entire result
  in one 200; there is nothing real to stream).

## Architecture

A new service `flasher` joins the existing compose stack alongside
`siteapp`, `caddy`, `chisel`, etc.

### Container

- **Build**: multi-stage Dockerfile.
  - Stage 1 (`node:20-alpine`): installs deps, runs `vite build` over
    `web/`, producing `dist/`.
  - Stage 2 (`python:3.13-slim`): installs Python deps (`fastapi`,
    `uvicorn[standard]`, `httpx`), copies `app/` and the built `dist/`
    from stage 1, runs `uvicorn flasher.main:app --host 0.0.0.0 --port 8000`.
- **Runtime port**: 8000 inside the container. Not published to the host.
- **Image reference**: pinned the same way as siteapp —
  `compose/pins.yaml` gets a new `flasher_image_repo` key; the tag lives in
  `compose/flasher/VERSION`. `task` exposes `flasher:build-and-push` next
  to the existing `siteapp:build-and-push`.

### Source layout

Mirrors `compose/siteapp/`:

```
compose/flasher/
  Dockerfile
  VERSION
  build.sh
  pyproject.toml
  uv.lock
  app/                     # FastAPI source
    __init__.py
    main.py                # FastAPI() + static mount + route includes
    config.py              # reads clients.json + chisel listen port from env
    clients.py             # client registry + online probe
    serialhop.py           # thin httpx wrapper over SerialHop's API
    flash.py               # job store + background runner
    routes.py              # all /api/* routes
  web/                     # React+TS source
    package.json
    tsconfig.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      api.ts               # typed wrappers over /api/*
      hex.ts               # hex normalize / format / byte-group helpers
      components/
        ClientPicker.tsx
        PortTable.tsx
        FirmwarePicker.tsx
        TestPairEditor.tsx
        FlashButton.tsx
        RunningView.tsx
        ResultView.tsx
  tests/
    test_routes.py
    test_flash.py
    test_clients.py
```

### Compose / Caddy integration

`compose/docker-compose.yml.tmpl` gains a `flasher` service:

```yaml
flasher:
  image: __FLASHER_IMAGE__
  restart: unless-stopped
  environment:
    FLASHER_CLIENTS_FILE: /etc/flasher/clients.json
    FLASHER_CHISEL_HOST: chisel
  volumes:
    - ./siteapp/clients.json:/etc/flasher/clients.json:ro
  networks: [labnet]
```

The `clients.json` file produced by `task secrets:add-client` already
contains the `{name, reverse_port, password}` entries the flasher needs,
so it's read-only mounted into both `siteapp` and `flasher` from the same
on-disk file. No new secret.

`compose/Caddyfile.tmpl` gains one block, just like the existing `/admin*`
block:

```caddy
handle /flash* {
    basic_auth {
        admin __ADMIN_BCRYPT_HASH__
    }
    reverse_proxy flasher:8000
}
```

Caddy's basic_auth header is forwarded; the flasher itself does not need
to authenticate. (The operator is whoever Caddy let through.)

### Release pipeline

The repo already runs release-please; the flasher gets the same treatment
as siteapp:

- A new `compose/flasher/VERSION` file. The image repository follows the
  same pattern as siteapp: `compose/pins.yaml` gains a
  `flasher_image_repo` key (e.g. `ghcr.io/<owner>/lab-bridge-flasher`),
  and the tag comes from `compose/flasher/VERSION`. The full image
  reference (`${flasher_image_repo}:${VERSION}`) is computed by `task
  flasher:build-and-push` exactly the way the siteapp task does.
- The release-please workflow builds + pushes both siteapp and flasher
  when their respective VERSION files change.
- `task deploy` renders the compose template with the pinned image.

## Backend API

All routes live under `/api/` on the flasher service, behind Caddy's
basic_auth. Static SPA assets are served from `/` (matched by Caddy's
`/flash*` block, so the SPA itself loads at `/flash/`).

### Client list

`GET /api/clients` → list of currently-online lab machines.

The flasher reads the same `clients.json` siteapp uses (mounted at
`/etc/flasher/clients.json`) to enumerate candidates. For each candidate,
it probes liveness by opening a short-timeout (~500 ms) TCP connection
to `chisel:<port>` (matching how SerialHop's URL would be built).
A client that doesn't accept the TCP connect in that window is treated
as offline and filtered out before returning. Probes run concurrently
across candidates so a slow / offline client doesn't stall the rest.

Response:

```json
{
  "clients": [
    { "name": "khamit_desktop",  "port": 8089 },
    { "name": "protres_ksenios", "port": 8081 }
  ]
}
```

The flasher emits a list (not the keyed-by-name on-disk shape) so the
SPA can render in a stable sort order without re-reshaping.

### Port list

`GET /api/clients/{name}/ports` → pass-through of SerialHop's
`GET /serial/ports/detailed` for the named client.

- **404** if `{name}` is not in `clients.json`.
- **502** with `{"error":"upstream unreachable","detail":"..."}` if the
  TCP/HTTP call to SerialHop fails.
- **200** with the SerialHop body verbatim otherwise. Shape:

```json
{
  "ports": [
    {
      "name":          "COM3",
      "is_usb":        true,
      "vid":           "2341",
      "pid":           "0043",
      "serial_number": "8543931323535121F0A0",
      "product":       "Arduino Uno",
      "discovered":    false,
      "device_id":     ""
    }
  ]
}
```

### Start a flash

`POST /api/flash` body:

```json
{
  "client":   "khamit_desktop",
  "port":     "COM3",
  "firmware": "<Intel HEX text>",
  "test":     { "command": "010203", "expected_response": "aabbcc" }
}
```

- `test` may be `null` (or omitted) to skip the post-flash test. If
  present, both `command` and `expected_response` must be non-empty
  even-length hex strings.
- `firmware` is rejected upfront if it's empty or exceeds 256 KiB.
- `client` must be present in `clients.json`; the flasher does not check
  online status here — if the client just went offline, SerialHop will
  surface the failure via the background job.

The handler:

1. Validates the request locally (see above).
2. Creates a `job_id` (UUID v4) and stores
   `{status: "running", client, port, firmware_sha256, started_at,
   request: <sanitized>}` in the in-memory job store. `firmware` is
   *not* stored in the job record; only its sha256 and length.
3. Schedules a background task via `asyncio.create_task` that, in order:
   a. `POST http://chisel:<port>/devices/disconnect`
   b. `POST http://chisel:<port>/flash/{port}` with the
      SerialHop-shaped body (the flasher reshapes the `test` sub-object
      into SerialHop's flat `test_command` / `expected_response` fields
      and applies SerialHop's defaults for `timeout_ms`,
      `inter_byte_ms`, `post_open_settle_ms` — those are not exposed to
      the operator in this iteration).
4. On the background task completing, writes one of:
   - `{status: "done", result: <SerialHop's 200 body verbatim>}`
   - `{status: "error", detail: "<short>", error_code: "<short>"}` for
     transport-level failures or non-200 responses from SerialHop.
     Mapping rules:
     - SerialHop returned a 4xx with its standard
       `{"error":"<code>","detail":"<msg>"}` body → flasher's
       `error_code` = SerialHop's `error`, `detail` = SerialHop's
       `detail`. Covers `flashing disabled`, `port not found`,
       `registry not empty`, `flash in flight`, `discovery in progress`,
       `invalid request body`.
     - SerialHop returned a 5xx or unparseable body → `error_code` =
       `upstream error`, `detail` = the raw status text + first ~200
       chars of the body.
     - The HTTP call itself failed (connection refused, timeout,
       DNS) → `error_code` = `upstream unreachable`, `detail` = the
       exception message.
5. Returns `{ "job_id": "..." }` immediately to the caller.

Note: SerialHop's *terminal* failure outcomes (`failed_backup`,
`rolled_back_verify_failed`, `rolled_back_test_failed`,
`failed_no_recovery`, `failed_preflight`) are *normal* HTTP 200
responses. The flasher treats them as `status: "done"` jobs and the
frontend renders the outcome.

### Poll a flash

`GET /api/flash/{job_id}` → one of:

```json
{ "status": "running", "started_at": "2026-05-13T14:22:08Z", "elapsed_ms": 12340 }
```

```json
{ "status": "done",    "result": <SerialHop's 200 body verbatim> }
```

```json
{ "status": "error",   "detail": "connection refused", "error_code": "upstream unreachable" }
```

**404** if the `job_id` is unknown (either never existed or fell out of
the in-memory store).

### Recover after refresh

`GET /api/flash/current` → if a job is running or finished within the
last few minutes, return `{ "job_id": "...", "status": "...", ... }`
(same shape as polling). Otherwise `{}`.

This lets the SPA detect on mount that a flash is already in flight and
jump straight into the running view instead of the wizard.

### Job store

- An in-memory `dict[str, JobRecord]` plus a deque of insertion order.
- Capped at the 10 most recent jobs; older jobs are pruned on insert.
- No persistence. Process restart loses history — fine, because
  SerialHop is the source of truth and its on-disk backups survive.

### Single-flight

SerialHop already enforces one flash at a time per service instance and
returns `409 flash in flight` on a concurrent call. The flasher relays
that as `{status: "error", error_code: "flash in flight"}` on the job
record. No second lock in the flasher.

## Frontend (single-page wizard)

One React+TS page; no router. Four stacked sections that progressively
unlock, plus running/result views that take over the whole page.

### 1. Lab machine picker

- Fetches `/api/clients` on mount.
- Renders a dropdown of online clients, sorted by name.
- If none online: shows "No lab machines are currently online." with a
  Retry button.
- Changing the selection clears port, firmware, and test-pair state.

### 2. Port table

- Activated when a client is picked. Fetches
  `/api/clients/{name}/ports`.
- Renders a table with columns: Port, Product, VID:PID, Serial number,
  Status. The Status cell shows "In use — {device_id}" if `discovered`
  is true, else "—".
- Clicking a row selects it (single-select). A `Refresh` button reloads
  the table.
- Non-USB ports are not disabled but are visually muted (they're rarely
  flash targets; the operator can still pick them if they really mean
  to).

### 3. Firmware file picker

- Standard `<input type="file" accept=".hex">`.
- On pick:
  - Read as text in the browser (`file.text()`).
  - Reject upfront if size > 256 KiB.
  - Compute SHA-256 client-side (`crypto.subtle.digest`).
  - Display `filename`, `<n> bytes`, and `sha256` (truncated, hover for
    full).
- The file content lives in React state only; it isn't uploaded until
  the operator clicks Flash.

### 4. Test pair (toggleable)

- A switch: **Run post-flash test (recommended)** / **Skip test**.
- When on: two text inputs labelled `test_command` and
  `expected_response`. Each input:
  - Stores its canonical value as a contiguous lowercase hex string in
    React state (this is what hits the API).
  - **Renders** the value byte-separated: `01 02 03`. Spaces, colons,
    and `0x` prefixes pasted in are stripped on input.
  - Shows `<n> bytes` below the field, computed from the canonical
    state.
  - Shows an ASCII preview (printable bytes as glyphs, non-printable as
    `·`) to one side.
  - Shows an inline error if the canonical hex is empty, odd-length, or
    contains non-hex characters.
- When off: both fields are removed and the API request will omit `test`.

The same byte-separation rule applies everywhere hex bytes are shown to
the operator (test inputs, result-view `expected` / `received`, any
future hex display) — group as `01 02 03 04`, lowercase, no separators
when copied programmatically.

### 5. Flash button

- Always visible at the bottom of the wizard.
- Enabled only when:
  - A client is selected and was online at last fetch.
  - A port is selected.
  - Firmware is loaded and ≤ 256 KiB.
  - Test pair is either both-fields-valid or switch-off.
- Label: **Disconnect devices and flash**.
- Subtext: "This kicks any active session off the bus on
  <client-name>."
- Click: POSTs to `/api/flash`, receives a `job_id`, transitions to the
  running view.

### 6. Running view

- Replaces the wizard with one card:
  - Header line: `<client> · <port> · <firmware filename>`.
  - Elapsed-time counter (`mm:ss`), ticking once per second.
  - An indeterminate progress bar. We do not fake per-stage progress —
    SerialHop doesn't expose any, so animating discrete stages would be
    a lie.
  - A small note: "Typical 15–30 s; up to ~60 s in worst case."
- Polls `/api/flash/{job_id}` every 1.5 s.
- On a refresh, the SPA calls `/api/flash/current` on mount; if a job
  is running, it jumps here.
- Transitions to the result view on `status: "done"` or
  `status: "error"`.

### 7. Result view

- Big outcome badge across the top, coloured:
  - **Green** — `success`.
  - **Amber** — `rolled_back_verify_failed`, `rolled_back_test_failed`,
    `failed_preflight`, `failed_backup` (device intact).
  - **Red** — `failed_no_recovery` (device potentially unusable), or
    flasher-level `status: "error"` (upstream unreachable etc.).
- Below it, a stage strip: seven chips in order
  `preflight backup erase program verify test rollback`, each coloured
  by its `status` field (`ok` green, `failed` red, `skipped` grey,
  `n/a` faint). Hovering shows `duration_ms` and any `error` string.
- If `test_result` is present:
  - Two byte-grouped hex rows labelled **Expected** and **Received**.
  - Mismatched byte positions are highlighted in red.
  - `match: true/false` shown explicitly.
- If `backup` is present:
  - Read-only fields for `saved_path`, `sha256`, `size_bytes`,
    `scope` (always `flash_only` — shown as a note).
- If `recovery_hint` is present, render it as a prominent note next to
  the red badge.
- A collapsible **Raw JSON** panel at the bottom, defaulting to closed,
  pretty-printing the full SerialHop response (or, for `status: "error"`,
  the flasher's error body).
- Two buttons:
  - **Flash another** — resets firmware + test pair, keeps the client
    and port selected, goes back to step 3.
  - **Done** — resets everything, goes back to step 1.

## Configuration

The flasher reads at startup:

- `FLASHER_CLIENTS_FILE` (path) — defaults to `/etc/flasher/clients.json`.
  Same shape that `scripts/lib/render.sh::render_siteapp_clients`
  already produces (and that siteapp's `app/clients.py` consumes):

  ```json
  {
    "khamit_desktop":  { "port": 8089, "password_sha256": "<hex>" },
    "protres_ksenios": { "port": 8081, "password_sha256": "<hex>" }
  }
  ```

  The flasher only needs `port` per entry. It ignores `password_sha256`
  (SerialHop has no auth at this layer; auth is enforced upstream by
  basic_auth at Caddy). The plaintext password is never written to
  disk, so the flasher cannot reach it — and doesn't need to.

- `FLASHER_CHISEL_HOST` (string) — defaults to `chisel`. Hostname used
  when building `http://<host>:<port>/`. Overridable for local testing.

The file is read on each request that needs it (it's tiny, and this
avoids a reload-on-change problem after `task secrets:add-client`).

## Error semantics summary

| Layer | What it returns | How the SPA shows it |
|---|---|---|
| Caddy basic_auth | 401 with browser prompt | Browser-native auth dialog |
| Flasher preflight (`POST /api/flash`, validation) | 400 with `{error, detail}` | Inline error on the wizard, no transition |
| Flasher upstream call to SerialHop fails | Job ends with `status: "error"` | Red badge in result view, with `detail` |
| SerialHop preflight rejection (4xx) | Job ends with `status: "error"`, `error_code` mirrors SerialHop's | Red badge, badge text uses SerialHop's `error_code` |
| SerialHop terminal outcome (200, any value) | Job ends with `status: "done"`, `result` is verbatim | Coloured badge + stage strip per outcome |

## Testing

Python (`pytest`, mirroring siteapp's setup):

- `test_clients.py` — fakes `clients.json`, mocks `chisel:<port>`
  reachability, asserts filtering of offline clients.
- `test_routes.py` — uses FastAPI's `TestClient`. Mocks `httpx` calls to
  SerialHop. Covers happy path, validation rejections, upstream errors,
  job polling, `current` recovery.
- `test_flash.py` — exercises the background job runner and the
  10-job in-memory cap.

Frontend tests are deferred for this first cut — the UI is exercised
end-to-end manually during the implementation plan. (We can introduce
Vitest + React Testing Library when there's a regression worth catching.)

## Open questions / deferred decisions

- **Multi-operator concurrency.** Two operators hitting Flash at once
  will be serialised by SerialHop (`409 flash in flight`). The second
  one sees a clean error in the result view. We don't need anything
  fancier today.
- **Audit log.** Not in scope. If we want one later, the natural place
  is to forward a structured log line per completed job into Loki via
  the existing chisel-loki tunnel — but that lands as a follow-up spec,
  not this one.
- **Exposing `timeout_ms` / `inter_byte_ms` / `post_open_settle_ms`.**
  Hidden in v1; the SerialHop defaults are fine for the boards we use
  today. A power-user "Advanced" disclosure can be added without
  reshaping the API.

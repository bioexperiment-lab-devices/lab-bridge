# Flasher service — firmware/backup library, history, and tabs

This is the v2 design for the flasher service. The v1 design
(`docs/superpowers/specs/2026-05-13-flasher-design.md`) shipped a single-page
wizard with an in-memory 10-job LRU and no persistent state beyond the
SerialHop side. This document turns the flasher into a stateful tool: it
gains a persistent firmware library, a persistent backup library
auto-populated from every flash, an immutable flash history, a tabbed UI
that no longer changes pages during a flash, and a bearer-authenticated
upload endpoint for CI integration.

The operator's day-to-day after this lands:

1. Switch to the **Flash** tab. Pick a lab machine and a port (offline
   machines are listed but disabled). Pick a firmware *record* from the
   library or a *backup* from the library; the picker spans both. Or
   pick "Create new firmware" to upload a `.hex` that lands in the
   library and gets used for this flash in one step. The chosen source's
   stored test pair prefills; the operator can edit it inline and
   optionally save the edit back to the source.
2. Click Flash. The form stays at the top of the tab; the running view
   and then the result view render below it. The flash record is durable
   from the moment Flash is clicked.
3. Switch tabs (Firmware, Backups, Logs) without losing or interrupting
   the running flash — but no flash status banner follows the operator
   around. The Flash tab is the single source of truth for what's
   flashing now.
4. After the flash, the captured backup is already in the **Backups**
   library, deduplicated by sha256 across all backups. The operator can
   give it a name and description, attach a test pair, or promote it
   into the firmware library if the bytes deserve a permanent home.
5. Browse all past flashes on the **Logs** tab, filtered by client,
   outcome, source, or date. Click any row for the full SerialHop
   response, the stage strip, the test diff, and a "Repeat this flash"
   button. Attach a free-text note to any historical flash row.

The flasher remains a single container in the existing compose stack,
behind Caddy's basic_auth for operator paths and bearer auth for the
single CI upload endpoint.

## Goals & non-goals

### In scope

- **Firmware library** — operator (and CI) upload `.hex` files with
  name, description, optional test pair, and tags. Bytes are immutable;
  labels are editable.
- **Backup library** — every successful or rolled-back flash auto-saves
  the captured backup, deduplicated by sha256. Each backup carries
  client, port, USB descriptors, sha256, size, source flash id, and
  editable name/description/test pair.
- **Flash history** — every flash inserts a row at click time with
  `status=running`, mutates only into `done` / `error` / `interrupted`,
  and is immutable thereafter except for a free-text operator note.
- **Promote backup → firmware** — clones a backup's bytes into a new
  firmware record.
- **Flash from firmware or backup** — unified source picker on the
  Flash tab.
- **Re-flash from history** — one-click replay of any past flash.
- **Download / export** — fetch the `.hex` bytes of any firmware or
  backup record.
- **Tags on firmware records** — many-to-many, with a tag-management
  modal and an AND-style tag filter on the firmware list.
- **Operator note on a flash record** — the only mutable field on a
  terminal-status flash row.
- **Tabs** — Flash / Firmware / Backups / Logs. The Flash tab keeps the
  wizard form always visible at the top; running and result views
  render below it.
- **Per-firmware and per-backup stats** — total flashes, success /
  rolled-back / failed counts, success rate %, last flashed when/where,
  plus the flash list itself.
- **Bearer-authenticated CI endpoint** for firmware upload, with a
  separate Caddy block so basic_auth doesn't intercept the
  `Authorization: Bearer` header.
- **Filters on the Logs tab** from day one — client, outcome, source,
  date range.

### Out of scope (deferred)

- A first-class Device entity. Backup and flash rows carry vid, pid,
  serial_number, product, client, and port_name as denormalised columns
  so the operator can identify what was on each board, but there is no
  shared identity table grouping flashes/backups by physical board.
  Revisit if and when "show me the history of this specific physical
  Arduino" becomes a recurring need.
- Backup-vs-backup or backup-vs-firmware diff view.
- Pin / favourite firmware records.
- Full-text search across names/descriptions.
- Multi-operator identity. Auth remains single-`admin` basic_auth at
  Caddy; the bearer endpoint is a service-to-service shared secret.
- Streaming per-stage progress. SerialHop does not expose it.
- Retention caps or automatic pruning on the backup library. Storage
  growth is the operator's responsibility via bulk delete on the
  Backups tab.
- Soft-delete and undelete flows. Deletes are hard. The operator is
  responsible for deleting only when it's safe.

## Architecture

A new persistent bind-mount holds SQLite plus the `.hex` blob store;
everything else about the container shape is unchanged from v1.

### Container & volume

- Existing flasher image (Node build of `web/` + Python `app/`).
- **New** persistent bind-mount: `./flasher_data:/var/lib/flasher` on
  the flasher service. Mirrors the existing `site_data`, `caddy_data`,
  `loki_data`, `grafana_data` pattern.
- Storage layout inside `flasher_data/`:
  ```
  flasher.db                       # SQLite, WAL-mode
  blobs/
    firmware/<firmware_id>.hex     # one file per firmware record
    backups/<backup_id>.hex        # one file per backup record
  ```
- Blob file names are uuid hex strings; the originating filename (for
  firmware) is stored in the DB row.

### SQLite

- `aiosqlite` driver. Plain SQL — no ORM. Pydantic models for
  request/response shapes only.
- PRAGMAs set on every connection: `journal_mode=WAL`,
  `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`.
- Single writer, multiple readers. A small process-wide
  `asyncio.Lock` serialises write paths in Python; SQLite's WAL handles
  concurrent reads independently.
- The DB file is safe to back up while the service is running via
  `sqlite3 flasher.db .backup …` or copying `flasher.db` plus
  `flasher.db-wal` / `flasher.db-shm` atomically.

### Source layout

```
services/flasher/
  app/
    __init__.py
    main.py             # FastAPI() + static mount + router includes + DB startup
    config.py           # env loader (extended)
    clients.py          # roster reader (unchanged shape)
    serialhop.py        # unchanged
    db.py               # connection factory, migration runner
    migrations/
      0001_init.sql
      # 0002_*.sql      # any future schema changes
    firmware.py         # firmware row CRUD + blob I/O
    backups.py          # backup row CRUD + blob I/O + dedup
    flashes.py          # flash row CRUD + stats queries + background runner
    tags.py             # tag CRUD
    routes/
      __init__.py
      clients.py        # GET /api/clients[/{name}/ports]
      firmware.py       # /api/firmware/* and /api/v1/firmware/*
      backups.py        # /api/backups/*
      flashes.py        # /api/flash, /api/flashes, /api/flash/*
      tags.py           # /api/tags/*
  web/src/
    main.tsx
    App.tsx
    api.ts
    hex.ts
    components/
      TabBar.tsx
      ClientPicker.tsx       # unchanged shape, now renders offline rows muted
      PortTable.tsx
      FirmwareSourcePicker.tsx    # NEW — replaces FirmwarePicker on Flash tab
      TestPairEditor.tsx
      FlashOptions.tsx
      FlashButton.tsx
      RunningView.tsx
      ResultView.tsx              # buttons removed; rendered below form
      StageStrip.tsx
      HexDiff.tsx
      # Firmware tab
      FirmwareList.tsx
      FirmwareDetail.tsx
      FirmwareUploadForm.tsx
      TagManager.tsx
      TagChip.tsx
      # Backups tab
      BackupList.tsx
      BackupDetail.tsx
      # Logs tab
      LogTable.tsx
      LogFilters.tsx
      LogDetailDrawer.tsx
      # shared
      StatsCard.tsx
  tests/
    test_db.py
    test_firmware.py
    test_backups.py
    test_flashes.py
    test_tags.py
    test_routes.py            # adapted from v1
    test_clients.py           # unchanged
    e2e/
      conftest.py
      test_firmware_lifecycle.py
      test_flash_from_record.py
      test_flash_from_backup.py
      test_promote_backup.py
      test_bulk_delete_backups.py
      test_delete_refused_while_running.py
      test_replay_after_source_deletion.py
      test_bearer_upload.py
      test_logs_filters.py
```

## Data model

Five tables, plus a single-row `schema_version`. All ids are uuid hex
strings. All timestamps are UTC ISO8601 strings (`%Y-%m-%dT%H:%M:%SZ`).

### `firmware`

| col | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | uuid hex |
| `name` | TEXT NOT NULL | non-unique; UI warns on duplicate but allows |
| `description` | TEXT NOT NULL DEFAULT '' | |
| `sha256` | TEXT NOT NULL | lowercase hex of the `.hex` text bytes |
| `size_bytes` | INTEGER NOT NULL | size of the `.hex` text |
| `original_filename` | TEXT | as uploaded, may be NULL for bearer-uploads with no filename |
| `test_command` | TEXT | nullable lowercase hex |
| `expected_response` | TEXT | nullable lowercase hex |
| `source_backup_id` | TEXT | nullable; set when this firmware was promoted from a backup. No SQL FK — backups can be hard-deleted independently. |
| `created_at` | TEXT NOT NULL | |

Indexes: `firmware(name)`, `firmware(sha256)`.

The `.hex` bytes live at `blobs/firmware/<id>.hex` on disk. Bytes are
immutable after row creation; mutable fields are `name`, `description`,
`test_command`, `expected_response`, and the tag set (`firmware_tags`).

### `backups`

| col | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | uuid hex |
| `name` | TEXT NOT NULL | default `"<client> · <port> · <product or vid:pid> · <iso>"` |
| `description` | TEXT NOT NULL DEFAULT '' | |
| `sha256` | TEXT NOT NULL | from SerialHop's `backup.sha256` |
| `size_bytes` | INTEGER NOT NULL | from SerialHop's `backup.size_bytes` |
| `client` | TEXT NOT NULL | |
| `port_name` | TEXT NOT NULL | |
| `vid` | TEXT | from port snapshot at flash time; may be empty |
| `pid` | TEXT | |
| `serial_number` | TEXT | |
| `product` | TEXT | |
| `serialhop_saved_path` | TEXT | as reported by SerialHop |
| `test_command` | TEXT | nullable lowercase hex |
| `expected_response` | TEXT | nullable lowercase hex |
| `source_flash_id` | TEXT NOT NULL | id of the flash that captured this backup |
| `captured_at` | TEXT NOT NULL | |

Indexes: `backups(sha256)` (UNIQUE), `backups(captured_at DESC)`,
`backups(client, port_name)`.

The `sha256` UNIQUE constraint is the dedup anchor: a second flash that
captures bytes already in the library reuses the existing backup row;
no new row is inserted. See *Backup capture & dedup* below.

The `.hex` bytes live at `blobs/backups/<id>.hex`.

Mutable fields: `name`, `description`, `test_command`,
`expected_response`. Everything else is fixed at first-capture.

### `flashes`

The immutable audit log. Only `operator_note` is editable on a
terminal-status row.

| col | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | uuid hex |
| `status` | TEXT NOT NULL | `running` / `done` / `error` / `interrupted` |
| `outcome` | TEXT | SerialHop's `outcome` when `status=done`; NULL otherwise |
| `client` | TEXT NOT NULL | |
| `port_name` | TEXT NOT NULL | |
| `port_snapshot_json` | TEXT NOT NULL | JSON: `{vid, pid, serial_number, product}` from the port table at flash time |
| `source_kind` | TEXT NOT NULL | `firmware` or `backup` |
| `source_id` | TEXT NOT NULL | references `firmware.id` or `backups.id` (resolved by `source_kind`; no SQL FK so deletes don't cascade here) |
| `firmware_sha256` | TEXT NOT NULL | denormalised — what bytes hit the device |
| `firmware_name` | TEXT NOT NULL | denormalised — survives source rename or delete |
| `test_command_used` | TEXT | denormalised — what was sent |
| `expected_response_used` | TEXT | denormalised |
| `skip_backup` | INTEGER NOT NULL | 0 / 1 |
| `started_at` | TEXT NOT NULL | |
| `finished_at` | TEXT | NULL while running |
| `duration_ms` | INTEGER | NULL while running |
| `result_json` | TEXT | SerialHop's full 200 body, verbatim, when `status=done` |
| `error_code` | TEXT | when `status=error` |
| `error_detail` | TEXT | when `status=error` |
| `backup_id` | TEXT | id of the backup row produced by this flash (or reused via dedup); NULL when no backup was captured |
| `operator_note` | TEXT NOT NULL DEFAULT '' | mutable annotation |

Indexes: `flashes(started_at DESC)`, `flashes(source_kind, source_id)`,
`flashes(status)`, `flashes(client)`, `flashes(outcome)`.

### `tags`

| col | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | uuid hex |
| `name` | TEXT NOT NULL UNIQUE | freeform, case-sensitive |
| `created_at` | TEXT NOT NULL | |

### `firmware_tags`

| col | type | notes |
|---|---|---|
| `firmware_id` | TEXT NOT NULL | FK → `firmware.id` ON DELETE CASCADE |
| `tag_id` | TEXT NOT NULL | FK → `tags.id` ON DELETE CASCADE |
| PRIMARY KEY (`firmware_id`, `tag_id`) | | |

### `schema_version`

Single-row `(version INTEGER NOT NULL)` table. The migration runner
reads and updates this transactionally.

### Stats

Per-firmware and per-backup stats are computed by SQL aggregation over
`flashes` rows; nothing is precomputed or cached.

Summary card for firmware record `X`:

```sql
SELECT
  COUNT(*)                                       AS total,
  COUNT(*) FILTER (WHERE outcome = 'success')    AS successes,
  COUNT(*) FILTER (WHERE outcome LIKE 'rolled_back%') AS rollbacks,
  COUNT(*) FILTER (WHERE status = 'error'
                     OR outcome LIKE 'failed_%')      AS failures,
  MAX(started_at)                                AS last_flashed_at
FROM flashes
WHERE source_kind = 'firmware' AND source_id = ?;
```

Success rate = `successes / NULLIF(total, 0)`. The card also shows the
client + port from the `flashes` row whose `started_at` matches
`last_flashed_at`. Identical query for backup stats with
`source_kind='backup'`.

## Backup capture & dedup

After a successful or rolled-back flash, SerialHop's 200 response
carries `backup.hex`, `backup.sha256`, `backup.size_bytes`,
`backup.saved_path`, `backup.scope`. The flasher's flash worker, before
updating the `flashes` row to `done`:

1. Reads `backup.sha256` from the response.
2. Runs `SELECT id FROM backups WHERE sha256 = ? LIMIT 1`. Single
   writer means no race.
3. If a row matches, sets `flashes.backup_id` to that id. **No new
   backup row, no blob write.**
4. If no row matches, generates a new uuid, writes
   `blobs/backups/<id>.hex`, inserts a `backups` row, sets
   `flashes.backup_id` to the new id.

Because `backups.sha256` carries a UNIQUE constraint, a buggy concurrent
caller would be caught by the database, but the application-level
single-writer serialisation makes the integrity check defensive rather
than load-bearing.

When the operator hard-deletes a backup row, the dedup anchor goes with
it: a later flash producing the same bytes inserts a fresh row. We do
not auto-resurrect.

## Lifecycle & deletion rules

### Firmware records

- **Created** by operator upload (`POST /api/firmware`), bearer upload
  (`POST /api/v1/firmware`), or promotion from a backup
  (`POST /api/backups/{id}/promote`). Each path writes the row +
  the blob in a single SQL transaction wrapping a single filesystem
  write, in that order; on filesystem failure, the row insert is rolled
  back.
- **Updated** via `PATCH /api/firmware/{id}` — `name`, `description`,
  `test_command`, `expected_response`, and the tag set. The blob is
  never replaced.
- **Deleted** via `DELETE /api/firmware/{id}`. Hard. Two safety rails:
  1. Refuse (409, `cannot delete: flash in flight`) if any `flashes`
     row with `source_kind='firmware' AND source_id=? AND
     status='running'` exists.
  2. UI confirm dialog surfaces `COUNT(*)` of `flashes` rows that
     reference the record so the operator can decide.
  Deletion removes the row, removes all `firmware_tags` rows via
  CASCADE, and unlinks the blob. `flashes` rows that referenced it
  remain and still render their denormalised name/sha; the "Repeat
  this flash" action on those rows returns 410 Gone going forward.

### Backup records

- **Created** by the flash worker (auto-save after a flash) and never
  by direct operator action. Dedup as described above.
- **Updated** via `PATCH /api/backups/{id}` — `name`, `description`,
  `test_command`, `expected_response`.
- **Deleted** via `DELETE /api/backups/{id}` or
  `POST /api/backups/bulk-delete`. Hard. Same safety rails as firmware:
  refuse while a flash in flight references the row; UI dialog shows
  affected flash count.

### Flash records

- **Inserted** at `POST /api/flash` time with `status=running`. The row
  carries the denormalised firmware metadata at insertion so a server
  crash mid-flash still leaves the audit trail meaningful.
- **Updated** by the flash worker to `done` / `error` exactly once.
  Result body, error fields, `finished_at`, `duration_ms`, and
  `backup_id` are set in the same statement.
- **Interrupted on boot.** On startup, `UPDATE flashes SET
  status='interrupted', finished_at=?, error_code='interrupted',
  error_detail='server restarted while flash was running' WHERE
  status='running'`. Run once per boot before the router accepts
  requests.
- **Mutable annotation.** `PATCH /api/flashes/{id}/note` updates
  `operator_note` only; rejected (400) if `status='running'`.
- **Never deleted.** No `DELETE` endpoint on `/api/flashes/*`.

## Backend API

All operator routes live under `/flash/api/...`. The bearer-auth
automation route lives under `/flash/api/v1/...`. The flasher service
sees these paths verbatim — Caddy does not strip the `/flash` prefix.

### Clients & ports

`GET /api/clients` — returns every client in the roster, each annotated
with online status:

```json
{
  "clients": [
    { "name": "khamit_desktop",  "port": 8089, "online": true  },
    { "name": "protres_ksenios", "port": 8081, "online": false }
  ]
}
```

Online status is the same short TCP probe as v1; offline clients are
included rather than filtered.

`GET /api/clients/{name}/ports` — unchanged from v1. 404 if `{name}` is
not in the roster.

### Firmware

`GET /api/firmware` — list. Optional query params:

| param | meaning |
|---|---|
| `tag` (repeatable) | AND-filter by tag id |
| `q` | substring match on `name` (case-insensitive) |
| `limit` | default 100, max 500 |
| `before` | cursor: an `id`; rows with `id < before` lexicographically — paired with stable `ORDER BY created_at DESC, id DESC` |

Response shape:
```json
{
  "items": [
    {
      "id": "…", "name": "pump v3", "description": "…",
      "sha256": "…", "size_bytes": 95234,
      "original_filename": "pump-v3.hex",
      "test_command": "01", "expected_response": "aa",
      "tags": [{"id": "…", "name": "pump"}, {"id": "…", "name": "prod"}],
      "stats": {
        "total": 7, "successes": 6, "rollbacks": 1, "failures": 0,
        "last_flashed_at": "2026-05-15T11:02:14Z",
        "last_flashed_client": "khamit_desktop",
        "last_flashed_port": "COM3"
      },
      "created_at": "2026-05-13T09:11:00Z"
    }
  ],
  "next_before": "…"
}
```

`GET /api/firmware/{id}` — detail, same per-item shape as above. 404
if unknown.

`POST /api/firmware` — operator upload. Body:
```json
{
  "name": "pump v3",
  "description": "<optional>",
  "test_command": "<optional hex>",
  "expected_response": "<optional hex>",
  "tags": ["<tag_id>", "..."],
  "firmware": "<Intel HEX text>",
  "original_filename": "<optional>"
}
```
Validation: `name` 1..256 chars, `firmware` non-empty and ≤ 256 KiB,
hex pair valid + symmetric if either set, tag ids must exist. Returns
the new full row (same shape as `GET /api/firmware/{id}`).

`PATCH /api/firmware/{id}` — body holds any subset of `name`,
`description`, `test_command`, `expected_response`, `tags`. `tags` is a
full replace, not a partial update. Returns the updated row.

`DELETE /api/firmware/{id}` — hard delete. 409 with `{error: "flash in
flight"}` if a `running` flash references it. 200 on success. 404
otherwise.

`GET /api/firmware/{id}/download` — file response, `Content-Type:
text/plain` (Intel HEX is text), `Content-Disposition: attachment;
filename="<original_filename or id>.hex"`. Body is the raw `.hex`
bytes.

`GET /api/firmware/{id}/flashes` — paginated flash history for this
firmware. Same paging shape as `/api/flashes` below.

### Bearer-auth firmware endpoints

`POST /api/v1/firmware` — same body shape as the operator endpoint.
`Authorization: Bearer <token>` required; `tags` are optional.
- 401 if header missing or token mismatched.
- Otherwise identical to the operator endpoint.

`GET /api/v1/firmware?sha256=<hex>` — idempotency probe.
- 200 with `{id, name, sha256, size_bytes, created_at}` if a row exists
  with that sha256.
- 404 otherwise.
- Same bearer requirement.

No silent dedup on POST. A CI caller wanting "create or get" semantics
runs the GET first.

### Backups

`GET /api/backups` — list. Optional query params: `client`, `q`
(name/description substring), `limit`, `before`. Defaults sort by
`captured_at DESC`. Response item:
```json
{
  "id": "…", "name": "…", "description": "…",
  "sha256": "…", "size_bytes": 95234,
  "client": "khamit_desktop", "port_name": "COM3",
  "vid": "2341", "pid": "0043", "serial_number": "…", "product": "Arduino Uno",
  "serialhop_saved_path": "C:\\ProgramData\\…\\COM3-…",
  "test_command": "…", "expected_response": "…",
  "source_flash_id": "…",
  "captured_at": "2026-05-14T17:11:09Z",
  "stats": { /* same shape as firmware stats */ }
}
```

`GET /api/backups/{id}` — single backup detail.

`PATCH /api/backups/{id}` — body: any subset of `name`, `description`,
`test_command`, `expected_response`. Returns the updated row.

`DELETE /api/backups/{id}` — hard delete. Same 409 rule for in-flight
references.

`POST /api/backups/bulk-delete` — body `{ ids: ["…", "…"] }`. Returns
`{ deleted: N, refused: [{id, reason}, …] }`. Per-id refusals (in-flight
reference) don't fail the whole call. Atomic per id; not atomic across
ids.

`GET /api/backups/{id}/download` — same shape as the firmware download.

`GET /api/backups/{id}/flashes` — paginated flash history for this
backup as source. Same shape as `/api/flashes`.

`POST /api/backups/{id}/promote` — clones bytes into a new firmware
record. Body:
```json
{
  "name": "…",
  "description": "<optional>",
  "tags": ["<tag_id>", "..."],
  "copy_test_pair": true
}
```
Returns the new firmware row (full shape). The backup row is unchanged;
`firmware.source_backup_id` on the new row points back to the backup
for provenance.

### Flashes

`POST /api/flash` — start a flash. Body:
```json
{
  "client":   "khamit_desktop",
  "port":     "COM3",
  "source":   { "kind": "firmware", "id": "<uuid>" },
  "test_override":      { "command": "01", "expected_response": "aa" },
  "save_test_to_record": false,
  "skip_backup": false
}
```
- `source.kind` ∈ `firmware` / `backup`. `source.id` references the
  corresponding library row.
- `test_override` is optional. If omitted, the source row's stored
  test pair is used (or no test if the source has none / both fields
  null). Asymmetric hex (one set, one not) is a 400.
- `save_test_to_record: true` writes the override back to the source
  row's `test_command` / `expected_response` *before* kicking off the
  flash. Defaults to `false`.
- The handler:
  1. Validates the request; loads the source row (and reads the blob
     into memory).
  2. Captures `port_snapshot` from a fresh `GET
     /serial/ports/detailed` against the target client. Missing port
     → 400. Cached for the lifetime of the request.
  3. If `save_test_to_record`, applies the PATCH-equivalent update.
  4. Inserts the `flashes` row with `status='running'` and all
     denormalised fields. Returns `{ job_id }` (the row id).
  5. Schedules a background task: `POST /devices/disconnect` then
     `POST /flash/{port}` against SerialHop, mapping the response or
     error per v1 rules. On terminal outcome, updates the row to
     `done` or `error` and (if backup was captured) runs the dedup
     procedure and sets `backup_id`.
- Single-flight is enforced by SerialHop, same as v1; the flasher
  relays its 409 verbatim.

`GET /api/flash/{id}` — fetch one row. Same envelope as v1 (status +
either result / error / running detail), augmented with the
denormalised fields and `operator_note`.

`GET /api/flash/current` — the most-recent `running` row, or `{}`.
SQL: `SELECT … FROM flashes WHERE status='running' ORDER BY
started_at DESC LIMIT 1`.

`GET /api/flashes` — paginated history. Query params:

| param | meaning |
|---|---|
| `client` (repeatable) | filter by client name |
| `outcome` (repeatable) | filter by `outcome` or status (`success`, `rolled_back_*`, `failed_*`, `error`, `interrupted`) |
| `source_kind` | `firmware` / `backup` |
| `source_id` | filter on source id (typeahead-by-name resolves to id on the SPA side) |
| `since` | ISO date; `started_at >= since` |
| `until` | ISO date; `started_at <= until` |
| `limit` | default 50, max 500 |
| `before` | cursor: `id` |

Response item — essentials only; full detail comes via
`/api/flash/{id}`:
```json
{
  "id": "…", "status": "done", "outcome": "success",
  "client": "khamit_desktop", "port_name": "COM3",
  "firmware_name": "pump v3", "firmware_sha256": "…",
  "source_kind": "firmware", "source_id": "…",
  "started_at": "…", "duration_ms": 23104,
  "operator_note": ""
}
```

`PATCH /api/flashes/{id}/note` — body `{ "note": "…" }`. 400 if
`status='running'`. Returns the updated row's note.

`POST /api/flashes/{id}/replay` — body `{ "client": "?", "port": "?" }`
(both optional; defaults to the original row's values). Resolves the
source row by `source_kind`/`source_id`; if the source has been
deleted, returns 410 Gone with `{ "error": "source deleted" }`.
Otherwise constructs the equivalent `POST /api/flash` body (using the
original `test_command_used` / `expected_response_used`) and returns
the new `{ job_id }`.

### Tags

- `GET /api/tags` — `{ items: [{id, name, created_at, firmware_count}] }`.
  `firmware_count` is a JOIN-aggregate; cheap at this scale.
- `POST /api/tags` — `{ name }`. 400 if name already exists.
- `PATCH /api/tags/{id}` — `{ name }`. 400 on duplicate.
- `DELETE /api/tags/{id}` — hard delete. CASCADE removes
  `firmware_tags` rows. The firmware records themselves are unaffected.

### Error envelopes

All 4xx/5xx responses use `{ "error": "<code>", "detail": "<msg>" }`,
matching v1 and SerialHop. Error codes added in this design:

| Status | Codes (new) |
|---|---|
| 400 | `invalid request`, `name in use`, `tag not found`, `source missing test pair fields` |
| 401 | `bearer required`, `bearer invalid` |
| 404 | `unknown firmware`, `unknown backup`, `unknown flash`, `unknown tag`, `unknown source` |
| 409 | `cannot delete: flash in flight` |
| 410 | `source deleted` (replay path only) |

SerialHop's own error codes still flow through into `flashes.error_code`
unchanged.

## Frontend

Single SPA. Top-level: a `TabBar` and a content pane. State is held in
React; no router. Internal navigation (e.g. opening a flash detail
drawer) is component state.

### App-level concerns

- On mount, the SPA calls `GET /api/flash/current`. If a row is
  returned, the Flash tab opens with the running view visible below
  the form; otherwise the Flash tab is in its idle state.
- A global polling loop (interval 1500 ms) runs whenever any flash row
  is `running` in the SPA's state — tied to a `running_flash_id` slice,
  not to which tab is foreground. The polling stops when the row
  reaches a terminal status.
- Tab switching never affects polling or running state.

### Tab 1 — Flash

A single vertically-scrolling page. The form ("wizard") is always
rendered at the top. The running view replaces itself with the result
view as the flash progresses. Both render below the form. No "Flash
another" / "Done" buttons; the operator simply edits the form and
clicks Flash again.

Form sections, top to bottom:

1. **Lab machine picker** — dropdown of every roster client. Offline
   rows are visible but rendered muted and not selectable. A small
   "Retry probe" link refetches.
2. **Port table** — same component as v1, enabled when a client is
   picked.
3. **Firmware source picker** — combobox with two segments:
   *Firmware* (the firmware library, with tag filter + name search)
   and *Backups* (the backup library, with name search). A third
   sticky option, *Create new firmware…*, expands an inline upload
   form (name [required], description, tags, optional test pair, file
   picker). Submitting the inline form `POST`s `/api/firmware` and
   selects the new record. The selected source's metadata (sha256
   short, size, original filename for firmware, captured client/port
   for backups) shows below the combobox.
4. **Test pair editor** — same component as v1, prefilled from the
   source. A checkbox **"Save edits to record"** appears (and is
   only enabled) once the operator has edited a prefilled value.
   When the source has no test pair, the editor is unlocked but
   empty.
5. **Skip backup switch** — unchanged from v1.
6. **Flash button** — same label and gating as v1.

Below the form:

- **Running view** — header `<client> · <port> · <firmware name>`,
  elapsed mm:ss, indeterminate progress bar, "Typical 15–30 s; up to
  ~60 s in worst case." line. Polls `/api/flash/{id}` until terminal.
- **Result view** — outcome badge (colours per v1), stage strip
  (`StageStrip`), test diff (`HexDiff`) if `test_result` present,
  backup card (`saved_path`, `sha256`, `size_bytes`, `scope`), recovery
  hint when relevant, collapsible Raw JSON. No buttons. Just below the
  form; stays until the next flash starts.

### Tab 2 — Firmware

Two-pane layout.

- **Left pane** — `FirmwareList`. Search box (`q`) and a tag filter
  chips row. Each row: name + tag chips, sha256 short, size, total
  flashes / success rate, last flashed at, kebab menu (Download,
  Delete). Header buttons: **Upload firmware** (opens the same inline
  form used in the Flash tab) and **Manage tags** (opens
  `TagManager`).
- **Right pane** — `FirmwareDetail` for the selected row. Inline
  editable fields: name, description, test pair, tag set.
  `StatsCard` shows summary aggregates. Below, a paginated list of
  the firmware's `flashes` rows; row click opens a `LogDetailDrawer`.

`TagManager` modal lists all tags with `firmware_count`, supports
create / rename / delete with the usual confirm on delete.

### Tab 3 — Backups

Two-pane layout, parallel to Firmware.

- **Left pane** — `BackupList`. Search box (`q`), client filter
  dropdown. Each row: row checkbox, name, captured at, client / port /
  product, sha256 short, size, used-in-flashes count, kebab (Download,
  Promote to firmware…, Delete). Header bulk action: **Delete
  selected** (calls `/api/backups/bulk-delete`).
- **Right pane** — `BackupDetail`. Inline editable: name, description,
  test pair. Read-only identifying-metadata card: vid / pid /
  serial_number / product / client / port / captured_at /
  serialhop_saved_path / sha256 / size. `StatsCard` showing how many
  flashes used this backup as source. Paginated flash list below; row
  click opens `LogDetailDrawer`. The "Promote to firmware…" action
  opens a small modal (name [required], description, tags, copy-test-
  pair checkbox) wired to `POST /api/backups/{id}/promote`.

### Tab 4 — Logs

Single-pane reverse-chronological table of every flash row.

- **Filters bar** (`LogFilters`) above the table:
  - Client (multi-select)
  - Outcome / status (multi-select; treats `error` and `interrupted`
    as their own outcomes for filter purposes)
  - Source kind (firmware / backup / either)
  - Source typeahead (filtered by kind)
  - Date range (since / until, date pickers)
  - Clear-all button. Filter state mirrors to the SPA's URL query
    string for sharability.
- **Table** (`LogTable`) — columns: started_at, client, port_name,
  source kind icon + firmware_name (+ tag chips for firmware), outcome
  badge, duration, operator_note (truncated, full on hover). Row click
  opens `LogDetailDrawer`. Pagination via the same cursor scheme.
- **`LogDetailDrawer`** — slides in from the right. Shows the full
  per-flash payload: stage strip, full SerialHop response with test
  diff, backup info with a link to the backup row, raw JSON panel,
  the **operator note editor** (inline `PATCH`), and a **Repeat this
  flash** button. Repeat is disabled (with the explanatory tooltip)
  when the source has been deleted.

### Component reuse

Carry forward from v1: `ClientPicker` (tweaked for offline rendering),
`PortTable`, `TestPairEditor`, `FlashOptions`, `FlashButton`,
`RunningView`, `StageStrip`, `HexDiff`, the `ResultView` minus its
buttons.

On the backend, the v1 in-memory `JobStore` class is removed; its
responsibilities migrate to `flashes.py`'s SQL-backed queries.

## Configuration

Extended `config.py`:

| Env var | Required | Default | Meaning |
|---|---|---|---|
| `FLASHER_CLIENTS_FILE` | yes | — | path to siteapp's `clients.json` |
| `FLASHER_CHISEL_HOST` | no | `chisel` | hostname for SerialHop URLs |
| `FLASHER_DATA_DIR` | yes | — | persistent data directory; SQLite + blob store |
| `FLASHER_UPLOAD_TOKEN__FILE` | no | — | path to a file holding the bearer token |
| `FLASHER_UPLOAD_TOKEN` | no | — | inline bearer token (lower-priority than `__FILE`) |

If neither token env var is set, the flasher synthesises a per-process
random token at boot (`secrets.token_urlsafe(32)`) so dev environments
boot cleanly. The synthesised token is logged once at INFO so a
developer can curl with it. Production deploys always set
`FLASHER_UPLOAD_TOKEN__FILE`.

## Compose & Caddy changes

### `compose/docker-compose.yml.tmpl`

```yaml
flasher:
  image: __FLASHER_IMAGE__
  restart: unless-stopped
  environment:
    FLASHER_CLIENTS_FILE: /etc/flasher/clients.json
    FLASHER_CHISEL_HOST: chisel
    FLASHER_DATA_DIR: /var/lib/flasher
    FLASHER_UPLOAD_TOKEN__FILE: /run/secrets/flasher_upload_token
  volumes:
    - ./siteapp/clients.json:/etc/flasher/clients.json:ro
    - ./flasher_data:/var/lib/flasher
    - ./flasher/upload_token:/run/secrets/flasher_upload_token:ro
  networks: [labnet]
```

### `compose/Caddyfile.tmpl`

Two ordered `handle` blocks — the specific bearer-auth one first:

```caddy
# Flasher bearer-auth automation. Caddy passes through; flasher verifies the token.
handle /flash/api/v1/* {
    reverse_proxy flasher:8000
}
# Flasher operator UI + operator API. Caddy enforces basic_auth.
handle /flash* {
    basic_auth {
        admin __ADMIN_BCRYPT_HASH__
    }
    reverse_proxy flasher:8000
}
```

### `scripts/lib/render.sh`

Renders `compose/flasher/upload_token` from the laptop's `config.yaml`
(new key under `secrets`). The deploy step in CI renders it from the
GH repo secret instead. Same shape as the existing
`siteapp/admin_password_hash` rendering.

## Secrets flow — `FLASHER_UPLOAD_TOKEN`

Unlike siteapp's `agent_upload_token` (laptop primary), this token's
canonical copy is the **GitHub repo secret**, because the primary
consumer is GitHub Actions (the firmware-build pipeline that calls
`POST /api/v1/firmware`). The flasher service is the secondary consumer
that verifies headers. The laptop mirror exists only for manual
`task deploy` runs.

New laptop command: `task secrets:rotate-flasher-upload-token`. It:

1. Generates a new value (`openssl rand -hex 32`).
2. Writes it to the local `config.yaml` (under `secrets.flasher_upload_token`).
3. Calls `gh secret set FLASHER_UPLOAD_TOKEN --body <value>` against the repo.
4. Prints a reminder: "Rotate at any time; CI consumers will pick up
   the new value on their next run."

Setting / rotating is the only blessed write path — both copies move in
lockstep. There is no read path for the GH secret (GH only exposes
secrets to running workflows), so the laptop's local copy is what gets
rendered during a `task deploy`.

## Database migrations

`services/flasher/app/db.py` exposes:

- `connect()` → returns an `aiosqlite.Connection` configured with the
  WAL / synchronous / foreign-keys PRAGMAs.
- `migrate(db)` → reads `schema_version`, runs every `.sql` in
  `migrations/` whose numeric prefix is greater than the current
  version, in ascending order, each inside a transaction. Updates
  `schema_version` at the end of each. Idempotent.

`main.py` calls `migrate()` during FastAPI's startup event before the
router accepts requests. On a fresh container, the `flasher.db` file
doesn't exist; the migration runner creates it.

`0001_init.sql` creates the full schema described above, plus the
single `schema_version` row.

The on-boot interrupted-job sweep runs after migrations, before the
router accepts requests.

## Release pipeline

The flasher service is its own release-please component. This
implementation produces:

- A `feat` commit on `services/flasher/**` → `flasher` component bumps
  (likely a minor or major version per release-please's rules).
- Compose / Caddy / scripts changes → `platform` component bumps.
- Both release-please PRs open in parallel; merge order doesn't
  matter.

The compose template already routes traffic to the flasher image via
`__FLASHER_IMAGE__`; the new `flasher_data` bind-mount is created by
the existing render step (or by the container at first start — bind-
mounted source directories are auto-created by Docker if missing).

The CI deploy workflow's "render secrets" stage gains one entry for
`compose/flasher/upload_token` (sourced from the GH secret
`FLASHER_UPLOAD_TOKEN`).

## Testing

### Unit (`services/flasher/tests/`)

- `test_db.py` — migration runner applies in order, updates
  `schema_version`, idempotent re-run, rolls back on bad SQL within a
  file, fresh-DB bootstrap.
- `test_firmware.py` — CRUD; sha256 + size correctness; blob write/read;
  delete-blocked-while-running-flash-references; deletion unlinks blob
  and CASCADEs tags.
- `test_backups.py` — auto-insert path, sha256 dedup (insert vs reuse),
  PATCH of labels, bulk-delete with mixed pass/refuse, blob lifecycle.
- `test_flashes.py` — insert-at-start, terminal update, on-boot sweep
  marks stale `running` rows interrupted, stats aggregation correctness,
  replay path 410 when source deleted, note PATCH rejected while
  running.
- `test_tags.py` — CRUD, unique-name enforcement, CASCADE on delete.
- `test_routes.py` — adapted from v1: FastAPI `TestClient` against an
  in-memory or tmpdir SQLite, mocked `httpx` for SerialHop. Covers
  every new route, validation rejections, error envelopes.
- `test_clients.py` — unchanged shape; the response now includes
  `online: bool` for every roster entry.

### Service e2e (`services/flasher/tests/e2e/`)

A real flasher container with a tmpdir-backed `FLASHER_DATA_DIR` and a
FastAPI-based SerialHop stub. Mirrors v1's e2e style.

- `test_firmware_lifecycle.py` — operator POST/PATCH/DELETE/download/
  promote flows, including 409 on delete-while-running.
- `test_flash_from_record.py` — full flow: pick firmware, flash, result
  view, flash row in `flashes`, backup auto-saved.
- `test_flash_from_backup.py` — same as above but `source.kind=backup`.
- `test_promote_backup.py` — promote creates firmware record with same
  bytes and `source_backup_id` set.
- `test_bulk_delete_backups.py` — mixed pass/refuse outcomes.
- `test_delete_refused_while_running.py` — 409 when running flash
  references the target.
- `test_replay_after_source_deletion.py` — replay returns 410 once
  source is gone; flash row's denormalised fields still render.
- `test_bearer_upload.py` — bearer-auth POST + sha256 idempotency
  probe; 401 on missing/wrong token.
- `test_logs_filters.py` — every filter param narrows the list as
  expected; date range; multi-value filters AND across params, OR
  within param.

### Platform integration (`tests/integration/`)

- Extend `test_routes_smoke.bats`: assert `/flash/api/v1/firmware`
  reaches the flasher *without* a basic_auth challenge, and returns
  401 without a bearer header. (Caddy ordering of the two `handle`
  blocks is the only thing this guards.)
- No new bats file.

## Open questions / deferred decisions

- **Device entity.** Operator-named or auto-detected device rows that
  group flashes/backups by physical board. Deferred. The denormalised
  USB descriptors plus `last_seen_*` fields on backup and flash rows
  are enough to identify hardware in the meantime.
- **Backup retention / pruning.** Operator-managed bulk delete only in
  v1. If storage cost becomes a problem, add a configurable cap.
- **Backup-vs-firmware / backup-vs-backup diff.** Useful for "what
  changed on this board between flashes"; modestly expensive (HEX-
  aware byte diff). Out of v1 scope.
- **Pin / favourites on firmware records.** Defer until the library
  size makes scrolling painful.
- **Full-text search on names/descriptions.** Substring filter is
  enough for v1; SQLite FTS5 is a cheap upgrade if it becomes useful.
- **Per-flash duration breakdown chart** in the per-firmware stats
  card. Defer.
- **Audit-log export** (download flashes as CSV). Defer.
- **Permanent purge of orphaned blobs.** With no soft-delete, every
  blob has a row; an orphan can only appear after a partial-failure
  during creation (row insert succeeded, blob write failed — or
  vice-versa). The CRUD code wraps both into a single
  transaction-then-fsync pattern; a small startup integrity sweep can
  be added later if needed.

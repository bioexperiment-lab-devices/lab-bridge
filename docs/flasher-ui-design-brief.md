# Flasher — UI/UX brief for redesign

This document describes the **Flasher** web app as it exists today. It enumerates every screen, every interactive element, and every user flow, without prescribing any visual style. Use it as the functional source of truth for a from-scratch redesign.

---

## 1. What the app does

Flasher is an internal tool for embedded engineers in a hardware lab. It lets an operator push compiled firmware (`.hex` files) to USB‑connected microcontrollers that are physically plugged into one of several remote "lab machines" (e.g. `lab-rpi-1`, `lab-rpi-2`). The full job is **disconnect any app currently using the target port → back up its current flash → erase → program → verify → optionally run a post‑flash hex test → roll back on failure**. Other ports on the same lab machine are not touched.

The same UI is also a permanent archive of firmware, of device backups, and of every flash that has ever run, so engineers can inspect what happened, replay a previous run on the same or a different device, and promote an interesting backup into a reusable firmware record.

Operators are technical (they know what a VID/PID is, they read raw hex). They are NOT software engineers — the UI is the only way they touch the system.

---

## 2. Top‑level navigation

The app is a single page with **four tabs** in a horizontal tab bar:

1. **Flash** — perform a flash. The "doing work" tab.
2. **Firmware** — browse, edit, upload firmware records.
3. **Backups** — browse, edit, delete, promote device backups.
4. **Logs** — browse the history of every flash that ever ran.

Only one tab is visible at a time. The tab bar is always present.

There is **no login screen** in the UI — the service is behind reverse‑proxy auth, so the user just lands on the Flash tab.

### Cross‑tab persistent state

- If a flash is currently in progress (started in another tab or by another user), the app detects it on load and the Flash tab shows the "Running…" state instead of the empty form. The polling loop updates the UI every 1.5 seconds until the flash terminates.

---

## 3. Tab 1 — Flash

### Purpose

Walk the operator through "I want to push *this firmware* to *this device* on *this lab machine*". This is the most frequently used screen.

### Layout

Two regions stacked or side‑by‑side:

- **Left/top: the form** — a vertical sequence of numbered steps the operator fills in top‑to‑bottom.
- **Right/bottom: the output area** — empty until a flash is in progress or just finished. Then it shows either the **Running view** or the **Result view**.

### Form elements, in order

#### 3.1 Lab machine picker

- Label: "Lab machine:"
- A dropdown listing every lab machine known to the server.
- Each option shows the machine's name (e.g. `lab-rpi-1`). Offline machines are shown but **disabled and suffixed " — offline"**.
- A **"Retry probe"** button next to the dropdown re‑queries the server for online status (the server actively pings each lab machine and returns the freshest status).
- Default: nothing selected (`(select…)`).
- Until a machine is picked, no further form steps are shown.

#### 3.2 Serial port table (only after a machine is picked)

- Header: "2. Serial port" with a **"Refresh"** button.
- Tabular list of every serial device the chosen lab machine currently sees. One row per port. Columns:
  - **Radio button** (single‑select)
  - **Port** — e.g. `/dev/ttyUSB0`
  - **Product** — human string from the USB descriptor (e.g. `FT232R USB UART`), or `—`
  - **VID:PID** — e.g. `0403:6001`, or `—`
  - **Serial** — the USB serial number, or `—`
  - **Status** — either `—` (free) or `In use — <device_id>` (some other process on the lab machine currently has the port open; the flash will forcibly disconnect that process from this port only — other ports on the same machine are left alone).
- Non‑USB ports (e.g. on‑board UARTs) are visually de‑emphasized but still selectable.
- Clicking anywhere on a row selects it.
- Empty state: "No serial ports reported by `<lab-machine>`."
- Loading state: "Loading…"
- Error state: "Failed to load ports: `<error>`"

Example row:
```
( • )  /dev/ttyUSB0   FT232R USB UART   0403:6001   AB0KL3Q9   In use — siteapp
```

#### 3.3 Firmware source picker

The same widget covers two distinct things — picking an existing firmware record OR picking an existing backup to flash back onto a device. Both kinds end up as the "source" of the flash.

- Header row contains three controls:
  - Segmented control: **Firmware** | **Backups** (mutually exclusive)
  - Button: **+ Create new firmware** (opens the firmware upload modal, see §7.1)
- A search box (`search by name`) that filters the list below.
- If **Firmware** segment is active: a row of **tag chips** under the search box. Clicking a chip toggles the filter (multi‑select; AND semantics on the server — selecting `production` and `v2` shows firmware that has BOTH tags).
- Below: a scrollable list of records.
  - **Firmware row** shows: name, its tag chips, and a meta line `sha <first 12 chars of sha256> · <size> B`.
  - **Backup row** shows: name, and a meta line `<captured_at> · <client>/<port_name> · sha <first 12 of sha256>`.
- Clicking a row selects it (highlighted). Below the list a "Selected: firmware — `<name>`" / "Selected: backup — `<name>`" line appears with a **Clear** button.

Example firmware row:
```
sensor-board-v2.3.0
[production] [v2]
sha 9af3b1c0e8a2 · 14336 B
```

Example backup row:
```
lab-rpi-1-ttyUSB0-2026-05-12T14:22:01Z
2026-05-12T14:22:01Z · lab-rpi-1/ /dev/ttyUSB0 · sha 7b1d2e0f9aa3
```

#### 3.4 Post‑flash test pair editor (only after a source is selected)

- Header: "4. Post-flash test" with an **On/Off toggle**.
- When **On**, two side‑by‑side hex inputs:
  - **`test_command`** — bytes to send to the device over serial after programming.
  - **`expected_response`** — bytes the device must reply with for the flash to be considered successful.
- Each hex input is a free‑text field that displays the value as space‑separated bytes (e.g. `01 02 A0 FF`). Below each field:
  - `<N> bytes` counter
  - `invalid hex` error label (only if the input is not parseable)
  - `ASCII: <printable preview>` showing the bytes as text where printable, e.g. `ASCII: ".U.."`
- When **Off**, a muted hint appears instead: *"The flash will succeed on byte-verify alone. No payload will be sent to the device after programming."*
- Initial values are pre‑filled from the selected source (firmware/backup record may have a saved test pair). Toggle defaults to On if the source has a test command, otherwise Off.
- A separate single checkbox below (visible only when source is **firmware**): **"Save edits to record"** — when checked, the test pair edits made here are persisted back onto the firmware record after the flash submits.

Example:
```
test_command:        55 AA 01 03            4 bytes   ASCII: "U..."
expected_response:   55 AA 81 00 FF FF     6 bytes   ASCII: "U....."
```

#### 3.5 Options

- Header: "5. Options"
- One toggle: **"Skip backup"**.
- When **Off** (default) — muted hint: *"The current device flash will be captured to disk on the lab machine before erasing. Adds ~8 s."*
- When **On** — warning hint with a ⚠ icon: *"The device's existing flash will not be saved. There will be no way to restore the previous firmware from the lab machine if this flash needs to be rolled back."*

#### 3.6 Submit

- Single primary button: **"Disconnect port and flash"**.
- Disabled until: a machine is picked, a port is selected, a source is chosen, AND (if the post‑flash test toggle is on) both hex fields are non‑empty.
- The label deliberately tells the operator the side‑effect: any application that currently has THIS port open on the lab machine WILL be kicked off it. Other ports on the same machine are unaffected.
- Error area below the button shows server errors verbatim (e.g. `Device already in flashing state` or validation errors).

### Output area states

#### 3.7 Running view

Shown while a flash is in progress. Replaces the form's right pane (or appears below). Contains:

- Heading: "Flashing…"
- Meta line: `<lab-machine> · <port> · <firmware-name>` (in monospace where appropriate).
- An indeterminate progress bar.
- Live elapsed timer in `MM:SS` format, updated every second.
- A muted hint: *"Typical 15–30 s; up to ~60 s in worst case."*

There is **no Cancel button**. A flash, once started, runs to completion (including its own rollback‑on‑failure logic).

#### 3.8 Result view

Shown the moment a flash terminates. Contains:

- A coloured **outcome badge**. The colour maps to one of three buckets:
  - **green** — `success`
  - **amber** — anything else that's not catastrophic (e.g. `rolled_back_verify_failed`, `rolled_back_test_failed`, `failed_preflight`, `failed_backup`, `interrupted`)
  - **red** — `failed_no_recovery`, `error`
- If the outcome carries a structured error: a heading with the **error code** (e.g. `VERIFY_MISMATCH`, `TEST_TIMEOUT`) and a paragraph of **error detail**.
- A definition list of meta:
  - Client
  - Port
  - Firmware
  - Started (ISO timestamp)
  - Finished (ISO timestamp, if terminal)
  - Duration (ms)
  - Backup ID (if a pre‑flash backup was captured — clicking it should ideally jump to the Backups tab on that record)
- A collapsible **"Raw result JSON"** section showing the full result payload (stages, test_result with expected/received bytes, etc.) — useful for debugging.

Example outcome badges and codes (see also §6, log detail drawer, which shows the same data more richly):

| Outcome | Bucket | Typical error code |
|---|---|---|
| `success` | green | — |
| `rolled_back_verify_failed` | amber | `VERIFY_MISMATCH` |
| `rolled_back_test_failed` | amber | `TEST_TIMEOUT`, `TEST_MISMATCH` |
| `failed_preflight` | amber | `PREFLIGHT_NO_DEVICE`, `PREFLIGHT_HEX_INVALID` |
| `failed_backup` | amber | `BACKUP_READ_FAILED` |
| `interrupted` | amber | — |
| `failed_no_recovery` | red | `ROLLBACK_FAILED` (device is potentially bricked) |
| `error` | red | uncategorised |

---

## 4. Tab 2 — Firmware

### Purpose

The catalogue of every firmware blob known to the system. Each firmware record is a `.hex` file plus metadata (name, description, tags, default test pair, link back to its source backup if it was promoted from one) plus accumulated **flash statistics**.

### Layout

Two panes side‑by‑side, with a thin header bar above them.

- **Header bar (above both panes):**
  - Button: **"Upload firmware"** — opens the firmware upload modal (§7.1).
  - Button: **"Manage tags"** — opens the tag manager modal (§7.2).
- **Left pane:** filterable list of firmware records.
- **Right pane:** detail view of the selected record. If nothing is selected, shows the placeholder text *"Select a firmware record on the left."*

### 4.1 Left pane — firmware list

- A **filter bar** at the top:
  - A search input (`search by name`) — substring match on the firmware name.
  - A row of **tag chips** — multi‑select toggle filter (AND semantics, same as on the Flash tab source picker).
- Scrollable list of rows. Each row contains:
  - **Name** (e.g. `motor-controller-v1.4`)
  - **Tags** as chips (e.g. `[production]`, `[experimental]`)
  - **Meta line**: `<first 12 chars of sha256> · <size> B · flashes: <total>`
  - **Inline actions** on the right:
    - **Download** link — downloads the `.hex` file with its original filename.
    - **Delete** button — opens a native confirm dialog.
      - If the firmware has never been flashed: *"Delete firmware "name"?"*.
      - If it has been flashed: *"Delete firmware "name"? It was used in `<N>` flashes — replay on those rows will fail."*.
- Clicking a row (not the action buttons) selects it.

Example row:
```
motor-controller-v1.4
[production] [v2-firmware]
9af3b1c0e8a2 · 14336 B · flashes: 27
                                                          [Download]  [Delete]
```

### 4.2 Right pane — firmware detail

When a firmware is selected, shows:

- **Heading**: firmware name.
- **Subheading (muted)**: `sha256 <full hash> · <size> B · created <ISO timestamp>`.
- **Stats card** (see §8.1) — flash count, success rate, last flashed info.
- **Edit form** with these fields:
  - Name (text input, required)
  - Description (multi‑line textarea)
  - Test command (single‑line text input — same hex semantics as on the Flash tab; ideally use the same hex‑aware input widget)
  - Expected response (same as above)
  - **Tags** fieldset — a checkbox per known tag.
  - **Save** button to commit.
- **"Flash history"** section: a vertical list of every flash that used this firmware. Each line: `<started_at> · <client> · <port_name> · <outcome or status> · <duration in seconds, if any>`. Clicking a line opens the **Log detail drawer** (§7.4) for that flash, NOT a navigation away.

Example flash history line:
```
2026-05-14T09:13:22Z · lab-rpi-1 · /dev/ttyUSB0 · success · 18.3s
```

---

## 5. Tab 3 — Backups

### Purpose

Same shape as the Firmware tab, but for **device backups** — copies of whatever firmware was on a device at the moment some flash captured it. Backups are valuable for two reasons: (a) they let you restore a device to its prior state and (b) an interesting backup can be **promoted** into a normal firmware record (so it can then be flashed onto OTHER devices and tagged like any other firmware).

### Layout

Identical two‑pane structure as Firmware (left list, right detail). **No top header bar** — actions live on each row and inside the detail.

### 5.1 Left pane — backup list

- **Filter bar:**
  - Search input (`search by name`).
  - Client dropdown (`(any client)` plus every lab machine).
  - **Bulk delete** button: *"Delete selected (`<N>`)"* — enabled only when one or more checkboxes are ticked. Triggers a confirm dialog *"Delete `<N>` backups?"*. The server may refuse to delete some (e.g. if they're still referenced by undeleted flashes); refusals are reported back with a per‑item reason and surfaced in an alert.
- Scrollable list of rows. Each row contains:
  - **Checkbox** for bulk select.
  - **Name** (defaults to `<lab-machine>-<port>-<ISO timestamp>` but is editable in detail view).
  - **Meta line**: `<captured_at> · <client> · <port_name> · <product OR VID:PID> · sha <first 12 chars> · flashes: <total times this backup has been re-flashed>`.
  - **Inline actions**:
    - **Download** — downloads the captured `.hex` file.
    - **Promote** — opens the Promote modal (§7.3) to turn this backup into a firmware record.
    - **Delete** — confirm dialog *"Delete backup "name"?"*. Refusal reasons (e.g. still referenced) shown in an alert.

Example row:
```
[ ]  lab-rpi-1-ttyUSB0-2026-05-12T14:22:01Z
     2026-05-12T14:22:01Z · lab-rpi-1 · /dev/ttyUSB0 · FT232R USB UART · sha 7b1d2e0f9aa3 · flashes: 0
                                                              [Download]  [Promote]  [Delete]
```

### 5.2 Right pane — backup detail

When a backup is selected, shows:

- **Heading**: backup name.
- **Subheading (muted)**: `sha256 <full hash> · <size> B · captured <ISO timestamp>`.
- **Device metadata grid (definition list)**:
  - Client
  - Port
  - VID:PID
  - Serial # (or `—`)
  - Product (or `—`)
  - SerialHop path (the on‑disk path where the lab machine stored the backup file)
- **Stats card** (§8.1).
- **Edit form** with:
  - Name
  - Description
  - Test command (hex)
  - Expected response (hex)
  - **Save** button.
- **"Used by flashes"** section: list of every flash that used this backup as its source (i.e. flashes that restored this backup onto a device). Same row shape as the firmware detail flash history. Clicking a row opens the Log detail drawer.

---

## 6. Tab 4 — Logs

### Purpose

The audit trail. Every flash that has ever run shows up here with its outcome, timing, and operator note. This is where engineers do post‑mortems and where they replay a previous flash.

### Layout

Two stacked regions:

- **Top: filter panel**
- **Below: results table**

Clicking any row opens the **Log detail drawer** (§7.4) on the right side, overlaying the table.

### 6.1 Filter panel

A horizontal arrangement of fieldsets:

- **Client** — fieldset of checkboxes, one per known lab machine. Each label shows the client name; offline ones have ` (offline)` appended. Multi‑select; OR semantics within this filter.
- **Outcome** — fieldset of checkboxes, one per outcome value:
  - `success`
  - `rolled_back_verify_failed`
  - `rolled_back_test_failed`
  - `failed_preflight`
  - `failed_backup`
  - `failed_no_recovery`
  - `error`
  - `interrupted`
- **Source** — fieldset with:
  - Source‑kind dropdown: `(any)` | `firmware` | `backup`.
  - If `firmware` is selected, a second dropdown appears listing every firmware record by name; lets the user narrow to "all flashes of THIS firmware".
- **Date range** — fieldset with two date inputs: **Since** and **Until** (whole‑day granularity; the server translates them to `T00:00:00Z` / `T23:59:59Z`).
- **"Clear all"** button — resets every filter.

### 6.2 Results table

Columns (in order): **Started · Client · Port · Source · Outcome · Duration · Note**.

- **Started** — ISO timestamp.
- **Client** — lab machine name.
- **Port** — e.g. `/dev/ttyUSB0`.
- **Source** — `<kind>: <firmware/backup name>`, e.g. `firmware: motor-controller-v1.4` or `backup: lab-rpi-1-ttyUSB0-...`.
- **Outcome** — outcome string, or `running` if still in progress.
- **Duration** — seconds with one decimal, e.g. `18.3s`. Empty if still running.
- **Note** — operator note, truncated at 60 characters and shown muted.

Clicking anywhere on a row opens the Log detail drawer (§7.4).

At the bottom: a **"Load more"** button — visible when there's another page; appends the next 50 rows.

Example row:
```
2026-05-14T09:13:22Z   lab-rpi-1   /dev/ttyUSB0   firmware: motor-controller-v1.4   success   18.3s   Re-flash after assembly fixture rework
```

---

## 7. Modals & overlays (reused across tabs)

### 7.1 Firmware upload modal

Triggered from: **Firmware tab → "Upload firmware"** AND **Flash tab → source picker → "+ Create new firmware"**.

Form fields:

- **Name** — required. If the user picks a file before typing a name, it auto‑fills with the filename stripped of `.hex`.
- **Description** — multi‑line textarea, optional.
- **Firmware (.hex)** — native file picker, accepts `.hex`. After picking, shows `<N> chars loaded.` as confirmation.
- **Test command (hex, optional)** — single text input.
- **Expected response (hex, optional)** — single text input.
- **Tags** — fieldset of checkboxes, one per existing tag.
- Bottom actions: **Upload** (disabled until both a file is loaded and the name is non‑empty) and **Cancel**.
- Errors from the server (e.g. duplicate sha256) shown verbatim above the actions.

Behaviour: on success, closes the modal and selects the newly created firmware in the underlying list.

### 7.2 Tag manager modal

Triggered from: **Firmware tab → "Manage tags"**.

- Header: "Tags" with a **Close** button.
- **Create row**: text input (`new tag name`) + **Create** button (disabled while empty).
- **Tag list**, one row per tag:
  - Tag name
  - Usage count (number of firmware records currently tagged)
  - **Rename** button — switches that row into edit mode (input + Save/Cancel).
  - **Delete** button — opens confirm *"Delete tag "name"? This removes it from all firmware records."*.
- Error area below the header.

Example row (read mode):
```
production                   12      [Rename]  [Delete]
```

### 7.3 Promote backup modal

Triggered from: **Backups tab → row → "Promote"**.

Form fields (pre‑filled from the backup):

- **Name** — defaults to the backup's name; required.
- **Description** — defaults to the backup's description.
- **Copy test pair** — checkbox, defaults on. If checked, the new firmware record inherits the backup's `test_command` / `expected_response`.
- **Tags** — fieldset of checkboxes, all existing tags.
- Bottom actions: **Create firmware** and **Cancel**.
- Errors shown verbatim above the actions.

On success: closes the modal. The new firmware record now exists in the firmware list; it has `source_backup_id` pointing back to the originating backup.

### 7.4 Log detail drawer

Triggered from: **Logs tab table**, **Firmware detail flash history**, and **Backup detail "used by flashes"** list.

A side drawer (overlay; does NOT replace the underlying view). Contents:

- **Header**: `Flash <first 8 chars of id>` + **Close** button.
- **Meta grid (definition list)**:
  - Started (timestamp)
  - Status (e.g. `done (success)`, `done (rolled_back_verify_failed)`, `error`, `interrupted`)
  - Client / port (`lab-rpi-1 · /dev/ttyUSB0`)
  - Firmware (`<name> (sha <first 12>)`)
  - Source kind (`firmware` or `backup`)
- **Stage strip** — a horizontal row of chips, one per stage, in this fixed order:
  1. `preflight`
  2. `backup`
  3. `erase`
  4. `program`
  5. `verify`
  6. `test`
  7. `rollback`
  Each chip has one of four states (visually distinct; up to designer):
  - **ok** — stage completed successfully
  - **failed** — stage failed
  - **skipped** — stage was deliberately skipped (e.g. `backup` when "Skip backup" was on, or `test` when post‑flash test was off)
  - **n/a** — stage didn't run (e.g. `rollback` when nothing failed)
  Hovering a chip should reveal a tooltip with `<status> · <duration ms> · <error message if any>`.
- **Hex diff** (only when there's a `test_result`, typically because the post‑flash test failed):
  - Two rows: **Expected** and **Received**, both shown as space‑separated hex bytes.
  - Bytes that differ between the two are visually marked (mismatch class).
  - Footer line: either `Byte-for-byte match.` or `<N> byte(s) differ.`
- **Raw JSON** — collapsible `<details>` with the full result payload pretty‑printed. Power users live here.
- **Operator note** form:
  - Multi‑line textarea pre‑filled with the existing note (free text — e.g. "Re-flash after assembly fixture rework", "intermittent USB drop, retry").
  - **Save note** button.
- **"Repeat this flash"** section (replay):
  - **Client** dropdown — defaults to the original client; same offline‑disabling rule as the flash form.
  - **Port** text input — defaults to the original port name; editable because the device may now be on a different port.
  - **Repeat** button — kicks off a new flash with the SAME source (firmware or backup) and the SAME test pair. On success, closes the drawer; user can switch to the Flash tab to watch progress. If the original source has been deleted in the meantime, an alert says *"Source firmware/backup has been deleted — cannot replay."*

Example stage strip read‑out for a successful flash with backup and test enabled:
```
[preflight ok]  [backup ok]  [erase ok]  [program ok]  [verify ok]  [test ok]  [rollback n/a]
```

Example for a flash that failed the post‑flash test and was rolled back:
```
[preflight ok]  [backup ok]  [erase ok]  [program ok]  [verify ok]  [test failed]  [rollback ok]
```

Example hex diff:
```
Expected   55 AA 81 00 FF FF
Received   55 AA 81 00 00 FF
                          ↑↑
4 byte(s) differ.   (illustrative — exact mismatch counter is bytewise)
```

---

## 8. Reusable sub‑components

### 8.1 Stats card

Shown on firmware detail and backup detail.

Definition list with six fields:
- **Total flashes** — integer.
- **Successes** — integer.
- **Rolled back** — integer (count of `rolled_back_*` outcomes).
- **Failures** — integer (count of `failed_*` and `error` and `interrupted`).
- **Success rate** — percent (`successes / total * 100`, rounded), or `—` if zero flashes.
- **Last flashed** — either `—` or `<timestamp> · <client> · <port>`.

Example:
```
Total flashes     27
Successes         24
Rolled back        2
Failures           1
Success rate      89%
Last flashed      2026-05-14T09:13:22Z · lab-rpi-1 · /dev/ttyUSB0
```

### 8.2 Tag chip

A small pill displaying a tag name. Three modes:
- **Plain** (just shows the tag name).
- **Selected** (when used as a filter; clicking toggles).
- **Removable** (with an inline `×` button) — used inside forms where you can detach a tag.

### 8.3 Hex input

The reusable text field used in the Test pair editor and (less prominently) elsewhere. Displays bytes space‑separated; lets the user type pretty much anything (lower/upper case, with or without spaces) and normalizes on the fly. Below the input:
- Byte count
- Invalid‑hex error (if applicable)
- ASCII preview (printable bytes shown as their ASCII character; unprintable as `.`).

---

## 9. End‑to‑end user flows

These are the canonical scenarios. The redesign should make all of them feel obvious.

### Flow A — First flash of a brand new firmware

1. Operator opens the app → lands on **Flash** tab.
2. Picks lab machine from the dropdown → port table appears.
3. Picks a port (the one their device is plugged into).
4. In the source picker, clicks **"+ Create new firmware"** → fills the upload modal (file, name, optional test pair, tags) → submits.
5. The new firmware is auto‑selected as the source.
6. Reviews / edits the test pair if needed.
7. Leaves "Skip backup" off (default).
8. Clicks **"Disconnect devices and flash"**.
9. Watches the Running view; when it terminates, reads the Result view.

### Flow B — Re‑flash the firmware that's already known

1. Operator opens **Flash** tab.
2. Picks lab machine, picks port.
3. In the source picker, types part of the firmware name into the search box, or filters by tag (e.g. clicks the `production` chip), then picks the row.
4. Hits **"Disconnect devices and flash"**.

### Flow C — Restore a previous backup onto a device

1. Operator opens **Flash** tab.
2. Picks lab machine, picks port.
3. In the source picker switches the segmented control to **Backups**, finds the backup (often by client filter), picks it.
4. Hits **Flash**.

### Flow D — Promote a backup into a firmware record

1. Operator opens **Backups** tab.
2. Finds the backup of interest (search / client filter).
3. Clicks **Promote** on the row → fills the modal (name, description, copy test pair, tags) → **Create firmware**.
4. Switches to **Firmware** tab; the new record is in the list.

### Flow E — Investigate a failed flash and retry

1. Operator opens **Logs** tab.
2. Filters by outcome `rolled_back_verify_failed` (or whatever they're investigating).
3. Clicks the row → Log detail drawer opens.
4. Reads the stage strip (which stage failed?), the hex diff (what was wrong with the test result?), the raw JSON.
5. Adds an operator note (e.g. "USB cable was flaky"). Clicks **Save note**.
6. Verifies the same client is online, leaves port as‑is (or changes it), clicks **Repeat**.
7. Switches to **Flash** tab to watch the rerun.

### Flow F — Curate the firmware library

1. Operator opens **Firmware** tab.
2. Clicks **Manage tags** → creates `v3-beta`, renames `experimental` → `v2-experimental`. Closes the modal.
3. Selects a firmware row; in the right pane edits its description, attaches the new tag, hits **Save**.
4. Optionally deletes an old, never‑flashed firmware via the row's Delete button.

### Flow G — Detect another flash is already running

1. Operator opens the app.
2. The Flash tab loads but the form area is empty and the **Running view** is shown on the right — meaning someone else (or another tab) is currently flashing.
3. The page polls every 1.5 s; when the flash terminates, the Running view is replaced by the Result view, and the form becomes usable again.

---

## 10. States checklist (designer reference)

For every list/detail/form please consider these states explicitly:

- **Empty** (no firmware yet, no backups yet, no logs match the filter).
- **Loading** (first paint and after refresh).
- **Error** (server unreachable, validation rejection, "device already in flashing state").
- **Disabled** (offline lab machine in dropdown; Flash button before form is complete; "Delete selected" with zero ticked).
- **Selected / active** (a row in any list, a tab, a segmented control, a tag chip filter).
- **In‑progress** (Running view; submit button after click; Save note button while saving).
- **Confirmation dialogs** for destructive actions (delete firmware, delete tag, delete backup, bulk delete backups).
- **Hover affordances** (rows are clickable; tags toggle filters; stage chips reveal tooltips).
- **Mobile / narrow viewport** is NOT a requirement — operators use this on a lab desktop, so a comfortable minimum width of ~1280 px is acceptable.

---

## 11. Glossary

- **Lab machine / client** — a Raspberry Pi (or similar small computer) physically located in the lab, with USB devices plugged into it. The server talks to it remotely.
- **Port** — a serial device file on a lab machine, e.g. `/dev/ttyUSB0`.
- **Firmware record** — a stored `.hex` file plus metadata (name, description, tags, default test pair).
- **Backup record** — a snapshot of whatever was on a device at the moment some flash captured it. Includes device metadata (VID:PID, serial, product).
- **Flash** — both the verb (the act of programming a device) and the noun (one row in the flashes table representing one such attempt and its result).
- **Stage** — one of preflight / backup / erase / program / verify / test / rollback inside a flash.
- **Outcome** — the final classification of a finished flash (success, rolled_back_*, failed_*, error, interrupted).
- **Test pair** — the `test_command` + `expected_response` pair sent over serial after programming, to assert the device is healthy.
- **Tag** — a free‑form label attached to firmware records. Used for filtering. Tags do not apply to backups.
- **Promote** — turn a backup record into a firmware record so it can be flashed onto other devices and tagged like a normal firmware.
- **Replay / repeat** — re‑run a previous flash, possibly on a different device/port, using the SAME source.

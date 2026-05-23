# The SerialHop panel

The SerialHop panel is the desktop window you open from the **SerialHop** shortcut on the desktop (or the Start Menu entry). It's the one and only operator surface for everything SerialHop does on this PC: managing the Windows service, editing config, watching devices and ports, and reading logs. The Windows service runs whether or not the panel is open — closing the window doesn't stop the service.

This page tours the five tabs. Each section says **what's on it**, **when you'd open it**, and **the actions it offers**.

## Status tab — health at a glance, service controls

Open it: any time you want to know whether the lab is healthy, or right after a config change to confirm everything came back up.

What's on it:

- **Three lamps** that summarize the state of each layer:
  - **Local service** — is the Windows service running? Red here means SerialHop isn't up locally; check the **Logs** tab for the reason (usually a YAML validation error).
  - **Lab-bridge server** — can SerialHop reach the configured host, and does its health probe respond? Red here means the host is unreachable from this PC's network, or the host in the Config tab is wrong.
  - **Reverse tunnel** — is the chisel reverse tunnel up against the lab-bridge server? **This is the source of truth for "is the lab connected".** Green here means researchers can reach this lab; anything else and you're offline regardless of what the lab-bridge home page says.
- **Service control buttons** — **Install**, **Uninstall**, and **Restart**. All require admin (UAC). Install is what you click after entering credentials on a fresh PC; Restart is what you click when something looks stuck.
- **Rediscover** — re-scan serial ports without restarting the service. Use this after plugging in a new device.
- **Keep-awake toggle** — prevents Windows from sleeping or shutting down while SerialHop is running. Useful for shared lab PCs that researchers expect to be reachable around the clock. The state is visible in `powercfg /requests` if you want to verify.
- **Update row** — appears when a newer SerialHop release is available. Clicking through handles the download, SHA-256 verification, install, and automatic rollback if the new version fails to come up. See **Config → auto_update** to disable this if you want to pin a version.
- **Crash report** — shows up if the panel itself crashed on a previous run, so you can ship the trace to the SerialHop maintainers.

## Config tab — typed editor for `SerialHop_config.yaml`

Open it: to set or change anything SerialHop reads at startup — credentials, discovery filters, log level, raw-serial or flashing flags.

What's on it:

- Fields grouped by section (**lab-bridge**, **REST**, **discovery**, **log**, **raw serial**, **auto-update**, **firmware flashing**), each with inline help describing what the field does and what values are valid. **This inline help is the authoritative per-field reference** — the [config reference page](/docs/operator/config) on this site is a copy that may lag the running version.
- Per-field validation. Bad values are flagged inline; you can't save until they're fixed. Lab-bridge credentials are additionally validated against the server at save time — wrong username/password are rejected before being written to disk.
- A dirty-state guard when switching tabs: if you have unsaved edits, a modal lists exactly which fields are dirty so you don't lose work by accident.
- **Save & restart** — the default action. Writes the YAML and restarts the service so the new values take effect. (SerialHop only reads config at startup, so the restart is mandatory.)
- **Open config file** — reveals `%ProgramData%\SerialHop\SerialHop_config.yaml` in Windows Explorer, in case you need to look at the raw file or copy it elsewhere.

For the full field list and common-task recipes, see the [config reference](/docs/operator/config).

## Devices tab — what SerialHop has positively identified

Open it: to confirm that a specific instrument is recognized, or to send a single raw command to a discovered device for diagnosis.

What's on it:

- One row per device SerialHop discovered: **type** (`pump` / `valve` / `densitometer` / …), **type code**, and the **COM port** it's bound to.
- A **raw command** box per row for submitting a single byte sequence to that device. Handy for confirming a board is responsive without running a full notebook workflow.
- A **Disconnect** button per row to release a single port without restarting the service. Useful when an instrument is misbehaving and you want to free it before re-scanning.

If an instrument you expect to see isn't in this list, the device wasn't classified. Common causes: it's plugged in but on an excluded port (check **Config → discovery → Exclude**), it needs more time to settle after open (raise **post_open_settle_ms**), or it's a board SerialHop doesn't know how to identify (check the **Ports** tab to confirm it enumerated at the USB layer at all).

## Ports tab — raw view of every enumerated COM port

Open it: to debug discovery — confirm a board enumerated at all, find its USB metadata, or send raw bytes when discovery can't classify it.

What's on it:

- One row per COM port Windows enumerated, with USB descriptors: **VID**, **PID**, **SerialNumber**, **Product**.
- A filter box to narrow the list when the PC has lots of ports.
- A **raw byte transmission** box per row (only active when **Config → raw serial → Enabled** is on). Lets you talk to a port whether or not SerialHop classified it as a known device — useful for poking an unrecognised board to see if it responds at all, or for instruments that SerialHop doesn't yet support.

The **Devices** tab is a filtered, classified view over a subset of what the **Ports** tab shows. If a port shows up in **Ports** but never in **Devices**, classification is failing — start there.

## Logs tab — structured log tail with filtering

Open it: any time something is wrong. This is where SerialHop tells you why a save failed, why a port didn't classify, why the tunnel won't come up. **It's the first stop for any troubleshooting** — the Status-tab lamps tell you what's wrong, the Logs tab tells you why.

What's on it:

- Newest-first tail of the structured logs SerialHop writes to `%ProgramData%\SerialHop\logs\`.
- A sticky filter bar at the top: filter by **level** (debug / info / warn / error) and by **free-text** match across the message.
- Inline detail view for each entry — click a row to expand its structured fields (port, device type, request bytes, response bytes, etc.) without leaving the tab.
- **Open logs folder** — reveals the log directory in Windows Explorer, in case you need to copy a file off the PC to share with the SerialHop maintainers.

Raise the verbosity on this tab by setting **Config → log → Level** to `debug` (Save & restart). That surfaces probe-by-probe details, request/response byte arrays, and other low-level events. Set it back to `info` when you're done — `debug` is noisy.

## Cross-reference: which tab for which symptom

| Symptom | Open first | Then |
|---|---|---|
| Researcher reports lab is offline | **Status** — check Reverse-tunnel lamp | If red, **Logs** for the reason |
| Just edited config, want to confirm it stuck | **Status** — all three lamps green? | If Local-service red, **Logs** for validation error |
| New instrument plugged in but not appearing | **Status** — click **Rediscover** | If still missing, **Devices** then **Ports** to see how far it got |
| Instrument acting wrong | **Devices** — try a raw command on the row | If unresponsive, **Logs** with `level: debug` to see request/response bytes |
| Adding a brand-new board SerialHop doesn't yet support | **Ports** — confirm it enumerated, find its VID/PID | Enable **raw serial** in Config to send commands directly |
| Update prompt showed up | **Status** — Update row | Read the release notes, then accept (auto-rollback covers a bad install) |

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

## Devices tab — ports SerialHop is considering, with discovery results

Open it: after plugging in a new instrument, or to confirm that a specific instrument was recognized.

What's on it:

- The list of COM ports SerialHop is considering — the system's available ports filtered by **Config → discovery → Include / Exclude**. For ports SerialHop classified, the row also shows the device **type** (`pump` / `valve` / `densitometer` / …) and **type code**; unclassified ports appear here too but without a device tag.
- **Rediscover** — re-scan all considered ports without restarting the service. This is what you click after plugging in a new instrument.

If an instrument you expect to see isn't in this list at all, it's being filtered out at the OS layer or by your include/exclude rules — check the **Ports** tab to confirm Windows enumerated it, and check **Config → discovery** for include/exclude entries. If the port appears here but without a device type, classification failed: it probably needs more time to settle after open (raise **discovery → post_open_settle_ms** in Config), or it's a board SerialHop doesn't know how to identify.

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
- A sticky filter bar at the top with three dimensions:
  - **Stream** — which log stream to show: **service log** (the structured slog stream from the Windows service — your default), **stderr** (chisel output and any panic traces), or **panel errors** (errors from the desktop panel itself, separate from the service). When something looks wrong, glance at all three: a service issue won't show in the panel-errors stream, and vice versa.
  - **Level** — debug / info / warn / error. Applies to the service-log stream.
  - **Free text** — substring match across the message.
- Inline detail view for each entry — click a row to expand its structured fields (port, device type, request bytes, response bytes, etc.) without leaving the tab.
- **Open logs folder** — reveals the log directory in Windows Explorer, in case you need to copy a file off the PC to share with the SerialHop maintainers.

Raise the verbosity on this tab by setting **Config → log → Level** to `debug` (Save & restart). That surfaces probe-by-probe details, request/response byte arrays, and other low-level events. Set it back to `info` when you're done — `debug` is noisy.

## Cross-reference: which tab for which symptom

| Symptom | Open first | Then |
|---|---|---|
| Researcher reports lab is offline | **Status** — check Reverse-tunnel lamp | If red, **Logs** for the reason |
| Just edited config, want to confirm it stuck | **Status** — all three lamps green? | If Local-service red, **Logs** for validation error |
| New instrument plugged in but not appearing | **Devices** — click **Rediscover** | If still missing, check the **Ports** tab to see if Windows enumerated it at all |
| Instrument acting wrong | **Logs** — set **Config → log → Level** to `debug`, Save & restart, then watch request/response bytes here | Once diagnosed, return level to `info` |
| Adding a brand-new board SerialHop doesn't yet support | **Ports** — confirm it enumerated, find its VID/PID | Enable **raw serial** in Config to send commands directly from this tab |
| Update prompt showed up | **Status** — Update row | Read the release notes, then accept (auto-rollback covers a bad install) |

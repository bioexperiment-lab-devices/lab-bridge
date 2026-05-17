# Flasher — Web UI design

Single-file HTML design mockup for the Flasher tool (a SerialHop module
for pushing compiled firmware to USB-connected microcontrollers).

## What's inside

- `Flasher.html` — the entire design. Open it in a browser to see all
  artboards laid out on a pan/zoom canvas:
  - Flash tab (5 states: pick source, ready, source-picker on backups,
    running, success, verify-failed + rollback)
  - Firmware tab (list + detail, upload modal)
  - Backups tab (list + detail, promote modal)
  - Logs tab (table + filters, detail drawer)

The file contains all CSS in a `<style>` block and all React/JSX in
`<script type="text/babel">` blocks. React 18, Babel standalone, and the
IBM Plex font are pulled from public CDNs — no build step.

## Structure (script blocks, in order)

1. **DesignCanvas** — pan/zoom artboard wrapper (`<DesignCanvas>`,
   `<DCSection>`, `<DCArtboard>`).
2. **Tweaks panel** — floating panel for live theme/accent tweaks
   (`<TweaksPanel>`, `useTweaks`).
3. **Browser shell + primitives** — `FlBrowser`, `FlTopbar`, `FlPage`,
   `FlButton`, `FlSeg`, `FlSwitch`, `FlTag`, `FlOutcome`, `FlStageStrip`,
   `FlHexInput`, `FlHexDiff`, `FlStatsCard`, `FlJSON`, and the three
   reusable form controls: `FlDropdown`, `FlDateInput`, `FlBadgeMulti`.
4. **Flash tab** — `FlashForm` + `FlashOutput_Empty` / `_Running` /
   `_Success` / `_Failure`.
5. **Firmware + Backups tabs** — `FirmwareTab`, `BackupsTab`,
   `UploadFirmwareModal`, `PromoteBackupModal`.
6. **Logs tab** — `LogsTab`, `FlLogFilters`, `LogDetailDrawer`.
7. **Canvas composition** — sample data, artboard list, and `<App />`
   that mounts everything.

## Design tokens

Defined as CSS variables on `:root` near the top of the file. Light/dark
both supplied via `[data-theme="dark"]`. Accent + theme are user-tweakable
through the Tweaks panel.

## Notes for implementation

- Hex bytes are rendered as readonly `<input>` for now — wire them to
  real validation.
- Custom dropdowns/multi-selects (`FlDropdown`, `FlBadgeMulti`) handle
  outside-click close but don't have keyboard nav yet.
- The autoload row in the Logs table is a static visual indicator;
  hook up an `IntersectionObserver` on `.fl-logs-loader` to actually
  fetch more.

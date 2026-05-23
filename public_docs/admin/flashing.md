# Flashing device firmware

The Flasher service (`/flash/*`, restricted to the `admins` group) is the admin's path to push new firmware to a connected lab device. The firmware library lives on the VPS; firmware uploads come primarily from the device manufacturer's CI via the bearer-token-protected upload API, and the admin's job is to push a specific build to a specific lab on request.

## How firmware lands in Flasher

There are two ingestion paths, and you should strongly prefer the first:

- **Primary path — manufacturer CI uploads.** The device manufacturer's CI POSTs new firmware to Flasher's upload API with a bearer token in the `Authorization` header. The token is set (and rotated) with `task secrets:rotate-flasher-upload-token` and given to the manufacturer's CI as a GitHub or GitLab secret. Every release of the device's firmware repo lands automatically in the lab-bridge library.
- **Secondary path — manual upload through the Flasher UI.** Sign in at `/flash/`, drop the firmware file into the upload form, name it. Reserve this for one-off testing or recovery — anything you upload manually is invisible to the manufacturer's release process, so the next CI upload may surprise you by introducing a name collision or shadowing your test build.

## Pushing firmware to a lab

1. Sign in at `/flash/`. You must be in the `admins` group; researchers cannot reach this UI.
2. Pick the firmware build from the library on the left. The list is sorted newest-first; each entry shows the version and upload time.
3. Pick the target lab from the lab roster on the right. The roster comes from the same `chisel_clients` array as the home page's Registered Labs panel. If the lab isn't in the roster yet, register it first — see [Registering a new lab](/docs/admin/labs).
4. Confirm. Flasher opens the chisel reverse tunnel back to the lab, hands the firmware bytes to SerialHop, and SerialHop programs the device.
5. Verify on the [lab client logs dashboard](/grafana/d/lab-bridge-client-logs/lab-client-logs) filtered by the lab name — the agent reports the new firmware version on its first connect after the flash completes.

## Rotating the upload token

```bash title="laptop"
task secrets:rotate-flasher-upload-token
task deploy
```

`task secrets:rotate-flasher-upload-token` generates a fresh URL-safe token, writes it to `compose/flasher/upload_token`, and prints it once. Update the manufacturer's CI secret (`FLASHER_UPLOAD_TOKEN` or whatever name they use) in lockstep — there is no grace window. As soon as `task deploy` lands the new token, every upload signed with the old token returns 401.

## Failure modes

- **Lab offline at push time.** Flasher reports a connection error to the chisel reverse port. The lab has no active chisel session — the operator likely needs to restart SerialHop on the lab PC. Retry once the lab shows ONLINE on the home page.
- **Device disconnected from the lab PC.** Same surface error as above, but the lab is online — SerialHop just can't find the device's serial port. Plug the device in (or have the operator do it) and retry.
- **Wrong firmware family.** The device's bootloader rejects incompatible firmware with a specific error. Flasher surfaces the device's error reply verbatim — read it, pick the right firmware, retry.

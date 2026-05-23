# Troubleshooting

This page covers what to do when a call doesn't return what you expected. Operator-side issues (SerialHop not running, network) live in [`/docs/operator/`](/docs/operator/).

## `discover()` returned nothing

- Lab is offline. Confirm with `LabDevicesClient.list_active_users()` — if your lab isn't in the list, ping the operator to restart SerialHop.
- Devices aren't physically connected to the lab PC. Operator-side check.
- The discovery cache is stale. Run `client.discover()` once more to force a fresh probe. Note this is destructive — see the [first-notebook walkthrough](/docs/researcher/first-notebook) for what that means.

## Lab appears in `list_registered_users()` but not in `list_active_users()`

The lab is known to the server but its SerialHop hasn't dialed in. Ask the operator to verify SerialHop is running and the chisel session is up; the Grafana dashboard `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>` shows the most recent connection attempt.

## Common exceptions

| Exception | Typical cause |
|---|---|
| `DeviceNotFound` | The device ID isn't in SerialHop's cache. Run `discover()` to refresh. |
| `DeviceBusy` | Another call is in flight against the same device. Wait and retry. |
| `DeviceUnreachable` | The chisel tunnel dropped or the device disconnected. Check the lab's status on `/`. |
| `TransportError` | The HTTP request to SerialHop failed (network, timeout). Retry; if persistent, the lab is likely offline. |
| `DiscoveryInProgress` | Someone else just called `discover()` and it's still running. Wait a few seconds and retry. |

Every exception is a subclass of `LabDevicesError` and carries `status`, `code`, and `detail` fields you can inspect. The full hierarchy is in the [`bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite) repo.

## Where to look next

- Lab status on `/` (home page roster).
- Live log tail at `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>`.
- If you've ruled out lab/network, ping the server admin — the issue may be on the VPS.

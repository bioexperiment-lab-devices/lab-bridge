# Lab operator guide

As a lab operator you install SerialHop on the Windows PC that has the instruments physically connected, give it the lab-bridge credentials your server admin issued, and keep it running. SerialHop runs as a Windows service that survives reboots, so once it's installed and configured, the lab stays connected to the lab-bridge server without further babysitting.

## One-time tasks

- Receive lab-bridge credentials from the server admin (see [registering a new lab](/docs/admin/labs)).
- Install SerialHop following [set up a new lab PC](/docs/operator/setup-lab-pc).
- Verify the lab shows ONLINE on [the home page](/).

## Ongoing tasks

- Keep instruments plugged into the lab PC.
- When you're at the lab PC, open SerialHop from the desktop shortcut and check the **Status** tab — the **Reverse tunnel** lamp is the source of truth for whether the lab is connected. If it's not connected, click **Restart**.
- Remotely, [the lab-bridge home page](/) roster is a convenient glance: your lab shows ONLINE while the tunnel is up. Don't rely on it for diagnosis — use the Status tab on the lab PC for that.
- Watch `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>` if a researcher reports a problem. The same stream is available locally in the panel's **Logs** tab, newest first, with level + free-text filtering.

## Reading order

- [Set up a new lab PC](/docs/operator/setup-lab-pc) — install walkthrough.
- [Panel tour](/docs/operator/panel) — what each tab in the SerialHop window is for, and when to open it.
- [SerialHop config reference](/docs/operator/config) — every setting the panel exposes and the YAML key behind it.

## More about SerialHop

Source, releases, and protocol notes are at [`bioexperiment-lab-devices/serialhop`](https://github.com/bioexperiment-lab-devices/serialhop).

# Lab operator guide

As a lab operator you install SerialHop on the Windows PC that has the instruments physically connected, give it the lab-bridge credentials your server admin issued, and keep it running. SerialHop runs as a Windows service that survives reboots, so once it's installed and configured, the lab stays connected to the VPS without further babysitting.

## One-time tasks

- Receive lab-bridge credentials from the server admin (see [registering a new lab](/docs/admin/labs)).
- Install SerialHop following [set up a new lab PC](/docs/operator/setup-lab-pc).
- Verify the lab shows ONLINE on [the home page](/).

## Ongoing tasks

- Keep instruments plugged into the lab PC.
- Check the lab-bridge home page roster periodically — if your lab shows OFFLINE, open the SerialHop control panel (double-click `SerialHop.exe`) and click **Restart** on the Status tab.
- Watch `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>` if a researcher reports a problem. The same stream is available locally in the panel's Logs tab, newest first, with level + free-text filtering.

## Reading order

- [Set up a new lab PC](/docs/operator/setup-lab-pc) — install walkthrough.
- [SerialHop config reference](/docs/operator/config) — every setting the panel exposes and the YAML key behind it.

## More about SerialHop

Source, releases, and protocol notes are at [`bioexperiment-lab-devices/serialhop`](https://github.com/bioexperiment-lab-devices/serialhop).

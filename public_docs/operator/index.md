# Lab operator guide

As a lab operator you install SerialHop on the Windows PC that has the instruments physically connected, give it the chisel credentials your server admin issued, and keep it running. SerialHop runs as a Windows service that survives reboots, so once it's installed and configured, the lab stays connected to the VPS without further babysitting.

## One-time tasks

- Receive chisel credentials from the server admin (see [registering a new lab](/docs/admin/labs)).
- Install SerialHop following [set up a new lab PC](/docs/operator/setup-lab-pc).
- Verify the lab shows ONLINE on [the home page](/).

## Ongoing tasks

- Keep instruments plugged into the lab PC.
- Check the lab-bridge home page roster periodically — if your lab shows OFFLINE, restart SerialHop from its control panel.
- Watch `/grafana/d/lab-bridge-client-logs/lab-client-logs?var-client=<your-lab>` if a researcher reports a problem.

## Reading order

- [Set up a new lab PC](/docs/operator/setup-lab-pc) — install walkthrough.
- [`SerialHop_config.yaml` reference](/docs/operator/config) — every key you might touch.

## More about SerialHop

Source, releases, and protocol notes are at [`bioexperiment-lab-devices/serialhop`](https://github.com/bioexperiment-lab-devices/serialhop).

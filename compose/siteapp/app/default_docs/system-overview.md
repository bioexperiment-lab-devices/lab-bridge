# System Overview

## Purpose

The system gives lab researchers remote access to bench instruments (pumps, valves, densitometers) that physically live on a Windows PC inside the lab network. Previously, these instruments could only be controlled from a Python script running on that same lab PC over a serial cable — experiments had to be authored and executed on-site. The system removes this constraint: a researcher can now write and run experiment notebooks from anywhere with a browser, against the real hardware.

The architecture has three components:

- **[`lab-bridge`](https://github.com/bioexperiment-lab-devices/lab-bridge)** — a public web server that hosts the shared notebook environment.
- **[`serialhop`](https://github.com/bioexperiment-lab-devices/serialhop)** — a small program installed on the lab PC that exposes the instruments to the outside world.
- **[`bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite)** — the Python library used inside notebooks to drive experiments. It is currently being migrated from controlling instruments locally over a serial cable to controlling them remotely over the network. The migration plan is documented in the [HTTP client design spec](https://github.com/khamitovdr/bio_tools/blob/main/docs/superpowers/specs/2026-04-27-lab-devices-http-client-design.md).

The system is currently deployed and running:

- **JupyterLab** (researcher workspace): [https://111.88.145.138/lab](https://111.88.145.138/lab)
- **Grafana** (lab agent logs and health dashboard): [https://111.88.145.138/grafana/](https://111.88.145.138/grafana/)

## How the components fit together

A researcher opens the notebook environment in a browser, writes Python code using `bioexperiment_suite`, and that code transparently talks to the instruments back in the lab. The lab PC itself initiates an outbound connection to the public server, so the lab network does not need to expose any inbound ports or set up port-forwarding — a typical blocker in institutional networks.

## 1. [`lab-bridge`](https://github.com/bioexperiment-lab-devices/lab-bridge) — the public server

`lab-bridge` is the team's shared workspace, running on a rented VPS (virtual server) reachable at a public URL ([JupyterLab](https://111.88.145.138/lab) · [Grafana](https://111.88.145.138/grafana/)). It is deployed as a single Docker Compose stack containing:

- **JupyterLab** — the notebook environment researchers log into, protected by a shared team password.
- **Caddy** — the web server in front of JupyterLab, handling HTTPS automatically.
- **chisel** — a tunneling service that lets each lab PC dial in and publish its instruments into the notebook environment.
- **Loki + Grafana** — an observability stack that collects logs from each lab agent and shows them in a pre-built dashboard (live tail, error counts, software version per lab machine).

Setting up a new VPS or registering a new lab machine is automated through a small set of operator commands (`task secrets:add-client`, `task provision`, `task deploy`).

## 2. [`serialhop`](https://github.com/bioexperiment-lab-devices/serialhop) — the lab agent

`serialhop` is a small program installed on the Windows PC that has the instruments physically connected to it. It is distributed as a single `.exe` file. Once installed, it runs as a Windows service — starting automatically at boot and surviving reboots and logouts. The operator interacts with it through a small native control panel (Install / Uninstall / Restart / Open config / Open log).

When running, it does three things:

1. **Discovers the instruments.** It scans the PC's serial ports, identifies which ones are pumps, valves, or densitometers, and keeps a cached list.
2. **Exposes them over a small REST API.** Three endpoints — list devices, re-discover, send a command to a specific device. The agent itself does not interpret the commands; it just shuttles bytes between the network and the serial port. The actual command vocabulary lives on the client side.
3. **Opens a secure tunnel to the public server.** Using chisel, it dials out to `lab-bridge` and asks for its REST API to be published back into the notebook environment. From the notebooks' point of view, the lab PC's API is now reachable as if it were a local service. The same tunnel also carries the agent's own logs into the central observability stack.

## 3. [`bioexperiment_suite`](https://github.com/khamitovdr/bioexperiment_suite) — the Python experiment library

This is the package researchers actually import in their notebooks. It provides high-level objects — `Pump`, `Densitometer`, `Valve` — and a higher-level `experiment/` module for composing whole protocols.

Until recently, the library talked directly to the serial port, which forced researchers to run notebooks on the lab PC itself. The current migration replaces this transport with an HTTP client (`LabDevicesClient`) that talks to `serialhop` over the tunnel. The high-level `experiment/` API is intentionally untouched — only the layer underneath changes — so existing experiment code keeps working with minimal adjustments.

Notebook code after the migration looks like:

```python
client = LabDevicesClient(port=9001)
devices = client.discover()
for pump in devices.pumps:
    pump.pour_in_volume(5.0)
density = devices.densitometers[0].measure_optical_density()
```

## End-to-end flow

1. The lab PC boots. `serialhop` starts as a Windows service, scans for instruments, and opens the tunnel to `lab-bridge`.
2. A researcher — anywhere with internet — opens the public URL, logs into JupyterLab with the shared team password, and runs a notebook.
3. The notebook creates a `LabDevicesClient`. Calling `.discover()` sends an HTTP request through the tunnel to `serialhop`, which returns the list of attached instruments.
4. Subsequent commands — set flow rate, pour a volume, read optical density — flow the same way: a Python method call becomes an HTTP request that becomes a serial command on the lab PC, with the response travelling back along the same path.
5. Throughout, `serialhop` streams its logs to the central server, where an operator can watch them live in Grafana.

## Technology summary

| Layer | Technology |
|---|---|
| Public server | Docker Compose with Caddy, JupyterLab, Loki, and Grafana, deployed on a VPS |
| Tunneling | chisel (lab PC dials out — no inbound ports needed) |
| Lab agent | Go, distributed as a single Windows `.exe` running as a service |
| Experiment library | Python (`httpx` for HTTP, `loguru` for logging) |
| Device protocol | Custom serial byte commands, defined per device type |

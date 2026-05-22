# Grafana dashboards

The lab-bridge stack ships five pre-provisioned dashboards under `compose/grafana/provisioning/dashboards/`. They cover lab-side logs, host VPS health, container health, and Caddy traffic. Sign in via `/grafana/` — Authelia gates the route, then Grafana completes an OIDC handshake against Authelia and maps your group to a Grafana role.

## Dashboards in this install

### Lab client logs (live tail)

File: `client-logs.json`.

Real-time view of every lab agent's log stream, sourced from Loki via the chisel forward tunnel. Filterable by client name, stream (stdout/stderr), and SerialHop version. Shows live log volume per client, error counts, and the currently running version of each connected agent.

Use it when:

- A specific lab reports a problem and you want to see what the agent is actually saying right now.
- You want to confirm which labs are actively connected (the panel only shows clients with recent logs).
- You're verifying that a SerialHop release reached every lab — the version banner is the first thing each agent logs on connect.

### Platform CPU

File: `platform.json`.

VPS host CPU broken out per container plus an aggregate. Sourced from cAdvisor and node-exporter via Prometheus.

Use it when:

- The stack feels slow and you want to know which container is hot.
- You're sizing up the VPS instance and want a recent baseline for "normal" CPU.

### cAdvisor (containers)

File: `cadvisor.json`.

Per-container resource usage from the upstream cAdvisor dashboard — CPU, memory pressure, file system, network IO. Historical, so you can scrub back in time.

Use it when:

- You suspect a specific service is misbehaving and want to see its memory or IO trend over the last day or week.
- You're investigating an OOM or a noisy disk.

### Node Exporter Full (VPS host)

File: `node-exporter-full.json`.

The canonical Node Exporter Full dashboard, with no lab-bridge-specific customisation. CPU, memory, disk, network, pressure stalls, file descriptor usage — every VPS-host metric Prometheus scrapes from node-exporter.

Use it when:

- You're doing a VPS-level resource investigation (disk filling up, IO saturating, swap thrashing).
- You're planning capacity changes (bigger droplet, more disk).

### Caddy

File: `caddy.json`.

Edge traffic at Caddy — request volume, status codes broken out per route, and TLS certificate health.

Use it when:

- You're investigating a 4xx or 5xx spike and want to see which route is responsible.
- You just landed a routing change and want a quick sanity check that traffic is going where you expect.
- You suspect cert renewal is misbehaving.

## Adding a new dashboard

1. Build the dashboard in the Grafana UI on the running VPS, signed in as an `admins` user.
2. Open **Settings → JSON Model** in the dashboard editor and copy the JSON to your clipboard.
3. Save it as a new file on your laptop at `compose/grafana/provisioning/dashboards/<name>.json`.
4. Commit the file — provisioned dashboards are tracked in git.
5. `task deploy` (or land the change through CI). Grafana reloads provisioned dashboards on restart.

The dashboard provider config at `compose/grafana/provisioning/dashboards/lab-bridge.yaml` picks up every `*.json` in the directory, so you do not need to register the new file anywhere else.

## OIDC role mapping

Authelia issues a `groups` claim on every login. Grafana's OIDC config maps `admins → Admin` and `researchers → Viewer`. A user with neither group never reaches Grafana in the first place — Caddy's `forward_auth` check rejects them before the OIDC handshake starts. The handshake is the only reason Grafana even talks to Authelia directly; the rest of the stack relies entirely on the `forward_auth` decision and the headers Caddy attaches. For the full sequence, see [authentication and authorization](/docs/architecture/auth).

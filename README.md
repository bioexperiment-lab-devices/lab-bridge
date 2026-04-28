# lab-bridge

Self-hosted JupyterLab for small lab teams, with chisel reverse tunnels
bringing NAT'd instruments onto the notebook network. VPS provisioning +
Docker Compose stack.

Design docs:
- `docs/superpowers/specs/2026-04-26-vps-provisioning-design.md` — base stack
- `docs/superpowers/specs/2026-04-28-chisel-client-logs-design.md` — internal
  Loki/Grafana for client log forwarding

## What runs on the VPS

One Docker Compose stack on `labnet`:

- **caddy** — public entrypoint on 80/443, TLS via Let's Encrypt, proxies
  `/grafana/*` to grafana and everything else to jupyter.
- **jupyter** — JupyterLab; cookie-based shared-password auth (not edge
  basic_auth, which breaks WebSocket kernels on mobile).
- **chisel** — public on `chisel.listen_port`; reverse tunnels for device
  ports + a forward tunnel to `loki:3100` for log push.
- **loki** + **grafana** — internal only; Loki has no published port, only
  reachable via Grafana on `labnet` and via chisel-tunneled clients.

## Quick start

```bash
task doctor                                   # check local prerequisites
cp config.example.yaml config.yaml            # then edit with your VPS details
task secrets:set-jupyter-password             # set the shared JupyterLab password
task secrets:set-grafana-password             # set the Grafana admin password
task secrets:add-client -- microscope-1 9001  # add a lab device
task provision                                # first-time VPS setup
task deploy                                   # render configs + bring up stack
```

JupyterLab serves a login page at `https://<vps-ip>/`; everyone on the team
uses the shared password. Auth is handled by JupyterLab itself (cookie-based)
rather than HTTP Basic Auth at the edge — basic_auth re-prompts on every
WebSocket upgrade on mobile browsers, breaking notebook kernels.

## Prerequisites (operator laptop)

- [task](https://taskfile.dev)
- [yq v4](https://github.com/mikefarah/yq) (mikefarah, *not* the Python one)
- `openssl`, `ssh`, `rsync`
- For development: `bats-core`, Docker (for the fake-VPS test container)

## Lab client logs

The server-side stack (Loki + Grafana, the chisel forward tunnel to
`loki:3100`, and the "Lab client logs" Grafana dashboard) is in place and
queryable at `https://<vps-ip>/grafana/` — log in with `admin` / the password
set via `task secrets:set-grafana-password`. The dashboard is provisioned
automatically: live tail, log volume by client, errors, and current versions
per client.

The matching push code lives in `lab_devices_client` (separate repo) and is
not yet shipped. The contract it must implement is in
`docs/superpowers/specs/2026-04-28-chisel-client-logs-client-spec.md`. Until
clients are updated, Loki will be running but empty.

Operations:

- `task ops:logs:loki` / `task ops:logs:grafana` — tail container stderr
- `task ops:loki-disk` — show `loki_data/` size and the configured retention

## Repo layout

- `Taskfile.yml` — operator entrypoints (`task --list` for the full menu)
- `config.example.yaml` — copy to `config.yaml` (gitignored) and fill in
- `compose/` — Docker Compose template, Caddyfile template, Loki config
  template, Grafana provisioning (datasource + dashboard JSON)
- `scripts/` — `provision.sh`, `deploy.sh`, `secrets.sh`, `ops.sh`,
  `doctor.sh`, plus `lib/` helpers and a `fake_vps/` test container
- `tests/` — bats suites; `task test` runs them all

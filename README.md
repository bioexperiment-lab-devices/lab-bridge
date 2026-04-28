# lab-bridge

Self-hosted JupyterLab for small lab teams, with chisel reverse tunnels
bringing NAT'd instruments onto the notebook network. VPS provisioning +
Docker Compose stack.

See `docs/superpowers/specs/2026-04-26-vps-provisioning-design.md` for the
design.

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

Chisel clients push their stdout/stderr through the existing tunnel into an
internal Loki, queryable in Grafana at `https://<vps-ip>/grafana/`. Log in
with `admin` / the password set via `task secrets:set-grafana-password`. The
"Lab client logs" dashboard is provisioned automatically: live tail, log
volume by client, errors, and current versions per client.

Operations:

- `task ops:logs:loki` / `task ops:logs:grafana` — tail container stderr
- `task ops:loki-disk` — show `loki_data/` size and the configured retention

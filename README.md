# lab-bridge

Lab-bridge connects research-lab instruments to a shared JupyterLab environment.
Devices behind NAT in a lab site are exposed to the notebook environment over
chisel reverse tunnels; researchers drive experiments remotely, operators push
firmware and watch logs from a single web portal.

The platform runs as a single Docker Compose stack behind Caddy with Let's
Encrypt TLS. The public surface includes a home page, a public documentation
site, a Windows-agent download, JupyterLab, Grafana, and an admin
firmware-flashing UI.

Example deployment: `https://<vps-host>/`.

## SerialHop

Windows agent that exposes lab-PC serial devices to lab-bridge over a chisel
reverse tunnel. Ships from its own repo:
https://github.com/bioexperiment-lab-devices/serialhop

## Architecture

```
  Lab site                          Internet               VPS
  --------                          --------               ----------------
  [devices] --serial--> [lab PC]    =======>   [caddy] --> [siteapp ]
                         SerialHop  chisel        |        [flasher ]
                          agent     reverse       |        [jupyter ]
                                    tunnel        |        [grafana ] --+
                                                  |                     +- loki
                                                  v                     +- prometheus
                                            Researcher --> /jupyter
                                            Operator   --> /grafana
                                            Admin      --> /flash
```

Services on the `labnet` Docker network:

- **caddy** — TLS edge on 80/443, applies the route table below, and injects a
  shared navbar into every HTML response.
- **siteapp** — FastAPI service serving the home page, public docs (`/docs/`),
  the agent download (`/download/agent`), and the public API (`/api/public/*`).
- **flasher** — Firmware library and flashing UI at `/flash/*`; pushes firmware
  to lab devices over the chisel tunnels.
- **jupyter** — Shared JupyterLab at `/jupyter/`, cookie-authenticated.
- **chisel** — Public chisel server. Reverse tunnels expose device ports to the
  VPS; a forward tunnel pushes lab-agent logs to Loki.
- **grafana**, **loki**, **prometheus**, **node-exporter**, **cadvisor** —
  Observability for lab-agent logs and VPS host/container metrics.

Route map:

| Path | Service | Auth |
|------|---------|------|
| `/` | siteapp | public |
| `/docs/*` | siteapp | public |
| `/download/*` | siteapp | public |
| `/api/agent/upload` | siteapp | bearer token |
| `/api/public/*` | siteapp | public |
| `/jupyter/*` | jupyter | shared password |
| `/grafana/*` | grafana | own login |
| `/flash/*` | flasher | admin basic_auth |
| `/_shared/*` | caddy (navbar) | public |

Each service lives at `services/<name>/` with its own Dockerfile, tests, and CI
workflow. See `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md`
for the isolation model.

## User flow

Three roles operate the platform:

- **Researcher** — drives experiments from JupyterLab using the `bioexperiment`
  Python package; addresses each lab by name and talks to its devices remotely.
- **Lab operator** — runs a specific lab site: installs SerialHop on the lab PC,
  keeps physical devices connected, watches that lab's agent logs in Grafana.
- **Server administrator** — operates the platform: provisions SerialHop
  credentials, pushes firmware via `/flash/*`, monitors system metrics, ships
  releases via CI.

End-to-end loop:

1. Lab staff connect instruments (pumps, valves, densitometers, thermostats, …)
   to a lab PC over serial.
2. SerialHop on the lab PC exposes those ports through a chisel reverse tunnel
   to the VPS.
3. A researcher addresses the lab by name from a JupyterLab notebook and drives
   the experiment.
4. The administrator pushes firmware updates over the same tunnel via Flasher;
   SerialHop itself auto-updates.

One lab = one SerialHop installation = one lab PC = many physical devices.
Client names registered via `task secrets:add-client` are lab-level identifiers;
per-device health lives in Grafana.

## Working with the repo

### Locally

Prerequisites: [`task`](https://taskfile.dev),
[`yq` v4](https://github.com/mikefarah/yq) (mikefarah, not the Python one),
`openssl`, `ssh`, `rsync`. Development additionally needs Docker, `bats-core`,
and `uv`.

Run tests at each layer:

```bash
cd services/siteapp && uv run pytest                 # unit
cd services/siteapp && uv run pytest tests/e2e/      # service e2e
bats tests/integration/test_routes_smoke.bats        # cross-service wiring
```

To add a new service, follow `docs/adding-a-service.md`.

### Via CI

CI is the path to production. Manual deploys exist only for first-time bring-up
and recovery.

1. Open a PR. Conventional Commit title (`feat fix chore docs refactor …`);
   squash-merge only.
2. Per-service workflows (`pr-caddy`, `pr-siteapp`, `pr-flasher`, `pr-platform`)
   gate the merge. `dorny/paths-filter` fast-skips workflows for services the PR
   doesn't touch.
3. After merge, release-please maintains a single platform release PR with the
   next version. Merging it cuts a `vX.Y.Z` tag.
4. The tag triggers `release-please.yml`, which builds the service images to
   GHCR and deploys the stack to the VPS.

See `docs/superpowers/specs/2026-05-12-cicd-design.md` and
`docs/superpowers/specs/2026-05-17-unified-release-design.md` for the full
release model.

## Operations reference

Day-to-day operation is via CI; the commands below cover first-time bring-up
and recovery.

```bash
task doctor                                   # check local prerequisites
cp config.example.yaml config.yaml            # then fill in VPS details
task secrets:set-jupyter-password             # shared JupyterLab password (deprecated)
task secrets:set-grafana-password             # Grafana admin password
task secrets:bootstrap-authelia               # generate Authelia runtime secrets (once per VPS)
task users:add -- admin admins                # add bootstrap admin user
task secrets:rotate-agent-upload-token        # CI upload token for new agent builds
task secrets:rotate-flasher-upload-token      # CI upload token for new firmware
task secrets:add-client -- microscope-1 9001  # register a lab
task provision                                # first-time VPS setup
task deploy                                   # render configs + bring up stack
task ops:logs -- siteapp                      # tail a service's logs
task ops:loki-disk                            # show Loki retention/size
```

`task --list` shows the full menu.

## Users & authentication

See [docs/adding-a-user.md](docs/adding-a-user.md). Users are managed via
`task users:*`; the first one is the bootstrap admin.

## Repo layout

- `services/<name>/` — siteapp, flasher, caddy. Each has its own `Dockerfile`,
  `app/`, `tests/`, `tests/e2e/`, and `build.sh`.
- `compose/` — `docker-compose.yml.tmpl`, `Caddyfile.tmpl`, `pins.yaml` (image
  pins, paths, retention), `grafana/`, `loki/`, `prometheus/`, `shell/` (shared
  navbar assets).
- `scripts/` — `provision.sh`, `deploy.sh`, `secrets.sh`, `ops.sh`, `doctor.sh`,
  plus `lib/` helpers and a `fake_vps/` test container.
- `public_docs/` — Markdown for the public documentation portal; deployed via
  the `deploy-public-docs` workflow on every push to main. Drop a `*.ru.md` next
  to any `*.md` to surface an EN/RU language toggle.
- `tests/integration/` — bats suites for cross-service wiring (`task test`).
- `.github/workflows/` — per-service PR workflows, `release-please.yml`,
  `ghcr-cleanup.yml`, `deploy-public-docs.yml`.
- `docs/superpowers/specs/` — design docs covering the base stack, CI/CD, the
  per-service isolation model, and the unified release flow.

# lab-bridge

Self-hosted JupyterLab for small lab teams, with chisel reverse tunnels
bringing NAT'd instruments onto the notebook network. VPS provisioning +
Docker Compose stack.

Design docs:
- `docs/superpowers/specs/2026-04-26-vps-provisioning-design.md` — base stack
- `docs/superpowers/specs/2026-04-28-chisel-client-logs-design.md` — internal
  Loki/Grafana for client log forwarding
- `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md` —
  public docs portal + Windows agent download

## What runs on the VPS

One Docker Compose stack on `labnet`:

- **caddy** — public entrypoint on 80/443, TLS via Let's Encrypt. Routes
  `/docs/*` and `/download/*` and `/api/agent/upload` to siteapp,
  `/admin/*` to siteapp behind basic_auth, `/grafana/*` to grafana, and
  everything else to jupyter.
- **jupyter** — JupyterLab; cookie-based shared-password auth (not edge
  basic_auth, which breaks WebSocket kernels on mobile).
- **chisel** — public on `chisel.listen_port`; reverse tunnels for device
  ports + a forward tunnel to `loki:3100` for log push.
- **siteapp** — Python (FastAPI) service that serves the public docs portal
  at `/docs/*`, the Windows agent download page at `/download/agent`, and an
  operator-only admin upload UI at `/admin/*` (Caddy basic_auth). CI uploads
  new agent builds via `POST /api/agent/upload` with a static bearer token.
- **loki** + **grafana** — internal only; Loki has no published port, only
  reachable via Grafana on `labnet` and via chisel-tunneled clients.

## Quick start

```bash
task doctor                                   # check local prerequisites
cp config.example.yaml config.yaml            # then edit with your VPS details
task secrets:set-jupyter-password             # set the shared JupyterLab password
task secrets:set-grafana-password             # set the Grafana admin password
task secrets:set-admin-password               # password for the admin upload UI
task secrets:rotate-agent-upload-token        # token CI uses to publish agent builds
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

## Public docs & agent download

Siteapp serves a public docs portal at `/docs/` and a Windows agent
download page at `/download/agent`. Both routes carve out a public surface
in front of JupyterLab without disturbing JupyterLab's cookie auth or
Grafana's login.

- Operator uploads markdown via `/admin/*` (Caddy basic_auth).
- CI publishes a new agent build via `POST /api/agent/upload` with a
  bearer token. Uploads stream to disk; the binary is atomically renamed
  into place so concurrent downloads never see a half-written file.

### Russian translations

Drop a `*.ru.md` next to any `*.md` (e.g. `intro.ru.md`) and an EN/RU
toggle appears on the page. English is always the source of truth — a
`*.ru.md` without a matching `*.md` is ignored. The selected language
persists in a cookie.

### CI example (GitHub Actions)

```yaml
- name: Upload agent build
  run: |
    curl -fsSL -X POST https://${{ secrets.VPS_HOST }}/api/agent/upload \
      -H "Authorization: Bearer ${{ secrets.AGENT_UPLOAD_TOKEN }}" \
      -F "version=${{ github.ref_name }}" \
      -F "binary=@dist/agent.exe"
```

### Operations

- `task ops:logs:siteapp` — tail siteapp container stderr
- `task ops:site-disk` — show `site_data/` size by section
- `task siteapp:build-and-push` — rebuild & publish the siteapp image
  (set `SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:<tag>` first)

## Repo layout

- `Taskfile.yml` — operator entrypoints (`task --list` for the full menu)
- `config.example.yaml` — copy to `config.yaml` (gitignored) and fill in
- `compose/` — Docker Compose template, Caddyfile template, Loki config
  template, Grafana provisioning (datasource + dashboard JSON)
- `compose/siteapp/` — Python source for the siteapp service (Dockerfile,
  pyproject.toml, app/, templates/, static/, tests/), plus `build.sh` for
  GHCR publish
- `scripts/` — `provision.sh`, `deploy.sh`, `secrets.sh`, `ops.sh`,
  `doctor.sh`, plus `lib/` helpers and a `fake_vps/` test container
- `tests/` — bats suites; `task test` runs them all

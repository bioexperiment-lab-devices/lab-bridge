# lab-bridge

Self-hosted lab portal: shared JupyterLab + chisel reverse tunnels that
bring NAT'd lab instruments onto the notebook network, with an operator
admin panel, public docs, and a Windows-agent download page in front.
VPS provisioning + Docker Compose stack.

The public root (`https://<vps-host>/`) lands on a docs welcome page;
JupyterLab moved to `/lab`. Grafana stays at `/grafana/`. See
"What runs on the VPS" for the full route map.

Design docs:
- `docs/superpowers/specs/2026-04-26-vps-provisioning-design.md` — base stack
- `docs/superpowers/specs/2026-04-28-chisel-client-logs-design.md` — internal
  Loki/Grafana for client log forwarding
- `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md` —
  public docs portal + Windows agent download

## What runs on the VPS

One Docker Compose stack on `labnet`:

- **caddy** — public entrypoint on 80/443, TLS via Let's Encrypt. Route map:
  - `/` → 302 redirect to `/docs/` (the welcome page)
  - `/docs/*`, `/download/*`, `/_static/*`, `/api/agent/upload` → siteapp
  - `/admin/*` → siteapp behind basic_auth (single user `admin`)
  - `/grafana/*` → grafana
  - everything else → jupyter (`/lab`, `/login`, `/api/sessions`, …)
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

# Publish the siteapp image to GHCR (or your registry) and pin its tag in
# config.yaml under siteapp.image — see "Publishing the siteapp image" below.

task deploy                                   # render configs + bring up stack
```

After deploy:
- `https://<vps-host>/` — public welcome page (docs portal landing)
- `https://<vps-host>/lab` — JupyterLab; everyone uses the shared password
- `https://<vps-host>/grafana/` — Grafana login (separate password)
- `https://<vps-host>/admin/` — operator admin panel (basic_auth)

Auth is handled by JupyterLab itself (cookie-based) rather than HTTP
Basic Auth at the edge — basic_auth re-prompts on every WebSocket upgrade
on mobile browsers, breaking notebook kernels.

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

### Publishing the siteapp image

The image lives at `ghcr.io/<owner>/lab-bridge-siteapp:<tag>` and is pinned
by tag in `config.yaml` under `siteapp.image`. To publish a new version:

**Recommended — tag-triggered GitHub Actions** (deterministic; uses the
auto-provisioned `GITHUB_TOKEN`, no PAT needed):

```bash
git tag siteapp-v0.2.0
git push origin siteapp-v0.2.0
# wait for the "Publish siteapp image" workflow run to finish
yq -i '.siteapp.image = "ghcr.io/<owner>/lab-bridge-siteapp:0.2.0"' config.yaml
task deploy
```

The package on GHCR is private by default; flip its visibility to public
once (Org → Packages → ⋯ → Package settings → Change visibility) so the
VPS can pull anonymously. Otherwise you'll need to `docker login ghcr.io`
on the VPS with a read-only token.

**Local build & push** (legacy path, requires a PAT with `write:packages`):

```bash
SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:0.2.0 task siteapp:build-and-push
```

## Repo layout

- `Taskfile.yml` — operator entrypoints (`task --list` for the full menu)
- `config.example.yaml` — copy to `config.yaml` (gitignored) and fill in
- `compose/` — Docker Compose template, Caddyfile template, Loki config
  template, Grafana provisioning (datasource + dashboard JSON)
- `compose/siteapp/` — Python source for the siteapp service (Dockerfile,
  pyproject.toml, app/, templates/, static/, tests/), plus `build.sh` for
  GHCR publish
- `.github/workflows/siteapp-publish.yml` — GitHub Actions workflow that
  publishes the siteapp image to GHCR on `siteapp-v*` tag push or manual
  dispatch
- `scripts/` — `provision.sh`, `deploy.sh`, `secrets.sh`, `ops.sh`,
  `doctor.sh`, plus `lib/` helpers and a `fake_vps/` test container
- `tests/` — bats suites; `task test` runs them all (the integration
  suites that build the fake-VPS stack require Docker Hub access — they
  cleanly skip if anonymous-pull is rate-limited on the runner)

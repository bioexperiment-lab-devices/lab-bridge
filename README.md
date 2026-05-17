# lab-bridge

Self-hosted lab portal: shared JupyterLab + chisel reverse tunnels that
bring NAT'd lab instruments onto the notebook network, with an operator
public docs (deployed from git), a Windows-agent download page, and an operator firmware-flashing UI (/flash/*) in front.
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
- `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` —
  the current `services/<name>/` layout, multi-component release-please,
  per-service parallel CI

For adding a new service to the stack, follow `docs/adding-a-service.md`
(checklist mirroring siteapp/flasher). The "Architecture philosophy"
section in `CLAUDE.md` summarises the invariants the repo enforces.

## What runs on the VPS

One Docker Compose stack on `labnet`:

- **caddy** — public entrypoint on 80/443, TLS via Let's Encrypt. Route map:
  - `/` → 302 redirect to `/docs/` (the welcome page)
  - `/docs/*`, `/download/*`, `/_static/*`, `/api/agent/upload` → siteapp
  - `/grafana/*` → grafana
  - everything else → jupyter (`/lab`, `/login`, `/api/sessions`, …)
- **jupyter** — JupyterLab; cookie-based shared-password auth (not edge
  basic_auth, which breaks WebSocket kernels on mobile).
- **chisel** — public on `chisel.listen_port`; reverse tunnels for device
  ports + a forward tunnel to `loki:3100` for log push.
- **siteapp** — Python (FastAPI) service that serves the public docs portal
  at `/docs/*`, the Windows agent download page at `/download/agent`. CI uploads
  new agent builds via `POST /api/agent/upload` with a static bearer token.
  Public docs live in `public_docs/` at the repo root and ship to the VPS via
  the `deploy-public-docs` workflow on every push to main.
- **loki** + **grafana** — internal only; Loki has no published port, only
  reachable via Grafana on `labnet` and via chisel-tunneled clients.

## Quick start

```bash
task doctor                                   # check local prerequisites
cp config.example.yaml config.yaml            # then edit with your VPS details
task secrets:set-jupyter-password             # set the shared JupyterLab password
task secrets:set-grafana-password             # set the Grafana admin password
task secrets:set-admin-password               # bcrypt hash for /flash/* operator gate
task secrets:rotate-agent-upload-token        # token CI uses to publish agent builds
task secrets:add-client -- microscope-1 9001  # add a lab device
task provision                                # first-time VPS setup

# Publish the siteapp image to GHCR (or your registry) — see "Publishing the
# siteapp image" below. The image tag is pinned in services/siteapp/VERSION.

task deploy                                   # render configs + bring up stack
```

After deploy:
- `https://<vps-host>/` — public welcome page (docs portal landing)
- `https://<vps-host>/lab` — JupyterLab; everyone uses the shared password
- `https://<vps-host>/grafana/` — Grafana login (separate password)

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

- Operator commits markdown to `public_docs/` on main; the `deploy-public-docs` workflow rsyncs to the VPS.
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

Two files control the image reference — no `config.yaml` field is involved:

- **`compose/pins.yaml`** → `siteapp_image_repo` — the GHCR repository path
  (e.g. `ghcr.io/<owner>/lab-bridge-siteapp`).
- **`VERSION`** at repo root — the image tag (e.g. `0.6.1`), shared by every
  service. Owned by release-please; do not bump by hand.

`task siteapp:build-and-push` reads both and builds
`${siteapp_image_repo}:${VERSION}` — no environment variables needed.
Manual rebuilds are rare; the normal flow is the release-please workflow
which builds both service images at every release.

See `docs/superpowers/specs/2026-05-17-unified-release-design.md` for the
release model and `docs/superpowers/specs/2026-05-12-cicd-design.md` for
the original CI/CD design.

The package on GHCR is private by default; flip its visibility to public
once (Org → Packages → ⋯ → Package settings → Change visibility) so the
VPS can pull anonymously. Otherwise you'll need to `docker login ghcr.io`
on the VPS with a read-only token.

## Repo layout

- `Taskfile.yml` — operator entrypoints (`task --list` for the full menu)
- `config.example.yaml` — copy to `config.yaml` (gitignored) and fill in
- `compose/` — Docker Compose template, Caddyfile template, Loki config
  template, Grafana provisioning (datasource + dashboard JSON)
- `services/siteapp/` — Python source for the siteapp service (Dockerfile,
  pyproject.toml, app/, templates/, static/, tests/), plus `build.sh` for
  GHCR publish
- `.github/workflows/` — CI: `pr.yml` (PR gate), `release-please.yml` (release + deploy), `ghcr-cleanup.yml` (monthly retention). See `docs/superpowers/specs/2026-05-12-cicd-design.md`.
- `scripts/` — `provision.sh`, `deploy.sh`, `secrets.sh`, `ops.sh`,
  `doctor.sh`, plus `lib/` helpers and a `fake_vps/` test container
- `tests/` — bats suites; `task test` runs them all (the integration
  suites that build the fake-VPS stack require Docker Hub access — they
  cleanly skip if anonymous-pull is rate-limited on the runner)

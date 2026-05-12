# CI/CD: protected main, release-please-driven VPS deploys

**Date:** 2026-05-12
**Status:** Draft (pending review)
**Audience:** Maintainers of `lab-bridge` (this repo). Operators who currently run `task deploy` from their laptop.
**Reference:** `bioexperiment-lab-devices/serialhop` repo, whose `pr.yml` / `release-please.yml` patterns we inherit for cross-repo consistency.

## Purpose

Today the only automation in this repo is `siteapp-publish.yml`, which builds the siteapp image to GHCR on `siteapp-v*` tag pushes. Everything else — rendering configs, restoring secrets, rsyncing to the VPS, `docker compose up`, post-deploy health-checks — runs from an operator laptop via `task deploy`. There is no PR gating, no semantic PR titles, no on-push CI, no automated release, no auto-deploy.

This design replaces the laptop-as-CI loop with three GitHub Actions workflows that together:

- Gate every PR with semantic-title and verify checks (shellcheck, bats, ruff, pytest, siteapp `docker build` pre-flight).
- Cut releases via `release-please` driven by conventional-commit PR titles, using a dedicated GitHub App so release PRs trigger the verify workflow.
- On each created release, build & push the siteapp image to GHCR, Sigstore-attest the build provenance, and SSH-deploy the stack to the VPS — without removing the operator's existing local `task deploy` path.

Adding or removing a lab device (the **chisel device roster**) remains a laptop-only operation. CI never touches `chisel/users.json` or `siteapp/clients.json`. This is the "hybrid" state model: GitHub owns *the stack* (compose, caddy, siteapp, grafana, loki, the four passwords, SSH access); the operator's laptop owns *the roster*.

## Goals

- Protected `main`; all changes via squash-merged PRs with conventional-commit titles.
- Required PR checks that prevent merging broken bash, broken Python, or broken siteapp Docker builds into `main`.
- One `vX.Y.Z` tag per repo release; siteapp image tag matches; both reconstructible from any tagged commit.
- Releases auto-deploy to the VPS from GitHub Actions with no operator intervention beyond merging the release PR.
- Deployed version is queryable from outside the VPS via `/api/public/server-info`.
- Rollback to a prior tag is a one-command operator action that re-runs the deploy job in CI, not a laptop SSH session.
- Operator's existing `task deploy` workflow continues to work unchanged for roster maintenance.

## Non-goals

- Migrating the chisel device roster to GitHub-stored state. The roster stays operator-managed via `task secrets:add-client` and is deployed by the operator's `task deploy`.
- Multi-environment deploys (staging / canary). There is one VPS.
- CodeQL or other heavy static analysis. The Python surface is small; `ruff` + a future `bandit` step is more than enough.
- Automated dependency *merging* (Renovate proposes monthly PRs; merging is manual).
- Decoupling siteapp version from stack version. They are the same number.

## Architecture

### Workflow files

| File | Trigger | Purpose |
|------|---------|---------|
| `.github/workflows/pr.yml` | `pull_request` | Semantic-title check + `verify` job (shellcheck, bats, ruff, pytest, siteapp docker build). |
| `.github/workflows/release-please.yml` | `push` to `main`; `workflow_dispatch` for rollback | release-please job + `release-build` job (build & push siteapp image, attest, deploy to VPS, version smoke test). |
| `.github/workflows/ghcr-cleanup.yml` | monthly cron, manual | Prune old siteapp image tags, keep latest 10. |

`siteapp-publish.yml` is **deleted**; its image-build responsibility folds into `release-build`.

### Single source of truth for version

`compose/siteapp/VERSION` is a one-line file containing the current semver (e.g. `0.4.2`). It is:

- Updated by release-please via `extra-files`, the same way SerialHop rewrites `assets/version.json`.
- Read by `compose/siteapp/build.sh` to set the image tag and `LAB_BRIDGE_VERSION` build-arg.
- Read by the deploy step to construct `SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:$(cat compose/siteapp/VERSION)`.
- Baked into the siteapp image as an env var, so `/api/public/server-info` can report it.

At any tag `vX.Y.Z`, the deployed system is reconstructible: image `:X.Y.Z` plus the configs in the repo at that ref.

### State model (hybrid)

| What | Source of truth | Reaches the VPS via |
|------|-----------------|---------------------|
| Stack templates (`compose/`, `Caddyfile.tmpl`, grafana provisioning, loki config) | repo (git) | release-build deploy job |
| siteapp image | GHCR | release-build builds it; deploy job pulls it |
| `config.yaml` (stack portion) | GH vars + secrets, assembled on runner | release-build deploy job |
| The four stack secrets (Jupyter password hash, Grafana admin password, /admin/ basic-auth hash, agent upload token) | GH `secrets.*` | release-build deploy job |
| SSH key + known_hosts | GH `secrets.*` | release-build deploy job |
| Chisel device roster (`chisel_clients` in `config.yaml`) and its rendered artifacts (`chisel/users.json`, `siteapp/clients.json`) | operator laptop | `task deploy` from laptop, untouched by CI |

The two-track ops are kept apart by a single new flag — `LDS_STACK_ONLY=1` — that tells `scripts/deploy.sh` to skip roster-derived renders and exclude roster files from rsync.

## Branch protection (GitHub UI; not in code)

Apply on `main` after the workflows ship and have run once green:

- Require pull request before merging; **squash-merge only** (disable merge commits and rebase).
- Required status checks (must pass + branch must be up to date with base):
  - `pr-title` (from `pr.yml`)
  - `verify` (from `pr.yml`)
- Require linear history.
- Require conversation resolution before merging.
- Disallow force-push to `main`; disallow direct branch deletion.
- **Include administrators**: on. (Guards the sole operator against accidental `git push origin main`.)
- No required reviewers — single-operator repo.

## PR workflow (`.github/workflows/pr.yml`)

```yaml
name: PR
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]
concurrency:
  group: pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true
permissions:
  contents: read
  pull-requests: read
```

### Job 1 — `pr-title`

Uses `amannn/action-semantic-pull-request@v6`. Type list mirrors SerialHop exactly:

```
feat, fix, chore, docs, refactor, test, perf, build, ci, revert
```

`requireScope: false`, `subjectPattern: ^.+$`.

PR titles are load-bearing: under squash-merge they become the commit subject on `main`, which release-please scans for conventional-commit prefixes to decide the next version bump and changelog content.

### Job 2 — `verify`

Single `ubuntu-latest` job, fastest-fail first:

1. **shellcheck** against `scripts/**/*.sh` and `scripts/lib/*.sh`. Existing `# shellcheck source=...` directives are honored.
2. **bats** via `task test`. The integration suites that build the fake-VPS container skip cleanly when Docker Hub anonymous-pull is rate-limited (already implemented per `README.md`); they stay in CI.
3. **Siteapp Python**:
   - `ruff check compose/siteapp/`
   - `ruff format --check compose/siteapp/`
   - `pytest compose/siteapp/tests/` with pip cache keyed on `compose/siteapp/pyproject.toml`.
4. **Siteapp Docker pre-flight**: `docker buildx build compose/siteapp --load` with `LAB_BRIDGE_VERSION=pr-${{ github.event.pull_request.number }}`, no push, no extra platforms. Prevents `release-build` failing *after* release-please has already tagged.

CodeQL is intentionally omitted (low signal on a small FastAPI service). A future `bandit -r compose/siteapp/app/` step can be added if light security scanning is wanted.

## Release flow (`.github/workflows/release-please.yml`)

### Triggers

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      rollback_to:
        description: 'Tag to redeploy (e.g. v0.4.1). Leave empty for normal release-please run.'
        required: false
```

Concurrency: `release-please-main`, `cancel-in-progress: false`.

Permissions (job-scoped where possible):

```yaml
permissions:
  contents: write       # release-please creates tags/releases
  pull-requests: write  # release-please opens PRs
  id-token: write       # Sigstore
  attestations: write   # build provenance
  packages: write       # GHCR push
```

### Job 1 — `release-please`

Runs on every trigger; its release-please action step is gated on `inputs.rollback_to == ''` so a rollback dispatch passes through the job without opening a release PR or producing tag outputs. Keeping the job in the graph (rather than skipping it) lets `release-build` declare a clean `needs: release-please` without `if: always()` gymnastics.

```yaml
release-please:
  runs-on: ubuntu-latest
  outputs:
    release_created: ${{ steps.rp.outputs.release_created }}
    tag_name:        ${{ steps.rp.outputs.tag_name }}
  steps:
    - id: app-token
      if: inputs.rollback_to == ''
      uses: actions/create-github-app-token@v3
      with:
        app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
        private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}
    - id: rp
      if: inputs.rollback_to == ''
      uses: googleapis/release-please-action@v5
      with:
        config-file: release-please-config.json
        manifest-file: .release-please-manifest.json
        token: ${{ steps.app-token.outputs.token }}
```

A dedicated GitHub App is required (not the default `GITHUB_TOKEN`) because PRs opened with `GITHUB_TOKEN` do not fire `pull_request` events — every release PR would otherwise sit without `verify` checks until manually closed-and-reopened. This is the same App pattern SerialHop uses.

Outputs:
- `release_created` — boolean
- `tag_name` — `vX.Y.Z`

### Job 2 — `release-build`

```yaml
needs: release-please
if: |
  inputs.rollback_to != '' ||
  needs.release-please.outputs.release_created == 'true'
runs-on: ubuntu-latest
```

Resolves the operative tag and image-tag string at the top:

```bash
if [[ -n "${{ inputs.rollback_to }}" ]]; then
  TAG="${{ inputs.rollback_to }}"
else
  TAG="${{ needs.release-please.outputs.tag_name }}"
fi
VERSION="${TAG#v}"
echo "tag=$TAG"        >> "$GITHUB_OUTPUT"
echo "version=$VERSION" >> "$GITHUB_OUTPUT"
```

Steps (in order):

1. **Checkout at the operative tag.**
2. **Build & push siteapp image** — skipped on rollback (image already in GHCR, attested).
   - `docker/login-action@v3` to `ghcr.io` with `GITHUB_TOKEN`.
   - `docker/setup-buildx-action@v3`.
   - `docker/build-push-action@v6`:
     - `context: compose/siteapp`
     - `platforms: linux/amd64`
     - `push: true`
     - `tags: ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp:${{ steps.resolve.outputs.version }}`
     - `build-args`: `LAB_BRIDGE_VERSION=${{ steps.resolve.outputs.version }}`, `LAB_BRIDGE_GIT_SHA=${{ github.sha }}`
     - `provenance: false` (attestation done explicitly next).
3. **Sigstore attest** — skipped on rollback.
   - `actions/attest-build-provenance@v4` with `subject-name: ghcr.io/<owner>/lab-bridge-siteapp` and `subject-digest` from the build-push step output.
4. **Install deploy prerequisites on runner**: `rsync`, `yq` (mikefarah). `apt-get install -y rsync; curl-install yq` — the official binary, *not* the Python `yq`.
5. **Load SSH** — `webfactory/ssh-agent@v0.9` with `secrets.VPS_SSH_KEY`; write `secrets.VPS_SSH_KNOWN_HOSTS` to `~/.ssh/known_hosts`. No `StrictHostKeyChecking=no`.
6. **Assemble `config.yaml` on runner** — render `compose/config.ci.yaml.tmpl` (a tracked file, see below) via `envsubst`, with `SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:${VERSION}`.
7. **Write secret files** (consumed by `deploy.sh` from these exact paths):
   - `compose/grafana/admin_password` ← `${{ secrets.GRAFANA_ADMIN_PASSWORD }}`. `deploy.sh` already re-modes this to 0644 in the staging dir before rsync (Grafana inside the container runs as uid 472).
   - `compose/siteapp/agent_upload_token` ← `${{ secrets.AGENT_UPLOAD_TOKEN }}`.
8. **Deploy**:
   ```bash
   LDS_CONFIG="$GITHUB_WORKSPACE/config.ci.yaml" \
   LDS_STACK_ONLY=1 \
   bash scripts/deploy.sh
   ```
   The existing health-check inside `deploy.sh` runs; deploy fails if any of `/`, `/grafana/login`, `/docs/`, `/download/agent`, `/admin/` (must be `401`), `/_static/site.css`, `/api/public/health`, `/api/public/server-info` is unhealthy.
9. **Version smoke test**:
   ```bash
   curl -fsSL "https://${{ vars.VPS_HOST }}/api/public/server-info" \
     | jq -e --arg v "${{ steps.resolve.outputs.version }}" '.version == $v'
   ```
   Fails the deploy if the deployed siteapp doesn't self-report the version we just released. Closes the loop.

### `release-please-config.json`

```json
{
  "release-type": "simple",
  "packages": {
    ".": {
      "package-name": "lab-bridge",
      "include-component-in-tag": false,
      "extra-files": [
        { "type": "generic", "path": "compose/siteapp/VERSION" }
      ]
    }
  },
  "changelog-sections": [
    { "type": "feat",     "section": "Features"      },
    { "type": "fix",      "section": "Bug Fixes"     },
    { "type": "perf",     "section": "Performance"   },
    { "type": "revert",   "section": "Reverts"       },
    { "type": "chore",    "section": "Chores",        "hidden": true },
    { "type": "docs",     "section": "Documentation", "hidden": true },
    { "type": "refactor", "section": "Refactoring",   "hidden": true },
    { "type": "test",     "section": "Tests",         "hidden": true },
    { "type": "build",    "section": "Build",         "hidden": true },
    { "type": "ci",       "section": "CI",            "hidden": true }
  ]
}
```

`compose/siteapp/VERSION` is wrapped in release-please annotations:

```
# x-release-please-start-version
0.4.2
# x-release-please-end
```

`.release-please-manifest.json` is seeded with the chosen starting version — `0.1.0` if starting fresh, or a higher number to reflect the current state of the deployed siteapp. Recommendation: seed with the current pinned siteapp version (read from your local `config.yaml`).

## Deploy mechanics — `scripts/deploy.sh` refactor

Existing `scripts/deploy.sh` does five things: (1) renders templates into a staging dir, (2) prepares secret files, (3) rsyncs to VPS, (4) `docker compose up -d` + selective restarts, (5) HTTPS health-check.

The refactor adds one mode flag, `LDS_STACK_ONLY`. When set to `1`:

| Step | Behavior change |
|------|-----------------|
| `render_chisel_users` | **Skipped**. CI's `config.yaml` carries `chisel_clients: []`, but skipping is belt-and-braces. |
| `render_siteapp_clients` | **Skipped** for the same reason. |
| rsync | Adds `--exclude='chisel/users.json' --exclude='siteapp/clients.json'` so the operator's roster on the VPS is preserved across CI deploys. |
| `docker compose restart …` | Drops `chisel` from the restart list (its bind-mount config did not change). `caddy` and `siteapp` still restart. |

Plus one guardrail: if `LDS_STACK_ONLY=1` and `chisel_clients` is non-empty in the supplied config, exit with a clear error ("CI deploy cannot manage the device roster"). Catches operator confusion.

Laptop deploys (no env var set) keep their existing behavior — render & rsync the roster, restart all three services.

### `compose/config.ci.yaml.tmpl` (new tracked file)

A copy of `config.example.yaml` with every value templated and the roster stubbed:

```yaml
vps:
  host: ${VPS_HOST}
  ssh_user: ${VPS_SSH_USER}
  ssh_port: ${VPS_SSH_PORT}
  remote_root: ${VPS_REMOTE_ROOT}
  notebooks_path: ${VPS_NOTEBOOKS_PATH}

caddy:
  acme_email: ${ACME_EMAIL}

jupyter:
  image: ${JUPYTER_IMAGE}
  password_hash: "${JUPYTER_PASSWORD_HASH}"

chisel:
  image: ${CHISEL_IMAGE}
  listen_port: ${CHISEL_LISTEN_PORT}

loki:
  image: ${LOKI_IMAGE}
  retention_days: ${LOKI_RETENTION_DAYS}

grafana:
  image: ${GRAFANA_IMAGE}

chisel_clients: []

siteapp:
  image: ${SITEAPP_IMAGE}
  admin_password_hash: "${ADMIN_PASSWORD_HASH}"
```

The workflow exports every `${VAR}` from `vars.*` / `secrets.*` / the resolved tag, then `envsubst < compose/config.ci.yaml.tmpl > config.ci.yaml` before invoking deploy.

## GitHub vars and secrets — final inventory

### Vars (`vars.*`)

| Name | Example value | Source |
|------|---------------|--------|
| `RELEASE_PLEASE_APP_ID` | `1234567` | GitHub App page |
| `VPS_HOST` | `lab.example.com` | operator's `config.yaml` |
| `VPS_SSH_USER` | `khamit` | operator's `config.yaml` |
| `VPS_SSH_PORT` | `22` | operator's `config.yaml` |
| `VPS_REMOTE_ROOT` | `/srv/lab-bridge` | operator's `config.yaml` |
| `VPS_NOTEBOOKS_PATH` | `/srv/jupyterlab/work` | operator's `config.yaml` |
| `ACME_EMAIL` | `you@example.com` | operator's `config.yaml` |
| `JUPYTER_IMAGE` | `quay.io/jupyter/scipy-notebook:2026-04-20` | operator's `config.yaml` |
| `CHISEL_IMAGE` | `jpillora/chisel:1.10.1` | operator's `config.yaml` |
| `CHISEL_LISTEN_PORT` | `8080` | operator's `config.yaml` |
| `LOKI_IMAGE` | `grafana/loki:3.2.1` | operator's `config.yaml` |
| `LOKI_RETENTION_DAYS` | `30` | operator's `config.yaml` |
| `GRAFANA_IMAGE` | `grafana/grafana:11.3.0` | operator's `config.yaml` |

`SITEAPP_IMAGE` is **not** a var — it is constructed in the workflow from the resolved tag.

### Secrets (`secrets.*`)

| Name | Format | Source |
|------|--------|--------|
| `RELEASE_PLEASE_APP_KEY` | PEM private key | GitHub App page |
| `VPS_SSH_KEY` | OpenSSH private key | operator |
| `VPS_SSH_KNOWN_HOSTS` | Single line, output of `ssh-keyscan -p <port> <host>` | operator |
| `JUPYTER_PASSWORD_HASH` | `sha1:<salt>:<digest>` | `jupyter.password_hash` field in laptop `config.yaml` (set via `task secrets:set-jupyter-password`) |
| `ADMIN_PASSWORD_HASH` | bcrypt | `siteapp.admin_password_hash` field in laptop `config.yaml` (set via `task secrets:set-admin-password`) |
| `GRAFANA_ADMIN_PASSWORD` | plaintext | `compose/grafana/admin_password` on laptop |
| `AGENT_UPLOAD_TOKEN` | opaque token | `compose/siteapp/agent_upload_token` on laptop |

The first-time migration is: operator reads each value from the corresponding local file (or via `task secrets:set-*` outputs), pastes into the GH UI, then keeps the local files for the laptop's `task deploy` of the roster.

## Server-version surface

### Dockerfile (`compose/siteapp/Dockerfile`)

Adds:

```dockerfile
ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION
ENV LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA
```

PR `verify` builds get `dev` / `unknown`; release builds get real values; local laptop `compose/siteapp/build.sh` is updated to pass `git describe --always --dirty` and the content of `VERSION`.

### Siteapp

New module `compose/siteapp/app/version.py`:

```python
import os
LAB_BRIDGE_VERSION = os.environ.get("LAB_BRIDGE_VERSION", "dev")
LAB_BRIDGE_GIT_SHA = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown")
```

`/api/public/server-info` response gains two fields:

```json
{
  "chisel": { "listen_port": 8080 },
  "loki": { ... existing ... },
  "forward_tunnels": [ ... existing ... ],
  "version": "0.4.2",
  "git_sha": "abc1234"
}
```

The contract change is additive. The matching client-spec update lands in a follow-up edit to `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` and is **not** part of this CI/CD design's scope.

## Rollback

`Taskfile.yml` gains:

```yaml
"deploy:rollback":
  desc: Trigger a CI rollback to a prior tag (e.g. task deploy:rollback -- v0.4.1)
  cmd: gh workflow run release-please.yml -f rollback_to={{.CLI_ARGS}}
```

Mechanism: `workflow_dispatch` on `release-please.yml` with the `rollback_to` input populated. The `release-please` job is skipped; `release-build` runs with the operative tag set to `inputs.rollback_to`, skipping its build/attest steps (the image already exists in GHCR with attestation) and going straight to deploy.

If a rollback is needed before the new flow has produced any tags, the operator's laptop `task deploy` against `git checkout <tag>` remains a working escape hatch.

## GHCR retention (`.github/workflows/ghcr-cleanup.yml`)

```yaml
on:
  schedule:
    - cron: '0 6 1 * *'   # 06:00 UTC on the 1st of every month
  workflow_dispatch:
permissions:
  packages: write
jobs:
  prune:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/delete-package-versions@v5
        with:
          package-name: lab-bridge-siteapp
          package-type: container
          min-versions-to-keep: 10
          delete-only-untagged-versions: false
          dry-run: true   # flip to false after one cycle of clean logs
```

## Renovate (`renovate.json`)

Requires the Renovate App installed on the org (one-time UI action; no workflow file).

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "schedule": ["before 6am on the first day of the month"],
  "timezone": "Etc/UTC",
  "labels": ["renovate"],
  "packageRules": [
    { "matchManagers": ["dockerfile", "docker-compose"], "groupName": "container images" },
    { "matchManagers": ["pip_requirements", "pep621"], "groupName": "siteapp python deps" }
  ]
}
```

Monthly cadence keeps PR noise low. Merging is manual.

## Failure modes and recovery

| Failure | What happens | Recovery |
|---------|--------------|----------|
| `verify` fails on a PR | Branch protection blocks merge. | Fix code; push. |
| release-please opens a release PR but `verify` fails on it | Release is blocked. | Fix the issue in a follow-up PR; release-please's PR rebases on merge. |
| `release-build` fails *after* siteapp image push but *before* deploy | Image is in GHCR with a tag that has no deployed instance. | Re-run the workflow (`gh workflow run release-please.yml`) — the deploy is idempotent; nothing to clean up. |
| `release-build` deploy succeeds but health-check fails | Workflow fails red; rollback via `task deploy:rollback -- v<previous>`. | Same. |
| VPS unreachable | SSH step fails before any state change on the VPS. | Investigate VPS; re-run workflow. |
| Operator pushes a roster change via `task deploy` while a CI deploy is mid-flight | Last-write-wins on the affected files. CI excludes the roster files; the operator's deploy restarts all three services. | Conflict is rare in practice (single operator). If it happens, re-run the laptop deploy. |
| GHCR cleanup deletes a tag still referenced on the VPS | Re-pulling that exact tag would fail. | `min-versions-to-keep: 10` and the cron's monthly cadence make this extremely unlikely. If it happens, `task deploy:rollback -- v<later>` to a tag that *is* still present. |

## Migration plan (one-time)

1. Create the dedicated GitHub App for release-please; install on the repo; record `App ID` as `vars.RELEASE_PLEASE_APP_ID` and the PEM as `secrets.RELEASE_PLEASE_APP_KEY`.
2. Populate the rest of `vars.*` and `secrets.*` from the operator's local state.
3. Add `VERSION` file, `release-please-config.json`, `.release-please-manifest.json`, the three workflow files, `renovate.json`, `compose/config.ci.yaml.tmpl`, and the deploy.sh refactor in **one PR**, with the existing `siteapp-publish.yml` deleted in the same PR.
4. Merge after `verify` passes. release-please will open its first release PR on the next push to `main`. Merge that to cut `v<initial>` and exercise the deploy job end-to-end.
5. After the first green release-build, enable branch protection with `pr-title` and `verify` as required checks.
6. After one clean cycle of `ghcr-cleanup` in dry-run, flip its `dry-run: false`.

## Open questions

None at draft time. Implementation will surface details that do not change the design:

- Exact action SHAs to pin to (we will pin all third-party actions at SHA, not tag, per the same hardening posture SerialHop uses).
- The precise `ssh-keyscan` invocation for seeding `VPS_SSH_KNOWN_HOSTS`.
- Whether `yq` (mikefarah) is fetched per-run or installed via a setup action.
- Whether the laptop `task deploy` path should be taught about `VERSION` (so a roster-only laptop deploy doesn't accidentally pin an old siteapp tag from a stale local `config.yaml`) — likely yes, but the change is small and contained to `Taskfile.yml` + a tiny render helper.

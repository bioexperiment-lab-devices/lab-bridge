# CI/CD: protected `main`, release-please, automated VPS deploys

**Date:** 2026-05-12
**Status:** Approved (design phase complete; implementation plan pending)
**Audience:** Maintainers of `lab-bridge` (this repo). Inherits conventions from `bioexperiment-lab-devices/serialhop` so the two repos feel identical to operate.

## Purpose

Today, every change to this repo ships in two manual steps performed from the operator's laptop:

1. Edit, commit, push to `main` (no automated checks; nothing prevents a broken script landing on `main`).
2. Run `task deploy`, which renders configs, rsyncs to the VPS over SSH, and runs `docker compose up -d`. The operator's laptop holds every secret and is the only place a deploy can originate.

Only one CI workflow exists (`siteapp-publish.yml`) and it does just the GHCR image push for siteapp on `siteapp-v*` tag pushes. After a publish, the operator still has to manually edit `config.yaml`'s `siteapp.image` pin and re-run `task deploy`.

This design replaces that flow end-to-end:

- `main` is protected; changes land via PRs with squash-merge, gated on automated checks.
- PR titles follow conventional-commit conventions; merges drive a `release-please` changelog and tag.
- On a release tag, CI builds the siteapp image to GHCR with Sigstore provenance, then deploys the stack to the VPS over SSH, and verifies the post-deploy version surface.
- The chisel-client roster (lab-device passwords) remains a laptop-managed concern — CI never touches `chisel/users.json` or `siteapp/clients.json` on the VPS.

## Goals

- Branch protection on `main`: no direct pushes, squash-merge only, required checks must pass.
- Semantic PR titles drive a `release-please` automated changelog + version bump.
- Releases trigger an automated VPS deploy from CI — no SSH from the operator's laptop required for stack changes.
- Siteapp image and "the stack" share **one** version number. At any tag `vX.Y.Z`, the running system is fully reconstructible.
- Deployed version is observable via `GET /api/public/server-info`.
- Image pins, paths, and other stack-level config live in tracked files (PR-reviewed, Renovate-bumpable), not in GitHub Actions variables.
- One-command rollback to any prior released tag, runnable from any operator's laptop without SSH.

## Non-goals

- Continuous deployment on every merge to `main`. Deploys happen only when a `release-please` release PR is squash-merged. This keeps the "ready to ship" decision a deliberate human action.
- Migrating the chisel-client roster (`task secrets:add-client`) into CI. The roster stays under operator-laptop ops. CI deploys are roster-preserving by construction.
- Multi-environment (staging/prod) support. One VPS, one deploy target.
- Per-PR siteapp preview images. PRs build the siteapp image (no push) as a pre-flight; they don't publish a `pr-<n>` tag to GHCR.
- Notifications, drift checks, and CodeQL — deferred (see "Deferred"). Renovate is in scope but on a monthly cron.

## Architecture overview

Three workflows under `.github/workflows/`:

- **`pr.yml`** — runs on every PR. Jobs: `pr-title` (semantic-PR check) and `verify` (shellcheck, bats, ruff, pytest, `docker build` of siteapp). Concurrency: per-PR, cancel-in-progress.
- **`release-please.yml`** — runs on push to `main` and on manual `workflow_dispatch` (for rollback). Jobs: `release-please` (creates/updates release PR; cuts tags via a dedicated GitHub App) and `release-build` (gated on `release_created == 'true'`, or on manual dispatch with a `rollback_to` input). `release-build` builds & pushes the siteapp image, attests provenance, SSH-deploys the stack to the VPS, and verifies `/api/public/server-info` reports the freshly-released version.
- **`ghcr-cleanup.yml`** — monthly cron, prunes old `lab-bridge-siteapp` image versions, keeps the most recent 10.

One configuration file: **`renovate.json`** with a monthly schedule (requires the Renovate App installed on the org; no workflow file needed).

The existing `siteapp-publish.yml` is **deleted** — its responsibility is folded into `release-build`. The `siteapp-v*` tag convention is retired.

### Single-version model

`release-please` drives one tag `vX.Y.Z` for the entire repo. Each release:

- Rebuilds the siteapp image, pushed to `ghcr.io/<owner>/lab-bridge-siteapp:X.Y.Z` and `:latest`, with build-args carrying the version and short SHA so siteapp's `/api/public/server-info` can advertise them.
- Updates a tracked file `compose/siteapp/VERSION` via `release-please`'s `extra-files` mechanism so the laptop `task deploy` path and CI deploy path read the same version.
- Deploys the rendered stack to the VPS in **stack-only** mode (see "Stack-only deploy mode").

Image rebuilds run unconditionally per release. Buildx cache makes this cheap; the alternative (skipping the rebuild when siteapp source didn't change) introduces ambiguity about which image is actually attested at this tag.

### Source-of-truth split

| Lives in | What |
|---|---|
| Tracked in git | Image pins, paths, retention, ACME email, port, chisel listen port — i.e. anything that's non-sensitive and benefits from PR review |
| GitHub vars (3) | `RELEASE_PLEASE_APP_ID`, `VPS_HOST`, `VPS_SSH_USER` |
| GitHub secrets (6) | `RELEASE_PLEASE_APP_KEY`, `VPS_SSH_KEY`, `JUPYTER_PASSWORD_HASH`, `ADMIN_PASSWORD_HASH`, `GRAFANA_ADMIN_PASSWORD`, `AGENT_UPLOAD_TOKEN` |
| Operator laptop (gitignored `config.yaml`) | Roster only: `chisel_clients[]` |
| Operator laptop (gitignored files) | The same password hashes/tokens as GH secrets, used by `task deploy` when run locally |

The "everything that isn't sensitive lives in git" rule deliberately keeps the GH Actions configuration small (3 vars + 6 secrets). Bumping a base image becomes a one-line PR with a visible diff, runs through `verify`, and lands as a release-please release — never an opaque click in the GH UI.

## Branch protection & PR conventions

Applied in GitHub UI on `main` (these settings live outside code; record them here for posterity):

- Require a PR before merging.
- **Squash-merge only.** No merge commits, no rebase-merge. The PR title becomes the commit subject on `main` — that's what `release-please` scans.
- Required status checks: `pr-title`, `verify`. (Branches do **not** need to be up to date before merging — required checks must pass on the PR head, but PRs aren't forced to rebase on every concurrent merge to `main`. No merge conflicts is enough.)
- Require linear history.
- Require conversation resolution before merging.
- Disallow force-push to `main`.
- Disallow direct deletion of `main`.
- Include administrators in the restrictions (guards against accidental `git push origin main`).
- No required reviewers (single-operator project).

### Semantic PR titles

`pr-title` uses `amannn/action-semantic-pull-request@v6` with the SerialHop type list:

```
feat, fix, chore, docs, refactor, test, perf, build, ci, revert
```

`requireScope: false`, `subjectPattern: ^.+$`. Optional scopes (used freely, never enforced) match the project subsystems: `siteapp`, `caddy`, `chisel`, `grafana`, `loki`, `deploy`, `render`, `secrets`.

### Changelog sections

Mirrors SerialHop:

| Type | Section | Hidden |
|---|---|---|
| `feat` | Features | no |
| `fix` | Bug Fixes | no |
| `perf` | Performance | no |
| `revert` | Reverts | no |
| `chore` | Chores | yes |
| `docs` | Documentation | yes |
| `refactor` | Refactoring | yes |
| `test` | Tests | yes |
| `build` | Build | yes |
| `ci` | CI | yes |

## `pr.yml` — PR verify

### Triggers

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]
```

`edited` is required so `pr-title` re-runs when a maintainer fixes a non-conforming title.

### Concurrency

```yaml
concurrency:
  group: pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true
```

### Permissions

```yaml
permissions:
  contents: read
  pull-requests: read
```

### Jobs

**`pr-title`** — `ubuntu-latest`, runs `amannn/action-semantic-pull-request@v6` with the type list above.

**`verify`** — `ubuntu-latest`, single job, steps in fastest-fail order:

1. Checkout.
2. `shellcheck` against `scripts/**/*.sh` and `scripts/lib/*.sh`. Existing `# shellcheck source=…` directives are honored.
3. Install Task (`arduino/setup-task@v2`), Python (`actions/setup-python@v5`, version from `compose/siteapp/pyproject.toml`), and bats (`bats-core/bats-action`).
4. `task test` — runs the full `tests/` suite. The integration suites that build the fake-VPS container already skip cleanly when Docker Hub anonymous-pull is rate-limited (per README), so they're safe to keep in CI.
5. siteapp lint: `ruff check compose/siteapp/app compose/siteapp/tests` and `ruff format --check ...`.
6. siteapp tests: `pytest compose/siteapp/tests/`.
7. siteapp image build (no push): `docker buildx build compose/siteapp --load`. This is the pre-flight that prevents `release-build` failing *after* `release-please` has cut a tag.

No CodeQL. If lightweight Python security scanning is wanted later, add `bandit -r compose/siteapp/app/` as a one-line step — cheap, no additional infrastructure.

## `release-please.yml` — release-please + release-build

### Triggers

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      rollback_to:
        description: 'Tag to redeploy (e.g. v0.4.1). Leave empty for a normal release-please run.'
        required: false
```

### Concurrency

```yaml
concurrency:
  group: release-please-main
  cancel-in-progress: false
```

`cancel-in-progress: false` is deliberate — never kill a mid-tag-cut.

### Permissions

```yaml
permissions:
  contents: write       # release-please tags/releases
  pull-requests: write  # release-please opens release PRs
  id-token: write       # Sigstore
  attestations: write   # build provenance
  packages: write       # GHCR push
```

These permissions are scoped to this workflow file only. `pr.yml` stays read-only.

### Job 1: `release-please`

Skipped entirely on `workflow_dispatch` with a non-empty `rollback_to`. Otherwise:

1. Mint an installation access token from a dedicated **GitHub App** — `vars.RELEASE_PLEASE_APP_ID` + `secrets.RELEASE_PLEASE_APP_KEY`. The default `GITHUB_TOKEN` would create PRs that don't fire downstream `pull_request` events (GitHub's anti-recursion safeguard), so every release PR would sit without `verify` checks until manually closed-and-reopened. App-minted tokens bypass that restriction.
2. Run `googleapis/release-please-action@v5` with `release-please-config.json` and `.release-please-manifest.json`.
3. Outputs `release_created` and `tag_name` for the next job.

### GitHub App

Reuses the existing SerialHop `release-please` App, renamed to a neutral identifier (e.g. `bel-release-please`). Renaming a GitHub App does not invalidate the App ID or private key. Setup:

1. Rename the existing App on github.com → Settings → Developer settings → GitHub Apps.
2. App settings → Install App → grant access to `lab_devices_server` in the `bioexperiment-lab-devices` org.
3. Verify permissions are still `Contents: read & write` and `Pull requests: read & write`.
4. Store the same App ID and `.pem` contents either as **org-level** variable/secret (cleanest — both repos share one source of truth, future repos inherit them) or duplicate as repo-level vars/secrets.

Rate limits are per-App-installation. The two repos share the (very generous) release-please quota; no practical impact.

### release-please config

**`release-please-config.json`:**

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

**`.release-please-manifest.json`** is seeded with the starting version (e.g. `{".": "0.4.0"}` to reflect current history — exact value chosen at implementation time).

**`compose/siteapp/VERSION`** is a one-line tracked file containing the current semver (no leading `v`). It is the single source of truth for the siteapp image tag and the `LAB_BRIDGE_VERSION` build arg. release-please rewrites it on every release; both laptop and CI deploys read it.

### Job 2: `release-build`

```yaml
needs: release-please
if: |
  (github.event_name == 'push' && needs.release-please.outputs.release_created == 'true')
  || (github.event_name == 'workflow_dispatch' && github.event.inputs.rollback_to != '')
```

Runs on `ubuntu-latest`. The deploy target ref is `${{ needs.release-please.outputs.tag_name }}` on a normal release, or `${{ github.event.inputs.rollback_to }}` on a manual dispatch.

Steps:

1. Checkout at the deploy ref.
2. **Build & push siteapp image** (skipped on rollback — image already exists in GHCR for that tag):
   - `docker/login-action@v3` to `ghcr.io` with `GITHUB_TOKEN`.
   - `docker/setup-buildx-action@v3`.
   - `docker/build-push-action@v6` with `context: compose/siteapp`, `platforms: linux/amd64`, `provenance: false`, build-args `LAB_BRIDGE_VERSION=<tag-without-v>` and `LAB_BRIDGE_GIT_SHA=${{ github.sha }}`, tags `ghcr.io/<owner>/lab-bridge-siteapp:<tag-without-v>` and `…:latest`.
3. **Attest provenance** (skipped on rollback): `actions/attest-build-provenance@v4` with the built image's digest.
4. **Set up SSH** on the runner:
   - Install `rsync` and `yq v4` (the runner's defaults are missing or wrong-version).
   - `webfactory/ssh-agent@v0.9` loads `secrets.VPS_SSH_KEY`.
   - Pass `LDS_SSH_OPTS='-o StrictHostKeyChecking=accept-new'` so the first SSH per job accepts the VPS host key without TOFU prompts; subsequent calls within the same job verify against it. (No `known_hosts` file is tracked — see "Why no `known_hosts` pin" in "Decisions".)
5. **Assemble runtime config on the runner.** A new tracked template `compose/config.ci.yaml.tmpl` carries the schema with `${VAR}` placeholders for the instance-specific values. The workflow renders it via `envsubst` using `vars.VPS_HOST`, `vars.VPS_SSH_USER`, and the three password-hash secrets (`JUPYTER_PASSWORD_HASH`, `ADMIN_PASSWORD_HASH`). Image pins, paths, retention, ACME email, ports come from `compose/pins.yaml` (see "Source-of-truth files"). The rendered file is written to a runner-local path that `deploy.sh` consumes via `LDS_CONFIG`. `chisel_clients` is hardcoded to `[]` in the template; an `LDS_REQUIRE_VAULT=1` guard in `deploy.sh` asserts it stays empty in stack-only mode.
6. **Assemble secret files** under `compose/grafana/admin_password` and `compose/siteapp/agent_upload_token` from `secrets.GRAFANA_ADMIN_PASSWORD` and `secrets.AGENT_UPLOAD_TOKEN` respectively (matches `deploy.sh`'s current expectations).
7. **Deploy:**
   ```bash
   LDS_CONFIG="$PWD/config.ci.rendered.yaml" \
   LDS_STACK_ONLY=1 \
   LDS_REQUIRE_VAULT=1 \
   bash scripts/deploy.sh
   ```
   (`LDS_SSH_OPTS` was already exported in step 4.)
   The existing health-check in `deploy.sh` (lines 90–127 of current `scripts/deploy.sh`) probes `/`, `/grafana/login`, `/docs/`, `/download/agent`, `/admin/` (asserted `401`), `/_static/site.css`, `/api/public/health`, `/api/public/server-info` — all already covered.
8. **Verify deployed version**: `curl https://${VPS_HOST}/api/public/server-info | jq -e --arg v "<expected>" '.version == $v'`. This closes the loop that the freshly-built image is the one actually running.

## Source-of-truth files

This design introduces two new tracked files plus a refactor of `config.yaml`'s schema.

### `compose/pins.yaml` (new, tracked)

Single source of truth for stack-level pins and stable infrastructure paths. Read by **both** laptop `task deploy` and CI `release-build`. Renovate targets this file.

Shape (final fields determined at implementation time; canonical example):

```yaml
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
chisel_listen_port: 8080
loki_image: grafana/loki:3.2.1
loki_retention_days: 30
grafana_image: grafana/grafana:11.3.0
siteapp_image_repo: ghcr.io/<owner>/lab-bridge-siteapp   # owner is tracked here, not derived
acme_email: you@example.com
remote_root: /srv/lab-bridge
notebooks_path: /srv/jupyterlab/work
ssh_port: 22
```

### `compose/siteapp/VERSION` (new, tracked)

One-line file. Holds the current siteapp semver (no leading `v`). release-please's `extra-files` rewrites it on every release. Both `task deploy` (laptop, via `scripts/lib/config.sh`) and CI's deploy step read it to determine the siteapp image tag.

The existing operator-managed `siteapp.image` field in `config.yaml` is removed by this refactor — the image reference is now fully derived from `compose/pins.yaml`'s `siteapp_image_repo` plus the version in `compose/siteapp/VERSION`. Both laptop and CI read from the same tracked source.

### `config.yaml` schema change (gitignored, operator-side)

Image pins, paths, ACME email, ports, retention — **removed** (moved to `compose/pins.yaml`).

`config.yaml` now carries only:

- `vps.host`, `vps.ssh_user`
- `jupyter.password_hash`, `siteapp.admin_password_hash` (sensitive — stay on laptop)
- `chisel_clients[]` — the roster, laptop-managed

`config.example.yaml` is updated to match the new minimal schema, with a comment pointing operators to `compose/pins.yaml` for stack pins.

`scripts/lib/config.sh` is updated to load `compose/pins.yaml` alongside `config.yaml`, with `pins.yaml` providing infrastructure-level values and `config.yaml` providing instance-level values + roster.

### `compose/config.ci.yaml.tmpl` (new, tracked)

CI-only template, rendered via `envsubst` on the runner. Carries the same minimal schema as the post-refactor `config.yaml` (host/user/password hashes/roster) with `${VAR}` placeholders for the instance values and `chisel_clients: []` hardcoded.

## Stack-only deploy mode

`scripts/deploy.sh` is refactored to support `LDS_STACK_ONLY=1` (env var, defaults to unset → original full-deploy behavior). When set:

- `render_chisel_users` and `render_siteapp_clients` calls are skipped.
- The rsync gains `--exclude='chisel/users.json' --exclude='siteapp/clients.json'`.
- The post-rsync `docker compose restart` list drops `chisel` (its bind-mounted `users.json` didn't change; restarting would kick live lab clients off their tunnels for no reason). `caddy` and `siteapp` continue to restart.

Additionally, `LDS_REQUIRE_VAULT=1` (set together with `LDS_STACK_ONLY=1` in CI) asserts that the loaded `config.yaml` has an empty `chisel_clients[]`. If not, `deploy.sh` fails fast with a clear error — guards against an operator accidentally letting roster data leak into the CI config template.

The laptop `task deploy` path is unaffected (neither env var is set by default), continues to render and rsync the roster files and restart chisel.

## Server-versioning surface

`compose/siteapp/Dockerfile` adds:

```dockerfile
ARG LAB_BRIDGE_VERSION=dev
ARG LAB_BRIDGE_GIT_SHA=unknown
ENV LAB_BRIDGE_VERSION=$LAB_BRIDGE_VERSION
ENV LAB_BRIDGE_GIT_SHA=$LAB_BRIDGE_GIT_SHA
```

PR `verify` builds with the defaults (image labelled `dev`/`unknown`). `release-build` passes real values. Local `compose/siteapp/build.sh` is updated to pass values derived from `git describe`.

A small siteapp module (e.g. `compose/siteapp/app/version.py`) reads the two env vars with safe fallbacks. The existing `/api/public/server-info` handler (per `2026-05-11-server-info-design.md`) gains two additive fields:

```json
{
  "chisel_listen_port": 8080,
  "loki": { "...": "..." },
  "version": "0.4.2",
  "git_sha": "abc1234"
}
```

The contract change is additive — existing clients keep working. The matching client-spec update lands in a separate PR amending `2026-05-11-server-info-client-spec.md`.

Surface in the docs portal footer is deferred.

## Rollback

`release-please.yml` accepts a `workflow_dispatch` input `rollback_to`. When set:

- The `release-please` job is skipped.
- The `release-build` job runs against the supplied tag.
- The image-build & attestation steps are skipped (image already in GHCR; attestation already attached). Deploy step runs unconditionally with the supplied tag's SITEAPP version.

`Taskfile.yml` gains:

```yaml
"deploy:rollback":
  desc: Trigger a CI rollback to a prior tag (e.g. task deploy:rollback -- v0.4.1)
  cmd: gh workflow run release-please.yml -f rollback_to={{.CLI_ARGS}}
```

Rollback runs from any operator's laptop with `gh` installed and authenticated — no SSH from the laptop. The roster on the VPS is preserved (stack-only mode).

## `ghcr-cleanup.yml` — image retention

```yaml
on:
  schedule:
    - cron: '0 6 1 * *'      # 06:00 UTC on the 1st of every month
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
          dry-run: true   # flipped to false after one cycle's logs look correct
```

The dry-run flag is flipped to `false` after the first scheduled run produces a sensible-looking delete list in the workflow logs.

## `renovate.json` — monthly dependency PRs

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "schedule": ["before 6am on the first day of the month"],
  "timezone": "Etc/UTC",
  "labels": ["renovate"],
  "packageRules": [
    { "matchManagers": ["dockerfile", "docker-compose", "regex"], "groupName": "container images" },
    { "matchManagers": ["pip_requirements", "pep621"], "groupName": "siteapp python deps" }
  ]
}
```

Requires the Renovate App installed on the `bioexperiment-lab-devices` org. The `regex` manager (configured via additional `customManagers` if needed at implementation time) is what targets `compose/pins.yaml`'s image-pin lines; out-of-box `dockerfile`/`docker-compose` managers cover `compose/siteapp/Dockerfile` and the compose template.

## GitHub vars & secrets inventory

**Variables (3):**

| Name | Purpose |
|---|---|
| `RELEASE_PLEASE_APP_ID` | Numeric App ID for the shared `release-please` GitHub App. Org-level recommended. |
| `VPS_HOST` | Public hostname or IPv4 of the VPS. |
| `VPS_SSH_USER` | Deploy user on the VPS (must already exist with passwordless sudo, per `provision.sh`). |

**Secrets (6):**

| Name | Purpose |
|---|---|
| `RELEASE_PLEASE_APP_KEY` | PEM private key for the App. Org-level recommended. |
| `VPS_SSH_KEY` | SSH private key for the deploy user. |
| `JUPYTER_PASSWORD_HASH` | `sha1:salt:digest` for the shared JupyterLab password. |
| `ADMIN_PASSWORD_HASH` | bcrypt hash for the `/admin/` basic-auth user. |
| `GRAFANA_ADMIN_PASSWORD` | Plaintext; written to `compose/grafana/admin_password` on the runner. |
| `AGENT_UPLOAD_TOKEN` | Bearer for `POST /api/agent/upload`; written to `compose/siteapp/agent_upload_token` on the runner. |

The siteapp image reference (`ghcr.io/<owner>/lab-bridge-siteapp:<tag>`) is **computed** at deploy time from the release tag + repo owner, not stored.

## First-run migration

One-time setup performed by the operator:

1. **GitHub App.** Rename SerialHop's `release-please` GitHub App to a neutral identifier; install on `lab_devices_server`. Store `RELEASE_PLEASE_APP_ID` and `RELEASE_PLEASE_APP_KEY` at org level (recommended) or repo level.
2. **GH vars/secrets.** Populate the three vars and six secrets above. Source values: laptop's current `config.yaml` (jupyter/admin password hashes), `compose/grafana/admin_password` (grafana password plaintext), `compose/siteapp/agent_upload_token` (agent token plaintext), `~/.ssh/<key>` (VPS SSH key).
3. **Branch protection.** Apply the rules listed in "Branch protection & PR conventions" via the GitHub UI.
4. **Renovate App.** Install on the org if not already; grant access to this repo.
5. **Seed `.release-please-manifest.json`.** Initial version chosen to reflect current state (e.g. `0.4.0`).
6. **Seed `compose/pins.yaml`** from current `config.yaml` values.
7. **Seed `compose/siteapp/VERSION`** with the currently-deployed siteapp version.
8. **First merge to `main`** with the new workflows triggers `release-please`; review and merge the resulting release PR to cut the first automated release.

## Decisions

### Why no `known_hosts` pin?

A tracked `compose/.known_hosts` file would protect the runner-to-VPS SSH path against MITM and against silent VPS replacement at the same DNS name. The cost is one tracked line plus a one-line PR after any host-key rotation. For a small private project where the deploy window is a few minutes per release and the attacker capability required is roughly "owns Azure egress to your VPS provider", the marginal protection isn't worth the maintenance touch. The runner uses `StrictHostKeyChecking=accept-new`: first SSH per job accepts whatever DNS returns, subsequent SSH calls within the same job verify against it. Effectively per-job TOFU. If the threat model ever changes, dropping in a `compose/.known_hosts` is a single non-breaking PR.

### Why one version for stack + siteapp instead of release-please multi-package?

Two reasons. First, "what version is deployed" should be one unambiguous number an operator can read off `/api/public/server-info` and `git tag`. Second, the multi-package config is meaningfully more YAML for very little benefit: the siteapp is a leaf component of "the stack", not an independently versioned product, and image rebuilds with buildx cache are essentially free. The cost — image rebuilt on releases that don't touch siteapp source — is invisible.

### Why image rebuilds run unconditionally per release (rather than skipping when siteapp didn't change)

A conditional skip introduces ambiguity: "this release's image is the previous release's image, retagged." That breaks the invariant that the attestation at tag `vX.Y.Z` is the build that ran for `vX.Y.Z`. Cheaper to rebuild from cache than to reason about which image is authoritative.

### Why CI deploy doesn't manage the chisel roster

The roster grows over time, one device at a time, with per-device passwords generated locally by `task secrets:add-client`. Moving it into GH secrets would mean either one secret per device (operator chore for every add/remove) or one JSON blob secret (no diff visibility, easy to corrupt). Neither is better than the current laptop-managed flow. The cost is a known limitation (see below); the benefit is that adding a lab device remains a single laptop command and CI releases never accidentally regenerate auth that live clients depend on.

## Known limitations

- **Roster lives only on the operator's laptop and the VPS.** If the laptop is lost, the roster can be reconstructed by SSHing to the VPS and reading back `chisel/users.json` and `siteapp/clients.json`, then reassembling the `chisel_clients[]` section in a fresh `config.yaml`. Not automated. Worth being aware of; not worth solving until it becomes a real problem.
- **Single-VPS only.** Adding a staging environment would mean another `VPS_HOST`/`VPS_SSH_USER`/`VPS_SSH_KEY` triplet and a matrix on `release-build`. Out of scope here; the design doesn't preclude it.
- **Rate-limited Docker Hub pulls on CI runners.** The bats integration suites that build the fake-VPS container already skip cleanly when anonymous-pull is rate-limited. This is documented in the README; no CI-specific mitigation needed.

## Deferred

- **CodeQL / bandit** for siteapp Python. Low signal-to-noise on a small FastAPI service; trivially addable later.
- **Deploy notifications** to Slack/Telegram/Discord. No channel exists today; revisit if/when one is provisioned.
- **Weekly drift check** comparing `/api/public/server-info` to the latest GitHub Release tag. Useful but not load-bearing; add later if drift turns out to be a real problem.
- **PR preview image** for siteapp (push `pr-<n>` tag to GHCR). Defer until the operator actually `docker run`s preview builds.
- **Docs-portal footer version surface.** Reading from `/api/public/server-info` is sufficient for now.

## Implementation order

This list is descriptive, not the implementation plan (the plan lives in a separate document via the `writing-plans` skill).

1. Extract image pins / paths / numeric config into `compose/pins.yaml`; update `scripts/lib/config.sh` and `config.example.yaml`; verify `task deploy` still works locally.
2. Add `compose/siteapp/VERSION`; teach the laptop deploy path and `compose/siteapp/build.sh` to consume it; add `LAB_BRIDGE_VERSION` / `LAB_BRIDGE_GIT_SHA` build-args to siteapp's Dockerfile; extend `/api/public/server-info` and update the client-spec doc.
3. Refactor `scripts/deploy.sh` for `LDS_STACK_ONLY=1` and `LDS_REQUIRE_VAULT=1`. Update bats coverage.
4. Add `compose/config.ci.yaml.tmpl`.
5. Set up the GitHub App (rename, install, populate vars/secrets).
6. Land `.github/workflows/pr.yml`. Verify on a no-op PR.
7. Land `release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`. Apply branch protection.
8. Cut the first release; verify image push, attestation, deploy, `/api/public/server-info` version assertion.
9. Land `.github/workflows/ghcr-cleanup.yml` (dry-run). After one cycle, flip to live.
10. Land `renovate.json`; ensure the Renovate App is installed.
11. Delete the legacy `.github/workflows/siteapp-publish.yml`.
12. Add `task deploy:rollback`; test against the freshly-cut release.

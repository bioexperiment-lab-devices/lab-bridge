# CLAUDE.md — development flow rules

Project conventions established by the CI/CD overhaul (PR #4, release v0.1.0). All changes to `main` go through this flow; CI deploys to the VPS automatically on every release.

Design + plan docs:
- `docs/superpowers/specs/2026-05-12-cicd-design.md`
- `docs/superpowers/plans/2026-05-12-cicd.md`

---

## Branch workflow

- **`main` is protected.** No direct pushes. Required checks: `pr-title`, `verify`. Linear history. Squash-merge only.
- **PR titles follow Conventional Commits.** Types: `feat fix chore docs refactor test perf build ci revert`. Scope optional but encouraged (`feat(siteapp): …`, `fix(deploy): …`). The PR title becomes the squash-commit subject on `main` — that's what `release-please` scans for the next version bump.
- **"Branches up to date before merging" is OFF.** No forced rebase on concurrent merges; conflicts still block.
- **Force-push and branch deletion disabled on `main`** (admins included).

## Version & release flow

```
PR with conventional title → squash-merge to main → release-please opens release PR
                                                  → review + squash-merge release PR
                                                  → release-build builds GHCR image + deploys VPS
                                                  → /api/public/server-info reports new version
```

- `release-please` (`googleapis/release-please-action@v5`) is driven by `release-please-config.json` + `.release-please-manifest.json` at the repo root. App used: `bioexperiment-release-please` (org-installed, App ID + private key in org-level vars/secrets).
- The siteapp image tag IS the release tag. There is one number for "the stack."
- `compose/siteapp/VERSION` carries the current version with a `# x-release-please-version` annotation comment. **Do not strip the annotation** — `release-please` uses it to find the line to rewrite. Both `scripts/lib/render.sh` and `compose/siteapp/build.sh` parse VERSION with `awk 'NF { print $1; exit }'`, which ignores the comment.
- **GitHub Releases publish automatically** as tags `vX.Y.Z`. No release notes to write by hand — release-please builds them from conventional-commit subjects.

## Source-of-truth files

| Where | What | Editable by |
|---|---|---|
| `compose/pins.yaml` (tracked) | Image pins, paths, retention, ACME email, ports, `siteapp_image_repo` | PR (or Renovate) |
| `compose/siteapp/VERSION` (tracked) | Current siteapp semver — annotated, release-please-owned | release-please only |
| `compose/config.ci.yaml.tmpl` (tracked) | CI-side `config.yaml` template (envsubst placeholders) | PR |
| `config.yaml` (gitignored, laptop only) | Instance values + secrets + chisel roster | Operator laptop |
| GH variables (3) | `RELEASE_PLEASE_APP_ID`, `VPS_HOST`, `VPS_SSH_USER` | Operator via GH UI |
| GH secrets (6) | `RELEASE_PLEASE_APP_KEY`, `VPS_SSH_KEY`, `JUPYTER_PASSWORD_HASH`, `ADMIN_PASSWORD_HASH`, `GRAFANA_ADMIN_PASSWORD`, `AGENT_UPLOAD_TOKEN` | Operator via GH UI |
| `compose/grafana/admin_password` (gitignored) | Grafana admin password plaintext | `task secrets:set-grafana-password` |
| `compose/siteapp/agent_upload_token` (gitignored) | Agent upload bearer | `task secrets:rotate-agent-upload-token` |

If you change `compose/pins.yaml`, both laptop deploys AND CI deploys pick up the change at the next deploy. Don't put image pins in `config.yaml`.

## Two deploy paths

**Laptop full deploy** (operator-driven, includes roster):

```bash
task deploy
```

Renders templates from `config.yaml` + `compose/pins.yaml`, rsyncs everything (including `chisel/users.json` + `siteapp/clients.json`), restarts `caddy chisel siteapp`. Use for roster changes or local-only experiments.

**CI stack-only deploy** (release-triggered, excludes roster):

Fires automatically on release-please tag creation. Sets `LDS_STACK_ONLY=1 LDS_REQUIRE_VAULT=1`:
- Skips `render_chisel_users` and `render_siteapp_clients`.
- rsync excludes `chisel/users.json` + `siteapp/clients.json`.
- Drops `chisel` from the restart list (live tunnels preserved).
- Asserts `chisel_clients` is empty in the CI config (vault guard).

**Rollback**:

```bash
task deploy:rollback -- v0.1.0
```

Triggers `release-please.yml` via `workflow_dispatch` with `rollback_to=<tag>`. Skips release-please job and image build; just redeploys the existing GHCR image of that tag. CI runs SSH deploy — no operator SSH needed.

## How to do common things

### Bump an image pin (jupyter, chisel, loki, grafana, base images)

Edit `compose/pins.yaml`. Open a PR titled `chore(deps): bump jupyter to <tag>` (or use Renovate's auto-PR). `verify` job confirms `validate_config` still accepts the schema. Merge → release-please includes it in the next release → CI deploys.

### Bump siteapp dependencies

Edit `compose/siteapp/pyproject.toml` (and run `uv lock` locally to update `uv.lock`). PR titled `chore(siteapp): bump <dep> to <version>`. `verify` job's `pytest` confirms the change.

### Add a lab device (chisel client)

**Laptop only:**

```bash
task secrets:add-client -- <name> <reverse_port>
task deploy
```

Updates `config.yaml`'s `chisel_clients` array, renders new `chisel/users.json` + `siteapp/clients.json`, rsyncs them to VPS, restarts chisel. **CI never touches this surface** — adding a device is not a release-gated change.

### Rotate a secret

| Secret | How |
|---|---|
| Jupyter password | `task secrets:set-jupyter-password` on laptop → update `JUPYTER_PASSWORD_HASH` in GH secrets to match → `task deploy` |
| Admin (Caddy basic_auth) | `task secrets:set-admin-password` → update `ADMIN_PASSWORD_HASH` in GH secrets → `task deploy` |
| Grafana admin | `task secrets:set-grafana-password` → update `GRAFANA_ADMIN_PASSWORD` in GH secrets → `task deploy` |
| Agent upload token | `task secrets:rotate-agent-upload-token` → update `AGENT_UPLOAD_TOKEN` in GH secrets → `task deploy` (rotates server-side; CI clients must update their token) |
| VPS SSH key | Generate new key locally → add public key to VPS `~/.ssh/authorized_keys` → update `VPS_SSH_KEY` in GH secrets → revoke old key |

The pattern: laptop sets the value, then GH secret has to be kept in sync OR the next CI deploy will fail. There's no automatic sync — secrets are dual-managed.

### Add a field to `/api/public/server-info`

Additive fields are safe (Go client uses `json.Unmarshal` without `DisallowUnknownFields`). Document the addition in `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` in the same PR. **Breaking changes need a major-version bump and client coordination.**

### Verify what's deployed

```bash
curl -s "https://<vps-host>/api/public/server-info" | jq '{version, git_sha}'
```

Compare `version` against `gh release list --limit 1`. If they disagree, deploy is stuck — check `gh run list --workflow=release-please.yml --limit 3`.

### Verify GHCR provenance

```bash
gh attestation verify oci://ghcr.io/bioexperiment-lab-devices/lab-bridge-siteapp:<tag> --repo bioexperiment-lab-devices/lab-bridge
```

Exit 0 means the image was built by this repo's CI from the corresponding commit.

## CI gates on every PR (`pr.yml`)

| Job | Steps | Required? |
|---|---|---|
| `pr-title` | `amannn/action-semantic-pull-request@v6` | Yes |
| `verify` | shellcheck (`-x --severity=warning`), bats (most files), ruff check + format, pytest, siteapp docker build (no push) | Yes |

**bats coverage in CI**: all `tests/test_*.bats` EXCEPT `test_siteapp_*.bats` (the 4 siteapp integration files do a full fake-VPS deploy each — too slow for CI). **If you touch `compose/siteapp/` or any siteapp routing/auth/upload/safety code, run the siteapp bats locally before opening the PR:**

```bash
bats tests/test_siteapp_auth.bats tests/test_siteapp_routing.bats \
     tests/test_siteapp_safety.bats tests/test_siteapp_uploads.bats
```

Follow-up to consolidate these into one shared-setup file is filed.

## CI workflows in this repo

| File | Trigger | What it does |
|---|---|---|
| `.github/workflows/pr.yml` | PR open/sync/reopen/edit | `pr-title` + `verify` gates |
| `.github/workflows/release-please.yml` | push to main; manual `workflow_dispatch` with `rollback_to` | release-please opens/updates release PR; on release_created, builds GHCR image + Sigstore attestation + SSH-deploys stack-only + verifies version |
| `.github/workflows/ghcr-cleanup.yml` | Monthly cron (1st @ 06:00 UTC); manual | Prunes old `lab-bridge-siteapp` GHCR versions (keeps last 10). Currently `dry-run: true` — flip after first scheduled run looks sensible |

Renovate is configured via `renovate.json` (monthly, with a custom regex manager targeting `compose/pins.yaml`).

## What I should not do (rules to honor)

- **Don't push directly to `main`.** Branch protection rejects it. Even small docs changes go through a PR.
- **Don't merge with merge-commit or rebase-merge.** Squash-only. The release-please flow depends on it.
- **Don't put image pins or paths in `config.yaml`.** They live in `compose/pins.yaml`. `config.yaml` is for instance values + secrets + roster only.
- **Don't add a `chisel_clients[]` entry to `compose/config.ci.yaml.tmpl`.** It must stay `[]`; the vault guard fails the deploy if it's non-empty.
- **Don't manually edit `compose/siteapp/VERSION`** unless you're seeding it for the first time. release-please owns it. Stripping the `# x-release-please-version` annotation breaks the next release.
- **Don't manually push images to `ghcr.io/.../lab-bridge-siteapp` with a release tag.** CI is the only path; manual pushes confuse `release-please` and the Sigstore attestation won't match.
- **Don't bump versions by hand.** Open a PR with conventional commits; release-please does the bump.
- **Don't run `task deploy` from CI** (the workflow already does this via `scripts/deploy.sh` with `LDS_STACK_ONLY=1`).
- **Don't run `task secrets:add-client` from CI.** Roster ops are laptop-only.
- **Don't change `pr.yml`'s required checks** without also updating branch protection's required-checks list. They must agree, otherwise PRs can't merge.

## Spec / plan workflow for non-trivial changes

Multi-step features land via `docs/superpowers/specs/` (design) and `docs/superpowers/plans/` (implementation plan). Use the brainstorming → writing-plans → subagent-driven-development flow for anything that touches more than 2-3 files. The CI/CD overhaul is the canonical example: spec dated 2026-05-12, plan dated 2026-05-12, 17 tasks executed via subagents with two-stage review (spec + code quality).

## Operator-laptop dependencies

The laptop needs (per README "Prerequisites"):
- [task](https://taskfile.dev), [yq v4](https://github.com/mikefarah/yq) (mikefarah, not the Python one), `openssl`, `ssh`, `rsync`
- For tests: `bats-core`, Docker (the fake-VPS integration suite)
- `gh` CLI authenticated for `task deploy:rollback`

The CI runner installs its own copies of these on every `verify` / `release-build` job.

## Where to look for stuff

- Operator entrypoints: `Taskfile.yml` (`task --list` for menu)
- Stack templates: `compose/`
- Deploy logic: `scripts/deploy.sh`, `scripts/provision.sh`, `scripts/lib/*.sh`
- Siteapp source: `compose/siteapp/app/`
- Tests: `tests/*.bats`, `compose/siteapp/tests/`
- CI: `.github/workflows/`
- Design history: `docs/superpowers/specs/`
- Implementation plans: `docs/superpowers/plans/`

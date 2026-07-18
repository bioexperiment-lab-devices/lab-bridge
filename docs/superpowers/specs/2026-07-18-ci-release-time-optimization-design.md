# CI & release-time optimization for external-image bumps — design

Date: 2026-07-18
Status: approved

## Problem

Bumping a single external image (Experiment Studio 0.6.0 → 0.7.0, measured
2026-07-18) costs **~55 minutes of wall-clock across 3 PRs**:

| Phase | What ran | Duration |
| --- | --- | --- |
| Pin PR #176 (`chore:`, edits `compose/pins.yaml`) | full fake-VPS bats matrix | ~21 min |
| Ship PR #177 (`feat:`, empty commit) | bats fast-skipped (no files changed) | ~40 s |
| Release PR #178 (`release-please--*`) | full fake-VPS bats matrix **again** | ~24 min |
| Deploy (on `v0.25.0` tag) | stack-only deploy + verify | ~4 min |

Three defects drive that cost:

1. **The full fake-VPS matrix runs twice.** `pins.yaml` lives under
   `compose/**`, which trips `pr-platform`'s paths-filter; the release PR then
   re-runs the same suite (release-please refs deliberately bypass the filter)
   against a functionally identical tree ~5 minutes later.
2. **Fake-VPS bringup is a ~14 min floor paid by every heavy cell.**
   `preload_fake_vps_images` (`tests/integration/helpers.bash:118`) side-loads
   the entire stack — including the multi-GB `scipy-notebook` — into the DinD
   for every suite, whether or not that suite asserts anything about those
   services. A `free-disk-space` step runs per heavy cell on top. This is why
   even "smoke" cells take ~15 min, and why the whole gate is bringup-bound
   rather than test-bound.
3. **The `chore:`-pin + empty-`feat:`-ship two-step strands pins.**
   `release-please-config.json` marks `chore` hidden, so a pin bump never cuts
   a release; `release-build` only runs on
   `needs.release-please.outputs.released == 'true'`. A pin therefore sits on
   `main` undeployed until some unrelated `feat`/`fix` ships it. This is not
   theoretical: while the 0.7.0 bump was in flight, #179 (`chore:` pin 0.8.0)
   merged and is stranded on `main` — deployed preprod still runs 0.7.0.

## Decisions (agreed in brainstorming)

| Decision | Choice |
| --- | --- |
| Pin-PR gate for image-only bumps | **Skip the fake-VPS matrix entirely.** Keep the no-fake-VPS `cheap` tier (~40 s) so typos/bad renders are still caught. The release PR remains the full pre-deploy gate. |
| How CI detects "image-only" | **Split external image pins into `compose/images.yaml`** so paths-filter separates image bumps from infra changes cleanly. Rejected an in-workflow diff heuristic (fragile bash parsing of `*_image:` lines). |
| Release trigger for a bump | **One `feat:` PR** created by `task images:bump`. Renovate keeps emitting grouped `chore` PRs (no unattended 6am auto-deploy); `task images:ship` cuts the release for those. |
| Bringup reduction | **Per-suite stack trimming via the existing `disabled_services` mechanism** plus profile-driven preload. |
| Long-pole handling | **Extract no-bringup tests** from `test_deploy.bats`/`test_ops.bats` into the `cheap` tier. Explicitly *not* gratuitous cell-splitting — every new cell re-pays bringup. |

## A. `compose/images.yaml` split + reduced pin-PR gate

### A1. File split

New tracked file `compose/images.yaml` holds exactly the nine Renovate-tracked
external image references:

```yaml
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
loki_image: grafana/loki:3.2.1
grafana_image: grafana/grafana:11.3.0
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.8.0
authelia_image: authelia/authelia:4.38.10
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: ghcr.io/google/cadvisor:v0.57.0
```

`compose/pins.yaml` keeps everything release-tied or infrastructural: the
`*_image_repo` keys (whose tag comes from the root `VERSION`), `chisel_listen_port`,
`loki_retention_days`, `prometheus_retention_days`, `acme_email`, `remote_root`,
`notebooks_path`, `ssh_port`.

**Invariant preserved:** the `*_image_repo` keys must NOT move. They are part of
the unified `VERSION` stream (`"${siteapp_image_repo}:$(cat VERSION)"`), so a
change to them is a platform change and must keep triggering the full suite.
Only images released *outside* this repo move to `images.yaml`.

The explanatory comments currently attached to moved keys (studio's `>= 0.3.0`
sub-path caveat, cadvisor's `>= v0.54.0` overlayfs caveat, the Renovate note)
move with them — they are load-bearing operational knowledge.

### A2. Consumers to update

| File | Change |
| --- | --- |
| `scripts/lib/config.sh` | Add `_default_images_file()` + `LDS_IMAGES_FILE` override (mirrors the existing `LDS_PINS_FILE` pattern). Move the nine keys out of `_REQUIRED_PINS_FIELDS` into a new `_REQUIRED_IMAGES_FIELDS`. `validate_config` validates both files and reports a missing images file with the same clear error style. `load_config` exports the same variable names as today, so downstream consumers are unchanged. |
| `scripts/lib/render.sh` | No logic change — it consumes exported variables, not file paths. Verify no direct `pins.yaml` reads remain. |
| `scripts/secrets.sh` | Audit for direct pins reads; repoint any image-key read. |
| `tests/integration/fixtures/` | Split `valid_pins.yaml` → add `valid_images.yaml`; update fixture loaders/`LDS_IMAGES_FILE` wiring in `helpers.bash`. |
| `renovate.json` | customManager `fileMatch` `^compose/pins\.yaml$` → `^compose/images\.yaml$`. **Required** — otherwise Renovate silently stops tracking every external image. |
| `compose/config.ci.yaml.tmpl`, `compose/docker-compose.yml.tmpl` | Verify placeholder substitution still resolves (they consume rendered values, not the pins file directly). |
| `docs/adding-a-service.md`, `CLAUDE.md` | Update the "Config split" rule: image pins → `images.yaml`, infra/ports/retention → `pins.yaml`. |

### A3. `pr-platform.yml` restructure

Split the single `bats` job into two, both feeding the existing `platform`
aggregator:

- **`bats-cheap`** — the current `cheap` suite (no fake-VPS, ~40 s). Runs when
  **any** of the watched paths change, `images.yaml` included.
- **`bats-heavy`** — the fake-VPS matrix. Runs only when **non-image** paths
  change, or on a release-please head ref.

paths-filter gains a negation so image-only edits don't trip the heavy gate:

```yaml
filters: |
  heavy:
    - 'compose/**'
    - '!compose/images.yaml'
    - 'scripts/**'
    - 'tests/integration/**'
    - 'config.example.yaml'
    - 'Taskfile.yml'
    - '.github/workflows/pr-platform.yml'
  images:
    - 'compose/images.yaml'
  shell:
    - 'scripts/**/*.sh'
```

`should-run` keeps the release-please bypass, forcing `heavy=true` for
`release-please--*` head refs so the release PR remains the full pre-deploy
integration gate. `bats-cheap` runs when `heavy || images`.

**Branch protection is unchanged.** `platform` remains the single required
check; it already treats `skipped` dependents as passing, and gains
`bats-cheap`/`bats-heavy` in its `needs` list.

**Net effect:** an `images.yaml`-only PR runs `pr-title` + `bats-cheap` (~40 s)
and skips the entire fake-VPS matrix.

## B. One-PR bumps: `task images:bump` / `task images:ship`

### B1. `task images:bump -- <service> <version>`

Backed by a new `scripts/images.sh` (subcommand style, mirroring `scripts/secrets.sh` and `scripts/users.sh`):

1. Validate `<service>` against the known external-image keys in `images.yaml`
   (reject unknown names with the allowed list, mirroring `disabled_services`
   validation style).
2. Verify the target image reference actually exists and is anonymously
   pullable (registry manifest check) **before** touching git — a bad tag must
   fail locally, not in CI.
3. Rewrite the `<service>_image` tag in `compose/images.yaml` via `yq`.
4. Create branch `chore/<service>-<version>`, commit as
   **`feat: bump <service> image to <version>`** — a releasable type, so
   release-please cuts the release and `release-build` deploys.
5. Push and open the PR.

One atomic PR replaces the chore-pin + empty-feat-ship dance and removes the
stranding failure mode.

**Commit-type rationale:** `feat` yields a minor bump, matching the precedent
this flow already set (0.24.0 → 0.25.0 for the studio 0.7.0 ship). Keeping the
type releasable is the whole point — a `chore` here would recreate the bug.

### B2. Renovate unchanged; `task images:ship` for its bumps

Renovate keeps opening grouped `chore` PRs against `images.yaml`. They land
without cutting a release (hidden type) and without tripping the heavy gate
(A3) — cheap to merge, and deliberately **not** an unattended production
deploy.

`task images:ship` creates the empty `feat: ship pinned images to the stack`
commit + PR that cuts the release for whatever `images.yaml` currently holds.
This is today's manual pattern reduced to one command, and it is the
supported way to deploy Renovate-landed bumps.

## C. Lower the bringup floor

### C1. Per-suite stack trimming

Each heavy suite deploys only the services it asserts, reusing the
`disabled_services` mechanism from the 2026-07-17 service-selection work rather
than inventing a parallel switch. The fake-VPS fixture config gains a
per-suite `disabled_services` value, so suites that never touch
jupyter/studio/monitoring skip both the multi-GB preload **and** those
containers' startup and healthchecks.

`preload_fake_vps_images` becomes profile-driven: it takes the set of images
the active suite needs (derived from the suite's effective service list)
instead of the hardcoded seven-image list. The matrix passes the suite name
through an env var already available as `matrix.suite`.

Two correctness notes:

- `compose_images_available` (the skip guard at `helpers.bash:141`) must be
  trimmed to the same profile, or suites will skip on images they no longer use.
- Both lists hardcode their image set (including `experiment-studio:0.3.0`).
  That tag currently *matches* `fixtures/valid_pins.yaml`, which is what the
  fake-VPS actually deploys, so preloading works today — but the set is
  duplicated in three places and must be hand-synced. Profiles must derive the
  image set from the test fixture rather than hardcode it, so a fixture bump
  can never silently disable preloading.

### C2. Extract no-bringup tests

Several cases in the long-pole files assert pre-flight validation and never
need a running stack — e.g. `test_deploy.bats`: "rejects config with invalid
hash before touching VPS", "fails fast when grafana admin_password is missing",
"fails fast when agent_upload_token is missing", "fails fast when authelia
users_database.yml is missing / has zero users". These move into the
no-fake-VPS `cheap` tier, removing bringup cost from tests that were paying it
for nothing.

Because matrix cells select whole files, the extraction is file-level: the
pre-flight cases move into new `tests/integration/test_deploy_preflight.bats`
(and `test_ops_preflight.bats` if `test_ops.bats` yields any), which are added
to the `cheap` suite's file list. This mirrors the existing convention — the
`cheap` suite already carries validation-only files such as
`test_deploy_stack_only.bats` and `test_service_selection_render.bats`. The
extracted files must not source the fake-VPS bringup helpers.

Tests that genuinely exercise a live stack (e.g. "loki and grafana come up
healthy on the fake VPS", the `ops` command surface) stay in the heavy tier.

**Deliberate non-goal:** splitting the remaining stack-dependent tests into
more matrix cells. Once bringup is trimmed and no-bringup tests are extracted,
each additional cell re-pays the (reduced) bringup, so more cells would add
wall-clock rather than remove it.

## Testing strategy

The laptop has no Docker, so all fake-VPS behaviour is verified in CI on the
implementation PR itself. Because this work touches `compose/`, `scripts/`,
`tests/integration/` and the workflow, it trips the heavy gate and exercises the
new structure end-to-end.

| Claim | How it is verified |
| --- | --- |
| Image-only PR skips the heavy matrix | Follow-up PR touching only `compose/images.yaml`; assert `bats-heavy` is skipped and `platform` still reports success |
| Cheap tier still catches a bad image | Deliberately break an image ref in a scratch commit; `bats-cheap` (render/config) must fail |
| Release PR still runs the full suite | The release PR for this work must show every heavy cell running (release-please bypass intact) |
| Config split is behaviour-preserving | Existing `test_config.bats` / `test_render.bats` extended for the two-file load, `LDS_IMAGES_FILE` override, and a missing-images-file error |
| Renovate still tracks images | `renovate.json` customManager regex validated against the new path |
| `images:bump` works | Unit-level bats coverage for service-name validation and tag rewriting; the manifest check exercised against a known-good and known-bad tag |
| Bringup actually got faster | Compare per-cell wall-clock on this PR against the 2026-07-18 baseline recorded above |

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Renovate silently stops tracking images after the split | `renovate.json` update is a required, called-out step; verified by regex check against the new path |
| A broken image reaches `main` because the pin PR no longer runs the heavy suite | The release PR runs the full suite before any deploy; `bats-cheap` still validates render/config on every image PR |
| Per-suite `disabled_services` hides a real cross-service regression | Only suites that assert nothing about a service may disable it; routing/navbar/auth smoke suites keep the full stack |
| Two-file config breaks an operator's laptop deploy | `validate_config` fails loudly with the path it expected; `LDS_IMAGES_FILE` provides an override; `config.sh` is the single load point |
| `feat`-typed bumps make releases noisier | Intended — every external bump becomes a visible, changelog-listed release, which is what makes the deploy happen at all |

## Expected outcome

External image bump: `task images:bump` → **one** PR → `bats-cheap` (~40 s) →
merge → release PR (full suite, each cell faster after C) → deploy.

**~55 min / 3 PRs → ~12–15 min / 1 PR + release.** The C work additionally
speeds up every platform PR, not just image bumps.

## Out of scope

- The stranded 0.8.0 studio pin (explicitly deferred by the operator; it will
  ride the next release or a `task images:ship` run).
- Changing the release-please component model or the single-`VERSION` stream.
- Reworking `pr-<service>.yml` workflows — they already fast-skip correctly.

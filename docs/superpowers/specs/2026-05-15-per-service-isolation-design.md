# Per-service isolation — design

**Status:** Draft (brainstormed 2026-05-15)
**Author:** khamitovdr
**Related:** `docs/superpowers/specs/2026-05-12-cicd-design.md` (the CI/CD foundation this builds on)

## Motivation

The repo has grown into a "Swiss-knife" lab platform: today two services (siteapp, flasher) plus the platform/deploy layer (compose, scripts, integration tests), with more services expected. The current single-service CI shape doesn't scale to that growth:

1. **Shared version, shared release cadence.** Both apps are pinned to one version (`0.3.1`) by a single release-please component. A siteapp-only fix bumps flasher too, conflating changelogs and creating noise.
2. **One serial `verify` job.** Every PR runs every step on the same runner; per-service work doesn't parallelize.
3. **Bats fake-VPS integration tests are heavy.** Each `test_siteapp_*.bats` does a full provision + 6-image deploy in `setup_file` (~7 min each). Today's CI runtime is ~17 min and would grow to ~45 min if all 4 ran.
4. **Release-PR CI burns time.** Today's release-please PRs re-run the full bats suite even though the actual VPS deploy on merge is the real integration test.
5. **No granular test ownership.** "Is siteapp's path-traversal handling correct?" is currently asked by spinning up the entire stack; the question has nothing to do with Caddy or chisel.

The constraint set surfaced during brainstorming:

- Independent versions and release cadence per service.
- Per-service CI that runs only on relevant changes, in parallel.
- A *thin* integration layer that proves "everything works together," not per-service behavior.
- Release-PR CI opt-in (label-gated), so platform-release PRs don't burn 17 minutes by default.

## Approach decision

Three alternatives were considered:

- **A — Monorepo with per-service isolation.** Restructure source tree + CI + release-please within this repo.
- **B — Polyrepo.** Extract siteapp, flasher, and future services to their own repos; this repo becomes platform-only.
- **C — Hybrid.** Apps in one repo, platform in another.

**Decision: Approach A.** Every stated pain point is solved by CI design and release-please configuration — no repo-boundary changes needed. Polyrepo would add coordination cost (multi-repo PRs for cross-service changes, published packages for shared code like `clients.py`, Renovate/dispatch glue between platform and apps repos) without buying CI parallelism that monorepo can't deliver. The `lab_devices_client` boundary is already polyrepo where it has to be (it lives on operator machines); don't expand polyrepo where there's no forcing function.

The hybrid (C) was rejected because it pays B's coordination cost without isolating per-service CI any better than A.

The user's earlier framing ("split siteapp into a thin docs/orchestration layer and isolate serial-communication logic in a new repo") is *out of scope* for this spec. Siteapp has no serial logic today (flasher does). Splitting siteapp internally is a code-organization question that should stand on its own merits — not coupled to the repo-restructure decision.

## Section 1 — Repo layout

### Target structure

```
services/
  siteapp/        # was compose/siteapp/
    app/  tests/  Dockerfile  pyproject.toml  uv.lock
    VERSION       # release-please component "siteapp"
  flasher/        # was compose/flasher/
    app/  web/  tests/  Dockerfile  pyproject.toml  uv.lock
    VERSION       # release-please component "flasher"
compose/          # platform configs only
  Caddyfile.tmpl  docker-compose.yml.tmpl  chisel-users.json.tmpl
  config.ci.yaml.tmpl  pins.yaml
  grafana/  loki/
  VERSION         # release-please component "platform"
scripts/          # unchanged: provision, deploy, secrets, ops
tests/
  integration/    # slimmed bats suite
.github/workflows/
  pr-title.yml
  pr-siteapp.yml
  pr-flasher.yml
  pr-platform.yml
  release-please.yml
  ghcr-cleanup.yml
```

### Rationale

- `compose/siteapp/` and `compose/flasher/` are misnamed — they're services, not compose configs. Co-locating with templates becomes actively confusing when a third service lands.
- Per-service tests stay co-located (`services/<name>/tests/`) so a service owns its tests; the per-service workflow runs them; no cross-references back into the top-level `tests/` dir.
- `tests/integration/` holds *only* the trimmed fake-VPS suite — "stack boots, routes wire up, `/admin` is 401, `server-info` reports the expected version."
- **Runtime layout on the VPS does not change.** `compose/siteapp/` still exists at runtime — it's where deploy.sh stages `agent_upload_token` and `clients.json`. The rename is source-tree only; no migration on deployed instances.

### Files touched by the rename

- `scripts/lib/render.sh` — `compose/<svc>/VERSION` → `services/<svc>/VERSION` paths.
- `Taskfile.yml` — `compose/<svc>/build.sh` → `services/<svc>/build.sh`.
- `release-please-config.json` — `extra-files` paths (replaced entirely in Section 2 anyway).
- `.github/workflows/pr.yml` — superseded by per-service workflows in Section 3.
- `.github/workflows/release-please.yml` — `context: compose/<svc>` → `context: services/<svc>`.
- `renovate.json` — any path regexes pointing at `compose/<svc>/`.

`scripts/deploy.sh`, `scripts/lib/render.sh`'s runtime template logic, and `scripts/secrets.sh` reference *runtime* paths (`$REPO_ROOT/compose/grafana/...`, `$REPO_ROOT/compose/siteapp/agent_upload_token`) — those stay put. Operator-state secrets live in `compose/<svc>/` on the laptop, written by `task secrets:*`, and are *not* moved.

## Section 2 — release-please: multi-component manifest

### Today

Single component `lab-bridge` at `.` with `release-type: simple`, version `0.3.1`. `extra-files` synchronises `compose/siteapp/VERSION` and `compose/flasher/VERSION` to the same number on every release. Tag format `v0.3.1`. One CHANGELOG.md at root.

### Target

Three components — one per release surface — with path-based commit routing.

```json
// release-please-config.json
{
  "packages": {
    "services/siteapp": {
      "package-name": "siteapp",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [{ "type": "generic", "path": "VERSION" }]
    },
    "services/flasher": {
      "package-name": "flasher",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [{ "type": "generic", "path": "VERSION" }]
    },
    ".": {
      "package-name": "platform",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [{ "type": "generic", "path": "compose/VERSION" }],
      "exclude-paths": ["services/siteapp", "services/flasher"]
    }
  },
  "changelog-sections": [ /* unchanged */ ]
}
```

```json
// .release-please-manifest.json
{
  "services/siteapp": "0.3.1",
  "services/flasher": "0.3.1",
  ".": "0.3.1"
}
```

### Resulting artefacts

- Tags: `siteapp-v0.3.2`, `flasher-v0.4.0`, `platform-v0.5.0` — independent.
- Changelogs: `services/siteapp/CHANGELOG.md`, `services/flasher/CHANGELOG.md`, `CHANGELOG.md` (root, platform only — past entries carry over).
- `compose/VERSION` — new file, anchor for the platform component. Pure metadata; nothing at deploy time reads it.

### Commit routing

release-please routes commits to components by **paths touched**, not Conventional Commits scope:

| Commit touches | Bumps |
|---|---|
| `services/siteapp/...` | siteapp |
| `services/flasher/...` | flasher |
| `compose/...`, `scripts/...`, `tests/integration/...` | platform |
| `services/siteapp/...` + `compose/...` | siteapp + platform (two release PRs) |
| `docs/...`, `README.md`, `CLAUDE.md` | platform (hidden under `chore`/`docs` — no release) |

### release-build job decomposition

Three sibling jobs in `release-please.yml`, each gated on whether *its* component was released this run:

```yaml
release-build-siteapp:
  needs: release-please
  if: needs.release-please.outputs['services/siteapp--release_created'] == 'true'
  # build & push ghcr.io/.../lab-bridge-siteapp:${siteapp_version}, attest, deploy

release-build-flasher:
  needs: release-please
  if: needs.release-please.outputs['services/flasher--release_created'] == 'true'
  # same shape

release-platform:
  needs: release-please
  if: needs.release-please.outputs['.--release_created'] == 'true'
  # no image build; deploy with currently pinned image tags
```

A siteapp-only release → only siteapp's image gets built, only its deploy runs. A multi-component release → multiple release PRs land independently, each triggering its own deploy. Deploys are idempotent (`docker compose up -d` only restarts changed containers), so the order doesn't matter.

### Healthcheck change

Today's `release-please.yml` verifies deployment by asserting `server-info.version == ${released_version}`. After the split, this assertion must know *which* component released this run:

- **siteapp release** — assert `server-info.version` matches the new siteapp version (siteapp is the service exposing `/api/public/server-info`, so this stays meaningful).
- **flasher release** — siteapp's `server-info` doesn't report flasher's version. Either: (a) add `flasher_version` to `server-info` and assert it; or (b) curl flasher's own `/healthz` or a new `/flash/version` endpoint. Option (a) keeps the agent contract additive and the healthcheck shape uniform.
- **platform release** — no image version bump. Verify deploy succeeded by asserting `server-info` is reachable and `200` (existing behavior in `deploy.sh` already does this via its own healthcheck loop). Skip the version-equality assertion.

Implementation deferred to the plan stage; the data already exists (`LAB_BRIDGE_VERSION` build-arg flows into both images) — just needs plumbing through `server-info` if option (a) is chosen.

### Migration mechanic

1. Add `services/<svc>/VERSION` files at `0.3.1` (mechanical move from `compose/<svc>/VERSION`).
2. Add `compose/VERSION` at `0.3.1`.
3. Replace `release-please-config.json` and `.release-please-manifest.json`.
4. Create empty `services/siteapp/CHANGELOG.md` and `services/flasher/CHANGELOG.md`.
5. Root `CHANGELOG.md` stays — it becomes the platform changelog.

All three start at `0.3.1` for continuity. They diverge naturally on next release.

## Section 3 — CI workflow decomposition

### Workflow file list

| File | Triggers on | Owns |
|---|---|---|
| `pr-title.yml` | every PR (unchanged) | Semantic-PR title check |
| `pr-siteapp.yml` | every PR | siteapp: ruff, pytest, image build, service e2e |
| `pr-flasher.yml` | every PR | flasher: ruff, pytest, SPA tsc+build, image build, service e2e |
| `pr-platform.yml` | every PR | shellcheck, slim fake-VPS bats; label gate for release PRs |
| `release-please.yml` | push to main | release-please + per-component build/deploy (Section 2) |
| `ghcr-cleanup.yml` | scheduled | unchanged |

### Always-trigger discipline

Each per-service workflow **always triggers on `pull_request`** (no workflow-level `paths:` filter) and uses `dorny/paths-filter@v3` *inside* to gate steps. A docs-only PR runs all three workflows but each one's job exits in <30s with success.

Rationale: GitHub branch protection requires a check to **succeed**, not just **not run**. A workflow gated by `paths:` at workflow level isn't triggered when paths don't match, and the required check is treated as missing — blocking merge. Always-trigger + internal step gating preserves "docs-only PR is fast" AND "required checks always report."

### `pr-siteapp.yml` skeleton

```yaml
name: pr-siteapp
on:
  pull_request:
    types: [opened, synchronize, reopened]
concurrency:
  group: pr-siteapp-${{ github.event.pull_request.number }}
  cancel-in-progress: true
permissions: { contents: read, pull-requests: read }
jobs:
  siteapp:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - '.github/workflows/pr-siteapp.yml'
      - if: steps.changed.outputs.src == 'true'
        uses: actions/setup-python@v5
        with: { python-version-file: services/siteapp/.python-version, cache: pip }
      - name: install uv
        if: steps.changed.outputs.src == 'true'
        run: pip install uv
      - name: deps
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv sync --frozen
      - name: lint
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv run ruff check app tests && uv run ruff format --check app tests
      - name: unit tests
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        run: uv run pytest -v tests/  # excludes tests/e2e/
      - if: steps.changed.outputs.src == 'true'
        uses: docker/setup-buildx-action@v3
      - name: image build (no push)
        if: steps.changed.outputs.src == 'true'
        uses: docker/build-push-action@v6
        with:
          context: services/siteapp
          platforms: linux/amd64
          push: false
          load: true
          tags: lab-bridge-siteapp:pr-${{ github.event.pull_request.number }}
      - name: service e2e
        if: steps.changed.outputs.src == 'true'
        working-directory: services/siteapp
        env:
          SITEAPP_TEST_IMAGE: lab-bridge-siteapp:pr-${{ github.event.pull_request.number }}
        run: uv run pytest -v tests/e2e/
```

`pr-flasher.yml` is the same shape with Node setup + `npm ci` + `tsc --noEmit` + `npm run build` + flasher e2e (which spins up flasher + stub-serialhop via the compose file in `services/flasher/tests/e2e/`).

### `pr-platform.yml` (label-gated for release PRs)

```yaml
name: pr-platform
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled]
concurrency:
  group: pr-platform-${{ github.event.pull_request.number }}
  cancel-in-progress: true
permissions: { contents: read, pull-requests: read }
jobs:
  platform:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'compose/**'
              - 'scripts/**'
              - 'tests/integration/**'
              - 'config.example.yaml'
              - 'Taskfile.yml'
              - '.github/workflows/pr-platform.yml'
            shell:
              - 'scripts/**/*.sh'
      - id: gate
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            if ${{ contains(github.event.pull_request.labels.*.name, 'run-integration') }}; then
              echo "run=true" >> "$GITHUB_OUTPUT"
            else
              echo "run=false" >> "$GITHUB_OUTPUT"
              echo "::notice::release-please PR — bats integration skipped. Apply 'run-integration' to opt in."
            fi
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi
      - name: shellcheck
        if: steps.gate.outputs.run == 'true' && steps.changed.outputs.shell == 'true'
        run: |
          sudo apt-get update && sudo apt-get install -y shellcheck
          shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh
      - name: install Task + yq + bats
        if: steps.gate.outputs.run == 'true'
        # ... existing installation logic from pr.yml ...
      - name: bats integration
        if: steps.gate.outputs.run == 'true'
        run: bats tests/integration/
```

### Behavior matrix

| PR type | siteapp | flasher | platform |
|---|---|---|---|
| docs-only | skip (<30s) | skip (<30s) | skip (<30s) |
| siteapp change | run full | skip | skip |
| flasher change | skip | run full | skip |
| compose/scripts change | skip | skip | run full |
| release-please PR (no label) | skip | skip | skip-with-notice |
| release-please PR + `run-integration` label | skip | skip | run full |

The "release-please PR with no label" case is the explicit CI-time savings: the *real* integration is the actual VPS deploy on merge (with `verify deployed version` healthcheck in `release-please.yml`). Fake-VPS bats is belt-and-suspenders insurance — opt in via label when desired.

### Concurrency

Per-workflow concurrency groups (`pr-siteapp-${PR}`, `pr-flasher-${PR}`, `pr-platform-${PR}`). A force-push to a PR cancels only that PR's in-flight runs of each workflow, no cross-workflow interference.

### Branch protection — required checks

After the migration:

- **Remove:** `verify`
- **Add:** `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`
- **Keep:** `pr-title / Semantic Pull Request`

This is a manual GitHub UI step taken by the operator between PR 1 and PR 2 (see Section 5). To avoid a merge-blocking gap during PR 1's own CI, `pr.yml` is reduced to a stub `verify` job that does nothing — preserving the existing required check until branch protection is updated.

### Renovate

`renovate.json` currently watches `compose/pins.yaml` and `compose/<svc>/VERSION`. After the rename it watches `services/<svc>/VERSION`. Any custom `regexManagers` patterns referencing the old paths need updating in PR 1.

## Section 4 — Test layer redesign

### Three layers

| Layer | Location | What it proves | Cost |
|---|---|---|---|
| Unit | `services/<name>/tests/test_*.py` | Internal logic of a service | seconds, no containers |
| Service e2e | `services/<name>/tests/e2e/test_*.py` | Service container behaves correctly via HTTP, with fakes for upstream deps | ~30s–1min per service |
| Platform integration | `tests/integration/test_*.bats` | Real stack wires up correctly; deploy works; ops scripts work | ~7min for one fake-VPS bring-up |

Each layer answers a different question:

- **Unit** — "is this function correct?"
- **Service e2e** — "is this service correct end-to-end, on its own?"
- **Platform integration** — "do all services work together when deployed?"

The bats fake-VPS layer today conflates layers 2 and 3 — it spins up the whole stack to assert siteapp-only behavior. The redesign moves layer-2 questions to per-service e2e and keeps layer 3 *thin*.

### Per-service e2e harness

```
services/siteapp/tests/
  test_*.py                   # unit (today's tests, path-only move)
  e2e/
    conftest.py               # session fixture: docker compose up siteapp
    compose.yaml              # single-service compose for the harness
    fixtures/
      clients.json
      agent_upload_token
    test_server_info.py       # GET /api/public/server-info → 200, schema
    test_health.py            # GET /api/public/health → 200 (chisel stub)
    test_public_clients.py    # auth matrix against test roster
    test_admin_upload.py      # token gate + atomic rename + meta.json
    test_safety.py            # path traversal, HTML escape
```

```python
# conftest.py
@pytest.fixture(scope="session")
def siteapp_url():
    subprocess.check_call(
        ["docker", "compose", "-f", "tests/e2e/compose.yaml", "up", "-d", "--wait"]
    )
    yield "http://localhost:8001"
    subprocess.check_call(
        ["docker", "compose", "-f", "tests/e2e/compose.yaml", "down", "-v"]
    )
```

```yaml
# services/siteapp/tests/e2e/compose.yaml
services:
  siteapp:
    image: ${SITEAPP_TEST_IMAGE:-lab-bridge-siteapp:local}
    ports: ["8001:8000"]
    environment:
      LAB_BRIDGE_VERSION: "test"
      SITEAPP_CHISEL_LISTEN_PORT: "7000"
    volumes:
      - ./fixtures:/data:ro
```

**Why pytest, not bats**: same runner as unit tests; nicer assertions; fixtures share between unit and e2e if helpful; team already knows pytest. Bats stays for *platform* integration where it's already proven.

**No Caddy, no chisel, no Loki, no Jupyter** in the harness. The service is poked directly on its listen port. If a test needs upstream behavior, it's stubbed with a python `httpx` mock or a tiny `responses` server.

**Local execution**: `cd services/siteapp && uv run pytest tests/e2e/` after `docker build .`. Same DX as unit tests.

### Flasher e2e

Same shape, plus a **stub SerialHop**: a small FastAPI app under `services/flasher/tests/e2e/stub_serialhop/` that responds to `/flash/{port}` with canned outcomes. Flasher's `serialhop.py` HTTP client is pointed at the stub via env var in the e2e compose. The whole proxy path (auth, request validation, response shaping, job tracking) is exercised end-to-end without real hardware.

```
services/flasher/tests/e2e/
  conftest.py
  compose.yaml              # two services: flasher + stub-serialhop
  stub_serialhop/           # tiny FastAPI app, canned responses
    main.py
    Dockerfile
  test_auth.py              # bearer-token matrix
  test_flash_success.py     # happy path against stub
  test_flash_rolled_back.py # stub returns rolled-back outcome
  test_spa.py               # SPA index served at /flash/
```

### Platform integration (slimmed)

`tests/*.bats` → `tests/integration/*.bats`. Pruned to:

**Keep:**
- `test_common.bats`, `test_crypto.bats`, `test_config.bats`, `test_render.bats`, `test_secrets.bats`, `test_grafana_provisioning.bats`, `test_deploy_stack_only.bats` — pure logic, no fake-VPS.
- `test_provision.bats` — fake-VPS but lean (no full stack deploy).
- `test_deploy.bats` — canonical "deploy.sh succeeds end-to-end."
- `test_ops.bats` — `ops.sh` against a real running stack.

**Replace four with one consolidated routes-smoke (`tests/integration/test_routes_smoke.bats`):**
- Single `setup_file` does one fake-VPS bring-up.
- Asserts only what can't be asserted in a per-service harness: Caddy's full route map (`/docs/`, `/download/`, `/admin/`, `/flash/`, `/api/public/...`, `/_static/`, `/grafana/`, everything else → Jupyter); basic_auth gate at the Caddy edge for `/admin/` and `/flash/`; trailing-slash redirects.
- ~10–15 curl assertions sharing one stack bring-up. Target: ~8 min total.
- **Routing assertions only.** Behavior assertions (HTML escape, path traversal, upload semantics, token validation) move entirely to siteapp e2e.

### Time budget target

| Workflow | Trigger | Target wall-clock |
|---|---|---|
| `pr-siteapp.yml` | siteapp source change | <5 min |
| `pr-flasher.yml` | flasher source change | <7 min |
| `pr-platform.yml` | platform paths or `run-integration` label | <12 min |
| `pr-platform.yml` | release-please PR default | <30s (skip-with-notice) |
| Any docs-only PR | all 3 workflows | <30s each, parallel |

Workflows run as separate runs on separate runners → naturally parallel. Worst-case "everything changed" PR's blocking time is the *longest* workflow (~12 min), not the sum. Today's serial ~17 min becomes the upper bound, hit only when platform paths change.

### Coverage translation table

To make PR 1's review tractable, every removed bats assertion is replaced one-for-one in a per-service e2e test. The mapping (to be expanded in the implementation plan):

| Removed bats assertion | Replacement |
|---|---|
| `test_siteapp_auth.bats` — `/admin/` returns 401 without creds | `tests/integration/test_routes_smoke.bats` (Caddy-side gate) |
| `test_siteapp_auth.bats` — `/admin/` returns 200 with valid basic_auth | `tests/integration/test_routes_smoke.bats` |
| `test_siteapp_routing.bats` — `/docs/`, `/download/*` route to siteapp | `tests/integration/test_routes_smoke.bats` |
| `test_siteapp_routing.bats` — `/_static/site.css` returns 200 | `tests/integration/test_routes_smoke.bats` |
| `test_siteapp_routing.bats` — unknown path → JupyterLab | `tests/integration/test_routes_smoke.bats` |
| `test_siteapp_safety.bats` — path-traversal upload returns 400 | `services/siteapp/tests/e2e/test_safety.py` |
| `test_siteapp_safety.bats` — raw HTML in markdown is escaped | `services/siteapp/tests/e2e/test_safety.py` |
| `test_siteapp_uploads.bats` — token gate (401 cases) | `services/siteapp/tests/e2e/test_admin_upload.py` |
| `test_siteapp_uploads.bats` — atomic rename + meta.json | `services/siteapp/tests/e2e/test_admin_upload.py` |
| `test_siteapp_uploads.bats` — agent download serves uploaded binary | `services/siteapp/tests/e2e/test_admin_upload.py` (+ optional smoke in `test_routes_smoke.bats`) |

## Section 5 — Migration plan

Two PRs, separated only by the manual GitHub UI step the operator must take in between.

### PR 1 — Full restructure

One PR containing all the substantive change, staged across well-named commits for review:

1. `chore(repo): move services to services/<name>/`
   - `git mv compose/{siteapp,flasher} services/`
   - Update paths in `scripts/lib/render.sh`, `Taskfile.yml`, both `build.sh`, `release-please-config.json`, `renovate.json`.
   - **Sanity check:** existing `verify` (in `pr.yml`) still passes with new paths.
2. `test(siteapp): add e2e harness`
   - New `services/siteapp/tests/e2e/` (compose.yaml, conftest, fixtures, ~5 tests).
3. `test(flasher): add e2e harness + stub-serialhop`
   - New `services/flasher/tests/e2e/` (compose.yaml, conftest, stub-serialhop, ~4 tests).
4. `ci: add pr-siteapp.yml, pr-flasher.yml`
   - New workflows running alongside existing `verify`.
5. `test(integration): consolidate routing/auth/safety bats into routes-smoke`
   - `git mv tests/*.bats tests/integration/` (mechanical).
   - Delete `test_siteapp_{auth,routing,safety,uploads}.bats`.
   - Add `tests/integration/test_routes_smoke.bats`.
6. `ci: add pr-platform.yml, reduce pr.yml to stub`
   - New workflow with label gate.
   - `pr.yml` becomes a stub `verify` job (`run: echo "moved to pr-{siteapp,flasher,platform}"`).
7. `chore(release-please): switch to multi-component manifest`
   - Replace `release-please-config.json` and `.release-please-manifest.json`.
   - Add `compose/VERSION`, `services/siteapp/CHANGELOG.md`, `services/flasher/CHANGELOG.md`.
   - Rewrite `release-please.yml` for per-component build/deploy.

**PR 1 description includes a checklist for the operator** detailing the branch-protection update to perform immediately after merge:

> After merging:
> 1. Repo settings → Branches → `main` → Branch protection rule.
> 2. **Remove required checks:** `verify`.
> 3. **Add required checks:** `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`.
> 4. Save.

### Operator action — branch protection update

Manual GitHub UI step. ~30 seconds.

### PR 2 — Cleanup

Trivial single-commit PR. Deletes `pr.yml` (the stub `verify` job). Can be merged whenever convenient after branch protection is updated. Could be skipped indefinitely — the stub costs ~5 CI seconds per PR and is harmless — but better hygiene to remove.

### Risk profile

- **PR 1 is large** (~50+ files changed). Mitigated by commit-staging for review and bisectability.
- **Bats coverage regression** is the main substantive risk. Mitigated by the coverage-translation table — every removed assertion has an explicit replacement.
- **Branch-protection gap** is mitigated by the stub `verify` job in PR 1: existing required check stays present until operator updates protection. No flag-day, no merge-blocked window.
- **First release-please run** after PR 1 merges may open multiple release PRs at once (one per component with new commits since `0.3.1`). Worst case: revert PR 1's release-please-config commit; no images shipped.

### What's intentionally not in this restructure

- **Siteapp internal split** (docs/admin vs platform-API routes). Standalone refactor, not coupled to repo structure.
- **`deploy.sh` hardcoded `restart_services="caddy siteapp"`** — adding a new service today requires hand-editing this. Follow-up; out of scope.
- **`deploy.sh` hardcoded route-probe list** in the healthcheck — same pattern, same follow-up.
- **`server-info` API surface** — unchanged; no client coordination with `lab_devices_client`.

## Open questions for the implementation plan

- Exact `dorny/paths-filter@v3` pattern set per workflow — initial sketch above is reasonable but may need fine-tuning once the trees move.
- Whether to install `docker compose` plugins via apt or use `docker compose` built into runner image — affects e2e harness reliability on CI.
- Whether `compose/VERSION` should track the same value as `services/<svc>/VERSION` for the very first migration commit (yes — all three at `0.3.1`), or reset to mark the architecture change (no — keep continuity).
- Stub-SerialHop image: rebuild on every PR vs cache via GHCR — the stub is small, rebuild is fine.
- Healthcheck for flasher release: add `flasher_version` to `server-info` (additive, agent-safe), or curl flasher's own endpoint? Implementation plan picks one.

## Definitions

- **service** — A long-running containerised app deployed as part of the stack (siteapp, flasher, future services). Owns its own image, version, release cadence, CI.
- **platform** — Everything that isn't a service: compose templates, Caddyfile, chisel config, scripts, integration tests. Versioned independently.
- **service e2e** — Tests that exercise a service container directly via HTTP, with all upstream deps stubbed. Runs in the per-service workflow.
- **platform integration** — Tests that bring up the real fake-VPS stack and assert cross-service wiring. Runs in `pr-platform.yml`.

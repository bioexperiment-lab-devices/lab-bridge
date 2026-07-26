# CLAUDE.md — development flow rules

Non-obvious rules for this repo. Operational how-tos live in README; CI mechanics are in `.github/workflows/`.

Design + plan docs:
- `docs/superpowers/specs/2026-05-12-cicd-design.md` — baseline CI/CD (release-please, GHCR, deploy)
- `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` — the per-service split (architecture this repo currently follows)
- `docs/superpowers/specs/2026-05-17-unified-release-design.md` — current release model (single component, single tag stream)
- `docs/adding-a-service.md` — checklist for adding a new service (do this, in order)

## Architecture philosophy

The repo is a "Swiss-knife" lab platform: a set of independent containerised services plus the platform (compose templates, scripts, integration tests) that ties them together. The structure makes growth cheap: adding a new service is mechanical (see `docs/adding-a-service.md`), each service ships independently, and CI parallelises per service.

**Invariants future work MUST preserve:**

- **Each service lives at `services/<name>/`** with its own `Dockerfile`, `pyproject.toml`, `build.sh`, `app/`, `tests/` (unit), and `tests/e2e/` (service-level e2e against the running container with stubs for upstream deps). Do NOT scatter a service across the repo. The platform version lives at root `VERSION` and is shared by every service.
- **Each service has its own CI workflow** `.github/workflows/pr-<name>.yml`. It always triggers on `pull_request` (no workflow-level `paths:` filter) and gates steps internally via `dorny/paths-filter@v3`. Docs-only PRs fast-skip in <30s. Required-check name is `pr-<name> / <name>`.
- **One release-please component covers the whole repo.** Single root `VERSION`, single tag stream `vX.Y.Z`, single release PR at a time. Any commit anywhere informs the next bump. Conventional Commits scope (`feat(siteapp): …`) is decorative — it surfaces in the changelog but does not route the bump.
- **`compose/` is platform-only.** It holds `Caddyfile.tmpl`, `docker-compose.yml.tmpl`, `chisel-users.json.tmpl`, `pins.yaml`, `images.yaml`, `grafana/`, `loki/`. **Never put service source code under `compose/<name>/`** — that's the old layout, deliberately renamed.
- **External app images get platform wiring only.** Apps built and released elsewhere (e.g. `studio` = Experiment Studio from the `bioexperiment-lab-devices/lab-devices` repo) are pinned with a full image ref in `compose/images.yaml` (like `chisel_image`, NOT the `*_image_repo` + `VERSION` pattern) and receive a compose service, Caddy route, Authelia rule, deploy probe, and navbar entry — no `services/<name>/` dir, no `pr-<name>.yml`, no release-build step, no branch-protection change. Behavior tests live in the app's home repo; this repo's bats only asserts the wiring. Precedent: jupyter, studio (spec: `docs/superpowers/specs/2026-07-12-experiment-studio-integration.md`).
- **Three test layers, separate locations:**
  1. **Unit** in `services/<name>/tests/test_*.py` — pure logic, no containers.
  2. **Service e2e** in `services/<name>/tests/e2e/` — one container via `docker compose`, stubs for upstream deps, runs in the service's own CI workflow. **Behavior tests live here**, not in bats.
  3. **Platform integration** in `tests/integration/*.bats` — the *thin* "everything wires together" tier. One fake-VPS bring-up per bats file. Asserts cross-service wiring (Caddy routing, deploy, ops scripts). **Do not add per-service behavior tests here** — they belong in the service's e2e tier.

## Branch & release rules

- **`main` is protected. Squash-merge only, linear history.** No direct pushes, no merge-commit, no rebase-merge — release-please depends on squash. Required checks (as configured on branch protection): `Semantic Pull Request`, `siteapp`, `flasher`, `caddy`, `platform`. Adding a service adds another required check; update branch protection in lockstep (`streamer` has a `pr-streamer` workflow but is not currently a required check — a known gap, not an oversight to silently drop).
- **PR titles follow Conventional Commits** (`feat fix chore docs refactor test perf build ci revert`, scope optional). The title becomes the squash subject and is what release-please scans for the version bump.
- **Don't bump the version by hand.** release-please owns root `VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
- **Don't manually push release-tagged images to GHCR.** CI is the only path; manual pushes break the Sigstore attestation.
- **Release PRs run full CI.** Regular PRs use paths-filter to fast-skip unrelated workflows; release-please PRs (head ref `release-please--*`) bypass the filter and run every workflow's full suite. The release PR is the integration test gate before the production deploy.

## Config split

- **External image pins → `compose/images.yaml`** (tracked). Ten externally-released images (jupyter, chisel, loki, grafana, studio, authelia, redis, prometheus, node_exporter, cadvisor). Bump with `task images:bump -- <service> <version>`, which lands one releasable `feat:` PR. Image-only edits skip the fake-VPS bats matrix. **`studio` bumps itself**: lab-devices' release-please dispatches `.github/workflows/image-bump.yml` after its GHCR push, which opens the `feat:` PR and enables auto-merge — Renovate is disabled for that one pin to avoid a competing PR (see `renovate.json`'s `packageRules` entry for `experiment-studio`; `docs/lab-devices-dispatch-snippet.md` covers the lab-devices dispatch side, not Renovate). The other nine stay on Renovate's monthly grouped `chore` bumps, shipped with `task images:ship`. Any pin can also be moved by hand from the Actions UI via the `image-bump` workflow.
- **Paths, ports, retention, `*_image_repo` → `compose/pins.yaml`** (tracked). Not `config.yaml`. A change here DOES trigger the full platform suite.
- **Instance values + secrets + chisel roster → `config.yaml`** (gitignored, laptop only).
- **Optional-service selection → `disabled_services` in `config.yaml`** (allowed names + monitoring-group expansion live in `scripts/lib/config.sh`). CI mirrors it via the `LDS_DISABLED_SERVICES` GH variable — dual-managed like secrets.
- **`compose/config.ci.yaml.tmpl`'s `chisel_clients` MUST stay `[]`.** The vault guard (`LDS_REQUIRE_VAULT=1`) fails the CI deploy if non-empty.

## Laptop vs CI surface

- **Roster ops (`task secrets:add-client`, etc.) are laptop-only.** CI never renders `chisel/users.json` or `siteapp/clients.json`; it rsyncs with those excluded and skips chisel restart.
- **CI deploys stack-only** on release-please tag creation (`LDS_STACK_ONLY=1`). Don't invoke `task deploy` from CI — the workflow already calls `scripts/deploy.sh` with the right env.
- **Secrets are dual-managed.** Laptop sets the value (`task secrets:set-*`); the matching GH secret must be updated by hand or the next CI deploy fails. No automatic sync.

## Testing

- **Per-service workflows are path-gated** via `dorny/paths-filter@v3` inside the workflow — docs-only PRs fast-skip all heavy steps. Required-check still reports because workflows always trigger.
- **Service behavior tests live in `services/<name>/tests/e2e/`**, NOT in bats. They run in `pr-<name>.yml`'s e2e step against the just-built image. If you touch a service's routing/auth/upload/safety, its `pr-<name>` workflow exercises the e2e suite automatically.
  ```bash
  bats tests/integration/test_routes_smoke.bats   # Caddy routing smoke (cross-service wiring only)
  cd services/siteapp && uv run pytest tests/e2e/  # siteapp behaviour
  cd services/flasher && uv run pytest tests/e2e/  # flasher behaviour
  ```
- **`pr-platform.yml`'s bats step is a per-suite matrix** (`cheap` plus one cell per fake-VPS bats file — see the workflow for the current list) running in parallel. The `platform` aggregator job is the only required check; matrix cells aren't individually required. Adding a fake-VPS-bringing bats file? Add a matrix cell.
- **Bats files that spin up the fake-VPS MUST have the `compose_images_available` skip pattern** (mirror `test_routes_smoke.bats:11-14`). Quay.io/Docker Hub anonymous pulls flake; skip gracefully rather than hard-fail.
- **Release-please PRs run full `pr-platform` bats** (no opt-in label needed). This is the integration test gate before the production deploy that follows the squash-merge.
- **When you add or rename a workflow** that becomes a required check, update branch protection's required-check list in lockstep. The legacy `verify` stub trick is the migration template if you need a no-op transitional check.

## Server-info API

Additive fields to `/api/public/server-info` are safe (Go client tolerates unknown keys). Document additions in `docs/superpowers/specs/2026-05-11-server-info-client-spec.md` in the same PR. Breaking changes require a major bump + client coordination.

## Spec/plan workflow

Anything touching more than 2–3 files: brainstorming → `docs/superpowers/specs/` → `docs/superpowers/plans/` → subagent-driven execution with two-stage review. The 2026-05-12 CI/CD overhaul is the canonical example.

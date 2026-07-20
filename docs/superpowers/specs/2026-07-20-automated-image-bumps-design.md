# Automated third-party image bumps — design

Date: 2026-07-20
Status: approved, ready for planning

## Problem

`compose/images.yaml` pins nine externally-released container images. Bumping
one requires `task images:bump -- <service> <version>` from the operator's
laptop. Every Experiment Studio bump to date (0.7.0, 0.8.0, 0.9.0, 0.10.0) went
that way.

Two costs:

- **Studio releases are frequent** — roughly one per platform release cycle — and
  each one blocks on the operator being at a laptop with `gh`, `yq`, and a clean
  tree.
- **Renovate does not cover this.** `renovate.json` exists and declares a
  `customManager` for `compose/images.yaml`, but it has never opened a PR in
  this repo. Its schedule is monthly (`before 6am on the first day of the
  month`), its bumps are grouped, and they land as `chore` — which
  release-please marks hidden, so a Renovate bump never ships on its own and
  needs a follow-up `task images:ship`. That cadence and typing suit the eight
  boring images; they do not suit studio.

The bump *machinery* is already good: `scripts/images.sh bump` validates the
service against an allowlist, probes the registry to confirm the tag is
anonymously pullable, rewrites only the tag, and opens a `feat:`-typed PR.
What is missing is a trigger that is not a laptop.

## Goals

- A studio release in `bioexperiment-lab-devices/lab-devices` reaches preprod
  with no laptop involvement.
- Any of the nine pins can be bumped from the GitHub Actions UI.
- The release PR stays a human gate before the production deploy.

## Non-goals

- Replacing Renovate for the other eight images. It keeps its monthly grouped
  `chore` cadence, shipped via `task images:ship`.
- Polling registries for new tags. The push model gives exact versions with no
  tag-sorting heuristics.
- Removing `task images:bump`. The laptop path stays as-is and remains the
  fallback.

## Architecture

### One entry point, two callers

`workflow_dispatch` is callable cross-repo through the API, so lab-devices and
the operator-in-the-UI use the *same* workflow with the *same* input schema.
This is why the design does not use `repository_dispatch`: a second trigger
would mean a second, separately-validated payload shape for no gain.

**New — `.github/workflows/image-bump.yml`:**

```yaml
on:
  workflow_dispatch:
    inputs:
      service:
        type: choice
        options: [jupyter, chisel, loki, grafana, studio,
                  authelia, prometheus, node_exporter, cadvisor]
      version:
        type: string
```

Steps:

1. Mint a token via `actions/create-github-app-token@v3` from the org-level
   `RELEASE_PLEASE_APP_ID` / `RELEASE_PLEASE_APP_KEY`.
2. `actions/checkout` **with that token** (persisted credentials are what let
   `images.sh`'s `git push` succeed).
3. Install `yq`; run `scripts/images.sh bump "$service" "$version"`, which
   validates `version` against `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` and fails
   closed before the value reaches `yq` or a shell interpolation.
4. If a PR was opened, `gh pr merge --squash --auto "$pr_url"`.

**The App token is load-bearing, not incidental.** A pull request created with
the default `GITHUB_TOKEN` does not trigger `pull_request` workflows. The
required checks (`Semantic Pull Request`, `siteapp`, `flasher`, `caddy`,
`platform`) would never report, and auto-merge would wait forever. Opening
the PR as the App avoids this.

### The lab-devices side

`bioexperiment-lab-devices/lab-devices/.github/workflows/release-please.yml`
already has a `release-please` job (outputs `release_created`, `tag_name`) and
an `image` job that pushes
`ghcr.io/bioexperiment-lab-devices/experiment-studio:<version>`.

Add one job:

```yaml
dispatch-bump:
  needs: [release-please, image]
  if: ${{ needs.release-please.outputs.release_created == 'true' }}
```

It mints an App token scoped to `lab-bridge` and runs
`gh workflow run image-bump.yml -R bioexperiment-lab-devices/lab-bridge
-f service=studio -f version=<version>`.

**`needs: image` is required, not stylistic.** `images.sh` probes the registry
before it commits; dispatching before the GHCR push completes would fail on a
tag that does not yet exist.

### Resulting chain

```
lab-devices tag v0.11.0
  → image pushed to GHCR
  → dispatch into lab-bridge
  → bump PR (App-authored, feat:)
  → CI  (image-only diff ⇒ heavy bats matrix skipped, per PR #182)
  → auto-merge (squash)
  → release-please PR
  → [operator merges]            ← the one remaining human gate
  → tag → CI deploy
```

## Changes to `scripts/images.sh`

Three focused changes, each covered by a bats case:

1. **Emit the PR URL.** When `GITHUB_OUTPUT` is set, `cmd_bump` writes
   `pr_url=<url>` to it. The workflow then auto-merges that exact PR instead of
   re-deriving `images/<service>-<version>` and coupling the workflow to the
   script's branch-naming.
2. **Re-dispatch is a no-op, not a failure.** The already-at-version path
   already returns 0 without opening a PR; it must also leave `pr_url` empty so
   the workflow skips the merge step rather than erroring on an empty argument.
3. **Detect a pre-existing *remote* branch.** `_checkout_new_branch` checks only
   local refs. A fresh CI checkout never has the local branch, but the remote
   one can exist (a re-run after its PR was closed), which currently surfaces as
   a raw `git push` rejection. Check the remote and die with the same
   actionable message the local case gives.

## Guardrails

- **Version format** validated in `scripts/images.sh` before use (regex above).
- **Service allowlist** enforced twice: the `choice` input constrains the UI and
  the API, and `images.sh` re-checks against `_SERVICES`.
- **Concurrency** — `concurrency: image-bump-${{ inputs.service }}` serialises
  *workflow runs* for the same service: a second dispatch queues behind the
  first rather than executing in parallel. It does NOT serialise the PR
  *lifecycle* that follows a run. If two dispatches for the same service land
  within one CI cycle (e.g. two studio releases before the first bump PR has
  merged), both runs branch from the same unbumped `main` and edit the same
  line. The second PR opens as CONFLICTING; GitHub silently disables
  auto-merge on it, and it sits open with no alert. This residual failure
  mode is not closed by the concurrency group.
- **Registry probe** stays on in CI; an unpullable tag fails before any commit.
- **Least privilege** — the workflow's own `permissions:` stay minimal; the App
  token carries what the git and PR operations need.

## Renovate de-confliction

Exclude `experiment-studio` from the `compose/images.yaml` `customManager`.
Without this, Renovate would open a competing monthly `chore` bump for a pin
that the automated `feat:` path already moves — two PRs racing on one line.

## Testing

- **Unit / cheap tier** — new cases in `tests/integration/test_images_cli.bats`
  covering the three `images.sh` changes. This file already runs in
  `pr-platform.yml`'s `bats-cheap` job with `LDS_NO_GIT` and `_scratch_repo`
  helpers; no fake VPS, no new matrix cell.
- **Live smoke, after merge** — dispatch `service=studio, version=0.10.0` (the
  currently-pinned version). Expected: the already-at-version no-op. This
  exercises App auth, checkout, and the registry probe end to end while
  mutating nothing and opening no PR.
- **No new bats matrix cell.** Per CLAUDE.md, `tests/integration/*.bats` is the
  thin cross-service wiring tier; this work adds no fake-VPS bring-up.

## Manual prerequisite (operator-only)

The org GitHub App backing `RELEASE_PLEASE_APP_ID` must have:

- **Actions: read & write** (to call `workflow_dispatch` on
  `lab-bridge`), and
- an installation covering **both** `lab-devices` and `lab-bridge`.

The lab-devices `dispatch-bump` job must request the target repo explicitly:

```yaml
- uses: actions/create-github-app-token@v3
  with:
    app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
    private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}
    owner: bioexperiment-lab-devices
    repositories: lab-bridge
```

Neither the permission grant nor the installation can be made from this repo.
If the grant is missing, the dispatch step fails with a 403 and no bump PR is
opened — a loud failure, not a silent one.

## Documentation

- `CLAUDE.md` — note in the config-split section that studio pins move
  automatically on a lab-devices release, and that the other eight stay on
  Renovate + `task images:ship`.
- `README.md` — the manual `workflow_dispatch` path alongside `task images:bump`.
- The lab-devices job is specified here; applying it is a change in that repo,
  outside this repo's PR.

## Rejected alternatives

- **Scheduled registry poll** — self-contained, but lags by the poll interval
  and needs semver tag-sorting per registry. The push model gives the exact
  version at the exact moment.
- **Fix Renovate only** (ungroup studio, daily schedule, `feat:` typing) — no
  new workflow, but still polling-based, still monthly-ish latency at best, and
  it entangles the fast studio path with the eight boring pins.
- **Dedicated fine-grained PAT** — simplest setup, but a long-lived credential
  that acts as the operator and needs manual rotation.
- **Auto-merging the release PR too** — maximum velocity, but it removes the
  last human gate before a production deploy.

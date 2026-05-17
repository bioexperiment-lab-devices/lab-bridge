# Unified release model — single platform version

**Status:** approved (brainstorming complete; pending implementation plan).
**Supersedes:** parts of `2026-05-12-cicd-design.md` and `2026-05-15-per-service-isolation-design.md` that established the multi-component release-please topology.

## Problem

The current release machinery treats every service as an independently versioned package:

- Three `VERSION` files (`services/siteapp/VERSION`, `services/flasher/VERSION`, `compose/VERSION`).
- Three release-please components in `release-please-config.json` with `separate-pull-requests: true`.
- Three component-prefixed tag streams (`siteapp-v0.4.0`, `flasher-v0.6.0`, `platform-v0.6.1`).
- Three `release-build-*` jobs in `release-please.yml`, each with a distinct rollback prefix and distinct post-deploy verify mechanism (siteapp via `/api/public/server-info`, flasher via `docker inspect`, platform via a rsynced `/srv/lab-bridge/VERSION` marker).
- Three CHANGELOG files.
- A ~190-line `release-please-rebase.yml` workflow whose only purpose is to rebase sibling release-please PRs whose shared `.release-please-manifest.json` went stale when one sibling merged.

The decoupling was intended to make CI cheap and releases independent. CI cheapness has since been achieved by other means: per-service `paths-filter` gating in PR workflows, plus moving behavior tests out of bats and into service-level e2e (`services/<name>/tests/e2e/`). The releases-independent half of the bet did not pay off — sibling-PR conflicts produce real merge bugs (PRs #36, #37, #38 were all fixes for this), and the operator mental model has fractured: bumping siteapp without bumping flasher does not actually buy anything because they ship from the same compose stack on the same VPS on the same merge.

The desired model is what the stack actually is: one product (the lab-bridge platform), one version, one release stream.

## Goals

1. **One version for the entire repo.** All services and the platform share a single semver. When release-please bumps it, every image gets tagged with that bump even if the service's source did not change.
2. **One release.** Squash-merging a release PR builds every service image at the new tag, deploys the new compose stack to the VPS, and verifies that what landed matches.
3. **Targeted CI on regular PRs.** A PR touching only `services/flasher/**` runs `pr-flasher` substantively, while `pr-siteapp` and `pr-platform` fast-skip. No redundant work.
4. **Full CI on release PRs.** Squash-merging the release PR triggers a production deploy, so the release PR itself must exercise the full test surface before merge: `pr-siteapp`, `pr-flasher`, and `pr-platform`'s full bats matrix all run substantively regardless of paths.
5. **Delete everything that exists only to manage multi-component complexity.** The rebase workflow, the per-service VERSION/CHANGELOG files, the per-service release-build jobs, the per-PR `run-integration` label dance, the three verify mechanisms.

## Non-goals

- Backwards compatibility with the old tag prefixes for new tags. Pre-refactor tags (`platform-v0.6.1` etc.) remain on the repo and on GHCR for rollback purposes, but new tags will be plain `vX.Y.Z`.
- A new release-please plugin or wrapper. We keep `googleapis/release-please-action@v5` as the engine and only reshape its config.
- Cross-version compatibility shims between services. Both images always ship at the same tag — there is no scenario where siteapp `0.7.0` runs against flasher `0.6.0`.

## Design

### Versioning

A single file: `/VERSION` at the repo root, content `0.6.1 # x-release-please-version`. The annotation comment is the release-please rewrite anchor (same convention as today). Release-please owns this file via the package's `extra-files` entry; no operator bumps it by hand.

Why `0.6.1` and not a fresh `0.7.0`: release-please infers the next bump from commits since the last tag matching its current config. Setting the manifest to `0.6.1` lets release-please pick the next version naturally (`0.7.0` for `feat:` commits, `0.6.2` for `fix:` only). The refactor itself is a `refactor:` commit (hidden in the changelog), so the first release will be inferred from whatever user-visible commits land alongside or after the refactor merge.

Read by:

- `services/siteapp/build.sh` and `services/flasher/build.sh` — both scripts read the repo-root `VERSION` (via `SCRIPT_DIR/../../VERSION`) and use it as the Docker image tag.
- `scripts/lib/render.sh` — the `_siteapp_image()` and `_flasher_image()` functions both delegate to a single `_unified_version()` helper that reads root `VERSION`. The repo-shape (each helper still emits its own image ref) is preserved so the sed-substitution glue in `render_compose()` is unchanged.
- The Docker `build-args` pipeline — `LAB_BRIDGE_VERSION` build-arg is set to the unified version for both images, so siteapp's `/api/public/server-info.version` (which it surfaces today) becomes THE post-deploy verification signal for the platform as a whole.

Deleted entirely:

- `services/siteapp/VERSION`
- `services/flasher/VERSION`
- `compose/VERSION`
- `services/siteapp/CHANGELOG.md`
- `services/flasher/CHANGELOG.md`

Root `CHANGELOG.md` continues to exist and accumulates release-please-managed sections from the first post-refactor release onward. Its pre-refactor sections (the existing `platform-v…` entries) stay as historical record.

### release-please configuration

`release-please-config.json`:

```json
{
  "packages": {
    ".": {
      "package-name": "lab-bridge",
      "release-type": "simple",
      "extra-files": [
        { "type": "generic", "path": "VERSION" }
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

`.release-please-manifest.json`:

```json
{ ".": "0.6.1" }
```

Notable omissions:

- No `include-component-in-tag` → tags are `vX.Y.Z`.
- No `separate-pull-requests` → only one component, no PR fan-out.
- No `tag-separator` → not needed without component prefix.
- No `exclude-paths` → the whole repo is in scope; every commit informs the next bump.

Conventional Commits scopes (`feat(siteapp): …`, `fix(flasher): …`, `chore(platform): …`) remain optional and decorative. They no longer route anything in CI, but they continue to surface in changelog entries as visual grouping for the reader. `pr-title.yml`'s `requireScope: false` setting is preserved.

### release-please.yml (rewritten)

The workflow collapses to one release-please job and one release-build job. The release-build job builds both service images sequentially, attests provenance for each, and runs a single deploy with a single post-deploy verify pass.

Key shape:

- **Trigger:** push to `main` (normal release path) or `workflow_dispatch` with `rollback_to: vX.Y.Z` (manual rollback) and optional `verify_version` override (see Rollback section).
- **release-please outputs:** `released` (boolean), `tag` (e.g. `v0.7.0`), `version` (e.g. `0.7.0`). Released as unprefixed outputs since the root component is the only one.
- **release-build job condition:** `(push && released == 'true') || (workflow_dispatch && rollback_to != '')`.
- **`resolve ref` step:** derives `tag`, `version` (strips component prefix and leading `v`), `mode` (`release` on push, `rollback` on dispatch), and `verify_version` (uses dispatch input if non-empty, else `version`; `none` becomes empty string downstream). Build/push/attest steps gate on `mode == 'release'`; the deploy step runs in both modes.
- **Image builds:** both `docker/build-push-action@v6` steps run sequentially in the same job (cheap on a single runner; no need for matrix parallelism — both builds finish in well under the deploy step's tolerance). Tags include `:<version>` and `:latest`. Build-args carry `LAB_BRIDGE_VERSION` and `LAB_BRIDGE_GIT_SHA`.
- **Attestations:** `actions/attest-build-provenance@v4` per image; each consumes its build's `digest` output.
- **Deploy:** calls the composite action `./.github/actions/deploy-stack` with `verify_version: ${{ steps.ref.outputs.verify_version }}`.

The new workflow runs to roughly 100 lines, down from 253 today.

### deploy-stack composite action (rewritten)

Three verify inputs (`verify_siteapp_version`, `verify_flasher_version`, `verify_platform_version`) collapse to one: `verify_version`.

When `verify_version` is non-empty, the action runs two checks in sequence (both timeout-bounded at 60s with 2s backoff):

1. **siteapp HTTP check.** Poll `https://$VPS_HOST/api/public/server-info` until `.version == verify_version`. Proves siteapp restarted with the new image. This is the strongest single signal: siteapp's reported version comes from the `LAB_BRIDGE_VERSION` build-arg baked into the image at release-build time, so a match implies the new image is running.

2. **flasher container check.** Poll `ssh … docker inspect --format '{{.Config.Image}}' lab-bridge-flasher-1` until the image tag matches `verify_version`. Proves the flasher container pulled and started the new image. (Flasher has no equivalent of `/api/public/server-info` and adding one is out of scope; the docker-inspect check is cheap and direct.)

Dropped: the platform `/srv/lab-bridge/VERSION` rsync marker check. It is redundant once the two checks above pass — siteapp running the new image presupposes the new compose templates rsynced (otherwise the compose `image:` field would still reference the old tag). The marker file itself is no longer written: `scripts/deploy.sh`'s "Platform VERSION marker" stanza is removed.

### PR CI gating

Goal:

- Regular PRs run **only what changed**.
- Release-please PRs run **everything**.

Implementation pattern, applied identically to `pr-siteapp.yml`, `pr-flasher.yml`, and `pr-platform.yml`:

```yaml
- id: changed
  uses: dorny/paths-filter@v3
  with:
    filters: |
      src:
        - '<paths for this workflow>'
        - '.github/workflows/pr-<name>.yml'

- id: should-run
  run: |
    if [[ "${{ github.head_ref }}" == release-please--* ]]; then
      echo "run=true" >> "$GITHUB_OUTPUT"
    else
      echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
    fi
```

Subsequent steps gate on `if: steps.should-run.outputs.run == 'true'`.

This delivers:

- **Regular PR** (e.g. touching only `services/flasher/**`): `pr-flasher` runs ruff/unit/SPA/e2e/image-build. `pr-siteapp` fast-skips. `pr-platform`'s shellcheck and bats matrix fast-skip.
- **Release-please PR** (head ref `release-please--branches--main--components--lab-bridge`): all three workflows run their full suites. Catches integration regressions before merge triggers the production deploy.

In `pr-platform.yml` specifically, the existing `gate` job (which skipped bats on release-please PRs unless `run-integration` was labeled) is **removed**. The new `should-run` step replaces it inline, with the opposite default — release-please PRs now run bats by default instead of skipping it. The `run-integration` label has no consumers after this and is retired.

Branch protection required checks (`pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`) are unchanged. The aggregator job in `pr-platform` still succeeds when dependent jobs are `success` or `skipped`, so docs-only regular PRs still flow green.

### Rollback

`gh workflow run release-please.yml -f rollback_to=v0.7.0` triggers the release-build job in `mode=rollback`: it skips the build/push/attest steps and runs the deploy step against the tagged commit. The deploy step's `verify_version=0.7.0` then confirms the rollback landed.

The workflow has two `workflow_dispatch` inputs:

- `rollback_to` — the tag to redeploy. Accepts plain `vX.Y.Z` (post-refactor) or legacy prefixed tags (`platform-vX.Y.Z`, `siteapp-vX.Y.Z`, `flasher-vX.Y.Z`).
- `verify_version` — optional override. When empty (default), the `resolve ref` step derives the verify version from the tag via `version="${tag#*-v}"; version="${version#v}"` (handles both unprefixed and any single-prefix form). When set to a non-empty value, that value is used as-is. When set to `none`, the deploy step is invoked with empty `verify_version` (verify skipped).

Why the override exists: legacy pre-refactor tags carry version numbers that don't match what their images actually report. A rollback to `platform-v0.6.1` deploys a stack whose siteapp image is `lab-bridge-siteapp:0.4.0` (per the `services/siteapp/VERSION` of that commit), so siteapp will report `0.4.0` via `/api/public/server-info`, not `0.6.1`. For such rollbacks the operator passes `verify_version=none` and inspects the deployed stack manually. Post-refactor rollbacks always have congruent verify values and the override is unused.

## File-level cleanup checklist

**Deleted:**

- `services/siteapp/VERSION`
- `services/flasher/VERSION`
- `compose/VERSION`
- `services/siteapp/CHANGELOG.md`
- `services/flasher/CHANGELOG.md`
- `.github/workflows/release-please-rebase.yml`

**Created:**

- `VERSION` at repo root (`0.6.1 # x-release-please-version`)

**Rewritten:**

- `release-please-config.json` — single component, as shown above.
- `.release-please-manifest.json` — `{ ".": "0.6.1" }`.
- `.github/workflows/release-please.yml` — collapsed shape described above, ~100 LOC.
- `.github/workflows/pr-platform.yml` — drop `gate` job; inline `paths-filter` + release-please bypass; bats matrix and aggregator preserved.
- `.github/workflows/pr-siteapp.yml` — add release-please bypass.
- `.github/workflows/pr-flasher.yml` — add release-please bypass.
- `.github/actions/deploy-stack/action.yml` — three verify inputs → one `verify_version` input; drop platform marker check.
- `scripts/lib/render.sh` — `_siteapp_image()` and `_flasher_image()` both delegate to a single `_unified_version()` helper reading root `VERSION`.
- `scripts/deploy.sh` — drop the "Platform VERSION marker" rsync stanza (no consumer left).
- `services/siteapp/build.sh` — read root `VERSION` via repo-root-relative path.
- `services/flasher/build.sh` — same.
- `Taskfile.yml` — update descriptions for `siteapp:build-and-push` / `flasher:build-and-push` to reference root `VERSION`.
- `compose/pins.yaml` — update comments to point at root `VERSION` instead of per-service files.
- `README.md` — replace the manual per-service VERSION bump example with a "version is owned by release-please at root `VERSION`" pointer.
- `CLAUDE.md` — rewrite the "Branch & release rules" and "Architecture philosophy" service-invariant lists to drop VERSION/CHANGELOG from per-service file requirements; drop the `separate-pull-requests` note; drop the `run-integration` label note.
- `docs/adding-a-service.md` — step 1 drops VERSION/CHANGELOG from the service tree; steps 8 (release-please wiring) and 9 (release-build job) collapse to "add a build & push step + an attest step to `release-please.yml`'s `release-build` job, mirroring siteapp/flasher". Step 14 (branch protection) is unchanged.

**Preserved (no change):**

- `release-please-action@v5` itself.
- GitHub App token configuration (`vars.RELEASE_PLEASE_APP_ID`, `secrets.RELEASE_PLEASE_APP_KEY`).
- Sigstore attestation flow per image.
- `LDS_STACK_ONLY=1` + `LDS_REQUIRE_VAULT=1` deploy guards.
- `pr-title.yml` (Conventional Commits enforcement).
- The bats matrix shape in `pr-platform.yml`.
- All branch protection required-check names.

## Migration

This is a single PR titled `refactor(release): unify versioning into single platform release` (or similar). The PR is large in line count but small in conceptual surface. Splitting it would create windows where the manifest, config, and workflows disagree.

Pre-merge step (operator, one-time): create a `v0.6.1` tag at the same commit as `platform-v0.6.1` and push it. This gives the new single-component release-please config a tag boundary to scan from:

```bash
git tag v0.6.1 platform-v0.6.1
git push origin v0.6.1
```

Without this tag, release-please has no reference point in its new config format and will scan all of main history (still correct, but slower and noisier).

Sequence after merge:

1. The squash-merge to `main` triggers `release-please.yml`. The release-please job sees the new config, the `v0.6.1` tag, and the commits since (including the refactor itself, hidden as `refactor:`). It opens a release PR for the inferred next version (likely `v0.7.0` once any `feat:` commit lands on top of the refactor, `v0.6.2` if only `fix:` commits accumulate).
2. That release PR's CI is the first end-to-end test of the unified gating: all three `pr-*` workflows run substantively (release-please bypass active) and `pr-platform` runs the full bats matrix.
3. Squash-merging the release PR triggers `release-please.yml` again. This time release-please tags the new version, then the `release-build` job builds both images at that tag, attests, deploys, and verifies via siteapp `/api/public/server-info` + flasher `docker inspect`.

For the first post-refactor merge, if anything goes wrong the rollback path is intact:

- `gh workflow run release-please.yml -f rollback_to=platform-v0.6.1 -f verify_version=none` redeploys the pre-refactor stack with verify skipped (since the legacy image's reported version won't match the prefixed tag's number).

Pre-refactor tags remain on GHCR untouched. The `lab-bridge-siteapp:latest` and `lab-bridge-flasher:latest` floating tags get rewritten at the first new release.

## Risks

- **First-release CI failure surface.** The first release PR exercises every workflow change at once. If something's wrong, the release PR fails and we iterate on the refactor branch directly. The rollback path is documented and tested-by-construction (mode=rollback is the same code path as mode=release minus build/push/attest).
- **Stale release-please state.** Release-please reads its manifest and config; pre-refactor branches with the old multi-component config will conflict if rebased onto the refactor commit. The mitigation is timing: merge the refactor when no other release-please PR is open (`gh pr list --state open --search "release-please"` should return nothing).
- **`latest` tag rewrite.** The `:latest` floating tag moves at every release. If anything pulls `:latest` outside of the documented deploy flow, it will get the new image even if the operator was expecting old behavior. The deploy.sh path always uses pinned tags from rendered compose templates, so this risk is limited to ad-hoc `docker pull :latest` invocations, which are not part of the operator workflow.
- **Conventional Commits scope ambiguity.** Today, `feat(siteapp): …` routes the commit to the siteapp component for bump-inference. After unification, the scope is decorative; any `feat:` anywhere bumps the unified version. This is the intended behavior but worth flagging to the operator so review heuristics adjust.

## Open questions

None at design time. All decisions are made in the spec.

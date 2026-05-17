# Unified release model — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the three-component release-please topology (siteapp/flasher/platform) into one — single root `VERSION`, single tag stream `vX.Y.Z`, single release-build job, single deploy verify. Delete the rebase workflow and the `gate` job.

**Architecture:** Refactor in seven logically-ordered commits within a single PR. Re-point all VERSION readers first so deletions are safe; then delete orphan files; then reshape release-please config; then collapse release workflows; then adjust PR gating; then delete the rebase workflow; then update docs.

**Tech Stack:** GitHub Actions, release-please-action v5, dorny/paths-filter v3, bats-core, bash + jq + yq, docker buildx.

**Spec:** `docs/superpowers/specs/2026-05-17-unified-release-design.md`

---

## Task 0: Worktree setup

The plan modifies workflows, scripts, configs, and docs across the repo simultaneously. Work in an isolated worktree off `main` so the existing `flasher-improvements` worktree (which has unrelated open work) stays untouched.

**Files:** none yet.

- [ ] **Step 1: Verify clean main state**

Run:
```bash
git -C /Users/khamitovdr/lab_devices_server fetch origin
git -C /Users/khamitovdr/lab_devices_server log --oneline -3 main
git -C /Users/khamitovdr/lab_devices_server worktree list
```

Expected: most recent commit is `c2886a5 docs: spec for unified single-version release model` (or newer). Worktree list shows main checked out at `/Users/khamitovdr/lab_devices_server` and the existing `flasher-improvements` worktree.

- [ ] **Step 2: Create a fresh worktree for this refactor**

Run:
```bash
cd /Users/khamitovdr/lab_devices_server
git worktree add -b refactor/unified-release .worktrees/unified-release main
cd .worktrees/unified-release
```

Expected: new worktree at `.worktrees/unified-release` on branch `refactor/unified-release`.

**All subsequent file paths in this plan are relative to `.worktrees/unified-release/`.** Use absolute paths or `cd` into the worktree before each task.

- [ ] **Step 3: Verify pre-merge tag prerequisite (do NOT push yet)**

The migration plan requires a `v0.6.1` tag at the same commit as `platform-v0.6.1` BEFORE the refactor PR merges. The tag does not need to exist during PR development — only at merge time. Record this in the PR description:

> Before squash-merging this PR, the maintainer must push a `v0.6.1` tag at the same commit as `platform-v0.6.1`:
> ```bash
> git tag v0.6.1 platform-v0.6.1
> git push origin v0.6.1
> ```
> Without this tag, release-please will scan all of main history on its first run after merge (still correct, but noisier).

(This is a maintainer action, not a code change. Mentioned here so the executor includes it in the PR body.)

---

## Task 1: Create root VERSION file

**Files:**
- Create: `VERSION`

- [ ] **Step 1: Write the root VERSION file**

Content of `VERSION` (exactly one line, trailing newline):

```
0.6.1 # x-release-please-version
```

Use:
```bash
printf '0.6.1 # x-release-please-version\n' > VERSION
```

- [ ] **Step 2: Verify contents**

Run: `awk 'NF { print $1; exit }' VERSION`
Expected output: `0.6.1`

- [ ] **Step 3: Do NOT commit yet**

We will commit Task 1–5 together as one logical unit ("re-point all VERSION readers to root, then add root VERSION").

---

## Task 2: Update `scripts/lib/render.sh` to read root VERSION

**Files:**
- Modify: `scripts/lib/render.sh` (lines 6-41 — both `_siteapp_image` and `_flasher_image`)

- [ ] **Step 1: Replace `_siteapp_image` and `_flasher_image` with a shared helper**

Open `scripts/lib/render.sh`. Replace the block from line 6 through line 41 (inclusive — the two helper functions and their comments) with this content:

```bash
# _unified_version — print the unified platform version from /VERSION.
# Override via LDS_VERSION_FILE for tests. The VERSION file path is
# resolved REPO-ROOT-RELATIVE via this script's location.
_unified_version() {
    local version_file="${LDS_VERSION_FILE:-}"
    if [[ -z "$version_file" ]]; then
        # scripts/lib/render.sh → repo root is two levels up.
        local script_dir
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        version_file="$script_dir/../../VERSION"
    fi
    [[ -f "$version_file" ]] || die "VERSION file not found: $version_file"
    local version
    version="$(awk 'NF { print $1; exit }' "$version_file")"
    [[ -n "$version" ]] || die "VERSION file is empty: $version_file"
    printf '%s' "$version"
}

# _siteapp_image — print ghcr.io/<owner>/lab-bridge-siteapp:<version>
_siteapp_image() {
    local repo="${SITEAPP_IMAGE_REPO:?SITEAPP_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}

# _flasher_image — print ghcr.io/<owner>/lab-bridge-flasher:<version>
_flasher_image() {
    local repo="${FLASHER_IMAGE_REPO:?FLASHER_IMAGE_REPO not set — did load_config run?}"
    printf '%s:%s' "$repo" "$(_unified_version)"
}
```

Note: the existing `render_compose()` function at line ~43 onward stays unchanged — it still calls `_siteapp_image` and `_flasher_image` and receives the same string shape (`<repo>:<version>`).

- [ ] **Step 2: Sanity-check the rewrite**

Run from the worktree root:
```bash
bash -c '
  source scripts/lib/common.sh
  source scripts/lib/render.sh
  export SITEAPP_IMAGE_REPO=ghcr.io/example/lab-bridge-siteapp
  export FLASHER_IMAGE_REPO=ghcr.io/example/lab-bridge-flasher
  echo "siteapp: $(_siteapp_image)"
  echo "flasher: $(_flasher_image)"
'
```

Expected:
```
siteapp: ghcr.io/example/lab-bridge-siteapp:0.6.1
flasher: ghcr.io/example/lab-bridge-flasher:0.6.1
```

Both helpers now resolve from root `VERSION`, not their old per-service files.

- [ ] **Step 3: Do NOT commit yet** (still bundling with Tasks 1, 3, 4, 5).

---

## Task 3: Update `services/{siteapp,flasher}/build.sh` to read root VERSION

**Files:**
- Modify: `services/siteapp/build.sh` (line 6)
- Modify: `services/flasher/build.sh` (line 6)

- [ ] **Step 1: Update `services/siteapp/build.sh`**

Open `services/siteapp/build.sh`. Replace the single line:

```bash
VERSION="$(awk 'NF { print $1; exit }' "$SCRIPT_DIR/VERSION")"
```

with:

```bash
VERSION="$(awk 'NF { print $1; exit }' "$REPO_ROOT/VERSION")"
```

Also update the final `echo` line (line 22) from:

```bash
echo "Bump services/siteapp/VERSION and commit to pin this tag."
```

to:

```bash
echo "Version is managed by release-please — do not bump VERSION manually."
```

- [ ] **Step 2: Update `services/flasher/build.sh`**

Same two changes in `services/flasher/build.sh` (the file is structurally identical to siteapp's).

Replace line 6 to use `$REPO_ROOT/VERSION` instead of `$SCRIPT_DIR/VERSION`. Replace the final-line message the same way as above.

- [ ] **Step 3: Sanity-check (read-only)**

Run:
```bash
bash -c '
  set -e
  SCRIPT_DIR="$(pwd)/services/siteapp"
  REPO_ROOT="$(pwd)"
  VERSION="$(awk "NF { print \$1; exit }" "$REPO_ROOT/VERSION")"
  echo "siteapp build.sh would tag: ghcr.io/.../lab-bridge-siteapp:$VERSION"
'
```

Expected output: `siteapp build.sh would tag: ghcr.io/.../lab-bridge-siteapp:0.6.1`

- [ ] **Step 4: Do NOT commit yet**.

---

## Task 4: Update `tests/integration/helpers.bash` to read root VERSION

**Files:**
- Modify: `tests/integration/helpers.bash` (lines 50-72 — `load_siteapp_test_image` and `load_flasher_test_image`)

- [ ] **Step 1: Update `load_siteapp_test_image()` (line 50-58)**

Open `tests/integration/helpers.bash`. Find the `load_siteapp_test_image()` function (around line 50). Replace its line 54:

```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/services/siteapp/VERSION")"
```

with:

```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
```

- [ ] **Step 2: Update `load_flasher_test_image()` (line 64-72)**

Find `load_flasher_test_image()` (around line 64). Replace its line 68 the same way:

```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/services/flasher/VERSION")"
```

becomes:

```bash
    version="$(awk 'NF { print $1; exit }' "$ROOT/VERSION")"
```

- [ ] **Step 3: Do NOT commit yet**.

---

## Task 5: Update `tests/integration/test_render.bats`

The existing test at lines 331-371 references `services/siteapp/VERSION` and the `LDS_SITEAPP_VERSION_FILE` env var (which no longer exists — replaced by `LDS_VERSION_FILE`). Update the test and add a parallel flasher test.

**Files:**
- Modify: `tests/integration/test_render.bats` (lines 331-371)

- [ ] **Step 1: Replace the existing test (lines 331-371)**

Delete the block from line 331 (`@test "render_compose: SITEAPP_IMAGE …`) through line 371 (the closing `}` of that test). Insert in its place:

```bash
@test "render_compose: SITEAPP_IMAGE is composed from pins.yaml + root VERSION" {
    mkdir -p "$BATS_TEST_TMPDIR/compose"
    cat > "$BATS_TEST_TMPDIR/compose/pins.yaml" <<'PINS'
jupyter_image: jup:1
chisel_image: chi:1
chisel_listen_port: 8080
loki_image: lok:1
loki_retention_days: 30
grafana_image: gra:1
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
acme_email: x@example.com
remote_root: /srv/lb
notebooks_path: /srv/lb/nb
ssh_port: 22
PINS
    echo "1.2.3 # x-release-please-version" > "$BATS_TEST_TMPDIR/VERSION"
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567 }
siteapp: { admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa }
chisel_clients: []
CFG
    # Minimal compose template that references __SITEAPP_IMAGE__.
    echo "image: __SITEAPP_IMAGE__" > "$BATS_TEST_TMPDIR/compose.tmpl"

    # Use the LDS_VERSION_FILE override so render.sh reads the test VERSION,
    # not the real repo's root VERSION.
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        export LDS_PINS_FILE='$BATS_TEST_TMPDIR/compose/pins.yaml'
        export LDS_VERSION_FILE='$BATS_TEST_TMPDIR/VERSION'
        load_config '$BATS_TEST_TMPDIR/config.yaml'
        render_compose '$BATS_TEST_TMPDIR/compose.tmpl' '$BATS_TEST_TMPDIR/out'
        cat '$BATS_TEST_TMPDIR/out'
    "
    [ "$status" -eq 0 ]
    [ "$output" = "image: ghcr.io/example/lab-bridge-siteapp:1.2.3" ]
}

@test "render_compose: FLASHER_IMAGE is composed from pins.yaml + root VERSION" {
    mkdir -p "$BATS_TEST_TMPDIR/compose"
    cat > "$BATS_TEST_TMPDIR/compose/pins.yaml" <<'PINS'
jupyter_image: jup:1
chisel_image: chi:1
chisel_listen_port: 8080
loki_image: lok:1
loki_retention_days: 30
grafana_image: gra:1
siteapp_image_repo: ghcr.io/example/lab-bridge-siteapp
flasher_image_repo: ghcr.io/example/lab-bridge-flasher
acme_email: x@example.com
remote_root: /srv/lb
notebooks_path: /srv/lb/nb
ssh_port: 22
PINS
    echo "1.2.3 # x-release-please-version" > "$BATS_TEST_TMPDIR/VERSION"
    cat > "$BATS_TEST_TMPDIR/config.yaml" <<'CFG'
vps: { host: 1.2.3.4, ssh_user: deploy }
jupyter: { password_hash: sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567 }
siteapp: { admin_password_hash: $2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa }
chisel_clients: []
CFG
    echo "image: __FLASHER_IMAGE__" > "$BATS_TEST_TMPDIR/compose.tmpl"

    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        export LDS_PINS_FILE='$BATS_TEST_TMPDIR/compose/pins.yaml'
        export LDS_VERSION_FILE='$BATS_TEST_TMPDIR/VERSION'
        load_config '$BATS_TEST_TMPDIR/config.yaml'
        render_compose '$BATS_TEST_TMPDIR/compose.tmpl' '$BATS_TEST_TMPDIR/out'
        cat '$BATS_TEST_TMPDIR/out'
    "
    [ "$status" -eq 0 ]
    [ "$output" = "image: ghcr.io/example/lab-bridge-flasher:1.2.3" ]
}
```

- [ ] **Step 2: Run the updated test to verify**

Run:
```bash
bats tests/integration/test_render.bats
```

Expected: all tests pass, including the two new/updated ones. If bats is not installed locally, skip and rely on CI.

- [ ] **Step 3: Commit Tasks 1–5 together**

Run:
```bash
git add VERSION scripts/lib/render.sh services/siteapp/build.sh services/flasher/build.sh tests/integration/helpers.bash tests/integration/test_render.bats
git commit -m "$(cat <<'EOF'
refactor(release): point all VERSION readers at new root VERSION

Adds a root VERSION file containing the platform version. Updates
render.sh, build.sh scripts, bats test helpers, and the affected
render-compose tests to read from the new location. The per-service
VERSION files still exist after this commit (deleted in the next one)
but no longer have any consumer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: clean commit. If any pre-commit hook fails, fix the underlying issue and re-commit (do NOT use `--no-verify` or `--amend`).

---

## Task 6: Delete orphaned per-service VERSION and CHANGELOG files

After Task 5's commit, no script or test reads these files. Delete them.

**Files:**
- Delete: `services/siteapp/VERSION`
- Delete: `services/flasher/VERSION`
- Delete: `compose/VERSION`
- Delete: `services/siteapp/CHANGELOG.md`
- Delete: `services/flasher/CHANGELOG.md`

- [ ] **Step 1: Delete the five files**

Run:
```bash
git rm services/siteapp/VERSION services/flasher/VERSION compose/VERSION services/siteapp/CHANGELOG.md services/flasher/CHANGELOG.md
```

Expected: five files staged for deletion.

- [ ] **Step 2: Verify nothing else references them**

Run:
```bash
git grep -nE 'services/(siteapp|flasher)/VERSION|services/(siteapp|flasher)/CHANGELOG\.md|compose/VERSION' -- ':!docs/' ':!CHANGELOG.md' || echo "no consumers"
```

Expected: `no consumers` (the `git grep` returns non-zero because no matches found). The exclusions skip docs and the root CHANGELOG.md (which contains historical compare-link URLs pointing at old tags — those stay).

- [ ] **Step 3: Commit the deletions**

Run:
```bash
git commit -m "$(cat <<'EOF'
refactor(release): delete per-service VERSION and CHANGELOG files

The platform is now versioned at root VERSION. Per-service version
files and changelogs are no longer the source of truth and have no
remaining readers (verified in the previous commit).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Rewrite `release-please-config.json` and `.release-please-manifest.json`

**Files:**
- Modify: `release-please-config.json` (full rewrite)
- Modify: `.release-please-manifest.json` (full rewrite)

- [ ] **Step 1: Rewrite `release-please-config.json`**

Replace the entire file with:

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

Use:
```bash
cat > release-please-config.json <<'JSON'
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
JSON
```

- [ ] **Step 2: Rewrite `.release-please-manifest.json`**

Replace the entire file with:

```json
{ ".": "0.6.1" }
```

Use:
```bash
printf '{ ".": "0.6.1" }\n' > .release-please-manifest.json
```

- [ ] **Step 3: Validate JSON**

Run:
```bash
jq . release-please-config.json > /dev/null && echo "config: ok"
jq . .release-please-manifest.json > /dev/null && echo "manifest: ok"
```

Expected: both lines print `ok`.

- [ ] **Step 4: Commit**

Run:
```bash
git add release-please-config.json .release-please-manifest.json
git commit -m "$(cat <<'EOF'
refactor(release): collapse release-please to a single component

One package, root VERSION as extra-file, no separate-pull-requests,
no include-component-in-tag (tags become plain vX.Y.Z), no
exclude-paths (every commit in scope). Manifest pins the current
platform version (0.6.1) so release-please infers the next bump
from commits since the v0.6.1 tag.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Rewrite `.github/workflows/release-please.yml`

**Files:**
- Modify: `.github/workflows/release-please.yml` (full rewrite)

- [ ] **Step 1: Rewrite the workflow**

Replace the entire file with:

```yaml
name: release-please

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      rollback_to:
        description: 'Tag to redeploy (e.g. v0.7.0 or legacy platform-v0.6.1). Empty for a normal release-please run.'
        required: false
      verify_version:
        description: 'Override the post-deploy version check. Empty = derive from tag. "none" = skip verify (use for legacy tags whose images report a different version than the tag carries).'
        required: false

concurrency:
  group: release-please-main
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write
  id-token: write
  attestations: write
  packages: write

jobs:
  release-please:
    name: release-please
    if: github.event_name == 'push' || github.event.inputs.rollback_to == ''
    runs-on: ubuntu-latest
    outputs:
      released: ${{ steps.rp.outputs.release_created }}
      tag:      ${{ steps.rp.outputs.tag_name }}
      version:  ${{ steps.rp.outputs.version }}
    steps:
      - id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}

      - id: rp
        uses: googleapis/release-please-action@v5
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
          token: ${{ steps.app-token.outputs.token }}

  release-build:
    name: release-build
    needs: release-please
    # !failure() && !cancelled() lets this job run when `release-please` is
    # skipped (workflow_dispatch rollback path), since the implicit success()
    # precondition on `needs:` would otherwise also skip this job.
    if: |
      !failure() && !cancelled() && (
        (github.event_name == 'push' && needs.release-please.outputs.released == 'true')
        || (github.event_name == 'workflow_dispatch' && github.event.inputs.rollback_to != '')
      )
    runs-on: ubuntu-latest
    steps:
      - name: resolve ref
        id: ref
        run: |
          set -euo pipefail
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            tag="${{ github.event.inputs.rollback_to }}"
            mode=rollback
            user_verify="${{ github.event.inputs.verify_version }}"
          else
            tag="${{ needs.release-please.outputs.tag }}"
            mode=release
            user_verify=""
          fi
          # Strip either `<prefix>-v` (legacy: platform-v0.6.1, siteapp-v0.4.0, flasher-v0.6.0)
          # or leading `v` (unified: v0.7.0).
          version="${tag#*-v}"
          version="${version#v}"
          # Resolve verify_version: explicit input wins, "none" → empty (skip),
          # otherwise derive from tag.
          if [[ "$user_verify" == "none" ]]; then
            verify_version=""
          elif [[ -n "$user_verify" ]]; then
            verify_version="$user_verify"
          else
            verify_version="$version"
          fi
          {
            echo "tag=$tag"
            echo "version=$version"
            echo "mode=$mode"
            echo "verify_version=$verify_version"
          } >> "$GITHUB_OUTPUT"

      - uses: actions/checkout@v4
        with:
          ref: ${{ steps.ref.outputs.tag }}

      - name: log in to GHCR
        if: steps.ref.outputs.mode == 'release'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: set up buildx
        if: steps.ref.outputs.mode == 'release'
        uses: docker/setup-buildx-action@v3

      - name: build & push siteapp image
        if: steps.ref.outputs.mode == 'release'
        id: build-siteapp
        uses: docker/build-push-action@v6
        with:
          context: services/siteapp
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp:${{ steps.ref.outputs.version }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: build & push flasher image
        if: steps.ref.outputs.mode == 'release'
        id: build-flasher
        uses: docker/build-push-action@v6
        with:
          context: services/flasher
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher:${{ steps.ref.outputs.version }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: attest siteapp build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-siteapp
          subject-digest: ${{ steps.build-siteapp.outputs.digest }}
          push-to-registry: true

      - name: attest flasher build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-flasher
          subject-digest: ${{ steps.build-flasher.outputs.digest }}
          push-to-registry: true

      - name: deploy + verify
        uses: ./.github/actions/deploy-stack
        with:
          vps_host:              ${{ vars.VPS_HOST }}
          vps_ssh_user:          ${{ vars.VPS_SSH_USER }}
          vps_ssh_key:           ${{ secrets.VPS_SSH_KEY }}
          jupyter_password_hash: ${{ secrets.JUPYTER_PASSWORD_HASH }}
          admin_password_hash:   ${{ secrets.ADMIN_PASSWORD_HASH }}
          grafana_password:      ${{ secrets.GRAFANA_ADMIN_PASSWORD }}
          agent_upload_token:    ${{ secrets.AGENT_UPLOAD_TOKEN }}
          flasher_upload_token:  ${{ secrets.FLASHER_UPLOAD_TOKEN }}
          verify_version:        ${{ steps.ref.outputs.verify_version }}
```

- [ ] **Step 2: YAML lint**

Run:
```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release-please.yml')); print('ok')"
```

Expected: `ok`. If yaml not installed, skip — CI will catch syntax issues.

- [ ] **Step 3: Do NOT commit yet** — Task 9 (deploy-stack action) and Task 10 (deploy.sh marker removal) ship in the same commit.

---

## Task 9: Rewrite `.github/actions/deploy-stack/action.yml`

**Files:**
- Modify: `.github/actions/deploy-stack/action.yml` (full rewrite)

- [ ] **Step 1: Rewrite the composite action**

Replace the entire file with:

```yaml
name: 'Deploy stack to VPS'
description: 'rsync + docker compose up on the VPS, with optional version-equality healthcheck'

inputs:
  vps_host:              { required: true }
  vps_ssh_user:          { required: true }
  vps_ssh_key:           { required: true }
  jupyter_password_hash: { required: true }
  admin_password_hash:   { required: true }
  grafana_password:      { required: true }
  agent_upload_token:    { required: true }
  flasher_upload_token:  { required: true }
  verify_version:
    description: "When set, assert siteapp /api/public/server-info.version == this AND the lab-bridge-flasher-1 container's image tag ends in :this. Omit (or empty) to skip verification."
    required: false
    default: ""

runs:
  using: composite
  steps:
    - name: install rsync, envsubst, yq
      shell: bash
      run: |
        sudo apt-get update
        sudo apt-get install -y rsync gettext-base
        sudo wget -q https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 -O /usr/local/bin/yq
        sudo chmod +x /usr/local/bin/yq

    - name: load SSH key
      uses: webfactory/ssh-agent@v0.9.0
      with:
        ssh-private-key: ${{ inputs.vps_ssh_key }}

    - name: render CI config.yaml
      shell: bash
      env:
        ADMIN_PASSWORD_HASH: ${{ inputs.admin_password_hash }}
        AGENT_UPLOAD_TOKEN: ${{ inputs.agent_upload_token }}
        FLASHER_UPLOAD_TOKEN: ${{ inputs.flasher_upload_token }}
        GRAFANA_PASSWORD: ${{ inputs.grafana_password }}
        JUPYTER_PASSWORD_HASH: ${{ inputs.jupyter_password_hash }}
        VPS_HOST: ${{ inputs.vps_host }}
        VPS_SSH_USER: ${{ inputs.vps_ssh_user }}
      run: |
        mkdir -p compose/grafana compose/siteapp compose/flasher
        envsubst < compose/config.ci.yaml.tmpl > config.ci.rendered.yaml
        printf '%s' "$GRAFANA_PASSWORD" > compose/grafana/admin_password
        printf '%s' "$AGENT_UPLOAD_TOKEN" > compose/siteapp/agent_upload_token
        printf '%s' "$FLASHER_UPLOAD_TOKEN" > compose/flasher/upload_token
        chmod 0600 compose/grafana/admin_password compose/siteapp/agent_upload_token compose/flasher/upload_token

    - name: deploy to VPS (stack-only)
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
        VPS_SSH_USER: ${{ inputs.vps_ssh_user }}
        LDS_CONFIG: ${{ github.workspace }}/config.ci.rendered.yaml
        LDS_STACK_ONLY: '1'
        LDS_REQUIRE_VAULT: '1'
        LDS_SSH_OPTS: '-o StrictHostKeyChecking=accept-new'
      run: bash scripts/deploy.sh

    - name: verify siteapp version via /api/public/server-info
      if: inputs.verify_version != ''
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
        EXPECTED_VERSION: ${{ inputs.verify_version }}
      run: |
        set -euo pipefail
        for i in $(seq 1 30); do
          body="$(curl -sk "https://$VPS_HOST/api/public/server-info")" || true
          if echo "$body" | jq -e --arg v "$EXPECTED_VERSION" '.version == $v' >/dev/null; then
            echo "verified: siteapp reports version $EXPECTED_VERSION"
            exit 0
          fi
          sleep 2
        done
        echo "::error::siteapp /api/public/server-info did not report expected version $EXPECTED_VERSION after 60s"
        echo "last body: $body"
        exit 1

    - name: verify flasher container image tag
      if: inputs.verify_version != ''
      shell: bash
      env:
        VPS_HOST: ${{ inputs.vps_host }}
        VPS_SSH_USER: ${{ inputs.vps_ssh_user }}
        EXPECTED_VERSION: ${{ inputs.verify_version }}
      run: |
        set -euo pipefail
        image=""
        for i in $(seq 1 30); do
          image="$(ssh -o StrictHostKeyChecking=accept-new "$VPS_SSH_USER@$VPS_HOST" \
            "docker inspect --format '{{.Config.Image}}' lab-bridge-flasher-1" 2>/dev/null || true)"
          if [[ "$image" == *":$EXPECTED_VERSION" ]]; then
            echo "verified: flasher container running $image"
            exit 0
          fi
          sleep 2
        done
        echo "::error::flasher container did not reach image tag :$EXPECTED_VERSION after 60s (last seen: '$image')"
        exit 1
```

- [ ] **Step 2: YAML lint**

Run:
```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/actions/deploy-stack/action.yml')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Do NOT commit yet** — wait for Task 10.

---

## Task 10: Drop the platform VERSION marker from `scripts/deploy.sh`

The deploy script copies `compose/VERSION` into the rsync stage. After the deletions in Task 6, `compose/VERSION` doesn't exist; remove the stanza that copies it.

**Files:**
- Modify: `scripts/deploy.sh` (lines 77-81)

- [ ] **Step 1: Delete the marker stanza**

Open `scripts/deploy.sh`. Find the block starting at line 77 (or wherever it now lives — the comment begins with `# Platform VERSION marker.`):

```bash
    # Platform VERSION marker. Rsynced to $VPS_REMOTE_ROOT/VERSION on the VPS,
    # where CI's release-platform verify step reads it back to confirm the
    # stack templates from the just-tagged release actually landed.
    install -m 644 "$REPO_ROOT/compose/VERSION" "$stage/VERSION"
```

Delete those four lines entirely (the comment and the `install` command).

- [ ] **Step 2: Sanity-check the script parses**

Run:
```bash
bash -n scripts/deploy.sh && echo "syntax ok"
```

Expected: `syntax ok`.

- [ ] **Step 3: Commit Tasks 8, 9, 10 together**

Run:
```bash
git add .github/workflows/release-please.yml .github/actions/deploy-stack/action.yml scripts/deploy.sh
git commit -m "$(cat <<'EOF'
refactor(release): collapse release workflows to single build+deploy

release-please.yml drops the three release-build-* jobs in favor of
one release-build that builds both images, attests both, and runs
one deploy with a single verify_version input. The deploy-stack
composite action collapses three verify inputs to one. The
scripts/deploy.sh platform VERSION marker stanza is removed
(no longer rsynced; no longer checked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Adjust PR workflows to bypass paths-filter on release-please PRs

**Files:**
- Modify: `.github/workflows/pr-platform.yml` (drop `gate` job, inline paths-filter + bypass)
- Modify: `.github/workflows/pr-siteapp.yml` (add bypass)
- Modify: `.github/workflows/pr-flasher.yml` (add bypass)

- [ ] **Step 1: Rewrite `pr-platform.yml`**

Replace the entire file with:

```yaml
name: pr-platform

on:
  pull_request:
    types: [opened, synchronize, reopened]

concurrency:
  group: pr-platform-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: read
  pull-requests: read

jobs:
  changes:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    outputs:
      run: ${{ steps.should-run.outputs.run }}
      shell: ${{ steps.changed.outputs.shell }}
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

      - id: should-run
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            echo "run=true" >> "$GITHUB_OUTPUT"
            echo "::notice::release-please PR — running full platform suite"
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi

  shellcheck:
    needs: changes
    if: needs.changes.outputs.run == 'true' && needs.changes.outputs.shell == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - name: shellcheck
        run: |
          sudo apt-get update
          sudo apt-get install -y shellcheck
          shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh

  bats:
    needs: changes
    if: needs.changes.outputs.run == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        include:
          - suite: cheap
            files: >-
              tests/integration/test_common.bats
              tests/integration/test_config.bats
              tests/integration/test_crypto.bats
              tests/integration/test_render.bats
              tests/integration/test_secrets.bats
              tests/integration/test_grafana_provisioning.bats
              tests/integration/test_deploy_stack_only.bats
          - suite: deploy
            files: tests/integration/test_deploy.bats
          - suite: ops
            files: tests/integration/test_ops.bats
          - suite: provision
            files: tests/integration/test_provision.bats
          - suite: routes-smoke
            files: tests/integration/test_routes_smoke.bats
    name: bats (${{ matrix.suite }})
    steps:
      - uses: actions/checkout@v4

      - name: install Task
        uses: arduino/setup-task@v2
        with:
          version: 3.x
          repo-token: ${{ secrets.GITHUB_TOKEN }}

      - name: install yq v4
        run: |
          sudo wget -q https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 -O /usr/local/bin/yq
          sudo chmod +x /usr/local/bin/yq
          yq --version

      - name: install bats
        uses: bats-core/bats-action@3.0.1

      - name: bats ${{ matrix.suite }}
        run: bats ${{ matrix.files }}

  # Aggregator: the single required check for branch protection. Succeeds
  # when changes ran and every dependent job either passed or was skipped
  # (e.g., docs-only PRs where changes.outputs.run=='false').
  platform:
    needs: [changes, shellcheck, bats]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: aggregate
        run: |
          set -e
          changes="${{ needs.changes.result }}"
          shellcheck="${{ needs.shellcheck.result }}"
          bats="${{ needs.bats.result }}"
          echo "changes:    $changes"
          echo "shellcheck: $shellcheck"
          echo "bats:       $bats"
          if [[ "$changes" != "success" ]]; then
            echo "::error::changes job did not succeed: $changes"
            exit 1
          fi
          for r in "$shellcheck" "$bats"; do
            case "$r" in
              success|skipped) ;;
              *)
                echo "::error::dependent job failed: $r"
                exit 1
                ;;
            esac
          done
          echo "platform: all required checks pass"
```

Key differences from the old workflow:
- The `gate` job is renamed `changes` (no special-case for release-please PRs other than "run everything"). Its old `labeled` trigger type is removed from the workflow `on:` — the run-integration label is retired.
- The release-please bypass flips the default: release-please PRs run the full bats matrix instead of skipping it.

- [ ] **Step 2: Update `pr-siteapp.yml`**

Open `.github/workflows/pr-siteapp.yml`. Find the block (currently lines 22-32):

```yaml
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - '.github/workflows/pr-siteapp.yml'

      - if: steps.changed.outputs.src != 'true'
        run: echo "no siteapp changes; skipping all steps"
```

Replace with:

```yaml
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - '.github/workflows/pr-siteapp.yml'

      - id: should-run
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            echo "run=true" >> "$GITHUB_OUTPUT"
            echo "::notice::release-please PR — running full siteapp suite"
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi

      - if: steps.should-run.outputs.run != 'true'
        run: echo "no siteapp changes; skipping all steps"
```

Then in the same file, replace **every occurrence** of `if: steps.changed.outputs.src == 'true'` with `if: steps.should-run.outputs.run == 'true'` (10 occurrences — every substantive step).

Use:
```bash
sed -i.bak "s/steps.changed.outputs.src == 'true'/steps.should-run.outputs.run == 'true'/g" .github/workflows/pr-siteapp.yml
rm .github/workflows/pr-siteapp.yml.bak
```

- [ ] **Step 3: Update `pr-flasher.yml`**

Apply the same pattern. Replace the `changed` paths-filter block + the "no flasher changes" echo step with the `should-run` variant, and rename all `steps.changed.outputs.src == 'true'` gates to `steps.should-run.outputs.run == 'true'`.

Find the block (currently lines 22-32):

```yaml
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/flasher/**'
              - '.github/workflows/pr-flasher.yml'

      - if: steps.changed.outputs.src != 'true'
        run: echo "no flasher changes; skipping all steps"
```

Replace with:

```yaml
      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            src:
              - 'services/flasher/**'
              - '.github/workflows/pr-flasher.yml'

      - id: should-run
        run: |
          set -e
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            echo "run=true" >> "$GITHUB_OUTPUT"
            echo "::notice::release-please PR — running full flasher suite"
          else
            echo "run=${{ steps.changed.outputs.src }}" >> "$GITHUB_OUTPUT"
          fi

      - if: steps.should-run.outputs.run != 'true'
        run: echo "no flasher changes; skipping all steps"
```

Then update all `if:` gates:
```bash
sed -i.bak "s/steps.changed.outputs.src == 'true'/steps.should-run.outputs.run == 'true'/g" .github/workflows/pr-flasher.yml
rm .github/workflows/pr-flasher.yml.bak
```

- [ ] **Step 4: YAML lint all three workflows**

Run:
```bash
for f in .github/workflows/pr-platform.yml .github/workflows/pr-siteapp.yml .github/workflows/pr-flasher.yml; do
  python3 -c "import yaml; yaml.safe_load(open('$f'))" && echo "$f: ok"
done
```

Expected: three `ok` lines.

- [ ] **Step 5: Spot-check the gate replacements**

Run:
```bash
grep -n 'steps.changed.outputs.src' .github/workflows/pr-siteapp.yml .github/workflows/pr-flasher.yml
```

Expected: only matches are in the `paths-filter` step's `id: changed` line and the `should-run` step that reads `steps.changed.outputs.src`. No remaining `if: steps.changed.outputs.src == 'true'` gates.

- [ ] **Step 6: Commit**

Run:
```bash
git add .github/workflows/pr-platform.yml .github/workflows/pr-siteapp.yml .github/workflows/pr-flasher.yml
git commit -m "$(cat <<'EOF'
refactor(ci): make release-please PRs run all CI substantively

Adds a should-run gate to pr-siteapp/pr-flasher/pr-platform: regular
PRs continue to fast-skip via dorny/paths-filter; release-please PRs
(head ref release-please--*) bypass and run their full suites. In
pr-platform, the old gate job (which skipped bats unless labeled
run-integration) is replaced by the should-run gate with the opposite
default. The run-integration label is retired.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Delete `.github/workflows/release-please-rebase.yml`

The workflow exists solely to rebase sibling release-please PRs that share a manifest. With one component, there are no siblings.

**Files:**
- Delete: `.github/workflows/release-please-rebase.yml`

- [ ] **Step 1: Delete**

Run:
```bash
git rm .github/workflows/release-please-rebase.yml
```

- [ ] **Step 2: Commit**

Run:
```bash
git commit -m "$(cat <<'EOF'
refactor(ci): delete release-please-rebase workflow

The workflow existed only to rebase sibling release-please PRs that
shared a manifest (release-please-action does not auto-rebase them).
With one release-please component there are no siblings, and the
~190-line rebase machinery is no longer needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Update docs and metadata files

**Files:**
- Modify: `Taskfile.yml` (lines 82-89 — task descriptions)
- Modify: `compose/pins.yaml` (comments around `siteapp_image_repo` and `flasher_image_repo`)
- Modify: `README.md` (drop the per-service VERSION bump example)
- Modify: `CLAUDE.md` (rewrite Branch & release rules + Architecture philosophy bullet)
- Modify: `docs/adding-a-service.md` (drop VERSION/CHANGELOG from step 1, collapse steps 8 and 9)

- [ ] **Step 1: Update `Taskfile.yml`**

Open `Taskfile.yml`. Find the two tasks at lines 82-89:

```yaml
  "siteapp:build-and-push":
    desc: Build and push the siteapp image. Reads version from services/siteapp/VERSION; reads SITEAPP_IMAGE_REPO from compose/pins.yaml (or env override).
    cmd: bash services/siteapp/build.sh

  # --- Flasher image ---
  "flasher:build-and-push":
    desc: Build and push the flasher image. Reads version from services/flasher/VERSION; reads FLASHER_IMAGE_REPO from compose/pins.yaml (or env override).
    cmd: bash services/flasher/build.sh
```

Replace the two `desc:` lines with:

```yaml
  "siteapp:build-and-push":
    desc: Build and push the siteapp image. Reads version from root VERSION; reads SITEAPP_IMAGE_REPO from compose/pins.yaml (or env override).
    cmd: bash services/siteapp/build.sh

  # --- Flasher image ---
  "flasher:build-and-push":
    desc: Build and push the flasher image. Reads version from root VERSION; reads FLASHER_IMAGE_REPO from compose/pins.yaml (or env override).
    cmd: bash services/flasher/build.sh
```

- [ ] **Step 2: Update `compose/pins.yaml` comments**

Open `compose/pins.yaml`. Replace the block at lines 12-20:

```yaml
# GHCR repository for the siteapp image. The image *tag* lives in
# services/siteapp/VERSION; the full reference is
# "${siteapp_image_repo}:$(cat services/siteapp/VERSION)".
siteapp_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-siteapp

# GHCR repository for the flasher image. The image *tag* lives in
# services/flasher/VERSION; the full reference is
# "${flasher_image_repo}:$(cat services/flasher/VERSION)".
flasher_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-flasher
```

with:

```yaml
# GHCR repository for the siteapp image. The image *tag* lives in
# the root VERSION (release-please-managed); the full reference is
# "${siteapp_image_repo}:$(cat VERSION)".
siteapp_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-siteapp

# GHCR repository for the flasher image. The image *tag* lives in
# the root VERSION (release-please-managed); the full reference is
# "${flasher_image_repo}:$(cat VERSION)".
flasher_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-flasher
```

- [ ] **Step 3: Update `README.md`**

Open `README.md`. Replace the block at lines 135-159:

```markdown
### Publishing the siteapp image

Two files control the image reference — no `config.yaml` field is involved:

- **`compose/pins.yaml`** → `siteapp_image_repo` — the GHCR repository path
  (e.g. `ghcr.io/<owner>/lab-bridge-siteapp`).
- **`services/siteapp/VERSION`** — the image tag (e.g. `0.2.0`).

`task siteapp:build-and-push` reads both and builds
`${siteapp_image_repo}:${VERSION}` — no environment variables needed.

To publish a new version manually (requires a PAT with `write:packages` or
an environment with a writable `GITHUB_TOKEN`):

```bash
# 1. Bump the version
echo "0.2.0" > services/siteapp/VERSION
git add services/siteapp/VERSION && git commit -m "chore(siteapp): bump version to 0.2.0"

# 2. Build and push
task siteapp:build-and-push

# 3. Deploy
task deploy
```

CI publishing is being migrated to release-please (automated tag + image
build on merge) — see
`docs/superpowers/specs/2026-05-12-cicd-design.md`.
```

with:

```markdown
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
```

- [ ] **Step 4: Update `CLAUDE.md`**

Open `CLAUDE.md`. Apply three targeted edits.

**Edit A — "Architecture philosophy" → "Invariants" first bullet (line 16).** Replace:

```markdown
- **Each service lives at `services/<name>/`** with its own `VERSION`, `CHANGELOG.md`, `Dockerfile`, `pyproject.toml`, `build.sh`, `app/`, `tests/` (unit), and `tests/e2e/` (service-level e2e against the running container with stubs for upstream deps). Do NOT scatter a service across the repo.
```

with:

```markdown
- **Each service lives at `services/<name>/`** with its own `Dockerfile`, `pyproject.toml`, `build.sh`, `app/`, `tests/` (unit), and `tests/e2e/` (service-level e2e against the running container with stubs for upstream deps). Do NOT scatter a service across the repo. The platform version lives at root `VERSION` and is shared by every service.
```

**Edit B — "Invariants" third bullet (line 18).** Replace:

```markdown
- **Each service is its own release-please component** in `release-please-config.json` + `.release-please-manifest.json`. Commits route to components by **path**, not by Conventional Commits scope. Tag format: `<name>-vX.Y.Z`. The `platform` component (`.`) has `exclude-paths: ["services/<name>", ...]` so service-only changes don't bump platform.
```

with:

```markdown
- **One release-please component covers the whole repo.** Single root `VERSION`, single tag stream `vX.Y.Z`, single release PR at a time. Any commit anywhere informs the next bump. Conventional Commits scope (`feat(siteapp): …`) is decorative — it surfaces in the changelog but does not route the bump.
```

**Edit C — "Invariants" fourth bullet (line 19).** Replace:

```markdown
- **`compose/` is platform-only.** It holds `Caddyfile.tmpl`, `docker-compose.yml.tmpl`, `chisel-users.json.tmpl`, `pins.yaml`, `grafana/`, `loki/`, `VERSION`. **Never put service source code under `compose/<name>/`** — that's the old layout, deliberately renamed.
```

with:

```markdown
- **`compose/` is platform-only.** It holds `Caddyfile.tmpl`, `docker-compose.yml.tmpl`, `chisel-users.json.tmpl`, `pins.yaml`, `grafana/`, `loki/`. **Never put service source code under `compose/<name>/`** — that's the old layout, deliberately renamed.
```

**Edit D — "Branch & release rules" section (lines 25-31).** Replace the entire section:

```markdown
## Branch & release rules

- **`main` is protected. Squash-merge only, linear history.** No direct pushes, no merge-commit, no rebase-merge — release-please depends on squash. Required checks: `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`. Adding a service adds another required check; update branch protection in lockstep.
- **PR titles follow Conventional Commits** (`feat fix chore docs refactor test perf build ci revert`, scope optional). The title becomes the squash subject and is what release-please scans for the version bump.
- **Don't bump versions by hand.** release-please owns `services/<name>/VERSION` and `compose/VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
- **Don't manually push release-tagged images to GHCR.** CI is the only path; manual pushes break the Sigstore attestation.
- **`separate-pull-requests: true`** in `release-please-config.json` — release-please opens one PR per component (e.g. `chore(main): release siteapp 0.3.2`). Don't combine.
```

with:

```markdown
## Branch & release rules

- **`main` is protected. Squash-merge only, linear history.** No direct pushes, no merge-commit, no rebase-merge — release-please depends on squash. Required checks: `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`. Adding a service adds another required check; update branch protection in lockstep.
- **PR titles follow Conventional Commits** (`feat fix chore docs refactor test perf build ci revert`, scope optional). The title becomes the squash subject and is what release-please scans for the version bump.
- **Don't bump the version by hand.** release-please owns root `VERSION`. Don't strip the `# x-release-please-version` annotation — it's the rewrite anchor.
- **Don't manually push release-tagged images to GHCR.** CI is the only path; manual pushes break the Sigstore attestation.
- **Release PRs run full CI.** Regular PRs use paths-filter to fast-skip unrelated workflows; release-please PRs (head ref `release-please--*`) bypass the filter and run every workflow's full suite. The release PR is the integration test gate before the production deploy.
```

**Edit E — "Testing" section, remove the release-please skip note.** Find the bullet (around line 56):

```markdown
- **Release-please PRs default to skip `pr-platform`'s bats** unless labelled `run-integration`. The real integration is the actual VPS deploy on merge (with `verify deployed version` healthcheck for siteapp releases).
```

Replace with:

```markdown
- **Release-please PRs run full `pr-platform` bats** (no opt-in label needed). This is the integration test gate before the production deploy that follows the squash-merge.
```

- [ ] **Step 5: Update `docs/adding-a-service.md`**

Open `docs/adding-a-service.md`. Apply edits to four sections.

**Edit A — section 1 ("Create the service tree"), lines 19-42.** Replace the tree listing:

```
services/<name>/
  Dockerfile
  VERSION                       # "0.1.0 # x-release-please-version"
  CHANGELOG.md                  # "# Changelog\n" (release-please appends on bumps)
  pyproject.toml
  uv.lock
  build.sh                      # copy services/siteapp/build.sh and substitute
  .python-version
  .gitignore
  .dockerignore
  app/
    __init__.py
    main.py                     # FastAPI factory; expose /healthz at minimum
    config.py                   # env-var → Settings
    ...
  tests/
    __init__.py
    conftest.py
    test_*.py                   # unit tests (pytest)
    e2e/                        # service-level e2e — see step 6
```

with (drop the VERSION and CHANGELOG.md entries):

```
services/<name>/
  Dockerfile
  pyproject.toml
  uv.lock
  build.sh                      # copy services/siteapp/build.sh and substitute
  .python-version
  .gitignore
  .dockerignore
  app/
    __init__.py
    main.py                     # FastAPI factory; expose /healthz at minimum
    config.py                   # env-var → Settings
    ...
  tests/
    __init__.py
    conftest.py
    test_*.py                   # unit tests (pytest)
    e2e/                        # service-level e2e — see step 6
```

**Edit B — section 8 ("release-please wiring"), lines 116-146.** Replace the entire section with:

```markdown
## 8. release-please wiring

No per-service release-please entry is needed. The whole repo is one
release-please component; the new service's commits inform the next
unified version bump automatically.

The new service's image tag will be the unified version from root
`VERSION`. Its `build.sh` (mirroring `services/siteapp/build.sh`) must
read `$REPO_ROOT/VERSION`, not a per-service file.
```

**Edit C — section 9 ("release-build job in release-please.yml"), lines 148-164.** Replace with:

```markdown
## 9. release-build steps in release-please.yml

Add two steps to `.github/workflows/release-please.yml`'s `release-build` job, mirroring the existing siteapp/flasher pairs:

```yaml
      - name: build & push <name> image
        if: steps.ref.outputs.mode == 'release'
        id: build-<name>
        uses: docker/build-push-action@v6
        with:
          context: services/<name>
          platforms: linux/amd64
          push: true
          provenance: false
          tags: |
            ghcr.io/${{ github.repository_owner }}/lab-bridge-<name>:${{ steps.ref.outputs.version }}
            ghcr.io/${{ github.repository_owner }}/lab-bridge-<name>:latest
          build-args: |
            LAB_BRIDGE_VERSION=${{ steps.ref.outputs.version }}
            LAB_BRIDGE_GIT_SHA=${{ github.sha }}

      - name: attest <name> build provenance
        if: steps.ref.outputs.mode == 'release'
        uses: actions/attest-build-provenance@v4
        with:
          subject-name: ghcr.io/${{ github.repository_owner }}/lab-bridge-<name>
          subject-digest: ${{ steps.build-<name>.outputs.digest }}
          push-to-registry: true
```

Place the build step alongside the existing `build & push siteapp/flasher`
steps and the attest step alongside the existing attest steps. The single
`deploy + verify` step at the end of the job covers the new service
implicitly (one verify per platform release).

If the new service exposes its own version endpoint and you want a verify
check beyond the existing siteapp HTTP + flasher docker-inspect pair, add
a third verify step in `.github/actions/deploy-stack/action.yml` gated
on `inputs.verify_version != ''`.
```

**Edit D — section "What you should NOT do", line 218.** Replace:

```markdown
- **Don't combine release PRs across services.** `separate-pull-requests: true` is load-bearing.
```

with:

```markdown
- **Don't add a per-service release-please component.** The repo uses a single unified component (see `docs/superpowers/specs/2026-05-17-unified-release-design.md`). Any commit anywhere bumps the unified version.
```

**Edit E — "Don't manually bump VERSION files…" line 220.** Replace:

```markdown
- **Don't manually bump VERSION files or push release-tagged images.** release-please owns those.
```

with:

```markdown
- **Don't manually bump root VERSION or push release-tagged images.** release-please owns the version and CI is the only path to GHCR.
```

- [ ] **Step 6: Commit**

Run:
```bash
git add Taskfile.yml compose/pins.yaml README.md CLAUDE.md docs/adding-a-service.md
git commit -m "$(cat <<'EOF'
docs: update operator/contributor guides for unified versioning

Taskfile and pins.yaml comments now point at root VERSION. README's
manual-bump example is replaced with a "release-please owns it" note.
CLAUDE.md's architecture invariants and branch rules are rewritten
for one release-please component. adding-a-service.md drops the
VERSION/CHANGELOG steps and collapses release wiring to "add two
steps to the existing release-build job".

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Final verification

Walk the worktree state to confirm nothing was missed.

- [ ] **Step 1: Sanity grep for stale references**

Run:
```bash
git grep -nE 'services/(siteapp|flasher)/VERSION|services/(siteapp|flasher)/CHANGELOG\.md|compose/VERSION|LDS_SITEAPP_VERSION_FILE|LDS_FLASHER_VERSION_FILE' -- ':!docs/superpowers/' ':!CHANGELOG.md'
```

Expected: no output (or only matches in this plan or the spec — both of which legitimately reference the old paths historically).

- [ ] **Step 2: Sanity grep for stale workflow refs**

Run:
```bash
git grep -nE 'release-please-rebase|verify_siteapp_version|verify_flasher_version|verify_platform_version|run-integration|release-build-siteapp|release-build-flasher|release-build-platform|separate-pull-requests|include-component-in-tag' -- ':!docs/superpowers/' ':!CHANGELOG.md'
```

Expected: no output.

- [ ] **Step 3: Verify root VERSION exists and reads correctly**

Run:
```bash
test -f VERSION && awk 'NF { print $1; exit }' VERSION
```

Expected: `0.6.1`.

- [ ] **Step 4: YAML validate every changed workflow**

Run:
```bash
for f in .github/workflows/release-please.yml .github/workflows/pr-platform.yml .github/workflows/pr-siteapp.yml .github/workflows/pr-flasher.yml .github/actions/deploy-stack/action.yml; do
  python3 -c "import yaml; yaml.safe_load(open('$f'))" && echo "$f: ok"
done
```

Expected: five `ok` lines.

- [ ] **Step 5: Verify release-please config + manifest**

Run:
```bash
jq -e '.packages["."]."package-name" == "lab-bridge"' release-please-config.json && echo "config: ok"
jq -e '."."  == "0.6.1"' .release-please-manifest.json && echo "manifest: ok"
```

Expected: both lines print `ok`.

- [ ] **Step 6: Verify release-please-rebase.yml is gone**

Run:
```bash
test ! -e .github/workflows/release-please-rebase.yml && echo "deleted: ok"
```

Expected: `deleted: ok`.

- [ ] **Step 7: Verify per-service VERSION/CHANGELOG files are gone**

Run:
```bash
for p in services/siteapp/VERSION services/flasher/VERSION compose/VERSION services/siteapp/CHANGELOG.md services/flasher/CHANGELOG.md; do
  test ! -e "$p" && echo "$p: deleted"
done
```

Expected: five `deleted` lines.

- [ ] **Step 8: Local bats run (optional but recommended)**

If bats and docker are available locally:

```bash
bats tests/integration/test_render.bats
bats tests/integration/test_common.bats
bats tests/integration/test_config.bats
bats tests/integration/test_crypto.bats
```

Expected: all pass. The `test_render.bats` is the most relevant — it exercises the updated `_unified_version` helper.

If bats is not installed, skip and rely on the CI run on the PR.

---

## Task 15: Open the PR

- [ ] **Step 1: Confirm commit list**

Run:
```bash
git log main..HEAD --oneline
```

Expected: 7 commits in this order (subjects):
1. `refactor(release): point all VERSION readers at new root VERSION`
2. `refactor(release): delete per-service VERSION and CHANGELOG files`
3. `refactor(release): collapse release-please to a single component`
4. `refactor(release): collapse release workflows to single build+deploy`
5. `refactor(ci): make release-please PRs run all CI substantively`
6. `refactor(ci): delete release-please-rebase workflow`
7. `docs: update operator/contributor guides for unified versioning`

- [ ] **Step 2: Push the branch**

Run:
```bash
git push -u origin refactor/unified-release
```

- [ ] **Step 3: Open the PR**

Run:
```bash
gh pr create --title "refactor(release): unify versioning into single platform release" --body "$(cat <<'EOF'
## Summary

- Collapses the three-component release-please topology into one: single root `VERSION`, single tag stream `vX.Y.Z`, single release-build job, single deploy verify.
- Deletes the `release-please-rebase.yml` hack (~190 LOC) — no more sibling-PR manifest conflicts because there's only one component.
- Regular PRs run only the modified workflow (paths-filter); release-please PRs bypass and run every workflow's full suite.

Spec: `docs/superpowers/specs/2026-05-17-unified-release-design.md`
Plan: `docs/superpowers/plans/2026-05-17-unified-release.md`

## Pre-merge action required

Before squash-merging this PR, push a `v0.6.1` tag at the same commit as `platform-v0.6.1` so release-please has a tag boundary in its new config format:

```bash
git tag v0.6.1 platform-v0.6.1
git push origin v0.6.1
```

Without this tag, release-please's first run after merge will scan all of main history (still correct, but slower and noisier).

## What lands

- Root `VERSION` file owns the unified semver. Per-service `VERSION` and `CHANGELOG.md` files are deleted.
- `release-please-config.json` collapses to one component (`lab-bridge`) with `extra-files: ["VERSION"]`, no `separate-pull-requests`, no `include-component-in-tag`.
- `.github/workflows/release-please.yml` collapses from 253 LOC (three `release-build-*` jobs) to ~110 LOC (one `release-build` building both images).
- `.github/actions/deploy-stack/action.yml` collapses three `verify_*_version` inputs to one `verify_version`.
- `scripts/lib/render.sh`'s `_siteapp_image`/`_flasher_image` helpers delegate to a shared `_unified_version()` that reads root `VERSION`.
- `pr-platform.yml`'s `gate` job and the `run-integration` label are retired; all three `pr-*` workflows gain a release-please bypass that forces the full suite on release-please-branch PRs.
- `scripts/deploy.sh` drops the platform VERSION rsync marker stanza.

## Test plan

- [ ] Local `bats tests/integration/test_render.bats` passes (exercises the new `_unified_version` helper)
- [ ] CI green on this PR (this PR is a regular PR; only modified workflows run substantively)
- [ ] After merge: release-please opens a release PR for the inferred next version
- [ ] On the release PR: all three `pr-*` workflows run substantively (release-please bypass active)
- [ ] After release-PR merge: `release-build` builds both images at `:<version>`, attests, deploys, verifies via siteapp `/api/public/server-info` + flasher `docker inspect`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Record the PR URL**

The `gh pr create` output is the PR URL. Share it back to the user.

---

## Notes for the executor

- **Squash-merge only.** Do NOT merge with a merge commit or rebase. The 7 commits in this branch will be squashed into one on merge.
- **Branch protection is unchanged.** Required checks (`pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`) keep the same names; their internal gating changes but the aggregator names do not.
- **Don't run the destructive cleanup commands suggested by the tooling** (e.g. `git clean -fd`). The plan does not introduce any state that needs cleaning.
- **If a bats test fails after Task 5**, do NOT skip ahead. The most likely cause is a missed `LDS_VERSION_FILE` env var name change or a leftover reference to `LDS_SITEAPP_VERSION_FILE`. Re-check the diff against the plan and re-run the test.
- **If release-please CI fails on the first push of the refactor branch** (i.e., the dev PR, not the post-merge release PR), inspect the manifest validation step — release-please-action runs in dry-run mode on PRs and may complain about manifest schema. The plan's manifest is valid for `release-please-action@v5`; double-check JSON syntax with `jq .`.

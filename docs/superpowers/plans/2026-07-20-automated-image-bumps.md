# Automated Third-Party Image Bumps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A studio release in `bioexperiment-lab-devices/lab-devices` opens, CI-checks, and auto-merges a `feat:` image-pin bump in this repo with no laptop involvement; any of the nine pins can also be bumped from the Actions UI.

**Architecture:** One `workflow_dispatch` entry point (`.github/workflows/image-bump.yml`) callable both cross-repo (from lab-devices, after its GHCR push) and from the Actions UI. It mints an org GitHub App token, checks out with it, delegates to the existing `scripts/images.sh bump`, then enables squash auto-merge on the PR that script opened. Hardening lands in `images.sh` — not the workflow — so the cheap-tier bats suite covers it and the laptop path benefits too.

**Tech Stack:** GitHub Actions, `actions/create-github-app-token@v3`, `gh` CLI, bash, `yq` v4, bats-core.

Spec: `docs/superpowers/specs/2026-07-20-automated-image-bumps-design.md`

## Global Constraints

- Version strings must match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` — validated in `images.sh` before the value reaches `yq` or any shell interpolation.
- The nine allowed services are exactly: `jupyter chisel loki grafana studio authelia prometheus node_exporter cadvisor`.
- Bump commits are typed `feat:` — `chore` is hidden in `release-please-config.json` and would never ship.
- The bump PR MUST be opened with the GitHub App token, never `GITHUB_TOKEN` — PRs authored by `GITHUB_TOKEN` do not trigger `pull_request` workflows, so required checks never report and auto-merge hangs forever.
- `tests/integration/test_images_cli.bats` runs in `pr-platform.yml`'s `bats-cheap` job. Do NOT add a fake-VPS bring-up or a new bats matrix cell.
- In `images.sh`, never end a function with a bare `[[ ... ]] && cmd` — under `set -e` a false condition makes the function return 1 and kills the script. Use `if ... fi`.
- Existing test env knobs: `LDS_IMAGES_FILE`, `LDS_REPO_DIR`, `LDS_NO_GIT`, `LDS_SKIP_REGISTRY_CHECK`.

---

### Task 1: Reject malformed version strings in `images.sh`

**Files:**
- Modify: `scripts/images.sh` (in `cmd_bump`, after the `_known_service` check)
- Test: `tests/integration/test_images_cli.bats`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `cmd_bump` exits 1 with a message containing `invalid version` when the version does not match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`. Later tasks rely on validation happening *before* any file write, registry probe, or git operation.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_images_cli.bats`:

```bash
@test "images bump: rejects a version with shell metacharacters" {
    run bash "$ROOT/scripts/images.sh" bump studio '1.0.0; rm -rf /'
    [ "$status" -ne 0 ]
    [[ "$output" == *"invalid version"* ]] || false

    # Refused before the yq write. 0.3.0 is what the fixture pins.
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [[ "$output" == *":0.3.0"* ]] || false
}

@test "images bump: rejects a version starting with a separator" {
    run bash "$ROOT/scripts/images.sh" bump studio '-1.0.0'
    [ "$status" -ne 0 ]
    [[ "$output" == *"invalid version"* ]] || false
}

@test "images bump: rejects an empty-ish version of only whitespace" {
    run bash "$ROOT/scripts/images.sh" bump studio '   '
    [ "$status" -ne 0 ]
    [[ "$output" == *"invalid version"* ]] || false
}

@test "images bump: accepts a normal semver tag" {
    run bash "$ROOT/scripts/images.sh" bump studio 1.2.3
    [ "$status" -eq 0 ]
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [[ "$output" == *":1.2.3"* ]] || false
}

@test "images bump: accepts a date-style tag with underscores and dots" {
    run bash "$ROOT/scripts/images.sh" bump jupyter 2026-04-20_x.1
    [ "$status" -eq 0 ]
    run yq e '.jupyter_image' "$LDS_IMAGES_FILE"
    [[ "$output" == *":2026-04-20_x.1"* ]] || false
}
```

Note: every `[[ ]]` assertion above ends with `|| false`. A bare `[[ ]]` that fails mid-test does NOT fail a bats test — it is a known repo-wide footgun.

The fixture pins `ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0` and `grafana/grafana:11.3.0` — the tests above and in later tasks depend on both values.

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_images_cli.bats`
Expected: the three "rejects" tests FAIL (status 0 instead of non-zero, no "invalid version" text). The two "accepts" tests already PASS — they guard against an over-strict regex.

- [ ] **Step 3: Add the validation**

In `scripts/images.sh`, inside `cmd_bump`, immediately after the `_known_service` check and before `[[ -f "$IMAGES_FILE" ]]`:

```bash
    # Validate before anything touches yq, the registry probe, or git. The
    # version arrives from a cross-repo workflow_dispatch input, so treat it
    # as untrusted: allow exactly what a Docker tag allows (leading
    # alphanumeric, then alphanumerics/dot/dash/underscore, max 128 chars).
    [[ "$version" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] \
        || die "invalid version '$version' — must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\$"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_images_cli.bats`
Expected: all tests PASS (11 pre-existing + 5 new = 16).

- [ ] **Step 5: Commit**

```bash
git add scripts/images.sh tests/integration/test_images_cli.bats
git commit -m "feat(images): validate version format before any mutation"
```

---

### Task 2: Emit the PR URL to `$GITHUB_OUTPUT`

**Files:**
- Modify: `scripts/images.sh` (`_open_pr`)
- Test: `tests/integration/test_images_cli.bats`

**Interfaces:**
- Consumes: Task 1's validation (already-invalid versions never reach here).
- Produces: when `GITHUB_OUTPUT` is set and a PR is created, `_open_pr` appends a single line `pr_url=<url>` to that file. When `cmd_bump` short-circuits on an already-pinned version, nothing is appended — the workflow in Task 4 keys off this emptiness to skip auto-merge.

- [ ] **Step 1: Write the failing tests**

First extend `teardown()` at the top of the file so the sidecar is cleaned up:

```bash
teardown() {
    # `if`, not `[[ ... ]] && rm`: bats runs teardown under errexit, so a
    # false condition on a non-final line would abort teardown and fail the
    # test whenever SIDECAR was never created.
    if [[ -n "${SIDECAR:-}" && -d "$SIDECAR" ]]; then
        rm -rf "$SIDECAR"
    fi
    teardown_tmpdir
}
```

Then append to `tests/integration/test_images_cli.bats`. These tests need a real pushable remote and a fake `gh`, so add these helpers directly above them:

```bash
# CRITICAL: both helpers write OUTSIDE $TMPDIR. $TMPDIR *is* the scratch git
# repo, and _require_clean_tree rejects untracked files — a bare repo or a
# bin/ dir created inside it would make every test using them fail with
# "git working tree is not clean". SIDECAR is torn down with $TMPDIR.
_sidecar() {
    if [[ -z "${SIDECAR:-}" ]]; then
        # `TMPDIR=/tmp` on this call is NOT redundant: mktemp honours $TMPDIR,
        # and setup_tmpdir exported TMPDIR as the scratch repo itself — a bare
        # `mktemp -d` would create the sidecar *inside* the repo, which is the
        # exact untracked-file problem this helper exists to avoid.
        SIDECAR="$(TMPDIR=/tmp mktemp -d)"
        export SIDECAR
    fi
}

# A local bare repo standing in for `origin`, so `git push` in _open_pr
# succeeds without network. Call after _scratch_repo.
_scratch_remote() {
    _sidecar
    git init -q --bare "$SIDECAR/origin.git"
    git -C "$TMPDIR" remote add origin "$SIDECAR/origin.git"
}

# Put a fake `gh` first on PATH. It prints a PR URL on stdout, which is what
# _open_pr captures. Real `gh` would need network and auth.
_fake_gh() {
    _sidecar
    mkdir -p "$SIDECAR/bin"
    cat >"$SIDECAR/bin/gh" <<'SH'
#!/usr/bin/env bash
echo "https://github.com/example/repo/pull/999"
SH
    chmod +x "$SIDECAR/bin/gh"
    export PATH="$SIDECAR/bin:$PATH"
}

@test "images bump: writes pr_url to GITHUB_OUTPUT when a PR is opened" {
    _scratch_repo
    _scratch_remote
    _fake_gh

    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        LDS_SKIP_REGISTRY_CHECK=1 LDS_NO_GIT=0 \
        GITHUB_OUTPUT="$SIDECAR/gh_output" \
        PATH="$PATH" \
        bash "$ROOT/scripts/images.sh" bump grafana 13.0.0
    [ "$status" -eq 0 ]

    run cat "$SIDECAR/gh_output"
    [[ "$output" == *"pr_url=https://github.com/example/repo/pull/999"* ]] || false
}

@test "images bump: an already-pinned version writes no pr_url and still exits 0" {
    _scratch_repo
    _scratch_remote
    _fake_gh
    : >"$SIDECAR/gh_output"

    # 11.3.0 is what the fixture already pins for grafana.
    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        LDS_SKIP_REGISTRY_CHECK=1 LDS_NO_GIT=0 \
        GITHUB_OUTPUT="$SIDECAR/gh_output" \
        PATH="$PATH" \
        bash "$ROOT/scripts/images.sh" bump grafana 11.3.0
    [ "$status" -eq 0 ]
    [[ "$output" == *"already at"* ]] || false

    run cat "$SIDECAR/gh_output"
    [ -z "$output" ]
}

@test "images bump: succeeds with GITHUB_OUTPUT unset" {
    _scratch_repo
    _scratch_remote
    _fake_gh
    unset GITHUB_OUTPUT

    run env -u GITHUB_OUTPUT LDS_REPO_DIR="$TMPDIR" \
        LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        LDS_SKIP_REGISTRY_CHECK=1 LDS_NO_GIT=0 PATH="$PATH" \
        bash "$ROOT/scripts/images.sh" bump grafana 13.0.0
    [ "$status" -eq 0 ]
}
```

The third test is the `set -e` guard: it fails if the emission is written as a bare `[[ -n ... ]] && printf`, because a false condition would make `_open_pr` return 1.

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_images_cli.bats`
Expected: the first test FAILS (no `pr_url` line in the output file). The other two may already pass; they must still pass at the end.

- [ ] **Step 3: Implement the emission**

In `scripts/images.sh`, replace the `gh pr create` line at the end of `_open_pr`:

```bash
    git -C "$REPO_DIR" push -u origin "$branch"
    # Capture the PR URL so CI can auto-merge this exact PR rather than
    # re-deriving the branch name and coupling the workflow to the naming
    # scheme here. `gh pr create` prints the URL as its last stdout line.
    local url
    url="$( cd "$REPO_DIR" && gh pr create --title "$subject" --body "$body" --base main --head "$branch" | tail -n1 )"
    printf '%s\n' "$url"
    # `if`, not `[[ ... ]] && printf`: under `set -e` a false condition as the
    # function's last command would make _open_pr return 1 and abort the run
    # whenever GITHUB_OUTPUT is unset (i.e. every laptop invocation).
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        printf 'pr_url=%s\n' "$url" >>"$GITHUB_OUTPUT"
    fi
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_images_cli.bats`
Expected: all PASS (19 total).

- [ ] **Step 5: Commit**

```bash
git add scripts/images.sh tests/integration/test_images_cli.bats
git commit -m "feat(images): emit pr_url to GITHUB_OUTPUT for CI auto-merge"
```

---

### Task 3: Detect a pre-existing *remote* branch

**Files:**
- Modify: `scripts/images.sh` (`_checkout_new_branch`)
- Test: `tests/integration/test_images_cli.bats`

**Interfaces:**
- Consumes: Task 2's `_scratch_remote` and `_fake_gh` bats helpers.
- Produces: `_checkout_new_branch` exits 1 with the same actionable message for a remote branch as for a local one. No new callers.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_images_cli.bats`:

```bash
@test "images bump: a pre-existing REMOTE branch dies with an actionable message" {
    _scratch_repo
    _scratch_remote
    _fake_gh

    # Simulate a prior run whose PR was closed but whose branch still exists
    # on the remote. A fresh CI checkout has no local branch, so only the
    # remote check can catch this.
    git -C "$TMPDIR" push -q origin HEAD:refs/heads/images/grafana-13.0.0

    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        LDS_SKIP_REGISTRY_CHECK=1 LDS_NO_GIT=0 PATH="$PATH" \
        bash "$ROOT/scripts/images.sh" bump grafana 13.0.0
    # die()'s exit 1, not a raw git push rejection (exit 128 / 1 with
    # "rejected" text). Require the guidance string only our message has.
    [ "$status" -eq 1 ]
    [[ "$output" == *"images/grafana-13.0.0"* ]] || false
    [[ "$output" == *"merge/close its PR"* ]] || false
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/integration/test_images_cli.bats -f "REMOTE branch"`
Expected: FAIL — the run currently gets past the branch guard and fails later (or succeeds), without the `merge/close its PR` guidance.

- [ ] **Step 3: Add the remote check**

In `scripts/images.sh`, extend `_checkout_new_branch`:

```bash
_checkout_new_branch() {
    local branch="$1"
    git -C "$REPO_DIR" show-ref --verify --quiet "refs/heads/$branch" \
        && die "branch '$branch' already exists in $REPO_DIR — delete it (git -C '$REPO_DIR' branch -D $branch) or merge/close its PR before re-running"
    # Also check the remote. A fresh CI checkout never has the local branch,
    # but the remote one survives a closed PR — without this the run dies on
    # a raw `git push` rejection instead of an actionable message.
    if git -C "$REPO_DIR" ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
        die "branch '$branch' already exists on origin — delete it (git -C '$REPO_DIR' push origin --delete $branch) or merge/close its PR before re-running"
    fi
    git -C "$REPO_DIR" checkout -b "$branch"
}
```

- [ ] **Step 4: Run the full file to verify**

Run: `bats tests/integration/test_images_cli.bats`
Expected: all PASS (20 total). The pre-existing local-branch test must still pass — it uses a scratch repo with no `origin`, and `ls-remote` failing there is handled by the `if`.

- [ ] **Step 5: Commit**

```bash
git add scripts/images.sh tests/integration/test_images_cli.bats
git commit -m "fix(images): catch a pre-existing remote branch with a clear message"
```

---

### Task 4: The `image-bump` workflow

**Files:**
- Create: `.github/workflows/image-bump.yml`

**Interfaces:**
- Consumes: `scripts/images.sh bump <service> <version>`; the `pr_url` output from Task 2; version validation from Task 1.
- Produces: a `workflow_dispatch` endpoint with inputs `service` (choice, nine options) and `version` (string), callable cross-repo via `gh workflow run image-bump.yml -R <owner>/lab_devices_server -f service=... -f version=...`.

- [ ] **Step 1: Create the workflow**

```yaml
name: image-bump

# One entry point for both callers: the operator via the Actions UI, and
# lab-devices' release-please via the cross-repo workflow_dispatch API.
# repository_dispatch would only add a second payload shape to validate.
on:
  workflow_dispatch:
    inputs:
      service:
        description: Which external image pin to bump
        required: true
        type: choice
        options:
          - jupyter
          - chisel
          - loki
          - grafana
          - studio
          - authelia
          - prometheus
          - node_exporter
          - cadvisor
      version:
        description: New tag (e.g. 0.11.0). Validated by scripts/images.sh.
        required: true
        type: string

# Serialise per service so two releases cannot race on the same pin.
concurrency:
  group: image-bump-${{ inputs.service }}
  cancel-in-progress: false

# Minimal: the App token below carries what git and gh actually need.
permissions:
  contents: read

jobs:
  bump:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      # The App token is load-bearing. A PR opened with GITHUB_TOKEN does not
      # trigger `pull_request` workflows, so the required checks would never
      # report and auto-merge would hang forever.
      - id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}

      - uses: actions/checkout@v4
        with:
          # Persisted so images.sh's `git push` authenticates as the App.
          token: ${{ steps.app-token.outputs.token }}

      - name: install yq v4
        run: |
          sudo wget -q https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 -O /usr/local/bin/yq
          sudo chmod +x /usr/local/bin/yq
          yq --version

      - name: configure git identity
        run: |
          git config user.name  "bioexperiment-release-please[bot]"
          git config user.email "bioexperiment-release-please[bot]@users.noreply.github.com"

      # images.sh validates the version format and the service allowlist, and
      # verifies the tag is anonymously pullable, before it commits anything.
      # It writes pr_url to $GITHUB_OUTPUT only when it actually opens a PR.
      - id: bump
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: bash scripts/images.sh bump "${{ inputs.service }}" "${{ inputs.version }}"

      - name: enable auto-merge
        if: steps.bump.outputs.pr_url != ''
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
        run: gh pr merge --squash --auto "${{ steps.bump.outputs.pr_url }}"

      - name: summary
        run: |
          if [ -n "${{ steps.bump.outputs.pr_url }}" ]; then
            echo "Opened and auto-merge-enabled: ${{ steps.bump.outputs.pr_url }}" >>"$GITHUB_STEP_SUMMARY"
          else
            echo "No PR — ${{ inputs.service }} is already pinned at ${{ inputs.version }}." >>"$GITHUB_STEP_SUMMARY"
          fi
```

- [ ] **Step 2: Verify the YAML parses and the inputs match the allowlist**

```bash
yq e '.on.workflow_dispatch.inputs.service.options[]' .github/workflows/image-bump.yml | sort >/tmp/wf_services
grep -o '_SERVICES=(.*)' scripts/images.sh | sed -E 's/^_SERVICES=\(//; s/\)$//' | tr ' ' '\n' | grep -v '^$' | sort >/tmp/sh_services
diff /tmp/wf_services /tmp/sh_services && echo "ALLOWLISTS MATCH"
```

Expected: `ALLOWLISTS MATCH`, no diff output.

- [ ] **Step 3: Confirm the workflow does not widen the platform CI gate**

The `heavy` paths-filter in `pr-platform.yml` lists `.github/workflows/pr-platform.yml` specifically, not `.github/workflows/**`, so this new file does not itself trigger the fake-VPS matrix. This PR still runs heavy because it touches `scripts/**` and `tests/integration/**` — that is intended.

Run: `grep -n "pr-platform.yml" .github/workflows/pr-platform.yml`
Expected: the single `heavy:` filter entry, unchanged.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/image-bump.yml
git commit -m "feat(ci): add image-bump workflow for dispatchable pin bumps"
```

---

### Task 5: Renovate de-confliction and documentation

**Files:**
- Modify: `renovate.json`
- Modify: `CLAUDE.md` (the "Config split" section)
- Modify: `README.md`
- Create: `docs/lab-devices-dispatch-snippet.md`

**Interfaces:**
- Consumes: the workflow name `image-bump.yml` from Task 4.
- Produces: no code interfaces. Final task.

- [ ] **Step 1: Exclude studio from Renovate**

Without this, Renovate opens a competing monthly `chore` bump for a pin the automated `feat:` path already moves — two PRs racing on one line.

In `renovate.json`, add to `packageRules`:

```json
    {
      "description": "experiment-studio is bumped automatically by lab-devices' release-please via the image-bump workflow. Renovate would open a competing monthly chore PR on the same line.",
      "matchPackageNames": ["ghcr.io/bioexperiment-lab-devices/experiment-studio"],
      "enabled": false
    }
```

Verify the file still parses:

```bash
yq -p=json e '.packageRules | length' renovate.json
```

Expected: `3`

- [ ] **Step 2: Document the lab-devices side**

Create `docs/lab-devices-dispatch-snippet.md`:

````markdown
# lab-devices → lab_devices_server bump dispatch

Applied in `bioexperiment-lab-devices/lab-devices`, not this repo. Add to that
repo's `.github/workflows/release-please.yml`:

```yaml
  dispatch-bump:
    needs: [release-please, image]
    if: ${{ needs.release-please.outputs.release_created == 'true' }}
    runs-on: ubuntu-latest
    steps:
      - id: app-token
        uses: actions/create-github-app-token@v3
        with:
          app-id: ${{ vars.RELEASE_PLEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_PLEASE_APP_KEY }}
          # Required: without these the token is scoped to lab-devices only.
          owner: bioexperiment-lab-devices
          repositories: lab_devices_server
      - env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          TAG: ${{ needs.release-please.outputs.tag_name }}
        run: |
          gh workflow run image-bump.yml \
            -R bioexperiment-lab-devices/lab_devices_server \
            -f service=studio \
            -f version="${TAG#v}"
```

`needs: image` is required, not stylistic: `images.sh` probes the registry
before it commits, so dispatching before the GHCR push completes would fail on
a tag that does not yet exist.

## Manual prerequisite

The org App behind `RELEASE_PLEASE_APP_ID` needs **Actions: read & write**, and
its installation must cover both repos. If the grant is missing the dispatch
step fails with a 403 and no bump PR is opened — a loud failure, not a silent
one.
````

- [ ] **Step 3: Update `CLAUDE.md`**

In the "Config split" section, extend the `compose/images.yaml` bullet:

```markdown
- **External image pins → `compose/images.yaml`** (tracked). Nine externally-released images (jupyter, chisel, loki, grafana, studio, authelia, prometheus, node_exporter, cadvisor). Bump with `task images:bump -- <service> <version>`, which lands one releasable `feat:` PR. Image-only edits skip the fake-VPS bats matrix. **`studio` bumps itself**: lab-devices' release-please dispatches `.github/workflows/image-bump.yml` after its GHCR push, which opens the `feat:` PR and enables auto-merge — Renovate is disabled for that one pin to avoid a competing PR (see `docs/lab-devices-dispatch-snippet.md`). The other eight stay on Renovate's monthly grouped `chore` bumps, shipped with `task images:ship`. Any pin can also be moved by hand from the Actions UI via the `image-bump` workflow.
```

- [ ] **Step 4: Update `README.md`**

Find the section documenting `task images:bump` and add after it:

```markdown
Image pins can also be bumped without a laptop: run the **image-bump** workflow
from the Actions tab (or `gh workflow run image-bump.yml -f service=<name> -f
version=<tag>`). It opens the same `feat:` PR and enables auto-merge, so a green
CI run lands it. Experiment Studio does this automatically on every lab-devices
release.
```

- [ ] **Step 5: Verify and commit**

```bash
yq -p=json e '.' renovate.json >/dev/null && echo "renovate.json OK"
bats tests/integration/test_images_cli.bats
git add renovate.json CLAUDE.md README.md docs/lab-devices-dispatch-snippet.md
git commit -m "docs: document automated studio bumps and disable Renovate for that pin"
```

Expected: `renovate.json OK`, all 20 bats tests pass.

---

## Post-merge verification (operator, not part of the PR)

1. Grant the org App **Actions: read & write** and confirm its installation covers both repos.
2. Live smoke: run the `image-bump` workflow with `service=studio, version=0.10.0` (the currently-pinned version). Expected: green run, no PR, summary reads "already pinned". This exercises App auth, checkout, and the registry probe while mutating nothing.
3. Apply `docs/lab-devices-dispatch-snippet.md` in the lab-devices repo.
4. The next studio release should open its own bump PR within a minute of its GHCR push.

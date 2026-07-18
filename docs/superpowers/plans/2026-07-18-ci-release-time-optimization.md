# CI & Release-Time Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut an external-image bump from ~55 min across 3 PRs down to ~12–15 min on 1 PR, by splitting image pins into their own file (so image-only PRs skip the fake-VPS bats matrix), collapsing the pin+ship dance into one releasable `feat:` PR, and lowering the fake-VPS bringup floor that every heavy cell pays.

**Architecture:** Three independent levers from `docs/superpowers/specs/2026-07-18-ci-release-time-optimization-design.md`. (A) `compose/images.yaml` holds the nine externally-released image refs; `pr-platform.yml` splits its `bats` job into `bats-cheap` (always) and `bats-heavy` (fake-VPS matrix, skipped for image-only edits). (B) `scripts/images.sh` gains `bump`/`ship` subcommands wired to `task images:bump` / `task images:ship`, following the existing `scripts/secrets.sh` subcommand convention. (C) Preload becomes profile-driven and derives its image set from the test fixture; no-bringup pre-flight tests move out of `test_deploy.bats` into the cheap tier.

**Tech Stack:** Bash 5 + `yq` v4 (YAML surgery), bats-core (tests), GitHub Actions + `dorny/paths-filter@v3`, release-please (simple release type), Renovate (custom regex manager), Taskfile v3.

## Global Constraints

- **Never move the `*_image_repo` keys** (`siteapp_image_repo`, `flasher_image_repo`, `streamer_image_repo`, `caddy_image_repo`, `authelia_image_repo`) out of `compose/pins.yaml`. Their tag comes from the root `VERSION`, so they are platform changes and MUST keep triggering the full heavy suite.
- `compose/config.ci.yaml.tmpl`'s `chisel_clients` MUST stay `[]` (vault guard `LDS_REQUIRE_VAULT=1` fails the CI deploy otherwise).
- The single required branch-protection check stays named **`platform`** (the aggregator job in `pr-platform.yml`). Do not rename it; do not add new required checks.
- The release-please bypass MUST be preserved: a `release-please--*` head ref forces the full heavy matrix.
- `release-please-config.json` marks `chore` hidden. Bump commits MUST use a releasable type (`feat`) or they will not deploy.
- Bats files that bring up the fake-VPS MUST keep the `compose_images_available` skip guard (mirror `test_routes_smoke.bats:11-14`).
- Laptop has **no Docker**. Any test that requires the fake-VPS can only be verified in CI. Tests added to the cheap tier MUST run without Docker.
- All commits use Conventional Commits; PR title becomes the squash subject.

---

### Task 1: Split `compose/images.yaml` out of `pins.yaml`

**Files:**
- Create: `compose/images.yaml`
- Create: `tests/integration/fixtures/valid_images.yaml`
- Modify: `compose/pins.yaml` (remove the nine external image keys)
- Modify: `scripts/lib/config.sh:11-16` (add images loader), `:28-50` (field lists), `:63-99` (validate), `:176-213` (load/export)
- Modify: `tests/integration/helpers.bash:291-307` (fixture wiring), `:227-234` (`bootstrap_authelia_for_tests` reads `authelia_image`)
- Test: `tests/integration/test_config.bats`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `compose/images.yaml` and `tests/integration/fixtures/valid_images.yaml`; env var `LDS_IMAGES_FILE` (override path, mirrors `LDS_PINS_FILE`); `config.sh` functions `_default_images_file()` and array `_REQUIRED_IMAGES_FIELDS`; `load_config` exports unchanged names (`JUPYTER_IMAGE`, `CHISEL_IMAGE`, `LOKI_IMAGE`, `GRAFANA_IMAGE`, `STUDIO_IMAGE`, `AUTHELIA_IMAGE`, `PROMETHEUS_IMAGE`, `NODE_EXPORTER_IMAGE`, `CADVISOR_IMAGE`) plus new `IMAGES_PATH`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_config.bats`:

```bash
@test "validate_config: accepts valid config with split images file" {
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: missing images file gives clear error" {
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; LDS_PINS_FILE=$TMPDIR/pins.yaml LDS_IMAGES_FILE=$TMPDIR/nope.yaml validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"images file not found"* ]]
}

@test "validate_config: rejects images file missing a required image key" {
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    yq -i 'del(.studio_image)' "$TMPDIR/images.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; LDS_PINS_FILE=$TMPDIR/pins.yaml LDS_IMAGES_FILE=$TMPDIR/images.yaml validate_config $ROOT/tests/integration/fixtures/valid_config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"studio_image"* ]]
}

@test "load_config: exports image vars sourced from images.yaml" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$STUDIO_IMAGE \$GRAFANA_IMAGE \$CADVISOR_IMAGE"
    [ "$status" -eq 0 ]
    [[ "$output" == *"experiment-studio"* ]]
    [[ "$output" == *"grafana"* ]]
    [[ "$output" == *"cadvisor"* ]]
}

@test "pins.yaml no longer carries external image keys" {
    run yq e '.studio_image // "absent"' "$ROOT/compose/pins.yaml"
    [ "$output" = "absent" ]
    run yq e '.siteapp_image_repo' "$ROOT/compose/pins.yaml"
    [[ "$output" == *"lab-bridge-siteapp"* ]]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_config.bats`
Expected: FAIL — the new tests error because `compose/images.yaml` and `fixtures/valid_images.yaml` do not exist and `LDS_IMAGES_FILE` is ignored.

- [ ] **Step 3: Create `compose/images.yaml`**

Move the nine external image keys here verbatim, carrying their load-bearing comments:

```yaml
# Externally-released container images. These are built and released OUTSIDE
# this repo's unified VERSION stream, so a bump here is not a platform change.
# Renovate-managed (see renovate.json customManager); bump via
# `task images:bump -- <service> <version>`.
#
# Kept separate from pins.yaml so CI can tell an image-only bump from an
# infrastructure change: pr-platform.yml skips the fake-VPS bats matrix when
# only this file changed. Do NOT add ports, retention, paths, or *_image_repo
# keys here — those belong in pins.yaml and must trigger the full suite.

jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
loki_image: grafana/loki:3.2.1
grafana_image: grafana/grafana:11.3.0

# Experiment Studio — operator UI for lab_devices experiments. Built and
# released by the bioexperiment-lab-devices/lab-devices repo. MUST be >= 0.3.0
# (sub-path portability behind the stripped /studio route; 0.2.0 emits absolute
# URLs and breaks).
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.8.0

# Authelia identity provider.
authelia_image: authelia/authelia:4.38.10

prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
# cadvisor must be >= v0.54.0 to read container stats under Docker's new
# `overlayfs` storage driver (default on Ubuntu 24.04 with Docker 28+).
# Older versions fail with "Failed to identify the read-write layer ID"
# and never attach the `name` label, leaving every container_* panel empty.
# Registry: from v0.56 onwards cadvisor only publishes to ghcr.io/google/cadvisor
# (the legacy gcr.io/cadvisor/cadvisor mirror stopped at v0.54.x).
cadvisor_image: ghcr.io/google/cadvisor:v0.57.0
```

- [ ] **Step 4: Remove those nine keys from `compose/pins.yaml`**

Delete `jupyter_image`, `chisel_image`, `loki_image`, `grafana_image`, `studio_image`, `authelia_image`, `prometheus_image`, `node_exporter_image`, `cadvisor_image` (and the comment blocks that moved with them). Keep `chisel_listen_port`, `loki_retention_days`, `prometheus_retention_days`, every `*_image_repo`, `acme_email`, `remote_root`, `notebooks_path`, `ssh_port`. Update the file's header comment to say image refs now live in `compose/images.yaml`.

- [ ] **Step 5: Create `tests/integration/fixtures/valid_images.yaml`**

Mirrors the fixture values previously in `valid_pins.yaml` (note `authelia_image` is a test-local ref, and `studio_image` stays `0.3.0` to match what the fake-VPS deploys):

```yaml
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
loki_image: grafana/loki:3.2.1
grafana_image: grafana/grafana:11.3.0
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0
authelia_image: ghcr.io/test/lab-bridge-authelia:0.0.0
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: ghcr.io/google/cadvisor:v0.57.0
```

Then delete those same nine keys from `tests/integration/fixtures/valid_pins.yaml`.

- [ ] **Step 6: Add the images loader to `scripts/lib/config.sh`**

After `_default_pins_file()` (line 16), add:

```bash
# Override via LDS_IMAGES_FILE for tests / CI assembly.
_default_images_file() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    printf '%s/../../compose/images.yaml' "$script_dir"
}
```

Remove the nine image entries from `_REQUIRED_PINS_FIELDS` and add below it:

```bash
# Required fields in images.yaml (externally-released images).
_REQUIRED_IMAGES_FIELDS=(
    .jupyter_image
    .chisel_image
    .loki_image
    .grafana_image
    .studio_image
    .authelia_image
    .prometheus_image
    .node_exporter_image
    .cadvisor_image
)
```

- [ ] **Step 7: Validate the images file in `validate_config`**

In `validate_config`, after the `pins_path` resolution (line 66) add:

```bash
    local images_path="${LDS_IMAGES_FILE:-$(_default_images_file)}"
```

After the pins existence check (line 76) add:

```bash
    if [[ ! -f "$images_path" ]]; then
        printf 'images file not found: %s (set LDS_IMAGES_FILE or place at compose/images.yaml)\n' "$images_path" >&2
        return 1
    fi
```

After the pins YAML check (line 85) add:

```bash
    if ! _yq e '.' "$images_path" >/dev/null; then
        printf 'images is not valid YAML: %s\n' "$images_path" >&2
        return 1
    fi
```

After the `_REQUIRED_PINS_FIELDS` loop (line 99) add:

```bash
    for field in "${_REQUIRED_IMAGES_FIELDS[@]}"; do
        val="$(_yq e "$field // \"\"" "$images_path")"
        if [[ -z "$val" || "$val" == "null" ]]; then
            errors+=("images: missing required field: ${field#.}")
        fi
    done
```

- [ ] **Step 8: Read image vars from the images file in `load_config`**

In `load_config`, after the `pins_path` local (line 179) add:

```bash
    local images_path="${LDS_IMAGES_FILE:-$(_default_images_file)}"
```

After `export PINS_PATH="$pins_path"` add `export IMAGES_PATH="$images_path"`. Then repoint the nine image reads from `"$pins_path"` to `"$images_path"`:

```bash
    export JUPYTER_IMAGE         ; JUPYTER_IMAGE="$(_yq e '.jupyter_image' "$images_path")"
    export CHISEL_IMAGE          ; CHISEL_IMAGE="$(_yq e '.chisel_image' "$images_path")"
    export LOKI_IMAGE            ; LOKI_IMAGE="$(_yq e '.loki_image' "$images_path")"
    export GRAFANA_IMAGE         ; GRAFANA_IMAGE="$(_yq e '.grafana_image' "$images_path")"
    export STUDIO_IMAGE          ; STUDIO_IMAGE="$(_yq e '.studio_image' "$images_path")"
    export AUTHELIA_IMAGE        ; AUTHELIA_IMAGE="$(_yq e '.authelia_image' "$images_path")"
    export PROMETHEUS_IMAGE      ; PROMETHEUS_IMAGE="$(_yq e '.prometheus_image' "$images_path")"
    export NODE_EXPORTER_IMAGE   ; NODE_EXPORTER_IMAGE="$(_yq e '.node_exporter_image' "$images_path")"
    export CADVISOR_IMAGE        ; CADVISOR_IMAGE="$(_yq e '.cadvisor_image' "$images_path")"
```

Leave `CHISEL_LISTEN_PORT`, `LOKI_RETENTION_DAYS`, `PROMETHEUS_RETENTION_DAYS` and every `*_IMAGE_REPO` reading from `"$pins_path"`. Update the header comment block (lines 5-9) to describe the three-file split.

- [ ] **Step 9: Wire the fixture into `helpers.bash`**

In `fake_vps_up_with_users` (after line 307) add:

```bash
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
```

Add `#   LDS_IMAGES_FILE   — path to the rendered images.yaml` to the exported-vars comment (line 289). In `bootstrap_authelia_for_tests` (line 231) change the source file:

```bash
    AUTHELIA_IMAGE="$(yq e '.authelia_image' "$ROOT/compose/images.yaml")"
```

Apply the same two-line fixture copy + `LDS_IMAGES_FILE` export to `test_deploy.bats`'s `setup_file()` (after line 25) and `setup()` (after line 63), since that file wires its fixtures inline rather than via `fake_vps_up_with_users`.

- [ ] **Step 10: Repoint the `authelia_image` fallback in `scripts/secrets.sh`**

`scripts/secrets.sh:246-251` reads `authelia_image` straight from `pins.yaml`
when `AUTHELIA_IMAGE` isn't already exported. After the split that key is gone
from `pins.yaml`, so this fallback would `die "authelia_image not set"`. Change
it to read the images file:

```bash
        local authelia_image="${AUTHELIA_IMAGE:-}"
        if [[ -z "$authelia_image" ]]; then
            local images_path="${LDS_IMAGES_FILE:-$SCRIPT_DIR/../compose/images.yaml}"
            authelia_image="$(yq e '.authelia_image' "$images_path")"
            [[ -n "$authelia_image" && "$authelia_image" != "null" ]] \
                || die "authelia_image not set in $images_path"
        fi
```

Update the surrounding comments (lines 228, 242-244) that say "from
compose/pins.yaml" to reference `compose/images.yaml`.

No change is needed in `compose/docker-compose.yml.tmpl` or
`compose/config.ci.yaml.tmpl`: they use `__*_IMAGE__` placeholders substituted
by `render.sh` from the exported variables, whose names are unchanged.

- [ ] **Step 11: Run the tests**

Run: `bats tests/integration/test_config.bats tests/integration/test_render.bats tests/integration/test_secrets.bats`
Expected: PASS (these are cheap-tier, no Docker required).

- [ ] **Step 12: Commit**

```bash
git add compose/images.yaml compose/pins.yaml scripts/lib/config.sh scripts/secrets.sh \
        tests/integration/fixtures/valid_images.yaml tests/integration/fixtures/valid_pins.yaml \
        tests/integration/helpers.bash tests/integration/test_config.bats tests/integration/test_deploy.bats
git commit -m "refactor: split external image pins into compose/images.yaml"
```

---

### Task 2: Repoint Renovate and update the config-split docs

**Files:**
- Modify: `renovate.json` (customManager `fileMatch`)
- Modify: `CLAUDE.md` ("Config split" section)
- Modify: `docs/adding-a-service.md`
- Test: `tests/integration/test_config.bats`

**Interfaces:**
- Consumes: `compose/images.yaml` from Task 1.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_config.bats`:

```bash
@test "renovate tracks compose/images.yaml, not pins.yaml" {
    run yq -o=json e '.customManagers[0].fileMatch[0]' "$ROOT/renovate.json"
    [ "$status" -eq 0 ]
    [[ "$output" == *"images"* ]]
    [[ "$output" != *"pins"* ]]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/integration/test_config.bats -f renovate`
Expected: FAIL — `fileMatch` still reads `^compose/pins\.yaml$`.

- [ ] **Step 3: Update `renovate.json`**

Change the customManager `fileMatch`:

```json
      "fileMatch": ["^compose/images\\.yaml$"],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bats tests/integration/test_config.bats -f renovate`
Expected: PASS

- [ ] **Step 5: Update the docs**

In `CLAUDE.md`, replace the first bullet of "## Config split" with:

```markdown
- **External image pins → `compose/images.yaml`** (tracked). Nine externally-released images (jupyter, chisel, loki, grafana, studio, authelia, prometheus, node_exporter, cadvisor). Bump with `task images:bump -- <service> <version>`, which lands one releasable `feat:` PR. Image-only edits skip the fake-VPS bats matrix.
- **Paths, ports, retention, `*_image_repo` → `compose/pins.yaml`** (tracked). Not `config.yaml`. A change here DOES trigger the full platform suite.
```

In `docs/adding-a-service.md`, update any step that says to add an image pin to `pins.yaml` so external images go to `compose/images.yaml` (and note that `*_image_repo` for repo-built services stays in `pins.yaml`).

- [ ] **Step 6: Commit**

```bash
git add renovate.json CLAUDE.md docs/adding-a-service.md tests/integration/test_config.bats
git commit -m "docs: repoint Renovate and config-split rules at compose/images.yaml"
```

---

### Task 3: Split `pr-platform.yml` into `bats-cheap` and `bats-heavy`

**Files:**
- Modify: `.github/workflows/pr-platform.yml`
- Test: `tests/integration/test_config.bats`

**Interfaces:**
- Consumes: `compose/images.yaml` from Task 1.
- Produces: workflow outputs `changes.outputs.heavy` and `changes.outputs.images`; jobs `bats-cheap` and `bats-heavy`; aggregator `platform` unchanged in name.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_config.bats`:

```bash
@test "pr-platform: heavy filter excludes compose/images.yaml" {
    run yq e '.jobs.changes.steps[] | select(.id == "changed") | .with.filters' \
        "$ROOT/.github/workflows/pr-platform.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == *"'!compose/images.yaml'"* ]]
}

@test "pr-platform: has separate cheap and heavy bats jobs" {
    run yq e '.jobs | keys | .[]' "$ROOT/.github/workflows/pr-platform.yml"
    [[ "$output" == *"bats-cheap"* ]]
    [[ "$output" == *"bats-heavy"* ]]
}

@test "pr-platform: platform aggregator still needs both bats jobs" {
    run yq e '.jobs.platform.needs | .[]' "$ROOT/.github/workflows/pr-platform.yml"
    [[ "$output" == *"bats-cheap"* ]]
    [[ "$output" == *"bats-heavy"* ]]
}

@test "pr-platform: release-please refs still force the heavy suite" {
    run grep -c 'release-please--' "$ROOT/.github/workflows/pr-platform.yml"
    [ "$output" -ge 1 ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_config.bats -f pr-platform`
Expected: FAIL — there is one `bats` job and no `!compose/images.yaml` negation.

- [ ] **Step 3: Rewrite the `changes` job filters and outputs**

Replace `.github/workflows/pr-platform.yml` lines 19-48 with:

```yaml
    outputs:
      heavy: ${{ steps.should-run.outputs.heavy }}
      any: ${{ steps.should-run.outputs.any }}
      shell: ${{ steps.changed.outputs.shell }}
    steps:
      - uses: actions/checkout@v4

      - id: changed
        uses: dorny/paths-filter@v3
        with:
          filters: |
            heavy:
              # NOT '!compose/images.yaml' as a separate entry:
              # dorny/paths-filter@v3 combines a rule's patterns with some(),
              # so a bare negation matches every path that ISN'T images.yaml —
              # a catch-all that makes heavy true for every PR (including
              # docs-only ones, regressing their <30s fast-skip). Keep the
              # '/**' too: 'compose/!(images.yaml)' does not cross '/' and
              # would drop compose/grafana/** and compose/loki/**.
              - 'compose/**/!(images.yaml)'
              - 'scripts/**'
              - 'tests/integration/**'
              - 'config.example.yaml'
              - 'Taskfile.yml'
              - '.github/workflows/pr-platform.yml'
            images:
              - 'compose/images.yaml'
            shell:
              - 'scripts/**/*.sh'

      - id: should-run
        name: determine which suites should run
        run: |
          set -e
          heavy="${{ steps.changed.outputs.heavy }}"
          images="${{ steps.changed.outputs.images }}"
          if [[ "${{ github.head_ref }}" == release-please--* ]]; then
            heavy=true
            echo "::notice::release-please PR — running full platform suite"
          fi
          any=false
          if [[ "$heavy" == "true" || "$images" == "true" ]]; then
            any=true
          fi
          echo "heavy=$heavy" >> "$GITHUB_OUTPUT"
          echo "any=$any"     >> "$GITHUB_OUTPUT"
          echo "heavy=$heavy any=$any"
```

- [ ] **Step 4: Regate `shellcheck` and split the bats job**

Change the `shellcheck` job's `if` to:

```yaml
    if: needs.changes.outputs.heavy == 'true' && needs.changes.outputs.shell == 'true'
```

Replace the single `bats` job with two. `bats-cheap` runs the no-fake-VPS files:

```yaml
  bats-cheap:
    needs: changes
    if: needs.changes.outputs.any == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    name: bats (cheap)
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
      - name: bats cheap
        run: |
          bats tests/integration/test_common.bats \
               tests/integration/test_config.bats \
               tests/integration/test_crypto.bats \
               tests/integration/test_render.bats \
               tests/integration/test_secrets.bats \
               tests/integration/test_grafana_provisioning.bats \
               tests/integration/test_deploy_stack_only.bats \
               tests/integration/test_service_selection_render.bats
```

`bats-heavy` keeps the existing matrix minus the `cheap` cell, and keeps the `free disk space` step (now unconditional, since every remaining cell is heavy):

```yaml
  bats-heavy:
    needs: changes
    if: needs.changes.outputs.heavy == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 35
    strategy:
      fail-fast: false
      matrix:
        include:
          - suite: deploy
            files: tests/integration/test_deploy.bats
          - suite: ops
            files: tests/integration/test_ops.bats
          - suite: provision
            files: tests/integration/test_provision.bats
          - suite: routes-smoke
            files: tests/integration/test_routes_smoke.bats
          - suite: metrics-smoke
            files: tests/integration/test_metrics_smoke.bats
          - suite: navbar
            files: tests/integration/test_navbar_smoke.bats
          - suite: auth
            files: tests/integration/test_auth_smoke.bats
          - suite: service-selection
            files: tests/integration/test_service_selection.bats
    name: bats (${{ matrix.suite }})
```

Keep the existing step list from the old `bats` job for `bats-heavy`, deleting the `if: matrix.suite != 'cheap'` condition on `free disk space`. Preserve the explanatory comment about the 35-minute cap.

- [ ] **Step 5: Update the aggregator**

```yaml
  platform:
    needs: [changes, shellcheck, bats-cheap, bats-heavy]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: aggregate
        run: |
          set -e
          changes="${{ needs.changes.result }}"
          shellcheck="${{ needs.shellcheck.result }}"
          cheap="${{ needs.bats-cheap.result }}"
          heavy="${{ needs.bats-heavy.result }}"
          echo "changes:    $changes"
          echo "shellcheck: $shellcheck"
          echo "bats-cheap: $cheap"
          echo "bats-heavy: $heavy"
          if [[ "$changes" != "success" ]]; then
            echo "::error::changes job did not succeed: $changes"
            exit 1
          fi
          for r in "$shellcheck" "$cheap" "$heavy"; do
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

- [ ] **Step 6: Run the tests**

Run: `bats tests/integration/test_config.bats -f pr-platform`
Expected: PASS

Also confirm the workflow still parses: `yq e '.jobs | keys' .github/workflows/pr-platform.yml`
Expected: lists `changes`, `shellcheck`, `bats-cheap`, `bats-heavy`, `platform`.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/pr-platform.yml tests/integration/test_config.bats
git commit -m "ci: split platform bats into cheap and heavy jobs, skip heavy for image-only PRs"
```

---

### Task 4: `scripts/images.sh bump` + `task images:bump`

**Files:**
- Create: `scripts/images.sh`
- Create: `tests/integration/test_images_cli.bats`
- Modify: `Taskfile.yml`
- Modify: `.github/workflows/pr-platform.yml` (add the new test file to the cheap list)

**Interfaces:**
- Consumes: `compose/images.yaml` from Task 1; `LDS_IMAGES_FILE` override from Task 1.
- Produces: `scripts/images.sh` with subcommand `bump <service> <version>`; honours `LDS_IMAGES_FILE`, and `LDS_SKIP_REGISTRY_CHECK=1` to bypass the network manifest probe in tests. Service names are the `*_image` keys minus the suffix: `jupyter chisel loki grafana studio authelia prometheus node_exporter cadvisor`.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_images_cli.bats`:

```bash
#!/usr/bin/env bats

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    export LDS_SKIP_REGISTRY_CHECK=1
}
teardown() { teardown_tmpdir; }

@test "images bump: rewrites the tag for a known service" {
    run bash "$ROOT/scripts/images.sh" bump studio 9.9.9
    [ "$status" -eq 0 ]
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [[ "$output" == *"experiment-studio:9.9.9"* ]]
}

@test "images bump: preserves the repository, changing only the tag" {
    bash "$ROOT/scripts/images.sh" bump grafana 12.0.0
    run yq e '.grafana_image' "$LDS_IMAGES_FILE"
    [ "$output" = "grafana/grafana:12.0.0" ]
}

@test "images bump: rejects an unknown service with the allowed list" {
    run bash "$ROOT/scripts/images.sh" bump nosuchsvc 1.0.0
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown service"* ]]
    [[ "$output" == *"studio"* ]]
}

@test "images bump: rejects a core repo-built service name" {
    run bash "$ROOT/scripts/images.sh" bump siteapp 1.0.0
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown service"* ]]
}

@test "images bump: requires both service and version" {
    run bash "$ROOT/scripts/images.sh" bump studio
    [ "$status" -ne 0 ]
    [[ "$output" == *"usage"* ]]
}

@test "images bump: leaves other image keys untouched" {
    bash "$ROOT/scripts/images.sh" bump studio 9.9.9
    run yq e '.grafana_image' "$LDS_IMAGES_FILE"
    [ "$output" = "grafana/grafana:11.3.0" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_images_cli.bats`
Expected: FAIL — `scripts/images.sh` does not exist.

- [ ] **Step 3: Create `scripts/images.sh`**

```bash
#!/usr/bin/env bash
# Manage externally-released image pins in compose/images.yaml.
#
#   images.sh bump <service> <version>   bump one image and open a feat: PR
#   images.sh ship                       cut a release for pins already on main
#
# `bump` commits with a RELEASABLE type (feat:) on purpose — release-please
# marks `chore` hidden, so a chore-typed pin never cuts a release and the new
# image sits on main undeployed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGES_FILE="${LDS_IMAGES_FILE:-$ROOT/compose/images.yaml}"

_SERVICES=(jupyter chisel loki grafana studio authelia prometheus node_exporter cadvisor)

die() { printf '%s\n' "$*" >&2; exit 1; }

_known_service() {
    local svc want="$1"
    for svc in "${_SERVICES[@]}"; do
        [[ "$svc" == "$want" ]] && return 0
    done
    return 1
}

# Verify the target reference is a real, anonymously-pullable image before
# touching git. Skipped in tests via LDS_SKIP_REGISTRY_CHECK=1.
#
# NOTE: an earlier draft of this plan carried a naive implementation here that
# was WRONG for 7 of the 9 real pins. Two bugs, both verified against live
# registries: (a) it prefixed single-slash Docker Hub refs (jpillora/chisel,
# grafana/grafana, prom/prometheus, ...) with "library/", which only applies to
# official single-NAME images; (b) Docker Hub delegates token auth to
# auth.docker.io, not registry-1.docker.io, so the token request 401'd.
# quay.io additionally needs an empty-bearer-token request. See the shipped
# scripts/images.sh for the correct resolution logic and
# .superpowers/sdd/task-4-report.md for the per-registry evidence.
_verify_pullable() {
    ...  # see scripts/images.sh — resolve registry/path per-registry, then
         # GET /v2/<path>/manifests/<tag> with the right Accept headers and
         # require HTTP 200.
}

cmd_bump() {
    local svc="${1:-}" version="${2:-}"
    [[ -n "$svc" && -n "$version" ]] || die "usage: images.sh bump <service> <version>"
    _known_service "$svc" \
        || die "unknown service '$svc' (allowed: ${_SERVICES[*]})"
    [[ -f "$IMAGES_FILE" ]] || die "images file not found: $IMAGES_FILE"

    local key current repo new
    key=".${svc}_image"
    current="$(yq e "$key" "$IMAGES_FILE")"
    [[ -n "$current" && "$current" != "null" ]] || die "no such key in $IMAGES_FILE: ${svc}_image"
    repo="${current%:*}"
    new="${repo}:${version}"
    if [[ "$current" == "$new" ]]; then
        printf 'already at %s\n' "$new"
        return 0
    fi
    _verify_pullable "$new"
    yq -i "$key = \"$new\"" "$IMAGES_FILE"
    printf 'bumped %s: %s -> %s\n' "$svc" "$current" "$new"
}

main() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        bump) cmd_bump "$@" ;;
        *)    die "usage: images.sh {bump} [args]" ;;
    esac
}

main "$@"
```

Make it executable: `chmod +x scripts/images.sh`

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_images_cli.bats`
Expected: PASS (all six)

- [ ] **Step 5: Add the Task entry**

In `Taskfile.yml`, add after the `deploy:rollback` entry:

```yaml
  "images:bump":
    desc: "Bump an external image pin and open a releasable PR (e.g. task images:bump -- studio 0.9.0)"
    cmd: bash scripts/images.sh bump {{.CLI_ARGS}}
```

- [ ] **Step 6: Register the new test file in the cheap suite**

In `.github/workflows/pr-platform.yml`, add `tests/integration/test_images_cli.bats` to the `bats cheap` file list.

- [ ] **Step 7: Verify shellcheck cleanliness**

Run: `shellcheck -x --severity=warning scripts/images.sh`
Expected: no warnings (CI runs this same command over `scripts/*.sh`).

- [ ] **Step 8: Commit**

```bash
git add scripts/images.sh Taskfile.yml tests/integration/test_images_cli.bats .github/workflows/pr-platform.yml
git commit -m "feat: add task images:bump for one-PR external image bumps"
```

---

### Task 5: `scripts/images.sh ship` + `task images:ship` + git/PR automation

**Files:**
- Modify: `scripts/images.sh` (add `ship`, add branch/commit/PR automation to `bump`)
- Modify: `tests/integration/test_images_cli.bats`
- Modify: `Taskfile.yml`

**Interfaces:**
- Consumes: `scripts/images.sh` from Task 4.
- Produces: subcommand `ship`; `LDS_NO_GIT=1` makes `bump` edit the file only (no branch/commit/PR) — the Task 4 tests rely on this, so they must set it; `LDS_REPO_DIR` overrides which git repo the git/PR helpers act on (defaults to `$ROOT`), so tests can point at a scratch repo.

- [ ] **Step 1: Write the failing tests**

Add to `tests/integration/test_images_cli.bats` (and add `export LDS_NO_GIT=1` to its `setup()` so the existing tests keep editing files only):

```bash
# Build a throwaway git repo so the git-touching paths never act on the real
# checkout. LDS_REPO_DIR is what points images.sh at it.
_scratch_repo() {
    git -C "$TMPDIR" init -q .
    git -C "$TMPDIR" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
}

@test "images ship: refuses when git working tree is dirty" {
    _scratch_repo
    touch "$TMPDIR/dirty"
    git -C "$TMPDIR" add dirty
    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        bash "$ROOT/scripts/images.sh" ship --dry-run
    [ "$status" -ne 0 ]
    [[ "$output" == *"working tree"* ]]
}

@test "images ship: dry-run prints the releasable commit subject" {
    _scratch_repo
    run env LDS_REPO_DIR="$TMPDIR" LDS_IMAGES_FILE="$TMPDIR/images.yaml" \
        bash "$ROOT/scripts/images.sh" ship --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"feat:"* ]]
}

@test "images bump: dry-run prints the subject and does NOT modify the file" {
    local before
    before="$(yq e '.studio_image' "$LDS_IMAGES_FILE")"
    run bash "$ROOT/scripts/images.sh" bump studio 9.9.9 --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"feat:"* ]]
    [[ "$output" == *"studio"* ]]
    run yq e '.studio_image' "$LDS_IMAGES_FILE"
    [ "$output" = "$before" ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_images_cli.bats -f ship`
Expected: FAIL — `ship` is not a known subcommand.

- [ ] **Step 3: Add git/PR automation and `ship` to `scripts/images.sh`**

Add the repo-dir indirection near the top, beside `IMAGES_FILE`:

```bash
# Git operations act on this repo. Overridable so tests can use a scratch repo
# instead of the real checkout.
REPO_DIR="${LDS_REPO_DIR:-$ROOT}"
```

Add these helpers above `main`:

```bash
_require_clean_tree() {
    git -C "$REPO_DIR" diff --quiet && git -C "$REPO_DIR" diff --cached --quiet \
        || die "git working tree is not clean — commit or stash first"
}

# _open_pr <branch> <subject> <body> — branch, commit staged changes, push, PR.
_open_pr() {
    local branch="$1" subject="$2" body="$3"
    git -C "$REPO_DIR" checkout -b "$branch"
    git -C "$REPO_DIR" commit -q -m "$subject" -m "$body"
    git -C "$REPO_DIR" push -u origin "$branch"
    gh pr create --title "$subject" --body "$body" --base main --head "$branch"
}
```

Extend `cmd_bump`. **Order matters:** parse `--dry-run` and return *before*
`_verify_pullable` and `yq -i`, so a dry run neither hits the network nor
modifies the file. Replace the tail of `cmd_bump` (from the `_verify_pullable`
call onward) with:

```bash
    local subject body branch dry_run=0
    [[ "${*: -1}" == "--dry-run" ]] && dry_run=1
    subject="feat: bump ${svc} image to ${version}"
    body="Bumps \`${svc}_image\` from \`${current}\` to \`${new}\` in compose/images.yaml.

Typed \`feat:\` deliberately: release-please marks \`chore\` hidden, so a
chore-typed pin never cuts a release and the image would sit on main
undeployed. This single PR both pins and ships the image.

Image verified pullable before commit."

    if (( dry_run )); then
        printf '%s\n' "$subject"
        return 0
    fi

    _verify_pullable "$new"
    yq -i "$key = \"$new\"" "$IMAGES_FILE"
    printf 'bumped %s: %s -> %s\n' "$svc" "$current" "$new"

    [[ "${LDS_NO_GIT:-0}" == "1" ]] && return 0
    branch="images/${svc}-${version}"
    git -C "$REPO_DIR" add "$IMAGES_FILE"
    _open_pr "$branch" "$subject" "$body"
```

Add `cmd_ship`:

```bash
cmd_ship() {
    local subject body
    subject="feat: ship pinned images to the stack"
    body="Empty by design — compose/images.yaml already holds the intended pins
on main. Renovate lands image bumps as \`chore\`, which release-please marks
hidden, so those pins never cut a release on their own. This commit carries a
releasable type so release-build deploys them."
    if [[ "${1:-}" == "--dry-run" ]]; then
        _require_clean_tree
        printf '%s\n' "$subject"
        return 0
    fi
    _require_clean_tree
    git -C "$REPO_DIR" checkout -b "images/ship-$(git -C "$REPO_DIR" rev-parse --short HEAD)"
    git -C "$REPO_DIR" commit -q --allow-empty -m "$subject" -m "$body"
    git -C "$REPO_DIR" push -u origin HEAD
    gh pr create --title "$subject" --body "$body" --base main
}
```

Register it in `main`:

```bash
        bump) cmd_bump "$@" ;;
        ship) cmd_ship "$@" ;;
        *)    die "usage: images.sh {bump|ship} [args]" ;;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_images_cli.bats`
Expected: PASS (all nine)

- [ ] **Step 5: Add the Task entry**

```yaml
  "images:ship":
    desc: "Cut a release for image pins already merged to main (e.g. Renovate chore bumps)"
    cmd: bash scripts/images.sh ship {{.CLI_ARGS}}
```

- [ ] **Step 6: Verify shellcheck cleanliness**

Run: `shellcheck -x --severity=warning scripts/images.sh`
Expected: no warnings

- [ ] **Step 7: Commit**

```bash
git add scripts/images.sh Taskfile.yml tests/integration/test_images_cli.bats
git commit -m "feat: add task images:ship and PR automation for image bumps"
```

---

### Task 6: Profile-driven preload + per-suite stack trimming

**Files:**
- Modify: `tests/integration/helpers.bash:118-160` (`preload_fake_vps_images`, `compose_images_available`)
- Modify: `.github/workflows/pr-platform.yml` (pass `LDS_SUITE_PROFILE` per matrix cell)

**Interfaces:**
- Consumes: `tests/integration/fixtures/valid_images.yaml` from Task 1.
- Produces: `preload_fake_vps_images` and `compose_images_available` both honour `LDS_SUITE_PROFILE` (values: `full` (default), `core`); helper `_profile_images()` prints the image list for the active profile, derived from the fixture.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_common.bats`:

```bash
@test "_profile_images: core profile omits the heavy optional images" {
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=core _profile_images"
    [ "$status" -eq 0 ]
    [[ "$output" != *"scipy-notebook"* ]]
    [[ "$output" != *"experiment-studio"* ]]
    [[ "$output" == *"caddy"* ]]
    [[ "$output" == *"authelia"* ]]
}

@test "_profile_images: full profile includes every fixture image" {
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [ "$status" -eq 0 ]
    [[ "$output" == *"scipy-notebook"* ]]
    [[ "$output" == *"experiment-studio"* ]]
    [[ "$output" == *"grafana"* ]]
}

@test "_profile_images: reads tags from the fixture, not hardcoded values" {
    local fixture_studio
    fixture_studio="$(yq e '.studio_image' "$ROOT/tests/integration/fixtures/valid_images.yaml")"
    run bash -c "source $ROOT/tests/integration/helpers.bash; LDS_SUITE_PROFILE=full _profile_images"
    [[ "$output" == *"$fixture_studio"* ]]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_common.bats -f _profile_images`
Expected: FAIL — `_profile_images` is not defined.

- [ ] **Step 3: Replace the hardcoded image lists in `helpers.bash`**

Replace the bodies of `preload_fake_vps_images` (line 118) and `compose_images_available` (line 141) so both consume one derived list:

```bash
# Image set the active suite profile needs, derived from the test fixture so a
# fixture bump can never silently desync the preload list.
#
#   full (default) — the whole stack, including the multi-GB scipy-notebook
#                    and the studio image
#   core           — caddy/chisel/authelia only; for suites that assert nothing
#                    about jupyter, studio, or the monitoring group
_profile_images() {
    local fixture="$ROOT/tests/integration/fixtures/valid_images.yaml"
    local profile="${LDS_SUITE_PROFILE:-full}"
    printf '%s\n' caddy:2
    yq e '.chisel_image' "$fixture"
    yq e '.authelia_image' "$fixture"
    [[ "$profile" == "core" ]] && return 0
    yq e '.loki_image' "$fixture"
    yq e '.grafana_image' "$fixture"
    yq e '.jupyter_image' "$fixture"
    yq e '.studio_image' "$fixture"
}

preload_fake_vps_images() {
    local img
    while IFS= read -r img; do
        [[ -z "$img" ]] && continue
        if docker image inspect "$img" >/dev/null 2>&1; then
            _save_and_load_into_fake_vps "$img" || true
        fi
    done < <(_profile_images)
}

compose_images_available() {
    local img
    while IFS= read -r img; do
        [[ -z "$img" ]] && continue
        if ! docker image inspect "$img" >/dev/null 2>&1; then
            if ! docker pull "$img" >/dev/null 2>&1; then
                return 1
            fi
        fi
    done < <(_profile_images)
    return 0
}
```

Keep the existing explanatory comments above both functions (rate-limit rationale, skip-guard contract).

- [ ] **Step 4: Set `disabled_services` for core-profile suites**

In `helpers.bash`'s `fake_vps_up_with_users`, after the config copy (line 303) add:

```bash
    # A `core` profile suite asserts nothing about jupyter/studio/monitoring,
    # so don't deploy them — this skips both their preload and their startup.
    if [[ "${LDS_SUITE_PROFILE:-full}" == "core" ]]; then
        yq -i '.disabled_services = ["jupyter", "studio", "monitoring"]' "$TMPDIR/config.yaml"
    fi
```

- [ ] **Step 5: Pass the profile from the workflow matrix**

In `.github/workflows/pr-platform.yml`'s `bats-heavy` matrix, add a `profile` key per cell — `core` only for suites that assert nothing about jupyter/studio/monitoring:

```yaml
          - suite: deploy
            files: tests/integration/test_deploy.bats
            profile: full
          - suite: ops
            files: tests/integration/test_ops.bats
            profile: full
          - suite: provision
            files: tests/integration/test_provision.bats
            profile: core
          - suite: routes-smoke
            files: tests/integration/test_routes_smoke.bats
            profile: full
          - suite: metrics-smoke
            files: tests/integration/test_metrics_smoke.bats
            profile: full
          - suite: navbar
            files: tests/integration/test_navbar_smoke.bats
            profile: full
          - suite: auth
            files: tests/integration/test_auth_smoke.bats
            profile: core
          - suite: service-selection
            files: tests/integration/test_service_selection.bats
            profile: full
```

And set it on the bats step:

```yaml
      - name: bats ${{ matrix.suite }}
        env:
          LDS_SUITE_PROFILE: ${{ matrix.profile }}
        run: bats ${{ matrix.files }}
```

**Conservatism note:** start with `core` only on `provision` and `auth`. If a CI run shows either failing because it needed a trimmed service, move that cell back to `full` rather than weakening the assertions.

- [ ] **Step 6: Run the tests**

Run: `bats tests/integration/test_common.bats`
Expected: PASS. The fake-VPS suites cannot run on this laptop (no Docker) — they are verified by CI on the PR.

- [ ] **Step 7: Verify shellcheck cleanliness**

Run: `shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh`
Expected: no warnings (helpers.bash is not in CI's shellcheck glob, but keep it clean).

- [ ] **Step 8: Commit**

```bash
git add tests/integration/helpers.bash tests/integration/test_common.bats .github/workflows/pr-platform.yml
git commit -m "test: derive fake-VPS preload from fixture and trim per-suite stack"
```

---

### Task 7: Extract no-bringup pre-flight tests out of `test_deploy.bats`

**Files:**
- Create: `tests/integration/test_deploy_preflight.bats`
- Create: `tests/integration/fixtures/valid_users_database.yml`
- Modify: `tests/integration/test_deploy.bats` (remove the five extracted tests)
- Modify: `.github/workflows/pr-platform.yml` (add the new file to the cheap list)

**Interfaces:**
- Consumes: `valid_images.yaml` + `LDS_IMAGES_FILE` from Task 1.
- Produces: nothing consumed by later tasks.

**Why these five:** each asserts `deploy.sh` fails during validation *before* touching the VPS, so none needs a running fake-VPS. `deploy.sh` gates in this order — grafana password (`:70`), users_db exists (`:100`), users_db non-empty (`:103`), agent token (`:111`) — so the fixture must satisfy every gate *earlier* than the one under test.

- [ ] **Step 1: Create the static users-database fixture**

`tests/integration/fixtures/valid_users_database.yml` — a literal argon2 hash, so no Docker/Authelia run is needed:

```yaml
users:
  _stub:
    displayname: Stub
    password: '$argon2id$v=19$m=65536,t=3,p=4$iNzLZUasKgeeGpEP6ugJBA$59JMNV5RK+f4FPe/XZh+pljt5iEuzt8P4CcLBKp/izQ'
    email: stub@example.invalid
    groups: []
```

- [ ] **Step 2: Write the new pre-flight file**

Create `tests/integration/test_deploy_preflight.bats`. Setup wires config/pins/images and every secret gate, but starts **no** fake-VPS and runs **no** provisioning:

```bash
#!/usr/bin/env bats
#
# Pre-flight deploy validation: every test here asserts deploy.sh fails during
# validation BEFORE it touches the VPS. No fake-VPS bringup, no Docker — this
# file runs in the cheap tier. Tests that need a live stack stay in
# test_deploy.bats.

load helpers

setup() {
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_images.yaml" "$TMPDIR/images.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_users_database.yml" "$TMPDIR/users_database.yml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_IMAGES_FILE="$TMPDIR/images.yaml"
    export LDS_USERS_DB="$TMPDIR/users_database.yml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    printf 'flashertok' > "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE" "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
}
teardown() { teardown_tmpdir; }

@test "deploy: rejects config with invalid hash before touching VPS" {
    cp "$ROOT/tests/integration/fixtures/bad_hash_config.yaml" "$LDS_CONFIG"
    yq -i ".vps.host = \"127.0.0.1\"" "$LDS_CONFIG"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"password_hash"* ]] || [[ "$output" == *"sha1"* ]]
}

@test "deploy: fails fast when grafana admin_password is missing" {
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"set-grafana-password"* ]] || [[ "$output" == *"admin_password"* ]]
}

@test "deploy: fails fast when authelia users_database.yml is missing" {
    export LDS_USERS_DB="$TMPDIR/does-not-exist-users.yml"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"users:add"* ]]
}

@test "deploy: fails fast when authelia users_database.yml has zero users" {
    printf 'users: {}\n' > "$LDS_USERS_DB"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"users:add"* ]]
}

@test "deploy: fails fast when agent_upload_token is missing" {
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"rotate-agent-upload-token"* ]]
}
```

- [ ] **Step 3: Run the new file — it must pass with no Docker**

Run: `bats tests/integration/test_deploy_preflight.bats`
Expected: PASS, all five, on the laptop without Docker.

If a test fails because `deploy.sh` reached a gate the fixture doesn't satisfy (e.g. it demands an Authelia secrets dir before the gate under test), add the missing file to `setup()` — do **not** weaken the assertion, and do **not** reintroduce fake-VPS bringup.

- [ ] **Step 4: Delete the five extracted tests from `test_deploy.bats`**

Remove these `@test` blocks (they now live in the pre-flight file):
- `deploy: rejects config with invalid hash before touching VPS`
- `deploy: fails fast when grafana admin_password is missing`
- `deploy: fails fast when authelia users_database.yml is missing`
- `deploy: fails fast when authelia users_database.yml has zero users`
- `deploy: fails fast when agent_upload_token is missing`

Leave the stack-dependent tests untouched: `rsyncs templates and brings up containers`, `rsync --delete preserves caddy_data`, `stages loki config, grafana provisioning, and admin_password`, `rsync --delete preserves loki_data and grafana_data`, `loki and grafana come up healthy on the fake VPS`, and the skipped `stages siteapp/agent_upload_token`.

- [ ] **Step 5: Register the new file in the cheap suite**

In `.github/workflows/pr-platform.yml`, add `tests/integration/test_deploy_preflight.bats` to the `bats cheap` file list.

- [ ] **Step 6: Verify the cheap tier still passes end-to-end**

Run:
```bash
bats tests/integration/test_common.bats tests/integration/test_config.bats \
     tests/integration/test_crypto.bats tests/integration/test_render.bats \
     tests/integration/test_images_cli.bats tests/integration/test_deploy_preflight.bats
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_deploy_preflight.bats tests/integration/test_deploy.bats \
        tests/integration/fixtures/valid_users_database.yml .github/workflows/pr-platform.yml
git commit -m "test: extract no-bringup deploy pre-flight tests into the cheap tier"
```

---

## Final verification (after all tasks)

- [ ] **Run the full cheap tier locally**

```bash
bats tests/integration/test_common.bats tests/integration/test_config.bats \
     tests/integration/test_crypto.bats tests/integration/test_render.bats \
     tests/integration/test_secrets.bats tests/integration/test_grafana_provisioning.bats \
     tests/integration/test_deploy_stack_only.bats tests/integration/test_service_selection_render.bats \
     tests/integration/test_images_cli.bats tests/integration/test_deploy_preflight.bats
```
Expected: PASS

- [ ] **Shellcheck the scripts CI checks**

```bash
shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh
```
Expected: no warnings

- [ ] **Confirm no stray references to moved keys**

```bash
grep -rn "studio_image\|jupyter_image\|cadvisor_image" --include="*.sh" --include="*.bash" --include="*.yml" --include="*.yaml" . \
  | grep -v "compose/images.yaml" | grep -v "fixtures/valid_images.yaml" | grep -v "^./docs/"
```
Expected: only `scripts/lib/config.sh` (the `_REQUIRED_IMAGES_FIELDS` / `load_config` reads) and `tests/integration/helpers.bash` (`_profile_images`).

- [ ] **Open the PR**

This PR touches `compose/`, `scripts/`, `tests/integration/` and the workflow, so it trips the heavy gate and exercises the new structure end-to-end. Confirm on the PR:
1. `bats-cheap` runs and passes.
2. `bats-heavy` runs (this PR is not image-only) and every cell passes.
3. `platform` reports success — it is still the only required check.
4. Per-cell wall-clock is lower than the 2026-07-18 baseline (`ops` ~19–20 min, `deploy` ~18–23 min, smoke cells ~14–15 min).

- [ ] **Post-merge validation of the image-only fast path**

After merge, verify the headline claim with a real bump:

```bash
task images:bump -- studio 0.8.0
```

Expected: one `feat:`-typed PR touching only `compose/images.yaml`; `bats-heavy` **skipped**; `platform` green in well under a minute; merging it cuts a release and deploys. (Studio is already pinned at `0.8.0` on main and currently stranded, so this doubles as the fix for that.)

# Unified Agent host monitoring — implementation plan

> **Status:** Superseded by [2026-05-18-vps-metrics-design.md](../specs/2026-05-18-vps-metrics-design.md) (and its forthcoming plan). The Yandex Unified Agent work shipped to `main` (PRs #58, #60) but was never deployed to prod before being swapped for a pure Prometheus + node-exporter stack to remove cloud lock-in. This plan is kept as historical record; do not execute it.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship host-level metrics (RAM, disk space, disk I/O, CPU+load, network, TCP, process counts, agent self-stats) from the prod VPS to Yandex Monitoring via Yandex Unified Agent, without breaking CI and with the Yandex-specific surface confined to two files for future portability.

**Architecture:** New compose service `unified-agent` (image `cr.yandex/yc/unified-agent:25.03.80`) running with `network_mode: host` and `pid: host`, with `/proc`, `/sys`, and `/` bind-mounted read-only. It reads system metrics from procfs/sysfs via the `linux_metrics` input and pushes them to Yandex Monitoring via the `yc_metrics` output. Auth uses the VM-attached service-account metadata (`cloud_meta`) — no secret in this repo. The render layer omits the service block when `yc.folder_id` is unset, so CI deploys are unaffected.

**Tech stack:** bash render scripts (`scripts/lib/render.sh`), yaml templates with `__PLACEHOLDER__` substitution, bats integration tests, Docker Compose, yq.

**Spec:** `docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md`

---

## File map

- **Create:**
  - `compose/unified-agent/config.yml.tmpl` — Unified Agent config template (linux_metrics + agent_metrics → yc_metrics).
- **Modify:**
  - `compose/pins.yaml` — add `unified_agent_image` pin.
  - `compose/docker-compose.yml.tmpl` — add `unified-agent` service block bracketed by `# >>>unified-agent` markers.
  - `scripts/lib/config.sh` — require `unified_agent_image` pin; export `UNIFIED_AGENT_IMAGE`; export optional `YC_FOLDER_ID` from `.yc.folder_id`.
  - `scripts/lib/render.sh` — substitute `__UNIFIED_AGENT_IMAGE__`; conditionally strip the bracketed block when `YC_FOLDER_ID` is empty; add `render_unified_agent_config`.
  - `scripts/deploy.sh` — call `render_unified_agent_config` only when `YC_FOLDER_ID` is set; create the `unified-agent/` dir in stage.
  - `config.example.yaml` — document the new `yc.folder_id` field.
  - `tests/integration/test_render.bats` — add four tests (image substitution, block include with folder id, block exclude without folder id, UA config rendering).
  - `tests/integration/fixtures/valid_pins.yaml` — add `unified_agent_image` so existing fixtures stay loadable.
  - `tests/integration/fixtures/valid_config.yaml` — add `yc.folder_id` so the "include block" path is exercised.
  - `README.md` — add a "First-time setup: host monitoring on Yandex Cloud" section.

The Yandex-specific surface is confined to `compose/unified-agent/config.yml.tmpl` and the bracketed service block in `compose/docker-compose.yml.tmpl`. Everything else is generic render/config plumbing.

---

## Task 1: Pin the Unified Agent image and wire config loading

**Files:**
- Modify: `compose/pins.yaml`
- Modify: `scripts/lib/config.sh:8-26` (`_REQUIRED_PINS_FIELDS`), `:128-157` (`load_config` exports)
- Modify: `tests/integration/fixtures/valid_pins.yaml`
- Modify: `tests/integration/fixtures/valid_config.yaml`
- Modify: `config.example.yaml`
- Test: `tests/integration/test_config.bats` (existing — confirm still green) and a new `test_render.bats` assertion in Task 2

- [ ] **Step 1: Add the pin to `compose/pins.yaml`**

Append below `grafana_image`:

```yaml
# Yandex Cloud Unified Agent — host metrics shipper. Yandex-specific; the
# service is rendered into docker-compose only when config.yaml has
# yc.folder_id set, so CI deploys (which leave it unset) bring up the
# stack without this container.
unified_agent_image: cr.yandex/yc/unified-agent:25.03.80
```

- [ ] **Step 2: Add the pin to the test fixture**

Append to `tests/integration/fixtures/valid_pins.yaml`:

```yaml
unified_agent_image: cr.yandex/yc/unified-agent:25.03.80
```

- [ ] **Step 3: Add `yc.folder_id` to the test config fixture**

The "block included" tests need a non-empty folder id. Append to `tests/integration/fixtures/valid_config.yaml`:

```yaml
yc:
  folder_id: b1g00000000000000000
```

- [ ] **Step 4: Require the new pin field and load both new variables**

In `scripts/lib/config.sh`, add `.unified_agent_image` to `_REQUIRED_PINS_FIELDS`:

```bash
_REQUIRED_PINS_FIELDS=(
    .jupyter_image
    .chisel_image
    .chisel_listen_port
    .loki_image
    .loki_retention_days
    .grafana_image
    .siteapp_image_repo
    .flasher_image_repo
    .caddy_image_repo
    .acme_email
    .remote_root
    .notebooks_path
    .ssh_port
    .unified_agent_image
)
```

In the `load_config` function (right after the `GRAFANA_IMAGE` export, before the image-repo exports), add:

```bash
    export UNIFIED_AGENT_IMAGE   ; UNIFIED_AGENT_IMAGE="$(_yq e '.unified_agent_image' "$pins_path")"
```

After the `SITEAPP_ADMIN_PASSWORD_HASH` export, add the optional folder id (no validation — its absence means "feature disabled"):

```bash
    # Optional: Yandex Cloud folder id for the unified-agent push target.
    # Empty/missing means the unified-agent service is omitted from the
    # rendered compose (CI path).
    export YC_FOLDER_ID          ; YC_FOLDER_ID="$(_yq e '.yc.folder_id // ""' "$config_path")"
```

- [ ] **Step 5: Document the new field in `config.example.yaml`**

Append (commented out — it's optional and instance-specific):

```yaml
# Yandex Cloud monitoring (optional; omit to disable host metrics).
# When set, the deploy renders the unified-agent service block into
# docker-compose. Auth uses the VM-attached service account (cloud_meta);
# no key file lives here. The VM must have a SA with monitoring.editor
# attached at the infra level — see README "First-time setup: host monitoring".
# yc:
#   folder_id: b1g00000000000000000
```

- [ ] **Step 6: Run existing config tests**

```bash
bats tests/integration/test_config.bats
```

Expected: all green. Any failure means `_REQUIRED_PINS_FIELDS` validation rejected an existing fixture — fix the missing field on the fixture before continuing.

- [ ] **Step 7: Commit**

```bash
git add compose/pins.yaml scripts/lib/config.sh tests/integration/fixtures/valid_pins.yaml tests/integration/fixtures/valid_config.yaml config.example.yaml
git commit -m "feat(pins): add unified_agent_image pin and yc.folder_id config field"
```

---

## Task 2: Render the unified-agent service block (always-included path)

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `scripts/lib/render.sh:43-65` (`render_compose`)
- Test: `tests/integration/test_render.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_compose: with yc.folder_id set, emits unified-agent service block" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"unified-agent:"* ]]
    [[ "$output" == *"image: cr.yandex/yc/unified-agent:25.03.80"* ]]
    [[ "$output" == *"network_mode: host"* ]]
    [[ "$output" == *"pid: host"* ]]
    [[ "$output" == *"/proc:/host/proc:ro"* ]]
    [[ "$output" == *"/sys:/host/sys:ro"* ]]
    # Marker comments must not leak into the rendered output.
    ! grep -q '>>>unified-agent' <<< "$output"
    ! grep -q '<<<unified-agent' <<< "$output"
    # No leftover placeholders.
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
bats tests/integration/test_render.bats -f "unified-agent service block"
```

Expected: FAIL — the template doesn't have the block yet, and `__UNIFIED_AGENT_IMAGE__` isn't substituted.

- [ ] **Step 3: Add the unified-agent block to the compose template**

Append to `compose/docker-compose.yml.tmpl` *before* the `networks:` block:

```yaml
  # >>>unified-agent
  # Yandex Cloud Unified Agent — host-metrics shipper. The render layer
  # strips this block (between the >>> / <<< markers) when yc.folder_id is
  # unset, so CI deploys (which leave it unset) bring up the stack
  # without this container. See compose/unified-agent/config.yml for the
  # collection config and docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md
  # for the rationale.
  unified-agent:
    image: __UNIFIED_AGENT_IMAGE__
    restart: unless-stopped
    command: ["unified_agent", "--config", "/etc/yandex/unified_agent/config.yml"]
    network_mode: host
    pid: host
    read_only: true
    volumes:
      - ./unified-agent/config.yml:/etc/yandex/unified_agent/config.yml:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/host/root:ro,rslave
    tmpfs:
      - /tmp
      - /var/lib/yandex/unified_agent
  # <<<unified-agent
```

Note on `network_mode: host` and the existing `networks: [labnet]` lines elsewhere in the file: those stay untouched. unified-agent is the only service on host networking; it doesn't sit on `labnet` because the `cloud_meta` IAM endpoint at `169.254.169.254` is reachable from host networking but not reliably from a bridge network.

- [ ] **Step 4: Substitute `__UNIFIED_AGENT_IMAGE__` in `render_compose`**

In `scripts/lib/render.sh`, inside the `sed` chain in `render_compose`, add the new substitution. Add a `-e` line near the other image substitutions:

```bash
        -e "s|__UNIFIED_AGENT_IMAGE__|${UNIFIED_AGENT_IMAGE:?}|g" \
```

The full sed chain after the change:

```bash
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__SITEAPP_IMAGE__|${siteapp_image}|g" \
        -e "s|__FLASHER_IMAGE__|${flasher_image}|g" \
        -e "s|__CADDY_IMAGE__|${caddy_image}|g" \
        -e "s|__UNIFIED_AGENT_IMAGE__|${UNIFIED_AGENT_IMAGE:?}|g" \
        "$tmpl" > "$out"
```

- [ ] **Step 5: Strip the marker comment lines from the output**

The test asserts `>>>unified-agent` and `<<<unified-agent` must not leak into the rendered file. Pipe the sed output through a second sed that deletes the marker lines. Update `render_compose` to use a pipeline:

```bash
    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__SITEAPP_IMAGE__|${siteapp_image}|g" \
        -e "s|__FLASHER_IMAGE__|${flasher_image}|g" \
        -e "s|__CADDY_IMAGE__|${caddy_image}|g" \
        -e "s|__UNIFIED_AGENT_IMAGE__|${UNIFIED_AGENT_IMAGE:?}|g" \
        "$tmpl" \
        | sed -e '/# >>>unified-agent/d' -e '/# <<<unified-agent/d' \
        > "$out"
```

The marker-stripping happens unconditionally — markers are scaffolding for Task 3's conditional removal; they don't belong in the final output either way.

- [ ] **Step 6: Run the test and verify it passes**

```bash
bats tests/integration/test_render.bats -f "unified-agent service block"
```

Expected: PASS.

- [ ] **Step 7: Run the full render test file to confirm nothing else broke**

```bash
bats tests/integration/test_render.bats
```

Expected: all green. The existing `render_compose: substitutes image, paths, password_hash, and chisel port` test will now see an extra block in the output but its `[[ "$output" == *"..."* ]]` assertions are substring matches, so they still pass.

- [ ] **Step 8: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(compose): render unified-agent service block from docker-compose template"
```

---

## Task 3: Strip the unified-agent block when `yc.folder_id` is unset

**Files:**
- Modify: `scripts/lib/render.sh` (`render_compose`)
- Test: `tests/integration/test_render.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_compose: without yc.folder_id, omits the unified-agent service block" {
    cat > $TMPDIR/no_yc.yaml <<'EOF'
vps: {host: 1.2.3.4, ssh_user: u}
jupyter: {password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"}
siteapp: {admin_password_hash: "$2a$14$HO81PFKmfx2eOcpGyeogN.ct3M9SzgDmvXYHaeNrlTzV66aFbPK2y"}
chisel_clients: []
EOF
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/no_yc.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    ! grep -q 'unified-agent:' <<< "$output"
    ! grep -q 'cr.yandex/yc/unified-agent' <<< "$output"
    ! grep -q '/host/proc' <<< "$output"
    # Marker comments must not leak either way.
    ! grep -q '>>>unified-agent' <<< "$output"
    ! grep -q '<<<unified-agent' <<< "$output"
    # Other services unaffected.
    [[ "$output" == *"image: grafana/loki:3.2.1"* ]]
    [[ "$output" == *"image: grafana/grafana:11.3.0"* ]]
}
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
bats tests/integration/test_render.bats -f "omits the unified-agent service block"
```

Expected: FAIL — `unified-agent:` is still in the output because the block is unconditionally rendered.

- [ ] **Step 3: Branch the rendering on `YC_FOLDER_ID`**

Update `render_compose` in `scripts/lib/render.sh` to use a multi-line awk to drop the bracketed range when `YC_FOLDER_ID` is empty. Replace the trailing `| sed ...` line from Task 2 step 5 with a conditional pipeline:

```bash
    local strip_unified_agent=""
    if [[ -z "${YC_FOLDER_ID:-}" ]]; then
        # Drop everything between the markers (inclusive). awk is used (not sed)
        # because GNU/BSD sed disagree on multi-line range syntax with /pattern/,/pattern/d.
        strip_unified_agent='awk "/# >>>unified-agent/{skip=1} !skip; /# <<<unified-agent/{skip=0}"'
    else
        # Markers are scaffolding; strip them but keep the body.
        strip_unified_agent='sed -e "/# >>>unified-agent/d" -e "/# <<<unified-agent/d"'
    fi

    sed \
        -e "s|__JUPYTER_IMAGE__|${JUPYTER_IMAGE:?}|g" \
        -e "s|__JUPYTER_PASSWORD_HASH__|${JUPYTER_PASSWORD_HASH:?}|g" \
        -e "s|__CHISEL_IMAGE__|${CHISEL_IMAGE:?}|g" \
        -e "s|__CHISEL_LISTEN_PORT__|${CHISEL_LISTEN_PORT:?}|g" \
        -e "s|__NOTEBOOKS_PATH__|${VPS_NOTEBOOKS_PATH:?}|g" \
        -e "s|__LOKI_IMAGE__|${LOKI_IMAGE:?}|g" \
        -e "s|__GRAFANA_IMAGE__|${GRAFANA_IMAGE:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__SITEAPP_IMAGE__|${siteapp_image}|g" \
        -e "s|__FLASHER_IMAGE__|${flasher_image}|g" \
        -e "s|__CADDY_IMAGE__|${caddy_image}|g" \
        -e "s|__UNIFIED_AGENT_IMAGE__|${UNIFIED_AGENT_IMAGE:?}|g" \
        "$tmpl" \
        | eval "$strip_unified_agent" \
        > "$out"
```

Note: the awk filter prints lines while `skip == 0`; it flips `skip` to 1 *before* checking `!skip` so the `>>>` line itself is dropped; it flips back to 0 *after* checking `!skip` so the `<<<` line is also dropped. This matches GNU and BSD awk behavior identically.

Watch out: when `YC_FOLDER_ID` is empty but `UNIFIED_AGENT_IMAGE` is still required by `${UNIFIED_AGENT_IMAGE:?}`, sed will still try to substitute the placeholder before awk strips the block. That's fine — sed runs first, awk drops the lines second. But if `UNIFIED_AGENT_IMAGE` were unset, sed would abort. Since Task 1 made the pin field required, this is never the case in practice.

- [ ] **Step 4: Run the test and verify it passes**

```bash
bats tests/integration/test_render.bats -f "omits the unified-agent service block"
```

Expected: PASS.

- [ ] **Step 5: Re-run all render tests**

```bash
bats tests/integration/test_render.bats
```

Expected: all green. In particular, the "with yc.folder_id set, emits unified-agent service block" test from Task 2 still passes (it uses `valid_config.yaml`, which Task 1 step 3 gave a non-empty `yc.folder_id`).

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(render): omit unified-agent block when yc.folder_id is unset"
```

---

## Task 4: Unified Agent config template and renderer

**Files:**
- Create: `compose/unified-agent/config.yml.tmpl`
- Modify: `scripts/lib/render.sh` (add `render_unified_agent_config`)
- Test: `tests/integration/test_render.bats`

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_unified_agent_config: substitutes folder_id and host labels" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_unified_agent_config $ROOT/compose/unified-agent/config.yml.tmpl $TMPDIR/ua-config.yml
        cat $TMPDIR/ua-config.yml
    "
    [ "$status" -eq 0 ]
    # Folder id from the fixture.
    [[ "$output" == *"folder_id: b1g00000000000000000"* ]]
    # Host label assigned to every series.
    [[ "$output" == *"host: 192.0.2.10"* ]]
    # Inputs and outputs we expect.
    [[ "$output" == *"plugin: linux_metrics"* ]]
    [[ "$output" == *"plugin: agent_metrics"* ]]
    [[ "$output" == *"plugin: yc_metrics"* ]]
    [[ "$output" == *"cloud_meta: {}"* ]]
    [[ "$output" == *"proc_directory: /host/proc"* ]]
    [[ "$output" == *"sys_directory: /host/sys"* ]]
    # No leftover placeholders.
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
    # Valid YAML.
    echo "$output" | yq e '.' >/dev/null
}
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
bats tests/integration/test_render.bats -f "render_unified_agent_config"
```

Expected: FAIL — neither the template nor the function exists yet.

- [ ] **Step 3: Create the config template**

Create `compose/unified-agent/config.yml.tmpl`:

```yaml
# Yandex Cloud Unified Agent — host metrics → Yandex Monitoring.
# Rendered from compose/unified-agent/config.yml.tmpl by scripts/lib/render.sh
# (render_unified_agent_config). See docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md
# for the why.

status:
  port: 0  # disable the status HTTP server; nothing scrapes us

agent_log:
  level: notice

main_thread_pool:
  threads: 2

storages:
  - name: main
    plugin: fs
    config:
      directory: /var/lib/yandex/unified_agent
      max_partition_size: 100mb

routes:
  - input:
      plugin: linux_metrics
      config:
        poll_period: 30s
        proc_directory: /host/proc
        sys_directory: /host/sys
        resources:
          cpu: advanced
          memory: advanced
          network: advanced
          storage: advanced
          io: advanced
          kernel: advanced
    channel:
      pipe:
        - filter:
            plugin: assign
            config:
              labels:
                host: __VPS_HOST__
                env: prod
      output:
        plugin: yc_metrics
        config:
          folder_id: __YC_FOLDER_ID__
          iam:
            cloud_meta: {}

  - input:
      plugin: agent_metrics
      config:
        poll_period: 60s
        namespace: ua
    channel:
      pipe:
        - filter:
            plugin: assign
            config:
              labels:
                host: __VPS_HOST__
                env: prod
      output:
        plugin: yc_metrics
        config:
          folder_id: __YC_FOLDER_ID__
          iam:
            cloud_meta: {}
```

- [ ] **Step 4: Add `render_unified_agent_config` to `scripts/lib/render.sh`**

Append at the end of `scripts/lib/render.sh`:

```bash
# render_unified_agent_config <template_path> <output_path>
# Substitutes __VPS_HOST__ and __YC_FOLDER_ID__.
# Callers MUST verify YC_FOLDER_ID is non-empty before calling — this
# function does not gate itself, because deploy.sh's higher-level flow
# decides whether to render and rsync the unified-agent dir at all.
render_unified_agent_config() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__YC_FOLDER_ID__|${YC_FOLDER_ID:?}|g" \
        "$tmpl" > "$out"
}
```

- [ ] **Step 5: Run the test and verify it passes**

```bash
bats tests/integration/test_render.bats -f "render_unified_agent_config"
```

Expected: PASS.

- [ ] **Step 6: Re-run all render tests**

```bash
bats tests/integration/test_render.bats
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add compose/unified-agent/config.yml.tmpl scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(unified-agent): add config template and render function"
```

---

## Task 5: Wire `render_unified_agent_config` into `deploy.sh`

**Files:**
- Modify: `scripts/deploy.sh:30-83` (the rendering + staging block)

- [ ] **Step 1: Add the conditional render call**

In `scripts/deploy.sh`, locate the block right after `render_loki_config` is called. Insert:

```bash
    # Unified Agent config — only when yc.folder_id is configured. Otherwise
    # the unified-agent service block was already stripped from the rendered
    # compose by render_compose, so we skip the matching config to avoid
    # staging an orphaned file.
    if [[ -n "${YC_FOLDER_ID:-}" ]]; then
        mkdir -p "$stage/unified-agent"
        render_unified_agent_config "$REPO_ROOT/compose/unified-agent/config.yml.tmpl" \
                                    "$stage/unified-agent/config.yml"
    fi
```

The exact location: right after `render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"` (currently line 42 in `scripts/deploy.sh`).

- [ ] **Step 2: Smoke-test the laptop render path**

Run the full deploy in dry-run mode (no real ssh — uses the test config without `yc.folder_id` set, so the conditional skips cleanly):

```bash
LDS_SKIP_HEALTHCHECK=1 \
LDS_PINS_FILE=tests/integration/fixtures/valid_pins.yaml \
LDS_CONFIG=tests/integration/fixtures/valid_config.yaml \
LDS_STACK_ONLY=1 \
bash -n scripts/deploy.sh
```

The `bash -n` is syntax-only; we just confirm the script parses. The real exercise comes from the existing bats deploy tests in step 3.

- [ ] **Step 3: Run existing deploy bats**

```bash
bats tests/integration/test_deploy_stack_only.bats
```

Expected: all green. These tests use a config WITHOUT `yc.folder_id`, so the new conditional is a no-op for them.

- [ ] **Step 4: Run the full bats suite**

```bash
bats tests/integration/
```

Expected: all green (or the same skip pattern as before for the compose-image-pull cells).

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): render unified-agent config when yc.folder_id is set"
```

---

## Task 6: Operator docs (README) and Renovate sanity check

**Files:**
- Modify: `README.md`
- Read-only: `renovate.json` (sanity check; no edits expected)

- [ ] **Step 1: Add the operator setup section to README**

Append a new section to `README.md` (after the existing deploy section — locate where the file currently documents `task deploy`). Insert:

````markdown
## First-time setup: host monitoring on Yandex Cloud

Host metrics (RAM, disk space, disk I/O, CPU + load, network, TCP connections, agent self-health) are shipped from the prod VPS to **Yandex Monitoring** by the `unified-agent` container, which appears in the stack only when `yc.folder_id` is set in your `config.yaml`. CI deploys leave it unset and bring up the stack without the container.

**One-time infrastructure setup (Yandex Cloud console / `yc` CLI — not in this repo):**

1. Create a service account in the target folder, e.g. `lab-bridge-monitoring-writer`.
2. Grant the SA the `monitoring.editor` role on that folder.
3. Attach the SA to the prod VM: Compute Cloud → VM → Edit → "Service account".

   After this, `cloud_meta` on the VM mints IAM tokens for the SA automatically — no key file lives on the VPS.

**Per-laptop setup:**

1. Put the folder id into `config.yaml`:

   ```yaml
   yc:
     folder_id: b1g...  # your Yandex Cloud folder id
   ```

2. `task deploy`.

3. After the first deploy, open Yandex Monitoring in the YC console → Metric explorer. Filter by `host=<your VPS hostname>`. You should see series for `cpu.*`, `memory.*`, `disk.*`, `net.*` from the `linux_metrics` namespace within ~1 minute.

**Disabling host monitoring:** remove or comment out the `yc` block in `config.yaml` and redeploy. The render layer drops the service from the next compose render; `docker compose up -d --remove-orphans` (already in `scripts/deploy.sh`) tears down the running container.

**Migrating off Yandex Cloud:** the Yandex-specific surface is contained in two files — `compose/unified-agent/config.yml.tmpl` and the `# >>>unified-agent` … `# <<<unified-agent` block in `compose/docker-compose.yml.tmpl`. Replace those with the new provider's agent (CloudWatch Agent for AWS, Ops Agent for GCP, or `node_exporter` + Prometheus for self-hosted). No app code, no Caddy route, and no Grafana provisioning depends on unified-agent.
````

- [ ] **Step 2: Verify Renovate picks up the new pin**

Read `renovate.json`:

```bash
cat renovate.json
```

Renovate auto-detects image pins in YAML files via the `regexManagers` / `customManagers` config or via the `docker` datasource on lines like `image: foo/bar:1.2.3`. Confirm that one of the following is true:

- The other entries in `compose/pins.yaml` (e.g. `loki_image`, `grafana_image`) already get bumped by Renovate PRs in the repo's PR history (`gh pr list --search "renovate pins" --state all --limit 5`). If yes, the new `unified_agent_image` will be picked up the same way.
- Or, `renovate.json` has a customManager that matches `^\s*\w+_image:\s*(?<depName>[^:]+):(?<currentValue>\S+)`. If yes, the new pin matches that regex too.

If neither is true (no existing renovate bumps for image pins), open a follow-up issue: "Renovate doesn't track pins.yaml image keys — wire it up." Do not block this PR on it.

- [ ] **Step 3: Final spec/plan/code sanity check**

Re-read the spec (`docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md`) end-to-end and confirm every "Design" section has corresponding code:

- Compose service block ✅ (Task 2)
- Conditional inclusion ✅ (Task 3)
- linux_metrics + agent_metrics + yc_metrics config ✅ (Task 4)
- `cloud_meta` auth ✅ (Task 4 — `iam: cloud_meta: {}`)
- 30s/60s polling ✅ (Task 4 config)
- `host` / `env` labels via `assign` filter ✅ (Task 4 config)
- Pins entry ✅ (Task 1)
- `yc.folder_id` config field ✅ (Task 1)
- CI omission ✅ (Task 3 + Task 5 conditional)
- README operator section ✅ (Task 6)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README section for host monitoring setup on Yandex Cloud"
```

---

## Post-merge verification (on the prod VPS, not in CI)

After the implementation PR squash-merges and release-please cuts the next version, the regular CI deploy will run *without* `yc.folder_id` (CI config doesn't have it) and bring up the stack unchanged. Then the operator does the per-laptop setup from Task 6 and runs `task deploy` from the laptop. Verify:

1. **Container is up:**

   ```bash
   ssh <vps> 'docker compose -f /srv/lab-bridge/docker-compose.yml ps unified-agent'
   ```
   Expected: `Up`, no restart loop.

2. **Container is healthy:**

   ```bash
   ssh <vps> 'docker logs --tail=50 lab-bridge-unified-agent-1'
   ```
   Expected: no auth errors, no "failed to deliver" loops. A few "delivered N samples" lines or quiet operation = good.

3. **Metrics arrive in Yandex Monitoring:**
   - Open YC console → Monitoring → Metric explorer.
   - Filter `host=<VPS_HOST>`, `env=prod`.
   - Expected: `cpu.usage_user`, `memory.MemAvailable`, `disk.*`, `net.*` series populated within ~2 minutes.

4. **Free-disk-space verification (the user's explicit ask):**
   - In Metric explorer, look for `disk.free_bytes` (or equivalent — the exact series name is determined by the Unified Agent `linux_metrics` `storage: advanced` resource set).
   - If no free-disk series appears but `disk.io.*` does: the container's view of `statfs()` on host mountpoints is the likely culprit. The `/:/host/root:ro,rslave` mount is staged for this case — file a follow-up to set the corresponding `mountpoints_root` (or whatever the Unified Agent option is named for remapping mountpoints to a different prefix) in `compose/unified-agent/config.yml.tmpl`. The exact option name is in the `linux_metrics` input docs at `https://yandex.cloud/en/docs/monitoring/concepts/data-collection/unified-agent/inputs`.

5. **RAM utilization verification (the user's explicit ask):**
   - Look for `memory.MemAvailable` / `memory.MemFree` / `memory.Buffers` / `memory.Cached` series. These come straight from `/proc/meminfo` via the `/host/proc` bind mount and should always populate.

---

## Notes for the implementing agent

- **Squash-merge style:** the repo enforces Conventional Commits PR titles (CLAUDE.md). The PR title for the squash should be `feat: add Yandex Unified Agent for host monitoring`. The individual commits inside the branch can use looser scopes (each task above gives an example) since they're squashed away.
- **Required checks:** this PR doesn't add a new service workflow, so no branch-protection update is needed. The change touches `compose/**`, `scripts/**`, `tests/integration/**`, and `README.md` — all already covered by `pr-platform / platform`.
- **No new secret in `secrets.sh`:** `cloud_meta` auth means the prod VM's attached service account does the work. No `task secrets:set-yc-*` command, no GH secret, no laptop secret file.
- **No new bats matrix cell:** the existing render-test cell exercises the new code paths; no fake-VPS bring-up is needed for these changes.

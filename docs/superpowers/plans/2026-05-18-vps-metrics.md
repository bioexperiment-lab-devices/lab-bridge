# VPS metrics: Prometheus + Grafana dashboard stack — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the just-merged Yandex Unified Agent path with a vendor-neutral Prometheus + node-exporter + cAdvisor stack, scraping Caddy and (best-effort) JupyterLab, surfaced in the existing Grafana via committed dashboard JSON. Single atomic PR.

**Architecture:** Three new compose services on `labnet` (no published ports), one Caddyfile line (`admin :2019`), one new Grafana datasource, four committed dashboard JSONs. UA code surface (~280 LOC across `compose/`, `scripts/lib/`, `tests/integration/`) is removed in the same PR; the UA spec + plan are already marked superseded (see commit `1446a85`).

**Tech Stack:** Docker Compose, Prometheus 3.x, node-exporter 1.8.x, cAdvisor 0.49.x, Caddy 2.x admin endpoint, Grafana 11.3 provisioning, `bats` integration tests, GitHub Actions matrix.

**Spec:** `docs/superpowers/specs/2026-05-18-vps-metrics-design.md`

**Pre-commit note:** Already done in commit `1446a85` and not in scope for any task below: the spec at `docs/superpowers/specs/2026-05-18-vps-metrics-design.md`, the supersession banner on `docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md`, and the supersession banner on `docs/superpowers/plans/2026-05-18-unified-agent-monitoring.md`.

---

## File map

**Create:**
- `compose/prometheus/prometheus.yml.tmpl` — scrape config template
- `compose/grafana/provisioning/datasources/prometheus.yaml` — Grafana datasource
- `compose/grafana/provisioning/dashboards/node-exporter-full.json`
- `compose/grafana/provisioning/dashboards/cadvisor.json`
- `compose/grafana/provisioning/dashboards/caddy.json`
- `compose/grafana/provisioning/dashboards/platform.json`
- `tests/integration/test_metrics_smoke.bats`

**Modify:**
- `compose/pins.yaml` — add 4 entries, remove 1
- `compose/docker-compose.yml.tmpl` — add 3 services, modify `grafana.depends_on`, remove UA block
- `compose/Caddyfile.tmpl` — add `admin :2019` directive
- `compose/grafana/provisioning/datasources/loki.yaml` — flip `isDefault: true → false`
- `scripts/lib/config.sh` — add 4 reads, remove 3 (UA-related)
- `scripts/lib/render.sh` — add `render_prometheus_config`, remove UA fn + strip helper
- `scripts/deploy.sh` — add `render_prometheus_config` call, remove UA conditional
- `config.example.yaml` — remove `yc.folder_id` example
- `tests/integration/test_render.bats` — drop UA branches, add new placeholder assertions
- `tests/integration/test_config.bats` — drop UA env-var assertions, add new
- `tests/integration/fixtures/valid_pins.yaml` — remove `unified_agent_image`, add 4 new pins
- `.github/workflows/pr-platform.yml` — add `metrics-smoke` matrix cell
- `README.md` — delete the "First-time setup: host monitoring" UA section

**Delete:**
- `compose/unified-agent/` directory (the `config.yml.tmpl`)

---

### Task 1: Create the feature branch

**Files:** none (git operation)

- [ ] **Step 1: Branch from main**

```bash
git checkout main
git pull --ff-only
git checkout -b feat/vps-metrics-prometheus
git log --oneline -1
```

Expected: HEAD shows `1446a85 docs(specs): add VPS metrics design; supersede unified-agent`.

- [ ] **Step 2: Verify clean working tree**

```bash
git status
```

Expected: `nothing to commit, working tree clean` (the `.claude/` directory is untracked and excluded by `.gitignore` — leave it alone).

---

### Task 2: Rip out the unified-agent code surface

The deletes ship as one coherent commit so render-bats stays compilable. Banners on the UA spec + plan are already in place from commit `1446a85`.

**Files:**
- Modify: `compose/pins.yaml`
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `scripts/lib/config.sh`
- Modify: `scripts/lib/render.sh`
- Modify: `scripts/deploy.sh`
- Modify: `config.example.yaml`
- Modify: `tests/integration/test_render.bats`
- Modify: `tests/integration/test_config.bats`
- Modify: `tests/integration/fixtures/valid_pins.yaml`
- Modify: `README.md`
- Delete: `compose/unified-agent/` directory

- [ ] **Step 1: Delete the unified-agent compose directory**

```bash
git rm -r compose/unified-agent
ls compose/unified-agent 2>&1
```

Expected: `ls: compose/unified-agent: No such file or directory`.

- [ ] **Step 2: Remove the UA service block from `docker-compose.yml.tmpl`**

Delete lines 101–129 (the `# >>>unified-agent` marker through the `# <<<unified-agent` marker, inclusive). Use the `Edit` tool with `old_string` matching the entire block:

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
    # Bypass the image's /entrypoint.sh: it renders /etc/yandex/unified_agent/config.tmpl.yml
    # into /etc/yandex/unified_agent/config.yml via shell eval, then exec's its args.
    # That write collides with our read-only bind mount of the pre-rendered config at
    # the same path, so the container crashes on startup. We've already rendered the
    # config in scripts/lib/render.sh (render_unified_agent_config), so we skip the
    # entrypoint and run the agent binary directly with --config pointing at our file.
    entrypoint: ["unified_agent", "--config", "/etc/yandex/unified_agent/config.yml"]
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

Replace with nothing (an empty `new_string`). Verify with:

```bash
grep -c 'unified-agent' compose/docker-compose.yml.tmpl
```

Expected: `0`.

- [ ] **Step 3: Remove the UA pin from `compose/pins.yaml`**

Delete lines 12–16 (the `# Yandex Cloud Unified Agent —` comment block plus the `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` line).

```bash
grep -c 'unified_agent\|cr.yandex' compose/pins.yaml
```

Expected: `0`.

- [ ] **Step 4: Remove the UA entry from the fixture pins**

Edit `tests/integration/fixtures/valid_pins.yaml`. Delete the line `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` (current line 14).

```bash
grep -c 'unified_agent' tests/integration/fixtures/valid_pins.yaml
```

Expected: `0`.

- [ ] **Step 5: Remove UA reads from `scripts/lib/config.sh`**

In `scripts/lib/config.sh`:

a) Delete the line `.unified_agent_image` from the `_REQUIRED_PINS_FIELDS` array (current line 41).

b) Delete the `YC_FOLDER_ID` export block (current lines 144–147):

```bash
    # Optional: Yandex Cloud folder id for the unified-agent push target.
    # Empty/missing means the unified-agent service is omitted from the
    # rendered compose (CI path).
    export YC_FOLDER_ID          ; YC_FOLDER_ID="$(_yq e '.yc.folder_id // ""' "$config_path")"
```

c) Delete the line `export UNIFIED_AGENT_IMAGE   ; UNIFIED_AGENT_IMAGE="$(_yq e '.unified_agent_image' "$pins_path")"` (current line 160).

Verify:

```bash
grep -c 'unified_agent\|YC_FOLDER\|yc\.folder' scripts/lib/config.sh
```

Expected: `0`.

- [ ] **Step 6: Remove UA logic from `scripts/lib/render.sh`**

In `scripts/lib/render.sh`:

a) In `render_compose` (currently lines 42–79), delete the entire `strip_unified_agent` setup block (lines 52–61):

```bash
    local strip_unified_agent=""
    if [[ -z "${YC_FOLDER_ID:-}" ]]; then
        # Drop everything between the markers (inclusive). awk gives us a single
        # tool that handles both branches symmetrically — drop body+markers here,
        # drop only markers in the else branch — without forking the syntax.
        strip_unified_agent='awk "/# >>>unified-agent/{skip=1} !skip; /# <<<unified-agent/{skip=0}"'
    else
        # Markers are scaffolding; strip them but keep the body.
        strip_unified_agent='sed -e "/# >>>unified-agent/d" -e "/# <<<unified-agent/d"'
    fi
```

b) Delete the `-e "s|__UNIFIED_AGENT_IMAGE__|${UNIFIED_AGENT_IMAGE:?}|g" \` line from the `sed` invocation (currently line 75).

c) Replace the trailing pipe-through-eval with a direct redirect. Change the current `sed ... "$tmpl" | eval "$strip_unified_agent" > "$out"` shape to `sed ... "$tmpl" > "$out"`. Concretely, in `render_compose`, the lines that currently read:

```bash
        "$tmpl" \
        | eval "$strip_unified_agent" \
        > "$out"
```

become:

```bash
        "$tmpl" \
        > "$out"
```

d) Delete the entire `render_unified_agent_config` function (currently lines 164–176).

Verify:

```bash
grep -c 'unified_agent\|UNIFIED_AGENT\|YC_FOLDER\|strip_unified' scripts/lib/render.sh
```

Expected: `0`.

- [ ] **Step 7: Remove UA logic from `scripts/deploy.sh`**

In `scripts/deploy.sh`, delete the entire UA conditional render block (currently lines 44–52):

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

Verify:

```bash
grep -c 'unified_agent\|YC_FOLDER\|render_unified' scripts/deploy.sh
```

Expected: `0`.

- [ ] **Step 8: Remove the YC field from `config.example.yaml`**

Open `config.example.yaml`, locate the `yc.folder_id` block (it includes a leading comment block), and delete it. If you're unsure of the exact lines, use:

```bash
grep -n 'yc\.\|folder_id\|Yandex' config.example.yaml
```

Delete the matched lines and any surrounding comment block that introduces the YC field. Verify:

```bash
grep -c 'yc\.\|folder_id\|Yandex' config.example.yaml
```

Expected: `0`.

- [ ] **Step 9: Drop UA test branches from `tests/integration/test_render.bats`**

Delete three full `@test` blocks (and their bodies) from `tests/integration/test_render.bats`:

a) `@test "render_compose: with yc.folder_id set, emits unified-agent service block"` (current lines ~375–421).

b) `@test "render_unified_agent_config: substitutes folder_id and host labels"` (current lines ~466–505).

c) `@test "render_compose: without yc.folder_id, omits the unified-agent service block"` (current lines ~507–544).

Also remove the `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` lines from the two inline `pins.yaml` heredocs in the `SITEAPP_IMAGE is composed` test (~line 347) and the `FLASHER_IMAGE is composed` test (~line 439).

Verify:

```bash
grep -c 'unified_agent\|UNIFIED_AGENT\|yc\.folder\|YC_FOLDER\|/host/proc\|cr.yandex' tests/integration/test_render.bats
```

Expected: `0`.

- [ ] **Step 10: Drop UA references from `tests/integration/test_config.bats`**

In `tests/integration/test_config.bats`, remove the `unified_agent_image: cr.yandex/yc/unified-agent:25.03.80` line from the inline pins.yaml heredoc in the test `"validate_config: passes when pins.yaml supplies image pins and paths"` (~line 100).

Verify:

```bash
grep -c 'unified_agent\|UNIFIED_AGENT\|yc\.folder\|YC_FOLDER\|cr.yandex' tests/integration/test_config.bats
```

Expected: `0`.

- [ ] **Step 11: Remove the UA "First-time setup" section from README.md**

```bash
grep -n 'Unified Agent\|monitoring' README.md | head
```

Locate the "First-time setup: host monitoring" section (introduced in PR #58). Delete the entire section, including its heading and all content until the next top-level section heading. If no such section is found in your branch, skip this step and note it in the commit message.

```bash
grep -c 'Unified Agent\|unified-agent\|cloud_meta\|yc.folder_id' README.md
```

Expected: `0`.

- [ ] **Step 12: Run the bats render + config tests, expect all pass**

```bash
bats tests/integration/test_render.bats tests/integration/test_config.bats
```

Expected: `ok` for every remaining test; **no errors**. If a test fails because of a removed assertion (e.g., the `no leftover placeholders` regex still finds `__UNIFIED_AGENT_IMAGE__`), revisit Step 6 — the sed list still includes the UA placeholder.

- [ ] **Step 13: Run shellcheck on the modified scripts**

```bash
shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh
```

Expected: no warnings.

- [ ] **Step 14: Commit**

```bash
git add -A
git diff --cached --stat
git commit -m "$(cat <<'EOF'
refactor(platform): remove Yandex Unified Agent code surface

Deletes the UA service block, render helper, config field plumbing,
pins entry, fixture entries, test branches, and README setup section.
Spec + plan files retain the supersession banners added in 1446a85.

Part of the swap to a vendor-neutral Prometheus + Grafana metrics
stack; see docs/superpowers/specs/2026-05-18-vps-metrics-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Add the Prometheus stack pins

Pins land first so subsequent compose-template tasks can reference the env vars.

**Files:**
- Modify: `compose/pins.yaml`
- Modify: `scripts/lib/config.sh`
- Modify: `tests/integration/fixtures/valid_pins.yaml`
- Modify: `tests/integration/test_config.bats`

- [ ] **Step 1: Write a failing assertion for the new env vars in `test_config.bats`**

Add this `@test` block after the existing `load_config: exports LOKI_IMAGE, LOKI_RETENTION_DAYS, GRAFANA_IMAGE` test:

```bash
@test "load_config: exports PROMETHEUS_IMAGE, NODE_EXPORTER_IMAGE, CADVISOR_IMAGE, PROMETHEUS_RETENTION_DAYS" {
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $ROOT/tests/integration/fixtures/valid_config.yaml; echo \$PROMETHEUS_IMAGE \$NODE_EXPORTER_IMAGE \$CADVISOR_IMAGE \$PROMETHEUS_RETENTION_DAYS"
    [ "$status" -eq 0 ]
    [[ "$output" == *"prom/prometheus:v3.0.1"* ]]
    [[ "$output" == *"quay.io/prometheus/node-exporter:v1.8.2"* ]]
    [[ "$output" == *"gcr.io/cadvisor/cadvisor:v0.49.1"* ]]
    [[ "$output" == *"30"* ]]
}
```

- [ ] **Step 2: Run the new test, expect failure**

```bash
bats tests/integration/test_config.bats -f "PROMETHEUS_IMAGE"
```

Expected: FAIL (config doesn't read these pins yet).

- [ ] **Step 3: Add a failing schema test for the new required pins**

Append this `@test` block:

```bash
@test "validate_config: rejects pins.yaml missing prometheus stack fields" {
    cat > "$TMPDIR/cfg.yaml" <<'CFG'
vps: {host: 1.2.3.4, ssh_user: u}
jupyter: {password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567"}
siteapp: {admin_password_hash: "$2a$14$HO81PFKmfx2eOcpGyeogN.ct3M9SzgDmvXYHaeNrlTzV66aFbPK2y"}
chisel_clients: []
CFG
    # Pins file is present but missing the prometheus stack pins.
    cat > "$TMPDIR/bad_pins.yaml" <<'PINS'
jupyter_image: quay.io/jupyter/scipy-notebook:2026-04-20
chisel_image: jpillora/chisel:1.10.1
chisel_listen_port: 8080
loki_image: grafana/loki:3.2.1
loki_retention_days: 30
grafana_image: grafana/grafana:11.3.0
siteapp_image_repo: ghcr.io/test/lab-bridge-siteapp
flasher_image_repo: ghcr.io/test/lab-bridge-flasher
caddy_image_repo: ghcr.io/test/lab-bridge-caddy
acme_email: ops@example.com
remote_root: /srv/lab-bridge
notebooks_path: /srv/jupyterlab/work
ssh_port: 22
PINS
    run bash -c "export LDS_PINS_FILE=$TMPDIR/bad_pins.yaml; source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/cfg.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"prometheus_image"* ]]
    [[ "$output" == *"node_exporter_image"* ]]
    [[ "$output" == *"cadvisor_image"* ]]
    [[ "$output" == *"prometheus_retention_days"* ]]
}
```

- [ ] **Step 4: Run the new test, expect failure**

```bash
bats tests/integration/test_config.bats -f "missing prometheus stack"
```

Expected: FAIL (validator doesn't yet require these pins).

- [ ] **Step 5: Add the new pins to `compose/pins.yaml`**

Append below the existing `grafana_image: grafana/grafana:11.3.0` line:

```yaml

# Prometheus host-monitoring stack. All vendor-neutral; no metadata-service
# dependency. Renovate-managed.
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1

# Prometheus TSDB retention. Mirrors loki_retention_days for symmetry between
# logs and metrics history (see compose/pins.yaml:loki_retention_days).
prometheus_retention_days: 30
```

- [ ] **Step 6: Add the matching entries to the fixture**

Edit `tests/integration/fixtures/valid_pins.yaml`. Append after the existing `ssh_port: 22` line:

```yaml
prometheus_image: prom/prometheus:v3.0.1
node_exporter_image: quay.io/prometheus/node-exporter:v1.8.2
cadvisor_image: gcr.io/cadvisor/cadvisor:v0.49.1
prometheus_retention_days: 30
```

- [ ] **Step 7: Extend `_REQUIRED_PINS_FIELDS` in `scripts/lib/config.sh`**

In `scripts/lib/config.sh`, modify the `_REQUIRED_PINS_FIELDS` array. The current array ends with `.ssh_port` followed by a closing `)`. Replace the closing `)` line so the array becomes:

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
    .prometheus_image
    .node_exporter_image
    .cadvisor_image
    .prometheus_retention_days
)
```

- [ ] **Step 8: Add exports in `load_config`**

In `scripts/lib/config.sh`'s `load_config`, after `export GRAFANA_IMAGE`, add:

```bash
    export PROMETHEUS_IMAGE      ; PROMETHEUS_IMAGE="$(_yq e '.prometheus_image' "$pins_path")"
    export NODE_EXPORTER_IMAGE   ; NODE_EXPORTER_IMAGE="$(_yq e '.node_exporter_image' "$pins_path")"
    export CADVISOR_IMAGE        ; CADVISOR_IMAGE="$(_yq e '.cadvisor_image' "$pins_path")"
    export PROMETHEUS_RETENTION_DAYS ; PROMETHEUS_RETENTION_DAYS="$(_yq e '.prometheus_retention_days' "$pins_path")"
```

- [ ] **Step 9: Add retention-format validation**

In `scripts/lib/config.sh`'s `validate_config`, after the existing `loki_retention_days` numeric check (around line 116–119), add a sibling for prometheus retention:

```bash
    local prom_retention
    prom_retention="$(_yq e '.prometheus_retention_days // ""' "$pins_path")"
    if [[ -n "$prom_retention" ]] && ! [[ "$prom_retention" =~ ^[0-9]+$ ]]; then
        errors+=("pins.prometheus_retention_days must be a positive integer, got: $prom_retention")
    fi
```

- [ ] **Step 10: Re-run the two new tests, expect PASS**

```bash
bats tests/integration/test_config.bats -f "PROMETHEUS_IMAGE"
bats tests/integration/test_config.bats -f "missing prometheus stack"
```

Expected: both PASS.

- [ ] **Step 11: Run the full config + render bats suite to confirm no regressions**

```bash
bats tests/integration/test_config.bats tests/integration/test_render.bats
```

Expected: every test passes.

- [ ] **Step 12: Commit**

```bash
git add compose/pins.yaml tests/integration/fixtures/valid_pins.yaml scripts/lib/config.sh tests/integration/test_config.bats
git commit -m "$(cat <<'EOF'
feat(platform): add Prometheus stack pins to pins.yaml schema

Pins prometheus, node-exporter, cAdvisor images and a 30d TSDB
retention setting. config.sh now reads + validates them; fixtures
updated to match.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Add the prometheus service to the compose template

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `tests/integration/test_render.bats`

- [ ] **Step 1: Write a failing render-bats assertion for the prometheus service**

Append this `@test` block to `tests/integration/test_render.bats`:

```bash
@test "render_compose: emits prometheus service with correct image and retention arg" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: prom/prometheus:v3.0.1"* ]]
    [[ "$output" == *"--storage.tsdb.retention.time=30d"* ]]
    [[ "$output" == *"./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro"* ]]
    [[ "$output" == *"./prometheus_data:/prometheus"* ]]
    # No published ports — labnet-only.
    run yq e '.services.prometheus | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
    # No leftover placeholders.
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run the new test, expect failure**

```bash
bats tests/integration/test_render.bats -f "prometheus service with correct image"
```

Expected: FAIL (no prometheus block, leftover `__PROMETHEUS_IMAGE__` placeholder, or schema mismatch).

- [ ] **Step 3: Add the prometheus service block to `docker-compose.yml.tmpl`**

In `compose/docker-compose.yml.tmpl`, after the existing `grafana` service block (which ends at the line `    depends_on: [loki]`), add:

```yaml

  prometheus:
    image: __PROMETHEUS_IMAGE__
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=__PROMETHEUS_RETENTION_DAYS__d
      - --web.listen-address=:9090
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./prometheus_data:/prometheus
    networks: [labnet]
```

Then modify the existing `grafana` block so its `depends_on` reads `[loki, prometheus]` instead of `[loki]`. The matching context line currently reads `    depends_on: [loki]` (around line 68); change to `    depends_on: [loki, prometheus]`.

- [ ] **Step 4: Add the placeholders to `render_compose`**

In `scripts/lib/render.sh`, inside `render_compose`'s `sed` invocation, add two new `-e` lines after the existing `s|__GRAFANA_IMAGE__|...|g` line:

```bash
        -e "s|__PROMETHEUS_IMAGE__|${PROMETHEUS_IMAGE:?}|g" \
        -e "s|__PROMETHEUS_RETENTION_DAYS__|${PROMETHEUS_RETENTION_DAYS:?}|g" \
```

- [ ] **Step 5: Run the new test, expect PASS**

```bash
bats tests/integration/test_render.bats -f "prometheus service with correct image"
```

Expected: PASS.

- [ ] **Step 6: Run the full render bats suite to confirm no regressions**

```bash
bats tests/integration/test_render.bats
```

Expected: every test passes.

- [ ] **Step 7: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "$(cat <<'EOF'
feat(platform): add prometheus service to compose template

Adds the prometheus TSDB + scraper service on labnet with no published
ports. Retention is templated from prometheus_retention_days (30d).
Grafana now depends on prometheus so the new datasource resolves on
first bring-up.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Add the node-exporter service

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/integration/test_render.bats`

- [ ] **Step 1: Write a failing render-bats assertion**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_compose: emits node-exporter service with host /proc and /sys mounts" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: quay.io/prometheus/node-exporter:v1.8.2"* ]]
    [[ "$output" == *"--path.procfs=/host/proc"* ]]
    [[ "$output" == *"--path.sysfs=/host/sys"* ]]
    [[ "$output" == *"--path.rootfs=/host/root"* ]]
    [[ "$output" == *"/proc:/host/proc:ro"* ]]
    [[ "$output" == *"/sys:/host/sys:ro"* ]]
    [[ "$output" == *"/:/host/root:ro,rslave"* ]]
    # Bridge networking (not host) — node-exporter reads procfs from the bind mount.
    run yq e '.services."node-exporter" | has("network_mode")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
    # No published ports.
    run yq e '.services."node-exporter" | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run the test, expect failure**

```bash
bats tests/integration/test_render.bats -f "node-exporter service"
```

Expected: FAIL.

- [ ] **Step 3: Add the node-exporter service block**

In `compose/docker-compose.yml.tmpl`, after the `prometheus:` block from Task 4, add:

```yaml

  node-exporter:
    image: __NODE_EXPORTER_IMAGE__
    restart: unless-stopped
    command:
      - --path.procfs=/host/proc
      - --path.sysfs=/host/sys
      - --path.rootfs=/host/root
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($|/)
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/host/root:ro,rslave
    networks: [labnet]
```

Add the new placeholder to `render_compose`'s `sed` invocation:

```bash
        -e "s|__NODE_EXPORTER_IMAGE__|${NODE_EXPORTER_IMAGE:?}|g" \
```

- [ ] **Step 4: Run the test, expect PASS**

```bash
bats tests/integration/test_render.bats -f "node-exporter service"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(platform): add node-exporter service for host metrics

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Add the cAdvisor service

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/integration/test_render.bats`

- [ ] **Step 1: Write a failing render-bats assertion**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_compose: emits cadvisor service mounting docker.sock read-only" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: gcr.io/cadvisor/cadvisor:v0.49.1"* ]]
    [[ "$output" == *"/var/run/docker.sock:/var/run/docker.sock:ro"* ]]
    [[ "$output" == *"/:/rootfs:ro"* ]]
    [[ "$output" == *"/var/lib/docker:/var/lib/docker:ro"* ]]
    # No published ports; labnet only.
    run yq e '.services.cadvisor | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
    # No privileged mode.
    run yq e '.services.cadvisor.privileged // false' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run the test, expect failure**

```bash
bats tests/integration/test_render.bats -f "cadvisor service"
```

Expected: FAIL.

- [ ] **Step 3: Add the cAdvisor service block**

In `compose/docker-compose.yml.tmpl`, after the `node-exporter:` block from Task 5, add:

```yaml

  cadvisor:
    image: __CADVISOR_IMAGE__
    restart: unless-stopped
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [labnet]
```

Add the new placeholder to `render_compose`'s `sed` invocation:

```bash
        -e "s|__CADVISOR_IMAGE__|${CADVISOR_IMAGE:?}|g" \
```

- [ ] **Step 4: Run the test, expect PASS**

```bash
bats tests/integration/test_render.bats -f "cadvisor service"
```

Expected: PASS.

- [ ] **Step 5: Run the full render suite**

```bash
bats tests/integration/test_render.bats
```

Expected: every test passes.

- [ ] **Step 6: Commit**

```bash
git add compose/docker-compose.yml.tmpl scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(platform): add cAdvisor service for per-container metrics

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Bind Caddy's admin endpoint on labnet

**Files:**
- Modify: `compose/Caddyfile.tmpl`
- Modify: `tests/integration/test_render.bats`

- [ ] **Step 1: Write a failing render-bats assertion**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_caddyfile: emits admin :2019 directive so Prometheus can scrape /metrics" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"admin :2019"* ]]
}
```

- [ ] **Step 2: Run the test, expect failure**

```bash
bats tests/integration/test_render.bats -f "admin :2019"
```

Expected: FAIL.

- [ ] **Step 3: Add the `admin :2019` directive**

In `compose/Caddyfile.tmpl`, modify the global options block at lines 1–9. After the line `    default_sni __VPS_HOST__` (line 3), add:

```
    admin :2019
```

The block then reads:

```
{
    email __ACME_EMAIL__
    default_sni __VPS_HOST__
    admin :2019
    ...
}
```

- [ ] **Step 4: Run the test, expect PASS**

```bash
bats tests/integration/test_render.bats -f "admin :2019"
```

Expected: PASS.

- [ ] **Step 5: Run the full render + caddyfile suite to confirm no regressions**

```bash
bats tests/integration/test_render.bats
```

Expected: every test passes.

- [ ] **Step 6: Commit**

```bash
git add compose/Caddyfile.tmpl tests/integration/test_render.bats
git commit -m "feat(platform): bind Caddy admin :2019 on labnet for Prometheus scrape

The admin endpoint already serves /metrics; the default localhost:2019
binding is unreachable from prometheus's container. Bind on all
interfaces inside the container so prometheus can scrape caddy:2019
over labnet. The admin port stays unpublished.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Create the Prometheus scrape config template

**Files:**
- Create: `compose/prometheus/prometheus.yml.tmpl`
- Modify: `scripts/lib/render.sh`
- Modify: `tests/integration/test_render.bats`

This task lands the template assuming JupyterLab's `/metrics` works unauth'd. Task 11 verifies that assumption against the running stack and removes the jupyter scrape job if it doesn't.

- [ ] **Step 1: Write a failing render-bats assertion**

Append to `tests/integration/test_render.bats`:

```bash
@test "render_prometheus_config: substitutes vps host and emits expected scrape jobs" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_prometheus_config $ROOT/compose/prometheus/prometheus.yml.tmpl $TMPDIR/prometheus.yml
        cat $TMPDIR/prometheus.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"host: 192.0.2.10"* ]]
    [[ "$output" == *"env: prod"* ]]
    [[ "$output" == *"job_name: prometheus"* ]]
    [[ "$output" == *"job_name: node-exporter"* ]]
    [[ "$output" == *"job_name: cadvisor"* ]]
    [[ "$output" == *"job_name: caddy"* ]]
    [[ "$output" == *"targets: ['caddy:2019']"* ]]
    [[ "$output" == *"targets: ['node-exporter:9100']"* ]]
    [[ "$output" == *"targets: ['cadvisor:8080']"* ]]
    run grep -qE '__[A-Z][A-Z0-9_]*__' "$TMPDIR/prometheus.yml"
    [ "$status" -eq 1 ]
    # Parses as valid YAML.
    yq e '.' "$TMPDIR/prometheus.yml" >/dev/null
}
```

- [ ] **Step 2: Run the test, expect failure**

```bash
bats tests/integration/test_render.bats -f "render_prometheus_config"
```

Expected: FAIL.

- [ ] **Step 3: Create the template**

Create `compose/prometheus/prometheus.yml.tmpl`:

```yaml
# Prometheus scrape config — rendered by scripts/lib/render.sh::render_prometheus_config.
# Only __VPS_HOST__ is templated; everything else is static.
global:
  scrape_interval: 15s
  scrape_timeout: 10s
  external_labels:
    host: __VPS_HOST__
    env: prod

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['prometheus:9090']

  - job_name: node-exporter
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: cadvisor
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: caddy
    static_configs:
      - targets: ['caddy:2019']

  # JupyterLab — best-effort. jupyter_server exposes /metrics natively, but
  # the quay.io/jupyter/scipy-notebook image may require auth on this endpoint.
  # If the metrics-smoke test finds this target unreachable, remove this job
  # block (see Task 11 fallback).
  - job_name: jupyter
    metrics_path: /jupyter/metrics
    static_configs:
      - targets: ['jupyter:8888']
```

- [ ] **Step 4: Add `render_prometheus_config` to `scripts/lib/render.sh`**

At the end of `scripts/lib/render.sh`, append:

```bash
# render_prometheus_config <template_path> <output_path>
# Substitutes __VPS_HOST__ into the Prometheus scrape config. Mirrors
# render_loki_config in shape.
render_prometheus_config() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    sed -e "s|__VPS_HOST__|${VPS_HOST:?}|g" "$tmpl" > "$out"
}
```

- [ ] **Step 5: Run the test, expect PASS**

```bash
bats tests/integration/test_render.bats -f "render_prometheus_config"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add compose/prometheus scripts/lib/render.sh tests/integration/test_render.bats
git commit -m "feat(platform): add Prometheus scrape config template

Scrapes prometheus, node-exporter, cadvisor, caddy, and (best-effort)
jupyter. host + env labels applied as external_labels for forward-compat
with a second VPS.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Add the Prometheus Grafana datasource and flip Loki's default

**Files:**
- Create: `compose/grafana/provisioning/datasources/prometheus.yaml`
- Modify: `compose/grafana/provisioning/datasources/loki.yaml`
- Modify: `tests/integration/test_grafana_provisioning.bats` (if it exists; check before editing)

- [ ] **Step 1: Check whether `test_grafana_provisioning.bats` exists and inspect its existing assertions**

```bash
ls tests/integration/test_grafana_provisioning.bats
head -60 tests/integration/test_grafana_provisioning.bats
```

If the file exists, note the existing assertion patterns — we'll extend them. If it does not, skip writing the assertion test (the metrics-smoke bats in Task 12 will exercise the datasource end-to-end).

- [ ] **Step 2: Create the Prometheus datasource file**

Create `compose/grafana/provisioning/datasources/prometheus.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus       # stable uid so dashboard JSON references resolve
                          # to this datasource across re-imports (same reason
                          # as loki.yaml's uid: loki — see its comment).
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

- [ ] **Step 3: Flip Loki's `isDefault: true → false`**

Edit `compose/grafana/provisioning/datasources/loki.yaml`. Change line 10 from `    isDefault: true` to `    isDefault: false`. The dashboard at `client-logs.json` references Loki by `uid: loki`, so this change is purely about which datasource is preselected in Grafana's UI.

```bash
grep 'isDefault' compose/grafana/provisioning/datasources/loki.yaml
```

Expected: `    isDefault: false`.

- [ ] **Step 4: (If `test_grafana_provisioning.bats` exists) add assertions**

If the file existed in Step 1, append an assertion that both datasource files exist and contain the expected `isDefault` values:

```bash
@test "grafana provisioning: prometheus is default, loki is not" {
    grep -q '^    isDefault: true$' "$ROOT/compose/grafana/provisioning/datasources/prometheus.yaml"
    grep -q '^    isDefault: false$' "$ROOT/compose/grafana/provisioning/datasources/loki.yaml"
}

@test "grafana provisioning: prometheus datasource uses stable uid" {
    grep -q '^    uid: prometheus$' "$ROOT/compose/grafana/provisioning/datasources/prometheus.yaml"
}
```

Run:

```bash
bats tests/integration/test_grafana_provisioning.bats
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add compose/grafana/provisioning/datasources/
[[ -f tests/integration/test_grafana_provisioning.bats ]] && git add tests/integration/test_grafana_provisioning.bats
git commit -m "$(cat <<'EOF'
feat(platform): add Prometheus Grafana datasource and flip default

Prometheus becomes the default datasource (isDefault: true, uid:
prometheus). Loki keeps its stable uid but is no longer default;
client-logs.json references Loki via uid so it keeps working.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Add the dashboard JSONs

Four files. Three are derived from public Grafana marketplace dashboards; one is hand-rolled.

**Files:**
- Create: `compose/grafana/provisioning/dashboards/node-exporter-full.json`
- Create: `compose/grafana/provisioning/dashboards/cadvisor.json`
- Create: `compose/grafana/provisioning/dashboards/caddy.json`
- Create: `compose/grafana/provisioning/dashboards/platform.json`

- [ ] **Step 1: Download node-exporter-full (marketplace 1860)**

```bash
mkdir -p compose/grafana/provisioning/dashboards
curl -fsSL "https://grafana.com/api/dashboards/1860/revisions/latest/download" \
    -o compose/grafana/provisioning/dashboards/node-exporter-full.json
# Confirm it's valid JSON.
jq -e '.title' compose/grafana/provisioning/dashboards/node-exporter-full.json
```

Expected: prints `"Node Exporter Full"` (or similar title).

- [ ] **Step 2: Rewrite the datasource reference in node-exporter-full.json**

The marketplace JSON uses a `${DS_PROMETHEUS}` template variable. Replace it with a hard reference to our `prometheus` uid:

```bash
jq '
  walk(
    if type == "object" and .type == "prometheus" and (.uid // "" | startswith("${"))
    then .uid = "prometheus"
    elif type == "object" and (.datasource // null | type) == "object" and .datasource.type == "prometheus"
    then .datasource.uid = "prometheus"
    elif type == "string" and . == "${DS_PROMETHEUS}"
    then "prometheus"
    else . end
  ) | del(.__inputs) | del(.__requires)
' compose/grafana/provisioning/dashboards/node-exporter-full.json > /tmp/ne.json
mv /tmp/ne.json compose/grafana/provisioning/dashboards/node-exporter-full.json
# Sanity check.
jq -e '.title' compose/grafana/provisioning/dashboards/node-exporter-full.json
grep -c 'DS_PROMETHEUS' compose/grafana/provisioning/dashboards/node-exporter-full.json
```

Expected: title prints, `grep -c` prints `0`.

- [ ] **Step 3: Repeat for cAdvisor (marketplace 19908)**

```bash
curl -fsSL "https://grafana.com/api/dashboards/19908/revisions/latest/download" \
    -o compose/grafana/provisioning/dashboards/cadvisor.json
jq -e '.title' compose/grafana/provisioning/dashboards/cadvisor.json

jq '
  walk(
    if type == "object" and .type == "prometheus" and (.uid // "" | startswith("${"))
    then .uid = "prometheus"
    elif type == "object" and (.datasource // null | type) == "object" and .datasource.type == "prometheus"
    then .datasource.uid = "prometheus"
    elif type == "string" and . == "${DS_PROMETHEUS}"
    then "prometheus"
    else . end
  ) | del(.__inputs) | del(.__requires)
' compose/grafana/provisioning/dashboards/cadvisor.json > /tmp/ca.json
mv /tmp/ca.json compose/grafana/provisioning/dashboards/cadvisor.json
grep -c 'DS_PROMETHEUS' compose/grafana/provisioning/dashboards/cadvisor.json
```

Expected: `0`.

- [ ] **Step 4: Repeat for Caddy (marketplace 20802)**

```bash
curl -fsSL "https://grafana.com/api/dashboards/20802/revisions/latest/download" \
    -o compose/grafana/provisioning/dashboards/caddy.json
jq -e '.title' compose/grafana/provisioning/dashboards/caddy.json

jq '
  walk(
    if type == "object" and .type == "prometheus" and (.uid // "" | startswith("${"))
    then .uid = "prometheus"
    elif type == "object" and (.datasource // null | type) == "object" and .datasource.type == "prometheus"
    then .datasource.uid = "prometheus"
    elif type == "string" and . == "${DS_PROMETHEUS}"
    then "prometheus"
    else . end
  ) | del(.__inputs) | del(.__requires)
' compose/grafana/provisioning/dashboards/caddy.json > /tmp/cy.json
mv /tmp/cy.json compose/grafana/provisioning/dashboards/caddy.json
grep -c 'DS_PROMETHEUS' compose/grafana/provisioning/dashboards/caddy.json
```

Expected: `0`. If marketplace ID 20802 is unavailable or the dashboard's structure differs (different datasource template variable name), inspect the file manually (`jq '.__inputs' compose/grafana/provisioning/dashboards/caddy.json`) and adapt the `jq` rewrite. If no suitable upstream dashboard exists for Caddy v2 metrics on the day of implementation, **skip this file** and note the omission in the PR description; Task 11's metrics-smoke test does not assert dashboard files.

- [ ] **Step 5: Write the hand-rolled platform overview dashboard**

Create `compose/grafana/provisioning/dashboards/platform.json` with this content:

```json
{
  "annotations": { "list": [] },
  "editable": false,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": { "unit": "percent", "thresholds": { "mode": "absolute", "steps": [{ "color": "green", "value": null }, { "color": "yellow", "value": 70 }, { "color": "red", "value": 90 }] } },
        "overrides": []
      },
      "gridPos": { "h": 6, "w": 6, "x": 0, "y": 0 },
      "id": 1,
      "options": { "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false }, "showThresholdLabels": false, "showThresholdMarkers": true },
      "targets": [{ "expr": "100 - (avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)", "refId": "A" }],
      "title": "CPU %",
      "type": "gauge"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": { "unit": "percent", "thresholds": { "mode": "absolute", "steps": [{ "color": "green", "value": null }, { "color": "yellow", "value": 80 }, { "color": "red", "value": 95 }] } },
        "overrides": []
      },
      "gridPos": { "h": 6, "w": 6, "x": 6, "y": 0 },
      "id": 2,
      "options": { "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false }, "showThresholdMarkers": true },
      "targets": [{ "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100", "refId": "A" }],
      "title": "RAM %",
      "type": "gauge"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": {
        "defaults": { "unit": "percent", "thresholds": { "mode": "absolute", "steps": [{ "color": "green", "value": null }, { "color": "yellow", "value": 75 }, { "color": "red", "value": 90 }] } },
        "overrides": []
      },
      "gridPos": { "h": 6, "w": 6, "x": 12, "y": 0 },
      "id": 3,
      "options": { "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false }, "showThresholdMarkers": true },
      "targets": [{ "expr": "(1 - (node_filesystem_avail_bytes{mountpoint=\"/host/root\",fstype!~\"tmpfs|overlay\"} / node_filesystem_size_bytes{mountpoint=\"/host/root\",fstype!~\"tmpfs|overlay\"})) * 100", "refId": "A" }],
      "title": "Disk %",
      "type": "gauge"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": { "defaults": { "unit": "Bps" }, "overrides": [] },
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 6 },
      "id": 4,
      "options": { "legend": { "displayMode": "list", "placement": "bottom" }, "tooltip": { "mode": "multi", "sort": "desc" } },
      "targets": [
        { "expr": "rate(node_network_receive_bytes_total{device!~\"lo|veth.*|docker.*\"}[5m])", "legendFormat": "rx {{device}}", "refId": "A" },
        { "expr": "rate(node_network_transmit_bytes_total{device!~\"lo|veth.*|docker.*\"}[5m])", "legendFormat": "tx {{device}}", "refId": "B" }
      ],
      "title": "Network bytes/s",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": { "defaults": { "unit": "percent" }, "overrides": [] },
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 6 },
      "id": 5,
      "options": { "legend": { "displayMode": "table", "placement": "right", "calcs": ["mean", "lastNotNull"] }, "tooltip": { "mode": "multi", "sort": "desc" } },
      "targets": [{ "expr": "topk(8, rate(container_cpu_usage_seconds_total{name!=\"\"}[5m]) * 100)", "legendFormat": "{{name}}", "refId": "A" }],
      "title": "Top containers by CPU %",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "prometheus" },
      "fieldConfig": { "defaults": { "unit": "reqps" }, "overrides": [] },
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 14 },
      "id": 6,
      "options": { "legend": { "displayMode": "table", "placement": "bottom", "calcs": ["mean", "lastNotNull"] } },
      "targets": [{ "expr": "sum by (code, handler) (rate(caddy_http_requests_total[5m]))", "legendFormat": "{{handler}} {{code}}", "refId": "A" }],
      "title": "Caddy request rate by handler + status",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "tags": ["platform"],
  "templating": { "list": [] },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "browser",
  "title": "Platform overview",
  "uid": "platform-overview",
  "version": 1,
  "weekStart": ""
}
```

This is six panels: CPU%, RAM%, Disk% (gauges); network bytes/s and top-container CPU% (timeseries); Caddy request rate (timeseries). The Caddy panel will be empty until Caddy is scraped successfully; the others depend on node-exporter and cAdvisor.

- [ ] **Step 6: Validate every dashboard is valid JSON and has the expected datasource uid**

```bash
for f in compose/grafana/provisioning/dashboards/*.json; do
    echo "=== $f ==="
    jq -e '.title' "$f"
    # If the dashboard has any datasource references, they must use uid=prometheus or uid=loki.
    jq '[.. | select(type == "object") | select(.datasource? | type == "object") | .datasource.uid] | unique' "$f"
done
```

Expected: each prints a title, and the unique-uid array contains only `"prometheus"` (or `"loki"` for the existing client-logs dashboard, which is unmodified). Anything starting with `"${` is a leftover template variable that must be replaced manually.

- [ ] **Step 7: Commit**

```bash
git add compose/grafana/provisioning/dashboards/
git commit -m "$(cat <<'EOF'
feat(platform): add Prometheus-backed Grafana dashboards

- node-exporter-full.json (from marketplace ID 1860)
- cadvisor.json (from marketplace ID 19908)
- caddy.json (from marketplace ID 20802)
- platform.json (hand-rolled 6-panel overview)

All marketplace JSONs are committed verbatim with their datasource
template variable rewritten to the literal prometheus uid. Future
upstream drift is a manual refresh.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Wire `render_prometheus_config` into `scripts/deploy.sh`

**Files:**
- Modify: `scripts/deploy.sh`

- [ ] **Step 1: Add the prometheus staging directory and render call**

In `scripts/deploy.sh`, modify the `mkdir -p` line at the rendering step (current line 35) so it also creates the prometheus subdir:

Before:
```bash
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning" "$stage/siteapp" "$stage/shell"
```

After:
```bash
    mkdir -p "$stage/chisel" "$stage/loki" "$stage/grafana/provisioning" "$stage/siteapp" "$stage/shell" "$stage/prometheus"
```

Then, after the existing `render_loki_config` call (the line was at ~line 42), add:

```bash
    render_prometheus_config "$REPO_ROOT/compose/prometheus/prometheus.yml.tmpl" "$stage/prometheus/prometheus.yml"
```

- [ ] **Step 2: Run shellcheck**

```bash
shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh
```

Expected: no warnings.

- [ ] **Step 3: Run the deploy-stack-only bats (if it's in the cheap matrix), expect pass**

```bash
bats tests/integration/test_deploy_stack_only.bats
```

If this test exists, it asserts the deploy.sh `LDS_STACK_ONLY=1` path works without a roster — including the rendering step. Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(platform): wire render_prometheus_config into deploy.sh

The Prometheus scrape config is rendered into the staging dir
alongside the existing Loki config, then rsynced to the VPS where
docker-compose mounts it read-only.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: Add the metrics-smoke bats and verify the JupyterLab fallback

**Files:**
- Create: `tests/integration/test_metrics_smoke.bats`

This test is the cross-service wiring assertion that catches misconfigured scrape targets. It also resolves the JupyterLab fallback: if `/jupyter/metrics` doesn't return 200 unauth'd, we strip the jupyter job from the template.

- [ ] **Step 1: Create the metrics-smoke bats file**

Create `tests/integration/test_metrics_smoke.bats`:

```bash
#!/usr/bin/env bats
# Metrics-smoke — one fake-VPS bring-up, asserts Prometheus's view of every
# scrape target. The platform-level "everything wires together" tier for the
# metrics stack. Behavior assertions (specific PromQL outputs, dashboard
# panels) are intentionally not here.

load helpers

setup_file() {
    if ! compose_images_available; then
        echo "host docker can't reach all compose images (Docker Hub rate-limited?)" \
            > "$BATS_FILE_TMPDIR/skip"
        return 0
    fi
    bash "$ROOT/tests/integration/fake_vps/start.sh"
    setup_tmpdir
    cp "$ROOT/tests/integration/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\"" "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/flasher_upload_token"
    printf 'flasher-smoke-tok' > "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE" "$LDS_FLASHER_UPLOAD_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    load_siteapp_test_image
    load_flasher_test_image
    load_caddy_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_prometheus_ready
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

# Helper — poll Prometheus's /-/ready inside the fake VPS until 200 or timeout.
wait_prometheus_ready() {
    local i status
    for ((i=0; i<60; i++)); do
        status="$(docker exec lds-fake-vps bash -c "cd /srv/lab-bridge && docker compose exec -T prometheus wget -qO- -S http://localhost:9090/-/ready 2>&1 | awk '/HTTP/ {print \$2}' | head -n1")"
        if [[ "$status" == "200" ]]; then
            return 0
        fi
        sleep 1
    done
    echo "prometheus never became ready: last status='$status'"
    return 1
}

# Helper — fetch the Prometheus targets API as JSON.
_targets_json() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T prometheus wget -qO- 'http://localhost:9090/api/v1/targets?state=active'
    "
}

@test "prometheus: every expected scrape target reports health=up" {
    json="$(_targets_json)"
    [[ -n "$json" ]] || { echo "no targets JSON returned"; false; }
    # Required jobs that MUST be up. jupyter is asserted separately because
    # the scipy-notebook image's /metrics behavior is image-version-dependent.
    for job in prometheus node-exporter cadvisor caddy; do
        health="$(echo "$json" | jq -r --arg j "$job" '.data.activeTargets[] | select(.labels.job == $j) | .health' | head -n1)"
        [[ "$health" == "up" ]] || { echo "job=$job health=$health"; echo "$json" | jq '.data.activeTargets[] | select(.labels.job == "'$job'") | {scrapeUrl, health, lastError}'; false; }
    done
}

@test "prometheus: caddy /metrics is reachable (admin :2019 directive works)" {
    json="$(_targets_json)"
    # The caddy target's lastError must be empty (so the admin endpoint
    # is reachable on labnet) and its health must be up.
    last_error="$(echo "$json" | jq -r '.data.activeTargets[] | select(.labels.job == "caddy") | .lastError' | head -n1)"
    [[ -z "$last_error" || "$last_error" == "null" ]] || { echo "caddy lastError=$last_error"; false; }
}

@test "prometheus: jupyter /metrics is either up OR cleanly removed from config" {
    # Best-effort assertion: if the jupyter job is present, it must be up.
    # If it's absent (Task 11 fallback kicked in during planning), the test
    # passes trivially. This shape lets the test stay green whether or not
    # the scipy-notebook image is shipping /metrics on the pinned tag.
    json="$(_targets_json)"
    jupyter_present="$(echo "$json" | jq -r '.data.activeTargets[] | select(.labels.job == "jupyter") | .health' | head -n1)"
    if [[ -n "$jupyter_present" && "$jupyter_present" != "null" ]]; then
        [[ "$jupyter_present" == "up" ]] || { echo "jupyter scrape job present but health=$jupyter_present"; false; }
    fi
    true
}
```

- [ ] **Step 2: Run the metrics-smoke locally**

```bash
bats tests/integration/test_metrics_smoke.bats
```

If your local Docker can't pull all compose images, the test will `skip` cleanly (same pattern as `test_routes_smoke.bats`).

Expected: PASS (or all-skipped if images aren't reachable).

- [ ] **Step 3: If the jupyter test fails because `/jupyter/metrics` is unreachable**

If Step 2's "jupyter is either up OR cleanly removed" test fails because the jupyter job is present but `health="down"` with an auth-required error, fall back by removing the jupyter scrape job from `compose/prometheus/prometheus.yml.tmpl`. Delete the entire trailing block:

```yaml
  # JupyterLab — best-effort. jupyter_server exposes /metrics natively, but
  # the quay.io/jupyter/scipy-notebook image may require auth on this endpoint.
  # If the metrics-smoke test finds this target unreachable, remove this job
  # block (see Task 11 fallback).
  - job_name: jupyter
    metrics_path: /jupyter/metrics
    static_configs:
      - targets: ['jupyter:8888']
```

Replace with a comment marking the omission:

```yaml
  # JupyterLab /metrics was unreachable on the pinned scipy-notebook image;
  # the jupyter scrape job is intentionally absent here. Revisit when the
  # image surfaces an unauth'd /metrics endpoint or when we add a sidecar.
```

Re-run the metrics-smoke. Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_metrics_smoke.bats compose/prometheus/prometheus.yml.tmpl
git commit -m "$(cat <<'EOF'
test(platform): add metrics-smoke bats for the Prometheus stack

Brings up the fake VPS, waits for Prometheus ready, and asserts every
expected scrape target reports health=up. Jupyter is asserted only if
the target is present — the scipy-notebook image's /metrics behavior
is checked at implementation time and the scrape job is removed if
unauth'd access doesn't work.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Add the metrics-smoke matrix cell to `pr-platform.yml`

**Files:**
- Modify: `.github/workflows/pr-platform.yml`

- [ ] **Step 1: Add the new matrix cell**

In `.github/workflows/pr-platform.yml`, locate the `strategy.matrix.include` block (currently at line 75–94). Add a new entry between the existing `routes-smoke` and `navbar` entries (alphabetical order is fine):

```yaml
          - suite: metrics-smoke
            files: tests/integration/test_metrics_smoke.bats
```

The full block should look like:

```yaml
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
          - suite: metrics-smoke
            files: tests/integration/test_metrics_smoke.bats
          - suite: navbar
            files: tests/integration/test_navbar_smoke.bats
```

- [ ] **Step 2: Verify the workflow YAML parses**

```bash
yq e '.jobs.bats.strategy.matrix.include | length' .github/workflows/pr-platform.yml
```

Expected: `7` (was `6`).

- [ ] **Step 3: Confirm the aggregator `platform` job still depends only on `[changes, shellcheck, bats]`**

```bash
yq e '.jobs.platform.needs' .github/workflows/pr-platform.yml
```

Expected: `- changes\n- shellcheck\n- bats`. The matrix-cell additions don't affect the required-check name.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/pr-platform.yml
git commit -m "ci(platform): add metrics-smoke matrix cell

Asserts cross-service wiring of the Prometheus stack — every scrape
target reports health=up after fake-VPS bring-up. New matrix cell;
required check stays the platform aggregator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: Self-review and final sanity sweep

**Files:** none (verification only).

- [ ] **Step 1: Confirm no UA artifacts remain in the working tree**

```bash
grep -rn 'unified_agent\|UNIFIED_AGENT\|YC_FOLDER\|yc\.folder\|cr.yandex\|cloud_meta' \
    --exclude-dir=.git \
    --exclude-dir=.claude \
    --exclude-dir=node_modules \
    --include='*.sh' --include='*.yaml' --include='*.yml' --include='*.tmpl' --include='*.bats' --include='*.md' --include='*.json' \
    .
```

Expected output: only matches inside `docs/superpowers/specs/2026-05-18-unified-agent-monitoring-design.md` and `docs/superpowers/plans/2026-05-18-unified-agent-monitoring.md` (the superseded docs, which intentionally still reference UA). Everywhere else: zero matches.

- [ ] **Step 2: Run the full bats integration suite**

```bash
bats tests/integration/test_render.bats \
     tests/integration/test_config.bats \
     tests/integration/test_common.bats \
     tests/integration/test_crypto.bats \
     tests/integration/test_secrets.bats \
     tests/integration/test_grafana_provisioning.bats \
     tests/integration/test_deploy_stack_only.bats
```

Expected: every test passes.

- [ ] **Step 3: Run shellcheck across all scripts**

```bash
shellcheck -x --severity=warning scripts/*.sh scripts/lib/*.sh
```

Expected: no warnings.

- [ ] **Step 4: Render the full compose locally and visually scan it for sanity**

```bash
mkdir -p /tmp/lds-render-check
bash -c "
    source scripts/lib/common.sh
    source scripts/lib/config.sh
    source scripts/lib/render.sh
    export LDS_PINS_FILE=$PWD/tests/integration/fixtures/valid_pins.yaml
    load_config $PWD/tests/integration/fixtures/valid_config.yaml
    render_compose $PWD/compose/docker-compose.yml.tmpl /tmp/lds-render-check/docker-compose.yml
    render_caddyfile $PWD/compose/Caddyfile.tmpl /tmp/lds-render-check/Caddyfile
    render_prometheus_config $PWD/compose/prometheus/prometheus.yml.tmpl /tmp/lds-render-check/prometheus.yml
"
yq e '.services | keys' /tmp/lds-render-check/docker-compose.yml
yq e '.scrape_configs | map(.job_name)' /tmp/lds-render-check/prometheus.yml
grep 'admin :2019' /tmp/lds-render-check/Caddyfile
```

Expected:
- `services` keys include `caddy`, `chisel`, `flasher`, `grafana`, `jupyter`, `loki`, `siteapp`, `prometheus`, `node-exporter`, `cadvisor`. No `unified-agent`.
- `scrape_configs` lists `prometheus`, `node-exporter`, `cadvisor`, `caddy`, and either includes or omits `jupyter` (depending on Task 12 Step 3 outcome).
- `admin :2019` appears in the rendered Caddyfile.

- [ ] **Step 5: Confirm the commit log is coherent**

```bash
git log --oneline main..HEAD
```

Expected output (order may vary slightly):

```
<sha> ci(platform): add metrics-smoke matrix cell
<sha> test(platform): add metrics-smoke bats for the Prometheus stack
<sha> feat(platform): wire render_prometheus_config into deploy.sh
<sha> feat(platform): add Prometheus-backed Grafana dashboards
<sha> feat(platform): add Prometheus Grafana datasource and flip default
<sha> feat(platform): add Prometheus scrape config template
<sha> feat(platform): bind Caddy admin :2019 on labnet for Prometheus scrape
<sha> feat(platform): add cAdvisor service for per-container metrics
<sha> feat(platform): add node-exporter service for host metrics
<sha> feat(platform): add prometheus service to compose template
<sha> feat(platform): add Prometheus stack pins to pins.yaml schema
<sha> refactor(platform): remove Yandex Unified Agent code surface
```

- [ ] **Step 6: Push the branch and open the PR**

```bash
git push -u origin feat/vps-metrics-prometheus
gh pr create --title "feat(platform): swap host monitoring from Yandex Unified Agent to Prometheus + Grafana stack" --body "$(cat <<'EOF'
## Summary

- Removes the just-merged Yandex Unified Agent code surface (~280 lines).
- Adds a vendor-neutral Prometheus + node-exporter + cAdvisor stack on `labnet`, scraping Caddy's admin endpoint and (best-effort) JupyterLab's `/metrics`.
- Ships Grafana dashboards as committed JSON: node-exporter-full (Marketplace 1860), cAdvisor (19908), Caddy (20802), and a hand-rolled platform overview.
- Adds a `metrics-smoke` bats cell to `pr-platform.yml` that asserts every scrape target reports `health=up` on the fake-VPS bring-up.

Spec: `docs/superpowers/specs/2026-05-18-vps-metrics-design.md`. The UA spec + plan are retained with supersession banners.

## Known caveats

1. **JupyterLab `/metrics`** — best-effort scrape job; removed from `prometheus.yml.tmpl` if unauth'd access doesn't work on the pinned scipy-notebook image. Document the omission here if it kicked in.
2. **Caddy admin API on `labnet`** — `admin :2019` makes Caddy's admin reachable from any labnet container. Trust model is the same as we already accept for Loki/Grafana inter-service traffic.
3. **No off-VPS metric history** — Prometheus TSDB is local; same property as Loki today.

## Test plan

- [x] `bats tests/integration/test_render.bats` — all PASS
- [x] `bats tests/integration/test_config.bats` — all PASS
- [x] `bats tests/integration/test_metrics_smoke.bats` — all PASS (or SKIP on image-pull rate-limit)
- [ ] Post-merge, post-deploy: confirm Grafana renders the platform dashboard against prod prometheus.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Note: `gh pr create` runs `pr-platform.yml` automatically. Watch the matrix cells — especially `metrics-smoke` — and address any cell that fails.

---

## Post-merge verification (manual, after CI deploys and after operator runs `task deploy`)

These are not steps in this plan; they're the operator's checklist after the release ships. Recorded here so the PR body and the release notes have a shared reference.

1. `task remote:status` — every container reports `Up`.
2. Browse `https://<vps>/grafana/`. Under Connections → Data sources, both Prometheus and Loki should be listed; "Test" both, expect green. The default datasource for new panels should be Prometheus.
3. Open the `Platform overview` dashboard. All gauges should show data within a minute. Top-container CPU and Network bytes/s should populate from node-exporter and cAdvisor. Caddy request rate may be empty until Caddy serves traffic, then populates.
4. SSH to the VPS:

```bash
docker compose -f /srv/lab-bridge/docker-compose.yml exec prometheus \
    wget -qO- localhost:9090/api/v1/targets \
    | jq '.data.activeTargets[] | {job: .labels.job, health, lastError}'
```

Every target reports `"health": "up"` and `"lastError": ""` (or omits `lastError`).

---

## Self-review checklist

This plan was reviewed against the spec before publication. Notable cross-references:

- **Spec § Component shape** → Tasks 4 (prometheus), 5 (node-exporter), 6 (cadvisor).
- **Spec § Scrape configuration** → Task 8 (template) + Task 12 (jupyter fallback verification).
- **Spec § Grafana wiring** → Task 9 (datasource + Loki default flip) + Task 10 (dashboard JSONs).
- **Spec § Render-layer changes** → Task 2 (rip-out) + Tasks 4–6 (placeholders) + Task 8 (render fn) + Task 11 (deploy.sh wiring).
- **Spec § Compose template changes** → Tasks 4–7.
- **Spec § Compose directory layout** → Task 2 (delete) + Task 8 (create) + Task 9–10 (grafana provisioning).
- **Spec § Spec/plan supersession** → already done in commit `1446a85`; not in this plan.
- **Spec § Testing** → Tasks 3 (config schema), 4–7 (render-bats), 12 (metrics-smoke), 13 (matrix cell).
- **Spec § Rollout** → Task 14 (PR creation).
- **Spec § Known caveats** → carried into Task 14's PR body.

Type/name consistency checks:
- `render_prometheus_config` — defined in Task 8, called in Task 11.
- `PROMETHEUS_IMAGE`, `NODE_EXPORTER_IMAGE`, `CADVISOR_IMAGE`, `PROMETHEUS_RETENTION_DAYS` — defined in Task 3, consumed in Tasks 4–6 + 8.
- Placeholder names `__PROMETHEUS_IMAGE__`, `__NODE_EXPORTER_IMAGE__`, `__CADVISOR_IMAGE__`, `__PROMETHEUS_RETENTION_DAYS__`, `__VPS_HOST__` — match between template (Tasks 4/5/6/8) and `sed` invocations (Tasks 4/5/6 + 8).
- Datasource `uid: prometheus` — set in Task 9 (datasource yaml), referenced by Task 10 (dashboards).

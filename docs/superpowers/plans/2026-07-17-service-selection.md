# Service Selection (optional-service deploys) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A gitignored `disabled_services` list in `config.yaml` that removes optional services (jupyter, monitoring group, studio, streamer, flasher) from the rendered deploy artifacts, so low-budget VPS instances skip heavy containers.

**Architecture:** Render-time filtering. `load_config` exports the disabled set; a `yq` post-pass deletes disabled services (+ `depends_on` and orphaned `secrets:` entries) from the rendered compose file; marker-wrapped Caddyfile route blocks are stripped; the navbar hides disabled entries via a `data-disabled` attribute Caddy injects; `deploy.sh` gates secret staging, config renders, restart lists, and healthcheck probes; CI learns the selection from a `LDS_DISABLED_SERVICES` GH variable envsubst'd into the CI config.

**Tech Stack:** bash (macOS bash 3.2 compatible), yq v4, sed, bats, GitHub Actions composite action.

**Spec:** `docs/superpowers/specs/2026-07-17-service-selection-design.md`

## Global Constraints

- Optional service names (exact): `jupyter`, `monitoring`, `studio`, `streamer`, `flasher`. Core (never disableable): `caddy`, `authelia`, `siteapp`, `chisel`.
- `monitoring` expands to compose services: `grafana loki prometheus node-exporter cadvisor`.
- Navbar-id mapping: `jupyter`→`jupyter`, `monitoring`→`grafana`, `studio`→`studio`, `flasher`→`flasher`, `streamer`→(no navbar entry).
- Absent `disabled_services` key or `[]` MUST render byte-identical behavior to today (full stack).
- Shell code must pass `shellcheck -x --severity=warning` and run on macOS bash 3.2 (no `mapfile`, no `${var,,}`; use `"${arr[@]:-}"` for possibly-empty arrays).
- Never edit root `VERSION`; PR title must be Conventional Commits.
- Work happens on branch `feat/service-selection` (already exists, has the spec commit).
- All commits: `git commit -m "<type>: <subject>"` with the repo's standard trailer lines (see existing history).

---

### Task 1: Registry, validation, and exports in config.sh

**Files:**
- Modify: `scripts/lib/config.sh` (registry after `_REQUIRED_PINS_FIELDS` ~line 50; validation inside `validate_config` after the chisel_clients loop ~line 118; exports at end of `load_config` ~line 177; helper after `load_config`)
- Create: `tests/integration/test_service_selection_render.bats`
- Modify: `.github/workflows/pr-platform.yml:78-86` (add new bats file to the `cheap` cell)

**Interfaces:**
- Produces: shell arrays `_OPTIONAL_SERVICES`, `_CORE_SERVICES`, `_MONITORING_COMPOSE_SERVICES` in config.sh; env vars `DISABLED_SERVICES` (space-separated group names, e.g. `"jupyter monitoring"`) and `DISABLED_COMPOSE_SERVICES` (space-separated compose names, e.g. `"jupyter grafana loki prometheus node-exporter cadvisor"`) exported by `load_config`; function `service_disabled <group-name>` returning 0/1. Tasks 2–4 consume all of these.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_service_selection_render.bats`:

```bash
#!/usr/bin/env bats
# Validation + render tier for optional-service selection. No containers.
# Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md

load helpers

setup() {
    setup_tmpdir
    export LDS_PINS_FILE="$ROOT/tests/integration/fixtures/valid_pins.yaml"
}
teardown() { teardown_tmpdir; }

# Write a minimal valid config with the given disabled_services YAML list.
# Usage: write_config '[jupyter, monitoring]'   — or '' to omit the key.
write_config() {
    cat > "$TMPDIR/config.yaml" <<'CFG'
vps: { host: 192.0.2.10, ssh_user: khamit }
jupyter: { password_hash: "sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" }
chisel_clients: []
CFG
    if [[ -n "$1" ]]; then
        printf 'disabled_services: %s\n' "$1" >> "$TMPDIR/config.yaml"
    fi
}

@test "validate_config: accepts every optional name" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -eq 0 ]
}

@test "validate_config: rejects an unknown service name" {
    write_config '[jupyterlab]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"jupyterlab"* ]]
    [[ "$output" == *"allowed"* ]]
}

@test "validate_config: rejects disabling a core service" {
    write_config '[caddy]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"core service"* ]]
}

@test "validate_config: rejects duplicate entries" {
    write_config '[jupyter, jupyter]'
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/config.yaml"
    [ "$status" -ne 0 ]
    [[ "$output" == *"duplicate"* ]]
}

@test "load_config: absent key exports empty DISABLED_* vars" {
    write_config ''
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $TMPDIR/config.yaml; echo \"[\$DISABLED_SERVICES][\$DISABLED_COMPOSE_SERVICES]\""
    [ "$status" -eq 0 ]
    [[ "$output" == *"[][]"* ]]
}

@test "load_config: monitoring expands to the five compose services" {
    write_config '[monitoring, flasher]'
    run bash -c "source $ROOT/scripts/lib/config.sh; load_config $TMPDIR/config.yaml; echo \"[\$DISABLED_SERVICES]\"; echo \"[\$DISABLED_COMPOSE_SERVICES]\""
    [ "$status" -eq 0 ]
    [[ "$output" == *"[monitoring flasher]"* ]]
    [[ "$output" == *"[grafana loki prometheus node-exporter cadvisor flasher]"* ]]
}

@test "service_disabled: matches group names only" {
    write_config '[monitoring]'
    run bash -c "
        source $ROOT/scripts/lib/config.sh
        load_config $TMPDIR/config.yaml
        service_disabled monitoring && echo yes-monitoring
        service_disabled jupyter || echo no-jupyter
        service_disabled grafana || echo no-grafana
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"yes-monitoring"* ]]
    [[ "$output" == *"no-jupyter"* ]]
    [[ "$output" == *"no-grafana"* ]]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: the first four may PASS or FAIL depending on yq null handling (unknown keys are currently ignored — the reject tests FAIL because validate_config exits 0), and the `load_config`/`service_disabled` tests FAIL (unset variable / command not found).

- [ ] **Step 3: Implement in scripts/lib/config.sh**

After the `_REQUIRED_PINS_FIELDS=( ... )` block (line ~50), add:

```bash
# Optional-service selection (spec: 2026-07-17-service-selection-design.md).
# The ONLY names an operator may list in config.yaml's disabled_services.
# `monitoring` is a group name expanding to the five observability compose
# services. Core services are deliberately absent — the platform cannot
# run without them.
_OPTIONAL_SERVICES=(jupyter monitoring studio streamer flasher)
_CORE_SERVICES=(caddy authelia siteapp chisel)
_MONITORING_COMPOSE_SERVICES=(grafana loki prometheus node-exporter cadvisor)
```

In `validate_config`, after the chisel_clients duplicate-port loop (ends ~line 118), add:

```bash
    # disabled_services: every entry must be a known optional service name.
    local ds_count j entry opt known core
    local seen_ds=()
    ds_count="$(_yq e '.disabled_services | length' "$config_path")"
    for ((j=0; j<ds_count; j++)); do
        entry="$(_yq e ".disabled_services[$j]" "$config_path")"
        known=false
        for opt in "${_OPTIONAL_SERVICES[@]}"; do
            [[ "$entry" == "$opt" ]] && known=true
        done
        if ! $known; then
            core=false
            for opt in "${_CORE_SERVICES[@]}"; do
                [[ "$entry" == "$opt" ]] && core=true
            done
            if $core; then
                errors+=("disabled_services: '$entry' is a core service and cannot be disabled")
            else
                errors+=("disabled_services: unknown service '$entry' (allowed: ${_OPTIONAL_SERVICES[*]})")
            fi
        fi
        for seen in "${seen_ds[@]:-}"; do
            [[ "$seen" == "$entry" ]] && errors+=("disabled_services: duplicate entry '$entry'")
        done
        seen_ds+=("$entry")
    done
```

At the end of `load_config` (after the `AUTHELIA_GRAFANA_OIDC_SECRET_HASH` line), add:

```bash
    # Optional-service selection. DISABLED_SERVICES carries the raw group
    # names (probe/secret/Caddyfile gating); DISABLED_COMPOSE_SERVICES the
    # compose-level expansion (filter_compose).
    export DISABLED_SERVICES
    DISABLED_SERVICES="$(_yq e '(.disabled_services // [])[]' "$config_path" | tr '\n' ' ' | sed 's/ *$//')"
    local _dcs="" _svc
    for _svc in $DISABLED_SERVICES; do
        if [[ "$_svc" == "monitoring" ]]; then
            _dcs+=" ${_MONITORING_COMPOSE_SERVICES[*]}"
        else
            _dcs+=" $_svc"
        fi
    done
    export DISABLED_COMPOSE_SERVICES
    DISABLED_COMPOSE_SERVICES="${_dcs# }"
```

After the closing `}` of `load_config`, add:

```bash
# service_disabled <name> — succeed when <name> (a GROUP name like
# "monitoring", never a compose-level name like "grafana") is disabled.
# Requires load_config to have run.
service_disabled() {
    local svc
    for svc in ${DISABLED_SERVICES:-}; do
        [[ "$svc" == "$1" ]] && return 0
    done
    return 1
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_service_selection_render.bats && bats tests/integration/test_config.bats`
Expected: all PASS (test_config.bats guards against regressions).

Run: `shellcheck -x --severity=warning scripts/lib/config.sh`
Expected: no output, exit 0.

- [ ] **Step 5: Add the file to the cheap CI cell**

In `.github/workflows/pr-platform.yml`, the `cheap` matrix entry's `files:` list, append after `tests/integration/test_deploy_stack_only.bats`:

```yaml
              tests/integration/test_service_selection_render.bats
```

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/config.sh tests/integration/test_service_selection_render.bats .github/workflows/pr-platform.yml
git commit -m "feat: disabled_services registry, validation, and exports in config.sh"
```

---

### Task 2: filter_compose in render.sh

**Files:**
- Modify: `scripts/lib/render.sh` (new function after `render_compose`; call it at the end of `render_compose` ~line 88)
- Test: `tests/integration/test_service_selection_render.bats` (append)

**Interfaces:**
- Consumes: `DISABLED_COMPOSE_SERVICES` (Task 1).
- Produces: `filter_compose <compose_path>` — mutates the file in place; also wired into `render_compose` so every caller gets filtering automatically. No-op when `DISABLED_COMPOSE_SERVICES` is empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_service_selection_render.bats`:

```bash
# Render the full compose template honoring $TMPDIR/config.yaml's
# disabled_services, into $TMPDIR/docker-compose.yml.
render_full_compose() {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
    "
}

@test "filter_compose: disabled services are removed, core stays" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    render_full_compose
    local gone
    for gone in jupyter grafana loki prometheus node-exporter cadvisor studio streamer flasher; do
        run yq e ".services | has(\"$gone\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "false" ]] || { echo "service '$gone' still present"; false; }
    done
    local kept
    for kept in caddy authelia siteapp chisel; do
        run yq e ".services | has(\"$kept\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "true" ]] || { echo "service '$kept' missing"; false; }
    done
}

@test "filter_compose: caddy depends_on is pruned to remaining services" {
    write_config '[jupyter, monitoring]'
    render_full_compose
    run yq e -o=json -I=0 '.services.caddy.depends_on' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == '["siteapp","flasher","streamer","studio","authelia"]' ]]
}

@test "filter_compose: unreferenced top-level secrets are pruned" {
    write_config '[monitoring, flasher]'
    render_full_compose
    local gone
    for gone in grafana_admin_password grafana_oidc_secret flasher_upload_token; do
        run yq e ".secrets | has(\"$gone\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "false" ]] || { echo "secret '$gone' still present"; false; }
    done
    local kept
    for kept in agent_upload_token authelia_jwt_secret authelia_session_secret authelia_storage_encryption_key authelia_oidc_hmac_secret authelia_oidc_jwks_key; do
        run yq e ".secrets | has(\"$kept\")" "$TMPDIR/docker-compose.yml"
        [[ "$output" == "true" ]] || { echo "secret '$kept' missing"; false; }
    done
}

@test "filter_compose: empty disabled list keeps all 13 services and 9 secrets" {
    write_config ''
    render_full_compose
    run yq e '.services | length' "$TMPDIR/docker-compose.yml"
    [[ "$output" == "13" ]]
    run yq e '.secrets | length' "$TMPDIR/docker-compose.yml"
    [[ "$output" == "9" ]]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: the three filter tests FAIL (services still present); the empty-list test PASSES (current behavior).

- [ ] **Step 3: Implement filter_compose in scripts/lib/render.sh**

At the end of `render_compose` (after the `sed ... > "$out"` pipeline, before the closing `}`), add:

```bash
    filter_compose "$out"
```

After `render_compose`'s closing `}`, add:

```bash
# filter_compose <compose_path> — strip disabled services from a rendered
# compose file, in place (spec: 2026-07-17-service-selection-design.md).
# Reads DISABLED_COMPOSE_SERVICES (exported by load_config). Beyond deleting
# the service entries, the file must stay deployable: a depends_on reference
# to a deleted service aborts `docker compose up`, and a top-level secret
# whose file is no longer staged aborts it too.
filter_compose() {
    local file="${1:?}"
    [[ -z "${DISABLED_COMPOSE_SERVICES:-}" ]] && return 0
    local name
    for name in $DISABLED_COMPOSE_SERVICES; do
        yq -i "del(.services.\"$name\")" "$file"
        yq -i "with(.services[]; select(has(\"depends_on\")) | .depends_on |= map(select(. != \"$name\")))" "$file"
    done
    # Prune top-level secrets no longer referenced by any remaining service.
    local referenced sname
    referenced="$(yq e '.services[] | .secrets // [] | .[]' "$file")"
    for sname in $(yq e '.secrets // {} | keys | .[]' "$file"); do
        if ! grep -qx "$sname" <<< "$referenced"; then
            yq -i "del(.secrets.\"$sname\")" "$file"
        fi
    done
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_service_selection_render.bats && bats tests/integration/test_render.bats`
Expected: all PASS (test_render.bats proves default rendering is unchanged — its fixtures have no `disabled_services`, so `filter_compose` early-returns).

Run: `shellcheck -x --severity=warning scripts/lib/render.sh`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/render.sh tests/integration/test_service_selection_render.bats
git commit -m "feat: filter disabled services out of the rendered compose file"
```

---

### Task 3: Caddyfile markers + route stripping + navbar hiding

**Files:**
- Modify: `compose/Caddyfile.tmpl` (marker comments around 6 blocks; `data-disabled` attr in the `inject_navbar` snippet line 49)
- Modify: `scripts/lib/render.sh:91-101` (`render_caddyfile`)
- Modify: `compose/shell/navbar.js` (DISABLED_IDS constant + SERVICES filter, lines ~13-31)
- Test: `tests/integration/test_service_selection_render.bats` (append)

**Interfaces:**
- Consumes: `DISABLED_SERVICES` (Task 1).
- Produces: rendered Caddyfile without disabled routes; navbar `<script>` tag carrying `data-disabled="<comma-separated navbar ids>"` (always substituted, empty string when nothing disabled). Marker syntax for future services: `# --- BEGIN svc:<group-name> ---` / `# --- END svc:<group-name> ---`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_service_selection_render.bats`:

```bash
render_full_caddyfile() {
    bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $TMPDIR/config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
    "
}

@test "render_caddyfile: disabled routes are stripped, core routes stay" {
    write_config '[jupyter, monitoring, studio, streamer, flasher]'
    render_full_caddyfile
    run cat "$TMPDIR/Caddyfile"
    ! grep -q 'reverse_proxy jupyter:8888'  <<< "$output"
    ! grep -q 'reverse_proxy grafana:3000'  <<< "$output"
    ! grep -q 'reverse_proxy flasher:8000'  <<< "$output"
    ! grep -q 'reverse_proxy streamer:8000' <<< "$output"
    ! grep -q 'reverse_proxy studio:8000'   <<< "$output"
    ! grep -q 'redir /studio'               <<< "$output"
    ! grep -q 'redir @old_jupyter'          <<< "$output"
    grep -q 'reverse_proxy siteapp:8000'  <<< "$output"
    grep -q 'reverse_proxy authelia:9091' <<< "$output"
    grep -q 'handle_errors'               <<< "$output"
    ! grep -qE '__[A-Z][A-Z0-9_]*__' <<< "$output"
}

@test "render_caddyfile: data-disabled maps monitoring to grafana and omits streamer" {
    write_config '[jupyter, monitoring, streamer]'
    render_full_caddyfile
    grep -q 'data-disabled="jupyter,grafana"' "$TMPDIR/Caddyfile"
}

@test "render_caddyfile: nothing disabled renders empty data-disabled and all routes" {
    write_config ''
    render_full_caddyfile
    grep -q 'data-disabled=""' "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy jupyter:8888'  "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy grafana:3000'  "$TMPDIR/Caddyfile"
    grep -q 'reverse_proxy streamer:8000' "$TMPDIR/Caddyfile"
}

@test "Caddyfile.tmpl: svc markers are balanced" {
    local begins ends
    begins="$(grep -c 'BEGIN svc:' "$ROOT/compose/Caddyfile.tmpl")"
    ends="$(grep -c 'END svc:' "$ROOT/compose/Caddyfile.tmpl")"
    [ "$begins" -eq "$ends" ]
    [ "$begins" -ge 6 ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: the four new tests FAIL (no markers, no data-disabled attr yet).

- [ ] **Step 3: Add markers + data-disabled to compose/Caddyfile.tmpl**

Change the `inject_navbar` snippet (line 49) to:

```
        "</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" data-version="__PLATFORM_VERSION__" data-disabled="__DISABLED_NAV__" defer></script></head>`
```

Wrap six blocks in marker comments (marker lines are plain Caddyfile comments; they remain — harmlessly — in renders where the service is enabled). Indent markers to match the block they wrap:

1. `flasher` — before the `# ─── Flasher …` header comment (line 143) insert `    # --- BEGIN svc:flasher ---`; after the `handle /flash*` block's closing `}` (line 154) insert `    # --- END svc:flasher ---`.
2. `streamer` — before `# ─── Streamer …` (line 156): `    # --- BEGIN svc:streamer ---`; after the `handle /streamer/*` closing `}` (line 172): `    # --- END svc:streamer ---`.
3. `studio` — before `# ─── Experiment Studio …` (line 174): `    # --- BEGIN svc:studio ---`; after the `handle /studio/*` closing `}` (line 196): `    # --- END svc:studio ---`. (The `redir /studio /studio/ 308` sits inside the block.)
4. `monitoring` — before `# ─── Grafana …` (line 198): `    # --- BEGIN svc:monitoring ---`; after the `handle /grafana/*` closing `}` (line 218): `    # --- END svc:monitoring ---`.
5. `jupyter` (first pair) — before `# ─── JupyterLab …` (line 220): `    # --- BEGIN svc:jupyter ---`; after the `handle /jupyter*` closing `}` (line 234): `    # --- END svc:jupyter ---`.
6. `jupyter` (second pair, old-bookmark redirect) — before `# ─── Temporary redirect for old Jupyter bookmarks …` (line 236): `    # --- BEGIN svc:jupyter ---`; after `redir @old_jupyter /jupyter{uri} 302` (line 240): `    # --- END svc:jupyter ---`. (sed range-deletes handle repeated BEGIN/END pairs with the same name.)

- [ ] **Step 4: Implement stripping in render_caddyfile (scripts/lib/render.sh)**

Replace the body of `render_caddyfile` with:

```bash
# render_caddyfile <template_path> <output_path>
render_caddyfile() {
    local tmpl="${1:?}" out="${2:?}"
    [[ -f "$tmpl" ]] || die "template not found: $tmpl"
    local platform_version
    platform_version="$(_unified_version)"
    # data-disabled carries navbar-entry ids for services disabled on this
    # instance; navbar.js hides matching entries. Mapping: monitoring's
    # navbar id is "grafana"; streamer has no navbar entry.
    local svc disabled_nav=""
    for svc in ${DISABLED_SERVICES:-}; do
        case "$svc" in
            monitoring) disabled_nav+="${disabled_nav:+,}grafana" ;;
            streamer)   ;;
            *)          disabled_nav+="${disabled_nav:+,}$svc" ;;
        esac
    done
    sed \
        -e "s|__ACME_EMAIL__|${CADDY_ACME_EMAIL:?}|g" \
        -e "s|__VPS_HOST__|${VPS_HOST:?}|g" \
        -e "s|__PLATFORM_VERSION__|${platform_version}|g" \
        -e "s|__DISABLED_NAV__|${disabled_nav}|g" \
        "$tmpl" > "$out"
    # Strip the marked route blocks of disabled services; their paths then
    # fall through to the catch-all → styled 404. sed -i.bak is the
    # BSD/GNU-portable in-place form.
    for svc in ${DISABLED_SERVICES:-}; do
        sed -i.bak "/# --- BEGIN svc:$svc ---/,/# --- END svc:$svc ---/d" "$out"
        rm -f "$out.bak"
    done
}
```

- [ ] **Step 5: Hide disabled entries in compose/shell/navbar.js**

After the `PLATFORM_VERSION` IIFE (ends line 20), insert:

```js
  // Navbar ids disabled on this instance. Caddy substitutes the
  // data-disabled attr at deploy time (Caddyfile.tmpl inject_navbar).
  const DISABLED_IDS = (function () {
    const scripts = document.querySelectorAll('script[src*="/_shared/navbar.js"]');
    for (const s of scripts) {
      const v = s.getAttribute('data-disabled');
      if (v != null) return new Set(v.split(',').map((x) => x.trim()).filter(Boolean));
    }
    return new Set();
  })();
```

Change the `SERVICES` array's closing bracket (line 31) from `];` to:

```js
  ].filter((svc) => !DISABLED_IDS.has(svc.id));
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `bats tests/integration/test_service_selection_render.bats && bats tests/integration/test_render.bats`
Expected: all PASS (test_render.bats's caddyfile tests confirm enabled-path rendering is intact; its `__[A-Z]*__` leftover check confirms `__DISABLED_NAV__` is always substituted).

Run: `shellcheck -x --severity=warning scripts/lib/render.sh && node --check compose/shell/navbar.js`
Expected: exit 0 for both.

- [ ] **Step 7: Commit**

```bash
git add compose/Caddyfile.tmpl scripts/lib/render.sh compose/shell/navbar.js tests/integration/test_service_selection_render.bats
git commit -m "feat: strip disabled-service Caddy routes and hide their navbar entries"
```

---

### Task 4: deploy.sh gating (secrets, renders, restarts, healthcheck)

**Files:**
- Modify: `scripts/deploy.sh` (config renders ~47-51; grafana password ~66-68; grafana OIDC secret ~74-77; flasher token ~109-114; restart list ~204-209; healthcheck probes ~229-286)
- Test: `tests/integration/test_service_selection_render.bats` (append)

**Interfaces:**
- Consumes: `service_disabled` (Task 1); filtering already happens inside `render_compose`/`render_caddyfile` (Tasks 2–3).
- Produces: deploy.sh that succeeds without grafana/flasher secret files when those services are disabled; restart list omitting disabled services; healthcheck status `skip` sentinel for disabled probes.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_service_selection_render.bats`:

```bash
# rsync/ssh spies that LOG their args (helpers' setup_fake_rsync_spy
# swallows ssh args; we need them to assert the restart list).
setup_logging_spies() {
    mkdir -p "$BATS_TEST_TMPDIR/spy_bin"
    cat > "$BATS_TEST_TMPDIR/spy_bin/rsync" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >> "$BATS_TEST_TMPDIR/rsync.log"
EOF
    cat > "$BATS_TEST_TMPDIR/spy_bin/ssh" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >> "$BATS_TEST_TMPDIR/ssh.log"
EOF
    chmod +x "$BATS_TEST_TMPDIR/spy_bin/rsync" "$BATS_TEST_TMPDIR/spy_bin/ssh"
    export PATH="$BATS_TEST_TMPDIR/spy_bin:$PATH"
}

@test "deploy.sh: disabled monitoring/flasher/streamer need no secrets and are not restarted" {
    write_config '[monitoring, flasher, streamer]'
    export LDS_CONFIG="$TMPDIR/config.yaml"
    stub_authelia_for_tests
    # Agent token is core (siteapp) — still required.
    printf 'tok' > "$TMPDIR/agent_upload_token"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    # Point the gated secrets at NONEXISTENT paths: with the gating in
    # place deploy.sh must not require them.
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/absent_grafana_pw"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/absent_flasher_tok"
    setup_logging_spies

    LDS_SKIP_HEALTHCHECK=1 run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]

    # rsync ran (stage was fully assembled without the gated secrets).
    [ -s "$BATS_TEST_TMPDIR/rsync.log" ]

    # The remote command restarts only enabled services.
    run cat "$BATS_TEST_TMPDIR/ssh.log"
    [[ "$output" == *"docker compose restart"* ]]
    restart_line="$(grep -o 'docker compose restart.*' "$BATS_TEST_TMPDIR/ssh.log")"
    [[ "$restart_line" == *"caddy"* ]]
    [[ "$restart_line" == *"siteapp"* ]]
    [[ "$restart_line" != *"grafana"* ]]
    [[ "$restart_line" != *"streamer"* ]]
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: new test FAILS — deploy.sh dies with `grafana admin password not found`.

- [ ] **Step 3: Implement the gating in scripts/deploy.sh**

(a) Replace lines 47-51 (loki/prometheus renders + grafana provisioning copy):

```bash
    if ! service_disabled monitoring; then
        render_loki_config  "$REPO_ROOT/compose/loki/config.yaml.tmpl"   "$stage/loki/config.yaml"
        render_prometheus_config "$REPO_ROOT/compose/prometheus/prometheus.yml.tmpl" "$stage/prometheus/prometheus.yml"

        # Static Grafana provisioning — datasource + dashboard provider + dashboard JSON.
        cp -R "$REPO_ROOT/compose/grafana/provisioning/." "$stage/grafana/provisioning/"
    fi
```

(b) Wrap the grafana admin-password block (the `local pwfile=` … `install -m 644 …` lines, ~66-68) in:

```bash
    if ! service_disabled monitoring; then
        local pwfile="${LDS_GRAFANA_PASSWORD_FILE:-$REPO_ROOT/compose/grafana/admin_password}"
        [[ -f "$pwfile" ]] || die "grafana admin password not found at $pwfile — run: task secrets:set-grafana-password"
        install -m 644 "$pwfile" "$stage/grafana/admin_password"
    fi
```

(c) Inside the existing `if [[ "${LDS_STACK_ONLY:-}" != "1" ]]` block, wrap only the grafana OIDC secret staging (~75-77) in:

```bash
        if ! service_disabled monitoring; then
            local grafana_oidc_secret_file="${LDS_GRAFANA_OIDC_SECRET_FILE:-$REPO_ROOT/compose/grafana/oidc_secret}"
            [[ -f "$grafana_oidc_secret_file" ]] || die "grafana OIDC secret not found at $grafana_oidc_secret_file — run: task secrets:bootstrap-authelia"
            install -m 644 "$grafana_oidc_secret_file" "$stage/grafana/oidc_secret"
        fi
```

(the Authelia secrets + users DB staging that follows stays unconditional).

(d) Wrap the flasher upload-token block (~109-114) in:

```bash
    if ! service_disabled flasher; then
        local flashertokfile="${LDS_FLASHER_UPLOAD_TOKEN_FILE:-$REPO_ROOT/compose/flasher/upload_token}"
        [[ -f "$flashertokfile" ]] || die "flasher upload token not found at $flashertokfile — run: task secrets:rotate-flasher-upload-token"
        mkdir -p "$stage/flasher"
        install -m 644 "$flashertokfile" "$stage/flasher/upload_token"
    fi
```

(e) Replace the restart-list lines (~205-208):

```bash
    local restart_services="caddy siteapp"
    service_disabled streamer   || restart_services+=" streamer"
    service_disabled monitoring || restart_services+=" grafana"
    if [[ "${LDS_STACK_ONLY:-}" != "1" ]]; then
        restart_services+=" chisel authelia"
    fi
```

(f) Healthcheck: inside the `for ((i=0; i<60; i++))` loop, replace each optional probe with a gated version using the `skip` sentinel (leave home/authelia/docs/download/static/public/server_info probes untouched):

```bash
            if service_disabled jupyter; then jupyter_status="skip"; else
                jupyter_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/jupyter/" || true)"
            fi
            if service_disabled monitoring; then grafana_status="skip"; else
                grafana_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/grafana/api/health" || true)"
            fi
            if service_disabled flasher; then flash_status="skip"; else
                flash_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/flash/" || true)"
            fi
            if service_disabled streamer; then streamer_status="skip"; else
                streamer_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/streamer/labs" || true)"
            fi
            if service_disabled studio; then studio_status="skip"; else
                studio_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/studio/" || true)"
            fi
```

and adjust the success condition's corresponding clauses to:

```bash
                && [[ "$jupyter_status" == "skip" || "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "skip" || "$grafana_status" == "200" ]] \
                && [[ "$flash_status" == "skip" || "$flash_status" == "302" ]] \
                && [[ "$streamer_status" =~ ^(skip|200|302|401|403)$ ]] \
                && [[ "$studio_status" =~ ^(skip|302|403)$ ]]
```

(keep the surrounding probe comments; the timeout `warn` lines need no change — they'll print `skip` verbatim, which is honest).

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_service_selection_render.bats && bats tests/integration/test_deploy_stack_only.bats`
Expected: all PASS (stack-only tests confirm the ungated path still works — their fixture has no `disabled_services`).

Run: `shellcheck -x --severity=warning scripts/deploy.sh`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy.sh tests/integration/test_service_selection_render.bats
git commit -m "feat: gate secrets, renders, restarts, and healthcheck probes on disabled services"
```

---

### Task 5: CI wiring (config.ci template, action input, smoke gating)

**Files:**
- Modify: `compose/config.ci.yaml.tmpl` (append `disabled_services` line)
- Modify: `.github/actions/deploy-stack/action.yml` (new input; env in "render CI config.yaml" and "post-deploy authenticated smoke" steps; gate the "verify flasher container image tag" step)
- Modify: `.github/workflows/release-please.yml:237-249` (pass the variable)
- Modify: `scripts/post_deploy_smoke.sh` (per-service gating)
- Test: `tests/integration/test_service_selection_render.bats` (append)

**Interfaces:**
- Consumes: `validate_config` (Task 1).
- Produces: GH repo variable contract `LDS_DISABLED_SERVICES` — comma-separated group names (e.g. `jupyter, monitoring`), empty = full stack. Env var of the same name read by `scripts/post_deploy_smoke.sh`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_service_selection_render.bats`:

```bash
@test "config.ci.yaml.tmpl: empty LDS_DISABLED_SERVICES renders [] and validates" {
    command -v envsubst >/dev/null || skip "envsubst not installed"
    VPS_HOST=1.2.3.4 VPS_SSH_USER=u \
    JUPYTER_PASSWORD_HASH="sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" \
    ADMIN_PASSWORD_HASH='$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa' \
    LDS_DISABLED_SERVICES= \
        envsubst < "$ROOT/compose/config.ci.yaml.tmpl" > "$TMPDIR/ci.yaml"
    grep -q 'disabled_services: \[\]' "$TMPDIR/ci.yaml"
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/ci.yaml"
    [ "$status" -eq 0 ]
}

@test "config.ci.yaml.tmpl: comma list renders a flow list that validates" {
    command -v envsubst >/dev/null || skip "envsubst not installed"
    VPS_HOST=1.2.3.4 VPS_SSH_USER=u \
    JUPYTER_PASSWORD_HASH="sha1:abcdef012345:0123456789abcdef0123456789abcdef01234567" \
    ADMIN_PASSWORD_HASH='$2a$14$DG5Aycl5h3ED0V1Qz50BfuZDxSle4cvw7sRFYCArNvB03eCpKSPxa' \
    LDS_DISABLED_SERVICES='jupyter, monitoring' \
        envsubst < "$ROOT/compose/config.ci.yaml.tmpl" > "$TMPDIR/ci.yaml"
    run yq e '.disabled_services | length' "$TMPDIR/ci.yaml"
    [[ "$output" == "2" ]]
    run bash -c "source $ROOT/scripts/lib/config.sh; validate_config $TMPDIR/ci.yaml"
    [ "$status" -eq 0 ]
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: both FAIL (`disabled_services` absent from the rendered file).

- [ ] **Step 3: Implement**

(a) Append to `compose/config.ci.yaml.tmpl`:

```yaml
# Optional-service selection for the CI-deployed VPS. Rendered from the
# LDS_DISABLED_SERVICES repo variable (comma-separated group names, e.g.
# "jupyter, monitoring"; empty = full stack). DUAL-MANAGED with the
# operator's laptop config.yaml, like the secret pairs above — if they
# drift, the next release re-enables (or removes) services on the VPS.
disabled_services: [${LDS_DISABLED_SERVICES}]
```

(b) `.github/actions/deploy-stack/action.yml` — add after the `flasher_upload_token` input:

```yaml
  disabled_services:
    description: "Comma-separated optional services to omit (e.g. 'jupyter, monitoring'). Must mirror the target VPS's laptop config.yaml. Empty = full stack."
    required: false
    default: ""
```

Add to the `render CI config.yaml` step's `env:` block:

```yaml
        LDS_DISABLED_SERVICES: ${{ inputs.disabled_services }}
```

Add the same line to the `post-deploy authenticated smoke` step's `env:` block.

Change the `verify flasher container image tag` step's `if:` to:

```yaml
      # No optional-service name is a substring of another, so contains() is safe.
      if: inputs.verify_version != '' && !contains(inputs.disabled_services, 'flasher')
```

(c) `.github/workflows/release-please.yml` — in the `deploy + verify` step's `with:` block, add:

```yaml
          disabled_services:      ${{ vars.LDS_DISABLED_SERVICES }}
```

(d) `scripts/post_deploy_smoke.sh` — after the `PROBE_TIMEOUT_S` line, add:

```bash
# Optional-service gating: LDS_DISABLED_SERVICES is the same comma-separated
# list the deploy used (group names). Probes for disabled services are
# skipped — their routes 404 by design.
service_disabled() {
    case ",$(printf '%s' "${LDS_DISABLED_SERVICES:-}" | tr -d ' ')," in
        *",$1,"*) return 0 ;;
        *)        return 1 ;;
    esac
}
```

In `main()`, replace the `grafana_oidc_handshake || failed=1` line and the jupyter/grafana/flasher probes with:

```bash
    if service_disabled monitoring; then
        log "  grafana: skipped (monitoring disabled)"
    else
        grafana_oidc_handshake || failed=1
    fi
```

```bash
    # 2. JupyterLab: status endpoint returns the standard Jupyter Server payload.
    if service_disabled jupyter; then
        log "  jupyter: skipped (disabled)"
    else
        probe "jupyter" \
            "https://$VPS_HOST/jupyter/api/status" \
            200 \
            'has("started")' || failed=1
    fi
```

```bash
    if ! service_disabled monitoring; then
        probe "grafana" \
            "https://$VPS_HOST/grafana/api/user" \
            200 \
            '.email != null and (.email | length) > 0' || failed=1
    fi
```

```bash
    if service_disabled flasher; then
        log "  flasher: skipped (disabled)"
    else
        probe "flasher" \
            "https://$VPS_HOST/flash/api/clients" \
            200 \
            'has("clients")' || failed=1
    fi
```

(keep each probe's original explanatory comment with it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: all PASS.

Run: `shellcheck -x --severity=warning scripts/post_deploy_smoke.sh && yq e '.' .github/actions/deploy-stack/action.yml >/dev/null && yq e '.' .github/workflows/release-please.yml >/dev/null`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add compose/config.ci.yaml.tmpl .github/actions/deploy-stack/action.yml .github/workflows/release-please.yml scripts/post_deploy_smoke.sh tests/integration/test_service_selection_render.bats
git commit -m "feat: LDS_DISABLED_SERVICES variable wires service selection into CI deploys"
```

---

### Task 6: Fake-VPS integration test + matrix cell

**Files:**
- Create: `tests/integration/test_service_selection.bats`
- Modify: `.github/workflows/pr-platform.yml` (new matrix cell after `auth`)

**Interfaces:**
- Consumes: everything from Tasks 1–4 through `scripts/deploy.sh`; helpers from `tests/integration/helpers.bash` (`compose_images_available`, `bootstrap_authelia_for_tests`, image loaders, `patch_caddyfile_tls_internal`, `wait_siteapp_ready`, `wait_authelia_ready`).
- Produces: the platform-tier proof that a trimmed stack deploys healthy end-to-end.

- [ ] **Step 1: Write the test file**

Create `tests/integration/test_service_selection.bats`:

```bash
#!/usr/bin/env bats
# Optional-service selection wiring: ONE fake-VPS bring-up with all five
# optional services disabled. Asserts the trimmed stack deploys healthy,
# disabled routes 404, and disabled containers do not exist. Thin wiring
# tier only — service behavior lives in services/<name>/tests/e2e/.
# Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md

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
    yq -i '.disabled_services = ["jupyter", "monitoring", "studio", "streamer", "flasher"]' "$TMPDIR/config.yaml"
    cp "$ROOT/tests/integration/fixtures/valid_pins.yaml" "$TMPDIR/pins.yaml"
    yq -i ".ssh_port = 2222" "$TMPDIR/pins.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_PINS_FILE="$TMPDIR/pins.yaml"
    bootstrap_authelia_for_tests
    export LDS_SSH_KEY="$ROOT/tests/integration/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_SKIP_HEALTHCHECK=1
    # Gated secrets point at NONEXISTENT paths on purpose: with monitoring
    # and flasher disabled, deploy.sh must not require them.
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/absent_grafana_pw"
    export LDS_FLASHER_UPLOAD_TOKEN_FILE="$TMPDIR/absent_flasher_tok"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'smoke-tok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    # Only the CORE custom images — flasher/streamer aren't in the trimmed stack.
    load_siteapp_test_image
    load_caddy_test_image
    load_authelia_test_image
    preload_fake_vps_images
    bash "$ROOT/scripts/deploy.sh"
    patch_caddyfile_tls_internal
    wait_siteapp_ready
    wait_authelia_ready
}

teardown_file() {
    docker rm -f lds-fake-vps >/dev/null 2>&1 || true
}

setup() {
    if [[ -f "$BATS_FILE_TMPDIR/skip" ]]; then
        skip "$(cat "$BATS_FILE_TMPDIR/skip")"
    fi
}

_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -k -s -o /dev/null -w \"%{http_code}\" --max-redirs 0 \"$1\"
        '
    "
}

_body_through_caddy() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -k -s --max-redirs 0 \"$1\"
        '
    "
}

@test "core routes respond on the trimmed stack" {
    code="$(_through_caddy 'https://127.0.0.1/')"
    [[ "$code" == "200" ]] || { echo "home got: $code"; false; }
    code="$(_through_caddy 'https://127.0.0.1/docs/')"
    [[ "$code" == "200" || "$code" == "308" ]] || { echo "docs got: $code"; false; }
    code="$(_through_caddy 'https://127.0.0.1/auth/api/health')"
    [[ "$code" == "200" ]] || { echo "authelia got: $code"; false; }
}

@test "disabled routes fall through to 404" {
    local p code
    for p in /jupyter/ /grafana/api/health /flash/ /streamer/labs /studio/; do
        code="$(_through_caddy "https://127.0.0.1$p")"
        [[ "$code" == "404" ]] || { echo "$p got: $code (want 404)"; false; }
    done
}

@test "/studio exact-path redirect is stripped too" {
    code="$(_through_caddy 'https://127.0.0.1/studio')"
    [[ "$code" == "404" ]] || { echo "got: $code"; false; }
}

@test "disabled containers do not exist; core containers do" {
    run docker exec lds-fake-vps bash -c 'cd /srv/lab-bridge && docker compose ps --services'
    [ "$status" -eq 0 ]
    local svc
    for svc in caddy siteapp authelia chisel; do
        grep -qx "$svc" <<< "$output" || { echo "core '$svc' missing: $output"; false; }
    done
    for svc in jupyter grafana loki prometheus node-exporter cadvisor studio streamer flasher; do
        ! grep -qx "$svc" <<< "$output" || { echo "disabled '$svc' present: $output"; false; }
    done
}

@test "navbar injection carries the disabled ids" {
    body="$(_body_through_caddy 'https://127.0.0.1/')"
    [[ "$body" == *'data-disabled="jupyter,grafana,studio,flasher"'* ]] \
        || { echo "tag not found; got: $(grep -o 'data-disabled=\"[^\"]*\"' <<< "$body" || echo NONE)"; false; }
}
```

- [ ] **Step 2: Run the suite locally**

Run: `bats tests/integration/test_service_selection.bats`
Expected: all PASS (or a clean `skip` if the host can't pull the compose images — in that case fix connectivity before proceeding; do NOT merge on a skip).

- [ ] **Step 3: Add the matrix cell**

In `.github/workflows/pr-platform.yml`, after the `auth` matrix entry, add:

```yaml
          - suite: service-selection
            files: tests/integration/test_service_selection.bats
```

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_service_selection.bats .github/workflows/pr-platform.yml
git commit -m "test: fake-VPS integration coverage for a fully trimmed stack"
```

---

### Task 7: Documentation

**Files:**
- Modify: `config.example.yaml` (new commented block)
- Modify: `README.md` (new "Optional services" subsection under "Operations reference")
- Modify: `CLAUDE.md` ("Config split" section, one bullet)
- Modify: `docs/adding-a-service.md` (new step 15)

**Interfaces:** none (docs only). Copy the exact texts below.

- [ ] **Step 1: config.example.yaml**

Append after the `chisel_clients` example block:

```yaml
# Optional-service selection. Services listed here are omitted from the
# deploy entirely: no container, no Caddy route (path → styled 404), no
# navbar entry, no healthcheck probe. Absent key or [] = full stack.
# Allowed names: jupyter, monitoring, studio, streamer, flasher
#   - monitoring = grafana + loki + prometheus + node-exporter + cadvisor
#     (disabling it also drops chisel-client log shipping to Loki)
# Core services (caddy, authelia, siteapp, chisel) cannot be disabled.
# Data dirs (grafana_data/, flasher_data/, …) are preserved on the VPS —
# re-enabling a service restores its state.
# NOTE: if this instance is also the CI deploy target, mirror this list in
# the LDS_DISABLED_SERVICES GitHub Actions variable (dual-managed, like
# secrets) or the next release will re-enable the services.
disabled_services: []
```

- [ ] **Step 2: README.md**

Add a subsection at the end of "Operations reference" (before "Users & authentication"):

```markdown
### Optional services

Low-budget instances can skip heavy containers via `disabled_services` in
`config.yaml` (gitignored):

​```yaml
disabled_services: [jupyter, monitoring]
​```

Allowed names: `jupyter`, `monitoring` (= grafana + loki + prometheus +
node-exporter + cadvisor, one toggle), `studio`, `streamer`, `flasher`.
Core services (caddy, authelia, siteapp, chisel) cannot be disabled.

A disabled service is fully absent: no container (`--remove-orphans` cleans
up on the next deploy), no Caddy route (its paths return the styled 404),
no navbar entry, no healthcheck probe, and its deploy-time secrets are not
required. Its `*_data/` directory on the VPS is untouched, so re-enabling
restores prior state. Caveat: disabling `monitoring` also drops chisel-client
log shipping (the `loki:3100` tunnel allow-list entry stays but has no
listener).

CI release deploys are dual-managed, like secrets: set the
`LDS_DISABLED_SERVICES` GitHub Actions **variable** (comma-separated, e.g.
`jupyter, monitoring`) to mirror the laptop `config.yaml` of the CI-deployed
VPS. If they drift, the next release re-enables (or removes) services.
```

(Remove the zero-width characters around the inner code fence when writing the actual file — they exist only to keep this plan's formatting intact.)

- [ ] **Step 3: CLAUDE.md**

In the "Config split" section, add a third bullet:

```markdown
- **Optional-service selection → `disabled_services` in `config.yaml`** (allowed names + monitoring-group expansion live in `scripts/lib/config.sh`). CI mirrors it via the `LDS_DISABLED_SERVICES` GH variable — dual-managed like secrets.
```

- [ ] **Step 4: docs/adding-a-service.md**

Add before "## What you should NOT do":

```markdown
## 15. Optional or mandatory?

Decide whether the new service may be disabled per-instance via
`disabled_services` (see the spec
`docs/superpowers/specs/2026-07-17-service-selection-design.md`). If optional:

1. Add its name to `_OPTIONAL_SERVICES` in `scripts/lib/config.sh` (and to
   a group expansion if it ships as part of a group).
2. Wrap its Caddyfile route blocks in `# --- BEGIN svc:<name> ---` /
   `# --- END svc:<name> ---` markers.
3. Map its navbar id in `render_caddyfile`'s `disabled_nav` case statement
   (or add a no-entry case like streamer's).
4. Gate its deploy-time secrets/renders/restart/healthcheck probe in
   `scripts/deploy.sh` with `service_disabled <name>`, and its smoke probe
   in `scripts/post_deploy_smoke.sh`.
5. Extend `tests/integration/test_service_selection_render.bats` (filtered
   compose/Caddyfile assertions) and the disabled sets in
   `tests/integration/test_service_selection.bats`.
```

- [ ] **Step 5: Verify and commit**

Run: `bats tests/integration/test_service_selection_render.bats`
Expected: still all PASS (docs changed nothing functional).

```bash
git add config.example.yaml README.md CLAUDE.md docs/adding-a-service.md
git commit -m "docs: operator + contributor docs for optional-service selection"
```

---

### Task 8: Real-world verification on preprod

**Files:** none in-repo (`config.yaml` is gitignored; it gets edited and restored).

**Interfaces:** consumes the finished feature via `task deploy` against preprod `khamit@111.88.145.138` (the laptop `config.yaml`'s current `vps.host`). Pre-authorized by the operator.

- [ ] **Step 1: Baseline full-stack deploy from the branch**

```bash
task deploy
```
Expected: `deployed: home 200, authelia 200, …` (all probes real, none `skip`).

- [ ] **Step 2: Deploy with jupyter + monitoring disabled**

```bash
yq -i '.disabled_services = ["jupyter", "monitoring"]' config.yaml
task deploy
```
Expected: deploy succeeds; the success log shows `jupyter skip` and `grafana skip`. This exercises the REAL healthcheck path that bats cannot (fake-VPS runs skip it).

- [ ] **Step 3: Verify absence + preserved core**

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://111.88.145.138/jupyter/            # expect 404
curl -sk -o /dev/null -w '%{http_code}\n' https://111.88.145.138/grafana/api/health  # expect 404
curl -sk -o /dev/null -w '%{http_code}\n' https://111.88.145.138/flash/              # expect 302 (flasher still enabled)
ssh khamit@111.88.145.138 'cd /srv/lab-bridge && docker compose ps --services | sort'
# expect: authelia caddy chisel flasher siteapp streamer studio — NO jupyter/grafana/loki/prometheus/node-exporter/cadvisor
curl -sk https://111.88.145.138/ | grep -o 'data-disabled="[^"]*"'                    # expect data-disabled="jupyter,grafana"
```

- [ ] **Step 4: Re-enable and restore**

```bash
yq -i 'del(.disabled_services)' config.yaml
task deploy
curl -sk -o /dev/null -w '%{http_code}\n' https://111.88.145.138/grafana/api/health  # expect 200
curl -sk -o /dev/null -w '%{http_code}\n' https://111.88.145.138/jupyter/            # expect 302
ssh khamit@111.88.145.138 'cd /srv/lab-bridge && docker compose ps --services | wc -l'  # expect 13
```
Confirm `git status` shows no tracked-file changes from this task and `yq e '.disabled_services' config.yaml` prints `null`.

---

### Task 9: PR, CI, merge

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin feat/service-selection
gh pr create \
  --title "feat: optional-service selection via gitignored disabled_services" \
  --body "$(cat <<'EOF'
Adds a `disabled_services` list to the gitignored `config.yaml` so low-budget
instances can skip heavy optional containers (jupyter, monitoring group,
studio, streamer, flasher). Core (caddy/authelia/siteapp/chisel) is not
disableable. Render-time filtering: compose services + depends_on + orphaned
secrets pruned via yq; marker-wrapped Caddy routes stripped (paths → styled
404); navbar entries hidden via a data-disabled attr; deploy.sh gates secret
staging, config renders, restart list, and healthcheck probes. CI deploys
mirror the selection via the LDS_DISABLED_SERVICES repo variable
(dual-managed like secrets; unset = full stack = current behavior).

Spec: docs/superpowers/specs/2026-07-17-service-selection-design.md
Real-world verified on preprod: trimmed deploy (jupyter+monitoring off),
404s + container absence + navbar hiding confirmed, then restored to full
stack.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 2: Watch CI; fix and re-push if red**

```bash
gh pr checks --watch
```
Required checks: `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-streamer / streamer`, `pr-platform / platform`. The service workflows fast-skip (no `services/**` changes). If a bats cell flakes on image pulls, re-run the job (`gh run rerun <id> --failed`).

- [ ] **Step 3: Squash-merge when green**

```bash
gh pr merge --squash --delete-branch
```
Post-merge notes: production behavior is unchanged until the `LDS_DISABLED_SERVICES` repo variable is set (deliberately NOT set as part of this work). No branch-protection changes needed (only a new matrix cell inside the existing `pr-platform` aggregator).

---

## Self-review checklist (run after writing, before execution)

- Spec coverage: schema/validation (T1), compose filter (T2), Caddy/navbar (T3), deploy gating (T4), CI + smoke (T5), fake-VPS test + matrix cell (T6), docs (T7), rollout (T8-9). Loki-caveat + data-preservation are doc'd in T7. "Deliberately unchanged" spec items require no tasks.
- The `restart_line` assertion in T4 greps `ssh.log` — the ssh spy receives the remote command as a single argument, so `grep -o 'docker compose restart.*'` extracts it.
- `data-disabled` order in T6 (`jupyter,grafana,studio,flasher`) follows the config-list order `[jupyter, monitoring, studio, streamer, flasher]` with monitoring→grafana and streamer dropped.

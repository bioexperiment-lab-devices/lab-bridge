# Experiment Studio Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the externally-built Experiment Studio image into the stack: compose service, Caddy `/studio` route, Authelia rule, deploy probe, navbar entry, ops task, and tests.

**Architecture:** Studio is the first *external app image* in the stack (precedent: jupyter): pinned in `compose/pins.yaml`, no source in this repo, platform wiring only. Public path `/studio/*` is prefix-stripped at Caddy and gated by Authelia forward_auth (researchers + admins). Data persists in a `./studio_data` bind mount on the VPS.

**Tech Stack:** bash (render/deploy scripts), Caddy, Authelia, docker compose templates, bats integration tests, vanilla-JS navbar.

**Spec:** `docs/superpowers/specs/2026-07-12-experiment-studio-integration.md`

## Global Constraints

- Pin `ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0` — never `0.2.0` (0.2.0 emits absolute URLs and breaks behind the stripped prefix). Availability of `0.3.0` on GHCR verified 2026-07-12 via registry API (HTTP 200).
- **No `pr-studio.yml`, no release-build step, no branch-protection change** (spec L6).
- Studio is NOT added to `restart_services` in `deploy.sh` (spec L7); one replica only (spec L8).
- PR title: `feat: add experiment-studio to the stack` (Conventional Commits; squash-merge).
- Do not bump root `VERSION` by hand; release-please owns it.
- shellcheck (`--severity=warning`) must stay clean on `scripts/*.sh` and `scripts/lib/*.sh`.
- Deviations from the spec (all justified, see tasks): (a) `load_config` enumerates exports — spec's "auto-export" doesn't exist, so `config.sh` gains the pin field + export; (b) Taskfile ops task delegates to `scripts/ops.sh` like every sibling, not the spec's inline SSH snippet; (c) deploy probe accepts `302|403`, not `302` only — stack-only CI deploys exclude `authelia/configuration.yml`, so until the next laptop `task deploy` Authelia default-denies `/studio` with 403 (same documented transient as the streamer probe); (d) the Caddy strip is wrapped in `route {}` — Caddy's directive order runs `uri` before `forward_auth`, which would strip the prefix before Authelia sees it and default-deny everyone (found in adversarial review); (e) `studio_data/` is added to deploy.sh's rsync `--delete` excludes — without it every deploy wipes studio's SQLite DB + run artifacts (the spec's L4 parenthetical contradicts its own "mirror flasher_data" instruction, and flasher_data is excluded).

---

### Task 1: Pin + config plumbing (pins, config.sh, render.sh, fixtures)

**Files:**
- Modify: `compose/pins.yaml` (add pin)
- Modify: `scripts/lib/config.sh` (required field + export)
- Modify: `scripts/lib/render.sh` (sed line)
- Modify: `tests/integration/fixtures/valid_pins.yaml` (fixture pin)
- Modify: `tests/integration/test_render.bats` (3 inline pins heredocs + 2 new tests)

**Interfaces:**
- Produces: `$STUDIO_IMAGE` exported by `load_config`; `__STUDIO_IMAGE__` substituted by `render_compose`.

- [ ] **Step 1: Add the pin to `compose/pins.yaml`** (after the `grafana_image:` line):

```yaml
# Experiment Studio — operator UI for lab_devices experiments. Built and
# released by the bioexperiment-lab-devices/lab-devices repo (NOT part of
# this repo's unified VERSION stream). Renovate-managed like the other
# external images. MUST be >= 0.3.0 (sub-path portability behind the
# stripped /studio route; 0.2.0 emits absolute URLs and breaks).
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0
```

- [ ] **Step 2: `scripts/lib/config.sh`** — append `.studio_image` to `_REQUIRED_PINS_FIELDS` (after `.prometheus_retention_days`), and in `load_config` add next to the other image exports:

```bash
    export STUDIO_IMAGE         ; STUDIO_IMAGE="$(_yq e '.studio_image' "$pins_path")"
```

- [ ] **Step 3: `scripts/lib/render.sh`** — in `render_compose`'s sed, after the `__GRAFANA_IMAGE__` line:

```bash
        -e "s|__STUDIO_IMAGE__|${STUDIO_IMAGE:?}|g" \
```

- [ ] **Step 4: `tests/integration/fixtures/valid_pins.yaml`** — add:

```yaml
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0
```

- [ ] **Step 5: `tests/integration/test_render.bats`** — add `studio_image: stu:1` to each of the three inline `PINS` heredocs (tests "SITEAPP_IMAGE is composed…", "FLASHER_IMAGE is composed…", "render_compose substitutes __AUTHELIA_IMAGE__") — without it `validate_config` now fails those tests.

- [ ] **Step 6: Run** `bats tests/integration/test_render.bats tests/integration/test_config.bats` — expect green (these files need yq + bats but no docker). If bats is unavailable locally, defer to CI and note it.

### Task 2: Compose + Caddyfile + Authelia templates

**Files:**
- Modify: `compose/docker-compose.yml.tmpl` (studio service + caddy depends_on)
- Modify: `compose/Caddyfile.tmpl` (redir + handle block)
- Modify: `services/authelia/config/configuration.yml.tmpl` (access rule)
- Modify: `tests/integration/test_render.bats` (2 new render tests)

**Interfaces:**
- Consumes: `__STUDIO_IMAGE__` substitution from Task 1.
- Produces: `studio` compose service on labnet:8000; public `/studio/*` route.

- [ ] **Step 1: `compose/docker-compose.yml.tmpl`** — after the `streamer:` block:

```yaml
  studio:
    image: __STUDIO_IMAGE__
    restart: unless-stopped
    environment:
      STUDIO_DATA_DIR: /data
      LAB_DEVICES_DISCOVERY_URL: http://siteapp:8000/api/clients/
    volumes:
      - ./studio_data:/data
    networks: [labnet]
```

and change caddy's depends_on to `[jupyter, siteapp, flasher, streamer, studio, grafana, authelia]`.

- [ ] **Step 2: `compose/Caddyfile.tmpl`** — insert after the streamer handle block, before the Grafana section:

```caddyfile
    # ─── Experiment Studio (researchers + admins) ────────────────────────
    # External image (lab-devices repo). SPA + API served at container root;
    # the app emits relative URLs (>= 0.3.0), so strip the public prefix.
    # The exact-path redirect is load-bearing: the SPA resolves relative
    # URLs against the document URL, so it must be loaded at /studio/
    # (trailing slash), never /studio.
    redir /studio /studio/ 308
    handle /studio/* {
        import authelia_required
        import inject_navbar
        uri strip_prefix /studio
        reverse_proxy studio:8000 {
            header_up -Accept-Encoding
        }
    }
```

- [ ] **Step 3: `services/authelia/config/configuration.yml.tmpl`** — after the `^/streamer($|/.*)` one_factor rule:

```yaml
    - domain: __VPS_HOST__
      resources:
        - '^/studio($|/.*)'
      policy: one_factor
      subject:
        - 'group:researchers'
        - 'group:admins'
```

(The authelia/siteapp e2e fixtures do NOT track the template rule list — verified: the authelia fixture already lacks the streamer rule and no test compares — so they stay untouched, per the spec's conditional.)

- [ ] **Step 4: `tests/integration/test_render.bats`** — add two tests at the end:

```bats
@test "render_compose: emits studio service with data volume and discovery env" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_compose $ROOT/compose/docker-compose.yml.tmpl $TMPDIR/docker-compose.yml
        cat $TMPDIR/docker-compose.yml
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0"* ]]
    [[ "$output" == *"./studio_data:/data"* ]]
    grep -q "LAB_DEVICES_DISCOVERY_URL: http://siteapp:8000/api/clients/" <<< "$output"
    # No published ports — studio is only reachable through Caddy.
    run yq e '.services.studio | has("ports")' "$TMPDIR/docker-compose.yml"
    [ "$status" -eq 0 ]
    [[ "$output" == "false" ]]
}

@test "render_caddyfile: routes /studio/* to studio:8000 with prefix strip behind forward_auth" {
    run bash -c "
        source $ROOT/scripts/lib/common.sh
        source $ROOT/scripts/lib/config.sh
        source $ROOT/scripts/lib/render.sh
        load_config $ROOT/tests/integration/fixtures/valid_config.yaml
        render_caddyfile $ROOT/compose/Caddyfile.tmpl $TMPDIR/Caddyfile
        cat $TMPDIR/Caddyfile
    "
    [ "$status" -eq 0 ]
    [[ "$output" == *"redir /studio /studio/ 308"* ]]
    [[ "$output" == *"handle /studio/*"* ]]
    studio_block="$(grep -A 8 'handle /studio/\*' <<< "$output")"
    [[ "$studio_block" == *"import authelia_required"* ]]
    [[ "$studio_block" == *"uri strip_prefix /studio"* ]]
    [[ "$studio_block" == *"reverse_proxy studio:8000"* ]]
}
```

- [ ] **Step 5: Run** `bats tests/integration/test_render.bats` — expect green.

### Task 3: Navbar entry (before JupyterLab)

**Files:**
- Modify: `compose/shell/navbar.js` (SERVICES, PATH_RULES, ICONS, sign-out copy)

- [ ] **Step 1:** In `SERVICES`, insert before the jupyter entry (bookmark mode — like jupyter/grafana, studio is a full-page external app whose own layout the persistent rail would fight):

```js
    { id: 'studio',  label: 'Experiment Studio', href: '/studio/',        mode: 'bookmark',   external: true  },
```

- [ ] **Step 2:** In `PATH_RULES`, add:

```js
    { prefix: '/studio', mode: 'bookmark' },
```

- [ ] **Step 3:** In `ICONS`, add (Lucide: flask-conical — fits "experiments"):

```js
    // Lucide: flask-conical
    studio:  ICON(`<path d="M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2"/>
                    <path d="M6.453 15h11.094"/>
                    <path d="M8.5 2h7"/>`),
```

- [ ] **Step 4:** Update the sign-out modal lede to include studio: `You'll be signed out of lab-bridge. Open sessions to Experiment Studio, JupyterLab, Grafana, and Flasher will end.`

- [ ] **Step 5:** If `compose/shell/README.md` enumerates the service list, add studio there.

### Task 4: Deploy health probe

**Files:**
- Modify: `scripts/deploy.sh` (probe + condition + log/warn lines)

- [ ] **Step 1:** Add `studio_status` to the `local` status-var declaration list.

- [ ] **Step 2:** After the streamer probe, add:

```bash
            # /studio/ — Authelia forward_auth → 302 to /login for anonymous.
            # 403 is the same transient as /streamer/labs above: stack-only CI
            # deploys exclude authelia/configuration.yml from rsync, so until
            # the next laptop `task deploy` lands the /studio rule Authelia
            # falls back to default_policy:deny → 403. A 502/504 would mean
            # the studio container failed to start.
            studio_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/studio/" || true)"
```

- [ ] **Step 3:** Add `&& [[ "$studio_status" =~ ^(302|403)$ ]]` to the success `if`, `studio $studio_status` to the success `log`, and `studio:${studio_status}[want 302/403]` to the timeout `warn`.

- [ ] **Step 4:** Run `shellcheck -x --severity=warning scripts/deploy.sh` (if installed) — clean.

### Task 5: Routes-smoke test + image helpers

**Files:**
- Modify: `tests/integration/test_routes_smoke.bats` (one test)
- Modify: `tests/integration/helpers.bash` (both image lists)

- [ ] **Step 1:** `helpers.bash` — add `ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0` to the `imgs` arrays in BOTH `preload_fake_vps_images` and `compose_images_available` (the skip pattern enumerates images; the spec requires the studio pin added when it does).

- [ ] **Step 2:** `test_routes_smoke.bats` — add after the `/flash/` gating test:

```bats
@test "/studio/ is gated by forward_auth (302 to /login)" {
    code="$(_through_caddy 'https://127.0.0.1/studio/')"
    [[ "$code" == "302" ]] || { echo "got: $code"; false; }
}
```

### Task 6: Ops task

**Files:**
- Modify: `scripts/ops.sh` (cmd + case)
- Modify: `Taskfile.yml` (task)

- [ ] **Step 1:** `scripts/ops.sh` — next to `cmd_logs_streamer`:

```bash
cmd_logs_studio()   { load_config "$CONFIG"; remote_compose "logs --tail=200 studio"; }
```

and in `main`'s case: `logs:studio)   cmd_logs_studio ;;`

- [ ] **Step 2:** `Taskfile.yml` — after the streamer ops block (repo idiom — delegate to ops.sh, NOT the spec's inline SSH snippet):

```yaml
  # --- Experiment Studio (external image; pinned in compose/pins.yaml) ---
  "ops:logs:studio":
    desc: Tail recent studio container logs
    cmd: bash scripts/ops.sh logs:studio
```

- [ ] **Step 3:** `shellcheck -x --severity=warning scripts/ops.sh` — clean.

### Task 7: CLAUDE.md touch

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1:** Add an invariant bullet under "Architecture philosophy": external app images (studio) are pinned in `pins.yaml`, get platform wiring only (compose service + Caddy route + Authelia rule + navbar), no `services/<name>/`, no `pr-<name>.yml`, no branch-protection change; behavior tests live in their home repo.

- [ ] **Step 2:** Fix the stale "5-cell matrix" line (the workflow now has 8 cells) — reword so it doesn't hardcode a count.

### Task 8: Verify, PR, CI, merge, deploy

- [ ] **Step 1:** Full local render check: render compose + caddyfile + authelia config from real pins, `grep -E '__[A-Z][A-Z0-9_]*__'` finds nothing, `docker compose config` parses (if docker CLI available).
- [ ] **Step 2:** Independent review pass (fresh-eyes subagent) of the full diff against the spec before pushing.
- [ ] **Step 3:** Branch `feat/experiment-studio`, commit spec + plan + implementation, push, open PR `feat: add experiment-studio to the stack`.
- [ ] **Step 4:** Watch CI (`pr-platform`, `pr-authelia`, `pr-title` + fast-skips); fix failures until green.
- [ ] **Step 5:** Re-verify `0.3.0` on GHCR (merge gate), squash-merge.
- [ ] **Step 6:** Wait for release-please PR; it runs the full suite; merge it; watch release-build + deploy-stack (expect `studio 403` transient in the health log).
- [ ] **Step 7:** Laptop `task deploy` to land the Authelia `/studio` rule (full-mode rsync + authelia restart).
- [ ] **Step 8:** Post-deploy checks: `https://<host>/studio` → 308 → `/studio/` → 302 → `/login` (anonymous); health log shows `studio 302`; `task ops:ps` shows studio running. Hand back to the lab-devices session for the W6 live smoke.

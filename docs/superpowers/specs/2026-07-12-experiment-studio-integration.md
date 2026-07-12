# Experiment Studio — lab-bridge integration

- **Date:** 2026-07-12
- **Status:** Approved for planning
- **Origin:** `lab-devices` repo, `docs/superpowers/specs/2026-07-11-experiment-studio-webapp-design.md`
  (§5 packaging, §12 increment W6). This spec is the lab-bridge side of W6: one new
  externally-built service in the stack. It was authored by the lab-devices session with the
  platform conventions of this repo (CLAUDE.md, `docs/adding-a-service.md`) already applied;
  where it deviates from `adding-a-service.md`, the deviation is deliberate and explained.
- **Scope:** platform-only changes (compose templates, Caddy route, Authelia rule, deploy
  probe, routes-smoke assertion, Taskfile). **No service source lands in this repo.**

## 1. What is being integrated

Experiment Studio is a single-user web app (FastAPI + built React SPA in one container) for
building and running `lab_devices` experiment workflows against the lab agents behind chisel.
It is developed and released in the `bioexperiment-lab-devices/lab-devices` repo and published
on that repo's releases as:

```
ghcr.io/bioexperiment-lab-devices/experiment-studio:<version>   (+ :latest)
```

The image is **public** (anonymous pull verified 2026-07-12), `linux/amd64`, and is *not* part
of this repo's unified `VERSION` stream — it has its own release cadence, like the other
external pins (jupyter, chisel, grafana…). Renovate's existing `compose/pins.yaml` regex
manager will pick up the new pin automatically; no `renovate.json` change is needed.

### Image contract (what the container expects/provides)

| Aspect | Value |
|---|---|
| Listen port | `8000` (uvicorn, fixed in image CMD) |
| API | `/api/*` (REST + `WS /api/runs/{id}/events`) |
| SPA | served at `/` (catch-all to `index.html`); **all asset/API/WS URLs are relative**, so it works behind a prefix-stripping proxy |
| Health | `GET /api/health` → `{status, library, studio}` (no separate `/healthz`) |
| Data | `STUDIO_DATA_DIR` (default `/data`): SQLite db + run artifact dirs. Must be a persistent volume. |
| Lab discovery | `LAB_DEVICES_DISCOVERY_URL` (default `http://siteapp:8000/api/clients/` — already correct in-stack; set explicitly anyway for greppability) |
| Auth | none in-app — the Caddy/Authelia edge is the only gate (same trust model as the internal roster) |
| User | runs as root; root-owned bind-mount data dir is fine (matches chisel/loki/etc.) |

### ⚠️ Minimum version: 0.3.0

Pin **`0.3.0` or newer, never `0.2.0`**. Sub-path portability (relative asset/API/WS URLs)
lands in `0.3.0` (lab-devices W6, being released the same day this spec was written). Under
`0.2.0` the SPA emits absolute `/assets/*` and `/api/*` URLs, which — behind the
prefix-stripped `/studio` route below — escape the prefix and collide with siteapp's
namespace. All wiring work in this repo can be developed and reviewed before `0.3.0` exists,
but the release/deploy must not happen until `ghcr.io/...:0.3.0` is published. Check with:

```bash
docker manifest inspect ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0
```

## 2. Settled decisions

| # | Decision | Choice |
|---|---|---|
| L1 | Public path | `/studio/*` on the main host, **prefix-stripped** at Caddy (`uri strip_prefix /studio`). The container keeps serving at `/`, so the same image works in local dev (`docker run -p 8000:8000`) and in the stack. Contrast with flasher, which natively mounts under `/flash` — studio's design (single-user tool, also runnable standalone) makes stripping the better fit. |
| L2 | Auth gate | `import authelia_required` + Authelia rule `^/studio($|/.*)` → `one_factor`, groups `researchers` + `admins` (same audience as jupyter/streamer/grafana). No bypass sub-routes: the run WebSocket authenticates with the same session cookie on the upgrade request, which forward_auth verifies fine. |
| L3 | Pin shape | `studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0` in `compose/pins.yaml` (full ref incl. tag — the *external image* pattern like `chisel_image`, NOT the `*_image_repo` + `VERSION` pattern, which is only for images this repo builds). `load_config` auto-exports it as `$STUDIO_IMAGE`. |
| L4 | Data dir | `./studio_data:/data` bind mount in the deploy root (mirrors `flasher_data`/`streamer_data`). Created on first `docker compose up`. Survives deploys (rsync `--delete` excludes are not needed — it lives only on the VPS, never in the staged tree; mirror how `flasher_data` is handled). |
| L5 | Navbar | `import inject_navbar` inside the studio handle (platform chrome consistency, mirrors `/streamer/*`). |
| L6 | CI | **No `pr-studio.yml`, no release-build steps, no branch-protection change.** There is no source here to test or build; `pr-platform` (bats) covers the wiring. This is the first *external app image* in the stack — precedent: jupyter (external image + Caddy route + Authelia rule). |
| L7 | Restart policy | `studio` is NOT added to `restart_services` in `deploy.sh` — it consumes no bind-mounted config file; `docker compose up -d` recreates it when the pin changes. |
| L8 | Concurrency caveat | Studio enforces one active run per instance (409 on a second start). One replica only; do not scale it. |

## 3. Changes, file by file

### 3.1 `compose/pins.yaml`

Add (alphabetical placement among the external pins is fine):

```yaml
# Experiment Studio — operator UI for lab_devices experiments. Built and
# released by the bioexperiment-lab-devices/lab-devices repo (NOT part of
# this repo's unified VERSION stream). Renovate-managed like the other
# external images. MUST be >= 0.3.0 (sub-path portability behind the
# stripped /studio route; 0.2.0 emits absolute URLs and breaks).
studio_image: ghcr.io/bioexperiment-lab-devices/experiment-studio:0.3.0
```

### 3.2 `scripts/lib/render.sh`

One sed line in `render_compose` (no helper function — `$STUDIO_IMAGE` comes straight from
pins via `load_config`, same as `$CHISEL_IMAGE`):

```bash
        -e "s|__STUDIO_IMAGE__|${STUDIO_IMAGE:?}|g" \
```

### 3.3 `compose/docker-compose.yml.tmpl`

New service block (place after `streamer`):

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

Also add `studio` to Caddy's `depends_on` list.

### 3.4 `compose/Caddyfile.tmpl`

Insert after the streamer block, before the Grafana block:

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

Notes for the implementer:

- `reverse_proxy` passes WebSocket upgrades through automatically; the run-events WS at
  `wss://<host>/studio/api/runs/{id}/events` needs no extra directive.
- The global CSP (`connect-src 'self'`) already admits same-origin `wss:` in every modern
  browser; the studio SPA needs no CSP override (no eval, no external origins — verify in
  the browser console during the deploy check; if a violation does appear, override CSP
  inside the handle like the jupyter block does rather than loosening the global one).
- `header_up -Accept-Encoding` matches every other route (replace-response/navbar needs
  uncompressed HTML).

### 3.5 `services/authelia/config/configuration.yml.tmpl`

Add an access-control rule (place next to the streamer rule):

```yaml
    - domain: __VPS_HOST__
      resources:
        - '^/studio($|/.*)'
      policy: one_factor
      subject:
        - 'group:researchers'
        - 'group:admins'
```

Mirror the same rule into the e2e fixtures that pin this file's shape if they assert on the
rule list (`services/authelia/tests/e2e/fixtures/configuration.yml`,
`services/siteapp/tests/e2e/fixtures/authelia_config.yml`) — check whether those fixtures
enumerate rules or are free-form; only touch them if a test actually compares.

### 3.6 `scripts/deploy.sh`

In the post-deploy health loop, add a probe (mirror `flash_status` — forward_auth gives
anonymous curl a 302 to `/login`):

```bash
            studio_status="$(curl -sk -o /dev/null -w '%{http_code}' --max-redirs 0 "https://$VPS_HOST/studio/" || true)"
```

- Declare `studio_status` alongside the other `local` status vars.
- Success condition: `[[ "$studio_status" == "302" ]]` (add to the `if`), and add
  `studio $studio_status` to both the success `log` line and the timeout `warn` line.

### 3.7 `tests/integration/test_routes_smoke.bats`

One assertion (this is the cross-service wiring tier — exactly one test, no behavior tests):

```bash
@test "/studio/ is gated by forward_auth (302 to /login)" {
    code="$(_through_caddy 'https://127.0.0.1/studio/')"
    [[ "$code" == "302" ]] || { echo "got: $code"; false; }
}
```

The fake-VPS bring-up will `docker compose pull` the studio image from ghcr (public). The
file's existing `compose_images_available` skip pattern must cover it — confirm the pattern
probes all compose images generically; if it enumerates images, add the studio pin to the
list.

### 3.8 `Taskfile.yml`

Add an ops log task mirroring the others:

```yaml
  "ops:logs:studio":
    desc: Tail studio logs
    cmds:
      - "{{.SSH_CMD}} 'cd {{.REMOTE_ROOT}} && docker compose logs -f --tail=100 studio'"
```

(Substitute the exact variable/ssh idiom used by `ops:logs:streamer` — copy that block.)

### 3.9 `CLAUDE.md` / docs touch

- `CLAUDE.md`: no invariant changes (studio adds no per-service workflow). If any section
  enumerates compose services or public routes, add `studio` there. Consider one line under
  "Architecture philosophy": external app images (studio) are pinned in `pins.yaml` and get
  platform wiring only — behavior tests live in their home repo.
- `docs/adding-a-service.md`: out of scope (that doc is for in-repo services; do not extend
  it in this increment).

### 3.10 Implementation notes (recorded at execution, 2026-07-12)

Deviations from the snippets above, discovered during implementation (details in
`docs/superpowers/plans/2026-07-12-experiment-studio-integration.md`):

- **§3.4 — the strip is wrapped in `route {}`.** Caddy sorts a handle's directives
  by its global directive order, which runs `uri` *before* `forward_auth`; as
  written above, Authelia would receive the stripped path (`/`), match no rule,
  and default-deny everyone with 403. `route` preserves written order so
  forward_auth authenticates against the un-stripped `/studio` path.
- **§L4 — `studio_data/` IS added to deploy.sh's rsync excludes.** The
  parenthetical above is self-contradictory: `rsync --delete` removes receiver
  dirs absent from the staged tree unless excluded, and `flasher_data` (the
  named mirror) is excluded for exactly that reason. Without the exclude every
  deploy would wipe studio's SQLite DB + run artifacts.
- **§3.1/L3 — no auto-export.** This repo's `load_config` enumerates exports, so
  `scripts/lib/config.sh` gains `.studio_image` in `_REQUIRED_PINS_FIELDS` plus
  an explicit `STUDIO_IMAGE` export.
- **§3.6 — the probe accepts `302|403`, not `302` only.** Stack-only CI deploys
  exclude `authelia/configuration.yml` from rsync, so the first CI deploy sees
  Authelia's default-deny 403 until the next laptop `task deploy` lands the
  rule — the same documented transient as the streamer probe.
- **§3.8 — Taskfile task delegates to `bash scripts/ops.sh logs:studio`** (the
  actual idiom used by every `ops:logs:*` sibling).

## 4. Testing & acceptance

1. **Unit/none** — no service code here.
2. **Platform bats:** `bats tests/integration/test_routes_smoke.bats` green locally
   (or skip-clean if images unavailable), and `pr-platform` green on the PR.
3. **Render check:** `docker compose config` on the rendered template parses; `__STUDIO_IMAGE__`
   is substituted (a rendered-template grep for `__` catching leftovers is the usual trick).
4. **Post-deploy (after release-please tag → CI deploy):**
   - `https://<host>/studio` → 308 → `/studio/` → 302 → `/login` (anonymous).
   - Logged in as a researcher: `/studio/` renders the app shell; the Devices tab lists the
     chisel roster labs (proves `LAB_DEVICES_DISCOVERY_URL` + labnet reachability).
   - `deploy.sh` health loop passes with `studio 302`.
5. **Live preprod smoke** (W6 gate, run by the **lab-devices** session, not this one): a
   scripted experiment against `windows_arm64_test_client` through the deployed studio.
   Coordinate: this repo's work is DONE when the deploy check (step 4) passes; hand back to
   the lab-devices session for the smoke.

## 5. Rollout sequence

1. Land this integration on a feature branch; PR titled `feat: add experiment-studio to the stack`
   (Conventional Commits — surfaces in the changelog; any type would bump the unified version).
2. **Gate on image availability:** before merging, verify `0.3.0` exists on ghcr (§1). If the
   lab-devices release hasn't landed yet, keep the PR open — merging pins a tag that
   `docker compose pull` can't resolve and the CI deploy's `--ignore-pull-failures` would
   leave the stack without the studio container (deploy health probe then fails on 502).
3. Squash-merge → release-please PR → merge → tag build → CI stack-only deploy to preprod.
4. Run §4.4 checks; then notify the operator/lab-devices session for §4.5.

## 6. Out of scope

- Studio behavior/e2e tests (live in `lab-devices/webapp/`, run in that repo's CI).
- Auth model changes, multi-user, per-user data isolation (studio is single-user by design).
- Backups/retention for `studio_data` (operator concern, same stance as `flasher_data`).
- `restart_services` wiring, chisel roster mounts, secrets — studio needs none of them.

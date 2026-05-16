# siteapp simplification — remove admin UI, docs-as-code, stale sweep

**Date:** 2026-05-16
**Status:** Draft (brainstormed 2026-05-16)
**Author:** khamitovdr
**Pairs with:**
- `2026-05-15-per-service-isolation-design.md` — the per-service split this builds on (the "split siteapp internally" follow-up that doc deferred).
- `2026-05-01-public-docs-and-agent-downloads-design.md` — original siteapp design, now partially superseded (admin UI surface).
- `2026-05-11-server-info-design.md` / `2026-05-11-public-client-status-design.md` — public APIs that stay.

## Motivation

`siteapp` accumulated two responsibilities that no longer carry their weight:

1. **An admin upload UI for markdown docs.** The docs are authoritative content; treating them as runtime-uploaded data means there's no source of truth in git, every VPS drifts independently, and the upload UI carries a non-trivial security surface (path traversal, MIME filtering, CSRF) for a workflow that ends with "operator edits a `.md` file."
2. **An admin upload UI for the Windows agent binary.** Already vestigial — the SerialHop CI pipeline uploads via `POST /api/agent/upload` (bearer-token auth). The hand-upload form just duplicates that path with an HTML wrapper.

Removing both lets siteapp shrink to what it does well: serve public docs, serve the agent binary, accept CI uploads of that binary, and expose the chisel-client discovery APIs that Jupyter notebooks and the agent depend on.

The replacement for the docs-upload UI is **docs-as-code**: markdown lives in git, ships via CI on push to main, no manual upload step. This matches how `clients.json` already flows (laptop-rendered, rsync'd to VPS) and avoids the version-bump churn that "bake docs into the siteapp image" would impose on prose edits.

## Goals

- Delete the `/admin/*` surface (docs manager + agent admin + rotate-token) from siteapp.
- Move public docs into the repo at `public_docs/`, deployed via a new docs-only CI workflow on push to main.
- Keep `/api/agent/upload` (bearer-auth, CI consumer).
- Keep `/api/clients/`, `/api/public/clients/{username}`, `/api/public/health`, `/api/public/server-info` (Jupyter + SerialHop consumers).
- Sweep stale references created by the above (README, deploy probes, test files, comments).

## Non-goals

- Splitting siteapp into multiple services. (Considered in brainstorming; siteapp's protocol responsibilities are on the SerialHop side, not the server, so there's no second service hiding inside.)
- Renaming `__ADMIN_BCRYPT_HASH__`, `siteapp.admin_password_hash`, or the `secrets:set-admin-password` task. The credential is still in play — flasher's `/flash/*` basic_auth uses it. Renaming for accuracy touches render, config validators, ops scripts, integration tests, and laptop muscle memory for cosmetic gain.
- Renaming `SITE_DATA` / restructuring the `./site_data:/data` mount. The agent binary still lives there (writable, CI-uploaded); renaming yields zero functional gain.
- Deduplicating `services/siteapp/app/clients.py` ↔ `services/flasher/app/clients.py`. They already diverged in return shape (siteapp adds `host`, flasher adds TCP probing). Deduping is a refactor on its own merits, not a stale-cleanup.
- Pruning historical entries from `CHANGELOG.md` (release-please-owned), `docs/superpowers/plans/*`, or `docs/superpowers/specs/*`. These are the project's memory.
- Authoring a markdown lint workflow for `public_docs/`. Out of scope; can be added later as a `pr-public-docs.yml`.

## Section 1 — Scope summary

### Removed entirely

| Surface | Files / config |
|---|---|
| Admin UI routes | `services/siteapp/app/admin.py` — all `/admin/*` handlers (dashboard, docs manager, docs upload/delete/rename/new-folder, agent admin, agent upload via UI, rotate-token) |
| Admin templates | `services/siteapp/app/templates/admin/` (whole subtree) |
| Caddy admin block | `compose/Caddyfile.tmpl` `/admin/*` `handle` (lines 32-40 today) |
| CSRF infrastructure | `URLSafeSerializer` usage, `csrf_secret` field, `SITEAPP_CSRF_SECRET` env, `itsdangerous` dep |
| Path-safety helpers used only by admin | `sanitize_filename` in `app/paths.py` and its tests |
| Admin tests | `services/siteapp/tests/test_routes_admin.py`, `services/siteapp/tests/e2e/test_admin_upload.py` |
| Default-docs seed | `app/config.py:73-81` seeding loop; `app/default_docs/` directory |
| Stale artifact | `services/siteapp/agent_upload_token.example` |

### Kept

| Surface | Why |
|---|---|
| `/docs/*` (public docs serving) | Core feature |
| `/download/agent`, `/download/agent/windows/agent.exe` | SerialHop distribution |
| `/api/agent/upload` | SerialHop CI uses it — bearer auth at app layer |
| `/api/clients/` | Jupyter notebooks consume this |
| `/api/public/clients/{username}`, `/api/public/health`, `/api/public/server-info` | SerialHop agent contract |
| `agent_upload_token` secret | Still required for `/api/agent/upload` |
| `./site_data:/data` writable mount | CI uploads the agent binary here |
| `__ADMIN_BCRYPT_HASH__` render var, `siteapp.admin_password_hash` config key, `secrets:set-admin-password` task | Flasher's `/flash/*` basic_auth uses the same credential |
| `lang` cookie + ru/en translations | Real feature, untouched |
| `app/paths.py::safe_join` | Used by `docs.py` and `translations.py`; only `sanitize_filename` becomes orphaned |

## Section 2 — Docs-as-code plumbing

### 2.1 Repo layout

- New top-level `public_docs/` directory (peer of `docs/`).
- Move `services/siteapp/app/default_docs/**` → `public_docs/**`, preserving the `.en.md`/`.ru.md` filename pairs and the icon/asset subdirectories.
- Delete `services/siteapp/app/default_docs/` after the move.

### 2.2 Container config (`services/siteapp/app/config.py`)

- New env var `SITEAPP_DOCS_DIR` (container path `/srv/docs`, read-only mount).
- `Settings.docs_root` reads from `SITEAPP_DOCS_DIR` instead of derived from `SITE_DATA`.
- Delete the default-docs seeding loop (current `config.py:73-81`). Source of truth is now the mount.
- Delete the `csrf_secret` field, the `SITEAPP_CSRF_SECRET` env read, and the `csrf_secret=` arg in the `Settings(...)` constructor.
- `SITE_DATA` keeps its meaning (writable mount for the agent binary at `/data/agent/`).

### 2.3 Compose change (`compose/docker-compose.yml.tmpl`)

Add to the `siteapp` service block:

```yaml
environment:
  SITEAPP_DOCS_DIR: /srv/docs        # new
  # existing env vars unchanged
volumes:
  - ./siteapp/docs:/srv/docs:ro      # new, read-only
  # existing ./site_data:/data unchanged
```

No new render variable needed — both paths are literals.

### 2.4 Deploy plumbing (`scripts/deploy.sh`, `scripts/lib/render.sh`)

- The staged tree (`$stage/siteapp/`) gains a `docs/` directory copied from `public_docs/` at the repo root.
- The existing rsync step ships `$stage/siteapp/docs/` → `~/lab-bridge/siteapp/docs/` on the VPS without code changes — same pattern that already moves `clients.json` and `agent_upload_token` under `$stage/siteapp/`.
- No service restart needed; siteapp reads docs on each request (`find_doc` + `read_text`).
- `LDS_STACK_ONLY=1` (CI release-please deploys) ships docs as part of the rsync — docs are tracked in git, so unlike `clients.json` they don't need to be excluded.

### 2.5 New docs-only CI workflow (`.github/workflows/deploy-public-docs.yml`)

- **Trigger:** `push` to `main` with `paths: ['public_docs/**']`.
- **Steps:** checkout, SSH key setup, rsync `public_docs/` → `~/lab-bridge/siteapp/docs/` on the VPS.
- **No image build, no version bump, no `docker compose` restart.**
- **Auth:** reuses the same SSH/vault GH secrets the release-please deploy job uses.
- **Concurrency:** group by branch so two rapid pushes serialize (rsync is idempotent but cheaper not to overlap).

### 2.6 Release-please scoping (`release-please-config.json`)

- Add `"public_docs"` to the **platform** component's `exclude-paths` so docs commits don't bump platform version.
- Docs are outside `services/siteapp/` already, so siteapp version is unaffected automatically.

### 2.7 Existing siteapp CI

- `pr-siteapp.yml`'s path filter (`services/siteapp/**`) already does the right thing — docs-only PRs match no service paths and fast-skip the heavy steps. No workflow edits.

### 2.8 VPS migration

- First deploy after this change creates `~/lab-bridge/siteapp/docs/` via rsync, and mounts it read-only.
- The old writable directory under `~/lab-bridge/site_data/docs/` becomes orphaned. One-time manual cleanup: `ssh <vps> rm -rf ~/lab-bridge/site_data/docs/`. This is documented in the implementation plan; not automated to keep the deploy idempotent.

## Section 3 — Admin removal details

### 3.1 Files deleted

- `services/siteapp/app/admin.py`
- `services/siteapp/app/templates/admin/` (whole subtree)
- `services/siteapp/tests/test_routes_admin.py`
- `services/siteapp/tests/e2e/test_admin_upload.py`
- `services/siteapp/agent_upload_token.example`

### 3.2 Code edits

- `services/siteapp/app/main.py` — drop `make_admin_router` import and `include_router` call.
- `services/siteapp/app/config.py` — drop `csrf_secret` field, env-var read, constructor arg, and the default-docs seed loop (the latter already covered in 2.2).
- `services/siteapp/pyproject.toml` — drop `itsdangerous>=2.2,<3` from `dependencies`. `uv lock` regenerates `uv.lock`.
- `services/siteapp/app/paths.py` — delete `sanitize_filename`. Keep `safe_join` (still consumed by `docs.py` and `translations.py`).
- `services/siteapp/tests/test_paths.py` — remove `sanitize_filename` tests; keep `safe_join` tests.

### 3.3 Caddy (`compose/Caddyfile.tmpl`)

- Delete the `/admin/*` `handle` block (current lines 32-40).
- Leave `__ADMIN_BCRYPT_HASH__` rendering in place — `/flash/*` still uses it.

### 3.4 Deploy script (`scripts/deploy.sh`)

- Drop `admin_status` variable, its curl probe, its `== 401` condition, the inline `# /admin/ MUST be 401` comment, and the `admin $admin_status` substring in the log/warn lines.
- Other probes (`docs`, `download`, `flash`, `static`, `public`, `server-info`) stay.

### 3.5 Secrets prompt (`scripts/secrets.sh:69`)

- Update prompt string: "Admin panel password (used at /admin/*)" → "Operator password (used at /flash/*)". Task name and config key stay.

### 3.6 Integration tests

- `tests/integration/test_routes_smoke.bats` — delete the `/admin/ is gated by basic_auth (401)` test case.
- `tests/integration/test_render.bats` — replace the `basic_auth` near `/admin` assertion with the same assertion against `/flash` (basic_auth render coverage shifts to its surviving consumer).

### 3.7 E2E test rewrite

- `services/siteapp/tests/e2e/test_safety.py` today mixes (a) path-traversal-via-admin-upload (gone) with (b) HTML-escape-on-rendered-markdown (stays).
- Trim (a) entirely. Keep (b), retargeting it to the static `public_docs/` corpus via the e2e fixture — the test fixture mounts a fixture docs tree at `SITEAPP_DOCS_DIR`, includes a doc with a script-tag payload, and asserts the rendered HTML escapes it.

### 3.8 READMEs

- `services/siteapp/README.md` — rewrite to: "Public docs (`/docs/*`), agent download page (`/download/*`), agent CI-upload API (`/api/agent/upload`), and chisel-client status APIs (`/api/public/*`)." No admin upload UI mention.
- Repo root `README.md` — multiple admin mentions (lines ~5, 33, 42, 54, 69, 108 in current text). Rewrite to reflect: docs auto-deployed from `public_docs/` on push to main; agent binary uploaded by SerialHop CI; admin UI removed; `/flash/*` still operator-gated.

### 3.9 config.example.yaml

- Line 18 comment "bcrypt hash for the admin panel — set via `task secrets:set-admin-password`" → "bcrypt hash for the operator-gated `/flash/*` UI — set via `task secrets:set-admin-password`." Key name unchanged.

### 3.10 Taskfile.yml

- `secrets:set-admin-password` description: "/admin/* basic-auth password" → "/flash/* basic-auth password (operator gate)." Task name and command unchanged.

## Section 4 — Out-of-scope items (explicitly preserved)

These were considered and deliberately kept:

- **`CHANGELOG.md`** — release-please owned. Historical admin-feature entries describe what shipped at the time and are accurate. Rewriting history is bad form.
- **`docs/superpowers/plans/*.md` and `docs/superpowers/specs/*.md`** — implementation plans and design docs for completed work. The project's memory; CLAUDE.md treats them as load-bearing context for future work. Pruning is its own decision, not a stale-cleanup.
- **`__ADMIN_BCRYPT_HASH__` / `siteapp.admin_password_hash` / `secrets:set-admin-password`** — credential still in use by `/flash/*`. Renaming touches render.sh, config.sh validator, deploy.sh, secrets.sh, `config.ci.yaml.tmpl`, integration tests, and the operator's GH secret values for cosmetic gain.
- **`SITE_DATA` env var and `./site_data:/data` mount** — still hosts the writable agent binary. Renaming yields zero functional gain.
- **`services/siteapp/app/clients.py` ↔ `services/flasher/app/clients.py`** duplication. Already diverged in shape; deduping is a refactor on its own merits.

## Section 5 — Commit order

Lands as one squash-merge PR; internal commits ordered so each one is independently reviewable and leaves the tree green:

1. **`feat: add public_docs/`** — move `services/siteapp/app/default_docs/**` → `public_docs/**` verbatim. No code changes; just file relocation.
2. **`feat(siteapp): read docs from SITEAPP_DOCS_DIR`** — add the new env var to `Settings`, switch `docs_root` to read from it; update compose template, deploy.sh staging, and the e2e harness in lockstep. Delete the default-docs seed loop. Service still works end-to-end.
3. **`refactor(siteapp): remove admin UI`** — delete `admin.py`, admin templates, admin tests, `csrf_secret`, `itsdangerous` dep, `sanitize_filename`; drop `make_admin_router` from `main.py`; rewrite `test_safety.py` to target the static fixture corpus.
4. **`refactor: drop /admin/* from Caddy + deploy probe`** — Caddyfile.tmpl block delete, deploy.sh admin probe removal, secrets.sh prompt copy.
5. **`docs: rewrite siteapp/repo READMEs + config comments`** — README files, config.example.yaml comment, Taskfile description.
6. **`test: drop admin from integration tests`** — `test_routes_smoke.bats`, `test_render.bats` edits.
7. **`ci: deploy-public-docs workflow + release-please exclude`** — new `.github/workflows/deploy-public-docs.yml`; add `public_docs` to platform component's `exclude-paths`.

Commits 1-2 together ship the new docs path before any admin code is removed, so a partial rollback at commit 2 still has working docs.

## Section 6 — Risks and mitigations

| Risk | Mitigation |
|---|---|
| First deploy ships an empty `public_docs/` (forgotten move) and the VPS serves a 404 landing page. | Implementation plan's first commit is the file move; subsequent commits assume the directory is populated. CI on the PR will boot siteapp e2e against the moved corpus. |
| Docs-only workflow rsyncs without service health check; a broken markdown file (unrenderable) wouldn't fail the deploy. | Markdown is rendered on each request, not at deploy time. A broken file 500s only the page that serves it; other docs continue to render. Optional follow-up: lint markdown in PR CI. |
| Operators with stale muscle memory hit `/admin/*` and get a 404 instead of a 401. | Deliberate — the surface is gone. README and the migration commit message will call this out. |
| `release-please-config.json` mis-edit causes `public_docs/` commits to bump platform version. | Spec verification: a docs-only commit on a feature branch triggers release-please dry-run; verify no PR is opened. |
| The existing writable `site_data/docs/` on the VPS still serves stale content after cutover. | Once `SITEAPP_DOCS_DIR=/srv/docs` is set in compose, siteapp ignores `site_data/docs/` entirely — no path through the app reads from `/data/docs/` anymore. Cleanup is purely cosmetic disk hygiene. Documented one-shot `rm -rf` in the plan. |

## Section 7 — Open questions resolved during brainstorming

For posterity (so future-me doesn't re-ask):

- **Q: Should docs be baked into the siteapp image at build time?** No. Every prose edit would burn a siteapp release-please bump + image build + push. The rsync-at-deploy path mirrors how `clients.json` already flows and avoids that churn.
- **Q: Should docs deploys be tied to release-please?** No. Docs change at a different cadence than the service; a separate `public_docs/**`-gated workflow ships prose edits in seconds without touching siteapp's version.
- **Q: Should docs live inside `services/siteapp/`?** No. Top-level `public_docs/` keeps `pr-siteapp.yml`'s path filter clean, makes the deploy-public-docs workflow trigger sit at the right level, and reflects that docs are content the service serves, not part of the service.
- **Q: Should we name the new dir just `docs`?** No — collides with the existing top-level `docs/` (specs, plans, internal docs). `public_docs/` makes the audience split explicit.
- **Q: Should we split siteapp into two services?** No. The "device discovery API" inside siteapp is small enough (one router file, ~115 lines) that splitting it out adds CI / release / compose overhead with no architectural payoff. The future SerialHop-protocol-v2 service is a separate concern; it'll be a new service, not a split of this one.

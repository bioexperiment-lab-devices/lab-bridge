# Public docs & agent downloads — design

Status: approved (brainstorm complete; implementation plan to follow)
Date: 2026-05-01
Scope: a new public surface on the existing VPS stack — markdown
documentation rendered from uploaded `.md` files (with optional Russian
translations) and a download page for the Windows agent binary that CI
publishes via a static token. One new container, no database.

## Problem

Today every route on `https://<vps-host>/` sits behind JupyterLab's cookie
auth (Grafana under `/grafana/*` has its own login). There is no public
surface for users who only need to read documentation or download the
Windows agent — they currently can't, because the front door is gated.

We want:

- A professional-looking public docs site rendered from operator-uploaded
  markdown, with folder hierarchy and an EN/RU toggle on pages that have a
  Russian translation.
- A public download page for the Windows agent binary. CI publishes new
  builds via a static token; humans never need to SSH to update it.
- A small admin panel (one human operator) for uploading and managing
  documentation files.
- All of the above without disturbing JupyterLab's cookie auth or
  Grafana's login.

## Goals

- New public routes on the existing domain: `/docs/*`, `/download/*`. No
  subdomain, no extra TLS cert.
- Drag-and-drop upload of `.md` files (plus inline images) under
  `/admin/*`, gated by Caddy basic_auth.
- CI-driven agent uploads via `POST /api/agent/upload` with a bearer token.
- Folder-on-disk hierarchy reflected automatically in the public sidebar.
- EN/RU toggle that appears only when a Russian translation exists for the
  current page; English is always the source of truth.
- Fits the existing `task deploy` flow, the `compose/` template pattern,
  and the bats-driven test setup. No new persistence layer.

## Non-goals

- Full-text search on docs (template hooks left for a later `lunr` index).
- Multi-platform agent builds. Windows only. Disk layout leaves room for
  macOS/Linux later without a refactor.
- Multiple admin users, RBAC, or in-browser markdown editing. One human
  admin, files authored in the operator's editor of choice.
- Versioned doc history, comments, analytics, feedback widgets.
- Versioned agent history. Each CI upload overwrites the previous binary;
  users always run the latest.
- Rate limiting (Caddy's `rate_limit` is a one-liner if abuse appears).

## Architecture

```
                          VPS (lab-bridge)
 ┌──────────────────────────────────────────────────────────┐
 │  Caddy (public on 80/443) ───┐                           │
 │     ├─ /docs*       → siteapp:8000   (public)            │
 │     ├─ /download*   → siteapp:8000   (public)            │
 │     ├─ /admin*      → siteapp:8000   (basic_auth here)   │
 │     ├─ /api/agent/upload → siteapp:8000 (bearer in app)  │
 │     ├─ /grafana/*   → grafana:3000   (unchanged)         │
 │     └─ /            → jupyter:8888   (unchanged)         │
 │                                                          │
 │  siteapp:8000 (FastAPI + Uvicorn, no published port)     │
 │     │                                                    │
 │     └─► /data (volume) = site_data/                      │
 │            ├── docs/    (operator uploads)               │
 │            └── agent/   (CI uploads + meta.json)         │
 └──────────────────────────────────────────────────────────┘

 CI (GitHub Actions) ──► POST /api/agent/upload (bearer token)
 Operator browser   ──► /admin/* (Caddy basic_auth)
 Public users       ──► /docs/*, /download/*
```

`siteapp` is one new container on the existing `labnet` network. No
published ports — only Caddy reaches it. JupyterLab and Grafana auth flows
are untouched because Caddy's `basic_auth` is scoped to the `/admin/*`
handler only.

## Caddy routing

Inside the existing `https://__VPS_HOST__` site block, add four `handle`
directives alongside the existing `handle /grafana/*` and the catchall
`reverse_proxy jupyter:8888`. Caddy's `handle` blocks are mutually
exclusive: each request matches the most-specific block, regardless of
source order, so adding the new ones doesn't change how `/grafana/*` or
`/` are routed.

```caddyfile
# Public docs.
handle_path /docs* {
    reverse_proxy siteapp:8000
}

# Public agent download page + binary.
handle_path /download* {
    reverse_proxy siteapp:8000
}

# Admin panel — basic_auth scoped here, NOT anywhere else.
handle /admin* {
    basic_auth { admin __ADMIN_BCRYPT_HASH__ }
    reverse_proxy siteapp:8000
}

# CI upload endpoint — bearer-token auth in the app, not Caddy.
handle /api/agent/upload {
    reverse_proxy siteapp:8000
}

# Existing routes (unchanged).
handle /grafana/* { reverse_proxy grafana:3000 }
reverse_proxy jupyter:8888
```

Notes:

- `handle_path` strips the `/docs` or `/download` prefix before forwarding;
  `handle` preserves the path (siteapp sees `/admin/...` as-is).
- The mobile-WebSocket caveat that drove JupyterLab's cookie-auth choice
  doesn't apply: the admin panel is plain HTTP file uploads, no kernels.

## Compose service

Added to `compose/docker-compose.yml.tmpl`:

```yaml
siteapp:
  image: __SITEAPP_IMAGE__       # built from compose/siteapp/, pinned by tag+digest
  restart: unless-stopped
  environment:
    SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
  volumes:
    - ./site_data:/data
  secrets:
    - agent_upload_token
  networks: [labnet]

secrets:
  agent_upload_token:
    file: ./siteapp/agent_upload_token
```

(`grafana_admin_password` is already declared under `secrets:`; this adds
a sibling entry.)

## Disk layout

On the VPS, under `${remote_root}/site_data/`:

```
site_data/
├── docs/
│   ├── index.md                     # landing page at /docs/
│   ├── index.ru.md                  # optional Russian translation
│   ├── getting-started/
│   │   ├── index.md                 # section landing at /docs/getting-started/
│   │   ├── install.md
│   │   ├── install.ru.md
│   │   └── img/
│   │       └── screenshot.png
│   └── reference/
│       └── api.md
└── agent/
    ├── windows/
    │   └── agent.exe                # always the latest; overwritten on CI upload
    ├── page.md                      # download-page copy (English)
    ├── page.ru.md                   # download-page copy (optional Russian)
    └── meta.json                    # { version, sha256, uploaded_at, size }
```

Conventions:

- A directory becomes a section in the sidebar. Its label comes from
  `index.md`'s H1, falling back to the directory name.
- Translation pairing: `foo.md` (English, required) + `foo.ru.md`
  (optional). A `foo.ru.md` without a matching `foo.md` is ignored.
- Images live next to the markdown that references them; relative links
  in markdown work as-is.
- A markdown file with no H1 falls back to its filename (sans extension)
  for both the page title and the sidebar entry.

## Configuration

`config.example.yaml` gains a `siteapp` block:

```yaml
siteapp:
  image: ghcr.io/<owner>/lab-bridge-siteapp:0.1.0@sha256:...
  # Admin panel password — set with `task secrets:set-admin-password`.
  # Stored as a bcrypt hash for Caddy's basic_auth directive.
  admin_password_hash: "<run task secrets:set-admin-password>"
  # CI agent upload token — generated with `task secrets:rotate-agent-upload-token`.
  # 32-char URL-safe random string; lives only in compose/siteapp/agent_upload_token.
```

The bcrypt hash is template-substituted into the rendered Caddyfile (same
`__VAR__` pattern as the rest). The bearer token never appears in the
Caddyfile or the image — it is mounted as a Docker secret on `siteapp`.

## Docs rendering

Request flow for `GET /docs/getting-started/install` (after Caddy strips
`/docs`):

1. Resolve to a file on disk:
   - `getting-started/install.md` for English (default), or
     `getting-started/install.ru.md` if Russian is selected and that
     file exists.
   - A bare directory URL (`.../getting-started/`) resolves to the
     directory's `index.md`.
   - A bare directory URL without a trailing slash (`.../getting-started`)
     issues a 308 redirect to the trailing-slash form, so relative links
     inside `index.md` resolve correctly in the browser.
   - Missing English file → 404 (the canonical "this page exists" check
     is always against the English file).
2. Render markdown with `markdown-it-py` plus plugins for tables, fenced
   code, footnotes, heading anchors, and task lists. Raw HTML is disabled
   (`html=False`) so a malicious `.md` cannot inject scripts.
3. Highlight code blocks server-side with Pygments.
4. Wrap in a Jinja2 layout template; return HTML.

In-memory LRU cache keyed by `(path, lang, mtime)`. Mtime changes on
upload, so cache invalidation is free.

The sidebar nav is built once at startup and rebuilt after every
successful upload by walking `docs/`. Order: directories first, then
files, alphabetical. (Manual ordering via a per-directory `.order` file
is a cheap follow-up if needed.)

### Layout

Single Jinja2 template, mobile-responsive, Tailwind via the official CDN:

- Top bar: project name on the left; EN/RU pill on the right (rendered
  only when the current page has a translation).
- Left sidebar (hamburger on mobile): auto-generated nav tree, current
  page highlighted.
- Main column: max-width ~720px, generous line-height, system font stack,
  subtle borders on tables/code blocks. Code blocks have a copy button
  (small inline JS).
- Right rail at ≥1280px: in-page TOC built from H2/H3 headings.
- Footer: small, "lab-bridge" + a link back to `/`.
- Dark mode follows OS preference via `prefers-color-scheme`. Aesthetic
  target: clean, Stripe/Linear-ish, restrained palette, no gradients.

### EN/RU behavior

- English is the default. The selected language is determined in this
  order: `?lang=` query parameter (if present and one of `en`, `ru`),
  else the `lang` cookie, else English.
- Clicking the EN/RU pill sets `?lang=…` on a redirect to the same path
  *and* writes the `lang` cookie, so the choice persists across
  subsequent navigations without query parameters.
- If the resolved language has no translation file for the current
  page, the renderer silently falls back to English. No broken links;
  the cookie is not cleared.
- The pill is rendered greyed-out and unclickable on pages where the
  inactive language has no translation.
- Sidebar entries display in the currently-selected language, falling
  back to English title-by-title for entries that have no translation.

## Admin panel

All routes under `/admin/*`, behind Caddy basic_auth (one operator). No
links from the public site.

- `GET /admin/` — dashboard with two cards:
  - **Documentation** — file count, last upload time, link to manager.
  - **Agent** — current version, upload time, sha256, link to manager.
- `GET /admin/docs` — file manager for `site_data/docs/`:
  - Breadcrumb + folder dropdown to pick the target directory.
  - Drag-and-drop upload zone (also clickable). Accepts `.md`, `.png`,
    `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`. Multi-file. 10 MB per file
    cap (configurable later).
  - Flat list of files in the current directory: filename, size, mtime,
    Delete and Rename buttons. No in-browser editing.
  - "New folder" button (text input → empty directory; convention is to
    drop a stub `index.md` so it appears in the public sidebar).
  - "View public page" link next to every `.md` row.
- `GET /admin/agent` — agent manager:
  - Current version, upload time, sha256.
  - Manual upload form (file + version field) — same effect as the CI
    endpoint, useful for testing builds locally.
  - "Rotate upload token" button (confirms, generates a new 32-char
    token, displays it once — same flow as the `task` command from CLI).

### Validation

- Filenames are sanitized: lowercased, `[a-z0-9._-]` only, no leading
  dots, no `..`, max length 100. Disallowed names → 400 with a clear
  inline error.
- Target paths are resolved with `Path.resolve()` and must live under
  `site_data/docs/` or `site_data/agent/`. Any escape attempt → 400.
- All write actions are CSRF-protected (synchronizer token in the form,
  validated on POST).
- Uploads stream to disk; no large-file buffering in RAM.
- After a successful upload/delete/rename, the in-memory nav cache is
  invalidated so the public site reflects the change immediately.
- Errors render inline; success shows a toast (e.g., "3 files uploaded
  to /docs/getting-started").

## Agent download page

`GET /download/agent` — a single focused landing page (no docs sidebar):

- Heading "Lab Bridge Agent" + a one-line subhead.
- Primary download button: `Download for Windows · v1.2.3 · 8.4 MB`,
  linking to `/download/agent/windows/agent.exe`.
- A body content area whose copy is whatever the operator writes in
  `site_data/agent/page.md` (and `page.ru.md` if present) — the
  expected sections are "What is this?", "System requirements", and
  "How to install", but the file is free-form markdown rendered into
  the content slot below the download button. No imposed structure.
- Version metadata block (version, release date, sha256 — copyable).
  Sourced from `meta.json`.
- If `agent.exe` is not yet uploaded, the page renders a friendly
  "Not yet available — check back soon" state with the download button
  disabled. No 404, no broken link. The body markdown still renders if
  it exists.
- Same EN/RU toggle as the docs site, with identical fallback rules
  (Russian only when `page.ru.md` exists).

`GET /download/agent/windows/agent.exe`:

- Streamed via FastAPI's `FileResponse` (no full-file RAM buffer).
- `Content-Disposition: attachment; filename="lab-bridge-agent-1.2.3.exe"`
  (filename includes the version even though the URL is generic).
- `Content-Type: application/octet-stream`.
- `Cache-Control: no-store` so users always get the current build.

## CI upload contract

`POST /api/agent/upload`:

```http
POST /api/agent/upload HTTP/1.1
Host: <vps-host>
Authorization: Bearer <agent_upload_token>
Content-Type: multipart/form-data; boundary=...

  binary:  <agent.exe bytes>
  version: 1.2.3
```

Server behavior:

1. `Authorization: Bearer <token>` is compared to the mounted secret
   using a constant-time compare. Missing / malformed / wrong → 401.
2. `version` must match `^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$`. Else
   400.
3. Stream the binary to a temp file under `site_data/agent/.tmp/` (same
   filesystem as the destination so the rename is atomic). Reject
   uploads larger than 100 MB (configurable).
4. Compute sha256 while streaming.
5. `os.replace(tmp, site_data/agent/windows/agent.exe)` — atomic;
   concurrent downloaders never see a half-written binary.
6. Write `meta.json` (`{version, sha256, uploaded_at, size}`) via the
   same temp-file + rename pattern.
7. Respond `200 {"version": "1.2.3", "sha256": "...", "size": 8421376}`.

GitHub Actions example (for the README):

```yaml
- name: Upload agent build
  run: |
    curl -fsSL -X POST https://${{ secrets.VPS_HOST }}/api/agent/upload \
      -H "Authorization: Bearer ${{ secrets.AGENT_UPLOAD_TOKEN }}" \
      -F "version=${{ github.ref_name }}" \
      -F "binary=@dist/agent.exe"
```

## Auth model

Three independent auth surfaces. None of them touch the others.

| Surface | Method | Audience | Where the secret lives |
|---|---|---|---|
| `/admin/*` | Caddy `basic_auth` (bcrypt) | One operator | bcrypt hash inlined in the rendered Caddyfile |
| `POST /api/agent/upload` | `Authorization: Bearer` (constant-time compare in siteapp) | CI | 32-char token mounted as a Docker secret on `siteapp` |
| `/`, `/grafana/*` | unchanged (Jupyter cookie, Grafana login) | Lab team | unchanged |

Threat-model notes:

- TLS-only — Caddy auto-redirects HTTP→HTTPS.
- The bearer token authorizes only `POST /api/agent/upload` and can be
  rotated without affecting humans.
- Path traversal, raw HTML in markdown, and disallowed file extensions
  are all rejected at the siteapp layer.
- No rate limiting in v1; endpoints are obscure and TLS-protected.

## Operator workflows

New `task` commands:

- `task secrets:set-admin-password` — prompts for a password, runs
  `caddy hash-password` (or `htpasswd -B` as a fallback) to produce a
  bcrypt hash, writes it into `config.yaml`'s
  `siteapp.admin_password_hash`. Same UX as the existing
  `secrets:set-jupyter-password`.
- `task secrets:rotate-agent-upload-token` — runs
  `python -c 'import secrets; print(secrets.token_urlsafe(32))'`,
  writes the value to `compose/siteapp/agent_upload_token` (gitignored,
  mode 0600), prints it once with a "save this now" warning. Re-running
  rotates.
- `task ops:logs:siteapp` — tails siteapp's container stderr.
- `task ops:site-disk` — shows `site_data/` size, broken into `docs/`
  and `agent/`.
- `task siteapp:build-and-push` — rebuilds the siteapp image and pushes
  to GHCR. Rare; only when siteapp itself changes.

Bootstrapping order on a fresh VPS (operator's first run):

```bash
task secrets:set-admin-password              # required for /admin/*
task secrets:rotate-agent-upload-token       # required for CI uploads
task deploy
```

If either secret is missing at deploy time, `scripts/deploy.sh` fails
before touching the VPS — same `die "... — run: task secrets:set-..."`
pattern as the existing Grafana password check (see
`scripts/deploy.sh` line 41).

## Deploy

`scripts/deploy.sh` is extended to:

- Render `siteapp.admin_password_hash` and `siteapp.image` into the
  Caddyfile and `docker-compose.yml` (existing `__VAR__` substitution
  pattern).
- `rsync` `compose/siteapp/agent_upload_token` to the VPS as a Docker
  secret file (mode 0600, owned by root) before `docker compose up`.
- Healthcheck the new endpoints, in addition to the existing ones:
  - `GET /docs/` returns 200.
  - `GET /download/agent` returns 200.
  - `GET /admin/` returns 401 *without* credentials. A 200 here is a
    deploy failure (proves basic_auth wired correctly).
  - `GET /grafana/` and `/` continue to be probed as today.

A failed healthcheck rolls back exactly like the existing Loki/Grafana
pattern (commit `56ccde9`).

## Image build

- `compose/siteapp/` contains: `Dockerfile`, `pyproject.toml`,
  `uv.lock`, `app/` (Python source), `templates/` (Jinja2),
  `static/` (small CSS/JS for the copy-code button).
- Pinned base (`python:3.13-slim`) and pinned dependency versions in
  `pyproject.toml`/`uv.lock` — matches the project's "pin everything"
  ethos.
- Built once and pushed to GHCR; `siteapp.image` in `config.yaml`
  references it by tag + digest, like the other services.

## Testing

bats suites under `tests/`, matching the existing structure:

- `tests/siteapp_routing.bats` — against the existing fake-VPS
  container: deploy a stack with siteapp, assert each route returns the
  expected status, including the basic_auth gate on `/admin/`.
- `tests/siteapp_uploads.bats` — POST a `.md` file to `/admin/docs`
  (with basic_auth), then GET `/docs/<that-path>` and grep for the
  rendered content. POST an agent binary to `/api/agent/upload` (with
  the bearer token), then GET `/download/agent/windows/agent.exe` and
  verify the bytes round-trip and the sha256 matches `meta.json`.
- `tests/siteapp_auth.bats` — negative cases: wrong basic_auth → 401;
  missing/wrong bearer token → 401; admin paths not exposed on the
  public surface.
- `tests/siteapp_safety.bats` — path-traversal upload
  (`../../etc/passwd`) → 400; HTML-in-markdown → escaped, not rendered;
  oversized upload → 413.
- Unit tests inside the siteapp image (`pytest`) for the markdown
  renderer, nav-tree builder, and translation-pairing logic. Run as
  part of `task siteapp:build-and-push`.

## Open follow-ups (deferred)

These are intentionally out of scope for v1 but the design leaves room
for them:

- Full-text search on docs (template hooks for a static `lunr` index
  are already planned).
- Manual sidebar ordering via a per-directory `.order` file.
- macOS/Linux agent builds (the `agent/<os>/` layout already
  accommodates them).
- Caddy `rate_limit` on `/api/agent/upload` if abuse appears.
- A second admin user / per-area RBAC, if the team grows past one
  operator.

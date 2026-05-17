# Shared platform navbar via Caddy HTML injection

**Status:** draft
**Date:** 2026-05-17
**Owners:** platform

## Goal

A single sidebar navigation rail that appears uniformly across every HTML page
in the lab-bridge stack, providing a common entry point to all services on one
domain. One source of truth for the navbar; future changes ship by editing one
file, not by touching individual services.

## Services in the nav (in order)

1. **Home** — `/`
2. **Docs** — `/docs/`
3. **Download Agent** — `/download/`
4. **JupyterLab** — `/jupyter/`
5. **Grafana** — `/grafana/`
6. **Flasher** — `/flash/`

## Architecture overview

```
browser ─► Caddy (custom image) ─► upstream service
                │
                ├─ replace-response: inject <script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" defer></script>
                │                    before </head> on every text/html response
                │
                ├─ CSP rewrite on /jupyter* and /grafana*: ensure script-src and
                │   style-src include 'self' so the injected asset is allowed
                │
                ├─ /_shared/* ─► file_server (compose/shell/, volume-mounted)
                │
                └─ /, /docs/*, /download/*, /jupyter/*, /grafana/*, /flash/*, /api/*
                      ─► respective backends
```

**Key invariants:**

- One JS bundle at `compose/shell/navbar.js` is the single source of truth for
  navigation membership, ordering, and rendering. Owned services never see another
  navbar-related PR after the one-time CSS hook lands.
- Two render modes, selected by `location.pathname` at boot:
  - **Persistent** for owned services (siteapp, flasher and any future owned
    service). Collapsed 52 px rail by default with content reflow via
    `padding-left: var(--nav-width)`; Expanded 240 px panel as overlay on top.
  - **Bookmark** for full-viewport third-party apps (JupyterLab, Grafana). A
    bookmark tab sits at the left edge of the viewport — anchored ~80 px from
    the bottom, ~16 px wide, protruding ~4 px from the edge. Hover or tap
    expands a 240 px overlay; mouse-leave (300 ms delay) or `Esc` returns to
    the tab. `--nav-width` stays `0`.
- The Caddy image is custom-built once via `xcaddy` to add the
  `caddyserver/replace-response` plugin. Built and pushed via the standard
  per-service CI pipeline (`services/caddy/`, `pr-caddy.yml`,
  GHCR + Sigstore attestation), pinned in `compose/pins.yaml`.
- JupyterLab moves off the catchall `/` to an explicit `/jupyter/*` prefix
  (`ServerApp.base_url=/jupyter`). The bare root `/` serves a new minimal siteapp
  Home stub.

## Components

### `services/caddy/`

New per-service directory following the established pattern.

```
services/caddy/
├── Dockerfile           # two-stage: caddy:2-builder → xcaddy build → caddy:2 runtime
├── build.sh             # local: docker buildx build --tag lab-bridge/caddy:dev .
├── README.md
└── tests/
    └── e2e/
        ├── conftest.py             # spin up caddy with fixture Caddyfile + stub upstream
        ├── test_injection.py       # <script> appears in HTML, absent from JSON/CSS
        ├── test_csp_rewrite.py     # script-src/style-src include 'self' on /jupyter*, /grafana*
        ├── test_passthrough.py     # non-HTML unchanged; gzip/brotli handled
        └── test_mutation_guard.py  # MutationObserver re-attaches if body content destroyed
```

Dockerfile shape:

```dockerfile
ARG CADDY_VERSION=2.8.4
ARG REPLACE_RESPONSE_VERSION=<specific-tag-or-commit-pinned-at-implementation-time>
FROM caddy:${CADDY_VERSION}-builder AS builder
RUN xcaddy build \
    --with github.com/caddyserver/replace-response@${REPLACE_RESPONSE_VERSION}

FROM caddy:${CADDY_VERSION}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

Both pins live in `Dockerfile` ARGs so Renovate can update them. The plugin
version is pinned at implementation time (most-recent tagged release at PR
authorship); the e2e suite catches regressions on subsequent bumps.

### `.github/workflows/pr-caddy.yml`

- Triggers on `pull_request` (no workflow-level `paths`).
- Internal `dorny/paths-filter@v3` gate on `services/caddy/**` and
  `compose/Caddyfile.tmpl`.
- Builds image, runs `tests/e2e/`, pushes to
  `ghcr.io/bioexperiment-lab-devices/lab-bridge-caddy:${{ github.sha }}` on
  PRs, Sigstore-attests on release-please tag pushes (mirroring the existing
  siteapp / flasher build flow).
- Final aggregator job named `caddy` — required-check name is `pr-caddy / caddy`.
- Branch protection's required-check list updated in lockstep (use the legacy
  `verify` stub trick as a transitional no-op if needed).

### `compose/shell/`

New platform-only directory containing the navbar assets.

```
compose/shell/
├── navbar.js              # ~10 KB, vanilla ES2020, defines <lds-navbar>
├── navbar-inner.css       # styles loaded inside the shadow root via <link>
└── README.md              # how to edit / version / cache-bust
```

These files are platform-only assets, not source code in the per-service sense;
they live next to `Caddyfile.tmpl` consistent with the "`compose/` is
platform-only" rule.

### `compose/Caddyfile.tmpl`

Full updated file (annotated against the current one):

```caddyfile
{
    email __ACME_EMAIL__
    default_sni __VPS_HOST__
}

https://__VPS_HOST__ {
    tls {
        issuer acme { profile shortlived }
    }

    # ─── 1. Platform shell assets ─────────────────────────────────────
    handle /_shared/* {
        root * /srv/shell
        file_server { precompressed gzip }
        header Cache-Control "public, max-age=60, must-revalidate"
        # Short max-age; cache-busting is via ?v=__PLATFORM_VERSION__
        # query string so versioned URLs are immutable for the duration
        # of a release.
    }

    # ─── 2. siteapp routes (unchanged paths) ──────────────────────────
    handle /_static/*       { reverse_proxy siteapp:8000 }
    handle /docs*           { reverse_proxy siteapp:8000 }
    handle /download*       { reverse_proxy siteapp:8000 }
    handle /api/agent/upload { reverse_proxy siteapp:8000 }
    handle /api/public*     { reverse_proxy siteapp:8000 }

    # ─── 3. Flasher (unchanged) ───────────────────────────────────────
    handle /flash/api/v1/* { reverse_proxy flasher:8000 }
    handle /flash* {
        basic_auth { admin __ADMIN_BCRYPT_HASH__ }
        reverse_proxy flasher:8000
    }

    # ─── 4. Grafana (CSP rewrite, then proxy) ─────────────────────────
    handle /grafana/* {
        header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
        header Content-Security-Policy "(style-src[^;]*)"  "${1} 'self'"
        reverse_proxy grafana:3000
    }

    # ─── 5. JupyterLab moved from catchall to explicit prefix ─────────
    handle /jupyter* {
        header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
        header Content-Security-Policy "(style-src[^;]*)"  "${1} 'self'"
        reverse_proxy jupyter:8888
    }

    # ─── 6. Home (siteapp serves /) ───────────────────────────────────
    handle / {
        reverse_proxy siteapp:8000
    }

    # ─── 7. Temporary redirect for old Jupyter bookmarks ──────────────
    # Removed in the release following the navbar release.
    @old_jupyter {
        path /lab* /tree* /login
    }
    redir @old_jupyter /jupyter{uri} 302

    # ─── 8. Global HTML rewrite (applies to every handle above) ───────
    @html header Content-Type *text/html*
    replace @html {
        "</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" defer></script></head>`
    }
}
```

Notes:

- The actual `caddyserver/replace-response` Caddyfile syntax (`replace` vs
  `replace_re` vs explicit block forms) follows the plugin's README at the
  pinned version; the snippet above is illustrative. The injection assertion
  in `services/caddy/tests/e2e/test_injection.py` is authoritative.
- `scripts/lib/render.sh::render_caddyfile` is extended with one new `sed`
  substitution: `-e "s|__PLATFORM_VERSION__|$(_unified_version)|g"`.
  `_unified_version` already exists in `render.sh` (used by `_siteapp_image` /
  `_flasher_image`). The substitution runs at deploy time on both laptop and
  CI, so the `?v=` query string in the injected `<script>` always matches the
  deployed platform release.
- Caddy `handle` blocks are mutually exclusive; the **most specific**
  matching block executes (Caddy does not fall through to less specific
  matches). The previous catchall `reverse_proxy jupyter:8888` is removed.
  Unmatched paths return 404.
- `/jupyter*` uses `handle` (not `handle_path`) because Jupyter is configured
  with `base_url=/jupyter` and expects to see the prefix.
- CSP rewriting uses Caddy's header regex form. If the upstream lacks an
  explicit `script-src` (so `default-src` applies), no match → no rewrite —
  this is safe **iff** the upstream's `default-src` already contains `'self'`
  (which is the case for current Grafana and Jupyter releases). Both
  scenarios (`script-src` present and absent) are covered by
  `test_csp_rewrite.py`; if a future upstream ships `default-src 'none'`,
  the test fails and we rewrite the broader directive.

### `compose/docker-compose.yml.tmpl`

Diff against current:

- `caddy.image` changes from `caddy:2` to `__CADDY_IMAGE__`. A new helper
  `_caddy_image` in `scripts/lib/render.sh` mirrors `_siteapp_image` /
  `_flasher_image`, returning `"${caddy_image_repo}:$(_unified_version)"`.
  `render_compose` is extended with a new `sed` substitution
  `-e "s|__CADDY_IMAGE__|${caddy_image}|g"`.
- `caddy.volumes` adds `./shell:/srv/shell:ro`.
- `jupyter.command` adds `--ServerApp.base_url=/jupyter`.
- Everything else unchanged.

### `compose/pins.yaml`

New entry following the existing `<service>_image_repo` pattern:

```yaml
# GHCR repository for the custom Caddy image (carries the replace-response
# plugin). The image *tag* lives in the root VERSION (release-please-managed);
# the full reference is "${caddy_image_repo}:$(cat VERSION)".
caddy_image_repo: ghcr.io/bioexperiment-lab-devices/lab-bridge-caddy
```

Bumped by the unified-release flow alongside siteapp and flasher.

### `compose/shell/navbar.js`

#### Top-level data

```js
const SERVICES = [
  { id: 'home',    label: 'Home',           href: '/',          icon: svgHome,    mode: 'persistent' },
  { id: 'docs',    label: 'Docs',           href: '/docs/',     icon: svgDocs,    mode: 'persistent' },
  { id: 'agent',   label: 'Download Agent', href: '/download/', icon: svgAgent,   mode: 'persistent' },
  { id: 'jupyter', label: 'JupyterLab',     href: '/jupyter/',  icon: svgJupyter, mode: 'bookmark' },
  { id: 'grafana', label: 'Grafana',        href: '/grafana/',  icon: svgGrafana, mode: 'bookmark' },
  { id: 'flasher', label: 'Flasher',        href: '/flash/',    icon: svgFlasher, mode: 'persistent' },
];

const PATH_RULES = [
  { prefix: '/jupyter', mode: 'bookmark' },
  { prefix: '/grafana', mode: 'bookmark' },
];  // anything else → persistent
```

Adding a service = one entry in `SERVICES` and, if it is a full-viewport app,
one entry in `PATH_RULES`. That is the entire surface for future changes.

#### Boot sequence

1. On `DOMContentLoaded`, determine current mode by longest-prefix match of
   `location.pathname` against `PATH_RULES`.
2. Create `<lds-navbar>`, append to `document.body`, attach Shadow DOM
   (`mode: 'open'`).
3. Inject `<link rel="stylesheet" href="/_shared/navbar-inner.css">` plus the
   rendered DOM template into the shadow root.
4. Set `document.documentElement.style.setProperty('--nav-width', initialWidth)`
   where `initialWidth` is `'52px'` for persistent, `'0px'` for bookmark.
5. Identify the active service (longest-prefix match against `SERVICES[].href`)
   and mark its DOM node `aria-current="page"`.
6. Register a `MutationObserver` on `document.body` (config:
   `{ childList: true }`) that watches for removal of the `<lds-navbar>` host
   element. If the host is no longer a direct child of body, re-append it.
   Defends against JupyterLab and other SPAs that may replace large
   subtrees during internal navigation.

#### State machine

```
persistent mode:                       bookmark mode:
  ┌───────────┐  toggle  ┌──────────┐    ┌──────────┐  hover/tap  ┌──────────┐
  │ collapsed │ ───────► │ expanded │    │ tab only │ ──────────► │ expanded │
  │  (52px)   │ ◄─────── │  (240px) │    │   (0px)  │ ◄────────── │  (240px) │
  └───────────┘          └──────────┘    └──────────┘  leave/Esc  └──────────┘
```

- **Persistent collapsed ↔ expanded**: chevron button at bottom of rail
  toggles. Choice persists in `localStorage['navbar:state']` and is applied on
  next page load. `--nav-width` stays `'52px'` in either state — expanded slides
  over content as overlay, no reflow on expand.
- **Bookmark tab ↔ expanded**: hover with 150 ms debounce (avoids accidental
  edge crossings); tap on touch devices. Collapses back on `Esc`, outside
  click, or mouseleave with 300 ms delay. `--nav-width` stays `'0px'`.

#### Shadow root DOM

```html
<aside part="rail" data-mode="persistent" data-state="collapsed"
       role="navigation" aria-label="Platform navigation">
  <nav>
    <a href="/" aria-label="Home" data-id="home">
      <svg>…</svg><span class="label">Home</span>
    </a>
    …
  </nav>
  <button class="toggle" aria-label="Expand sidebar">▶</button>
</aside>
<div class="backdrop" hidden></div>  <!-- visible only in expanded mode -->
```

#### Accessibility

- Collapsed-mode rail labels are visually hidden but accessible via
  `aria-label` on each link.
- Active service marked `aria-current="page"`.
- `Esc` collapses the expanded panel.
- Focus moves into the rail when expanded via keyboard; restored to the
  triggering element on collapse.
- Host element has `role="navigation"` and `aria-label="Platform navigation"`.

#### Failure modes

- If `navbar.js` fails to load (404, network error): the `<script>` tag fails
  silently, no `--nav-width` is set, the `padding-left: var(--nav-width, 0)`
  fallback keeps content at full width. Pages remain fully usable.
- If a service is down, nav links still render and click through to whatever
  Caddy returns.
- If the script somehow loads twice, custom-element registration is
  idempotent (`if (!customElements.get('lds-navbar')) …`); the mount check
  refuses to insert a second host element.

### Per-service hooks (one-time touches)

- `services/siteapp/app/templates/base.html`:
  - Add `padding-left: var(--nav-width, 0); transition: padding-left .15s ease;`
    to the outer container (likely `<body>` or `<main>`).
  - Remove the existing `<header class="topbar">` block — the sidebar replaces
    it.
- `services/siteapp/app/templates/home.html` (new): minimal stub with heading,
  one paragraph, links to the other services. Real content lands in a follow-up
  spec.
- `services/siteapp/app/main.py` (or wherever routes are wired): add a `GET /`
  handler that renders `home.html`. (The previous bare-root → `/docs/`
  redirect lives in the Caddyfile, not siteapp, and is removed there — see
  the new Caddyfile in the Components section, which replaces the
  `@bare_root path_regexp ^/$ / redir @bare_root /docs/ 302` lines with a
  `handle /` block proxying to siteapp.)
- `services/flasher/web/src/App.tsx` (or its root layout): add
  `padding-left: var(--nav-width, 0)` to the root container.

These are the only per-service changes. After this PR, modifying the navbar
never requires touching any service again — only `compose/shell/navbar.js`
and/or `compose/shell/navbar-inner.css`.

## Testing

Three tiers per CLAUDE.md.

### Unit tests (none required)

`navbar.js` logic is so small that the e2e tier covers it; no separate unit
tier.

### Service-level e2e

- `services/caddy/tests/e2e/test_injection.py` — `<script>` injected on
  text/html, absent from JSON/CSS/binary.
- `services/caddy/tests/e2e/test_csp_rewrite.py` — CSP `script-src` and
  `style-src` include `'self'` after passing through `/jupyter*` and
  `/grafana*` handlers.
- `services/caddy/tests/e2e/test_passthrough.py` — non-HTML responses
  byte-identical; gzip and brotli round-trip correctly.
- `services/caddy/tests/e2e/test_mutation_guard.py` — fixture page that
  destroys `document.body`; assert the host element is re-attached.
- `services/siteapp/tests/e2e/test_home_page.py` — `/` returns 200 with the
  Home stub; the old bare-root → `/docs/` redirect is gone.
- `services/siteapp/tests/e2e/test_navbar_hook.py` — `base.html` exposes
  `padding-left: var(--nav-width, 0)` on the relevant container; the old
  `<header class="topbar">` is absent.
- `services/flasher/tests/e2e/test_navbar_hook.py` — root container's
  computed style respects `--nav-width` when a test value is injected.

### Platform integration (bats)

New matrix cell `navbar` in `pr-platform.yml`:

- `tests/integration/test_navbar_smoke.bats`:
  1. Every HTML response across siteapp/flasher/jupyter/grafana contains
     `<script src="/_shared/navbar.js?v=`.
  2. `/_shared/navbar.js` returns 200 with `Content-Type: application/javascript`.
  3. `/_shared/navbar.css` returns 200.
  4. CSP rewriting visible on `/jupyter` and `/grafana` response headers.
  5. JSON responses (e.g., `/api/public/server-info`) are unmodified.
  6. Bare root `/` serves the Home stub, not Jupyter.
  7. The temporary redirect `/lab* → /jupyter/lab*` returns 302 with the
     expected location.

Mirror the `compose_images_available` skip pattern from
`test_routes_smoke.bats:11-14`; Quay/Docker Hub anonymous pulls can flake.

## Release strategy

- **Single PR**, single squash-merge. The change touches the custom Caddy
  build, Caddyfile, Jupyter `base_url`, siteapp templates and Home route, and
  the flasher root layout — they must land atomically.
- Conventional Commit title: `feat(platform): shared navbar via Caddy
  injection` (the `feat` triggers a minor bump under release-please).
- The release-please PR for that version is the integration test gate
  (`pr-platform` runs full bats, `pr-caddy / caddy` runs full e2e).
- Branch protection's required-check list updated **before** the workflow
  ships, using the `verify` stub transitional pattern from CLAUDE.md if there
  is a window where the workflow exists but isn't yet required.
- The `/lab → /jupyter/lab` redirect is removed in the next release after the
  navbar lands.

## Risks and mitigations

1. **`caddyserver/replace-response` is community-maintained, not core.** Pin
   to a specific tag in `xcaddy`; Renovate watches updates; the e2e suite
   catches regressions on bump.
2. **HTML rewriting can corrupt edge-case responses.** Plugin buffers the
   full body by default (size-capped). The e2e suite includes fixtures with
   `</head>` inside `<script>` string literals and inside `<![CDATA[` blocks.
3. **JupyterLab's pushState nav doesn't re-trigger script load.** Custom
   element mounts once at initial load and persists. A `MutationObserver`
   defends against body-content destruction during internal nav.
4. **Jupyter `base_url` migration breaks existing bookmarks.** Caddy keeps a
   temporary `/lab* → /jupyter/lab*` 302 redirect for one release; documented
   in the release notes that release-please generates.
5. **CSP regex rewrite is fragile against upstream policy format changes.**
   e2e tests assert against canned upstream fixtures; Renovate-triggered
   Grafana/Jupyter image bumps re-run the suite before merge.
6. **`replace-response` adds CPU/memory cost on large pages.** Acceptable for
   an internal lab tool; monitor via Loki/Grafana; if it bites, add a
   body-size cap and fall back to passthrough on large responses.
7. **Shadow DOM CSP under strict-dynamic-only nonces.** Known unknown.
   Browsers honor both `'self'` and `'nonce-...'` when both are present, so
   regex-appending `'self'` is sufficient for current Grafana/Jupyter. If
   either upstream moves to nonce-only `'strict-dynamic'`, the navbar needs
   a server-rendered nonce. No v1 action.
8. **Adding `pr-caddy / caddy` as required check blocks PRs if branch
   protection is not updated in lockstep.** Mitigation: use the `verify`
   stub transitional pattern (see CLAUDE.md).
9. **Hot edits to `compose/shell/navbar.js` in production stay
   query-string-pinned to the deployed `__PLATFORM_VERSION__`.** Documented;
   emergency patches append `?force=<timestamp>`; `task deploy` reloads
   Caddy.

## Out of scope (non-goals)

- Per-user navigation customisation (reorder, hide).
- Service health / status badges in the nav.
- Login state / who-is-logged-in indicator.
- Mobile-first layout (works on narrow widths; no breakpoint-specific design).
- Translations (English-only labels for v1).
- Animated transitions beyond the 150 ms ease on `padding-left`.
- A "search" or command-palette overlay in the navbar.
- The Home page **content** — this spec defines the route and a minimal stub;
  real welcome-page design is a separate follow-up.

## Open implementation details (not blocking)

- Exact `caddyserver/replace-response` directive syntax — follow the plugin
  README at the pinned version; e2e test is authoritative.
- Icon set — heroicons / lucide / hand-rolled SVG — implementation taste.
- `navbar-inner.css` as a separate file vs inlined in `navbar.js` as a tagged
  template literal — implementation taste.

## References

- `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` — the
  per-service split that `services/caddy/` follows.
- `docs/superpowers/specs/2026-05-17-unified-release-design.md` — the unified
  release flow that pins and ships the custom Caddy image.
- `docs/adding-a-service.md` — checklist mirrored when adding
  `services/caddy/`.
- `CLAUDE.md` — invariants: per-service isolation, single VERSION, three-tier
  testing, branch-protection lockstep.

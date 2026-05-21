# Auth UI surfaces — login form, common navbar, 403 / 404 (and sign-out modal)

Status: draft
Date: 2026-05-21
Design source: `docs/design_handoff_auth/` (README, `auth.css`, JSX references, `preview.html`)

## Goal

Bring four auth-related UI surfaces in lab-bridge up to the high-fidelity design shipped in `docs/design_handoff_auth/`:

1. The **sign-in page** at `/login`.
2. The **403 (Forbidden)** and **404 (Not found)** error pages at `/_errors/403` and `/_errors/404`.
3. The platform **navbar's auth slot** — both signed-in (user block with avatar + live-session dot + name) and signed-out (accent-soft "Sign in" CTA) — plus the three-tier rail-bottom button hierarchy (sign-in CTA / theme toggle / collapse) from the handoff.
4. The **sign-out confirmation modal** opened directly from the rail's user block (no popover).

The visual chrome of nav items, brand row, and rail mode (persistent / bookmark) already roughly matches the design — this change finishes the work for the auth-related rail surfaces only and does not touch routing or active-state logic.

## Non-goals

- RU translations for the new surfaces (deferred — see "Deferred").
- A user-menu popover. We open the sign-out modal directly from the user block; if a second menu item ever appears, we add a popover then.
- Renaming `/login` → `/sign-in`. The design's URL bar shows `/sign-in` but the route is incidental to the surface, and renaming would force Authelia + CI changes for no user-visible benefit.
- Headless-browser tests for the navbar. The existing pytest navbar hook test (`test_navbar_hook.py`) stays as the only navbar-level assertion; visual correctness is verified in a browser before PR.
- Changes to Authelia access-control rules or the `/api/auth/firstfactor` / `/api/auth/whoami` API contracts.

## Constraints inherited from the codebase

- **No React.** The siteapp uses Jinja2 + vanilla JS; the platform navbar is a Shadow-DOM vanilla web component (`<lds-navbar>`) injected by Caddy's `replace-response` plugin. The handoff explicitly says the JSX files are design references — recreate in the existing environment.
- **Tokens already match the design.** `services/siteapp/app/static/tokens.css` and `compose/shell/navbar-inner.css` already define the color tokens (`--accent`, `--surface-rail`, `--warning-soft`, etc.) used by the design. No new CSS variables are added; rules use the existing names.
- **`/api/auth/whoami` already returns enough context** for the user block. It returns `{user, groups, display_name, email}`. We use `display_name || user` for the name; we derive initials client-side (split on whitespace, take first letter of each, cap at 2, uppercase). Groups are not displayed.
- **Caddy navbar injection is a single `<script>` tag at `/_shared/navbar.js`** appended to `</head>` for every `text/html` response. We do not touch the injection mechanism, only the script + its inner CSS.
- **The siteapp navbar's `--nav-width` hook** must stay: `base.html` sets `body { padding-left: var(--nav-width, 0) }` so the rail doesn't overlap content. Test `test_navbar_hook.py` enforces this.

## Architecture

```
┌────────────────────────────── browser ──────────────────────────────┐
│                                                                     │
│  every text/html page ─── Caddy replace-response ───┐               │
│                                                     ▼               │
│  ┌────────────── <lds-navbar> (Shadow DOM) ──────────────┐         │
│  │  rail (brand • nav • auth slot • theme/collapse)      │         │
│  │  auth slot ──fetch──> /api/auth/whoami                │         │
│  │    signed-in:  .user button → opens .modal (in DOM)   │         │
│  │    signed-out: .signin-cta link → /login?rd=…         │         │
│  │  .modal ── confirm ──> POST /logout → 302 /           │         │
│  └────────────────────────────────────────────────────────┘         │
│                                                                     │
│  /login           ──→ siteapp/login.html  (Jinja, vanilla JS)       │
│  /_errors/403,404 ──→ siteapp/error_*.html (Jinja, attempted path)  │
└─────────────────────────────────────────────────────────────────────┘
```

Boundaries, each owned by one piece of code:
- **`services/siteapp/app/auth.py`** owns route handlers (`/login`, `/api/auth/firstfactor`, `/api/auth/whoami`, `/logout` — extended to accept POST, `/_errors/403`, `/_errors/404`), Authelia proxying, and `attempted_path` extraction (reads `?path=` from the query string set by Caddy).
- **`services/siteapp/app/templates/*` + `app/static/site.css`** own the rendered surfaces for `/login` and the error pages.
- **`compose/shell/navbar.js` + `navbar-inner.css`** own the rail, the user block, and the sign-out modal.
- **`compose/Caddyfile.tmpl`** owns one small addition: the `handle_errors` rewrites thread `{http.request.orig_uri}` into the `?path=` query string so siteapp can render the attempted URL.

The sign-out modal lives **inside the navbar's Shadow DOM**, not in siteapp templates, because it has to render over Jupyter/Grafana too — and the navbar is the only thing reliably injected into those.

## Component details

### 4.1. Sign-in page — `services/siteapp/app/templates/login.html`

Full rewrite. Markup follows the design 1:1.

**Structure (top to bottom):**
1. `.lb-login-page` outer (flex centered, padding `40px 32px`).
2. `.lb-login` (max-width 420, flex column).
3. `.lb-login__card` `<form>` (white surface, `border-strong`, 8px radius, `shadow-card`, padding `28px 30px 22px`):
   - `h1.lb-login__title` — "Sign in to lab-bridge".
   - `.lb-login__error[role="alert"]` (hidden by default) — red-left-border banner with circular `!` mark + message.
   - `.lb-field` × 2 (username + password). Each: mono-uppercase `.lb-field__label`, `.lb-field__input` (height 38, 14px text). Password field wraps the input + `.lb-field__reveal` (`<button type="button">` with `aria-pressed` + `aria-label`, toggles eye / eye-off SVG and the input `type` between `password` and `text`).
   - `.lb-check` — visually-hidden checkbox + custom `.lb-check__box` (focus-visible ring), two-line text: `.lb-check__label` ("Keep me signed in") + `.lb-check__hint` ("Stay signed in for 90 days on this device.").
   - `button.lb-login__submit` — accent fill, height 40, weight 600. Disabled when either field is empty or `loading === true`. Loading state swaps the arrow SVG for `.lb-login__spinner` and the label for "Signing in…".
   - `footer.lb-login__foot` — top border, mono-muted note: key icon + "No account? Ask your server administrator — sign-up is not public."

**Behavior (inline `<script>`, no module/build):**
- Read `rd` from `URLSearchParams` (fall back to `{{ rd|tojson }}` from the template context).
- Track `loading` via a `data-loading` attribute on the form to toggle the submit content.
- On submit: `e.preventDefault()`, POST `/api/auth/firstfactor` with `{username, password, targetURL: rd, keepMeLoggedIn: <checkbox>}`.
- On 200: read body, `location.assign(body.redirect || '/')`.
- On non-200: show the error banner. Copy: status 401 → "Incorrect username or password."; other → "Sign-in failed (<status>)." (matches today's behavior).
- On network error: "Network error."
- The reveal button click toggles a `show` flag, updates input `type`, swaps icon, sets `aria-pressed`.
- The submit button's `disabled` attribute is recomputed on `input` of either field.

**Accessibility:**
- `autoComplete="username"` / `"current-password"` so password managers work.
- Error banner is `role="alert"` so SR users hear it on appearance.
- Spinner is `aria-hidden="true"`; the button label text changes for SR.
- Reveal button is `<button type="button">` (so it doesn't submit) with `aria-label="Show password"` / `"Hide password"` and `aria-pressed`.
- Visually-hidden checkbox is focusable; `.lb-check__box` shows focus-visible ring driven by `:focus-visible` on the input.

**Route stays `/login`.** `auth.py`'s `login_page` handler is unchanged in signature: `GET /login?rd=…` renders the template with `{"rd": rd}`.

### 4.2. Error pages — `templates/error_403.html`, `templates/error_404.html`

Full rewrite. Both share the same shell from the handoff:

```
.lb-forbidden-page  (flex centered, padding 56px 32px)
└── .lb-forbidden
    ├── span.lb-forbidden__code   ("Error 403 · Forbidden" / "Error 404 · Not found")
    └── .lb-forbidden__card
        ├── .lb-forbidden__head    (icon badge + h1 title)
        ├── p.lb-forbidden__body   (single paragraph)
        ├── dl.lb-forbidden__meta  (one row: dt "Attempted path", dd <code>{{ path }}</code>)
        └── .lb-forbidden__actions
            └── button.lb-forbidden__primary   onclick="history.back()"  (← Back)
```

Differences between 403 and 404:
- **403** — eyebrow "Error 403 · Forbidden"; icon badge `.lb-forbidden__lock` (warning-soft fill, warning border, warning text); lock SVG; title "You don't have access to this page"; body "This area is restricted to a different role. If you need access for your work, ask the server administrator to update your permissions."
- **404** — eyebrow "Error 404 · Not found"; icon badge gets the additional modifier class `.lb-forbidden__lock--404` (surface-sunken, border-strong, text-secondary); magnifying-glass SVG; title "Page not found"; body "We couldn't find that page. The link may be broken or the resource may have been renamed."

Both `extend "base.html"`, so the injected `<lds-navbar>` and the `--nav-width` body padding apply — the rail stays on the left, matching the design intent: "the rail stays — this is NOT a logout."

**`attempted_path` source.** The naïve choice — `X-Forwarded-Uri` — doesn't work here: Caddy's `handle_errors` block does `rewrite @e403 /_errors/403` *before* proxying to siteapp, so the proxied request already carries the rewritten URI in `X-Forwarded-Uri`, not the original path the user typed. To preserve the original, extend the `handle_errors` rewrites in `compose/Caddyfile.tmpl` to thread it through as a query string using Caddy's `{http.request.orig_uri}` placeholder (the URI as received, before any rewrites):

```caddy
rewrite @e403 /_errors/403?path={http.request.orig_uri}
rewrite @e404 /_errors/404?path={http.request.orig_uri}
rewrite @e401 /_errors/403?path={http.request.orig_uri}
```

In `auth.py`'s `error_403` / `error_404` handlers:

```python
attempted_path = request.query_params.get("path") or request.url.path
```

Pass it as `{"attempted_path": attempted_path}`. The template HTML-escapes it via Jinja autoescape (default in `Jinja2Templates`). The mono `<code>` chip has `user-select: all` so users can copy the path with a single click — useful when forwarding to an operator. The fallback to `request.url.path` covers direct hits to `/_errors/403` (e.g. e2e tests, manual debugging) so the template never breaks.

### 4.3. Navbar visual upgrade — `compose/shell/navbar.js` + `navbar-inner.css`

Three-tier rail-bottom button hierarchy. The current code applies one uniform button shape to sign-in, theme, and collapse; the design splits them by visual weight:

| Element | Treatment | Class change |
|---|---|---|
| Sign-in CTA (signed-out) | `bg: accent-soft`, border `accent-border`, text+icon `accent` | New `.signin-cta` (replaces the current `.lds-login-btn`) |
| Theme toggle | `bg: surface`, border `border`, text `text-secondary`, icon `text-muted` | Existing `.theme-toggle` — verify it matches; no class change |
| Collapse | `bg: transparent`, no border, text `text-muted`, 26px tall | Existing `.toggle` — tune to recessive look |

The brand row already has the version pill — verify spacing matches 56px. Nav-item active-state visuals already match the design (`background: surface`, `border: border`, accent left bar) — no change.

### 4.4. Navbar auth slot — signed-in user block

Replace the current `.lds-avatar` round-circle-link with a proper user block. The render path is in `renderAuthSlot()` (already inside `navbar.js`).

**Signed-in markup (inside `.auth-slot`, in the persistent rail):**

```html
<button class="user" type="button" aria-label="Account menu: {name}">
  <span class="user__avatar" aria-hidden="true">{initials}</span>
  <span class="user__text">
    <span class="user__name">{name}</span>
  </span>
</button>
```

**CSS rules** (added to `navbar-inner.css`, mapped from the design's `.lb-rail__user` / `.lb-rail__avatar`):

- `.user` — flex row, gap 10, padding `6px 8px`, border `border`, bg `surface`, radius 5, min-height 40, hover → border `border-strong` + bg `surface-strip`.
- `.user__avatar` — 26×26 circle, accent fill, white text (`text-inverse` in dark), mono initials 10.5px, uppercase.
  - `.user__avatar::after` — 9×9 circle absolutely positioned bottom-right (offset `-2px / -2px`), `bg: var(--success)`, 2px solid `surface-rail` border. The live-session dot. (Always shown when signed in — there is no "offline" state for an authenticated session in this product.)
- `.user__text` — flex column, name overflow-ellipsis.
- `.user__name` — 13px, weight 600, `letter-spacing: -0.005em`.
- In collapsed rail (`aside[data-state="collapsed"]`): `.user__text` hides, `.user` reduces to padding 5, justify-center, min-height 36 — leaving just the avatar with the live-dot.

**Initials derivation (client-side, in `renderAuthSlot`):**

```js
const source = data.display_name || data.user || '';
const initials = source
  .split(/\s+/)
  .filter(Boolean)
  .slice(0, 2)
  .map(s => s[0])
  .join('')
  .toUpperCase() || '?';
```

**Click handler:** opens the sign-out modal (see 4.5). The block is `<button type="button">`, not an anchor — we no longer link to `/logout` directly.

### 4.5. Navbar auth slot — signed-out CTA

Replace `.lds-login-btn` with `.signin-cta`:

```html
<a class="signin-cta" href="/login?rd={encoded}">
  <svg>…key icon…</svg>
  <span>Sign in</span>
</a>
```

CSS: `bg: accent-soft`, border `accent-border`, color `accent`, icon `accent`, hover keeps bg but darkens via `filter: brightness(0.97)` (or `1.08` in dark). Matches the design's `.lb-rail__signin`.

In collapsed rail, the label hides, leaving just the key icon — same pattern as today.

### 4.6. Sign-out modal

Rendered inside the navbar's Shadow DOM as a sibling to `<aside>`. Created/destroyed on demand (not always-mounted) so it doesn't intercept events when closed.

**Markup:**

```html
<div class="modal" role="dialog" aria-modal="true" aria-labelledby="lb-signout-title">
  <div class="modal__backdrop"></div>
  <div class="modal__card">
    <header class="modal__head">
      <div class="modal__ico" aria-hidden="true"><svg>…logout arrow…</svg></div>
      <h2 id="lb-signout-title" class="modal__title">Sign out?</h2>
      <button class="modal__close" type="button" aria-label="Cancel"><svg>…X…</svg></button>
    </header>
    <div class="modal__body">
      <p class="modal__lede">You'll be signed out of lab-bridge. Open sessions to JupyterLab, Grafana, and Flasher will end.</p>
      <div class="modal__user">
        <span class="user__avatar">{initials}</span>
        <div class="modal__user-text"><b>{name}</b></div>
      </div>
    </div>
    <footer class="modal__foot">
      <button class="modal__btn" type="button" data-action="cancel">Cancel</button>
      <button class="modal__btn modal__btn--danger" type="button" data-action="confirm">Sign out</button>
    </footer>
  </div>
</div>
```

**CSS** (added to `navbar-inner.css`, mapped from `auth.css` `.lb-modal*` rules; selector prefix `.modal` inside the shadow root):

- `.modal` — `position: fixed; inset: 0; z-index: 10000;` flex centered, padding 24.
- `.modal__backdrop` — `position: absolute; inset: 0; background: rgba(26,25,22,0.45); backdrop-filter: blur(2px);` (dark theme overrides to `rgba(0,0,0,0.55)`).
- `.modal__card` — surface, border-strong, radius 8, `shadow-overlay`, max-width 420, animation `lb-modal-in` 160ms.
- `.modal__head` — surface-strip, padding `16px 16px 14px 18px`, border-bottom, flex row gap 12.
- `.modal__ico` — 36×36 rounded badge, `danger-soft` bg, `danger-border` border, `danger` color, contains the logout arrow icon.
- `.modal__title` — 16px, weight 600, `letter-spacing: -0.01em`.
- `.modal__close` — 28×28 transparent button, on hover slight neutral wash.
- `.modal__body` — padding `18px 20px`, gap 14.
- `.modal__lede` — 13.5px, line 1.55, `text-secondary`.
- `.modal__user` — surface-sunken row with avatar + name (reuses `.user__avatar` rules; no live-dot needed inside the modal, achieved via `.modal__user .user__avatar::after { display: none }`).
- `.modal__foot` — surface-strip, flex-end, gap 10, padding `14px 16px`, border-top.
- `.modal__btn` — height 34, padding `0 14px`, radius 5, surface bg, border-strong, hover deepens border.
- `.modal__btn--danger` — danger fill, white text (`text-inverse` in dark), weight 600.
- `@keyframes lb-modal-in { from { opacity: 0; transform: translateY(8px) scale(0.98); } to { opacity: 1; transform: none; } }`.

**Open / close logic** (in `navbar.js`, on the `<lds-navbar>` instance):

- `_openSignOutModal()` — saves `document.activeElement` (the user button) as the focus-return target, mounts the modal HTML into the shadow root, wires backdrop / cancel / close / Esc, applies focus trap (`focusin` listener that bounces focus back to the first focusable inside `.modal__card` if it leaves), focuses the Cancel button.
- `_closeSignOutModal()` — removes the modal node, restores focus to the saved target.
- The existing `_handleEscape` already handles Esc for rail collapse — we extend it: if a modal is open, close the modal first (do not collapse the rail).
- Confirm handler:
  ```js
  fetch('/logout', { method: 'POST', credentials: 'include' })
    .finally(() => location.assign('/'));
  ```
  We `location.assign('/')` regardless of POST outcome — the page reload will re-fetch whoami; if the session is somehow still alive (e.g. Authelia 500ed) the user sees they're still signed in and can retry, which is a better failure mode than silently swallowing the error.

### 4.7. `/logout` route — accept POST in addition to GET

Today `/logout` is a `GET` that POSTs to Authelia and returns a 302 + Set-Cookie expiry. We extend it to also accept `POST` with identical behavior. Keep `GET` because (a) bookmarks / link-style `<a href="/logout">` may exist in the wild and (b) the previous nav design relied on it.

Implementation: change the decorator from `@router.get("/logout")` to `@router.api_route("/logout", methods=["GET", "POST"])`. The handler body is unchanged.

### 4.8. CSS organization

- **Page-level rules** (`.lb-login*`, `.lb-field*`, `.lb-check*`, `.lb-forbidden*`) → appended to `services/siteapp/app/static/site.css`. Tokens already exist in `tokens.css`; we reuse them.
- **Rail-level rules** (`.user`, `.signin-cta`, `.modal*`) → appended to `compose/shell/navbar-inner.css`. The Shadow DOM is self-contained — host-page CSS does not propagate in.
- **No new files.** No CSS-in-JS. No build step.

## Data flow

**Sign-in:**
```
user → /login → GET → siteapp renders login.html (with rd from query)
user submits → POST /api/auth/firstfactor → siteapp proxies to Authelia
  200 → siteapp returns {redirect} + Set-Cookie → JS does location.assign(redirect)
  401/etc → siteapp returns Authelia's body → JS renders error banner
```

**Sign-out (new):**
```
user clicks .user → navbar opens modal
user clicks Sign out → fetch POST /logout → siteapp POSTs Authelia /api/logout
  then siteapp returns 302 /  + Set-Cookie (Max-Age=0)
finally → location.assign('/')
```

**403 / 404:**
```
user requests /some/path → Caddy gets non-2xx from upstream → handle_errors
  → rewrite to /_errors/403?path=/some/path  (path= sourced from {http.request.orig_uri})
  → siteapp renders error_403.html with attempted_path from query params
  → template chip shows /some/path
```

**Navbar auth state:**
```
<lds-navbar> connects → renderAuthSlot() fetches /api/auth/whoami
  → response cached on the instance (re-render on storage event for theme only;
     no re-fetch on navigation — full page reloads re-fetch naturally)
  → if user: render .user button; else render .signin-cta link
```

## Error handling

- **`/api/auth/whoami` unreachable.** Today's behavior: render signed-out state (no surprises). Keep.
- **`/api/auth/firstfactor` returns non-JSON.** Today's behavior: JS throws and falls into the `catch`, shows "Network error." Keep.
- **`POST /logout` fails.** Modal's `.finally` runs `location.assign('/')`. The user lands on the home page; if the session is still alive, the navbar re-fetches whoami and shows signed-in state. The user can retry. (No silent dead-end.)
- **`?path=` missing on `/_errors/*`.** Fall back to `request.url.path`. The chip will show `/_errors/403`, which is mildly weird but does not break the page. This is the path direct-hits (debugging, e2e tests) take.

## Testing

### siteapp pytest e2e (`services/siteapp/tests/e2e/`)

- **`test_login_page.py`** — extend with assertions for the new markup:
  - `aria-pressed` reveal button is present in the password field.
  - Error banner element with `role="alert"` is present (hidden initially).
  - Submit button has `disabled` attribute in the initial render.
  - Foot note is present (text "server administrator").
  - Existing assertions (`name="username"`, `name="password"`, rd preservation, base.html marker) stay.
- **`test_error_pages.py`** — extend:
  - 403 page contains the eyebrow text "Error 403 · Forbidden" and the lock SVG.
  - 404 page contains "Error 404 · Not found" and the magnifier SVG (asserted via the `.lb-forbidden__lock--404` class on its container).
  - Both pages, when called with `?path=/admin/users`, render `<code>/admin/users</code>` in the meta block.
- A direct hit to `/_errors/403` (no `?path=`) falls back to `request.url.path` and renders `<code>/_errors/403</code>` without erroring.
- **`test_logout.py`** — add: `POST /logout` returns 302 + Set-Cookie expiry (identical to today's GET). Keep the GET test.
- **`test_login_flow.py`** — unchanged.
- **`test_navbar_hook.py`** — unchanged.

### Manual browser verification (per CLAUDE.md UI rule)

Before opening the PR, walk through these by hand in a browser against a local stack (`scripts/deploy.sh` to the fake-VPS, or `docker compose` for siteapp directly):

1. `/login` — error banner shows on bad password, reveal toggle flips icon + input type, "Keep me signed in" reflects in the cookie's Max-Age on successful login.
2. `/_errors/403` and `/_errors/404` — rail stays on the left, attempted-path chip is selectable, Back returns to the previous page.
3. Navbar signed-out — sign-in CTA is the accent-soft treatment, opens `/login?rd=`.
4. Navbar signed-in — user block shows avatar + name + live-dot, clicking opens the sign-out modal, Cancel/Esc/backdrop close it, Confirm signs out and lands on `/`.
5. Sign-in CTA visible on a Jupyter/Grafana page in bookmark mode (overlay).
6. Dark theme — toggle, verify all surfaces (login, errors, modal) flip correctly.

## Deferred

- **RU translations** for login, error pages, modal. The design ships full EN+RU; the codebase has an EN/RU pattern in `strings.py` for home + download. Adding it here means (a) three more dicts in `strings.py` and threading lang through templates, and (b) plumbing a locale into the Shadow-DOM navbar (which has no SSR locale today). Defer to a follow-up PR; capture the EN+RU copy from the handoff JSX files in that PR's spec.
- **User-menu popover.** We open the sign-out modal directly. Add a popover when there's >1 menu item.
- **Headless-browser tests for the navbar.** Visual correctness is verified manually for this PR. Headless-browser coverage is a separate effort that should apply to all navbar interactions (collapse, bookmark drag, theme toggle, auth slot), not just sign-out.

## Risks

- **Modal in Shadow DOM + focus trap.** Focus management across the shadow boundary is fiddly. The plan uses a `focusin` listener bouncing focus back into the modal card if it leaves — verified pattern, but worth checking that Tab cycling works across Cancel/Confirm/Close. If we hit issues, fallback is to portal the modal to `document.body` (still inside our z-index plane) — would mean duplicating the CSS at light-DOM scope.
- **`POST /logout` from the Shadow DOM.** Cookies are `SameSite=Lax`, so `fetch('/logout', { credentials: 'include' })` works for same-site requests. Verified by reading the cookie set in `auth.py`. No CORS concerns (same origin).
- **Caddyfile `?path=` rewrite.** Modifying `handle_errors` is a small, isolated change, but the Caddyfile is platform-wide config — a typo there can break every error response. Verify locally with the platform integration tests (`bats tests/integration/test_routes_smoke.bats`) and by manually triggering a 404 against a fake-VPS bring-up before merging.

## Acceptance

1. `/login`, `/_errors/403`, `/_errors/404` visually match `docs/design_handoff_auth/preview.html` for those surfaces (light + dark themes).
2. The platform navbar's auth slot (signed-in + signed-out) matches the rail design from `preview.html`.
3. Clicking the user block opens the sign-out modal; Cancel/Esc/backdrop close it; Confirm signs out and lands on `/`.
4. siteapp e2e suite passes (existing + new assertions).
5. `test_navbar_hook.py` still passes; `base.html`'s `--nav-width` body padding is still in place.
6. No new files; no CSS-in-JS; no build step.

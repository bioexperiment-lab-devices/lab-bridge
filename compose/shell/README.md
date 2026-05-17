# compose/shell

Platform shell assets — the navbar shared across all lab-bridge services.

These files are served by Caddy at `/_shared/*` (file_server bound to this
directory, with `uri strip_prefix /_shared` so `/_shared/navbar.js`
resolves to `compose/shell/navbar.js`). The navbar script is injected by
Caddy's `replace-response` plugin into every `text/html` response across
the stack.

## Files

- `navbar.js` — vanilla ES2020 web component (`<lds-navbar>`). Boots on
  `DOMContentLoaded`, picks render mode by path, mounts to `document.body`,
  exposes `--nav-width` on `:root`. **Single source of truth for navigation.**
- `navbar-inner.css` — visual styles loaded into the Shadow DOM via
  `<link rel="stylesheet">`. Kept separate from the host element's
  positioning so Shadow DOM isolation stays clean.

## Editing

- Adding/renaming a service: edit `SERVICES` (and `PATH_RULES` if the new
  service is full-viewport) in `navbar.js`. No other file needs to change.
- Styling tweaks: edit `navbar-inner.css`.

## Cache-busting

Caddy injects the script tag with `?v=__PLATFORM_VERSION__`, substituted at
deploy time from the root `VERSION` file. Bumping the release auto-busts the
cache. For emergency patches between releases, edit the `replace` directive in
`compose/Caddyfile.tmpl` to append a unique query parameter (e.g.,
`?v=__PLATFORM_VERSION__&force=20260517-1`) and redeploy.

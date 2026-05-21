# Unified group-based auth via Authelia

**Status:** draft
**Date:** 2026-05-20
**Owners:** platform

## Goal

Replace today's three independent auth surfaces — Jupyter's shared password,
Flasher's Caddy `basic_auth`, and Grafana's local admin account — with a single
group-based identity provider (Authelia) that gates every protected service on
the stack. Two groups: `researchers` (JupyterLab + Grafana viewer) and `admins`
(everything, including Flasher and Grafana admin). Custom login form, 403, and
404 pages render inside the existing siteapp navbar shell. User management is
task-automated.

Bearer tokens (`agent_upload_token`, `flasher_upload_token`) remain out of
scope — they continue to be managed by hand via existing `task secrets:rotate-*`
commands.

## Services in scope

- **Gated, group-based:**
  - `/jupyter*` — groups `admins` + `researchers`
  - `/grafana/*` — groups `admins` + `researchers`; OIDC role map sends
    `admins` → Grafana `Admin`, `researchers` → `Viewer`
  - `/flash*` — group `admins` only
- **Unauthenticated (unchanged):**
  - `/` (home), `/docs/*`, `/download/*`, `/api/public/*`,
    `/api/agent/upload` (bearer-token gated, not session-based)
- **New public endpoints (siteapp):**
  - `/login`, `/logout`, `/api/auth/firstfactor`, `/api/auth/whoami`,
    `/_errors/403`, `/_errors/404`
- **New public path (Caddy → Authelia):**
  - `/auth/*` — only because OIDC discovery + redirects need to be reachable
    from the browser. The Authelia React portal is not used; `/auth/` redirects
    to `/login`.

## Architecture overview

```
                                      ┌──────────────────────────┐
                                      │ Authelia (labnet only)   │
                                      │  - users_database.yml    │
                                      │  - SQLite storage        │
                                      │  - OIDC issuer + portal  │
                                      └────────────┬─────────────┘
                                                   │
   browser ─► Caddy (single domain) ──┬────────────┤
                                      │            │
                                      │   /auth/*  │  (public — OIDC endpoints
                                      │            │   + .well-known)
                                      │            │
                                      │   /jupyter*, /flash*  ── forward_auth ──► Authelia
                                      │            │
                                      │   /grafana/*  ──► Grafana ── OIDC ──► Authelia
                                      │            │
                                      │   /login, /logout, /_errors/*  ──► siteapp templates
                                      │   /api/auth/*  ──► siteapp ──► Authelia (server-to-server)
                                      │
                                      └──── /docs, /download, /api/public  (PUBLIC, unchanged)
```

**Key invariants:**

- **Three auth modes per upstream:**
  - **OIDC** for Grafana (Grafana needs identity to map roles).
  - **forward_auth** for JupyterLab and Flasher (header-based:
    `Remote-User`, `Remote-Groups`, `Remote-Name`, `Remote-Email`).
  - **None** for siteapp's public routes.
- **Authelia is reachable two ways:** at `/auth/*` (public — OIDC redirects and
  JWKS) and via the internal `labnet` hostname `authelia:9091`
  (forward_auth + siteapp's server-side first-factor proxy).
- **Custom login is owned by siteapp.** Authelia's React portal is bypassed.
  - `GET /login` renders `templates/login.html` (Jinja, extends `base.html`,
    inherits the global navbar).
  - `POST /api/auth/firstfactor` server-side-proxies `{username, password,
    targetURL, requestMethod, keepMeLoggedIn}` to `authelia:9091/api/firstfactor`
    and pipes back the `Set-Cookie` header so the browser holds the
    `authelia_session` cookie scoped to the domain.
- **403 and 404 are siteapp routes.** Caddy's `handle_errors` block rewrites to
  `/_errors/403` / `/_errors/404` and reverse-proxies to siteapp. Templates
  extend `base.html` so the navbar renders.
- **Groups are fixed: `admins`, `researchers`.** No arbitrary group creation.
  Users may belong to both. Group checks are encoded in Authelia's
  `access_control` rules.
- **navbar.js gains an auth indicator.** On boot it fetches
  `/api/auth/whoami`. If `{user}` → renders a circle avatar with the first
  letter of `user`, linking to `/logout`. Else → renders a "Login" link to
  `/login?rd=<current_path>`. Works across all upstreams (siteapp, flasher,
  jupyter, grafana) because the call is to siteapp on the same domain and the
  Authelia cookie is sent with credentials.

## Components

### `services/authelia/`

New per-service directory mirroring the per-service-isolation pattern.

```
services/authelia/
├── Dockerfile              # FROM authelia/authelia:<pinned>
├── build.sh                # builds + pushes to GHCR (matches siteapp/flasher pattern)
├── config/
│   └── configuration.yml.tmpl
├── README.md
└── tests/
    └── e2e/
        ├── conftest.py              # spin up authelia with fixture users + config
        ├── test_firstfactor.py      # POST /api/firstfactor → 200 + Set-Cookie
        ├── test_forward_auth.py     # /api/verify with valid session → 200 + Remote-User
        ├── test_oidc_discovery.py   # /.well-known/openid-configuration shape
        └── test_group_gating.py     # researcher cannot pass admins-only verify
```

`configuration.yml.tmpl` highlights (file-backend; SQLite for storage; 1FA only;
remember-me 90 days):

```yaml
theme: light
default_redirection_url: https://__VPS_HOST__/

authentication_backend:
  password_reset:
    disable: true
  refresh_interval: 30s
  file:
    path: /config/users_database.yml
    password:
      algorithm: argon2id

access_control:
  default_policy: deny
  rules:
    - domain: __VPS_HOST__
      resources: ['^/flash.*']
      policy: one_factor
      subject: 'group:admins'
    - domain: __VPS_HOST__
      resources: ['^/jupyter.*']
      policy: one_factor
      subject: ['group:admins', 'group:researchers']
    - domain: __VPS_HOST__
      resources: ['^/grafana/.*']
      policy: one_factor
      subject: ['group:admins', 'group:researchers']

session:
  name: authelia_session
  domain: __VPS_HOST__
  expiration: 1h
  inactivity: 5m
  remember_me_duration: 2160h    # 90 days

storage:
  local:
    path: /data/db.sqlite3

identity_providers:
  oidc:
    clients:
      - id: grafana
        secret: '__GRAFANA_OIDC_SECRET_HASH__'   # PBKDF2-hashed
        redirect_uris:
          - https://__VPS_HOST__/grafana/login/generic_oauth
        scopes: [openid, profile, email, groups]
        grant_types: [authorization_code, refresh_token]
        response_types: [code]
```

`users_database.yml` (gitignored, laptop-rendered, rsynced to the VPS at
deploy):

```yaml
users:
  alice:
    displayname: "Alice"
    password: "$argon2id$v=19$..."
    email: alice@lab.example
    groups: [admins]
  bob:
    displayname: "Bob"
    password: "$argon2id$v=19$..."
    email: bob@lab.example
    groups: [researchers]
```

### `.github/workflows/pr-authelia.yml`

- Triggers on `pull_request` (no workflow-level `paths`).
- Internal `dorny/paths-filter@v3` gate on `services/authelia/**`,
  `compose/Caddyfile.tmpl`, and `compose/docker-compose.yml.tmpl`.
- Builds image, runs `tests/e2e/`, pushes to
  `ghcr.io/bioexperiment-lab-devices/lab-bridge-authelia:${{ github.sha }}` on
  PRs, Sigstore-attests on release-please tag pushes.
- Final aggregator job named `authelia` — required-check name is
  `pr-authelia / authelia`. Branch protection updated in lockstep using the
  `verify`-stub transitional pattern from CLAUDE.md.

### `compose/Caddyfile.tmpl`

Diff against current (sketch — final syntax verified in
`tests/integration/test_auth_smoke.bats`):

```caddyfile
# ─── Authelia (public for OIDC discovery + redirects) ───────────────
handle /auth/* {
    reverse_proxy authelia:9091
}

# ─── forward_auth snippet, reused by /flash* and /jupyter* ──────────
(authelia_required) {
    forward_auth authelia:9091 {
        uri /api/verify?rd=https://__VPS_HOST__/login
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email
    }
}

# ─── Flasher (basic_auth removed) ───────────────────────────────────
handle /flash/api/v1/* { reverse_proxy flasher:8000 }
handle /flash* {
    import authelia_required
    reverse_proxy flasher:8000
}

# ─── Jupyter (shared password removed) ──────────────────────────────
handle /jupyter* {
    import authelia_required
    header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
    header Content-Security-Policy "(style-src[^;]*)"  "${1} 'self'"
    reverse_proxy jupyter:8888
}

# ─── Grafana — Caddy layer unchanged; OIDC handled inside Grafana ───
handle /grafana/* {
    header Content-Security-Policy "(script-src[^;]*)" "${1} 'self'"
    header Content-Security-Policy "(style-src[^;]*)"  "${1} 'self'"
    reverse_proxy grafana:3000
}

# ─── Login + auth API + error pages (siteapp templates) ─────────────
handle /login   { reverse_proxy siteapp:8000 }
handle /logout  { reverse_proxy siteapp:8000 }
handle /api/auth/* { reverse_proxy siteapp:8000 }

handle_errors {
    @403 expression {http.error.status_code} == 403
    @404 expression {http.error.status_code} == 404
    rewrite @403 /_errors/403
    rewrite @404 /_errors/404
    reverse_proxy @403 siteapp:8000
    reverse_proxy @404 siteapp:8000
}
```

Notes:
- `forward_auth`'s `rd=…/login` makes Caddy return 302 to `/login?rd=<original>`
  on 401, so anonymous users always land on our custom form instead of
  Authelia's portal.
- The previous `basic_auth { admin __ADMIN_BCRYPT_HASH__ }` block on
  `/flash*` is removed. The `__ADMIN_BCRYPT_HASH__` substitution in
  `scripts/lib/render.sh::render_caddyfile` is also removed.
- The corresponding `task secrets:set-admin-password` command is removed in
  favor of `task users:set-password` against an `admins`-group user.

### `compose/docker-compose.yml.tmpl`

Additions and edits (diff sketch):

```yaml
authelia:
  image: __AUTHELIA_IMAGE__
  restart: unless-stopped
  volumes:
    - ./authelia/configuration.yml:/config/configuration.yml:ro
    - ./authelia/users_database.yml:/config/users_database.yml:ro
    - ./authelia_data:/data
  secrets:
    - authelia_jwt_secret
    - authelia_session_secret
    - authelia_storage_encryption_key
    - authelia_oidc_hmac_secret
    - authelia_oidc_jwks_key
  environment:
    AUTHELIA_JWT_SECRET_FILE: /run/secrets/authelia_jwt_secret
    AUTHELIA_SESSION_SECRET_FILE: /run/secrets/authelia_session_secret
    AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE: /run/secrets/authelia_storage_encryption_key
    AUTHELIA_IDENTITY_PROVIDERS_OIDC_HMAC_SECRET_FILE: /run/secrets/authelia_oidc_hmac_secret
    AUTHELIA_IDENTITY_PROVIDERS_OIDC_ISSUER_PRIVATE_KEY_FILE: /run/secrets/authelia_oidc_jwks_key
  networks: [labnet]

jupyter:
  # command: remove --ServerApp.token= and --ServerApp.password=… lines.
  # Auth lives at the Caddy edge only.
  command:
    - start-notebook.sh
    - --ServerApp.token=
    - --ServerApp.password=
    - --ServerApp.allow_origin=*
    - --ServerApp.base_url=/jupyter
    - --ServerApp.root_dir=/home/jovyan/work
    - --ServerApp.disable_check_xsrf=true

grafana:
  environment:
    # existing keys unchanged
    GF_AUTH_GENERIC_OAUTH_ENABLED: "true"
    GF_AUTH_GENERIC_OAUTH_NAME: Authelia
    GF_AUTH_GENERIC_OAUTH_CLIENT_ID: grafana
    GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET__FILE: /run/secrets/grafana_oidc_secret
    GF_AUTH_GENERIC_OAUTH_SCOPES: "openid profile email groups"
    GF_AUTH_GENERIC_OAUTH_AUTH_URL: https://__VPS_HOST__/auth/api/oidc/authorization
    GF_AUTH_GENERIC_OAUTH_TOKEN_URL: https://__VPS_HOST__/auth/api/oidc/token
    GF_AUTH_GENERIC_OAUTH_API_URL: https://__VPS_HOST__/auth/api/oidc/userinfo
    GF_AUTH_GENERIC_OAUTH_USE_PKCE: "true"
    GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH: "contains(groups[*], 'admins') && 'Admin' || contains(groups[*], 'researchers') && 'Viewer'"
    GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN: "true"
    GF_AUTH_DISABLE_LOGIN_FORM: "true"
  secrets:
    - grafana_admin_password
    - grafana_oidc_secret

secrets:
  # ...existing secrets...
  authelia_jwt_secret:
    file: ./authelia/secrets/jwt_secret
  authelia_session_secret:
    file: ./authelia/secrets/session_secret
  authelia_storage_encryption_key:
    file: ./authelia/secrets/storage_encryption_key
  authelia_oidc_hmac_secret:
    file: ./authelia/secrets/oidc_hmac_secret
  authelia_oidc_jwks_key:
    file: ./authelia/secrets/oidc_jwks_key.pem
  grafana_oidc_secret:
    file: ./grafana/oidc_secret
```

Notes:
- `GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN=true` + `GF_AUTH_DISABLE_LOGIN_FORM=true`
  means hitting `/grafana/` immediately bounces through Authelia — no Grafana
  built-in login form is shown to end users.
- The Grafana local admin password stays as a break-glass fallback (Grafana
  always keeps a built-in admin even with OAuth configured). Documented in the
  README addendum.
- JupyterLab's `disable_check_xsrf=true` is set because cross-origin auth is
  now handled at the edge; without this the notebook's own XSRF check rejects
  edge-authenticated requests that don't carry its in-app token.

### `compose/pins.yaml`

```yaml
# Authelia identity provider. Renovate-managed.
authelia_image: authelia/authelia:4.38.10
```

(Specific version pinned at implementation time; the e2e suite catches
regressions on Renovate bumps.)

### `scripts/lib/render.sh` extensions

- New `_authelia_image` mirroring `_siteapp_image` / `_flasher_image`.
- `render_compose` adds substitution `-e "s|__AUTHELIA_IMAGE__|${authelia_image}|g"`.
- `render_caddyfile` removes the `__ADMIN_BCRYPT_HASH__` substitution (no
  longer used) and adds nothing new (Caddyfile no longer references any
  user-managed secret directly).
- New `render_authelia_config` renders `services/authelia/config/configuration.yml.tmpl`
  → `compose/authelia/configuration.yml` with `__VPS_HOST__` and
  `__GRAFANA_OIDC_SECRET_HASH__` substitutions.

### `scripts/deploy.sh` extensions

- Renders `compose/authelia/configuration.yml` from the template (above).
- rsyncs `compose/authelia/` and `compose/grafana/oidc_secret` to the VPS
  alongside existing artifacts. **Excludes** `users_database.yml` from CI
  rsync the same way `chisel/users.json` and `siteapp/clients.json` are
  excluded (laptop-only). The vault guard pattern from `compose/config.ci.yaml.tmpl`
  applies: CI deploys must not render or push a populated user database.

### siteapp additions

New file `services/siteapp/app/routes/auth.py`:

- `GET /login` — renders `templates/login.html`. Accepts `?rd=<path>` (URL-
  encoded). The template includes:
  - username + password fields
  - "Remember me" checkbox (default checked)
  - error message slot
  - submit posts to `/api/auth/firstfactor` via fetch with JSON
- `POST /api/auth/firstfactor` — request body `{username, password, targetURL,
  keepMeLoggedIn}`. Server-side POSTs to `http://authelia:9091/api/firstfactor`
  with `Cookie:` header forwarded from the inbound request and Authelia's
  `X-Forwarded-Method` / `X-Forwarded-Uri` / `X-Forwarded-Proto` /
  `X-Forwarded-Host` headers set to the original request context. Pipes back
  the `Set-Cookie` header. Returns JSON `{redirect: targetURL}` on 200, JSON
  `{error: "..."}` with appropriate status on 401/429/etc.
- `GET /api/auth/whoami` — calls `authelia:9091/api/verify` with the inbound
  `Cookie:` header. Returns `{user: <username>, groups: [...], display_name,
  email}` on 200, `{user: null}` on 401/403, `{user: null}` on connect-error
  (degrade gracefully so the navbar still loads when Authelia is down).
- `GET /logout` — calls `authelia:9091/api/logout`, pipes back the cookie-
  expiring `Set-Cookie`, returns 302 to `/`.
- `GET /_errors/403` — renders `templates/error_403.html`.
- `GET /_errors/404` — renders `templates/error_404.html`.

New templates (extend `base.html`):
- `templates/login.html`
- `templates/error_403.html`
- `templates/error_404.html`

### `compose/shell/navbar.js` additions

Boot extension immediately after the existing mount step:

```js
async function renderAuthSlot() {
  const slot = root.querySelector('.auth-slot');
  try {
    const r = await fetch('/api/auth/whoami', { credentials: 'include' });
    const data = await r.json();
    if (data.user) {
      slot.innerHTML = `<a class="avatar" href="/logout" aria-label="Logout ${escapeHtml(data.user)}">${data.user[0].toUpperCase()}</a>`;
    } else {
      const rd = encodeURIComponent(location.pathname + location.search);
      slot.innerHTML = `<a class="login-btn" href="/login?rd=${rd}">Login</a>`;
    }
  } catch {
    // Network error — treat as logged out, no surprises.
    slot.innerHTML = `<a class="login-btn" href="/login">Login</a>`;
  }
}
```

The `.auth-slot` lives at the bottom of the rail's `<nav>` in both render
modes (persistent and bookmark). Styling is intentionally minimal — colors and
spacing are placeholders the user will style later.

### Task automation — `task users:*`

New top-level task group in `Taskfile.yml`, backed by `scripts/users.sh`
(mirrors `secrets.sh` shape):

```
task users:add USER              # prompts for password + group (admins|researchers)
task users:rm USER
task users:set-password USER     # prompts for new password
task users:set-groups USER       # prompts for new comma-separated group list
task users:list                  # prints users.yml in a table
```

Implementation notes:
- Argon2id hashing via the Authelia CLI: `docker run --rm -i
  authelia/authelia:<pin> authelia hash-password --no-confirm`. Pin matches
  the running container's pin (read from `compose/pins.yaml`).
- Group validation: only `admins` and `researchers` accepted; anything else
  is a hard error from the task.
- File location: `compose/authelia/users_database.yml`, gitignored.
- File is created on first `task users:add` if missing.
- After every mutation, the task prints a "next: task deploy" hint. Authelia's
  file backend reloads on its own (`authentication_backend.refresh_interval`
  defaults to 5 minutes; we set it to `30s` in the config), so a full deploy
  is only needed for schema-changing edits.

### Authelia secrets bootstrap — `task secrets:bootstrap-authelia`

One-shot command, idempotent, refuses to overwrite without `--rotate`:

- Generates 64-byte hex random values for:
  - `compose/authelia/secrets/jwt_secret`
  - `compose/authelia/secrets/session_secret`
  - `compose/authelia/secrets/storage_encryption_key`
  - `compose/authelia/secrets/oidc_hmac_secret`
- Generates a 4096-bit RSA private key for
  `compose/authelia/secrets/oidc_jwks_key.pem` (used by Authelia to sign
  OIDC tokens).
- Generates a 32-byte URL-safe random for `compose/grafana/oidc_secret`
  (raw secret used by Grafana). Computes PBKDF2 hash via `docker run --rm
  authelia/authelia:<pin> authelia crypto hash generate pbkdf2 --random …`
  and writes it to `config.yaml` under `authelia.grafana_oidc_secret_hash`
  for substitution into `configuration.yml.tmpl`.
- All files chmod 600.
- GH-secret mirror: none required — Authelia is never bootstrapped from CI.
  The roster + secrets are laptop-only, mirroring the chisel pattern.

### Branch-protection lockstep

Add `pr-authelia / authelia` as a required check. Use the `verify`-stub
transitional pattern from CLAUDE.md if there's a window where the workflow
exists but the check is not yet required.

## Data flow

### First-time login (Flasher / Jupyter — forward_auth path)

```
1. browser GET /flash
2. Caddy → forward_auth ► authelia:9091/api/verify?rd=…/login
3. Authelia: no cookie → 401
4. Caddy redirects: 302 → /login?rd=/flash
5. browser GET /login?rd=/flash → siteapp renders login.html
6. browser POST /api/auth/firstfactor {username, password, targetURL:/flash,
   keepMeLoggedIn:true}
7. siteapp → POST authelia:9091/api/firstfactor (server-to-server)
8. Authelia: validates, returns 200 + Set-Cookie authelia_session=…
9. siteapp pipes Set-Cookie back; returns JSON {redirect:/flash}
10. browser GET /flash (now has cookie)
11. Caddy → forward_auth ► authelia:9091/api/verify
12. Authelia: cookie valid, group=admins → 200 + headers Remote-User,
    Remote-Groups, Remote-Name, Remote-Email
13. Caddy proxies to flasher:8000 with those headers
```

### Grafana OIDC login

```
1. browser GET /grafana/  → GF_AUTH_GENERIC_OAUTH_AUTO_LOGIN bounces to
   /grafana/login/generic_oauth
2. Grafana redirects to https://<host>/auth/api/oidc/authorization?…
3. Authelia: no session → 302 to https://<host>/login?rd=/auth/api/oidc/authorization?…
4. Same custom login form as above
5. After login, Authelia returns to /auth/api/oidc/authorization, issues code
6. Grafana exchanges code, gets ID token with groups claim
7. role_attribute_path maps: admins→Admin, researchers→Viewer
8. Grafana auto-provisions user (auto-create on first login)
```

### `whoami` from a third-party app's page

navbar.js fetches `/api/auth/whoami` from any page (cross-handle, same domain;
cookies sent with `credentials: 'include'`). siteapp resolves it independent
of which upstream rendered the page — so the avatar shows correctly on Jupyter
and Grafana too.

### Logout

```
1. browser GET /logout
2. siteapp calls authelia:9091/api/logout (forwards cookie)
3. Authelia clears server-side session, returns Set-Cookie expiring authelia_session
4. siteapp pipes that Set-Cookie back, 302 → /
```

### 403 / 404 flow

```
1. browser GET /something-that-doesnt-exist
2. Caddy: no matching handle → default 404
3. handle_errors block matches → rewrite to /_errors/404 → reverse_proxy siteapp:8000
4. siteapp renders error_404.html (extends base.html, navbar present)
```

403 (researcher hits /flash):

```
1. browser GET /flash, session active, group=researchers
2. forward_auth /api/verify → 403 (admins-only rule denies)
3. Caddy handle_errors → /_errors/403 → siteapp
```

Authelia returns 403 (not redirect-to-login) for authenticated-but-forbidden
requests, so we get correct forbidden semantics rather than a login loop.

## Error handling & failure modes

- **Authelia down.** All gated routes return 502 from Caddy's forward_auth →
  falls into `handle_errors` (extended to also catch 502 → a generic
  "service unavailable" rendered by siteapp at `/_errors/503` if we add it,
  otherwise it falls through to `/_errors/404`). Siteapp public routes still
  work. `whoami` returns `{user: null}` rather than 500 if Authelia is
  unreachable — degrades gracefully (navbar shows the "Login" button).
- **siteapp down.** No login form, no avatar, no error pages — Caddy serves
  its raw default error. Acceptable degradation; everything else is broken
  anyway in this case.
- **Stale cookie after `task users:rm`.** Authelia's file backend rejects
  unknown users on the next `/api/verify` call → 401 → user gets bounced to
  `/login`. Removed users lose access on their next request — no manual
  session invalidation required.
- **Group change while user has active session.** Authelia re-reads the file
  on each verify (file backend with 30 s refresh interval), so
  `task users:set-groups` takes effect on next request without restart.
  The "next: task deploy" hint is informational, not strictly required for
  group edits.
- **OIDC issuer key rotation.** Out of scope for v1 — manual: rotate the
  JWKS private key, restart Authelia, all Grafana sessions invalidate on
  next refresh.
- **Forgotten password.** Authelia's password reset flow requires SMTP —
  explicitly disabled (`password_reset.disable: true`). Recovery path:
  `task users:set-password <user>` resets it; admin tells the user
  out-of-band. Documented in `docs/adding-a-user.md`.
- **Race: navbar boots before whoami resolves.** Auth slot renders empty
  briefly, then fills in. Acceptable — the navbar itself doesn't depend on
  auth state for its primary navigation.

## Testing

Three tiers per CLAUDE.md.

### Unit

None specifically. `scripts/users.sh` is exercised by the bats integration
suite (see below); it has the same surface as `secrets.sh`.

### Service-level e2e

- `services/authelia/tests/e2e/`:
  - `test_firstfactor.py` — POST `/api/firstfactor` against a real container
    with a seeded users file returns 200 + `Set-Cookie`.
  - `test_forward_auth.py` — `/api/verify` with a valid session returns 200
    and the expected `Remote-User` / `Remote-Groups` headers; without cookie
    returns 401.
  - `test_oidc_discovery.py` — `/.well-known/openid-configuration` shape is
    correct; JWKS endpoint serves the configured key.
  - `test_group_gating.py` — a researcher's cookie fails `/api/verify` on a
    `/flash*` URL but passes on `/jupyter*`.
- `services/siteapp/tests/e2e/`:
  - `test_login_flow.py` — full first-factor through `/api/auth/firstfactor`
    against a real Authelia container with a seeded users file. Asserts
    `Set-Cookie` propagation and that the JSON response carries `targetURL`.
  - `test_whoami.py` — anonymous returns `{user: null}`; authenticated
    returns `{user, groups}`; Authelia-down returns `{user: null}` and HTTP 200
    (degraded mode).
  - `test_error_pages.py` — `/_errors/403` and `/_errors/404` render
    templates that include the `<script src="/_shared/navbar.js"` injection
    marker (navbar present).
  - `test_logout.py` — `/logout` sends an expiring cookie and 302s to `/`.

### Platform integration (bats)

New matrix cell `auth` in `pr-platform.yml`:

- `tests/integration/test_auth_smoke.bats`:
  1. Anonymous `GET /flash` → 302 to `/login?rd=/flash`.
  2. Anonymous `GET /jupyter/` → 302 to `/login?rd=/jupyter/`.
  3. Anonymous `GET /grafana/` → 302 through Authelia → 302 to `/login`.
  4. Login flow end-to-end: POST `/api/auth/firstfactor` as admin → cookie
     → GET `/flash` returns 200.
  5. researcher GET `/flash` returns 403 → response body is the
     `/_errors/403` HTML (navbar marker present).
  6. Logout clears the cookie (next GET `/flash` re-redirects to `/login`).
  7. `GET /api/auth/whoami` reflects session state on any handle (siteapp,
     flasher, grafana, jupyter).
  8. `task users:add` / `rm` / `set-password` / `set-groups` round-trip
     works against a fake-VPS bring-up.

Mirrors the `compose_images_available` skip pattern from
`test_routes_smoke.bats:11-14`.

## Release & ops

- **Single PR, single squash-merge.** Touches the new Authelia service,
  Caddyfile, compose template, Grafana env, Jupyter command-line, siteapp
  routes + templates, navbar.js, tasks, and branch-protection. Atomic.
- **Conventional Commit title:** `feat(platform): unified Authelia auth with
  groups and custom login` → minor bump under release-please.
- **Branch protection lockstep:** add `pr-authelia / authelia` as required
  check using the `verify`-stub transitional pattern.
- **Migration on the running VPS:**
  1. `task secrets:bootstrap-authelia` (laptop, once).
  2. `task users:add <name>` for each existing user (replaces shared Jupyter
     password, shared Flasher basic_auth, Grafana admin login for end users).
  3. `task deploy`.
  4. The deprecated config keys `siteapp.admin_password_hash` and
     `jupyter.password_hash` are read but ignored during the deploy that
     follows; they are removed from `config.example.yaml` and from
     `render.sh` substitutions in the next release.
  5. Grafana local admin account stays bootable as a break-glass path.
- **Renovate:** picks up the new `authelia_image` pin in `compose/pins.yaml`
  like every other image.

## Risks and mitigations

1. **Authelia's first-factor API surface and `forward_auth` semantics are
   the integration contract.** Verify against the pinned Authelia version's
   docs; e2e tests are authoritative. Renovate bumps re-run the suite.
2. **Forward_auth + multiple proxy hops can drop `Set-Cookie` if Caddy is
   misconfigured.** The e2e test_login_flow asserts cookie propagation
   end-to-end. The siteapp `/api/auth/firstfactor` handler explicitly
   forwards the `Set-Cookie` header from Authelia's response.
3. **Grafana's OIDC role mapping uses JMESPath; syntax drift across Grafana
   versions has happened in the past.** Pin Grafana via `compose/pins.yaml`;
   the auth bats suite verifies admin/viewer role assignment end-to-end on
   each release.
4. **JupyterLab's edge-only auth means the `jovyan` workspace is shared
   across all logged-in users.** Documented; per-user isolation is a future
   JupyterHub migration.
5. **`/auth/*` exposed publicly is a new attack surface.** Authelia's API
   has rate-limiting on `/api/firstfactor`; default settings (3 attempts per
   2 minutes, then ban) are kept. Rate-limit and ban events show up in
   Authelia's stdout → Loki.
6. **Loss of bootstrap admin password.** Recovery: edit
   `compose/authelia/users_database.yml` by hand and replace the password
   hash with one generated by `docker run --rm -i authelia/authelia:<pin>
   authelia hash-password`. Documented in the README addendum.
7. **Cookie domain mismatch.** Authelia's `session.domain` must exactly
   match the Host header the browser sends. The deploy renders
   `__VPS_HOST__` into both Caddy and Authelia configs from the same
   `config.yaml:vps.host` field, so they cannot diverge.
8. **OIDC client secret rotation breaks Grafana mid-session.** Acceptable —
   `task secrets:bootstrap-authelia --rotate` is an explicit, infrequent
   operation; documented as requiring `task deploy` and a restart of
   Grafana.

## Out of scope (non-goals)

- 2FA / TOTP (1FA only).
- LDAP / external user directory (file backend only).
- Bearer-token issuance (managed by hand via existing
  `task secrets:rotate-*-token` commands).
- Per-user JupyterLab workspaces (shared `jovyan` workspace — the
  forward_auth trade-off).
- Per-dashboard Grafana permissions beyond the org-role mapping.
- SMTP / password reset / email-based flows.
- Authelia exposed at a subdomain (path-prefix only, `/auth/*`).
- Self-service user signup.
- Audit log / login history UI.
- Custom-themed Authelia portal (not used; siteapp owns login UI).

## References

- `docs/superpowers/specs/2026-05-15-per-service-isolation-design.md` — the
  per-service split that `services/authelia/` follows.
- `docs/superpowers/specs/2026-05-17-shared-navbar-design.md` — navbar host
  + render modes; auth slot lives in the rail.
- `docs/superpowers/specs/2026-05-17-unified-release-design.md` — the
  unified release flow that pins and ships the new image.
- `docs/adding-a-service.md` — checklist mirrored when adding
  `services/authelia/`.
- `CLAUDE.md` — invariants: per-service isolation, single VERSION, three-
  tier testing, branch-protection lockstep, laptop-vs-CI surface split.

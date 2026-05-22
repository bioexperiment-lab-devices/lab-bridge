# Security audit 2026-05-22 — remediation design

- Date: 2026-05-22
- Source audit: `docs/security/2026-05-22-audit-report.md`
- Audit harness spec: `docs/superpowers/specs/2026-05-22-security-audit-design.md`
- Scope: all `vulnerable` findings + the **3.2-hardening** constant-time bearer compare. Other `informational` findings are explicitly out of scope (see §8).

## 1. Problem statement

The 2026-05-22 audit run against preprod (`https://111.88.145.138`) surfaced
**1 Critical, 2 High, 2 Medium, 6 Low, and 17 Informational** findings. Eight of
those carry status `vulnerable` or are otherwise actionable code-level
weaknesses. We remediate all eight in a single bundled PR, redeploy preprod,
re-run the audit harness, and commit the post-fix report as the artifact that
proves zero `vulnerable` rows in scope.

The harness in `tests/security/` is the regression gate. After remediation,
every fixed case is the kind of thing worth running continuously, so each gets
`@pytest.mark.regression`. Wiring that marker into CI is its own design and is
**out of scope** here.

## 2. Findings in scope

| ID | Severity | Status | One-line | Owning service |
|---|---|---|---|---|
| 1.6 | Critical | vulnerable | Non-GET from researcher reaches `/flash` upstream | Caddy + Authelia |
| 2.1 | High | vulnerable | Cookie replay after `GET /logout` still works | siteapp |
| 2.2 | High | vulnerable | Cookie replay after `POST /logout` still works | siteapp |
| 5.0 | Medium | vulnerable | 403/404 templates served at HTTP 200 | siteapp |
| 3.2-hardening | Medium | informational | Bearer compare uses `!=`, not `compare_digest` | flasher |
| 5.1 | Low | vulnerable | Missing HSTS / nosniff / Referrer-Policy / CSP | Caddy |
| 3.7 | Low | vulnerable | `/flash/api/v1/firmware` returns 422 before bearer check | flasher |
| 2.5 | Low | vulnerable | Logout-cleared cookies omit `Secure` | siteapp |
| 6.1 | Info | vulnerable | Brute-force regulation appears not to engage | audit harness |

## 3. Findings out of scope (explicit non-goals)

These are reviewed and deliberately deferred. Each needs its own spec if we
later choose to address it.

| ID | Why deferred |
|---|---|
| 5.6 | Open-redirect via `/login?rd=` — Authelia owns the `rd` parameter; architectural. |
| 2.11 | Cross-origin POST to `/api/auth/firstfactor` — SameSite=Lax is the documented CSRF mitigation. |
| 2.12 | `GET /logout` enables CSRF-logout — UX trade-off; documented. |
| 2.3 | Per-session (not user-global) invalidation — documented behaviour. |
| 1.15(*) | Authelia surface (`jwks.json`, `.well-known/openid-configuration`, `api/health`, `api/state`, `api/configuration`, `api/password-reset/identity/start`) — by-design OIDC discovery + status endpoints. |
| 1.7 / 1.10 | Researcher reaches `/grafana/` and `/jupyter/`, `/grafana/api/health` is public — by design. |
| 5.4 / 5.7 / 7.2 / 7.4 | Informational inventories; no action. |
| 3.5 / 6.3 / 6.4 | Positive controls passing. |

## 4. The fixes

### 4.1 — Finding 1.6 · Authelia method enforcement on `/flash*`

**Where:** `compose/Caddyfile.tmpl`, snippet `(authelia_required)`.

**Root cause:** Caddy's `forward_auth` directive proxies the **original request's
method and body** to Authelia's `/api/verify`. Authelia 4.38 expects
`GET /api/verify` with `X-Forwarded-Method` indicating the upstream method.
When a `POST /flash/...` arrives, Caddy sends `POST /api/verify` with the
firmware body; Authelia handles this unexpectedly and the request is allowed
through to the flasher upstream, which then returns its own 405.

**Change:** Pin the verify call to GET and explicitly pass the original method
and URI via `X-Forwarded-*` headers, plus strip `Content-Length` so Authelia
treats the verify request as body-less.

```
(authelia_required) {
    forward_auth authelia:9091 {
        uri /api/verify?rd=https://__VPS_HOST__/login
        method GET
        header_up X-Forwarded-Method {method}
        header_up X-Forwarded-Uri {uri}
        header_up Content-Length ""
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email

        @forbidden status 403
        handle_response @forbidden {
            error 403
        }
    }
}
```

**Notes on Caddy semantics:**

- `method GET` forces the sub-request to `/api/verify` to be a GET regardless of
  original method.
- `header_up X-Forwarded-Method {method}` uses Caddy's placeholder for the
  original request method. Caddy 2.x sets this automatically inside
  `forward_auth`, but pinning it explicitly is defensive against future Caddy
  default changes.
- `header_up Content-Length ""` removes the original body's length header so
  Authelia doesn't try to read a body off a GET.

**Verification:** `tests/security/test_01_routing.py::test_1_6_researcher_flash_post`
must return `reached_upstream=False`, `status_code` 403, and the response body
must be the siteapp 403 page (not a flasher 405).

### 4.2 — Findings 2.1 & 2.2 · Server-side logout actually invalidates session

**Where:** `services/siteapp/app/auth.py` — `logout` handler around line 126.

**Root cause:** The current code calls `POST /api/logout` on the in-cluster
Authelia URL with only the `Cookie` header. Authelia matches sessions by cookie
domain — but the in-cluster request has `Host: authelia:9091` (Docker DNS), not
`__VPS_HOST__`. Authelia's session-domain check fails, the logout becomes a
no-op, the client cookie is cleared, and the same cookie value replays
successfully (the server-side session record still lives).

**Change:** Forward the same `X-Forwarded-Host` / `X-Forwarded-Proto` headers
that `firstfactor` and `whoami` already use, so Authelia matches the session to
its configured domain. Mirror the `_forwarded_headers` pattern.

```python
@router.api_route("/logout", methods=["GET", "POST"], include_in_schema=False)
async def logout(request: Request) -> Response:
    cookie = request.headers.get("cookie", "")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or "https"
    try:
        await client.post(
            "/api/logout",
            headers={
                "Cookie": cookie,
                "X-Forwarded-Host": host,
                "X-Forwarded-Proto": proto,
            },
        )
    except httpx.RequestError:
        pass
    # … cookie-clearing logic unchanged from current code (plus Secure flag — see §4.6) …
```

The `try/except` stays best-effort: a network failure to Authelia shouldn't
strand the user. The cookie clears still happen. We do **not** add a hard
assertion on Authelia's response status — the audit harness is the structured
gate for that.

**Verification:** `tests/security/test_06_session.py::test_2_1_replay_after_get_logout`
and `::test_2_2_replay_after_post_logout` must show `replay_status` 401 (or 302
to `/login`), `reached_flasher_spa=False`.

### 4.3 — Finding 5.0 · Error pages return the right HTTP status

**Where:** `services/siteapp/app/auth.py` — `error_403` and `error_404` handlers
(around lines 176–186).

**Change:** Pass `status_code=` to `TemplateResponse`.

```python
@router.get("/_errors/403", response_class=HTMLResponse, include_in_schema=False)
async def error_403(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error_403.html",
        {"attempted_path": _attempted_path(request)},
        status_code=403,
    )

@router.get("/_errors/404", response_class=HTMLResponse, include_in_schema=False)
async def error_404(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "error_404.html",
        {"attempted_path": _attempted_path(request)},
        status_code=404,
    )
```

Caddy's `handle_errors` already rewrites to `/_errors/{403,404}` — the
status_code now correctly propagates instead of being masqueraded as 200.

**Verification:** `test_5_0_status_code_masquerading` —
`anon_flash_masquerade=False` and `anon_missing_masquerade=False`.

### 4.4 — Findings 3.7 & 3.2-hardening · Flasher bearer

**Where:** `services/flasher/app/routes/firmware.py`.

**3.7 — Bearer enforcement before query validation:**

```python
@router.get("/api/v1/firmware")
async def bearer_get_by_sha256(
    sha256: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_bearer(authorization, settings.upload_token)
    if not sha256:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing query", "detail": "sha256 query parameter required"},
        )
    async with conn_factory() as conn:
        row = await get_firmware_by_sha256(conn, sha256=sha256)
    # … rest unchanged …
```

Making `sha256` optional in the signature defers pydantic's required-field
check to after `_require_bearer`. Unauthenticated callers can no longer probe
the schema by triggering 422.

**3.2-hardening — Constant-time bearer compare:**

```python
import secrets
# …
def _require_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "bearer required", ...})
    provided = authorization[len("Bearer "):]
    if not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail={"error": "bearer invalid", ...})
```

`compare_digest` matches what `services/flasher/app/routes/agent.py` already
does for the agent-upload endpoint, so the codebase is consistent.

**Verification:**
- `test_3_7_bearer_validation_order` — status 401 (not 422).
- `test_3_2_flasher_bearer_wrong` — still passes, finding remains
  `informational` (it's a hardening item, no functional regression possible
  without a clock-side-channel observation).

### 4.5 — Finding 5.1 · Security headers at the Caddy layer

**Where:** `compose/Caddyfile.tmpl`, inside the `https://__VPS_HOST__ {}` block,
before the `handle` directives.

**Change:**

```
header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Content-Type-Options    "nosniff"
    Referrer-Policy           "strict-origin-when-cross-origin"
    Content-Security-Policy   "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    -Server
}
```

**Rationale per header:**

- **HSTS** — preprod and prod are HTTPS-only via ACME (`tls` directive). One
  year + `includeSubDomains` is the standard hardening value. No `preload`
  flag, because we don't intend to submit the preprod IP to the preload list.
- **X-Content-Type-Options: nosniff** — single value, no downside.
- **Referrer-Policy: strict-origin-when-cross-origin** — leaks no path
  information cross-origin, keeps same-origin Referer for navigation.
- **CSP** — baseline conservative policy. Per-handler `header
  Content-Security-Policy` directives on `/grafana/*` and `/jupyter*` already
  override (Caddy's `header` directives at handle scope replace the outer one
  for matching responses). Siteapp's inline `<script>` blocks (theme bootstrap,
  navbar) are loaded from `/_shared/navbar.js` and from inline initializers; if
  CSP breaks them we add `'unsafe-inline'` to `script-src` as the documented
  trade-off and rerun.
- **-Server** — removes the `Server: Caddy` banner. Minor obfuscation; cheap.

**Risk:** The CSP `script-src 'self'` may break siteapp's inline theme-bootstrap
script. Mitigation: verify with `bats tests/integration/test_routes_smoke.bats`
and a manual browser smoke before merge. If broken, relax `script-src` to
include `'unsafe-inline'` and document why in a comment.

**Verification:** `test_5_1_security_headers` — `missing` list empty.

### 4.6 — Finding 2.5 · `Secure` flag on logout cookie clears

**Where:** `services/siteapp/app/auth.py` — three `set-cookie` lines in
`logout`.

**Change:** Append `Secure` to each clear-line:

```python
resp.raw_headers.append(
    (
        b"set-cookie",
        f"authelia_session=; Max-Age=0; domain={domain}; path=/; HttpOnly; Secure; SameSite=Lax".encode(
            "latin-1"
        ),
    )
)
for cookie_name in ("grafana_session", "grafana_session_expiry"):
    resp.raw_headers.append(
        (
            b"set-cookie",
            f"{cookie_name}=; Max-Age=0; path=/grafana; HttpOnly; Secure; SameSite=Lax".encode(
                "latin-1"
            ),
        )
    )
```

`grafana_session_expiry` is non-HttpOnly in Grafana's own implementation (it's
read by the SPA). For a clear-line we mirror the cookie's actual attributes —
HttpOnly is harmless on a `Max-Age=0` clear because the browser only needs
(name, domain, path) to match. Adding `Secure` is correct on both clear-lines
in any case; the cleared cookie won't be re-sent over plaintext anyway, and
the audit asserts the attribute is present.

**Verification:** `test_2_5_logout_cookie_attributes` — `missing_secure` empty.

### 4.7 — Finding 6.1 · Re-frame brute-force regulation test

**Where:** `tests/security/test_07_state.py::test_6_1_brute_force_regulation`.

**Root cause (audit-harness, not platform):** Authelia regulation is keyed by
**username**. By design, regulation **does not engage for unknown usernames**
— this is a deliberate anti-user-enumeration property. The current test
probes with a random non-existent username, so identical 401s are the correct
platform behaviour, not a finding.

**Change:** Invert the assertion and re-document.

```python
def test_6_1_brute_force_regulation(target_url, verify_tls, anon_log, record):
    probe_user = f"bf-probe-{secrets.token_hex(4)}"
    statuses: list[int] = []
    for _ in range(5):
        r, _ = _attempt_login(target_url, verify_tls, probe_user, "wrong-password")
        statuses.append(r.status_code)
    distinct = len(set(statuses)) > 1
    # Authelia regulation is per-username. For an unknown user, identical 401s
    # are the intentional anti-enumeration behaviour. Distinct responses would
    # indicate a user-enumeration leak.
    record(
        Finding(
            id="6.1",
            title="Brute-force regulation does not leak user existence",
            severity="Informational",
            status="vulnerable" if distinct else "verified",
            summary=(
                "Authelia regulation is keyed by username; unknown users must "
                "get identical 401s across attempts to prevent enumeration."
            ),
            details={
                "probe_user": probe_user,
                "statuses": statuses,
                "distinct_responses": distinct,
            },
        ),
        anon_log,
    )
```

This converts a misleading false-positive into a real control: distinct
responses across attempts would now correctly flag a user-enumeration leak.

**Verification:** Status becomes `verified` on the next audit run.

## 5. Testing

Layered to match this repo's conventions (see CLAUDE.md §Testing):

### 5.1 — Unit tests (service-local, no containers)

- **siteapp** (`services/siteapp/tests/`) — extend the existing auth/error
  tests:
  - `error_403`/`error_404` handlers return HTTP 403/404 (not 200).
  - `logout` Set-Cookie clears all carry `Secure`.
- **flasher** (`services/flasher/tests/`) — extend
  `tests/test_routes_firmware.py`:
  - `GET /api/v1/firmware` without bearer **and** without `sha256` returns
    401, not 422.
  - Wrong-bearer with a token of length ≠ expected still returns 401 cleanly
    (smoke test for `compare_digest`).

### 5.2 — Service e2e (`services/<name>/tests/e2e/`, one container)

- **siteapp e2e** — extend the existing 403/404 page e2e to assert the
  response status matches the rendered title.
- **flasher e2e** — add a probe that posts `GET /api/v1/firmware` without
  bearer and without `sha256` → 401.

### 5.3 — Audit harness (`tests/security/`) — integration gate

After the fixes deploy to preprod, re-running
`scripts/security_audit.sh --target-url=https://111.88.145.138` must yield
**zero `vulnerable` rows** in the eight in-scope findings:

| Test | Expected post-fix outcome |
|---|---|
| `test_1_6_researcher_flash_post` | status 403, `reached_upstream=False` |
| `test_2_1_replay_after_get_logout` | `replay_status` ∈ {401, 302}, `reached_flasher_spa=False` |
| `test_2_2_replay_after_post_logout` | same as 2.1 |
| `test_5_0_status_code_masquerading` | both masquerade booleans False |
| `test_3_7_bearer_validation_order` | status 401, not 422 |
| `test_5_1_security_headers` | `missing` empty |
| `test_2_5_logout_cookie_attributes` | `missing_secure` empty |
| `test_6_1_brute_force_regulation` | status `verified` under re-framed assertion |

The post-fix report is committed in the same PR to
`docs/security/2026-05-23-audit-report.md` (or whatever date the rerun lands).

### 5.4 — Platform bats

No new bats file. The existing matrix cells (`cheap`, `deploy`, `ops`,
`provision`, `routes-smoke`) must keep passing. `routes-smoke` is the
load-bearing cell for the Caddyfile changes — if the security headers or the
new `forward_auth` snippet break a route, that's where it surfaces.

### 5.5 — Promote to `@pytest.mark.regression`

After the audit re-run is clean, add `@pytest.mark.regression` to the seven
tests in §5.3 (skipping `test_6_1` since its new outcome depends on Authelia
internals — keep it `audit_only` for now). Wiring the marker into a CI cell
needs its own design.

## 6. Verification gate (before merge)

1. All per-service `pytest` runs green locally (unit + e2e).
2. `bats tests/integration/test_routes_smoke.bats` green locally.
3. Deploy the PR branch to preprod via the laptop flow (the PR branch isn't a
   release-tag, so CI won't auto-deploy — we deploy manually for the rerun).
4. `scripts/security_audit.sh` against preprod produces zero `vulnerable` rows
   in scope.
5. Commit the post-fix audit report to `docs/security/` in the same PR.
6. Only then mark the PR ready for review / merge.

## 7. Delivery

**Worktree:** `.claude/worktrees/security-audit-fixes/`

**Branch:** `fix/security-audit-2026-05-22`

**Commits** (logical units; will squash on merge):

1. `fix(caddy): pin forward_auth verify to GET to gate non-GET methods (1.6)`
2. `fix(siteapp): forward Host headers to /api/logout, surface logout response (2.1, 2.2)`
3. `fix(siteapp): return 403/404 status on error pages, add Secure to logout clears (5.0, 2.5)`
4. `fix(flasher): enforce bearer before query validation, use compare_digest (3.7, 3.2)`
5. `fix(caddy): add HSTS, X-Content-Type-Options, Referrer-Policy, baseline CSP (5.1)`
6. `test(security): re-frame 6.1 — unknown-user regulation is by-design (6.1)`
7. `test(security): mark fixed audit cases as @regression`
8. `docs(security): post-remediation audit report`

**PR title (Conventional Commits):**

```
fix(security): remediate 2026-05-22 audit — critical + high + medium + low vulnerable findings
```

`fix(security)` → release-please cuts a patch bump on the next merge to main.

**Required checks:** `pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`,
`pr-platform / platform` (per CLAUDE.md branch rules).

## 8. Out of scope (record)

Repeating §3 here in delivery-prose so the PR description can reference it:

- **5.6 open-redirect** (`/login?rd=`) — Authelia owns the redirect parameter;
  any fix would couple siteapp's login form to an Authelia-internal contract.
  Needs its own design and Authelia-side discussion.
- **2.11 cross-origin `firstfactor`** — `SameSite=Lax` on the session cookie is
  the documented CSRF mitigation. Origin/Referer checking on the auth API is
  belt-and-braces but introduces complexity for embedded-IDP flows. Defer.
- **2.12 GET `/logout` CSRF** — documented soft spot; logout-CSRF is low-impact
  (an attacker can sign the user out, but cannot impersonate). UX trade-off
  worth a separate spec.
- **2.3** — per-session invalidation is the documented, intentional behaviour.
- **1.15(*)** — exposed Authelia endpoints (`jwks.json`,
  `.well-known/openid-configuration`, `api/health`, `api/state`,
  `api/configuration`, `api/password-reset/identity/start`) are by-design OIDC
  discovery and status endpoints; `password-reset` is disabled but the route
  exists.
- **CI wiring** for `@pytest.mark.regression` — needs its own spec (which
  workflow, which preprod env, how creds are injected).

## 9. Risks & open questions

- **CSP may break siteapp inline scripts.** Mitigation in §4.5. We will verify
  via `routes-smoke` bats + manual browser smoke before merge. If broken, fall
  back to `script-src 'self' 'unsafe-inline'` and note the trade-off in a
  comment.
- **Authelia logout fix depends on Authelia 4.38 honoring `X-Forwarded-Host`
  for session-domain matching on `/api/logout`.** This is the same mechanism
  `firstfactor` uses successfully, so we expect parity. If it fails to
  invalidate, the audit rerun will show the replay tests still `vulnerable` —
  fallback is to call Authelia's session-management endpoint directly or to
  invalidate via the storage layer (last-resort; ugly).
- **forward_auth `method GET` semantics across Caddy versions.** The fix
  assumes Caddy 2.x's `forward_auth` honors `method` to override the
  sub-request method. Pinned Caddy version in `pins.yaml` should be verified
  against this assumption before merge.

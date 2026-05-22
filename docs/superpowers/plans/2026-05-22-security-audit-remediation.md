# Security audit 2026-05-22 remediation — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the 8 in-scope `vulnerable` findings + 3.2-hardening from `docs/security/2026-05-22-audit-report.md`, bundled into a single PR; re-run the audit harness against preprod to prove zero `vulnerable` rows; commit the post-fix report in the same PR.

**Architecture:** Pure code/config changes to three services and one audit-harness test. No new components, no schema changes. Behavior-preserving for happy paths. Five edits in three services (siteapp, flasher, audit harness) plus the Caddyfile template; everything else is verification.

**Tech Stack:** Caddy 2.x (Caddyfile), Authelia 4.38, FastAPI + httpx (siteapp, flasher), pytest, docker compose, release-please.

**Spec:** `docs/superpowers/specs/2026-05-22-security-audit-remediation-design.md`

---

## File map

| Path | Why we touch it |
|---|---|
| `compose/Caddyfile.tmpl` | 1.6 forward_auth snippet, 5.1 global security headers |
| `services/siteapp/app/auth.py` | 2.1/2.2 logout, 5.0 error status codes, 2.5 Secure flag |
| `services/siteapp/tests/e2e/test_logout.py` | Cover Secure flag, Host-header forwarding |
| `services/siteapp/tests/e2e/test_error_pages.py` | Update expected status from 200 → 403/404 |
| `services/flasher/app/routes/firmware.py` | 3.7 bearer ordering, 3.2 compare_digest |
| `services/flasher/tests/test_firmware.py` | Cover bearer-before-validation, wrong-length token |
| `tests/security/test_07_state.py` | 6.1 re-framed assertion |
| `tests/security/test_01_routing.py` etc. | Mark fixed cases `@pytest.mark.regression` |
| `docs/security/2026-05-22-audit-report.md` (post-fix rerun, new dated file) | Proof artifact |

---

## Task 1: Create worktree, branch, and bring spec along

**Files:** none modified yet; this is environment setup.

- [ ] **Step 1: Create the worktree**

```bash
cd /Users/khamitovdr/lab_devices_server
git worktree add -b fix/security-audit-2026-05-22 .claude/worktrees/security-audit-fixes main
cd .claude/worktrees/security-audit-fixes
```

Expected: new worktree at `.claude/worktrees/security-audit-fixes/` checked out on the new branch.

- [ ] **Step 2: Verify the spec is reachable from the worktree**

```bash
ls docs/superpowers/specs/2026-05-22-security-audit-remediation-design.md
ls docs/superpowers/plans/2026-05-22-security-audit-remediation.md
```

Expected: both files listed.

- [ ] **Step 3: Verify base branch is up-to-date**

```bash
git log --oneline -3
```

Expected: top commit is `docs(security): add 2026-05-22 audit remediation design` (the spec commit on main).

**Notes for the engineer:** From here on, ALL paths in subsequent tasks are relative to `.claude/worktrees/security-audit-fixes/`. Run all `pytest` / `git` commands from inside the worktree.

---

## Task 2: Finding 5.0 — error pages return 403/404 status

**Files:**
- Modify: `services/siteapp/app/auth.py:176-186`
- Modify: `services/siteapp/tests/e2e/test_error_pages.py:8-66` (update existing assertions)

- [ ] **Step 1: Update the e2e tests to expect 403/404 (failing)**

In `services/siteapp/tests/e2e/test_error_pages.py`, change every `assert r.status_code == 200` that targets `/_errors/403` or `/_errors/404` to `403` / `404` respectively. The affected tests are:
- `test_error_403_renders_with_base_template` — change `200` → `403`
- `test_error_403_renders_attempted_path_from_query` — change `200` → `403`
- `test_error_403_falls_back_to_request_path_when_query_missing` — change `200` → `403`
- `test_error_403_escapes_html_in_attempted_path` — change `200` → `403`
- `test_error_404_renders_with_base_template` — change `200` → `404`
- `test_error_404_renders_attempted_path_from_query` — change `200` → `404`
- `test_error_404_falls_back_to_request_path_when_query_missing` — change `200` → `404`
- `test_error_404_escapes_html_in_attempted_path` — change `200` → `404`

Do **not** change `test_unknown_route_returns_styled_404_to_browser`, `test_unknown_docs_path_returns_styled_404`, or `test_unknown_route_returns_json_to_api_clients` — those already expect 404 and go through the global exception handler.

- [ ] **Step 2: Run the updated tests to verify they fail**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_error_pages.py -v
```

Expected: 8 failures, all of the form `assert 200 == 403` or `assert 200 == 404`.

- [ ] **Step 3: Add `status_code=` to both error handlers**

In `services/siteapp/app/auth.py`, replace the two handlers (lines 176-186) with:

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

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_error_pages.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run the full siteapp suite**

```bash
cd services/siteapp
uv run pytest -v
```

Expected: all green.

- [ ] **Step 6: Format and lint**

```bash
cd services/siteapp
uv run ruff format app/ tests/
uv run ruff check app/ tests/
```

Expected: no diff from `format`, no errors from `check`.

- [ ] **Step 7: Commit**

```bash
git add services/siteapp/app/auth.py services/siteapp/tests/e2e/test_error_pages.py
git commit -m "fix(siteapp): return 403/404 status on error pages (5.0)"
```

---

## Task 3: Finding 2.5 — `Secure` flag on logout cookie clears

**Files:**
- Modify: `services/siteapp/app/auth.py:142-167` (Set-Cookie clear lines in `logout`)
- Modify: `services/siteapp/tests/e2e/test_logout.py` (add Secure-flag assertion)

- [ ] **Step 1: Add a failing test for the Secure flag**

In `services/siteapp/tests/e2e/test_logout.py`, append:

```python
def test_logout_cleared_cookies_carry_secure(http: httpx.Client) -> None:
    """All three logout-cleared cookies must include Secure so they're never
    re-sent over plaintext. Audit finding 2.5."""
    cookie = _login(http, "alice", "alice-password")
    r = http.get(
        "/logout",
        headers={"Cookie": cookie},
        follow_redirects=False,
    )
    set_cookies = r.headers.get_list("set-cookie")
    for name in ("authelia_session", "grafana_session", "grafana_session_expiry"):
        matches = [c for c in set_cookies if c.startswith(f"{name}=")]
        assert matches, f"missing clear-line for {name}: {set_cookies}"
        for c in matches:
            assert "Secure" in c, f"{name} clear-line missing Secure: {c}"
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_logout.py::test_logout_cleared_cookies_carry_secure -v
```

Expected: FAIL with `missing Secure: authelia_session=; Max-Age=0; ...` (no `Secure` in the current clear-line).

- [ ] **Step 3: Add `Secure` to all three clear-lines**

In `services/siteapp/app/auth.py`, replace the three `set-cookie` clear lines so each contains `Secure`:

```python
resp.raw_headers.append(
    (
        b"set-cookie",
        f"authelia_session=; Max-Age=0; domain={domain}; path=/; HttpOnly; Secure; SameSite=Lax".encode(
            "latin-1"
        ),
    )
)
# Grafana's session cookie is independent of Authelia — without
# explicit expiry here, the user stays logged in (with whatever role
# OIDC mapped them to) for up to 7 days on grafana_session alone.
# Grafana sets these host-only (no Domain attribute) with `Path=/grafana`
# — no trailing slash, even when serve_from_sub_path=true. Per RFC 6265
# the browser identifies a cookie by (name, domain, path) exactly, so a
# `Path=/grafana/` expire creates a *new* empty cookie at /grafana/ and
# leaves the original at /grafana untouched. Mirror Grafana's path.
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

- [ ] **Step 4: Run the new test to verify it passes**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_logout.py -v
```

Expected: all logout tests pass, including the new one.

- [ ] **Step 5: Run the full siteapp suite**

```bash
cd services/siteapp
uv run pytest -v
```

Expected: all green.

- [ ] **Step 6: Format and lint**

```bash
cd services/siteapp
uv run ruff format app/ tests/
uv run ruff check app/ tests/
```

- [ ] **Step 7: Commit**

```bash
git add services/siteapp/app/auth.py services/siteapp/tests/e2e/test_logout.py
git commit -m "fix(siteapp): add Secure flag to logout cookie clears (2.5)"
```

---

## Task 4: Findings 2.1 & 2.2 — logout forwards Host headers to Authelia

**Files:**
- Modify: `services/siteapp/app/auth.py:126-167` (logout handler)
- Modify: `services/siteapp/tests/e2e/test_logout.py` (add session-replay assertion)

**Important context:** The siteapp e2e suite runs siteapp + a real Authelia 4.38 container via docker compose (see `services/siteapp/tests/e2e/compose.yaml`). There is **no** httpx mock — we test the actual behaviour. The session-replay shape is the right assertion: log in, save the cookie, log out, replay the cookie against `/api/auth/whoami` — it should now return `{"user": null}` instead of the alice user, because Authelia's `/api/verify` now returns non-200 for the invalidated session.

- [ ] **Step 1: Add a failing test for session-replay after logout**

Append to `services/siteapp/tests/e2e/test_logout.py`:

```python
def test_logout_invalidates_authelia_session_server_side(
    http: httpx.Client,
) -> None:
    """The cookie issued by /api/auth/firstfactor must not work against
    /api/auth/whoami after /logout. Without server-side invalidation,
    Authelia's session record persists and the cookie remains valid even
    though the client-side clear succeeded. Audit findings 2.1, 2.2."""
    cookie = _login(http, "alice", "alice-password")
    # Sanity: the cookie works pre-logout.
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    assert r.json()["user"] == "alice", f"pre-logout whoami unexpected: {r.json()}"
    # Log out via GET (covers 2.1) — POST flavour covered by 2.2 in the
    # audit harness.
    http.get("/logout", headers={"Cookie": cookie}, follow_redirects=False)
    # Replay the *original* cookie. It must not authenticate any more.
    r = http.get("/api/auth/whoami", headers={"Cookie": cookie})
    assert r.status_code == 200
    assert r.json()["user"] is None, (
        f"replay after logout should not authenticate; got {r.json()}"
    )
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_logout.py::test_logout_invalidates_authelia_session_server_side -v
```

Expected: FAIL. Current code calls Authelia `/api/logout` with only the `Cookie` header. The in-cluster request reaches Authelia with `Host: authelia:9091`, which doesn't match the session-cookie domain Authelia configured for the e2e container — so Authelia treats it as a no-op. The replayed cookie still authenticates and the test sees `user == "alice"` instead of `null`.

If the test unexpectedly passes today, the e2e Authelia configuration may be permissive enough that the no-op is masked. Inspect `services/siteapp/tests/e2e/fixtures/authelia_config.yml` for the configured `session.domain` and `default_redirection_url`. If the e2e Authelia accepts logout despite the mismatch, the test won't fail until we deploy to preprod — in which case mark this task's TDD step as a known-limited unit gate, document it in the commit message, and rely on the Task 10 audit-harness rerun to confirm the fix.

- [ ] **Step 3: Update the logout handler to forward Host headers**

In `services/siteapp/app/auth.py`, replace the `logout` handler so it forwards `X-Forwarded-Host` and `X-Forwarded-Proto` on the POST to Authelia:

```python
@router.api_route("/logout", methods=["GET", "POST"], include_in_schema=False)
async def logout(request: Request) -> Response:
    cookie = request.headers.get("cookie", "")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or "https"
    # Authelia 4.38 /api/logout is POST-only; it invalidates the session
    # server-side but does not emit a Set-Cookie header. Authelia matches
    # the session by cookie domain, so we must forward X-Forwarded-Host —
    # otherwise the in-cluster request (Host: authelia:9091) fails the
    # session-domain check and the logout is a no-op (audit 2.1, 2.2).
    # We POST to invalidate, then clear the client-side cookie ourselves.
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
    resp = RedirectResponse("/", status_code=302)
    domain = host.split(":")[0]  # strip port if present
    # … cookie-clearing lines from Task 3 unchanged …
```

Keep all of the existing cookie-clearing logic (including the Secure flag from Task 3) untouched. Only the `client.post("/api/logout", …)` call grows headers, and the comment around it is updated.

- [ ] **Step 4: Run the new test to verify it passes**

```bash
cd services/siteapp
uv run pytest tests/e2e/test_logout.py -v
```

Expected: all logout tests pass, including the new replay assertion. (If the e2e Authelia was permissive enough to mask the no-op in Step 2, the test will pass both before and after — that's acceptable; the real gate is Task 10.)

- [ ] **Step 5: Run the full siteapp suite**

```bash
cd services/siteapp
uv run pytest -v
```

Expected: all green.

- [ ] **Step 6: Format and lint**

```bash
cd services/siteapp
uv run ruff format app/ tests/
uv run ruff check app/ tests/
```

- [ ] **Step 7: Commit**

```bash
git add services/siteapp/app/auth.py services/siteapp/tests/e2e/test_logout.py
git commit -m "fix(siteapp): forward Host headers to Authelia /api/logout (2.1, 2.2)"
```

---

## Task 5: Finding 3.2-hardening — constant-time bearer compare in flasher

**Files:**
- Modify: `services/flasher/app/routes/firmware.py:67-83`
- Modify: `services/flasher/tests/test_firmware.py` (add wrong-length-token test)

- [ ] **Step 1: Add a failing test for wrong-length token**

Append to `services/flasher/tests/test_firmware.py` (after `test_bearer_post_wrong_token`):

```python
def test_bearer_post_short_token_rejected_cleanly(http_app: TestClient) -> None:
    """A bearer token whose length differs from the expected token must be
    rejected with the standard 401 error shape. compare_digest accepts
    unequal-length inputs without raising. Audit hardening 3.2."""
    r = http_app.post(
        "/flash/api/v1/firmware",
        json={"name": "x", "firmware": ":00000001FF\n"},
        headers={"Authorization": "Bearer short"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"
```

- [ ] **Step 2: Run the new test to verify it fails OR passes (sanity check)**

```bash
cd services/flasher
uv run pytest tests/test_firmware.py::test_bearer_post_short_token_rejected_cleanly -v
```

Expected: PASS today (current `!=` compare returns 401 for unequal strings; the test is a behavioral guard for the refactor).

- [ ] **Step 3: Switch `_require_bearer` to `compare_digest`**

In `services/flasher/app/routes/firmware.py`, add `import secrets` near the top of the file (if absent) and rewrite `_require_bearer` (lines 67-83):

```python
def _require_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "bearer required",
                "detail": "Authorization: Bearer <token> required",
            },
        )
    provided = authorization[len("Bearer "):]
    # compare_digest avoids a timing side-channel and accepts unequal-length
    # inputs without raising. Mirrors services/flasher/app/routes/agent.py.
    if not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "bearer invalid",
                "detail": "token does not match",
            },
        )
```

- [ ] **Step 4: Run the new test to verify it still passes**

```bash
cd services/flasher
uv run pytest tests/test_firmware.py::test_bearer_post_short_token_rejected_cleanly -v
uv run pytest tests/test_firmware.py::test_bearer_post_wrong_token -v
uv run pytest tests/test_firmware.py::test_bearer_post_succeeds -v
```

Expected: all three pass.

- [ ] **Step 5: Format and lint**

```bash
cd services/flasher
uv run ruff format app/ tests/
uv run ruff check app/ tests/
```

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/routes/firmware.py services/flasher/tests/test_firmware.py
git commit -m "fix(flasher): use compare_digest for bearer compare (3.2)"
```

---

## Task 6: Finding 3.7 — bearer check precedes query validation

**Files:**
- Modify: `services/flasher/app/routes/firmware.py:239-257` (the `GET /api/v1/firmware` handler)
- Modify: `services/flasher/tests/test_firmware.py` (add ordering test)

- [ ] **Step 1: Add a failing test for bearer-before-query ordering**

Append to `services/flasher/tests/test_firmware.py`:

```python
def test_bearer_get_without_token_and_without_sha256_returns_401(
    http_app: TestClient,
) -> None:
    """An unauthenticated GET /api/v1/firmware with no sha256 query must
    return 401 (bearer required), not 422 (schema leak). Audit finding 3.7."""
    r = http_app.get("/flash/api/v1/firmware")
    assert r.status_code == 401
    assert r.json()["error"] == "bearer required"


def test_bearer_get_with_wrong_token_and_without_sha256_returns_401(
    http_app: TestClient,
) -> None:
    """Same as above but with an invalid bearer — must reject on bearer, not
    surface the missing-sha256 422."""
    r = http_app.get(
        "/flash/api/v1/firmware",
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"


def test_bearer_get_with_valid_token_but_missing_sha256_returns_400(
    http_app: TestClient,
) -> None:
    """With a valid bearer but no sha256, return our own 400 (not pydantic's
    422). This keeps the auth-leak fix from breaking the legitimate
    'missing-param' UX for authenticated clients."""
    r = http_app.get(
        "/flash/api/v1/firmware",
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "missing query"
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd services/flasher
uv run pytest tests/test_firmware.py::test_bearer_get_without_token_and_without_sha256_returns_401 tests/test_firmware.py::test_bearer_get_with_wrong_token_and_without_sha256_returns_401 tests/test_firmware.py::test_bearer_get_with_valid_token_but_missing_sha256_returns_400 -v
```

Expected: all three fail with `assert 422 == 401` or `assert 422 == 400` (FastAPI's required-Query validation runs before the function body).

- [ ] **Step 3: Make `sha256` optional in the handler signature and validate after bearer**

In `services/flasher/app/routes/firmware.py`, replace the `GET /api/v1/firmware` handler (currently at lines 239-257) with:

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
            detail={
                "error": "missing query",
                "detail": "sha256 query parameter required",
            },
        )
    async with conn_factory() as conn:
        row = await get_firmware_by_sha256(conn, sha256=sha256)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown firmware",
                "detail": sha256,
            },
        )
    return row
```

Preserve the rest of the function body (the existing `if row is None: ...` 404 branch and the final `return row`) — only `sha256` becomes optional and we add a `_require_bearer` + missing-param check before the DB query.

- [ ] **Step 4: Run the new tests to verify they pass**

```bash
cd services/flasher
uv run pytest tests/test_firmware.py::test_bearer_get_without_token_and_without_sha256_returns_401 tests/test_firmware.py::test_bearer_get_with_wrong_token_and_without_sha256_returns_401 tests/test_firmware.py::test_bearer_get_with_valid_token_but_missing_sha256_returns_400 -v
```

Expected: all three pass.

- [ ] **Step 5: Run the existing `test_bearer_get_by_sha256` to verify no regression**

```bash
cd services/flasher
uv run pytest tests/test_firmware.py::test_bearer_get_by_sha256 -v
```

Expected: still passes (round-trip GET with valid bearer + valid sha256 → 200; GET with valid bearer + bogus sha256 → 404).

- [ ] **Step 6: Run the full flasher suite**

```bash
cd services/flasher
uv run pytest -v
```

Expected: all green.

- [ ] **Step 7: Format and lint**

```bash
cd services/flasher
uv run ruff format app/ tests/
uv run ruff check app/ tests/
```

- [ ] **Step 8: Commit**

```bash
git add services/flasher/app/routes/firmware.py services/flasher/tests/test_firmware.py
git commit -m "fix(flasher): enforce bearer before query validation (3.7)"
```

---

## Task 7: Finding 1.6 — Caddy forward_auth pins verify to GET

**Files:**
- Modify: `compose/Caddyfile.tmpl:13-27` (the `(authelia_required)` snippet)

**Note on test strategy:** Caddyfile changes are not covered by service-local pytest. The verification gate is the integration audit harness in Task 10 (`test_1_6_researcher_flash_post` must show `reached_upstream=False` and a 403 status). The platform `routes-smoke` bats matrix cell will also catch any cross-service routing regression.

- [ ] **Step 1: Update the `(authelia_required)` snippet**

In `compose/Caddyfile.tmpl`, replace lines 13-27 (the entire `(authelia_required)` snippet) with:

```
(authelia_required) {
    forward_auth authelia:9091 {
        uri /api/verify?rd=https://__VPS_HOST__/login
        # Pin the verify sub-request to GET. By default Caddy forwards the
        # original method (and body) to /api/verify, which causes Authelia
        # 4.38 to treat non-GET requests inconsistently — researcher POSTs
        # to /flash/api/firmware reach upstream and return the backend's 405
        # instead of Authelia's 403. Audit finding 1.6.
        method GET
        header_up X-Forwarded-Method {method}
        header_up X-Forwarded-Uri {uri}
        # Strip the original Content-Length so Authelia doesn't try to read
        # a body off the GET we just pinned above.
        header_up Content-Length ""
        copy_headers Remote-User Remote-Groups Remote-Name Remote-Email

        # Authelia returns 403 (raw "Forbidden" body) for authenticated users
        # who lack the required role. Without this hook, forward_auth proxies
        # that response unchanged. Converting it to an internal Caddy error
        # routes it through handle_errors below → /_errors/403.
        @forbidden status 403
        handle_response @forbidden {
            error 403
        }
    }
}
```

- [ ] **Step 2: Render the template locally and lint Caddyfile**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
sed 's/__VPS_HOST__/lab.example/g; s/__ACME_EMAIL__/x@example/g; s/__PLATFORM_VERSION__/0.0.0/g' compose/Caddyfile.tmpl > /tmp/Caddyfile.rendered
docker run --rm -v /tmp:/etc/caddy caddy:2 caddy validate --config /etc/caddy/Caddyfile.rendered --adapter caddyfile
```

Expected: `Valid configuration`. (If `docker pull caddy:2` is required, run it first.)

- [ ] **Step 3: Commit the snippet change**

```bash
git add compose/Caddyfile.tmpl
git commit -m "fix(caddy): pin forward_auth verify to GET (1.6)"
```

---

## Task 8: Finding 5.1 — security headers at the Caddyfile server scope

**Files:**
- Modify: `compose/Caddyfile.tmpl` (add `header { … }` block inside the server-level `https://__VPS_HOST__ { … }` block, immediately after the `tls { … }` block and before the first `handle`)

- [ ] **Step 1: Add the global header block**

In `compose/Caddyfile.tmpl`, locate the `https://__VPS_HOST__ {` server block (around line 42) and after the `tls { … }` block (around line 47) but **before** the first `handle /_shared/*` directive, insert:

```
    # ─── Global security headers ─────────────────────────────────────────
    # Applied to every response except where a child `handle` block sets
    # its own Content-Security-Policy (Grafana / Jupyter override below).
    # Audit finding 5.1.
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options    "nosniff"
        Referrer-Policy           "strict-origin-when-cross-origin"
        Content-Security-Policy   "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        -Server
    }
```

**On `script-src 'unsafe-inline'`:** siteapp's `base.html` ships an inline theme-bootstrap script (the `localStorage.getItem('theme')` block visible in audit response bodies). Without `'unsafe-inline'`, that script is CSP-blocked and the dark-mode flash-of-light returns. We accept the lower CSP value here as the documented trade-off; the cross-origin protections (`frame-ancestors 'none'`, restricted `connect-src` / `img-src`) still apply.

- [ ] **Step 2: Validate the Caddyfile renders**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
sed 's/__VPS_HOST__/lab.example/g; s/__ACME_EMAIL__/x@example/g; s/__PLATFORM_VERSION__/0.0.0/g' compose/Caddyfile.tmpl > /tmp/Caddyfile.rendered
docker run --rm -v /tmp:/etc/caddy caddy:2 caddy validate --config /etc/caddy/Caddyfile.rendered --adapter caddyfile
```

Expected: `Valid configuration`.

- [ ] **Step 3: Commit**

```bash
git add compose/Caddyfile.tmpl
git commit -m "fix(caddy): add HSTS, nosniff, Referrer-Policy, baseline CSP (5.1)"
```

---

## Task 9: Finding 6.1 — re-frame brute-force regulation test

**Files:**
- Modify: `tests/security/test_07_state.py:32-56`

- [ ] **Step 1: Update the test to encode the by-design assertion**

Replace the body of `test_6_1_brute_force_regulation` in `tests/security/test_07_state.py`:

```python
def test_6_1_brute_force_regulation(target_url, verify_tls, anon_log, record):
    """Authelia regulation is keyed by username; for unknown users it returns
    identical 401s on every attempt — this is intentional anti-enumeration
    behaviour. Distinct responses across attempts would indicate a user-
    enumeration leak."""
    probe_user = f"bf-probe-{secrets.token_hex(4)}"
    statuses: list[int] = []
    for _ in range(5):
        r, _ = _attempt_login(target_url, verify_tls, probe_user, "wrong-password")
        statuses.append(r.status_code)
    distinct = len(set(statuses)) > 1
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

- [ ] **Step 2: Run the audit harness test locally against preprod**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
cd tests/security
export LDS_AUDIT_ADMIN_PASS="$(grep -A1 admin_pass ../../config.yaml | tail -1 | awk -F': ' '{print $2}' | tr -d '\"')"
export LDS_AUDIT_RES_PASS="$(grep -A1 researcher_pass ../../config.yaml | tail -1 | awk -F': ' '{print $2}' | tr -d '\"')"
uv run pytest test_07_state.py::test_6_1_brute_force_regulation -v
```

If the env-var extraction one-liners don't match your `config.yaml` shape, set them manually from the same secrets the audit harness already uses (see `tests/security/README.md`).

Expected: PASS, and the finding records `status="verified"`.

- [ ] **Step 3: Format and lint**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
cd tests/security
uv run ruff format .
uv run ruff check .
```

- [ ] **Step 4: Commit**

```bash
git add tests/security/test_07_state.py
git commit -m "test(security): re-frame 6.1 — unknown-user regulation is by-design"
```

---

## Task 10: Deploy preprod and re-run the audit harness

**Files:**
- Create: `docs/security/<rerun-date>-audit-report.md` (output of the post-fix audit run)

**Important:** This task only runs after Tasks 2–9 are committed on the worktree branch. The preprod deploy is via the laptop-side `task deploy` flow (see CLAUDE.md §Laptop vs CI), not a CI deploy. Get explicit user approval before deploying.

- [ ] **Step 1: Confirm with the user that preprod deploy is OK now**

Auto-mode allows internal changes; preprod is shared infra. Ask explicitly:

> "Ready to deploy this branch to preprod (`111.88.145.138`) and run the audit harness against it. Confirm before I proceed?"

Wait for explicit ack.

- [ ] **Step 2: Build and push the service images for the current branch SHA**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
( cd services/siteapp && ./build.sh )
( cd services/flasher && ./build.sh )
```

Expected: both `build.sh` runs end with `Pushed ghcr.io/.../...:<VERSION>` lines.

- [ ] **Step 3: Deploy to preprod**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
task deploy
```

Expected: deploy completes, health checks green.

- [ ] **Step 4: Smoke-test in a browser**

Visit:
- `https://111.88.145.138/` — page loads, theme bootstrap works (no FOUC, dark-mode honored). The new `'unsafe-inline'` CSP must allow the bootstrap script.
- `https://111.88.145.138/login` then sign in as both admin and researcher.
- `https://111.88.145.138/flash/` — admin: SPA loads. Researcher: 403 page.
- Open DevTools → Network → response headers: confirm HSTS / nosniff / Referrer-Policy / CSP are present, `Server` is missing.

If anything is broken, **do not** proceed — fix and redeploy.

- [ ] **Step 5: Re-run the audit harness against preprod**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
export LDS_AUDIT_ADMIN_PASS='...'  # from config.yaml or the same source the original run used
export LDS_AUDIT_RES_PASS='...'
RUN_DATE=$(date +%Y-%m-%d)
scripts/security_audit.sh \
    --target-url=https://111.88.145.138 \
    --report=docs/security/${RUN_DATE}-audit-report.md
```

Expected: harness completes. The exit code may be non-zero if any finding is `vulnerable`.

- [ ] **Step 6: Verify zero in-scope `vulnerable` rows in the new report**

```bash
grep -A1 "^### " docs/security/${RUN_DATE}-audit-report.md | grep -E "Status:" | sort | uniq -c
```

Read the new report. The following findings must NOT appear under the `## Critical / High / Medium / Low findings` sections (they should be `verified` and live under `## Passed controls` or have status `informational`):
- 1.6, 2.1, 2.2, 5.0, 5.1, 3.7, 2.5

If any of these is still `vulnerable`, stop and investigate. Likely culprits:
- 1.6 still failing → Caddy version may interpret `method GET` differently; try `request method GET` instead, or look for Authelia logs.
- 2.1/2.2 still failing → Authelia may need additional headers (Origin, Referer); inspect Authelia logs at `/srv/lab-bridge/authelia_data/`.

- [ ] **Step 7: Commit the new audit report**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
git add docs/security/${RUN_DATE}-audit-report.md
git commit -m "docs(security): post-remediation audit report ${RUN_DATE}"
```

---

## Task 11: Promote fixed audit cases to `@pytest.mark.regression`

**Files:**
- Modify: `tests/security/test_01_routing.py` (test_1_6)
- Modify: `tests/security/test_02_disclosure.py` (test_5_0, test_5_1)
- Modify: `tests/security/test_05_bearer.py` (test_3_7)
- Modify: `tests/security/test_06_session.py` (test_2_1, test_2_2, test_2_5)

- [ ] **Step 1: Confirm the existing audit_only / regression conventions**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
grep -rn "pytest.mark.regression\|pytest.mark.audit_only" tests/security/ | head
```

Read the output. Note which tests are already promoted and the exact marker decorator form (e.g., `@pytest.mark.regression` vs `@pytest.mark.regression()`).

- [ ] **Step 2: Add `@pytest.mark.regression` to each of the seven fixed cases**

For each of the following tests, add `@pytest.mark.regression` immediately above the `def test_*` line (preserve any existing markers like `@pytest.mark.audit_only` — replace if present, do not duplicate). The seven tests are:

- `tests/security/test_01_routing.py::test_1_6_researcher_flash_post`
- `tests/security/test_02_disclosure.py::test_5_0_status_code_masquerading`
- `tests/security/test_02_disclosure.py::test_5_1_security_headers`
- `tests/security/test_05_bearer.py::test_3_7_bearer_validation_order`
- `tests/security/test_06_session.py::test_2_1_replay_after_get_logout`
- `tests/security/test_06_session.py::test_2_2_replay_after_post_logout`
- `tests/security/test_06_session.py::test_2_5_logout_cookie_attributes`

Example transformation (apply per-test):

```python
@pytest.mark.regression
def test_1_6_researcher_flash_post(...):
    ...
```

If `pytest` isn't imported in a given file, add `import pytest` at the top.

Do **not** add `@pytest.mark.regression` to `test_6_1_brute_force_regulation` — its assertion depends on Authelia internals and stays `audit_only` per the spec.

- [ ] **Step 3: Verify the marker collection**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
cd tests/security
uv run pytest -m regression --collect-only -q
```

Expected: the seven promoted tests appear in the collection.

- [ ] **Step 4: Format and lint**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
cd tests/security
uv run ruff format .
uv run ruff check .
```

- [ ] **Step 5: Commit**

```bash
git add tests/security/
git commit -m "test(security): mark fixed audit cases as @regression"
```

---

## Task 12: Push branch and open PR

**Files:** none (delivery step).

- [ ] **Step 1: Verify all commits are clean and in order**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
git log --oneline main..HEAD
git status
```

Expected: 7–8 commits in the order from the spec §7; `working tree clean`.

- [ ] **Step 2: Push the branch**

```bash
git push -u origin fix/security-audit-2026-05-22
```

- [ ] **Step 3: Open the PR**

```bash
cd /Users/khamitovdr/lab_devices_server/.claude/worktrees/security-audit-fixes
gh pr create \
    --title "fix(security): remediate 2026-05-22 audit — critical + high + medium + low vulnerable findings" \
    --body "$(cat <<'EOF'
## Summary

Remediates the 2026-05-22 security audit (`docs/security/2026-05-22-audit-report.md`):

- **Critical** 1.6 — `forward_auth` now pins the verify sub-request to GET so Authelia enforces `/flash*` on all methods.
- **High** 2.1 & 2.2 — `/logout` now forwards `X-Forwarded-Host` to Authelia's `/api/logout`, so the server-side session is actually invalidated.
- **Medium** 5.0 — `/_errors/{403,404}` return their proper HTTP status (no more 200 masquerade).
- **Medium-info** 3.2 — flasher bearer compare switched to `secrets.compare_digest`.
- **Low** 5.1 — HSTS / X-Content-Type-Options / Referrer-Policy / baseline CSP at Caddy server scope.
- **Low** 3.7 — flasher `/api/v1/firmware` enforces bearer before query validation.
- **Low** 2.5 — logout cookie clears carry `Secure`.
- **Info** 6.1 — audit-harness test re-framed: identical 401s for unknown users is now correctly recorded as `verified` (anti-enumeration), not `vulnerable`.

Out of scope (documented in `docs/superpowers/specs/2026-05-22-security-audit-remediation-design.md` §3 / §8): 5.6 open-redirect, 2.11 cross-origin firstfactor, 2.12 GET-logout CSRF, 2.3 per-session invalidation, 1.15(*) Authelia surface, 1.7 / 1.10 by-design routes, CI wiring for `@regression`.

Post-remediation audit report committed at `docs/security/<date>-audit-report.md` shows zero `vulnerable` rows in scope.

## Test plan

- [x] siteapp unit + e2e green (`cd services/siteapp && uv run pytest`)
- [x] flasher unit + e2e green (`cd services/flasher && uv run pytest`)
- [x] Caddyfile renders + validates (`caddy validate`)
- [x] preprod deploy + manual smoke (login as admin + researcher, /flash, /grafana, /jupyter, theme bootstrap)
- [x] audit harness re-run against preprod yields zero `vulnerable` rows for in-scope findings
- [ ] Required CI checks (`pr-title`, `pr-siteapp / siteapp`, `pr-flasher / flasher`, `pr-platform / platform`) all green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR created; CLI prints the URL.

- [ ] **Step 4: Surface the PR URL to the user**

Print the URL from the `gh pr create` output as the final message to the user.

---

## Self-review notes

- **Spec coverage**:
  - 1.6 → Task 7 ✓
  - 2.1, 2.2 → Task 4 ✓
  - 5.0 → Task 2 ✓
  - 3.2-hardening → Task 5 ✓
  - 5.1 → Task 8 ✓
  - 3.7 → Task 6 ✓
  - 2.5 → Task 3 ✓
  - 6.1 → Task 9 ✓
  - Verification gate (§6) → Task 10 ✓
  - `@regression` promotion (§5.5) → Task 11 ✓
  - Delivery (§7) → Tasks 1, 12 ✓
- **Placeholder scan**: clean. The only conditional language is in Task 4 Step 2 (the "if the e2e Authelia is permissive enough to mask the no-op" caveat) and Task 10 Step 6 (Caddy fallback if `method GET` fails on the live preprod) — both are genuine fork-in-the-road notes, not placeholders.
- **Type consistency**: `_require_bearer`'s signature stays identical across Tasks 5 and 6.

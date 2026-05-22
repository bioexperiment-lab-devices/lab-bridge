# lab-bridge security audit report

- Target: `https://111.88.145.138`
- Run at: 2026-05-22T10:26:34+00:00
- Git SHA: `cb94e4e4ddff`
- TLS verification disabled: `true`
- --slow enabled: `False`

## Executive summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 2 |
| Medium | 2 |
| Low | 6 |
| Informational | 17 |

Passed controls: 46

## Critical findings

### 1.6 — Researcher POST /flash/api/firmware must be denied by Authelia

- Severity: **Critical**
- Status: `vulnerable`
- Test: `test_01_routing.py::test_1_6_researcher_flash_post`

Authelia rule '^/flash.*' subject:group:admins must enforce on all methods. If a non-GET request from a researcher reaches flasher upstream, the gate fails for non-GET methods (Caddy forward_auth + Authelia interaction).

**Details:**

- status_code: `405`
- reached_upstream: `True`
- created_id: `None`
- body_excerpt: `{"detail":"Method Not Allowed"}`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 108
  - req body: `{"username":"test","password":"test_researcher","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=zl7cD*...(32 chars); expires=Thu, 20 Aug 2026 10:25:39 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/flash/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Forbidden — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `POST https://111.88.145.138/flash/api/firmware` → `405`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars), content-length: 93, content-type: application/json
  - req body: `{"name":"audit-probe","description":"","firmware":":020000040000FA\n:00000001FF\n","tags":[]}`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Method Not Allowed"}`

## High findings

### 2.1 — Cookie replay after GET /logout must fail

- Severity: **High**
- Status: `vulnerable`
- Test: `test_06_session.py::test_2_1_replay_after_get_logout`

Server-side session must be invalidated, not just client-side cookie cleared. siteapp/app/auth.py:133 fires-and-forgets POST /api/logout to Authelia; if Authelia 4.38 server-to-server logout doesn't kill the session, the stale cookie keeps working until inactivity timeout.

**Details:**

- replay_status: `200`
- replay_location: `None`
- reached_flasher_spa: `True`
- body_excerpt: `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>F`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 114
  - req body: `{"username":"khamitovdr","password":"U$rKtI3N2M*5*Wg","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=WDGJpu...(32 chars); expires=Thu, 20 Aug 2026 10:26:18 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=WDGJpu...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax
- `GET https://111.88.145.138/flash/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=WDGJpu...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!DOCTYPE html> <html lang="en">   <head>     <meta charset="UTF-8" />     <meta name="viewport" content="width=device-width, initial-scale=1.0" />     <title>Flasher</title>     <script>       (function () {         var t = localStorage.ge…`

### 2.2 — Cookie replay after POST /logout must fail

- Severity: **High**
- Status: `vulnerable`
- Test: `test_06_session.py::test_2_2_replay_after_post_logout`

POST /logout must invalidate the server-side session.

**Details:**

- replay_status: `200`
- replay_location: `None`
- reached_flasher_spa: `True`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 114
  - req body: `{"username":"khamitovdr","password":"U$rKtI3N2M*5*Wg","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=0Ou8Y$...(32 chars); expires=Thu, 20 Aug 2026 10:26:19 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `POST https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, content-length: 0, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=0Ou8Y$...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax
- `GET https://111.88.145.138/flash/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=0Ou8Y$...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!DOCTYPE html> <html lang="en">   <head>     <meta charset="UTF-8" />     <meta name="viewport" content="width=device-width, initial-scale=1.0" />     <title>Flasher</title>     <script>       (function () {         var t = localStorage.ge…`

## Medium findings

### 5.0 — Status-code masquerading: 403/404 pages served at HTTP 200

- Severity: **Medium**
- Status: `vulnerable`
- Test: `test_02_disclosure.py::test_5_0_status_code_masquerading`

Caddy's handle_errors rewrites 403/404 → /_errors/{403,404} on siteapp, which returns TemplateResponse without an explicit status_code (defaults to 200). Fix: services/siteapp/app/auth.py error_403/error_404 handlers should pass status_code=403/404 to TemplateResponse.

**Details:**

- anon_flash_status: `302`
- anon_flash_masquerade: `False`
- anon_missing_status: `200`
- anon_missing_masquerade: `True`

**Evidence:**

- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`
- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `403 Forbidden`
- `GET https://111.88.145.138/auth/api/password-reset/identity/start` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `404 Not Found`
- `GET https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/this-route-definitely-does-not-exist` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`

### 3.2-hardening — Flasher bearer compare is not constant-time

- Severity: **Medium**
- Status: `informational`
- Test: `test_05_bearer.py::test_3_2_flasher_bearer_wrong`

services/flasher/app/routes/firmware.py:76 uses `!=` to compare the bearer token; switching to `secrets.compare_digest` removes a theoretical timing side-channel. The agent.py upload endpoint already uses compare_digest.

**Details:**

- file: `services/flasher/app/routes/firmware.py:76`

**Evidence:**

_(no recorded exchanges)_

## Low findings

### 1.15(/auth/api/password-reset/identity/start) — Authelia surface /auth/api/password-reset/identity/start

- Severity: **Low**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/api/password-reset/identity/start-None]`

Exposed via /auth/* reverse_proxy. Status 404.

**Details:**

- path: `/auth/api/password-reset/identity/start`
- status_code: `404`
- body_excerpt: `404 Not Found`

**Evidence:**

- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`
- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `403 Forbidden`
- `GET https://111.88.145.138/auth/api/password-reset/identity/start` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `404 Not Found`

### 5.1 — Security headers on the platform root

- Severity: **Low**
- Status: `vulnerable`
- Test: `test_02_disclosure.py::test_5_1_security_headers`

Hardening miss: missing security headers strict-transport-security, x-content-type-options, referrer-policy, content-security-policy

**Details:**

- missing: `['strict-transport-security', 'x-content-type-options', 'referrer-policy', 'content-security-policy']`
- present: `{'strict-transport-security': None, 'x-content-type-options': None, 'referrer-policy': None, 'content-security-policy': None}`

**Evidence:**

- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `403 Forbidden`
- `GET https://111.88.145.138/auth/api/password-reset/identity/start` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `404 Not Found`
- `GET https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/this-route-definitely-does-not-exist` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>lab-bridge — Home</title>    <script>     (function () {       var t = localStorage.getItem('th…`

### 5.6 — Open-redirect via /login?rd=

- Severity: **Low**
- Status: `informational`
- Test: `test_02_disclosure.py::test_5_6_open_redirect`

The login form sets `rd` as a query param. Real exploit requires a successful login that 302s to the value — only a finding if the final redirect leaves the VPS host. We capture the page render here; full flow tested via session class.

**Details:**

- status_code: `200`
- body_has_rd: `True`

**Evidence:**

- `GET https://111.88.145.138/healthz` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.16.1","git_sha":"6cedd9aa90d4e1d779e8cebbdaa0112f1c77…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.16.1","git_sha":"6cedd9aa90d4e1d779e8cebbdaa0112f1c77…`
- `GET https://111.88.145.138/%3Cscript%3Ealert(1)%3C/script%3E` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/login?rd=https%3A%2F%2Fevil.example%2F` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Sign in — lab-bridge</title>    <script>     (function () {       var t = localStorage.getItem(…`

### 3.7 — Bearer check ordering on /flash/api/v1/firmware

- Severity: **Low**
- Status: `vulnerable`
- Test: `test_05_bearer.py::test_3_7_bearer_validation_order`

If the endpoint returns 422 (validation error) to an unauthenticated request missing the sha256 query, the schema is enumerable without credentials. Bearer enforcement should precede pydantic validation.

**Details:**

- status_code: `422`
- body_excerpt: `{"detail":[{"type":"missing","loc":["query","sha256"],"msg":"Field required","input":null}]}`

**Evidence:**

- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=111173d2a9e4cfd53b8dcf80ea0559d4
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=b4f03f958b769920172a869cdf7fd432
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/flash/api/v1/firmware` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=e8fb0d26a5772e1c0570c46e296b1b64
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `GET https://111.88.145.138/flash/api/v1/firmware` → `422`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"detail":[{"type":"missing","loc":["query","sha256"],"msg":"Field required","input":null}]}`

### 2.5 — Logout-cleared cookies must include Secure

- Severity: **Low**
- Status: `vulnerable`
- Test: `test_06_session.py::test_2_5_logout_cookie_attributes`

Manual cookie clearing in siteapp/app/auth.py omits Secure on these cookies: authelia_session, grafana_session, grafana_session_expiry

**Details:**

- missing_secure: `['authelia_session', 'grafana_session', 'grafana_session_expiry']`
- lines: `['authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax', 'grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax', 'grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax']`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 114
  - req body: `{"username":"khamitovdr","password":"U$rKtI3N2M*5*Wg","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=63mNMB...(32 chars); expires=Thu, 20 Aug 2026 10:26:22 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=63mNMB...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax

### 2.11 — Cross-origin POST to /api/auth/firstfactor

- Severity: **Low**
- Status: `vulnerable`
- Test: `test_06_session.py::test_2_11_csrf_firstfactor_origin`

Authelia does not check Origin/Referer on the auth API; SameSite=Lax on the session cookie is the actual CSRF mitigation. Documented for awareness.

**Details:**

- status_code: `200`
- set_cookie_present: `True`

**Evidence:**

_(no recorded exchanges)_

## Informational findings

### 1.7 — Researcher reaches /grafana/ and /jupyter/

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_7_researcher_grafana_jupyter`

Positive test: researcher group is allowed through Authelia to both services.

**Details:**

- grafana_status: `302`
- jupyter_status: `302`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 108
  - req body: `{"username":"test","password":"test_researcher","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=zl7cD*...(32 chars); expires=Thu, 20 Aug 2026 10:25:39 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/flash/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Forbidden — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `POST https://111.88.145.138/flash/api/firmware` → `405`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars), content-length: 93, content-type: application/json
  - req body: `{"name":"audit-probe","description":"","firmware":":020000040000FA\n:00000001FF\n","tags":[]}`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Method Not Allowed"}`
- `GET https://111.88.145.138/grafana/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login, set-cookie: redirect_to=%2Fgra...(13 chars); Path=/grafana; HttpOnly; SameSite=Lax
  - resp body: `<a href="/grafana/login">Found</a>.  `
- `GET https://111.88.145.138/jupyter/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=zl7cD*...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8, location: /jupyter/lab?

### 1.10 — /grafana/api/health is public (documented exception)

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_10_grafana_health_public`

Health check used by deploy.sh; must stay public.

**Details:**

- status_code: `200`

**Evidence:**

- `GET https://111.88.145.138/flash/api/v1/firmware?sha256=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"error":"bearer required","detail":"Authorization: Bearer <token> required"}`
- `POST https://111.88.145.138/flash/api/firmware` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars), content-length: 2, content-type: application/json
  - req body: `{}`
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=POST, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:38 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&amp;rm=POST">303 See Other</a>`
- `GET https://111.88.145.138/jupyter/api/contents/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fjupyter%2Fapi%2Fcontents%2F&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:40 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fjupyter%2Fapi%2Fcontents%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/grafana/api/datasources` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fgrafana%2Fapi%2Fdatasources&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:41 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fgrafana%2Fapi%2Fdatasources&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/grafana/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=UTF-8
  - resp body: `{   "database": "ok",   "version": "11.3.0",   "commit": "d9455ff7db73b694db7d412e49a68bec767f2b5a" }`

### 1.15(/auth/.well-known/openid-configuration) — Authelia surface /auth/.well-known/openid-configuration

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/.well-known/openid-configuration-True]`

Exposed via /auth/* reverse_proxy. Status 200.

**Details:**

- path: `/auth/.well-known/openid-configuration`
- status_code: `200`
- body_excerpt: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/o`

**Evidence:**

- `GET https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/flash?x=1` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&amp;rm=GET">302 Found</a>`
- `OPTIONS https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`

### 1.15(/auth/jwks.json) — Authelia surface /auth/jwks.json

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/jwks.json-True]`

Exposed via /auth/* reverse_proxy. Status 200.

**Details:**

- path: `/auth/jwks.json`
- status_code: `200`
- body_excerpt: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47`

**Evidence:**

- `GET https://111.88.145.138/flash?x=1` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&rm=GET, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&amp;rm=GET">302 Found</a>`
- `OPTIONS https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`

### 1.15(/auth/api/health) — Authelia surface /auth/api/health

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/api/health-True]`

Exposed via /auth/* reverse_proxy. Status 200.

**Details:**

- path: `/auth/api/health`
- status_code: `200`
- body_excerpt: `{"status":"OK"}`

**Evidence:**

- `OPTIONS https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK"}`

### 1.15(/auth/api/state) — Authelia surface /auth/api/state

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/api/state-None]`

Exposed via /auth/* reverse_proxy. Status 200.

**Details:**

- path: `/auth/api/state`
- status_code: `200`
- body_excerpt: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`

**Evidence:**

- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=n2RrM7...(32 chars); expires=Fri, 22 May 2026 11:25:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`

### 1.15(/auth/api/configuration) — Authelia surface /auth/api/configuration

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_15_authelia_surface[/auth/api/configuration-None]`

Exposed via /auth/* reverse_proxy. Status 403.

**Details:**

- path: `/auth/api/configuration`
- status_code: `403`
- body_excerpt: `403 Forbidden`

**Evidence:**

- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`
- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8
  - resp body: `403 Forbidden`

### 5.4 — /api/public/server-info field inventory

- Severity: **Informational**
- Status: `informational`
- Test: `test_02_disclosure.py::test_5_4_server_info_fields`

Fields returned to anonymous callers — review for unexpected additions.

**Details:**

- status_code: `200`
- keys: `['chisel', 'forward_tunnels', 'git_sha', 'loki', 'version']`

**Evidence:**

- `GET https://111.88.145.138/this-route-definitely-does-not-exist` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>lab-bridge — Home</title>    <script>     (function () {       var t = localStorage.getItem('th…`
- `GET https://111.88.145.138/healthz` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.16.1","git_sha":"6cedd9aa90d4e1d779e8cebbdaa0112f1c77…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.16.1","git_sha":"6cedd9aa90d4e1d779e8cebbdaa0112f1c77…`

### 5.7 — TLS protocol and cipher

- Severity: **Informational**
- Status: `informational`
- Test: `test_02_disclosure.py::test_5_7_tls_protocols`

Negotiated TLSv1.3 / TLS_AES_128_GCM_SHA256

**Details:**

- protocol: `TLSv1.3`
- cipher: `('TLS_AES_128_GCM_SHA256', 'TLSv1.3', 128)`
- cert_len: `842`

**Evidence:**

_(no recorded exchanges)_

### 7.2 — Caddy admin /config/ unreachable

- Severity: **Informational**
- Status: `informational`
- Test: `test_04_direct_ports.py::test_7_2_caddy_admin_http`

Port 2019 closed; admin surface not exposed.

**Details:**

- port: `2019`
- open: `False`

**Evidence:**

_(no recorded exchanges)_

### 7.4 — Chisel server port 7000

- Severity: **Informational**
- Status: `informational`
- Test: `test_04_direct_ports.py::test_7_4_chisel_port_documented`

Chisel port is intentionally public for SerialHop reverse tunnels.

**Details:**

- port: `7000`
- open: `True`

**Evidence:**

_(no recorded exchanges)_

### 3.5 — Tokens are not interchangeable across endpoints

- Severity: **Informational**
- Status: `informational`
- Test: `test_05_bearer.py::test_3_5_token_separation`

Confirms a single bogus value is rejected on both endpoints.

**Details:**

- flash_status: `401`
- agent_status: `401`

**Evidence:**

- `POST https://111.88.145.138/flash/api/v1/firmware` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=111173d2a9e4cfd53b8dcf80ea0559d4
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=b4f03f958b769920172a869cdf7fd432
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/flash/api/v1/firmware` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=e8fb0d26a5772e1c0570c46e296b1b64
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`

### 2.3 — Logging out one session does not kill other sessions

- Severity: **Informational**
- Status: `informational`
- Test: `test_06_session.py::test_2_3_concurrent_sessions_independent`

Per-session invalidation, not user-global, is the documented behaviour.

**Details:**

- distinct_cookies: `True`
- b_status_after_a_logout: `200`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 114
  - req body: `{"username":"khamitovdr","password":"U$rKtI3N2M*5*Wg","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=$6ta_f...(32 chars); expires=Thu, 20 Aug 2026 10:26:20 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=$6ta_f...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax

### 2.12 — GET /logout enables CSRF-logout

- Severity: **Informational**
- Status: `informational`
- Test: `test_06_session.py::test_2_12_get_logout_csrf`

GET-based logout means a third-party page can log the user out via <img src=>. Low impact; documented in siteapp/app/auth.py.

**Details:**

- status_code: `302`
- method: `GET`

**Evidence:**

- `POST https://111.88.145.138/api/auth/firstfactor` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, content-type: application/json, origin: https://111.88.145.138, referer: https://111.88.145.138/login, content-length: 114
  - req body: `{"username":"khamitovdr","password":"U$rKtI3N2M*5*Wg","targetURL":"/","requestMethod":"GET","keepMeLoggedIn":true}`
  - resp headers: content-type: application/json, set-cookie: authelia_session=tzdxHc...(32 chars); expires=Thu, 20 Aug 2026 10:26:27 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=tzdxHc...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; SameSite=Lax

### 6.1 — Brute-force regulation triggers within max_retries+2

- Severity: **Informational**
- Status: `vulnerable`
- Test: `test_07_state.py::test_6_1_brute_force_regulation`

Authelia is configured with max_retries=3, ban_time=5m. After 3 wrongs, response should change.

**Details:**

- probe_user: `bf-probe-6de55724`
- statuses: `[401, 401, 401, 401, 401]`
- distinct_responses: `False`

**Evidence:**

- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=b4f03f958b769920172a869cdf7fd432
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/flash/api/v1/firmware` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=n2RrM7...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=e8fb0d26a5772e1c0570c46e296b1b64
  - req body: `<unreadable>`
  - resp headers: content-type: application/json
  - resp body: `{"detail":"Unauthorized"}`
- `GET https://111.88.145.138/flash/api/v1/firmware` → `422`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=n2RrM7...(32 chars)
  - resp headers: content-type: application/json
  - resp body: `{"detail":[{"type":"missing","loc":["query","sha256"],"msg":"Field required","input":null}]}`
- `GET https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=AAAAAA...(64 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=GET, set-cookie: authelia_session=AAAAAA...(64 chars); expires=Fri, 22 May 2026 11:26:23 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=GET">302 Found</a>`

### 6.3 — Admin completes OIDC handshake into Grafana

- Severity: **Informational**
- Status: `informational`
- Test: `test_07_state.py::test_6_3_oidc_admin_handshake`

Authelia OIDC → Grafana should complete in ≤5 hops with a 200 or final auth cookie.

**Details:**

- statuses: `[302, 307, 302, 303, 302, 200]`

**Evidence:**

- `GET https://111.88.145.138/grafana/login` → `307`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=A0ybs3...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login/generic_oauth
  - resp body: `<a href="/grafana/login/generic_oauth">Temporary Redirect</a>.  `
- `GET https://111.88.145.138/grafana/login/generic_oauth` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=A0ybs3...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=U2WxEc4bn4M5i5GYp1UeypgJlrXuq7nx5W-6lzaVO-Q&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=l5gWSj6Xbhd6ORU7KzMJ8tjkvy7-7M4O4Zg4HvTY6ZA%3D, set-cookie: oauth_state=4a572b...(64 chars); Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, oauth_code_verifier=wxr6six1wGQumxzLyUE_Z_xU59sicKFaAVc0QuqFjit-gkb-eOYbrGWLUxuB1O2_c4cMYxQG0s-5T59nRS0QZvoSPrnHPamoHkSrun8Ffs4iv5Shb9D_WpXpZxS8yIH7; Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&amp;code_challenge=U2WxEc4bn4M5i5GYp1UeypgJlrXuq7nx5W-6lzaVO-Q&amp;code_challenge_method=S256&amp;redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fge…`
- `GET https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=U2WxEc4bn4M5i5GYp1UeypgJlrXuq7nx5W-6lzaVO-Q&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=l5gWSj6Xbhd6ORU7KzMJ8tjkvy7-7M4O4Zg4HvTY6ZA%3D` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=A0ybs3...(32 chars)
  - resp headers: location: https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_h2oOZUqTdzF6lPLXsD_ar5ewjuT3wiNkrWBXzsxP9_8.-qLivupYSnm-xBp_EqfGFcXe4RDlHPsTimtFiqQdGzM&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=l5gWSj6Xbhd6ORU7KzMJ8tjkvy7-7M4O4Zg4HvTY6ZA%3D
- `GET https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_h2oOZUqTdzF6lPLXsD_ar5ewjuT3wiNkrWBXzsxP9_8.-qLivupYSnm-xBp_EqfGFcXe4RDlHPsTimtFiqQdGzM&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=l5gWSj6Xbhd6ORU7KzMJ8tjkvy7-7M4O4Zg4HvTY6ZA%3D` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); oauth_state=4a572b...(64 chars); oauth_code_verifier=wxr6si...(128 chars); authelia_session=A0ybs3...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/, set-cookie: oauth_state=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, oauth_code_verifier=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, grafana_session=576b61d675dcfc3db1b06a249e66f8bb; Path=/grafana; Max-Age=2592000; HttpOnly; SameSite=Lax, grafana_session_expiry=1779446186; Path=/grafana; Max-Age=2592000; SameSite=Lax, redirect_to=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax
  - resp body: `<a href="/grafana/">Found</a>.  `
- `GET https://111.88.145.138/grafana/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: grafana_session=576b61...(32 chars); grafana_session_expiry=177944...(10 chars); authelia_session=A0ybs3...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8
  - resp body: `<!DOCTYPE html> <html lang="en-US">   <head>          <meta charset="utf-8" />     <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />     <meta name="viewport" content="width=device-width" />     <meta name="theme-color" conte…`

### 6.4 — Researcher completes OIDC handshake into Grafana

- Severity: **Informational**
- Status: `informational`
- Test: `test_07_state.py::test_6_4_oidc_researcher_handshake`

Researcher group must also complete OIDC and land in Grafana.

**Details:**

- statuses: `[302, 307, 302, 303, 302, 200]`

**Evidence:**

- `GET https://111.88.145.138/grafana/login` → `307`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=m7gduT...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login/generic_oauth
  - resp body: `<a href="/grafana/login/generic_oauth">Temporary Redirect</a>.  `
- `GET https://111.88.145.138/grafana/login/generic_oauth` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=m7gduT...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=0iyrAsGyosb4qsW1sHVDAocMMmMLCp17ceNZqKDd6nk&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=7B6DkuRv2ubeuMKm27Hhj75L5RnOVm806b6qax86nIQ%3D, set-cookie: oauth_state=923f94...(64 chars); Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, oauth_code_verifier=lB0k1YAyUstEjDMCcszn18lcPUQde2nmOgDXBVJSyohsTf091WdUK-w7rhlfDId-1OaFlHPbDqsDjdmxJzPAL-Vr5XbU0H5nU3JCjfjcLTNqo8sw4FXuQ1MuQydfRuO7; Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax
  - resp body: `<a href="https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&amp;code_challenge=0iyrAsGyosb4qsW1sHVDAocMMmMLCp17ceNZqKDd6nk&amp;code_challenge_method=S256&amp;redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fge…`
- `GET https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=0iyrAsGyosb4qsW1sHVDAocMMmMLCp17ceNZqKDd6nk&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=7B6DkuRv2ubeuMKm27Hhj75L5RnOVm806b6qax86nIQ%3D` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=m7gduT...(32 chars)
  - resp headers: location: https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_Yu-VdgM8tldFRL8eh97jMp7k4qxyFJlTaKXDofovNN0.I7rNymoX4U-gnR24h8FAL62cNQFFkCv0Onx9FOklrcE&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=7B6DkuRv2ubeuMKm27Hhj75L5RnOVm806b6qax86nIQ%3D
- `GET https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_Yu-VdgM8tldFRL8eh97jMp7k4qxyFJlTaKXDofovNN0.I7rNymoX4U-gnR24h8FAL62cNQFFkCv0Onx9FOklrcE&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=7B6DkuRv2ubeuMKm27Hhj75L5RnOVm806b6qax86nIQ%3D` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); oauth_state=923f94...(64 chars); oauth_code_verifier=lB0k1Y...(128 chars); authelia_session=m7gduT...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/, set-cookie: oauth_state=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, oauth_code_verifier=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, grafana_session=75a57c863bb239c6850757bbc444275f; Path=/grafana; Max-Age=2592000; HttpOnly; SameSite=Lax, grafana_session_expiry=1779446188; Path=/grafana; Max-Age=2592000; SameSite=Lax, redirect_to=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax
  - resp body: `<a href="/grafana/">Found</a>.  `
- `GET https://111.88.145.138/grafana/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: grafana_session=75a57c...(32 chars); grafana_session_expiry=177944...(10 chars); authelia_session=m7gduT...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8
  - resp body: `<!DOCTYPE html> <html lang="en-US">   <head>          <meta charset="utf-8" />     <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />     <meta name="viewport" content="width=device-width" />     <meta name="theme-color" conte…`

## Passed controls

<details>
<summary>Click to expand</summary>

- `1.1` — Anonymous GET /flash/ must require auth (`test_01_routing.py::test_1_1_anon_flash_index`)
- `1.2` — /flash/api/firmware must require admin auth (`test_01_routing.py::test_1_2_anon_flash_api_firmware`)
- `1.3` — /flash/api/v1/* is bearer-only, not Authelia-gated (`test_01_routing.py::test_1_3_anon_flash_api_v1`)
- `1.4` — POST /flash/api/firmware (operator) must require admin (`test_01_routing.py::test_1_4_anon_flash_api_firmware_post`)
- `1.5` — Researcher must not access /flash/ (`test_01_routing.py::test_1_5_researcher_flash`)
- `1.8` — Anonymous /jupyter/api/* must redirect to /login (`test_01_routing.py::test_1_8_anon_jupyter_api`)
- `1.9` — Anonymous /grafana/api/datasources must require auth (`test_01_routing.py::test_1_9_anon_grafana_datasources`)
- `1.11(/FLASH/)` — Case-mutated path /FLASH/ must not match (`test_01_routing.py::test_1_11_case_mutation[/FLASH/]`)
- `1.11(/Flash/api/v1/firmware)` — Case-mutated path /Flash/api/v1/firmware must not match (`test_01_routing.py::test_1_11_case_mutation[/Flash/api/v1/firmware]`)
- `1.11(/FLASH/api/firmware)` — Case-mutated path /FLASH/api/firmware must not match (`test_01_routing.py::test_1_11_case_mutation[/FLASH/api/firmware]`)
- `1.12(/flash/../grafana)` — Path traversal /flash/../grafana must not bypass auth (`test_01_routing.py::test_1_12_path_traversal[/flash/../grafana]`)
- `1.12(/grafana/%2e%2e/flash)` — Path traversal /grafana/%2e%2e/flash must not bypass auth (`test_01_routing.py::test_1_12_path_traversal[/grafana/%2e%2e/flash]`)
- `1.12(/flash/./api/firmware)` — Path traversal /flash/./api/firmware must not bypass auth (`test_01_routing.py::test_1_12_path_traversal[/flash/./api/firmware]`)
- `1.13(/flash)` — Trailing-slash variant /flash must require auth (`test_01_routing.py::test_1_13_trailing_slash[/flash]`)
- `1.13(/flash/)` — Trailing-slash variant /flash/ must require auth (`test_01_routing.py::test_1_13_trailing_slash[/flash/]`)
- `1.13(/flash?x=1)` — Trailing-slash variant /flash?x=1 must require auth (`test_01_routing.py::test_1_13_trailing_slash[/flash?x=1]`)
- `1.14(OPTIONS /flash/)` — OPTIONS /flash/ must enforce same auth as GET (`test_01_routing.py::test_1_14_method_confusion[OPTIONS-/flash/]`)
- `1.14(HEAD /flash/api/firmware)` — HEAD /flash/api/firmware must enforce same auth as GET (`test_01_routing.py::test_1_14_method_confusion[HEAD-/flash/api/firmware]`)
- `5.2` — /healthz must not be reachable through Caddy (`test_02_disclosure.py::test_5_2_healthz_not_exposed`)
- `5.3` — No Python tracebacks in API responses (`test_02_disclosure.py::test_5_3_no_traceback`)
- `5.5` — attempted_path reflected XSS in 404/403 (`test_02_disclosure.py::test_5_5_attempted_path_xss`)
- `5.8(/loki/api/v1/labels)` — Internal observability path /loki/api/v1/labels must not be reachable (`test_02_disclosure.py::test_5_8_internal_observability_not_exposed[/loki/api/v1/labels]`)
- `5.8(/prometheus/)` — Internal observability path /prometheus/ must not be reachable (`test_02_disclosure.py::test_5_8_internal_observability_not_exposed[/prometheus/]`)
- `5.8(/api/datasources/proxy/1/)` — Internal observability path /api/datasources/proxy/1/ must not be reachable (`test_02_disclosure.py::test_5_8_internal_observability_not_exposed[/api/datasources/proxy/1/]`)
- `4.1` — X-Forwarded-User / Remote-Groups must not grant access (`test_03_smuggling.py::test_4_1_xforwarded_user_injection`)
- `4.2` — X-Forwarded-Host on /login must not influence rendered form action (`test_03_smuggling.py::test_4_2_xforwarded_host_login`)
- `4.3` — Manipulated X-Forwarded-Uri must not grant access on bad creds (`test_03_smuggling.py::test_4_3_xforwarded_uri_firstfactor`)
- `4.4` — Host header injection must not serve the platform under another name (`test_03_smuggling.py::test_4_4_host_header_injection`)
- `7.2019` — Port 2019 (Caddy admin API) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[2019-Caddy admin API]`)
- `7.9091` — Port 9091 (Authelia) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[9091-Authelia]`)
- `7.3000` — Port 3000 (Grafana) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[3000-Grafana]`)
- `7.8000` — Port 8000 (siteapp/flasher uvicorn) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[8000-siteapp/flasher uvicorn]`)
- `7.8888` — Port 8888 (JupyterLab) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[8888-JupyterLab]`)
- `7.3100` — Port 3100 (Loki) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[3100-Loki]`)
- `7.9090` — Port 9090 (Prometheus) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[9090-Prometheus]`)
- `7.9100` — Port 9100 (node-exporter) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[9100-node-exporter]`)
- `7.8080` — Port 8080 (cadvisor) must not be reachable from the internet (`test_04_direct_ports.py::test_7_internal_port_closed[8080-cadvisor]`)
- `3.1` — /flash/api/v1/firmware without bearer must 401 (`test_05_bearer.py::test_3_1_flasher_bearer_missing`)
- `3.2` — /flash/api/v1/firmware with wrong bearer must 401 (`test_05_bearer.py::test_3_2_flasher_bearer_wrong`)
- `3.3` — POST /api/agent/upload without auth must 401 (`test_05_bearer.py::test_3_3_agent_upload_no_auth`)
- `3.4` — POST /api/agent/upload with wrong bearer must 401 (`test_05_bearer.py::test_3_4_agent_upload_wrong_bearer`)
- `2.4` — Login Set-Cookie attribute hygiene (`test_06_session.py::test_2_4_login_cookie_attributes`)
- `2.6` — Forged authelia_session cookie must be rejected (`test_06_session.py::test_2_6_forged_cookie_rejected`)
- `2.7` — Truncated valid cookie must be rejected (`test_06_session.py::test_2_7_truncated_cookie_rejected`)
- `2.9` — Cookie scope is per-user, role gating works (`test_06_session.py::test_2_9_cross_role_cookie`)
- `2.10` — Session fixation: login issues a fresh cookie (`test_06_session.py::test_2_10_session_fixation`)

</details>

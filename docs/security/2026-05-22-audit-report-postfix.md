# lab-bridge security audit report

- Target: `https://111.88.145.138`
- Run at: 2026-05-22T20:55:30+00:00
- Git SHA: `unknown`
- TLS verification disabled: `true`
- --slow enabled: `False`

## Executive summary

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 3 |
| Informational | 16 |

Passed controls: 54

## Medium findings

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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`
- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `403 Forbidden`
- `GET https://111.88.145.138/auth/api/password-reset/identity/start` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `404 Not Found`

### 5.6 — Open-redirect via /login?rd=

- Severity: **Low**
- Status: `informational`
- Test: `test_02_disclosure.py::test_5_6_open_redirect`

The login form sets `rd` as a query param. Real exploit requires a successful login that 302s to the value — only a finding if the final redirect leaves the VPS host. We capture the page render here; full flow tested via session class.

**Details:**

- status_code: `200`
- body_has_rd: `True`

**Evidence:**

- `GET https://111.88.145.138/healthz` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.17.0","git_sha":"d6f85fb106b8598f6d49e1e22eca0b83077a…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.17.0","git_sha":"d6f85fb106b8598f6d49e1e22eca0b83077a…`
- `GET https://111.88.145.138/%3Cscript%3Ealert(1)%3C/script%3E` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/login?rd=https%3A%2F%2Fevil.example%2F` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Sign in — lab-bridge</title>    <script>     (function () {       var t = localStorage.getItem(…`

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
  - resp headers: content-type: application/json, set-cookie: authelia_session=jhoTla...(32 chars); expires=Thu, 20 Aug 2026 20:54:43 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/flash/` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=jhoTla...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Forbidden — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `POST https://111.88.145.138/flash/api/firmware` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=jhoTla...(32 chars), content-length: 93, content-type: application/json
  - req body: `{"name":"audit-probe","description":"","firmware":":020000040000FA\n:00000001FF\n","tags":[]}`
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Forbidden — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/grafana/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=jhoTla...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login, set-cookie: redirect_to=%2Fgra...(13 chars); Path=/grafana; HttpOnly; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="/grafana/login">Found</a>.  `
- `GET https://111.88.145.138/jupyter/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=jhoTla...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8, location: /jupyter/lab?, strict-transport-security: max-age=31536000; includeSubDomains

### 1.10 — /grafana/api/health is public (documented exception)

- Severity: **Informational**
- Status: `informational`
- Test: `test_01_routing.py::test_1_10_grafana_health_public`

Health check used by deploy.sh; must stay public.

**Details:**

- status_code: `200`

**Evidence:**

- `GET https://111.88.145.138/flash/api/v1/firmware?sha256=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"error":"bearer required","detail":"Authorization: Bearer <token> required"}`
- `POST https://111.88.145.138/flash/api/firmware` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars), content-length: 2, content-type: application/json
  - req body: `{}`
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=POST, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:42 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&amp;rm=POST">303 See Other</a>`
- `GET https://111.88.145.138/jupyter/api/contents/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fjupyter%2Fapi%2Fcontents%2F&rm=GET, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fjupyter%2Fapi%2Fcontents%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/grafana/api/datasources` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fgrafana%2Fapi%2Fdatasources&rm=GET, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fgrafana%2Fapi%2Fdatasources&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/grafana/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=UTF-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=GET, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=GET">302 Found</a>`
- `GET https://111.88.145.138/flash?x=1` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&rm=GET, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&amp;rm=GET">302 Found</a>`
- `OPTIONS https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&rm=GET, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%3Fx%3D1&amp;rm=GET">302 Found</a>`
- `OPTIONS https://111.88.145.138/flash/` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&rm=OPTIONS, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2F&amp;rm=OPTIONS">302 Found</a>`
- `HEAD https://111.88.145.138/flash/api/firmware` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: location: https://111.88.145.138/login?rd=https%3A%2F%2F111.88.145.138%2Fflash%2Fapi%2Ffirmware&rm=HEAD, set-cookie: authelia_session=CsLa!d...(32 chars); expires=Fri, 22 May 2026 21:54:45 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/auth/.well-known/openid-configuration` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"issuer":"https://111.88.145.138","jwks_uri":"https://111.88.145.138/jwks.json","authorization_endpoint":"https://111.88.145.138/api/oidc/authorization","token_endpoint":"https://111.88.145.138/api/oidc/token","subject_types_supported":["p…`
- `GET https://111.88.145.138/auth/jwks.json` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"keys":[{"use":"sig","kty":"RSA","kid":"db558f-rs256","alg":"RS256","n":"8q1EhyZCaFC5hSpyVGafErzuSHvQ8j0Z7GOw3gKGMWUae5bAypXDWFZKFGO2cqqR4ulpGI1T59gKZ7JCTW6haFbB63HS3FBAJ5CXrUll8zLNDohAd62xb7EmOFjJ47vFfZj2dPot3UwU8o2jYL6mvxCzFFwLB3YLj8TWtQ…`
- `GET https://111.88.145.138/auth/api/health` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"status":"OK"}`
- `GET https://111.88.145.138/auth/api/state` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"status":"OK","data":{"username":"","authentication_level":0,"default_redirection_url":"https://111.88.145.138/"}}`
- `GET https://111.88.145.138/auth/api/configuration` → `403`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/plain; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
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

- `GET https://111.88.145.138/this-route-definitely-does-not-exist` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>lab-bridge — Home</title>    <script>     (function () {       var t = localStorage.getItem('th…`
- `GET https://111.88.145.138/healthz` → `404`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8
  - resp body: `<!doctype html> <html lang="en"> <head>   <meta charset="utf-8">   <meta name="viewport" content="width=device-width, initial-scale=1">   <title>Not found — lab-bridge</title>    <script>     (function () {       var t = localStorage.getIte…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.17.0","git_sha":"d6f85fb106b8598f6d49e1e22eca0b83077a…`
- `GET https://111.88.145.138/api/public/server-info` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars)
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"chisel":{"listen_port":7000},"loki":{"push_url":"http://127.0.0.1:3100/loki/api/v1/push"},"forward_tunnels":[{"name":"loki","local":"127.0.0.1:3100","remote":"loki:3100"}],"version":"0.17.0","git_sha":"d6f85fb106b8598f6d49e1e22eca0b83077a…`

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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=CsLa!d...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=CsLa!d...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=9346f37aebd80af21f2cf405588a7b86
  - req body: `<unreadable>`
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=CsLa!d...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=4115a7d3a6382f3698c39b7e783bad49
  - req body: `<unreadable>`
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"detail":"Unauthorized"}`
- `POST https://111.88.145.138/flash/api/v1/firmware` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=CsLa!d...(32 chars), content-length: 56, content-type: application/json
  - req body: `{"name":"x","firmware":":020000040000FA\n:00000001FF\n"}`
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"error":"bearer invalid","detail":"token does not match"}`
- `POST https://111.88.145.138/api/agent/upload` → `401`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, authorization: Bearer <redacted>, cookie: authelia_session=CsLa!d...(32 chars), content-length: 284, content-type: multipart/form-data; boundary=d7c7687dddc5b0a7208389a096a676be
  - req body: `<unreadable>`
  - resp headers: content-type: application/json, strict-transport-security: max-age=31536000; includeSubDomains
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
  - resp headers: content-type: application/json, set-cookie: authelia_session=fuwYBo...(32 chars); expires=Thu, 20 Aug 2026 20:55:20 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=fuwYBo...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; Secure; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; Secure; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; Secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains

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
  - resp headers: content-type: application/json, set-cookie: authelia_session=2hBFr%...(32 chars); expires=Thu, 20 Aug 2026 20:55:25 GMT; domain=111.88.145.138; path=/; HttpOnly; secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `{"redirect":"/"}`
- `GET https://111.88.145.138/logout` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=2hBFr%...(32 chars)
  - resp headers: location: /, set-cookie: authelia_session=; Max-Age=0; domain=111.88.145.138; path=/; HttpOnly; Secure; SameSite=Lax, grafana_session=; Max-Age=0; path=/grafana; HttpOnly; Secure; SameSite=Lax, grafana_session_expiry=; Max-Age=0; path=/grafana; HttpOnly; Secure; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains

### 6.3 — Admin completes OIDC handshake into Grafana

- Severity: **Informational**
- Status: `informational`
- Test: `test_07_state.py::test_6_3_oidc_admin_handshake`

Authelia OIDC → Grafana should complete in ≤5 hops with a 200 or final auth cookie.

**Details:**

- statuses: `[302, 307, 302, 303, 302, 200]`

**Evidence:**

- `GET https://111.88.145.138/grafana/login` → `307`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=VD-Gov...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login/generic_oauth, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="/grafana/login/generic_oauth">Temporary Redirect</a>.  `
- `GET https://111.88.145.138/grafana/login/generic_oauth` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=VD-Gov...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=CEEGLBw2FQlsZ16hW-by00yz5WHqQKCDzDMOJuBEyXM&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=yw4U3yopgw4svS_NYWjtX1sY6Bca0N_A5E8qPT-7Evo%3D, set-cookie: oauth_state=1cda38...(64 chars); Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, oauth_code_verifier=IA7zsqjsczXwKH7B6osVbDhlYXuHFDD4TJ2ifh_tL-zS9hzxlqiSCp8Vu5SmVQesPQl_1hx9112zgnef4WKvoZKAI4D6vd6V3K4J4nykU6h5ljRBliAJeTw3qjKL-UhU; Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&amp;code_challenge=CEEGLBw2FQlsZ16hW-by00yz5WHqQKCDzDMOJuBEyXM&amp;code_challenge_method=S256&amp;redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fge…`
- `GET https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=CEEGLBw2FQlsZ16hW-by00yz5WHqQKCDzDMOJuBEyXM&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=yw4U3yopgw4svS_NYWjtX1sY6Bca0N_A5E8qPT-7Evo%3D` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=VD-Gov...(32 chars)
  - resp headers: location: https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_w9T3TMQHotuQxn9qAd37_CIjxzhHwbfKn4T9ggnznZ0.YJcdB5DPgeVN02m-6uxjRuyGEmy_KqniBhg3SL75RXo&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=yw4U3yopgw4svS_NYWjtX1sY6Bca0N_A5E8qPT-7Evo%3D, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac_w9T3TMQHotuQxn9qAd37_CIjxzhHwbfKn4T9ggnznZ0.YJcdB5DPgeVN02m-6uxjRuyGEmy_KqniBhg3SL75RXo&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=yw4U3yopgw4svS_NYWjtX1sY6Bca0N_A5E8qPT-7Evo%3D` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); oauth_state=1cda38...(64 chars); oauth_code_verifier=IA7zsq...(128 chars); authelia_session=VD-Gov...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/, set-cookie: oauth_state=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, oauth_code_verifier=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, grafana_session=c6baef195577fe9779f0edbdac15ae28; Path=/grafana; Max-Age=2592000; HttpOnly; SameSite=Lax, grafana_session_expiry=1779483924; Path=/grafana; Max-Age=2592000; SameSite=Lax, redirect_to=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="/grafana/">Found</a>.  `
- `GET https://111.88.145.138/grafana/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: grafana_session=c6baef...(32 chars); grafana_session_expiry=177948...(10 chars); authelia_session=VD-Gov...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8, strict-transport-security: max-age=31536000; includeSubDomains
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
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=lVH8EP...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/login/generic_oauth, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="/grafana/login/generic_oauth">Temporary Redirect</a>.  `
- `GET https://111.88.145.138/grafana/login/generic_oauth` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); authelia_session=lVH8EP...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=iRv_d_UeDqebEx9ixXrBtTuISNUDYRbh8xP9X5HoP8g&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=5RDFNhFBMXns1rmwrFO8PZhZY128VVLaBEoInRORhcA%3D, set-cookie: oauth_state=819fe0...(64 chars); Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, oauth_code_verifier=sOfSIPSzIbx02S0cb9xfKz6SNCXLTFBiN5nVXpYLKQD64QDicjSatDDo59I84QmXiBuHukZRMYtsMnM7LOVF8cr72hiLwP1BXDSq8FY5DoMxlGOzF1-Iy2NhsiHqpT4v; Path=/grafana; Max-Age=600; HttpOnly; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&amp;code_challenge=iRv_d_UeDqebEx9ixXrBtTuISNUDYRbh8xP9X5HoP8g&amp;code_challenge_method=S256&amp;redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fge…`
- `GET https://111.88.145.138/auth/api/oidc/authorization?client_id=grafana&code_challenge=iRv_d_UeDqebEx9ixXrBtTuISNUDYRbh8xP9X5HoP8g&code_challenge_method=S256&redirect_uri=https%3A%2F%2F111.88.145.138%2Fgrafana%2Flogin%2Fgeneric_oauth&response_type=code&scope=openid+profile+email+groups&state=5RDFNhFBMXns1rmwrFO8PZhZY128VVLaBEoInRORhcA%3D` → `303`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: authelia_session=lVH8EP...(32 chars)
  - resp headers: location: https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac__9CJfnF7r6U8jP8khD3DHv0z4RKi8pkpDBqfBzwEtPY.lKQi_ST6phwihvxg6J9mWnnfIV8nZKDy0a1ox9WGgus&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=5RDFNhFBMXns1rmwrFO8PZhZY128VVLaBEoInRORhcA%3D, strict-transport-security: max-age=31536000; includeSubDomains
- `GET https://111.88.145.138/grafana/login/generic_oauth?code=authelia_ac__9CJfnF7r6U8jP8khD3DHv0z4RKi8pkpDBqfBzwEtPY.lKQi_ST6phwihvxg6J9mWnnfIV8nZKDy0a1ox9WGgus&iss=https%3A%2F%2F111.88.145.138&scope=openid+profile+email+groups&state=5RDFNhFBMXns1rmwrFO8PZhZY128VVLaBEoInRORhcA%3D` → `302`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: redirect_to=%2Fgra...(13 chars); oauth_state=819fe0...(64 chars); oauth_code_verifier=sOfSIP...(128 chars); authelia_session=lVH8EP...(32 chars)
  - resp headers: content-type: text/html; charset=utf-8, location: /grafana/, set-cookie: oauth_state=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, oauth_code_verifier=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, grafana_session=9b0909b2da0fd4bc1d439df5644016c9; Path=/grafana; Max-Age=2592000; HttpOnly; SameSite=Lax, grafana_session_expiry=1779483925; Path=/grafana; Max-Age=2592000; SameSite=Lax, redirect_to=; Path=/grafana; Max-Age=0; HttpOnly; SameSite=Lax, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<a href="/grafana/">Found</a>.  `
- `GET https://111.88.145.138/grafana/` → `200`
  - req headers: host: 111.88.145.138, accept: */*, accept-encoding: gzip, deflate, connection: keep-alive, user-agent: python-httpx/0.28.1, cookie: grafana_session=9b0909...(32 chars); grafana_session_expiry=177948...(10 chars); authelia_session=lVH8EP...(32 chars)
  - resp headers: content-type: text/html; charset=UTF-8, strict-transport-security: max-age=31536000; includeSubDomains
  - resp body: `<!DOCTYPE html> <html lang="en-US">   <head>          <meta charset="utf-8" />     <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />     <meta name="viewport" content="width=device-width" />     <meta name="theme-color" conte…`

## Passed controls

<details>
<summary>Click to expand</summary>

- `1.1` — Anonymous GET /flash/ must require auth (`test_01_routing.py::test_1_1_anon_flash_index`)
- `1.2` — /flash/api/firmware must require admin auth (`test_01_routing.py::test_1_2_anon_flash_api_firmware`)
- `1.3` — /flash/api/v1/* is bearer-only, not Authelia-gated (`test_01_routing.py::test_1_3_anon_flash_api_v1`)
- `1.4` — POST /flash/api/firmware (operator) must require admin (`test_01_routing.py::test_1_4_anon_flash_api_firmware_post`)
- `1.5` — Researcher must not access /flash/ (`test_01_routing.py::test_1_5_researcher_flash`)
- `1.6` — Researcher POST /flash/api/firmware must be denied by Authelia (`test_01_routing.py::test_1_6_researcher_flash_post`)
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
- `5.0` — Status-code masquerading: 403/404 pages served at HTTP 200 (`test_02_disclosure.py::test_5_0_status_code_masquerading`)
- `5.1` — Security headers on the platform root (`test_02_disclosure.py::test_5_1_security_headers`)
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
- `3.7` — Bearer check ordering on /flash/api/v1/firmware (`test_05_bearer.py::test_3_7_bearer_validation_order`)
- `2.1` — Cookie replay after GET /logout must fail (`test_06_session.py::test_2_1_replay_after_get_logout`)
- `2.2` — Cookie replay after POST /logout must fail (`test_06_session.py::test_2_2_replay_after_post_logout`)
- `2.4` — Login Set-Cookie attribute hygiene (`test_06_session.py::test_2_4_login_cookie_attributes`)
- `2.5` — Logout-cleared cookies must include Secure (`test_06_session.py::test_2_5_logout_cookie_attributes`)
- `2.6` — Forged authelia_session cookie must be rejected (`test_06_session.py::test_2_6_forged_cookie_rejected`)
- `2.7` — Truncated valid cookie must be rejected (`test_06_session.py::test_2_7_truncated_cookie_rejected`)
- `2.9` — Cookie scope is per-user, role gating works (`test_06_session.py::test_2_9_cross_role_cookie`)
- `2.10` — Session fixation: login issues a fresh cookie (`test_06_session.py::test_2_10_session_fixation`)
- `6.1` — Brute-force regulation does not leak user existence (`test_07_state.py::test_6_1_brute_force_regulation`)

</details>

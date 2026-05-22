"""Auth-related routes for siteapp.

Hosts /login, /logout, /api/auth/firstfactor, /api/auth/whoami, and the
shared /_errors/{403,404} pages. All HTML routes extend base.html so the
global navbar (Caddy replace-response injection) shows up.

The firstfactor handler proxies to Authelia server-to-server. Authelia
treats the inbound headers (Host, X-Forwarded-*) as the source of truth for
the access-control resource match, so we forward them faithfully.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.templates import templates


def _target_path(target: str) -> str:
    # Authelia's /api/verify writes the *full* original URL into ?rd= on its
    # 303 to /login, so the login form's targetURL arrives here as
    # 'https://host/path'. Authelia in turn builds the requested URL as
    # X-Forwarded-Proto + X-Forwarded-Host + X-Forwarded-Uri, so a full-URL
    # X-Forwarded-Uri concatenates into 'https://hosthttps://host/path' and
    # fails session-cookie-domain matching — the 1FA attempt is rejected
    # with 'Authentication failed' before the password is ever checked.
    if target.startswith(("http://", "https://")):
        parts = urlsplit(target)
        path = parts.path or "/"
        return f"{path}?{parts.query}" if parts.query else path
    return target or "/"


def _forwarded_headers(request: Request, target_uri: str) -> dict[str, str]:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return {
        "X-Forwarded-Host": host,
        "X-Forwarded-Proto": proto,
        "X-Forwarded-Uri": target_uri,
        "X-Forwarded-Method": "GET",
    }


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    base = settings.authelia_url.rstrip("/")
    client = httpx.AsyncClient(base_url=base, timeout=5.0)

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(request: Request, rd: str = "/") -> HTMLResponse:
        return templates.TemplateResponse(request, "login.html", {"rd": rd})

    @router.post("/api/auth/firstfactor")
    async def firstfactor(request: Request) -> Response:
        payload: dict[str, Any] = await request.json()
        target = _target_path(payload.get("targetURL") or "/")
        body = {
            "username": payload.get("username", ""),
            "password": payload.get("password", ""),
            "targetURL": target,
            "requestMethod": "GET",
            "keepMeLoggedIn": bool(payload.get("keepMeLoggedIn", True)),
        }
        headers = _forwarded_headers(request, target)
        try:
            r = await client.post("/api/firstfactor", json=body, headers=headers)
        except httpx.RequestError as exc:
            return JSONResponse(
                {"error": f"authelia unreachable: {exc.__class__.__name__}"},
                status_code=502,
            )
        resp = JSONResponse(
            {"redirect": target} if r.status_code == 200 else r.json(),
            status_code=r.status_code,
        )
        # Pipe Set-Cookie through (FastAPI strips it from the constructor).
        for key, value in r.headers.multi_items():
            if key.lower() == "set-cookie":
                resp.raw_headers.append((b"set-cookie", value.encode("latin-1")))
        return resp

    @router.get("/api/auth/whoami")
    async def whoami(
        request: Request,
        authelia_session: str | None = Cookie(default=None),
    ) -> JSONResponse:
        if not authelia_session:
            return JSONResponse({"user": None})
        # Use a fixed sentinel URI that any authenticated user can access
        # (see access_control rule for ^/api/auth/whoami$).  The proto must
        # be https because Authelia issues secure cookies tied to the TLS
        # session domain; in prod Caddy provides https, so we hardcode it here.
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        verify_headers = {
            "Cookie": f"authelia_session={authelia_session}",
            "X-Forwarded-Host": host,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Uri": "/api/auth/whoami",
            "X-Forwarded-Method": "GET",
        }
        try:
            r = await client.get("/api/verify", headers=verify_headers)
        except httpx.RequestError:
            return JSONResponse({"user": None})
        if r.status_code != 200:
            return JSONResponse({"user": None})
        user = r.headers.get("remote-user")
        groups_header = r.headers.get("remote-groups", "")
        groups = [g.strip() for g in groups_header.split(",") if g.strip()]
        return JSONResponse(
            {
                "user": user,
                "groups": groups,
                "display_name": r.headers.get("remote-name"),
                "email": r.headers.get("remote-email"),
            }
        )

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
        # Expire the authelia_session cookie. Domain-scoped to match the one
        # Authelia set; the browser only deletes a cookie when (name, domain,
        # path) all match.
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
        return resp

    def _attempted_path(request: Request) -> str:
        # Caddy's handle_errors rewrites to /_errors/{code}?path={http.request.orig_uri.path}.
        # (orig_uri.path, not orig_uri — the query string is intentionally stripped
        # to avoid splicing raw query params after ?path=.)
        # Direct hits (e2e, debugging) have no ?path= and fall back to the URI.
        return request.query_params.get("path") or request.url.path

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

    return router

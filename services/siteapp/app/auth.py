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

import httpx
from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.templates import templates


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
        target = payload.get("targetURL") or "/"
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
        # Authelia 4.38 /api/logout is POST-only; it invalidates the session
        # server-side but does not emit a Set-Cookie header.  We POST to
        # invalidate, then clear the client-side cookie ourselves.
        try:
            await client.post("/api/logout", headers={"Cookie": cookie})
        except httpx.RequestError:
            pass
        resp = RedirectResponse("/", status_code=302)
        # Expire the authelia_session cookie on the client.
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        domain = host.split(":")[0]  # strip port if present
        expire_cookie = (
            f"authelia_session=; Max-Age=0; domain={domain}; path=/; HttpOnly; SameSite=Lax"
        )
        resp.raw_headers.append((b"set-cookie", expire_cookie.encode("latin-1")))
        return resp

    @router.get("/_errors/403", response_class=HTMLResponse, include_in_schema=False)
    async def error_403(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "error_403.html", {})

    @router.get("/_errors/404", response_class=HTMLResponse, include_in_schema=False)
    async def error_404(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "error_404.html", {})

    return router

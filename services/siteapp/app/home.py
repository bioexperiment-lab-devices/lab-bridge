# app/home.py
from __future__ import annotations

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.labs import LabsAggregator
from app.strings import HOME_STRINGS, pick_lang
from app.templates import templates


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    aggregator = LabsAggregator(settings.agent_root, settings.clients_file)

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home(
        request: Request,
        lang: str | None = None,
        _panel: int | None = None,
        authelia_session: str | None = Cookie(default=None),
    ) -> HTMLResponse:
        chosen = pick_lang(lang, request.cookies.get("lang"))
        # Gate the Registered-labs panel on Authelia session presence. This is
        # a UX hide, not an auth boundary — /api/public/labs is itself public
        # — so we skip the /api/verify round-trip and just check the cookie.
        # Stale cookies briefly showing labs after logout is acceptable; the
        # 5s _panel poll re-evaluates and reverts to the hidden state.
        signed_in = bool(authelia_session)
        # Anonymous visitors don't see lab data, so don't pay the aggregator
        # cost (which fans out to every agent over the chisel tunnel).
        labs_initial = await aggregator.list_labs() if signed_in else []
        template_name = "_home_status_row.html" if _panel else "home.html"
        context: dict[str, object] = {
            "lang": chosen,
            "s": HOME_STRINGS[chosen],
            "labs_initial": labs_initial,
            "signed_in": signed_in,
        }
        if _panel:
            context["labs"] = labs_initial
        response = templates.TemplateResponse(request, template_name, context)
        if lang in ("en", "ru"):
            response.set_cookie(
                "lang",
                lang,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=True,
                httponly=True,
            )
        return response

    return router

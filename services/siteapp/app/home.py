# app/home.py
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.labs import LabsAggregator
from app.strings import HOME_STRINGS, pick_lang
from app.templates import templates


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    aggregator = LabsAggregator(settings.agent_root, settings.clients_file)

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home(request: Request, lang: str | None = None) -> HTMLResponse:
        chosen = pick_lang(lang, request.cookies.get("lang"))
        labs_initial = await aggregator.list_labs()
        response = templates.TemplateResponse(
            request,
            "home.html",
            {
                "lang": chosen,
                "s": HOME_STRINGS[chosen],
                "labs_initial": labs_initial,
            },
        )
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

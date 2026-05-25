"""Server-rendered viewer pages + JSON API for the SPA."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import RequiredGroupsDep
from app.discovery import TranslationDescriptor
from app.templates import templates


class _DiscoveryLike(Protocol):
    async def list(
        self, lab_name: str, *, force_refresh: bool = False
    ) -> list[TranslationDescriptor]: ...


def make_router(*, roster: dict[str, int], discovery: _DiscoveryLike) -> APIRouter:
    router = APIRouter()

    @router.get("/streamer/labs", response_class=HTMLResponse)
    async def labs_picker(request: Request, _identity=RequiredGroupsDep) -> HTMLResponse:
        labs = []
        for name in sorted(roster.keys()):
            translations = await discovery.list(name)
            labs.append(
                {
                    "name": name,
                    "active": len(translations) > 0,
                    "translation_count": len(translations),
                }
            )
        return templates.TemplateResponse(request, "labs.html", {"labs": labs})

    @router.get("/streamer/labs/{name}", response_class=HTMLResponse)
    async def lab_view(
        request: Request,
        name: str = Path(..., min_length=1, max_length=128),
        _identity=RequiredGroupsDep,
    ) -> HTMLResponse:
        if name not in roster:
            raise HTTPException(status_code=404, detail="unknown lab")
        translations = await discovery.list(name, force_refresh=True)
        return templates.TemplateResponse(
            request,
            "lab.html",
            {"lab_name": name, "translations": translations},
        )

    @router.get("/streamer/api/labs")
    async def api_labs(_identity=RequiredGroupsDep) -> JSONResponse:
        out = []
        for name in sorted(roster.keys()):
            translations = await discovery.list(name)
            out.append(
                {
                    "name": name,
                    "active": len(translations) > 0,
                    "translation_count": len(translations),
                }
            )
        return JSONResponse(out)

    @router.get("/streamer/api/labs/{name}/translations")
    async def api_lab_translations(
        name: str = Path(..., min_length=1, max_length=128),
        _identity=RequiredGroupsDep,
    ) -> JSONResponse:
        if name not in roster:
            raise HTTPException(status_code=404, detail="unknown lab")
        translations = await discovery.list(name, force_refresh=True)
        return JSONResponse([{"id": t.id, "label": t.label} for t in translations])

    return router

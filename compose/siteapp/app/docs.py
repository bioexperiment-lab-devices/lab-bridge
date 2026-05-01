from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from starlette.status import HTTP_308_PERMANENT_REDIRECT

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.nav import build_nav
from app.templates import templates
from app.translations import find_doc, resolve_lang_file


def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]:
    for v in (query, cookie):
        if v in ("en", "ru"):
            return v  # type: ignore[return-value]
    return "en"


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/docs", include_in_schema=False)
    def docs_root_no_slash() -> Response:
        return RedirectResponse(url="/docs/", status_code=HTTP_308_PERMANENT_REDIRECT)

    @router.get("/docs/{path:path}")
    def docs_path(
        path: str,
        request: Request,
        lang: str | None = None,
    ) -> Response:
        # Trailing-slash semantics: a directory URL must end with `/` so relative
        # links inside index.md resolve correctly in the browser.
        if path and not path.endswith("/"):
            candidate = settings.docs_root / path
            if candidate.is_dir():
                return RedirectResponse(
                    url=f"/docs/{path}/", status_code=HTTP_308_PERMANENT_REDIRECT
                )

        doc = find_doc(settings.docs_root, path)
        if doc is None:
            return Response(status_code=404)

        chosen = _pick_lang(lang, request.cookies.get("lang"))
        file = resolve_lang_file(settings.docs_root, doc, chosen)
        text = file.read_text(encoding="utf-8")
        html, title = render_markdown(text)

        nav = build_nav(settings.docs_root)
        response = templates.TemplateResponse(
            request,
            "doc.html",
            {
                "title": title or doc.rel_path.name,
                "html": html,
                "lang": chosen,
                "doc": doc,
                "nav": nav,
                "current_url": str(request.url.path),
                "pygments_css": pygments_css(),
            },
        )
        if lang in ("en", "ru"):
            response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
        return response

    return router

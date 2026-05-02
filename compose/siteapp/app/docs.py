from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.status import HTTP_308_PERMANENT_REDIRECT

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.nav import build_nav
from app.paths import safe_join
from app.templates import templates
from app.translations import find_doc, resolve_lang_file


DOC_STATIC_EXTS: frozenset[str] = frozenset({
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp",
})


def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]:
    for v in (query, cookie):
        if v == "en":
            return "en"
        if v == "ru":
            return "ru"
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
        # Resolve the URL once to a candidate filesystem path. safe_join
        # rejects URL-encoded traversal; treat that as a missing doc.
        candidate: Path | None = None
        if path:
            try:
                candidate = safe_join(settings.docs_root, *[p for p in path.split("/") if p])
            except ValueError:
                return Response(status_code=404)

        # Trailing-slash semantics: a directory URL must end with `/` so relative
        # links inside index.md resolve correctly in the browser.
        if path and not path.endswith("/") and candidate is not None and candidate.is_dir():
            return RedirectResponse(
                url=f"/docs/{path}/", status_code=HTTP_308_PERMANENT_REDIRECT
            )

        # Doc-relative static asset (e.g., icons/jupyter.svg next to a .md):
        # serve the file directly when its extension is in the allow-list.
        # Anything outside the allow-list 404s — including .md files, which
        # belong to the markdown render path below.
        if (
            candidate is not None
            and candidate.is_file()
            and candidate.suffix.lower() in DOC_STATIC_EXTS
        ):
            return FileResponse(candidate)

        doc = find_doc(settings.docs_root, path)
        if doc is None:
            return Response(status_code=404)

        chosen = _pick_lang(lang, request.cookies.get("lang"))
        file = resolve_lang_file(settings.docs_root, doc, chosen)
        text = file.read_text(encoding="utf-8")
        result = render_markdown(text)

        nav = build_nav(settings.docs_root)
        response = templates.TemplateResponse(
            request,
            "doc.html",
            {
                "title": result.title or doc.rel_path.name,
                "html": result.html,
                "needs_mermaid": result.needs_mermaid,
                "lang": chosen,
                "doc": doc,
                "nav": nav,
                "current_url": str(request.url.path),
                "pygments_css": pygments_css(),
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

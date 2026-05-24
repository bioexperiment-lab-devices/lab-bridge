from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.status import HTTP_308_PERMANENT_REDIRECT

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.nav import NavEntry, build_nav, flatten_nav
from app.paths import safe_join
from app.strings import DOCS_STRINGS, pick_lang
from app.templates import templates
from app.translations import find_doc, resolve_lang_file


class BreadcrumbCrumb(TypedDict):
    title: str
    url: str | None  # None for the leaf (current page)


def _find_path(nav: list[NavEntry], target_url: str) -> list[NavEntry]:
    """DFS for target_url through children; return ancestor + self list."""
    for entry in nav:
        if entry.url == target_url:
            return [entry]
        if entry.children:
            sub = _find_path(list(entry.children), target_url)
            if sub:
                return [entry, *sub]
    return []


def build_breadcrumb(nav: list[NavEntry], current_url: str) -> list[BreadcrumbCrumb]:
    """Compose [Docs, ancestors..., self] crumbs for the current URL.

    Returns at least one crumb (the 'Docs' root). Leaf crumb has ``url=None``
    so the template can render it as plain text.
    """
    path = _find_path(nav, current_url)
    crumbs: list[BreadcrumbCrumb] = [{"title": "Docs", "url": "/docs/"}]
    for i, entry in enumerate(path):
        is_leaf = i == len(path) - 1
        crumbs.append({"title": entry.title_en, "url": None if is_leaf else entry.url})
    return crumbs


def prev_next(nav: list[NavEntry], current_url: str) -> tuple[NavEntry | None, NavEntry | None]:
    """Return (prev, next) entries in pre-order DFS reading order.

    Walks the entire docs tree as one flat sequence: a section index is
    followed by its first child, the last child of one section is followed
    by the next top section's index, and so on. (None, None) when the
    current URL is not in the nav at all.
    """
    flat = flatten_nav(nav)
    for i, entry in enumerate(flat):
        if entry.url == current_url:
            prev = flat[i - 1] if i > 0 else None
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            return prev, nxt
    return None, None


DOC_STATIC_EXTS: frozenset[str] = frozenset(
    {
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
    }
)


def _is_top_section(nav: list[NavEntry], url: str) -> bool:
    """True iff `url` matches a depth-0 entry in `nav`.

    Used to switch the prev/next eyebrow between "Previous"/"Next" (in-section
    page) and "Previous section"/"Next section" (crossing into a new section).
    Under pure pre-order DFS, cross-section transitions always land on the
    next section's *index page* — exactly the case this returns True for.
    """
    return any(top.url == url for top in nav)


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
                raise HTTPException(status_code=404)

        # Trailing-slash semantics: a directory URL must end with `/` so relative
        # links inside index.md resolve correctly in the browser.
        if path and not path.endswith("/") and candidate is not None and candidate.is_dir():
            return RedirectResponse(url=f"/docs/{path}/", status_code=HTTP_308_PERMANENT_REDIRECT)

        # Doc-relative static asset (e.g., diagrams/topology.svg next to a .md):
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
            # No root index.md? Redirect /docs/ to the first sidebar entry so
            # users land on real content instead of a 404.
            if path == "":
                nav = build_nav(settings.docs_root)
                if nav:
                    return RedirectResponse(url=nav[0].url, status_code=HTTP_308_PERMANENT_REDIRECT)
            raise HTTPException(status_code=404)

        chosen = pick_lang(lang, request.cookies.get("lang"))
        file = resolve_lang_file(settings.docs_root, doc, chosen)
        text = file.read_text(encoding="utf-8")
        result = render_markdown(text)

        nav = build_nav(settings.docs_root)
        crumbs = build_breadcrumb(nav, str(request.url.path))
        prev, nxt = prev_next(nav, str(request.url.path))
        prev_is_section = bool(prev) and _is_top_section(nav, prev.url)
        next_is_section = bool(nxt) and _is_top_section(nav, nxt.url)
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
                "crumbs": crumbs,
                "prev": prev,
                "next": nxt,
                "prev_is_section": prev_is_section,
                "next_is_section": next_is_section,
                "s": DOCS_STRINGS[chosen],
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

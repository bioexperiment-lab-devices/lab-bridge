from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.templates import templates


@dataclass(frozen=True)
class AgentInfo:
    version: str
    size: int
    sha256: str
    uploaded_at: str


def load_meta(agent_root: Path) -> AgentInfo | None:
    meta_path = agent_root / "meta.json"
    binary_path = agent_root / "windows" / "agent.exe"
    if not (meta_path.is_file() and binary_path.is_file()):
        return None
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    return AgentInfo(
        version=str(data.get("version", "?")),
        size=int(data.get("size", 0)),
        sha256=str(data.get("sha256", "")),
        uploaded_at=str(data.get("uploaded_at", "")),
    )


def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]:
    for v in (query, cookie):
        if v == "en":
            return "en"
        if v == "ru":
            return "ru"
    return "en"


def _body_markdown(agent_root: Path, lang: str) -> tuple[str | None, bool]:
    """Returns (html, needs_mermaid) — the second flag tells the template
    whether the rendered body contains a Mermaid block."""
    candidates: list[Path] = []
    if lang == "ru":
        candidates.append(agent_root / "page.ru.md")
    candidates.append(agent_root / "page.md")
    for c in candidates:
        if c.is_file():
            result = render_markdown(c.read_text(encoding="utf-8"))
            return result.html, result.needs_mermaid
    return None, False


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/download/agent")
    def agent_page(request: Request, lang: str | None = None) -> Response:
        chosen = _pick_lang(lang, request.cookies.get("lang"))
        info = load_meta(settings.agent_root)
        body_html, needs_mermaid = _body_markdown(settings.agent_root, chosen)
        ru_body_exists = (settings.agent_root / "page.ru.md").is_file()
        response = templates.TemplateResponse(
            request,
            "agent.html",
            {
                "info": info,
                "body_html": body_html,
                "needs_mermaid": needs_mermaid,
                "lang": chosen,
                "ru_exists": ru_body_exists,
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

    @router.get("/download/agent/windows/agent.exe")
    def agent_binary() -> Response:
        info = load_meta(settings.agent_root)
        if info is None:
            return Response(status_code=404)
        path = settings.agent_root / "windows" / "agent.exe"
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"lab-bridge-agent-{info.version}.exe",
            headers={"Cache-Control": "no-store"},
        )

    return router

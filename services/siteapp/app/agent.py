from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

from app.config import Settings
from app.markdown import Rendered, pygments_css, render_markdown
from app.strings import DL_STRINGS, Lang, pick_lang
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


def _relative_time(iso: str, lang: Lang) -> str:
    """Localized 'X units ago' string for a UTC ISO timestamp.

    Returns "" on parse failure (template should fall back to the raw
    timestamp). Uses DL_STRINGS for unit phrases so they stay in one place.
    """
    try:
        normalized = iso.replace("Z", "+00:00")
        then = datetime.fromisoformat(normalized)
    except ValueError:
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - then
    seconds = max(int(delta.total_seconds()), 0)
    s = DL_STRINGS[lang]
    if seconds < 60:
        return s["just_now"]
    minutes = seconds // 60
    if minutes < 60:
        return s["minutes_ago"].format(n=minutes)
    hours = minutes // 60
    if hours < 24:
        return s["hours_ago"].format(n=hours)
    days = hours // 24
    if days < 14:
        return s["days_ago"].format(n=days)
    weeks = days // 7
    return s["weeks_ago"].format(n=weeks)


def _body_markdown(agent_root: Path, lang: str) -> Rendered | None:
    """Render the agent download page's optional markdown body.

    Returns None when no `page.md` (or `page.ru.md`) exists for the
    requested language; the caller treats that as "no body" and just
    renders the hero + metadata."""
    candidates: list[Path] = []
    if lang == "ru":
        candidates.append(agent_root / "page.ru.md")
    candidates.append(agent_root / "page.md")
    for c in candidates:
        if c.is_file():
            return render_markdown(c.read_text(encoding="utf-8"))
    return None


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/download/agent")
    def agent_page(request: Request, lang: str | None = None) -> Response:
        chosen = pick_lang(lang, request.cookies.get("lang"))
        info = load_meta(settings.agent_root)
        body = _body_markdown(settings.agent_root, chosen)
        body_html = body.html if body else None
        needs_mermaid = body.needs_mermaid if body else False
        released_relative = _relative_time(info.uploaded_at, chosen) if info else ""
        response = templates.TemplateResponse(
            request,
            "agent.html",
            {
                "info": info,
                "body_html": body_html,
                "needs_mermaid": needs_mermaid,
                "lang": chosen,
                "s": DL_STRINGS[chosen],
                "released_relative": released_relative,
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
            filename=f"SerialHop-v{info.version}.exe",
            headers={"Cache-Control": "no-store"},
        )

    return router

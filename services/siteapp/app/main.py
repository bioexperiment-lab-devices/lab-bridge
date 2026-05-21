from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agent import make_router as make_agent_router
from app.api import make_router as make_api_router
from app.auth import make_router as make_auth_router
from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.home import make_router as make_home_router
from app.labs import make_router as make_labs_router
from app.public_clients import make_router as make_public_clients_router
from app.server_info import make_router as make_server_info_router
from app.templates import TEMPLATE_DIR, templates

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_home_router(settings))
app.include_router(make_docs_router(settings))
app.include_router(make_agent_router(settings))
app.include_router(make_api_router(settings))
app.include_router(make_public_clients_router(settings))
app.include_router(make_server_info_router(settings))
app.include_router(make_labs_router(settings))
app.include_router(make_auth_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    # Browsers hitting an unknown route on siteapp (e.g. /docsd) should land on
    # the styled 404 template, not FastAPI's default `{"detail":"Not Found"}`
    # JSON. JSON API clients (Accept: application/json or path under /api/)
    # still get a JSON body — they're scripts, not humans, and a wall of HTML
    # would only confuse them.
    if exc.status_code == 404 and _wants_html(request):
        return templates.TemplateResponse(
            request,
            "error_404.html",
            {"attempted_path": request.url.path},
            status_code=404,
        )
    if exc.status_code == 403 and _wants_html(request):
        return templates.TemplateResponse(
            request,
            "error_403.html",
            {"attempted_path": request.url.path},
            status_code=403,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def _wants_html(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return False
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return True
    # No Accept header (curl, simple clients) → default to HTML; browsers
    # always send Accept and matching above already handled them.
    return accept == "" or accept == "*/*"

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.flash import JobStore
from app.routes import make_router

STATIC_DIR = Path(__file__).parent / "static"

settings = load_settings()
JOB_STORE = JobStore(capacity=10)
app = FastAPI(title="lab-bridge flasher")
app.include_router(make_router(settings, JOB_STORE))


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Surface dict-typed detail at the top level.

    A handler that raises HTTPException(detail={"error": ..., "detail": ...})
    gets the dict as the response body verbatim; anything else falls back to
    FastAPI's default `{"detail": <value>}` shape.
    """
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# Static SPA assets — only mounted if the build output exists.
if (STATIC_DIR / "assets").is_dir():
    app.mount("/flash/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="spa-assets")

if (STATIC_DIR / "index.html").is_file():

    @app.get("/flash/{path:path}")
    def spa_index(path: str) -> FileResponse:
        """Serve index.html for any /flash/* path that isn't a static asset.

        Lets the SPA own client-side routing (we don't have any today, but this
        is the standard SPA fallback pattern and costs nothing).
        """
        return FileResponse(STATIC_DIR / "index.html")

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.config import load_settings
from app.routes import make_router

settings = load_settings()
app = FastAPI(title="lab-bridge flasher")
app.include_router(make_router(settings))


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

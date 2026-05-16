from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.db import connect, migrate

STATIC_DIR = Path(__file__).parent / "static"

settings = load_settings()
app = FastAPI(title="lab-bridge flasher")


@app.on_event("startup")
async def _on_startup() -> None:
    db_path = settings.data_dir / "flasher.db"
    await migrate(db_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    async with connect(db_path) as conn:
        await conn.execute(
            "UPDATE flashes SET status='interrupted', finished_at=?, "
            "error_code='interrupted', error_detail='server restarted while flash was running' "
            "WHERE status='running'",
            (now,),
        )
        await conn.commit()


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


if (STATIC_DIR / "assets").is_dir():
    app.mount("/flash/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="spa-assets")

if (STATIC_DIR / "index.html").is_file():

    @app.get("/flash/{path:path}")
    def spa_index(path: str) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

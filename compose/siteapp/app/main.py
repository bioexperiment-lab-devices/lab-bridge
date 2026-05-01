from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_docs_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

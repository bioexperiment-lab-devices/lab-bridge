from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

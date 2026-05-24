from __future__ import annotations

from fastapi import FastAPI

from app.config import load_settings

settings = load_settings()

app = FastAPI(title="lab-bridge streamer")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.lab_bridge_version,
        "git_sha": settings.lab_bridge_git_sha,
    }

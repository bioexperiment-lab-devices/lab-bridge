from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="lab-bridge flasher")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

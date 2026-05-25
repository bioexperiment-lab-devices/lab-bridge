from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.control import ControlPlaneClient
from app.discovery import DiscoveryCache
from app.pages import make_router as make_pages_router
from app.roster import load_roster
from app.session_manager import SessionManager
from app.templates import STATIC_DIR
from app.whep import make_router as make_whep_router
from app.whip import make_router as make_whip_router


def _build_base_url(public_ip: str) -> str:
    return f"https://{public_ip}"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


settings = load_settings()


def _roster() -> dict[str, int]:
    try:
        return load_roster(settings.clients_file)
    except OSError:
        return {}


roster = _roster()

discovery = DiscoveryCache(
    roster=roster,
    chisel_host=settings.chisel_host,
    ttl_s=settings.discovery_cache_ttl_s,
    request_timeout_s=settings.discovery_request_timeout_s,
)
control = ControlPlaneClient(
    roster=roster,
    chisel_host=settings.chisel_host,
    request_timeout_s=2.0,
)
manager = SessionManager(whip_token_validity_s=settings.whip_token_validity_s)

app = FastAPI(title="lab-bridge streamer", lifespan=_lifespan)

app.mount("/streamer/_static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(make_whip_router(manager=manager, public_ip=settings.public_ip))
app.include_router(
    make_whep_router(
        manager=manager,
        discovery=discovery,
        control=control,
        public_ip=settings.public_ip,
        publish_ready_timeout_s=settings.publish_ready_timeout_s,
        drain_debounce_s=settings.drain_debounce_s,
        max_subscribers_per_session=settings.max_subscribers_per_session,
        base_url=_build_base_url(settings.public_ip),
    )
)
app.include_router(make_pages_router(roster=roster, discovery=discovery))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.lab_bridge_version,
        "git_sha": settings.lab_bridge_git_sha,
    }

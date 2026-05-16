from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite
from fastapi import APIRouter

from app.config import Settings
from app.db import connect

from app.routes import backups as backups_routes
from app.routes import firmware as firmware_routes
from app.routes import tags as tags_routes


def make_router(settings: Settings) -> APIRouter:
    db_path = settings.data_dir / "flasher.db"
    blobs_root = settings.data_dir / "blobs"
    # Ensure blob directories exist before any handler runs.
    (blobs_root / "firmware").mkdir(parents=True, exist_ok=True)
    (blobs_root / "backups").mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def conn_factory() -> AsyncIterator[aiosqlite.Connection]:
        async with connect(db_path) as conn:
            yield conn

    router = APIRouter()
    router.include_router(firmware_routes.make_router(settings, conn_factory, blobs_root))
    router.include_router(backups_routes.make_router(settings, conn_factory, blobs_root))
    router.include_router(tags_routes.make_router(settings, conn_factory))
    return router

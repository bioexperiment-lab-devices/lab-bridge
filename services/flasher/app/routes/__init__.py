from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

import aiosqlite
from fastapi import APIRouter

from app.config import Settings
from app.db import connect

from app.routes import firmware as firmware_routes


ConnFactory = Callable[[], "asynccontextmanager[aiosqlite.Connection]"]


def make_router(settings: Settings) -> APIRouter:
    db_path = settings.data_dir / "flasher.db"
    blobs_root = settings.data_dir / "blobs"

    @asynccontextmanager
    async def conn_factory() -> AsyncIterator[aiosqlite.Connection]:
        async with connect(db_path) as conn:
            yield conn

    router = APIRouter()
    router.include_router(firmware_routes.make_router(settings, conn_factory, blobs_root))
    return router

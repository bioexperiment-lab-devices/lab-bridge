from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@asynccontextmanager
async def connect(db_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """Open a SQLite connection with the project's standard PRAGMAs applied.

    WAL keeps readers unblocked by the single writer; foreign_keys is off by
    default in SQLite and must be enabled per connection; busy_timeout makes
    transient lock contention spin briefly instead of failing.
    """
    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.commit()
        yield conn
    finally:
        await conn.close()


async def migrate(db_path: Path, *, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply pending migrations in numeric order. Returns the resulting schema version."""
    raise NotImplementedError  # filled in by Task 1.4

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from app.db import connect, migrate, MIGRATIONS_DIR


@pytest.mark.asyncio
async def test_connect_applies_pragmas(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    async with connect(db_path) as conn:
        row = await (await conn.execute("PRAGMA journal_mode")).fetchone()
        assert row[0] == "wal"
        row = await (await conn.execute("PRAGMA foreign_keys")).fetchone()
        assert row[0] == 1
        row = await (await conn.execute("PRAGMA synchronous")).fetchone()
        # NORMAL == 1
        assert row[0] == 1

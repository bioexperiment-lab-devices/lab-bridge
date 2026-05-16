from __future__ import annotations

import time
import uuid
from typing import Any

import aiosqlite


class TagNotFound(Exception):
    """Raised when a tag id does not exist."""


class DuplicateTagName(Exception):
    """Raised when a tag name collides with an existing one."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def create_tag(conn: aiosqlite.Connection, *, name: str) -> dict[str, Any]:
    tag_id = uuid.uuid4().hex
    created_at = _now()
    try:
        await conn.execute(
            "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)",
            (tag_id, name, created_at),
        )
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        if "tags.name" in str(exc) or "UNIQUE" in str(exc).upper():
            raise DuplicateTagName(name) from exc
        raise
    return {"id": tag_id, "name": name, "created_at": created_at, "firmware_count": 0}


async def list_tags(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "SELECT t.id, t.name, t.created_at, "
        "(SELECT COUNT(*) FROM firmware_tags ft WHERE ft.tag_id = t.id) AS firmware_count "
        "FROM tags t ORDER BY t.name COLLATE NOCASE ASC"
    )
    rows = await cur.fetchall()
    return [{"id": r[0], "name": r[1], "created_at": r[2], "firmware_count": r[3]} for r in rows]


async def rename_tag(conn: aiosqlite.Connection, *, tag_id: str, name: str) -> None:
    cur = await conn.execute("SELECT 1 FROM tags WHERE id = ?", (tag_id,))
    if (await cur.fetchone()) is None:
        raise TagNotFound(tag_id)
    try:
        await conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        if "UNIQUE" in str(exc).upper():
            raise DuplicateTagName(name) from exc
        raise


async def delete_tag(conn: aiosqlite.Connection, *, tag_id: str) -> None:
    cur = await conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    if cur.rowcount == 0:
        await conn.rollback()
        raise TagNotFound(tag_id)
    await conn.commit()


async def set_firmware_tags(
    conn: aiosqlite.Connection, *, firmware_id: str, tag_ids: list[str]
) -> None:
    """Replace the set of tags on `firmware_id` with `tag_ids`. Validates every id."""
    for tid in tag_ids:
        cur = await conn.execute("SELECT 1 FROM tags WHERE id = ?", (tid,))
        if (await cur.fetchone()) is None:
            raise TagNotFound(tid)
    await conn.execute("DELETE FROM firmware_tags WHERE firmware_id = ?", (firmware_id,))
    for tid in tag_ids:
        await conn.execute(
            "INSERT INTO firmware_tags (firmware_id, tag_id) VALUES (?, ?)",
            (firmware_id, tid),
        )
    await conn.commit()

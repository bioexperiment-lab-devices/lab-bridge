from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from app.tags import TagNotFound, set_firmware_tags


class FirmwareNotFound(Exception):
    """Unknown firmware id."""


class FirmwareInUse(Exception):
    """A running flash references this firmware; refuse delete."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _blob_path(blobs_dir: Path, firmware_id: str) -> Path:
    return blobs_dir / f"{firmware_id}.hex"


async def _row_to_dict(conn: aiosqlite.Connection, row: aiosqlite.Row | tuple) -> dict[str, Any]:
    cols = [
        "id",
        "name",
        "description",
        "sha256",
        "size_bytes",
        "original_filename",
        "test_command",
        "expected_response",
        "source_backup_id",
        "created_at",
    ]
    out: dict[str, Any] = dict(zip(cols, row))
    # tags
    cur = await conn.execute(
        "SELECT t.id, t.name FROM tags t "
        "JOIN firmware_tags ft ON ft.tag_id = t.id "
        "WHERE ft.firmware_id = ? "
        "ORDER BY t.name COLLATE NOCASE ASC",
        (out["id"],),
    )
    out["tags"] = [{"id": r[0], "name": r[1]} for r in await cur.fetchall()]
    # stats
    cur = await conn.execute(
        "SELECT "
        "COUNT(*), "
        "SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN outcome LIKE 'rolled_back%' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN status = 'error' OR outcome LIKE 'failed_%' THEN 1 ELSE 0 END), "
        "MAX(started_at) "
        "FROM flashes WHERE source_kind = 'firmware' AND source_id = ?",
        (out["id"],),
    )
    total, succ, roll, fail, last_at = await cur.fetchone()
    last_client = last_port = None
    if last_at:
        cur = await conn.execute(
            "SELECT client, port_name FROM flashes "
            "WHERE source_kind = 'firmware' AND source_id = ? AND started_at = ? "
            "ORDER BY id LIMIT 1",
            (out["id"], last_at),
        )
        rr = await cur.fetchone()
        if rr:
            last_client, last_port = rr
    out["stats"] = {
        "total": int(total or 0),
        "successes": int(succ or 0),
        "rollbacks": int(roll or 0),
        "failures": int(fail or 0),
        "last_flashed_at": last_at,
        "last_flashed_client": last_client,
        "last_flashed_port": last_port,
    }
    return out


async def create_firmware(
    conn: aiosqlite.Connection,
    *,
    blobs_dir: Path,
    name: str,
    firmware: str,
    description: str = "",
    test_command: str | None = None,
    expected_response: str | None = None,
    original_filename: str | None = None,
    tag_ids: list[str] | None = None,
    source_backup_id: str | None = None,
) -> dict[str, Any]:
    firmware_id = uuid.uuid4().hex
    encoded = firmware.encode("utf-8")
    sha256 = hashlib.sha256(encoded).hexdigest()
    size_bytes = len(encoded)
    created_at = _now()
    # Write blob FIRST so a row never references a missing file. If the row
    # insert fails, the blob is an orphan and the next create with the same
    # uuid would catch it — but uuid collision is unrealistic at this scale.
    blob = _blob_path(blobs_dir, firmware_id)
    blob.write_text(firmware, encoding="utf-8")
    try:
        await conn.execute(
            "INSERT INTO firmware (id, name, description, sha256, size_bytes, "
            "original_filename, test_command, expected_response, source_backup_id, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                firmware_id,
                name,
                description,
                sha256,
                size_bytes,
                original_filename,
                test_command,
                expected_response,
                source_backup_id,
                created_at,
            ),
        )
        if tag_ids:
            await set_firmware_tags(conn, firmware_id=firmware_id, tag_ids=tag_ids)
        else:
            await conn.commit()
    except Exception:
        blob.unlink(missing_ok=True)
        await conn.rollback()
        raise
    cur = await conn.execute(
        "SELECT id, name, description, sha256, size_bytes, original_filename, "
        "test_command, expected_response, source_backup_id, created_at "
        "FROM firmware WHERE id = ?",
        (firmware_id,),
    )
    row = await cur.fetchone()
    return await _row_to_dict(conn, row)


async def get_firmware(conn: aiosqlite.Connection, *, firmware_id: str) -> dict[str, Any] | None:
    cur = await conn.execute(
        "SELECT id, name, description, sha256, size_bytes, original_filename, "
        "test_command, expected_response, source_backup_id, created_at "
        "FROM firmware WHERE id = ?",
        (firmware_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return await _row_to_dict(conn, row)


async def get_firmware_by_sha256(
    conn: aiosqlite.Connection, *, sha256: str
) -> dict[str, Any] | None:
    cur = await conn.execute(
        "SELECT id, name, description, sha256, size_bytes, original_filename, "
        "test_command, expected_response, source_backup_id, created_at "
        "FROM firmware WHERE sha256 = ? LIMIT 1",
        (sha256,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return await _row_to_dict(conn, row)


async def list_firmware(
    conn: aiosqlite.Connection,
    *,
    tag_ids: list[str] | None = None,
    q: str | None = None,
    limit: int = 100,
    before: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(500, int(limit)))
    where = []
    params: list[Any] = []
    if q:
        where.append("LOWER(f.name) LIKE ?")
        params.append(f"%{q.lower()}%")
    if before:
        where.append("(f.created_at, f.id) < (SELECT created_at, id FROM firmware WHERE id = ?)")
        params.append(before)
    if tag_ids:
        # AND-style: row must carry every requested tag.
        for tid in tag_ids:
            where.append(
                "EXISTS (SELECT 1 FROM firmware_tags ft "
                "WHERE ft.firmware_id = f.id AND ft.tag_id = ?)"
            )
            params.append(tid)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT f.id FROM firmware f "
        + where_sql
        + " ORDER BY f.created_at DESC, f.id DESC LIMIT ?"
    )
    params.append(limit + 1)
    cur = await conn.execute(sql, params)
    ids = [r[0] for r in await cur.fetchall()]
    next_before = None
    if len(ids) > limit:
        ids = ids[:limit]
        next_before = ids[-1]
    items = []
    for fid in ids:
        item = await get_firmware(conn, firmware_id=fid)
        if item is not None:
            items.append(item)
    return {"items": items, "next_before": next_before}


async def update_firmware(
    conn: aiosqlite.Connection,
    *,
    firmware_id: str,
    name: str | None = None,
    description: str | None = None,
    test_command: str | None = ...,
    expected_response: str | None = ...,
    tag_ids: list[str] | None = None,
) -> dict[str, Any]:
    cur = await conn.execute("SELECT 1 FROM firmware WHERE id = ?", (firmware_id,))
    if (await cur.fetchone()) is None:
        raise FirmwareNotFound(firmware_id)
    sets: list[str] = []
    params: list[Any] = []
    if name is not None:
        sets.append("name = ?")
        params.append(name)
    if description is not None:
        sets.append("description = ?")
        params.append(description)
    if test_command is not ...:
        sets.append("test_command = ?")
        params.append(test_command)
    if expected_response is not ...:
        sets.append("expected_response = ?")
        params.append(expected_response)
    if sets:
        params.append(firmware_id)
        await conn.execute(f"UPDATE firmware SET {', '.join(sets)} WHERE id = ?", params)
    if tag_ids is not None:
        try:
            await set_firmware_tags(conn, firmware_id=firmware_id, tag_ids=tag_ids)
        except TagNotFound:
            await conn.rollback()
            raise
    else:
        await conn.commit()
    out = await get_firmware(conn, firmware_id=firmware_id)
    assert out is not None
    return out


async def delete_firmware(conn: aiosqlite.Connection, *, blobs_dir: Path, firmware_id: str) -> None:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes "
        "WHERE source_kind = 'firmware' AND source_id = ? AND status = 'running'",
        (firmware_id,),
    )
    if (await cur.fetchone())[0] > 0:
        raise FirmwareInUse(firmware_id)
    cur = await conn.execute("DELETE FROM firmware WHERE id = ?", (firmware_id,))
    if cur.rowcount == 0:
        await conn.rollback()
        raise FirmwareNotFound(firmware_id)
    await conn.commit()
    _blob_path(blobs_dir, firmware_id).unlink(missing_ok=True)


async def download_firmware_bytes(blobs_dir: Path, *, firmware_id: str) -> str:
    p = _blob_path(blobs_dir, firmware_id)
    if not p.exists():
        raise FirmwareNotFound(firmware_id)
    return p.read_text(encoding="utf-8")


async def count_flashes_referencing(conn: aiosqlite.Connection, *, firmware_id: str) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes WHERE source_kind = 'firmware' AND source_id = ?",
        (firmware_id,),
    )
    return int((await cur.fetchone())[0])

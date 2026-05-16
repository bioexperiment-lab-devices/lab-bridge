from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite


class BackupNotFound(Exception):
    """Unknown backup id."""


class BackupInUse(Exception):
    """A running flash references this backup; refuse delete."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _blob_path(blobs_dir: Path, backup_id: str) -> Path:
    return blobs_dir / f"{backup_id}.hex"


def _default_name(client: str, port_name: str, port_snapshot: dict, captured_at: str) -> str:
    product = (port_snapshot or {}).get("product") or ""
    vidpid = ""
    vid = (port_snapshot or {}).get("vid") or ""
    pid = (port_snapshot or {}).get("pid") or ""
    if vid and pid:
        vidpid = f"{vid}:{pid}"
    descriptor = product or vidpid or "unknown"
    return f"{client} · {port_name} · {descriptor} · {captured_at}"


async def _row_to_dict(conn: aiosqlite.Connection, row: tuple) -> dict[str, Any]:
    cols = [
        "id",
        "name",
        "description",
        "sha256",
        "size_bytes",
        "client",
        "port_name",
        "vid",
        "pid",
        "serial_number",
        "product",
        "serialhop_saved_path",
        "test_command",
        "expected_response",
        "source_flash_id",
        "captured_at",
    ]
    out: dict[str, Any] = dict(zip(cols, row))
    # stats
    cur = await conn.execute(
        "SELECT "
        "COUNT(*), "
        "SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN outcome LIKE 'rolled_back%' THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN status = 'error' OR outcome LIKE 'failed_%' THEN 1 ELSE 0 END), "
        "MAX(started_at) "
        "FROM flashes WHERE source_kind = 'backup' AND source_id = ?",
        (out["id"],),
    )
    total, succ, roll, fail, last_at = await cur.fetchone()
    last_client = last_port = None
    if last_at:
        cur = await conn.execute(
            "SELECT client, port_name FROM flashes "
            "WHERE source_kind = 'backup' AND source_id = ? AND started_at = ? "
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


async def capture_or_reuse_backup(
    conn: aiosqlite.Connection,
    *,
    blobs_dir: Path,
    client: str,
    port_name: str,
    port_snapshot: dict,
    source_flash_id: str,
    backup: dict,
) -> str:
    """Insert a new backup row OR return existing id if sha256 matches.

    `backup` is SerialHop's response sub-object (`hex`, `sha256`,
    `size_bytes`, `saved_path`, `scope`).
    """
    sha = backup.get("sha256")
    if not sha:
        raise ValueError("backup payload missing sha256")
    cur = await conn.execute("SELECT id FROM backups WHERE sha256 = ?", (sha,))
    existing = await cur.fetchone()
    if existing is not None:
        return existing[0]

    backup_id = uuid.uuid4().hex
    captured_at = _now()
    name = _default_name(client, port_name, port_snapshot, captured_at)
    blob = _blob_path(blobs_dir, backup_id)
    blob.write_text(backup.get("hex", ""), encoding="utf-8")
    try:
        await conn.execute(
            "INSERT INTO backups (id, name, description, sha256, size_bytes, client, "
            "port_name, vid, pid, serial_number, product, serialhop_saved_path, "
            "test_command, expected_response, source_flash_id, captured_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                backup_id,
                name,
                "",
                sha,
                int(backup.get("size_bytes") or 0),
                client,
                port_name,
                (port_snapshot or {}).get("vid"),
                (port_snapshot or {}).get("pid"),
                (port_snapshot or {}).get("serial_number"),
                (port_snapshot or {}).get("product"),
                backup.get("saved_path"),
                None,
                None,
                source_flash_id,
                captured_at,
            ),
        )
        await conn.commit()
    except Exception:
        blob.unlink(missing_ok=True)
        await conn.rollback()
        raise
    return backup_id


async def get_backup(conn: aiosqlite.Connection, *, backup_id: str) -> dict[str, Any] | None:
    cur = await conn.execute(
        "SELECT id, name, description, sha256, size_bytes, client, port_name, "
        "vid, pid, serial_number, product, serialhop_saved_path, "
        "test_command, expected_response, source_flash_id, captured_at "
        "FROM backups WHERE id = ?",
        (backup_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return await _row_to_dict(conn, row)


async def list_backups(
    conn: aiosqlite.Connection,
    *,
    client: str | None = None,
    q: str | None = None,
    limit: int = 100,
    before: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(500, int(limit)))
    where: list[str] = []
    params: list[Any] = []
    if client:
        where.append("client = ?")
        params.append(client)
    if q:
        where.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ?)")
        params.extend([f"%{q.lower()}%", f"%{q.lower()}%"])
    if before:
        where.append("(captured_at, id) < (SELECT captured_at, id FROM backups WHERE id = ?)")
        params.append(before)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = "SELECT id FROM backups" + where_sql + " ORDER BY captured_at DESC, id DESC LIMIT ?"
    params.append(limit + 1)
    cur = await conn.execute(sql, params)
    ids = [r[0] for r in await cur.fetchall()]
    next_before = None
    if len(ids) > limit:
        ids = ids[:limit]
        next_before = ids[-1]
    items: list[dict[str, Any]] = []
    for bid in ids:
        item = await get_backup(conn, backup_id=bid)
        if item is not None:
            items.append(item)
    return {"items": items, "next_before": next_before}


async def update_backup(
    conn: aiosqlite.Connection,
    *,
    backup_id: str,
    name: str | None = None,
    description: str | None = None,
    test_command: str | None = ...,
    expected_response: str | None = ...,
) -> dict[str, Any]:
    cur = await conn.execute("SELECT 1 FROM backups WHERE id = ?", (backup_id,))
    if (await cur.fetchone()) is None:
        raise BackupNotFound(backup_id)
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
        params.append(backup_id)
        await conn.execute(f"UPDATE backups SET {', '.join(sets)} WHERE id = ?", params)
        await conn.commit()
    out = await get_backup(conn, backup_id=backup_id)
    assert out is not None
    return out


async def _running_flash_reference_count(conn: aiosqlite.Connection, backup_id: str) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes "
        "WHERE source_kind = 'backup' AND source_id = ? AND status = 'running'",
        (backup_id,),
    )
    return int((await cur.fetchone())[0])


async def delete_backup(conn: aiosqlite.Connection, *, blobs_dir: Path, backup_id: str) -> None:
    cur = await conn.execute("SELECT 1 FROM backups WHERE id = ?", (backup_id,))
    if (await cur.fetchone()) is None:
        raise BackupNotFound(backup_id)
    if await _running_flash_reference_count(conn, backup_id) > 0:
        raise BackupInUse(backup_id)
    await conn.execute("DELETE FROM backups WHERE id = ?", (backup_id,))
    await conn.commit()
    _blob_path(blobs_dir, backup_id).unlink(missing_ok=True)


async def bulk_delete_backups(
    conn: aiosqlite.Connection, *, blobs_dir: Path, ids: list[str]
) -> dict[str, Any]:
    deleted = 0
    refused: list[dict[str, str]] = []
    for bid in ids:
        try:
            await delete_backup(conn, blobs_dir=blobs_dir, backup_id=bid)
            deleted += 1
        except BackupNotFound:
            refused.append({"id": bid, "reason": "unknown backup"})
        except BackupInUse:
            refused.append({"id": bid, "reason": "flash in flight"})
    return {"deleted": deleted, "refused": refused}


async def download_backup_bytes(blobs_dir: Path, *, backup_id: str) -> str:
    p = _blob_path(blobs_dir, backup_id)
    if not p.exists():
        raise BackupNotFound(backup_id)
    return p.read_text(encoding="utf-8")


async def count_flashes_referencing(conn: aiosqlite.Connection, *, backup_id: str) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes WHERE source_kind = 'backup' AND source_id = ?",
        (backup_id,),
    )
    return int((await cur.fetchone())[0])

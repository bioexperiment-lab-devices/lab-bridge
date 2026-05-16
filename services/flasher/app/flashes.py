from __future__ import annotations

import json
import time
import uuid
from typing import Any

import aiosqlite


class FlashNotFound(Exception):
    """Unknown flash id."""


class FlashStillRunning(Exception):
    """Operation not permitted while the flash is in flight."""


_TERMINAL_STATUSES = {"done", "error", "interrupted"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _row_to_dict(row: tuple) -> dict[str, Any]:
    cols = [
        "id",
        "status",
        "outcome",
        "client",
        "port_name",
        "port_snapshot_json",
        "source_kind",
        "source_id",
        "firmware_sha256",
        "firmware_name",
        "test_command_used",
        "expected_response_used",
        "skip_backup",
        "started_at",
        "finished_at",
        "duration_ms",
        "result_json",
        "error_code",
        "error_detail",
        "backup_id",
        "operator_note",
    ]
    out = dict(zip(cols, row))
    try:
        out["port_snapshot"] = json.loads(out.pop("port_snapshot_json") or "{}")
    except ValueError:
        out["port_snapshot"] = {}
    if out.get("result_json"):
        try:
            out["result"] = json.loads(out["result_json"])
        except ValueError:
            out["result"] = None
    out["skip_backup"] = bool(out["skip_backup"])
    return out


_SELECT_COLS = (
    "id, status, outcome, client, port_name, port_snapshot_json, "
    "source_kind, source_id, firmware_sha256, firmware_name, "
    "test_command_used, expected_response_used, skip_backup, "
    "started_at, finished_at, duration_ms, "
    "result_json, error_code, error_detail, backup_id, operator_note"
)


async def create_running_flash(
    conn: aiosqlite.Connection,
    *,
    client: str,
    port_name: str,
    port_snapshot: dict,
    source_kind: str,
    source_id: str,
    firmware_sha256: str,
    firmware_name: str,
    test_command_used: str | None,
    expected_response_used: str | None,
    skip_backup: bool,
) -> str:
    flash_id = uuid.uuid4().hex
    await conn.execute(
        "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
        "source_kind, source_id, firmware_sha256, firmware_name, "
        "test_command_used, expected_response_used, skip_backup, started_at) "
        "VALUES (?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            flash_id,
            client,
            port_name,
            json.dumps(port_snapshot),
            source_kind,
            source_id,
            firmware_sha256,
            firmware_name,
            test_command_used,
            expected_response_used,
            1 if skip_backup else 0,
            _now(),
        ),
    )
    await conn.commit()
    return flash_id


async def get_flash(conn: aiosqlite.Connection, *, flash_id: str) -> dict[str, Any] | None:
    cur = await conn.execute(f"SELECT {_SELECT_COLS} FROM flashes WHERE id = ?", (flash_id,))
    row = await cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


async def get_running_flash(conn: aiosqlite.Connection) -> dict[str, Any] | None:
    cur = await conn.execute(
        f"SELECT {_SELECT_COLS} FROM flashes WHERE status='running' "
        "ORDER BY started_at DESC, rowid DESC LIMIT 1"
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


async def set_terminal_done(
    conn: aiosqlite.Connection,
    *,
    flash_id: str,
    outcome: str,
    result_json: str,
    backup_id: str | None,
    duration_ms: int,
) -> None:
    cur = await conn.execute(
        "UPDATE flashes SET status='done', outcome=?, result_json=?, "
        "backup_id=?, duration_ms=?, finished_at=? "
        "WHERE id = ? AND status='running'",
        (outcome, result_json, backup_id, int(duration_ms), _now(), flash_id),
    )
    if cur.rowcount == 0:
        await conn.rollback()
        raise FlashNotFound(flash_id)
    await conn.commit()


async def set_terminal_error(
    conn: aiosqlite.Connection,
    *,
    flash_id: str,
    error_code: str,
    error_detail: str,
    duration_ms: int,
) -> None:
    cur = await conn.execute(
        "UPDATE flashes SET status='error', error_code=?, error_detail=?, "
        "duration_ms=?, finished_at=? "
        "WHERE id = ? AND status='running'",
        (error_code, error_detail, int(duration_ms), _now(), flash_id),
    )
    if cur.rowcount == 0:
        await conn.rollback()
        raise FlashNotFound(flash_id)
    await conn.commit()


async def set_note(conn: aiosqlite.Connection, *, flash_id: str, note: str) -> None:
    cur = await conn.execute("SELECT status FROM flashes WHERE id = ?", (flash_id,))
    row = await cur.fetchone()
    if row is None:
        raise FlashNotFound(flash_id)
    if row[0] == "running":
        raise FlashStillRunning(flash_id)
    await conn.execute("UPDATE flashes SET operator_note = ? WHERE id = ?", (note, flash_id))
    await conn.commit()


async def list_flashes(
    conn: aiosqlite.Connection,
    *,
    client: list[str] | None = None,
    outcome: list[str] | None = None,
    source_kind: str | None = None,
    source_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
    before: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(500, int(limit)))
    where: list[str] = []
    params: list[Any] = []
    if client:
        where.append("client IN (" + ",".join(["?"] * len(client)) + ")")
        params.extend(client)
    if outcome:
        # An "outcome" filter conceptually OR's across status='error',
        # status='interrupted', and the per-outcome values.
        clauses = []
        for o in outcome:
            if o in ("error", "interrupted"):
                clauses.append("status = ?")
                params.append(o)
            else:
                clauses.append("outcome = ?")
                params.append(o)
        where.append("(" + " OR ".join(clauses) + ")")
    if source_kind:
        where.append("source_kind = ?")
        params.append(source_kind)
    if source_id:
        where.append("source_id = ?")
        params.append(source_id)
    if since:
        where.append("started_at >= ?")
        params.append(since)
    if until:
        where.append("started_at <= ?")
        params.append(until)
    if before:
        where.append("(started_at, id) < (SELECT started_at, id FROM flashes WHERE id = ?)")
        params.append(before)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT id, status, outcome, client, port_name, source_kind, source_id, "
        "firmware_name, firmware_sha256, started_at, duration_ms, operator_note "
        "FROM flashes" + where_sql + " ORDER BY started_at DESC, id DESC LIMIT ?"
    )
    params.append(limit + 1)
    cur = await conn.execute(sql, params)
    rows = await cur.fetchall()
    next_before = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_before = rows[-1][0]
    cols = [
        "id",
        "status",
        "outcome",
        "client",
        "port_name",
        "source_kind",
        "source_id",
        "firmware_name",
        "firmware_sha256",
        "started_at",
        "duration_ms",
        "operator_note",
    ]
    items = [dict(zip(cols, r)) for r in rows]
    return {"items": items, "next_before": next_before}

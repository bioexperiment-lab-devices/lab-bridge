from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol

from app.backups import capture_or_reuse_backup
from app.flashes import set_terminal_done, set_terminal_error
from app.serialhop import SerialHopError, UpstreamErrorResponse, UpstreamUnreachable


class _SerialHopLike(Protocol):
    async def disconnect_port(self, port: str) -> dict: ...
    async def flash(self, **kwargs: Any) -> dict: ...


async def run_flash_job(
    *,
    conn_factory,
    blobs_root: Path,
    flash_id: str,
    client: _SerialHopLike,
    port: str,
    firmware: str,
    test_command: str | None,
    expected_response: str | None,
    skip_backup: bool = False,
) -> None:
    """Run the disconnect -> flash sequence and write the outcome into the DB.

    Never raises. Any exception is mapped onto the flash row's `status='error'`.
    A successful flash that returns a `backup` sub-object auto-saves it (sha256
    deduplicated) and links `backup_id` on the flash row.
    """
    started = time.monotonic()
    try:
        await client.disconnect_port(port)
        kwargs: dict[str, Any] = {"port": port, "firmware": firmware}
        if test_command is not None and expected_response is not None:
            kwargs["test_command"] = test_command
            kwargs["expected_response"] = expected_response
        if skip_backup:
            kwargs["skip_backup"] = True
        result = await client.flash(**kwargs)
        duration_ms = int((time.monotonic() - started) * 1000)
        backup_id: str | None = None
        backup = result.get("backup") if isinstance(result, dict) else None
        async with conn_factory() as conn:
            if isinstance(backup, dict) and backup.get("hex") and backup.get("sha256"):
                # Look up the originating flash row so we can echo its client/port/snapshot
                # into the new backup row as metadata.
                cur = await conn.execute(
                    "SELECT client, port_name, port_snapshot_json FROM flashes WHERE id = ?",
                    (flash_id,),
                )
                row = await cur.fetchone()
                if row is not None:
                    try:
                        snapshot = json.loads(row[2] or "{}")
                    except ValueError:
                        snapshot = {}
                    backup_id = await capture_or_reuse_backup(
                        conn,
                        blobs_dir=blobs_root / "backups",
                        client=row[0],
                        port_name=row[1],
                        port_snapshot=snapshot,
                        source_flash_id=flash_id,
                        backup=backup,
                    )
            await set_terminal_done(
                conn,
                flash_id=flash_id,
                outcome=str(result.get("outcome") or "") if isinstance(result, dict) else "",
                result_json=json.dumps(result),
                backup_id=backup_id,
                duration_ms=duration_ms,
            )
    except UpstreamErrorResponse as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn,
                flash_id=flash_id,
                error_code=exc.error_code,
                error_detail=exc.detail,
                duration_ms=duration_ms,
            )
    except UpstreamUnreachable as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn,
                flash_id=flash_id,
                error_code="upstream unreachable",
                error_detail=exc.detail,
                duration_ms=duration_ms,
            )
    except SerialHopError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn,
                flash_id=flash_id,
                error_code="upstream error",
                error_detail=str(exc),
                duration_ms=duration_ms,
            )
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn,
                flash_id=flash_id,
                error_code="internal error",
                error_detail=str(exc) or type(exc).__name__,
                duration_ms=duration_ms,
            )

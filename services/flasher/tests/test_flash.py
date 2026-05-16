from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.db import connect, migrate
from app.flash import run_flash_job
from app.flashes import create_running_flash, get_flash


class _StubClient:
    """In-memory stand-in for SerialHopClient."""

    def __init__(self, flash_response: dict | Exception) -> None:
        self._flash_response = flash_response
        self.disconnect_calls = 0
        self.flash_calls: list[dict] = []

    async def disconnect_devices(self) -> dict:
        self.disconnect_calls += 1
        return {"released": 0}

    async def flash(self, **kwargs: Any) -> dict:
        self.flash_calls.append(kwargs)
        if isinstance(self._flash_response, Exception):
            raise self._flash_response
        return self._flash_response


@pytest.fixture
async def ctx(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    blobs_root = tmp_path / "blobs"
    (blobs_root / "backups").mkdir(parents=True)
    (blobs_root / "firmware").mkdir(parents=True)
    await migrate(db_path)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def conn_factory():
        async with connect(db_path) as conn:
            yield conn

    yield {"db_path": db_path, "blobs_root": blobs_root, "conn_factory": conn_factory}


@pytest.mark.asyncio
async def test_run_flash_job_writes_done_and_saves_backup(ctx) -> None:
    async with connect(ctx["db_path"]) as conn:
        fid = await create_running_flash(
            conn,
            client="c",
            port_name="COM3",
            port_snapshot={"vid": "2341", "pid": "0043", "serial_number": "", "product": "u"},
            source_kind="firmware",
            source_id="fw-1",
            firmware_sha256="abc",
            firmware_name="x",
            test_command_used=None,
            expected_response_used=None,
            skip_backup=False,
        )
    response = {
        "outcome": "success",
        "port": "COM3",
        "stages": {"preflight": {"status": "ok"}},
        "backup": {
            "hex": ":00000001FF\n",
            "sha256": "bbb",
            "size_bytes": 12,
            "saved_path": "/x",
            "scope": "flash_only",
        },
    }
    stub = _StubClient(response)
    await run_flash_job(
        conn_factory=ctx["conn_factory"],
        blobs_root=ctx["blobs_root"],
        flash_id=fid,
        client=stub,
        port="COM3",
        firmware=":00000001FF\n",
        test_command=None,
        expected_response=None,
        skip_backup=False,
    )
    async with connect(ctx["db_path"]) as conn:
        row = await get_flash(conn, flash_id=fid)
    assert row["status"] == "done"
    assert row["outcome"] == "success"
    assert row["backup_id"] is not None
    assert stub.disconnect_calls == 1
    assert (ctx["blobs_root"] / "backups" / f"{row['backup_id']}.hex").exists()


@pytest.mark.asyncio
async def test_run_flash_job_dedup_reuses_existing_backup(ctx) -> None:
    # First flash writes the backup row.
    async with connect(ctx["db_path"]) as conn:
        a = await create_running_flash(
            conn,
            client="c",
            port_name="COM3",
            port_snapshot={},
            source_kind="firmware",
            source_id="fw-1",
            firmware_sha256="abc",
            firmware_name="x",
            test_command_used=None,
            expected_response_used=None,
            skip_backup=False,
        )
        b = await create_running_flash(
            conn,
            client="c",
            port_name="COM3",
            port_snapshot={},
            source_kind="firmware",
            source_id="fw-1",
            firmware_sha256="abc",
            firmware_name="x",
            test_command_used=None,
            expected_response_used=None,
            skip_backup=False,
        )
    resp = {
        "outcome": "success",
        "stages": {},
        "backup": {
            "hex": ":00000001FF\n",
            "sha256": "same",
            "size_bytes": 12,
            "saved_path": "/x",
            "scope": "flash_only",
        },
    }
    await run_flash_job(
        conn_factory=ctx["conn_factory"],
        blobs_root=ctx["blobs_root"],
        flash_id=a,
        client=_StubClient(resp),
        port="COM3",
        firmware="hex",
        test_command=None,
        expected_response=None,
        skip_backup=False,
    )
    await run_flash_job(
        conn_factory=ctx["conn_factory"],
        blobs_root=ctx["blobs_root"],
        flash_id=b,
        client=_StubClient(resp),
        port="COM3",
        firmware="hex",
        test_command=None,
        expected_response=None,
        skip_backup=False,
    )
    async with connect(ctx["db_path"]) as conn:
        ra = await get_flash(conn, flash_id=a)
        rb = await get_flash(conn, flash_id=b)
    assert ra["backup_id"] == rb["backup_id"]
    # Only one backup row was created.
    blobs = list((ctx["blobs_root"] / "backups").iterdir())
    assert len(blobs) == 1


@pytest.mark.asyncio
async def test_run_flash_job_upstream_unreachable(ctx) -> None:
    from app.serialhop import UpstreamUnreachable

    async with connect(ctx["db_path"]) as conn:
        fid = await create_running_flash(
            conn,
            client="c",
            port_name="COM3",
            port_snapshot={},
            source_kind="firmware",
            source_id="fw-1",
            firmware_sha256="abc",
            firmware_name="x",
            test_command_used=None,
            expected_response_used=None,
            skip_backup=False,
        )
    stub = _StubClient(UpstreamUnreachable(detail="connection refused"))
    await run_flash_job(
        conn_factory=ctx["conn_factory"],
        blobs_root=ctx["blobs_root"],
        flash_id=fid,
        client=stub,
        port="COM3",
        firmware="hex",
        test_command=None,
        expected_response=None,
        skip_backup=False,
    )
    async with connect(ctx["db_path"]) as conn:
        row = await get_flash(conn, flash_id=fid)
    assert row["status"] == "error"
    assert row["error_code"] == "upstream unreachable"

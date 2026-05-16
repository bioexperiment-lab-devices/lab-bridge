from __future__ import annotations

from pathlib import Path

import pytest

from app.db import connect, migrate
from app.flashes import (
    FlashNotFound,
    FlashStillRunning,
    create_running_flash,
    get_flash,
    get_running_flash,
    list_flashes,
    set_note,
    set_terminal_done,
    set_terminal_error,
)


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    await migrate(db_path)
    async with connect(db_path) as conn:
        yield conn


def _running_payload(**over) -> dict:
    base = dict(
        client="khamit",
        port_name="COM3",
        port_snapshot={"vid": "2341", "pid": "0043", "serial_number": "", "product": "Arduino Uno"},
        source_kind="firmware",
        source_id="fw-1",
        firmware_sha256="abc",
        firmware_name="pump v3",
        test_command_used="01",
        expected_response_used="aa",
        skip_backup=False,
    )
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_create_running_flash_inserts_row(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "running"
    assert row["client"] == "khamit"
    assert row["firmware_name"] == "pump v3"
    assert row["started_at"]


@pytest.mark.asyncio
async def test_set_terminal_done_writes_outcome_and_duration(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_done(
        db,
        flash_id=fid,
        outcome="success",
        result_json='{"outcome":"success"}',
        backup_id="b-1",
        duration_ms=12345,
    )
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "done"
    assert row["outcome"] == "success"
    assert row["result_json"] == '{"outcome":"success"}'
    assert row["backup_id"] == "b-1"
    assert row["duration_ms"] == 12345
    assert row["finished_at"]


@pytest.mark.asyncio
async def test_set_terminal_error(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_error(
        db,
        flash_id=fid,
        error_code="upstream unreachable",
        error_detail="connection refused",
        duration_ms=100,
    )
    row = await get_flash(db, flash_id=fid)
    assert row["status"] == "error"
    assert row["error_code"] == "upstream unreachable"


@pytest.mark.asyncio
async def test_get_unknown_returns_none(db) -> None:
    assert await get_flash(db, flash_id="no") is None


@pytest.mark.asyncio
async def test_get_running_flash_returns_most_recent(db) -> None:
    a = await create_running_flash(db, **_running_payload())
    b = await create_running_flash(db, **_running_payload())
    assert (await get_running_flash(db))["id"] == b
    await set_terminal_done(
        db, flash_id=b, outcome="success", result_json="{}", backup_id=None, duration_ms=1000
    )
    assert (await get_running_flash(db))["id"] == a


@pytest.mark.asyncio
async def test_list_flashes_with_filters(db) -> None:
    a = await create_running_flash(db, **_running_payload(client="khamit"))
    b = await create_running_flash(db, **_running_payload(client="other"))
    await set_terminal_done(
        db, flash_id=a, outcome="success", result_json="{}", backup_id=None, duration_ms=1000
    )
    await set_terminal_done(
        db, flash_id=b, outcome="failed_backup", result_json="{}", backup_id=None, duration_ms=2000
    )

    # filter by client
    page = await list_flashes(db, client=["khamit"])
    assert {x["id"] for x in page["items"]} == {a}

    # filter by outcome
    page = await list_flashes(db, outcome=["success"])
    assert {x["id"] for x in page["items"]} == {a}

    # date range — both should be included with wide range
    page = await list_flashes(db, since="2020-01-01T00:00:00Z", until="2030-01-01T00:00:00Z")
    assert len(page["items"]) == 2


@pytest.mark.asyncio
async def test_set_note_rejected_while_running(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    with pytest.raises(FlashStillRunning):
        await set_note(db, flash_id=fid, note="x")


@pytest.mark.asyncio
async def test_set_note_after_terminal(db) -> None:
    fid = await create_running_flash(db, **_running_payload())
    await set_terminal_done(
        db, flash_id=fid, outcome="success", result_json="{}", backup_id=None, duration_ms=1
    )
    await set_note(db, flash_id=fid, note="hello")
    row = await get_flash(db, flash_id=fid)
    assert row["operator_note"] == "hello"


@pytest.mark.asyncio
async def test_set_note_unknown_raises(db) -> None:
    with pytest.raises(FlashNotFound):
        await set_note(db, flash_id="no", note="x")

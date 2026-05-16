from __future__ import annotations

from pathlib import Path

import pytest

from app.backups import (
    BackupInUse,
    BackupNotFound,
    bulk_delete_backups,
    capture_or_reuse_backup,
    delete_backup,
    download_backup_bytes,
    get_backup,
    list_backups,
    update_backup,
)
from app.db import connect, migrate


@pytest.fixture
async def ctx(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    blobs_dir = tmp_path / "blobs" / "backups"
    blobs_dir.mkdir(parents=True)
    await migrate(db_path)
    async with connect(db_path) as conn:
        # Seed a flash row so source_flash_id has somewhere to point.
        await conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('flash-1', 'running', 'khamit', 'COM3', "
            '\'{"vid":"2341","pid":"0043","serial_number":"","product":"Arduino Uno"}\', '
            "'firmware', 'fw-1', 'sha', 'fw', 0, '2026-01-01T00:00:00Z')"
        )
        await conn.commit()
        yield {"conn": conn, "blobs_dir": blobs_dir}


def _backup_payload() -> dict:
    return {
        "hex": ":00000001FF\n",
        "sha256": "abc123",
        "size_bytes": 12,
        "saved_path": "C:\\backups\\COM3-x.hex",
        "scope": "flash_only",
    }


@pytest.mark.asyncio
async def test_capture_first_time_inserts_row_and_blob(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={
            "vid": "2341",
            "pid": "0043",
            "serial_number": "",
            "product": "Arduino Uno",
        },
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    row = await get_backup(ctx["conn"], backup_id=bid)
    assert row["sha256"] == "abc123"
    assert (ctx["blobs_dir"] / f"{bid}.hex").read_text() == ":00000001FF\n"


@pytest.mark.asyncio
async def test_capture_with_same_sha_returns_existing_id(ctx) -> None:
    first = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    # Second capture: same sha, different port/client — should reuse.
    second = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="other",
        port_name="COM4",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    assert first == second
    # No second blob written.
    blobs = list(ctx["blobs_dir"].iterdir())
    assert len(blobs) == 1


@pytest.mark.asyncio
async def test_get_backup_returns_none_for_unknown(ctx) -> None:
    assert await get_backup(ctx["conn"], backup_id="no") is None


@pytest.mark.asyncio
async def test_list_backups_paginates(ctx) -> None:
    payloads = []
    for i in range(3):
        p = _backup_payload()
        p["sha256"] = f"sha-{i}"
        await capture_or_reuse_backup(
            ctx["conn"],
            blobs_dir=ctx["blobs_dir"],
            client="khamit",
            port_name=f"COM{i}",
            port_snapshot={},
            source_flash_id="flash-1",
            backup=p,
        )
        payloads.append(p)
    page = await list_backups(ctx["conn"], limit=2)
    assert len(page["items"]) == 2
    assert page["next_before"]


@pytest.mark.asyncio
async def test_update_backup_mutates_labels(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    row = await update_backup(
        ctx["conn"],
        backup_id=bid,
        name="known good",
        description="d",
        test_command="01",
        expected_response="aa",
    )
    assert row["name"] == "known good"
    assert row["test_command"] == "01"


@pytest.mark.asyncio
async def test_update_unknown_raises(ctx) -> None:
    with pytest.raises(BackupNotFound):
        await update_backup(ctx["conn"], backup_id="no", name="x")


@pytest.mark.asyncio
async def test_delete_backup_removes_row_and_blob(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    await delete_backup(ctx["conn"], blobs_dir=ctx["blobs_dir"], backup_id=bid)
    assert await get_backup(ctx["conn"], backup_id=bid) is None
    assert not (ctx["blobs_dir"] / f"{bid}.hex").exists()


@pytest.mark.asyncio
async def test_delete_refuses_when_running_flash_references(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    await ctx["conn"].execute(
        "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
        "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
        "VALUES ('flash-2', 'running', 'c', 'COM3', '{}', 'backup', ?, 'sha', 'n', 0, '2026-01-01T00:00:00Z')",
        (bid,),
    )
    await ctx["conn"].commit()
    with pytest.raises(BackupInUse):
        await delete_backup(ctx["conn"], blobs_dir=ctx["blobs_dir"], backup_id=bid)


@pytest.mark.asyncio
async def test_bulk_delete_mixed_outcomes(ctx) -> None:
    a = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup={**_backup_payload(), "sha256": "sha-a"},
    )
    b = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup={**_backup_payload(), "sha256": "sha-b"},
    )
    # b is in flight; a is free.
    await ctx["conn"].execute(
        "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
        "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
        "VALUES ('flash-running', 'running', 'c', 'COM3', '{}', 'backup', ?, 'sha', 'n', 0, '2026-01-01T00:00:00Z')",
        (b,),
    )
    await ctx["conn"].commit()
    result = await bulk_delete_backups(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        ids=[a, b, "missing"],
    )
    assert result["deleted"] == 1
    refused = {r["id"]: r["reason"] for r in result["refused"]}
    assert refused[b] == "flash in flight"
    assert refused["missing"] == "unknown backup"


@pytest.mark.asyncio
async def test_download_backup_bytes(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        client="khamit",
        port_name="COM3",
        port_snapshot={},
        source_flash_id="flash-1",
        backup=_backup_payload(),
    )
    body = await download_backup_bytes(ctx["blobs_dir"], backup_id=bid)
    assert body == ":00000001FF\n"

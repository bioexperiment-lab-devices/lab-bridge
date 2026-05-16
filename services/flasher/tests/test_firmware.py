from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.db import connect, migrate
from app.firmware import (
    FirmwareInUse,
    FirmwareNotFound,
    create_firmware,
    delete_firmware,
    download_firmware_bytes,
    get_firmware,
    list_firmware,
    update_firmware,
)
from app.tags import create_tag


@pytest.fixture
async def ctx(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    blobs_dir = tmp_path / "blobs" / "firmware"
    blobs_dir.mkdir(parents=True)
    await migrate(db_path)
    async with connect(db_path) as conn:
        yield {"conn": conn, "blobs_dir": blobs_dir}


@pytest.mark.asyncio
async def test_create_firmware_writes_row_and_blob(ctx) -> None:
    hex_text = ":00000001FF\n"
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="pump v3",
        description="desc",
        firmware=hex_text,
        test_command="01",
        expected_response="aa",
        original_filename="pump.hex",
        tag_ids=[],
    )
    assert row["name"] == "pump v3"
    assert row["sha256"] == hashlib.sha256(hex_text.encode()).hexdigest()
    assert row["size_bytes"] == len(hex_text.encode())
    assert row["original_filename"] == "pump.hex"
    assert row["tags"] == []
    blob = ctx["blobs_dir"] / f"{row['id']}.hex"
    assert blob.read_text() == hex_text


@pytest.mark.asyncio
async def test_create_firmware_with_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    b = await create_tag(ctx["conn"], name="prod")
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="f",
        firmware=":00000001FF\n",
        tag_ids=[a["id"], b["id"]],
    )
    names = {t["name"] for t in row["tags"]}
    assert names == {"pump", "prod"}


@pytest.mark.asyncio
async def test_get_firmware_returns_full_row(ctx) -> None:
    created = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="x",
        firmware=":00000001FF\n",
        tag_ids=[],
    )
    got = await get_firmware(ctx["conn"], firmware_id=created["id"])
    assert got["id"] == created["id"]
    assert got["stats"] == {
        "total": 0,
        "successes": 0,
        "rollbacks": 0,
        "failures": 0,
        "last_flashed_at": None,
        "last_flashed_client": None,
        "last_flashed_port": None,
    }


@pytest.mark.asyncio
async def test_get_unknown_returns_none(ctx) -> None:
    assert await get_firmware(ctx["conn"], firmware_id="no") is None


@pytest.mark.asyncio
async def test_list_firmware_pagination_and_tag_filter(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="aa",
        firmware=":00000001FF\n",
        tag_ids=[a["id"]],
    )
    await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="bb", firmware=":00000001FE\n", tag_ids=[]
    )

    page = await list_firmware(ctx["conn"], limit=10)
    assert len(page["items"]) == 2

    filtered = await list_firmware(ctx["conn"], tag_ids=[a["id"]])
    assert [x["name"] for x in filtered["items"]] == ["aa"]


@pytest.mark.asyncio
async def test_update_firmware_mutates_fields_and_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    updated = await update_firmware(
        ctx["conn"],
        firmware_id=row["id"],
        name="y",
        description="d",
        test_command="03",
        expected_response="bb",
        tag_ids=[a["id"]],
    )
    assert updated["name"] == "y"
    assert updated["description"] == "d"
    assert updated["test_command"] == "03"
    assert [t["name"] for t in updated["tags"]] == ["pump"]


@pytest.mark.asyncio
async def test_update_unknown_raises(ctx) -> None:
    with pytest.raises(FirmwareNotFound):
        await update_firmware(ctx["conn"], firmware_id="no", name="x")


@pytest.mark.asyncio
async def test_delete_firmware_removes_row_blob_and_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    row = await create_firmware(
        ctx["conn"],
        blobs_dir=ctx["blobs_dir"],
        name="x",
        firmware=":00000001FF\n",
        tag_ids=[a["id"]],
    )
    await delete_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"], firmware_id=row["id"])
    assert await get_firmware(ctx["conn"], firmware_id=row["id"]) is None
    assert not (ctx["blobs_dir"] / f"{row['id']}.hex").exists()
    cur = await ctx["conn"].execute("SELECT COUNT(*) FROM firmware_tags")
    assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_delete_refuses_when_running_flash_references(ctx) -> None:
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    await ctx["conn"].execute(
        "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
        "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
        "VALUES ('j1', 'running', 'c', 'COM3', '{}', 'firmware', ?, 'sha', 'x', 0, '2026-01-01T00:00:00Z')",
        (row["id"],),
    )
    await ctx["conn"].commit()
    with pytest.raises(FirmwareInUse):
        await delete_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"], firmware_id=row["id"])
    # row still exists
    assert await get_firmware(ctx["conn"], firmware_id=row["id"]) is not None


@pytest.mark.asyncio
async def test_download_firmware_bytes(ctx) -> None:
    row = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"], name="x", firmware=":00000001FF\n", tag_ids=[]
    )
    data = await download_firmware_bytes(ctx["blobs_dir"], firmware_id=row["id"])
    assert data == ":00000001FF\n"

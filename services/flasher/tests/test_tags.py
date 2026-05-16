from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect, migrate
from app.tags import (
    DuplicateTagName,
    TagNotFound,
    create_tag,
    delete_tag,
    list_tags,
    rename_tag,
    set_firmware_tags,
)


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "flasher.db"
    await migrate(db_path)
    async with connect(db_path) as conn:
        yield conn


@pytest.mark.asyncio
async def test_create_then_list_tag(db) -> None:
    t = await create_tag(db, name="pump")
    assert t["name"] == "pump"
    assert t["id"]
    assert t["created_at"]
    items = await list_tags(db)
    assert [x["name"] for x in items] == ["pump"]
    assert items[0]["firmware_count"] == 0


@pytest.mark.asyncio
async def test_duplicate_name_raises(db) -> None:
    await create_tag(db, name="pump")
    with pytest.raises(DuplicateTagName):
        await create_tag(db, name="pump")


@pytest.mark.asyncio
async def test_rename_tag(db) -> None:
    t = await create_tag(db, name="pump")
    await rename_tag(db, tag_id=t["id"], name="pumps")
    items = await list_tags(db)
    assert items[0]["name"] == "pumps"


@pytest.mark.asyncio
async def test_rename_duplicate_name_raises(db) -> None:
    await create_tag(db, name="pump")
    b = await create_tag(db, name="motor")
    with pytest.raises(DuplicateTagName):
        await rename_tag(db, tag_id=b["id"], name="pump")


@pytest.mark.asyncio
async def test_rename_unknown_raises(db) -> None:
    with pytest.raises(TagNotFound):
        await rename_tag(db, tag_id="no-such-id", name="x")


@pytest.mark.asyncio
async def test_delete_tag_cascades_firmware_tags(db) -> None:
    t = await create_tag(db, name="pump")
    # Insert a firmware row directly (no firmware module yet).
    await db.execute(
        "INSERT INTO firmware (id, name, sha256, size_bytes, created_at) "
        "VALUES ('f1', 'fw', 'abc', 1, '2026-01-01T00:00:00Z')"
    )
    await db.execute("INSERT INTO firmware_tags (firmware_id, tag_id) VALUES ('f1', ?)", (t["id"],))
    await db.commit()

    await delete_tag(db, tag_id=t["id"])
    cur = await db.execute("SELECT COUNT(*) FROM firmware_tags")
    assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_delete_unknown_raises(db) -> None:
    with pytest.raises(TagNotFound):
        await delete_tag(db, tag_id="no-such-id")


@pytest.mark.asyncio
async def test_set_firmware_tags_replaces_existing(db) -> None:
    a = await create_tag(db, name="pump")
    b = await create_tag(db, name="motor")
    c = await create_tag(db, name="prod")
    await db.execute(
        "INSERT INTO firmware (id, name, sha256, size_bytes, created_at) "
        "VALUES ('f1', 'fw', 'abc', 1, '2026-01-01T00:00:00Z')"
    )
    await db.commit()

    await set_firmware_tags(db, firmware_id="f1", tag_ids=[a["id"], b["id"]])
    cur = await db.execute("SELECT tag_id FROM firmware_tags WHERE firmware_id='f1'")
    rows = sorted([r[0] for r in await cur.fetchall()])
    assert rows == sorted([a["id"], b["id"]])

    await set_firmware_tags(db, firmware_id="f1", tag_ids=[c["id"]])
    cur = await db.execute("SELECT tag_id FROM firmware_tags WHERE firmware_id='f1'")
    rows = [r[0] for r in await cur.fetchall()]
    assert rows == [c["id"]]


@pytest.mark.asyncio
async def test_set_firmware_tags_unknown_id_raises(db) -> None:
    await db.execute(
        "INSERT INTO firmware (id, name, sha256, size_bytes, created_at) "
        "VALUES ('f1', 'fw', 'abc', 1, '2026-01-01T00:00:00Z')"
    )
    await db.commit()
    with pytest.raises(TagNotFound):
        await set_firmware_tags(db, firmware_id="f1", tag_ids=["no-such-tag"])


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    import app.main as m

    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c


def test_post_tag_then_list(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/tags", json={"name": "pump"})
    assert r.status_code == 200
    assert r.json()["name"] == "pump"
    r = http_app.get("/flash/api/tags")
    assert [t["name"] for t in r.json()["items"]] == ["pump"]


def test_post_duplicate_name_400(http_app: TestClient) -> None:
    http_app.post("/flash/api/tags", json={"name": "pump"})
    r = http_app.post("/flash/api/tags", json={"name": "pump"})
    assert r.status_code == 400
    assert r.json()["error"] == "name in use"


def test_patch_rename(http_app: TestClient) -> None:
    tid = http_app.post("/flash/api/tags", json={"name": "pump"}).json()["id"]
    r = http_app.patch(f"/flash/api/tags/{tid}", json={"name": "pumps"})
    assert r.status_code == 200
    assert r.json()["name"] == "pumps"


def test_delete_tag(http_app: TestClient) -> None:
    tid = http_app.post("/flash/api/tags", json={"name": "pump"}).json()["id"]
    r = http_app.delete(f"/flash/api/tags/{tid}")
    assert r.status_code == 200
    r = http_app.get("/flash/api/tags")
    assert r.json()["items"] == []


def test_delete_unknown_404(http_app: TestClient) -> None:
    r = http_app.delete("/flash/api/tags/no-such-id")
    assert r.status_code == 404

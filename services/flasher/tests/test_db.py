from __future__ import annotations

from pathlib import Path

import pytest

from app.db import connect, migrate, MIGRATIONS_DIR


@pytest.mark.asyncio
async def test_connect_applies_pragmas(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    async with connect(db_path) as conn:
        row = await (await conn.execute("PRAGMA journal_mode")).fetchone()
        assert row[0] == "wal"
        row = await (await conn.execute("PRAGMA foreign_keys")).fetchone()
        assert row[0] == 1
        row = await (await conn.execute("PRAGMA synchronous")).fetchone()
        # NORMAL == 1
        assert row[0] == 1


@pytest.mark.asyncio
async def test_migrate_on_fresh_db_creates_schema_version(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    # Stage a minimal migration file just for this test.
    test_migrations = tmp_path / "migrations"
    test_migrations.mkdir()
    (test_migrations / "0001_init.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL);\n"
        "INSERT INTO schema_version (version) VALUES (0);\n"
        "CREATE TABLE demo (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    version = await migrate(db_path, migrations_dir=test_migrations)
    assert version == 1

    async with connect(db_path) as conn:
        cur = await conn.execute("SELECT version FROM schema_version")
        row = await cur.fetchone()
        assert row == (1,)
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demo'")
        assert (await cur.fetchone()) is not None


@pytest.mark.asyncio
async def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    test_migrations = tmp_path / "migrations"
    test_migrations.mkdir()
    (test_migrations / "0001_init.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL);\n"
        "INSERT INTO schema_version (version) VALUES (0);\n"
        "CREATE TABLE demo (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    await migrate(db_path, migrations_dir=test_migrations)
    # Second call must not re-apply (would explode on CREATE TABLE).
    version = await migrate(db_path, migrations_dir=test_migrations)
    assert version == 1


@pytest.mark.asyncio
async def test_migrate_applies_pending_in_order(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    test_migrations = tmp_path / "migrations"
    test_migrations.mkdir()
    (test_migrations / "0001_init.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL);\n"
        "INSERT INTO schema_version (version) VALUES (0);\n"
        "CREATE TABLE a (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    await migrate(db_path, migrations_dir=test_migrations)

    (test_migrations / "0002_add_b.sql").write_text(
        "CREATE TABLE b (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    version = await migrate(db_path, migrations_dir=test_migrations)
    assert version == 2

    async with connect(db_path) as conn:
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='b'")
        assert (await cur.fetchone()) is not None


@pytest.mark.asyncio
async def test_migrate_rolls_back_on_bad_sql(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    test_migrations = tmp_path / "migrations"
    test_migrations.mkdir()
    (test_migrations / "0001_init.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL);\n"
        "INSERT INTO schema_version (version) VALUES (0);\n"
        "CREATE TABLE a (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )
    await migrate(db_path, migrations_dir=test_migrations)

    (test_migrations / "0002_bad.sql").write_text(
        "CREATE TABLE c (id INTEGER PRIMARY KEY);\nNOT VALID SQL;\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        await migrate(db_path, migrations_dir=test_migrations)

    # Roll-back means: table c was NOT created and version is still 1.
    async with connect(db_path) as conn:
        cur = await conn.execute("SELECT version FROM schema_version")
        assert (await cur.fetchone()) == (1,)
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='c'")
        assert (await cur.fetchone()) is None


@pytest.mark.asyncio
async def test_real_init_migration_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    version = await migrate(db_path)  # uses the package's MIGRATIONS_DIR
    assert version >= 1

    expected = {"schema_version", "firmware", "backups", "flashes", "tags", "firmware_tags"}
    async with connect(db_path) as conn:
        cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        names = {row[0] async for row in cur}
    missing = expected - names
    assert not missing, f"missing tables: {missing}"


@pytest.mark.asyncio
async def test_real_init_migration_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "flasher.db"
    await migrate(db_path)
    async with connect(db_path) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        names = {row[0] async for row in cur}
    for needed in [
        "idx_firmware_name", "idx_firmware_sha256",
        "idx_backups_captured_at", "idx_backups_client_port",
        "idx_flashes_started_at", "idx_flashes_source",
        "idx_flashes_status", "idx_flashes_client", "idx_flashes_outcome",
    ]:
        assert needed in names, f"missing index: {needed}"

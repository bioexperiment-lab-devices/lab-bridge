# Flasher Library, History, and Tabs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the flasher service into a stateful tool with persistent firmware and backup libraries, an immutable flash audit log, a tabbed SPA, sha256-deduped backups, a bearer-auth firmware upload endpoint for CI, and tags + filters.

**Architecture:** Add a SQLite database (WAL mode, `aiosqlite`) plus a `.hex` blob store under a new bind-mounted `flasher_data/` volume. Split the FastAPI app into a `routes/` package backed by per-table modules (`firmware.py`, `backups.py`, `flashes.py`, `tags.py`) wrapping plain SQL. Flash records insert at click time and mutate only into `done` / `error` / `interrupted`. Frontend becomes a four-tab SPA (Flash, Firmware, Backups, Logs); the Flash tab's form is always rendered at the top, with running/result views below — no mode switch, no "Done" / "Flash another" buttons.

**Tech Stack:** Python 3.13, FastAPI, `aiosqlite`, Pydantic, pytest + httpx, React 18 + TypeScript + Vite, Caddy, Docker Compose, release-please, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-16-flasher-library-design.md`

---

## File structure (created / modified / deleted)

**Created — backend:**

- `services/flasher/app/db.py` — connection factory + migration runner
- `services/flasher/app/migrations/0001_init.sql` — full schema
- `services/flasher/app/firmware.py` — firmware row CRUD + blob I/O
- `services/flasher/app/backups.py` — backup row CRUD + blob I/O + sha256 dedup
- `services/flasher/app/flashes.py` — flash row CRUD + stats queries + background runner
- `services/flasher/app/tags.py` — tag CRUD + `firmware_tags` join helpers
- `services/flasher/app/routes/__init__.py` — `make_router(settings, deps)` aggregator
- `services/flasher/app/routes/clients.py` — `/api/clients[/{name}/ports]`
- `services/flasher/app/routes/firmware.py` — `/api/firmware/*` and `/api/v1/firmware/*`
- `services/flasher/app/routes/backups.py` — `/api/backups/*`
- `services/flasher/app/routes/flashes.py` — `/api/flash`, `/api/flashes`, `/api/flash/*`, `/api/flashes/*`
- `services/flasher/app/routes/tags.py` — `/api/tags/*`
- `services/flasher/tests/test_db.py`
- `services/flasher/tests/test_firmware.py`
- `services/flasher/tests/test_backups.py`
- `services/flasher/tests/test_flashes.py`
- `services/flasher/tests/test_tags.py`
- `services/flasher/tests/e2e/test_firmware_lifecycle.py`
- `services/flasher/tests/e2e/test_flash_from_record.py`
- `services/flasher/tests/e2e/test_flash_from_backup.py`
- `services/flasher/tests/e2e/test_promote_backup.py`
- `services/flasher/tests/e2e/test_bulk_delete_backups.py`
- `services/flasher/tests/e2e/test_delete_refused_while_running.py`
- `services/flasher/tests/e2e/test_replay_after_source_deletion.py`
- `services/flasher/tests/e2e/test_bearer_upload.py`
- `services/flasher/tests/e2e/test_logs_filters.py`

**Created — frontend:**

- `services/flasher/web/src/components/TabBar.tsx`
- `services/flasher/web/src/components/FirmwareSourcePicker.tsx`
- `services/flasher/web/src/components/FirmwareUploadForm.tsx`
- `services/flasher/web/src/components/FirmwareList.tsx`
- `services/flasher/web/src/components/FirmwareDetail.tsx`
- `services/flasher/web/src/components/TagManager.tsx`
- `services/flasher/web/src/components/TagChip.tsx`
- `services/flasher/web/src/components/BackupList.tsx`
- `services/flasher/web/src/components/BackupDetail.tsx`
- `services/flasher/web/src/components/PromoteBackupModal.tsx`
- `services/flasher/web/src/components/LogTable.tsx`
- `services/flasher/web/src/components/LogFilters.tsx`
- `services/flasher/web/src/components/LogDetailDrawer.tsx`
- `services/flasher/web/src/components/StatsCard.tsx`
- `services/flasher/web/src/tabs/FlashTab.tsx`
- `services/flasher/web/src/tabs/FirmwareTab.tsx`
- `services/flasher/web/src/tabs/BackupsTab.tsx`
- `services/flasher/web/src/tabs/LogsTab.tsx`

**Modified — backend:**

- `services/flasher/pyproject.toml` — add `aiosqlite`
- `services/flasher/app/config.py` — add `data_dir`, `upload_token`
- `services/flasher/app/main.py` — startup migrations + interrupted-job sweep; mount router from `routes/`; remove `JobStore` reference
- `services/flasher/app/clients.py` — `load_roster_with_online` helper returning `online: bool` per entry
- `services/flasher/app/flash.py` — `run_flash_job` writes outcome to DB instead of `JobStore`; auto-saves backup with dedup
- `services/flasher/app/serialhop.py` — unchanged (carried forward)
- `services/flasher/tests/conftest.py` — autouse `FLASHER_DATA_DIR` pointing at `tmp_path`
- `services/flasher/tests/test_clients.py` — updated for online-flag response shape
- `services/flasher/tests/test_routes.py` — superseded by per-route tests; deleted after split
- `services/flasher/tests/test_flash.py` — adapted to DB-backed flash runner
- `services/flasher/tests/e2e/conftest.py` — compose stack gains `flasher_data` tmpfs + bearer token file
- `services/flasher/tests/e2e/compose.yaml` — same as above

**Modified — frontend:**

- `services/flasher/web/src/App.tsx` — replace single-page wizard with TabBar + four tabs; lift `running_flash_id` polling to app level
- `services/flasher/web/src/api.ts` — full API surface
- `services/flasher/web/src/types.ts` — all new response shapes
- `services/flasher/web/src/components/ClientPicker.tsx` — render offline rows muted
- `services/flasher/web/src/components/ResultView.tsx` — remove "Flash another" / "Done" buttons; remove `onFlashAnother`/`onDone` props
- `services/flasher/web/src/components/styles.css` — tab bar + new component styling

**Modified — platform:**

- `compose/docker-compose.yml.tmpl` — flasher gains `flasher_data` volume + `upload_token` file + new env vars
- `compose/Caddyfile.tmpl` — split `/flash*` into ordered bearer-first and basic_auth blocks
- `compose/config.ci.yaml.tmpl` — add `secrets.flasher_upload_token: ""` placeholder (CI provides real value via deploy step)
- `scripts/lib/render.sh` — render `compose/flasher/upload_token` from `secrets.flasher_upload_token`
- `taskfiles/secrets.yml` (or equivalent) — `secrets:rotate-flasher-upload-token` task
- `.github/workflows/deploy.yml` (and/or the release-please workflow that performs deploy) — inject `FLASHER_UPLOAD_TOKEN` from GH secret into the render step
- `tests/integration/test_routes_smoke.bats` — bearer endpoint reachable without basic_auth; 401 without bearer

**Deleted:**

- `services/flasher/app/routes.py` — split into `routes/` package
- `services/flasher/app/flash.py`'s `JobStore` class (file remains; class removed)
- `services/flasher/tests/test_routes.py` — replaced by per-module route tests

---

## Phasing overview

Tasks are grouped into 10 phases. Each phase ends in a green test suite and a commit. Phases are sequential — each builds on the previous.

1. **Foundation:** dependency, settings, DB connection + migrations, schema, startup wiring.
2. **Tags backend.**
3. **Firmware backend** (CRUD + bearer + download).
4. **Backups backend** (CRUD + dedup + bulk).
5. **Flashes backend** (insert-at-start, lifecycle, runner, stats, replay, list+filters).
6. **Clients & routes reorg.**
7. **Frontend foundation** (types, API client, tab bar, app shell).
8. **Firmware, Backups, Logs tabs.**
9. **Flash tab rework.**
10. **Deployment plumbing + e2e tests + bats smoke.**

---

## Phase 1 — Foundation

### Task 1.1: Add `aiosqlite` dependency

**Files:**
- Modify: `services/flasher/pyproject.toml`

- [ ] **Step 1: Add dependency**

In `services/flasher/pyproject.toml`, change the `dependencies` block from:
```toml
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "httpx>=0.27,<0.29",
]
```
to:
```toml
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "httpx>=0.27,<0.29",
    "aiosqlite>=0.20,<0.21",
]
```

- [ ] **Step 2: Lock**

Run from `services/flasher/`: `uv lock`
Expected: `uv.lock` is updated; no errors.

- [ ] **Step 3: Commit**

```bash
git add services/flasher/pyproject.toml services/flasher/uv.lock
git commit -m "chore(flasher): add aiosqlite dependency"
```

---

### Task 1.2: Extend `Settings` with `data_dir` and `upload_token`

**Files:**
- Modify: `services/flasher/app/config.py`
- Modify: `services/flasher/tests/test_config.py`

- [ ] **Step 1: Write failing tests for `data_dir`**

Replace `services/flasher/tests/test_config.py` with:
```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import load_settings


def test_load_settings_requires_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("FLASHER_DATA_DIR", raising=False)
    with pytest.raises(RuntimeError, match="FLASHER_DATA_DIR"):
        load_settings()


def test_load_settings_creates_data_dir_and_blob_subdirs(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "flasher_data"
    monkeypatch.setenv("FLASHER_DATA_DIR", str(data_dir))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN", raising=False)
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)

    s = load_settings()

    assert s.data_dir == data_dir.resolve()
    assert (data_dir / "blobs" / "firmware").is_dir()
    assert (data_dir / "blobs" / "backups").is_dir()


def test_load_settings_synthesises_token_when_neither_env_set(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN", raising=False)
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)

    s = load_settings()

    assert isinstance(s.upload_token, str)
    assert len(s.upload_token) >= 32


def test_load_settings_reads_token_from_file_when_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    tok_file = tmp_path / "token"
    tok_file.write_text("from-file-token\n", encoding="utf-8")
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN__FILE", str(tok_file))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "inline-token")  # __FILE wins

    s = load_settings()

    assert s.upload_token == "from-file-token"


def test_load_settings_reads_token_from_env_when_no_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("FLASHER_UPLOAD_TOKEN__FILE", raising=False)
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "inline-token")

    s = load_settings()

    assert s.upload_token == "inline-token"
```

- [ ] **Step 2: Run tests to verify they fail**

From `services/flasher/`: `uv run pytest tests/test_config.py -v`
Expected: 5 tests fail because `Settings` has no `data_dir` / `upload_token` fields and `load_settings` does not read those env vars.

- [ ] **Step 3: Update `Settings` and `load_settings`**

Replace `services/flasher/app/config.py` with:
```python
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    clients_file: Path
    chisel_host: str
    data_dir: Path
    upload_token: str
    version: str = "dev"
    git_sha: str = "unknown"


def _load_upload_token() -> str:
    tok_file = os.environ.get("FLASHER_UPLOAD_TOKEN__FILE")
    if tok_file:
        return Path(tok_file).read_text(encoding="utf-8").strip()
    inline = os.environ.get("FLASHER_UPLOAD_TOKEN", "").strip()
    if inline:
        return inline
    # Dev/test convenience: synthesize a per-process random token so the app boots
    # without configuration. Production deploys always set FLASHER_UPLOAD_TOKEN__FILE.
    return secrets.token_urlsafe(32)


def load_settings() -> Settings:
    clients_env = os.environ.get("FLASHER_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("FLASHER_CLIENTS_FILE env var is required")
    clients_file = Path(clients_env)

    chisel_host = os.environ.get("FLASHER_CHISEL_HOST", "chisel").strip() or "chisel"

    data_env = os.environ.get("FLASHER_DATA_DIR")
    if not data_env:
        raise RuntimeError("FLASHER_DATA_DIR env var is required")
    data_dir = Path(data_env).resolve()
    (data_dir / "blobs" / "firmware").mkdir(parents=True, exist_ok=True)
    (data_dir / "blobs" / "backups").mkdir(parents=True, exist_ok=True)

    upload_token = _load_upload_token()

    version = os.environ.get("LAB_BRIDGE_VERSION", "dev").strip() or "dev"
    git_sha = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown").strip() or "unknown"

    return Settings(
        clients_file=clients_file,
        chisel_host=chisel_host,
        data_dir=data_dir,
        upload_token=upload_token,
        version=version,
        git_sha=git_sha,
    )
```

- [ ] **Step 4: Update conftest autouse fixture for `FLASHER_DATA_DIR`**

Edit `services/flasher/tests/conftest.py` — add a third autouse fixture:
```python
@pytest.fixture(autouse=True)
def _data_dir_default(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "flasher_data"
    d.mkdir()
    monkeypatch.setenv("FLASHER_DATA_DIR", str(d))
    return d
```

- [ ] **Step 5: Run all flasher unit tests; expect config tests pass**

From `services/flasher/`: `uv run pytest tests/test_config.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/config.py services/flasher/tests/test_config.py services/flasher/tests/conftest.py
git commit -m "feat(flasher): config carries data_dir and upload_token"
```

---

### Task 1.3: Database connection factory and PRAGMA setup

**Files:**
- Create: `services/flasher/app/db.py`
- Create: `services/flasher/tests/test_db.py`

- [ ] **Step 1: Write failing test for `connect()`**

Create `services/flasher/tests/test_db.py`:
```python
from __future__ import annotations

from pathlib import Path

import aiosqlite
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
```

- [ ] **Step 2: Run; expect failure on import**

From `services/flasher/`: `uv run pytest tests/test_db.py -v`
Expected: ImportError or ModuleNotFoundError for `app.db`.

- [ ] **Step 3: Create `app/db.py` with connection factory**

Create `services/flasher/app/db.py`:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


@asynccontextmanager
async def connect(db_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """Open a SQLite connection with the project's standard PRAGMAs applied.

    WAL keeps readers unblocked by the single writer; foreign_keys is off by
    default in SQLite and must be enabled per connection; busy_timeout makes
    transient lock contention spin briefly instead of failing.
    """
    conn = await aiosqlite.connect(db_path)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA busy_timeout=5000")
        await conn.commit()
        yield conn
    finally:
        await conn.close()


async def migrate(db_path: Path) -> int:
    """Apply pending migrations in numeric order. Returns the resulting schema version."""
    raise NotImplementedError  # filled in by Task 1.4
```

- [ ] **Step 4: Run test; expect pass**

From `services/flasher/`: `uv run pytest tests/test_db.py::test_connect_applies_pragmas -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/db.py services/flasher/tests/test_db.py
git commit -m "feat(flasher): db.connect with WAL + foreign_keys PRAGMAs"
```

---

### Task 1.4: Migration runner

**Files:**
- Modify: `services/flasher/app/db.py`
- Modify: `services/flasher/tests/test_db.py`
- Create: `services/flasher/app/migrations/0001_init.sql` (empty for now — Task 1.5 fills it)
- Create: `services/flasher/app/migrations/__init__.py` (empty marker — required if migrations are inside the `app` package)

- [ ] **Step 1: Create the empty migrations directory**

```bash
mkdir -p services/flasher/app/migrations
touch services/flasher/app/migrations/__init__.py
```

- [ ] **Step 2: Write failing tests for `migrate()`**

Append to `services/flasher/tests/test_db.py`:
```python
from app.db import MIGRATIONS_DIR


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
```

- [ ] **Step 3: Run; expect failure**

From `services/flasher/`: `uv run pytest tests/test_db.py -v`
Expected: 4 new tests fail because `migrate` raises `NotImplementedError`.

- [ ] **Step 4: Implement `migrate()`**

Replace the `migrate` stub in `services/flasher/app/db.py` with:
```python
import re

_MIGRATION_RE = re.compile(r"^(\d+)_.+\.sql$")


async def migrate(db_path: Path, *, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply pending .sql migrations in numeric order.

    File naming: `NNNN_<slug>.sql` (any digit count, leading zeros OK). The
    numeric prefix is the migration's version. The first migration MUST
    create the `schema_version` table and INSERT a single row (any value)
    so subsequent migrations have somewhere to update.

    Idempotent: re-runs are no-ops once every file is applied. A failing
    migration leaves the schema_version unchanged and rolls back its DDL.
    """
    files: list[tuple[int, Path]] = []
    for p in sorted(migrations_dir.glob("*.sql")):
        m = _MIGRATION_RE.match(p.name)
        if not m:
            continue
        files.append((int(m.group(1)), p))
    files.sort(key=lambda t: t[0])
    if not files:
        return 0

    async with connect(db_path) as conn:
        # Determine current version. If the table doesn't exist yet, we're at 0
        # and the first migration is responsible for creating the table.
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        has_table = (await cur.fetchone()) is not None
        if has_table:
            cur = await conn.execute("SELECT version FROM schema_version")
            row = await cur.fetchone()
            current = int(row[0]) if row else 0
        else:
            current = 0

        for version, path in files:
            if version <= current:
                continue
            sql = path.read_text(encoding="utf-8")
            await conn.execute("BEGIN")
            try:
                await conn.executescript(sql)
                if version == files[0][0] and not has_table:
                    # Migration 1 just created schema_version + inserted a seed row;
                    # overwrite that seed to the migration's version.
                    await conn.execute("UPDATE schema_version SET version = ?", (version,))
                    has_table = True
                else:
                    await conn.execute("UPDATE schema_version SET version = ?", (version,))
                await conn.commit()
                current = version
            except Exception:
                await conn.rollback()
                raise

        return current
```

- [ ] **Step 5: Run tests; expect pass**

From `services/flasher/`: `uv run pytest tests/test_db.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/db.py services/flasher/app/migrations/__init__.py services/flasher/tests/test_db.py
git commit -m "feat(flasher): SQL migration runner"
```

---

### Task 1.5: Initial schema migration `0001_init.sql`

**Files:**
- Create: `services/flasher/app/migrations/0001_init.sql`
- Modify: `services/flasher/tests/test_db.py`

- [ ] **Step 1: Write failing test that asserts the real schema applies**

Append to `services/flasher/tests/test_db.py`:
```python
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
```

- [ ] **Step 2: Run; expect failure (file does not exist)**

From `services/flasher/`: `uv run pytest tests/test_db.py::test_real_init_migration_creates_all_tables -v`
Expected: fails — `app/migrations/` contains no real `.sql` file yet, so `migrate()` returns 0.

- [ ] **Step 3: Write the schema migration**

Create `services/flasher/app/migrations/0001_init.sql`:
```sql
-- 0001_init.sql — full schema for the flasher library + history.

CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
INSERT INTO schema_version (version) VALUES (0);

CREATE TABLE firmware (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    original_filename TEXT,
    test_command TEXT,
    expected_response TEXT,
    source_backup_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_firmware_name ON firmware(name);
CREATE INDEX idx_firmware_sha256 ON firmware(sha256);

CREATE TABLE backups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL UNIQUE,
    size_bytes INTEGER NOT NULL,
    client TEXT NOT NULL,
    port_name TEXT NOT NULL,
    vid TEXT,
    pid TEXT,
    serial_number TEXT,
    product TEXT,
    serialhop_saved_path TEXT,
    test_command TEXT,
    expected_response TEXT,
    source_flash_id TEXT NOT NULL,
    captured_at TEXT NOT NULL
);
CREATE INDEX idx_backups_captured_at ON backups(captured_at DESC);
CREATE INDEX idx_backups_client_port ON backups(client, port_name);

CREATE TABLE flashes (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    outcome TEXT,
    client TEXT NOT NULL,
    port_name TEXT NOT NULL,
    port_snapshot_json TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    firmware_sha256 TEXT NOT NULL,
    firmware_name TEXT NOT NULL,
    test_command_used TEXT,
    expected_response_used TEXT,
    skip_backup INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    result_json TEXT,
    error_code TEXT,
    error_detail TEXT,
    backup_id TEXT,
    operator_note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_flashes_started_at ON flashes(started_at DESC);
CREATE INDEX idx_flashes_source ON flashes(source_kind, source_id);
CREATE INDEX idx_flashes_status ON flashes(status);
CREATE INDEX idx_flashes_client ON flashes(client);
CREATE INDEX idx_flashes_outcome ON flashes(outcome);

CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE firmware_tags (
    firmware_id TEXT NOT NULL REFERENCES firmware(id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (firmware_id, tag_id)
);
```

- [ ] **Step 4: Run; expect pass**

From `services/flasher/`: `uv run pytest tests/test_db.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/migrations/0001_init.sql services/flasher/tests/test_db.py
git commit -m "feat(flasher): initial DB schema (firmware/backups/flashes/tags)"
```

---

### Task 1.6: Wire migrations into FastAPI startup; add on-boot interrupted-flash sweep

**Files:**
- Modify: `services/flasher/app/main.py`
- Modify: `services/flasher/tests/test_main.py`

- [ ] **Step 1: Write failing test asserting `flasher.db` exists after app boot**

Replace `services/flasher/tests/test_main.py` with:
```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    # Re-import main after env vars are set so load_settings + startup runs fresh.
    import importlib
    import app.main as m
    importlib.reload(m)
    return m.app


def test_app_boot_creates_database_file(app, tmp_path: Path) -> None:
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
    assert (tmp_path / "flasher.db").exists()
```

- [ ] **Step 2: Add a second failing test for interrupted-flash sweep**

Append to `services/flasher/tests/test_main.py`:
```python
import sqlite3


def test_app_boot_sweeps_running_flashes_to_interrupted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")

    # Build a DB with one "running" flash row, simulating a server crash.
    import asyncio
    from app.db import migrate

    db_path = tmp_path / "flasher.db"
    asyncio.run(migrate(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES (?, 'running', 'c', 'COM3', '{}', 'firmware', 'fid', 'sha', 'name', 0, '2026-01-01T00:00:00Z')",
            ("job-abc",),
        )
        conn.commit()

    import importlib
    import app.main as m
    importlib.reload(m)

    with TestClient(m.app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT status, error_code FROM flashes WHERE id = 'job-abc'").fetchone()
    assert row[0] == "interrupted"
    assert row[1] == "interrupted"
```

- [ ] **Step 3: Run; expect failure**

From `services/flasher/`: `uv run pytest tests/test_main.py -v`
Expected: both tests fail (DB file not created; running flashes not swept).

- [ ] **Step 4: Update `app/main.py` with startup hook**

Replace `services/flasher/app/main.py` with:
```python
from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.db import connect, migrate

STATIC_DIR = Path(__file__).parent / "static"

settings = load_settings()
app = FastAPI(title="lab-bridge flasher")


@app.on_event("startup")
async def _on_startup() -> None:
    db_path = settings.data_dir / "flasher.db"
    await migrate(db_path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    async with connect(db_path) as conn:
        await conn.execute(
            "UPDATE flashes SET status='interrupted', finished_at=?, "
            "error_code='interrupted', error_detail='server restarted while flash was running' "
            "WHERE status='running'",
            (now,),
        )
        await conn.commit()


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


if (STATIC_DIR / "assets").is_dir():
    app.mount("/flash/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="spa-assets")

if (STATIC_DIR / "index.html").is_file():

    @app.get("/flash/{path:path}")
    def spa_index(path: str) -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
```

Note: the router is intentionally NOT mounted yet — that comes in Phase 6, after the per-route modules exist. Until then, the app exposes only `/healthz` and the (optional) SPA paths. The existing v1 router import is removed so the app boots cleanly.

- [ ] **Step 5: Run; expect pass**

From `services/flasher/`: `uv run pytest tests/test_main.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run full unit suite to make sure nothing else broke**

From `services/flasher/`: `uv run pytest -v`
Expected: existing route tests (`test_routes.py`, `test_flash.py`) fail because their imports of the now-unmounted router break; mark these as `pytest.skip` for now (they are rewritten in Phase 6) by adding a single `pytestmark = pytest.mark.skip(reason="rewritten in Phase 6")` at the top of each file. Other tests pass.

Add `pytestmark = pytest.mark.skip(reason="rewritten in Phase 6")` to:
- `services/flasher/tests/test_routes.py`
- `services/flasher/tests/test_flash.py`

Re-run: `uv run pytest -v`. Expected: all non-skipped tests pass; the two files report skips.

- [ ] **Step 7: Commit**

```bash
git add services/flasher/app/main.py services/flasher/tests/test_main.py services/flasher/tests/test_routes.py services/flasher/tests/test_flash.py
git commit -m "feat(flasher): run migrations on boot; sweep stale running flashes"
```

---

## Phase 2 — Tags backend

### Task 2.1: `app/tags.py` — CRUD module

**Files:**
- Create: `services/flasher/app/tags.py`
- Create: `services/flasher/tests/test_tags.py`

- [ ] **Step 1: Write failing tests**

Create `services/flasher/tests/test_tags.py`:
```python
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

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
    a = await create_tag(db, name="pump")
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
```

- [ ] **Step 2: Run; expect import failure**

From `services/flasher/`: `uv run pytest tests/test_tags.py -v`
Expected: collection error / ImportError for `app.tags`.

- [ ] **Step 3: Implement `app/tags.py`**

Create `services/flasher/app/tags.py`:
```python
from __future__ import annotations

import time
import uuid
from typing import Any

import aiosqlite


class TagNotFound(Exception):
    """Raised when a tag id does not exist."""


class DuplicateTagName(Exception):
    """Raised when a tag name collides with an existing one."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


async def create_tag(conn: aiosqlite.Connection, *, name: str) -> dict[str, Any]:
    tag_id = uuid.uuid4().hex
    created_at = _now()
    try:
        await conn.execute(
            "INSERT INTO tags (id, name, created_at) VALUES (?, ?, ?)",
            (tag_id, name, created_at),
        )
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        if "tags.name" in str(exc) or "UNIQUE" in str(exc).upper():
            raise DuplicateTagName(name) from exc
        raise
    return {"id": tag_id, "name": name, "created_at": created_at, "firmware_count": 0}


async def list_tags(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
    cur = await conn.execute(
        "SELECT t.id, t.name, t.created_at, "
        "(SELECT COUNT(*) FROM firmware_tags ft WHERE ft.tag_id = t.id) AS firmware_count "
        "FROM tags t ORDER BY t.name COLLATE NOCASE ASC"
    )
    rows = await cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "created_at": r[2], "firmware_count": r[3]} for r in rows
    ]


async def rename_tag(conn: aiosqlite.Connection, *, tag_id: str, name: str) -> None:
    cur = await conn.execute("SELECT 1 FROM tags WHERE id = ?", (tag_id,))
    if (await cur.fetchone()) is None:
        raise TagNotFound(tag_id)
    try:
        await conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        if "UNIQUE" in str(exc).upper():
            raise DuplicateTagName(name) from exc
        raise


async def delete_tag(conn: aiosqlite.Connection, *, tag_id: str) -> None:
    cur = await conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    if cur.rowcount == 0:
        await conn.rollback()
        raise TagNotFound(tag_id)
    await conn.commit()


async def set_firmware_tags(
    conn: aiosqlite.Connection, *, firmware_id: str, tag_ids: list[str]
) -> None:
    """Replace the set of tags on `firmware_id` with `tag_ids`. Validates every id."""
    for tid in tag_ids:
        cur = await conn.execute("SELECT 1 FROM tags WHERE id = ?", (tid,))
        if (await cur.fetchone()) is None:
            raise TagNotFound(tid)
    await conn.execute("DELETE FROM firmware_tags WHERE firmware_id = ?", (firmware_id,))
    for tid in tag_ids:
        await conn.execute(
            "INSERT INTO firmware_tags (firmware_id, tag_id) VALUES (?, ?)",
            (firmware_id, tid),
        )
    await conn.commit()
```

- [ ] **Step 4: Run tests**

From `services/flasher/`: `uv run pytest tests/test_tags.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/tags.py services/flasher/tests/test_tags.py
git commit -m "feat(flasher): tags CRUD module"
```

---

## Phase 3 — Firmware backend

### Task 3.1: `app/firmware.py` — row CRUD + blob I/O

**Files:**
- Create: `services/flasher/app/firmware.py`
- Create: `services/flasher/tests/test_firmware.py`

- [ ] **Step 1: Write failing tests**

Create `services/flasher/tests/test_firmware.py`:
```python
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        name="f", firmware=":00000001FF\n", tag_ids=[a["id"], b["id"]],
    )
    names = {t["name"] for t in row["tags"]}
    assert names == {"pump", "prod"}


@pytest.mark.asyncio
async def test_get_firmware_returns_full_row(ctx) -> None:
    created = await create_firmware(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        name="x", firmware=":00000001FF\n", tag_ids=[],
    )
    got = await get_firmware(ctx["conn"], firmware_id=created["id"])
    assert got["id"] == created["id"]
    assert got["stats"] == {
        "total": 0, "successes": 0, "rollbacks": 0, "failures": 0,
        "last_flashed_at": None, "last_flashed_client": None, "last_flashed_port": None,
    }


@pytest.mark.asyncio
async def test_get_unknown_returns_none(ctx) -> None:
    assert await get_firmware(ctx["conn"], firmware_id="no") is None


@pytest.mark.asyncio
async def test_list_firmware_pagination_and_tag_filter(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                         name="aa", firmware=":00000001FF\n", tag_ids=[a["id"]])
    await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                         name="bb", firmware=":00000001FE\n", tag_ids=[])

    page = await list_firmware(ctx["conn"], limit=10)
    assert len(page["items"]) == 2

    filtered = await list_firmware(ctx["conn"], tag_ids=[a["id"]])
    assert [x["name"] for x in filtered["items"]] == ["aa"]


@pytest.mark.asyncio
async def test_update_firmware_mutates_fields_and_tags(ctx) -> None:
    a = await create_tag(ctx["conn"], name="pump")
    row = await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                                name="x", firmware=":00000001FF\n", tag_ids=[])
    updated = await update_firmware(
        ctx["conn"], firmware_id=row["id"],
        name="y", description="d", test_command="03",
        expected_response="bb", tag_ids=[a["id"]],
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
    row = await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                                name="x", firmware=":00000001FF\n", tag_ids=[a["id"]])
    await delete_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"], firmware_id=row["id"])
    assert await get_firmware(ctx["conn"], firmware_id=row["id"]) is None
    assert not (ctx["blobs_dir"] / f"{row['id']}.hex").exists()
    cur = await ctx["conn"].execute("SELECT COUNT(*) FROM firmware_tags")
    assert (await cur.fetchone())[0] == 0


@pytest.mark.asyncio
async def test_delete_refuses_when_running_flash_references(ctx) -> None:
    row = await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                                name="x", firmware=":00000001FF\n", tag_ids=[])
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
    row = await create_firmware(ctx["conn"], blobs_dir=ctx["blobs_dir"],
                                name="x", firmware=":00000001FF\n", tag_ids=[])
    data = await download_firmware_bytes(ctx["blobs_dir"], firmware_id=row["id"])
    assert data == ":00000001FF\n"
```

- [ ] **Step 2: Run; expect import failure**

From `services/flasher/`: `uv run pytest tests/test_firmware.py -v`
Expected: ImportError for `app.firmware`.

- [ ] **Step 3: Implement `app/firmware.py`**

Create `services/flasher/app/firmware.py`:
```python
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


async def _row_to_dict(
    conn: aiosqlite.Connection, row: aiosqlite.Row | tuple
) -> dict[str, Any]:
    cols = [
        "id", "name", "description", "sha256", "size_bytes", "original_filename",
        "test_command", "expected_response", "source_backup_id", "created_at",
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
            (firmware_id, name, description, sha256, size_bytes, original_filename,
             test_command, expected_response, source_backup_id, created_at),
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
        "SELECT f.id FROM firmware f " + where_sql +
        " ORDER BY f.created_at DESC, f.id DESC LIMIT ?"
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


async def delete_firmware(
    conn: aiosqlite.Connection, *, blobs_dir: Path, firmware_id: str
) -> None:
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


async def count_flashes_referencing(
    conn: aiosqlite.Connection, *, firmware_id: str
) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes WHERE source_kind = 'firmware' AND source_id = ?",
        (firmware_id,),
    )
    return int((await cur.fetchone())[0])
```

- [ ] **Step 4: Run tests; expect pass**

From `services/flasher/`: `uv run pytest tests/test_firmware.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/firmware.py services/flasher/tests/test_firmware.py
git commit -m "feat(flasher): firmware CRUD with blob I/O and stats"
```

---

### Task 3.2: Firmware HTTP routes (operator + bearer)

**Files:**
- Create: `services/flasher/app/routes/__init__.py` (router aggregator)
- Create: `services/flasher/app/routes/firmware.py`
- Modify: `services/flasher/app/main.py` (mount router)

This task wires the routes into the FastAPI app. Because subsequent phases keep adding routes to the same aggregator, the router itself is structured so each module exposes a `make_router(settings, conn_factory)` builder; `routes/__init__.py` composes them.

- [ ] **Step 1: Create `routes/__init__.py` skeleton**

Create `services/flasher/app/routes/__init__.py`:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Callable

import aiosqlite
from fastapi import APIRouter

from app.config import Settings
from app.db import connect

from app.routes import firmware as firmware_routes


ConnFactory = Callable[[], "asynccontextmanager[aiosqlite.Connection]"]


def make_router(settings: Settings) -> APIRouter:
    db_path = settings.data_dir / "flasher.db"
    blobs_root = settings.data_dir / "blobs"

    @asynccontextmanager
    async def conn_factory() -> AsyncIterator[aiosqlite.Connection]:
        async with connect(db_path) as conn:
            yield conn

    router = APIRouter()
    router.include_router(firmware_routes.make_router(settings, conn_factory, blobs_root))
    return router
```

- [ ] **Step 2: Write failing tests for firmware HTTP routes**

Append to `services/flasher/tests/test_firmware.py`:
```python
from fastapi.testclient import TestClient


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    import importlib
    import app.main as m
    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c


def test_post_firmware_creates_record(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/firmware", json={
        "name": "pump v3",
        "firmware": ":00000001FF\n",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "pump v3"
    assert body["sha256"]
    assert body["size_bytes"] > 0


def test_post_firmware_rejects_empty_firmware(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": ""})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid request"


def test_post_firmware_rejects_oversize(http_app: TestClient) -> None:
    big = "A" * (256 * 1024 + 1)
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": big})
    assert r.status_code == 400
    assert "exceeds" in r.json()["detail"]


def test_get_firmware_returns_one(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/firmware", json={"name": "x", "firmware": ":00000001FF\n"})
    fid = r.json()["id"]
    r = http_app.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    assert r.json()["id"] == fid


def test_get_firmware_404(http_app: TestClient) -> None:
    r = http_app.get("/flash/api/firmware/no-such-id")
    assert r.status_code == 404


def test_list_firmware_paginates(http_app: TestClient) -> None:
    for i in range(3):
        http_app.post("/flash/api/firmware",
                      json={"name": f"name-{i}", "firmware": f":000000{i:02d}FF\n"})
    r = http_app.get("/flash/api/firmware?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["next_before"]


def test_patch_firmware_updates_fields(http_app: TestClient) -> None:
    fid = http_app.post("/flash/api/firmware",
                        json={"name": "x", "firmware": ":00000001FF\n"}).json()["id"]
    r = http_app.patch(f"/flash/api/firmware/{fid}",
                       json={"name": "y", "description": "d"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "y"
    assert body["description"] == "d"


def test_delete_firmware_succeeds(http_app: TestClient) -> None:
    fid = http_app.post("/flash/api/firmware",
                        json={"name": "x", "firmware": ":00000001FF\n"}).json()["id"]
    r = http_app.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    r = http_app.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 404


def test_delete_firmware_409_when_running_flash_references(http_app: TestClient, tmp_path) -> None:
    fid = http_app.post("/flash/api/firmware",
                        json={"name": "x", "firmware": ":00000001FF\n"}).json()["id"]
    import sqlite3
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('jx', 'running', 'c', 'COM3', '{}', 'firmware', ?, 'sha', 'x', 0, '2026-01-01T00:00:00Z')",
            (fid,),
        )
        conn.commit()
    r = http_app.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 409
    assert r.json()["error"] == "cannot delete: flash in flight"


def test_download_firmware(http_app: TestClient) -> None:
    fid = http_app.post("/flash/api/firmware",
                        json={"name": "x", "firmware": ":00000001FF\n",
                              "original_filename": "x.hex"}).json()["id"]
    r = http_app.get(f"/flash/api/firmware/{fid}/download")
    assert r.status_code == 200
    assert r.text == ":00000001FF\n"
    assert "x.hex" in r.headers.get("content-disposition", "")


def test_bearer_post_requires_token(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/v1/firmware",
                      json={"name": "x", "firmware": ":00000001FF\n"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer required"


def test_bearer_post_wrong_token(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/v1/firmware",
                      json={"name": "x", "firmware": ":00000001FF\n"},
                      headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"


def test_bearer_post_succeeds(http_app: TestClient) -> None:
    r = http_app.post("/flash/api/v1/firmware",
                      json={"name": "x", "firmware": ":00000001FF\n"},
                      headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    assert r.json()["name"] == "x"


def test_bearer_get_by_sha256(http_app: TestClient) -> None:
    posted = http_app.post("/flash/api/v1/firmware",
                           json={"name": "x", "firmware": ":00000001FF\n"},
                           headers={"Authorization": "Bearer test-token"}).json()
    r = http_app.get(f"/flash/api/v1/firmware?sha256={posted['sha256']}",
                     headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200
    assert r.json()["id"] == posted["id"]

    r = http_app.get("/flash/api/v1/firmware?sha256=deadbeef",
                     headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 404
```

- [ ] **Step 3: Run; expect failures (routes do not exist yet)**

From `services/flasher/`: `uv run pytest tests/test_firmware.py -v -k "http_app or bearer"`
Expected: all new tests fail because the router is not mounted and `routes/firmware.py` doesn't exist.

- [ ] **Step 4: Implement `app/routes/firmware.py`**

Create `services/flasher/app/routes/firmware.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.config import Settings
from app.firmware import (
    FirmwareInUse,
    FirmwareNotFound,
    count_flashes_referencing,
    create_firmware,
    delete_firmware,
    download_firmware_bytes,
    get_firmware,
    get_firmware_by_sha256,
    list_firmware,
    update_firmware,
)
from app.tags import TagNotFound

MAX_FIRMWARE_BYTES = 256 * 1024


class _FirmwarePost(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    firmware: str
    test_command: str | None = None
    expected_response: str | None = None
    original_filename: str | None = None
    tags: list[str] = Field(default_factory=list)


class _FirmwarePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    test_command: str | None = None
    expected_response: str | None = None
    tags: list[str] | None = None
    # Sentinels: PATCH treats `test_command` / `expected_response` of `None`
    # in the JSON body as "set to NULL". An absent key means "do not touch".
    # FastAPI's model_dump(exclude_unset=True) handles that.


def _validate_firmware_bytes(body: _FirmwarePost) -> None:
    if not body.firmware:
        raise HTTPException(status_code=400, detail={
            "error": "invalid request", "detail": "firmware is empty",
        })
    if len(body.firmware.encode("utf-8")) > MAX_FIRMWARE_BYTES:
        raise HTTPException(status_code=400, detail={
            "error": "invalid request", "detail": "firmware exceeds 256 KiB",
        })


def _require_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={
            "error": "bearer required", "detail": "Authorization: Bearer <token> required",
        })
    if authorization[len("Bearer "):] != expected:
        raise HTTPException(status_code=401, detail={
            "error": "bearer invalid", "detail": "token does not match",
        })


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    fw_blobs = blobs_root / "firmware"

    # ----- Operator endpoints -----

    @router.get("/api/firmware")
    async def operator_list(
        tag: list[str] = Query(default_factory=list),
        q: str | None = None,
        limit: int = 100,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_firmware(conn, tag_ids=tag, q=q, limit=limit, before=before)

    @router.get("/api/firmware/{firmware_id}")
    async def operator_get(firmware_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_firmware(conn, firmware_id=firmware_id)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown firmware", "detail": firmware_id,
            })
        return row

    @router.post("/api/firmware")
    async def operator_post(body: _FirmwarePost) -> dict[str, Any]:
        _validate_firmware_bytes(body)
        async with conn_factory() as conn:
            try:
                return await create_firmware(
                    conn, blobs_dir=fw_blobs,
                    name=body.name, description=body.description,
                    firmware=body.firmware,
                    test_command=body.test_command,
                    expected_response=body.expected_response,
                    original_filename=body.original_filename,
                    tag_ids=body.tags,
                )
            except TagNotFound as exc:
                raise HTTPException(status_code=400, detail={
                    "error": "tag not found", "detail": str(exc),
                })

    @router.patch("/api/firmware/{firmware_id}")
    async def operator_patch(firmware_id: str, body: _FirmwarePatch) -> dict[str, Any]:
        kwargs = body.model_dump(exclude_unset=True)
        async with conn_factory() as conn:
            try:
                return await update_firmware(conn, firmware_id=firmware_id, **kwargs)
            except FirmwareNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown firmware", "detail": firmware_id,
                })
            except TagNotFound as exc:
                raise HTTPException(status_code=400, detail={
                    "error": "tag not found", "detail": str(exc),
                })

    @router.delete("/api/firmware/{firmware_id}")
    async def operator_delete(firmware_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_firmware(conn, blobs_dir=fw_blobs, firmware_id=firmware_id)
            except FirmwareInUse:
                raise HTTPException(status_code=409, detail={
                    "error": "cannot delete: flash in flight", "detail": firmware_id,
                })
            except FirmwareNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown firmware", "detail": firmware_id,
                })
        return {"status": "deleted"}

    @router.get("/api/firmware/{firmware_id}/download")
    async def operator_download(firmware_id: str) -> Response:
        async with conn_factory() as conn:
            row = await get_firmware(conn, firmware_id=firmware_id)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown firmware", "detail": firmware_id,
            })
        body = await download_firmware_bytes(fw_blobs, firmware_id=firmware_id)
        filename = row["original_filename"] or f"{firmware_id}.hex"
        return PlainTextResponse(
            content=body,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ----- Bearer-auth endpoints -----

    @router.post("/api/v1/firmware")
    async def bearer_post(
        body: _FirmwarePost,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer(authorization, settings.upload_token)
        _validate_firmware_bytes(body)
        async with conn_factory() as conn:
            try:
                return await create_firmware(
                    conn, blobs_dir=fw_blobs,
                    name=body.name, description=body.description,
                    firmware=body.firmware,
                    test_command=body.test_command,
                    expected_response=body.expected_response,
                    original_filename=body.original_filename,
                    tag_ids=body.tags,
                )
            except TagNotFound as exc:
                raise HTTPException(status_code=400, detail={
                    "error": "tag not found", "detail": str(exc),
                })

    @router.get("/api/v1/firmware")
    async def bearer_get_by_sha256(
        sha256: str = Query(min_length=64, max_length=64),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer(authorization, settings.upload_token)
        async with conn_factory() as conn:
            row = await get_firmware_by_sha256(conn, sha256=sha256)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown firmware", "detail": sha256,
            })
        return row

    return router
```

- [ ] **Step 5: Mount the router in `app/main.py`**

Edit `services/flasher/app/main.py` — add after the `settings = load_settings()` line:
```python
from app.routes import make_router
```
and after the `app = FastAPI(...)` line:
```python
app.include_router(make_router(settings), prefix="/flash")
```

- [ ] **Step 6: Run firmware tests; expect pass**

From `services/flasher/`: `uv run pytest tests/test_firmware.py -v`
Expected: all 24 tests pass (the 10 module tests + 14 HTTP tests).

- [ ] **Step 7: Commit**

```bash
git add services/flasher/app/routes/__init__.py services/flasher/app/routes/firmware.py services/flasher/app/main.py services/flasher/tests/test_firmware.py
git commit -m "feat(flasher): firmware HTTP routes (operator + bearer)"
```

---

### Task 3.3: Tags HTTP routes

**Files:**
- Create: `services/flasher/app/routes/tags.py`
- Modify: `services/flasher/app/routes/__init__.py`
- Modify: `services/flasher/tests/test_tags.py`

- [ ] **Step 1: Write failing tests for tag HTTP routes**

Append to `services/flasher/tests/test_tags.py`:
```python
from fastapi.testclient import TestClient


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    import importlib, app.main as m
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
```

- [ ] **Step 2: Run; expect failure**

From `services/flasher/`: `uv run pytest tests/test_tags.py -v -k http_app`
Expected: tag routes don't exist; tests fail.

- [ ] **Step 3: Implement `routes/tags.py`**

Create `services/flasher/app/routes/tags.py`:
```python
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings
from app.tags import (
    DuplicateTagName,
    TagNotFound,
    create_tag,
    delete_tag,
    list_tags,
    rename_tag,
)


class _TagPost(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class _TagPatch(BaseModel):
    name: str = Field(min_length=1, max_length=128)


def make_router(settings: Settings, conn_factory) -> APIRouter:
    router = APIRouter()

    @router.get("/api/tags")
    async def get_all() -> dict[str, Any]:
        async with conn_factory() as conn:
            return {"items": await list_tags(conn)}

    @router.post("/api/tags")
    async def post(body: _TagPost) -> dict[str, Any]:
        async with conn_factory() as conn:
            try:
                return await create_tag(conn, name=body.name)
            except DuplicateTagName:
                raise HTTPException(status_code=400, detail={
                    "error": "name in use", "detail": body.name,
                })

    @router.patch("/api/tags/{tag_id}")
    async def patch(tag_id: str, body: _TagPatch) -> dict[str, Any]:
        async with conn_factory() as conn:
            try:
                await rename_tag(conn, tag_id=tag_id, name=body.name)
            except TagNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown tag", "detail": tag_id,
                })
            except DuplicateTagName:
                raise HTTPException(status_code=400, detail={
                    "error": "name in use", "detail": body.name,
                })
            tags = await list_tags(conn)
            for t in tags:
                if t["id"] == tag_id:
                    return t
            raise HTTPException(status_code=500, detail={"error": "internal", "detail": ""})

    @router.delete("/api/tags/{tag_id}")
    async def delete(tag_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_tag(conn, tag_id=tag_id)
            except TagNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown tag", "detail": tag_id,
                })
        return {"status": "deleted"}

    return router
```

- [ ] **Step 4: Wire into the aggregator**

Edit `services/flasher/app/routes/__init__.py` — add the import and `include_router` call so the file becomes:
```python
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from fastapi import APIRouter

from app.config import Settings
from app.db import connect

from app.routes import firmware as firmware_routes
from app.routes import tags as tags_routes


def make_router(settings: Settings) -> APIRouter:
    db_path = settings.data_dir / "flasher.db"
    blobs_root = settings.data_dir / "blobs"

    @asynccontextmanager
    async def conn_factory() -> AsyncIterator[aiosqlite.Connection]:
        async with connect(db_path) as conn:
            yield conn

    router = APIRouter()
    router.include_router(firmware_routes.make_router(settings, conn_factory, blobs_root))
    router.include_router(tags_routes.make_router(settings, conn_factory))
    return router
```

- [ ] **Step 5: Run; expect pass**

From `services/flasher/`: `uv run pytest tests/test_tags.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/routes/tags.py services/flasher/app/routes/__init__.py services/flasher/tests/test_tags.py
git commit -m "feat(flasher): tag HTTP routes"
```

---

## Phase 4 — Backups backend

### Task 4.1: `app/backups.py` — row CRUD + dedup + blob I/O

**Files:**
- Create: `services/flasher/app/backups.py`
- Create: `services/flasher/tests/test_backups.py`

- [ ] **Step 1: Write failing tests**

Create `services/flasher/tests/test_backups.py`:
```python
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
            "'{\"vid\":\"2341\",\"pid\":\"0043\",\"serial_number\":\"\",\"product\":\"Arduino Uno\"}', "
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={
            "vid": "2341", "pid": "0043", "serial_number": "", "product": "Arduino Uno",
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
    )
    # Second capture: same sha, different port/client — should reuse.
    second = await capture_or_reuse_backup(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="other", port_name="COM4", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
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
            ctx["conn"], blobs_dir=ctx["blobs_dir"],
            client="khamit", port_name=f"COM{i}", port_snapshot={},
            source_flash_id="flash-1", backup=p,
        )
        payloads.append(p)
    page = await list_backups(ctx["conn"], limit=2)
    assert len(page["items"]) == 2
    assert page["next_before"]


@pytest.mark.asyncio
async def test_update_backup_mutates_labels(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
    )
    row = await update_backup(
        ctx["conn"], backup_id=bid,
        name="known good", description="d", test_command="01", expected_response="aa",
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
    )
    await delete_backup(ctx["conn"], blobs_dir=ctx["blobs_dir"], backup_id=bid)
    assert await get_backup(ctx["conn"], backup_id=bid) is None
    assert not (ctx["blobs_dir"] / f"{bid}.hex").exists()


@pytest.mark.asyncio
async def test_delete_refuses_when_running_flash_references(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup={**_backup_payload(), "sha256": "sha-a"},
    )
    b = await capture_or_reuse_backup(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup={**_backup_payload(), "sha256": "sha-b"},
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
        ctx["conn"], blobs_dir=ctx["blobs_dir"], ids=[a, b, "missing"],
    )
    assert result["deleted"] == 1
    refused = {r["id"]: r["reason"] for r in result["refused"]}
    assert refused[b] == "flash in flight"
    assert refused["missing"] == "unknown backup"


@pytest.mark.asyncio
async def test_download_backup_bytes(ctx) -> None:
    bid = await capture_or_reuse_backup(
        ctx["conn"], blobs_dir=ctx["blobs_dir"],
        client="khamit", port_name="COM3", port_snapshot={},
        source_flash_id="flash-1", backup=_backup_payload(),
    )
    body = await download_backup_bytes(ctx["blobs_dir"], backup_id=bid)
    assert body == ":00000001FF\n"
```

- [ ] **Step 2: Run; expect import failure**

From `services/flasher/`: `uv run pytest tests/test_backups.py -v`
Expected: ImportError for `app.backups`.

- [ ] **Step 3: Implement `app/backups.py`**

Create `services/flasher/app/backups.py`:
```python
from __future__ import annotations

import json
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


async def _row_to_dict(
    conn: aiosqlite.Connection, row: tuple
) -> dict[str, Any]:
    cols = [
        "id", "name", "description", "sha256", "size_bytes", "client",
        "port_name", "vid", "pid", "serial_number", "product",
        "serialhop_saved_path", "test_command", "expected_response",
        "source_flash_id", "captured_at",
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
                backup_id, name, "", sha, int(backup.get("size_bytes") or 0),
                client, port_name,
                (port_snapshot or {}).get("vid"),
                (port_snapshot or {}).get("pid"),
                (port_snapshot or {}).get("serial_number"),
                (port_snapshot or {}).get("product"),
                backup.get("saved_path"),
                None, None,
                source_flash_id, captured_at,
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
        where.append(
            "(captured_at, id) < (SELECT captured_at, id FROM backups WHERE id = ?)"
        )
        params.append(before)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT id FROM backups" + where_sql +
        " ORDER BY captured_at DESC, id DESC LIMIT ?"
    )
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


async def _running_flash_reference_count(
    conn: aiosqlite.Connection, backup_id: str
) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes "
        "WHERE source_kind = 'backup' AND source_id = ? AND status = 'running'",
        (backup_id,),
    )
    return int((await cur.fetchone())[0])


async def delete_backup(
    conn: aiosqlite.Connection, *, blobs_dir: Path, backup_id: str
) -> None:
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


async def count_flashes_referencing(
    conn: aiosqlite.Connection, *, backup_id: str
) -> int:
    cur = await conn.execute(
        "SELECT COUNT(*) FROM flashes WHERE source_kind = 'backup' AND source_id = ?",
        (backup_id,),
    )
    return int((await cur.fetchone())[0])
```

- [ ] **Step 4: Run tests; expect pass**

From `services/flasher/`: `uv run pytest tests/test_backups.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/backups.py services/flasher/tests/test_backups.py
git commit -m "feat(flasher): backup CRUD with sha256 dedup and bulk delete"
```

---

### Task 4.2: Backup HTTP routes (including `promote`)

**Files:**
- Create: `services/flasher/app/routes/backups.py`
- Modify: `services/flasher/app/routes/__init__.py`
- Modify: `services/flasher/tests/test_backups.py`

- [ ] **Step 1: Write failing tests for HTTP routes**

Append to `services/flasher/tests/test_backups.py`:
```python
from fastapi.testclient import TestClient


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    (tmp_path / "clients.json").write_text("{}", encoding="utf-8")
    import importlib, app.main as m
    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c, tmp_path


def _seed_backup(http_app) -> str:
    """Seed a backup row directly in SQLite (no flash flow yet)."""
    client, tmp_path = http_app
    import sqlite3, uuid
    bid = uuid.uuid4().hex
    with sqlite3.connect(tmp_path / "flasher.db") as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('seed-flash', 'done', 'c', 'COM3', '{}', 'firmware', 'fid', 'sha', 'n', 0, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO backups (id, name, sha256, size_bytes, client, port_name, "
            "source_flash_id, captured_at) "
            "VALUES (?, 'b', 'abc', 12, 'c', 'COM3', 'seed-flash', '2026-01-02T00:00:00Z')",
            (bid,),
        )
        conn.commit()
    (tmp_path / "blobs" / "backups" / f"{bid}.hex").write_text(":00000001FF\n")
    return bid


def test_list_backups(http_app) -> None:
    client, _ = http_app
    _seed_backup(http_app)
    r = client.get("/flash/api/backups")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_get_backup(http_app) -> None:
    client, _ = http_app
    bid = _seed_backup(http_app)
    r = client.get(f"/flash/api/backups/{bid}")
    assert r.status_code == 200
    assert r.json()["id"] == bid


def test_patch_backup(http_app) -> None:
    client, _ = http_app
    bid = _seed_backup(http_app)
    r = client.patch(f"/flash/api/backups/{bid}",
                     json={"name": "known good", "test_command": "01"})
    assert r.status_code == 200
    assert r.json()["name"] == "known good"


def test_delete_backup(http_app) -> None:
    client, _ = http_app
    bid = _seed_backup(http_app)
    r = client.delete(f"/flash/api/backups/{bid}")
    assert r.status_code == 200


def test_bulk_delete_backups(http_app) -> None:
    client, _ = http_app
    a = _seed_backup(http_app)
    # Make a second backup with a different sha.
    import sqlite3, uuid
    _, tmp_path = http_app
    b = uuid.uuid4().hex
    with sqlite3.connect(tmp_path / "flasher.db") as conn:
        conn.execute(
            "INSERT INTO backups (id, name, sha256, size_bytes, client, port_name, "
            "source_flash_id, captured_at) "
            "VALUES (?, 'b2', 'def', 12, 'c', 'COM3', 'seed-flash', '2026-01-02T00:00:00Z')",
            (b,),
        )
        conn.commit()
    r = client.post("/flash/api/backups/bulk-delete", json={"ids": [a, b, "missing"]})
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == 2
    assert any(x["id"] == "missing" for x in body["refused"])


def test_download_backup(http_app) -> None:
    client, _ = http_app
    bid = _seed_backup(http_app)
    r = client.get(f"/flash/api/backups/{bid}/download")
    assert r.status_code == 200
    assert r.text == ":00000001FF\n"


def test_promote_backup_creates_firmware(http_app) -> None:
    client, _ = http_app
    bid = _seed_backup(http_app)
    r = client.post(f"/flash/api/backups/{bid}/promote",
                    json={"name": "pump from backup", "copy_test_pair": True})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "pump from backup"
    assert body["source_backup_id"] == bid
    # Firmware blob now has the same bytes as the backup.
    fid = body["id"]
    r = client.get(f"/flash/api/firmware/{fid}/download")
    assert r.text == ":00000001FF\n"
```

- [ ] **Step 2: Run; expect failure**

From `services/flasher/`: `uv run pytest tests/test_backups.py -v -k http_app`
Expected: routes missing.

- [ ] **Step 3: Implement `routes/backups.py`**

Create `services/flasher/app/routes/backups.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from app.backups import (
    BackupInUse,
    BackupNotFound,
    bulk_delete_backups,
    delete_backup,
    download_backup_bytes,
    get_backup,
    list_backups,
    update_backup,
)
from app.config import Settings
from app.firmware import create_firmware
from app.tags import TagNotFound


class _BackupPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    test_command: str | None = None
    expected_response: str | None = None


class _BulkDelete(BaseModel):
    ids: list[str]


class _Promote(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    copy_test_pair: bool = True


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    b_blobs = blobs_root / "backups"
    f_blobs = blobs_root / "firmware"

    @router.get("/api/backups")
    async def list_(
        client: str | None = None,
        q: str | None = None,
        limit: int = 100,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_backups(conn, client=client, q=q, limit=limit, before=before)

    @router.get("/api/backups/{backup_id}")
    async def get_one(backup_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_backup(conn, backup_id=backup_id)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown backup", "detail": backup_id,
            })
        return row

    @router.patch("/api/backups/{backup_id}")
    async def patch(backup_id: str, body: _BackupPatch) -> dict[str, Any]:
        kwargs = body.model_dump(exclude_unset=True)
        async with conn_factory() as conn:
            try:
                return await update_backup(conn, backup_id=backup_id, **kwargs)
            except BackupNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown backup", "detail": backup_id,
                })

    @router.delete("/api/backups/{backup_id}")
    async def delete_one(backup_id: str) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await delete_backup(conn, blobs_dir=b_blobs, backup_id=backup_id)
            except BackupNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown backup", "detail": backup_id,
                })
            except BackupInUse:
                raise HTTPException(status_code=409, detail={
                    "error": "cannot delete: flash in flight", "detail": backup_id,
                })
        return {"status": "deleted"}

    @router.post("/api/backups/bulk-delete")
    async def bulk_delete(body: _BulkDelete) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await bulk_delete_backups(conn, blobs_dir=b_blobs, ids=body.ids)

    @router.get("/api/backups/{backup_id}/download")
    async def download(backup_id: str) -> Response:
        async with conn_factory() as conn:
            row = await get_backup(conn, backup_id=backup_id)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown backup", "detail": backup_id,
            })
        body = await download_backup_bytes(b_blobs, backup_id=backup_id)
        return PlainTextResponse(
            content=body,
            headers={"Content-Disposition": f'attachment; filename="{backup_id}.hex"'},
        )

    @router.post("/api/backups/{backup_id}/promote")
    async def promote(backup_id: str, body: _Promote) -> dict[str, Any]:
        async with conn_factory() as conn:
            backup = await get_backup(conn, backup_id=backup_id)
            if backup is None:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown backup", "detail": backup_id,
                })
            try:
                hex_text = await download_backup_bytes(b_blobs, backup_id=backup_id)
            except BackupNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown backup", "detail": backup_id,
                })
            test_command = backup["test_command"] if body.copy_test_pair else None
            expected_response = backup["expected_response"] if body.copy_test_pair else None
            try:
                return await create_firmware(
                    conn, blobs_dir=f_blobs,
                    name=body.name, description=body.description,
                    firmware=hex_text,
                    test_command=test_command,
                    expected_response=expected_response,
                    tag_ids=body.tags,
                    source_backup_id=backup_id,
                )
            except TagNotFound as exc:
                raise HTTPException(status_code=400, detail={
                    "error": "tag not found", "detail": str(exc),
                })

    return router
```

- [ ] **Step 4: Wire in aggregator and re-mount**

Edit `services/flasher/app/routes/__init__.py` — add import and `include_router`:
```python
from app.routes import backups as backups_routes
# ...
router.include_router(backups_routes.make_router(settings, conn_factory, blobs_root))
```

Add `/api/backups/{id}/flashes` is handled in Phase 5 (it needs the flashes module). For now this task ships the rest of the backup endpoints.

- [ ] **Step 5: Run tests**

From `services/flasher/`: `uv run pytest tests/test_backups.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/routes/backups.py services/flasher/app/routes/__init__.py services/flasher/tests/test_backups.py
git commit -m "feat(flasher): backup HTTP routes (CRUD + bulk + promote)"
```

---

## Phase 5 — Flashes backend

This phase is the heart of the redesign. It replaces the in-memory `JobStore` with SQLite-backed flash records, wires the existing `run_flash_job` into the DB, and adds list/filter/replay/note endpoints.

### Task 5.1: `app/flashes.py` — row CRUD, stats, list with filters

**Files:**
- Create: `services/flasher/app/flashes.py`
- Create: `services/flasher/tests/test_flashes.py`

- [ ] **Step 1: Write failing tests for non-runner module surface**

Create `services/flasher/tests/test_flashes.py`:
```python
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
    await set_terminal_done(db, flash_id=fid,
                            outcome="success", result_json='{"outcome":"success"}',
                            backup_id="b-1", duration_ms=12345)
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
    await set_terminal_error(db, flash_id=fid,
                             error_code="upstream unreachable",
                             error_detail="connection refused",
                             duration_ms=100)
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
    await set_terminal_done(db, flash_id=b, outcome="success", result_json="{}",
                            backup_id=None, duration_ms=1000)
    assert (await get_running_flash(db))["id"] == a


@pytest.mark.asyncio
async def test_list_flashes_with_filters(db) -> None:
    a = await create_running_flash(db, **_running_payload(client="khamit"))
    b = await create_running_flash(db, **_running_payload(client="other"))
    await set_terminal_done(db, flash_id=a, outcome="success", result_json="{}",
                            backup_id=None, duration_ms=1000)
    await set_terminal_done(db, flash_id=b, outcome="failed_backup",
                            result_json="{}", backup_id=None, duration_ms=2000)

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
    await set_terminal_done(db, flash_id=fid, outcome="success", result_json="{}",
                            backup_id=None, duration_ms=1)
    await set_note(db, flash_id=fid, note="hello")
    row = await get_flash(db, flash_id=fid)
    assert row["operator_note"] == "hello"


@pytest.mark.asyncio
async def test_set_note_unknown_raises(db) -> None:
    with pytest.raises(FlashNotFound):
        await set_note(db, flash_id="no", note="x")
```

- [ ] **Step 2: Run; expect import failure**

From `services/flasher/`: `uv run pytest tests/test_flashes.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `app/flashes.py` (module surface)**

Create `services/flasher/app/flashes.py`:
```python
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
        "id", "status", "outcome", "client", "port_name", "port_snapshot_json",
        "source_kind", "source_id", "firmware_sha256", "firmware_name",
        "test_command_used", "expected_response_used", "skip_backup",
        "started_at", "finished_at", "duration_ms",
        "result_json", "error_code", "error_detail", "backup_id", "operator_note",
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
        (flash_id, client, port_name, json.dumps(port_snapshot),
         source_kind, source_id, firmware_sha256, firmware_name,
         test_command_used, expected_response_used,
         1 if skip_backup else 0, _now()),
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
        "ORDER BY started_at DESC, id DESC LIMIT 1"
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


async def set_note(
    conn: aiosqlite.Connection, *, flash_id: str, note: str
) -> None:
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
        "FROM flashes" + where_sql +
        " ORDER BY started_at DESC, id DESC LIMIT ?"
    )
    params.append(limit + 1)
    cur = await conn.execute(sql, params)
    rows = await cur.fetchall()
    next_before = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_before = rows[-1][0]
    cols = [
        "id", "status", "outcome", "client", "port_name", "source_kind", "source_id",
        "firmware_name", "firmware_sha256", "started_at", "duration_ms", "operator_note",
    ]
    items = [dict(zip(cols, r)) for r in rows]
    return {"items": items, "next_before": next_before}
```

- [ ] **Step 4: Run; expect pass**

From `services/flasher/`: `uv run pytest tests/test_flashes.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/flashes.py services/flasher/tests/test_flashes.py
git commit -m "feat(flasher): flashes module (CRUD, stats, list+filters, note)"
```

---

### Task 5.2: Rewrite `app/flash.py`'s `run_flash_job` to write to SQLite + auto-save backups

**Files:**
- Modify: `services/flasher/app/flash.py`
- Modify: `services/flasher/tests/test_flash.py`

The existing `run_flash_job(store: JobStore, ...)` updates an in-memory store. Replace it with `run_flash_job(conn_factory, blobs_dir, flash_id, ...)` that calls into `flashes` + `backups` modules. The `JobStore` class is deleted.

- [ ] **Step 1: Write failing test for the rewritten runner**

Replace the entirety of `services/flasher/tests/test_flash.py` (currently `pytest.skip`-marked) with:
```python
from __future__ import annotations

import json
import time
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
            conn, client="c", port_name="COM3",
            port_snapshot={"vid": "2341", "pid": "0043", "serial_number": "", "product": "u"},
            source_kind="firmware", source_id="fw-1",
            firmware_sha256="abc", firmware_name="x",
            test_command_used=None, expected_response_used=None,
            skip_backup=False,
        )
    response = {
        "outcome": "success",
        "port": "COM3",
        "stages": {"preflight": {"status": "ok"}},
        "backup": {
            "hex": ":00000001FF\n", "sha256": "bbb", "size_bytes": 12,
            "saved_path": "/x", "scope": "flash_only",
        },
    }
    stub = _StubClient(response)
    await run_flash_job(
        conn_factory=ctx["conn_factory"], blobs_root=ctx["blobs_root"],
        flash_id=fid, client=stub, port="COM3", firmware=":00000001FF\n",
        test_command=None, expected_response=None, skip_backup=False,
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
            conn, client="c", port_name="COM3", port_snapshot={},
            source_kind="firmware", source_id="fw-1",
            firmware_sha256="abc", firmware_name="x",
            test_command_used=None, expected_response_used=None, skip_backup=False,
        )
        b = await create_running_flash(
            conn, client="c", port_name="COM3", port_snapshot={},
            source_kind="firmware", source_id="fw-1",
            firmware_sha256="abc", firmware_name="x",
            test_command_used=None, expected_response_used=None, skip_backup=False,
        )
    resp = {
        "outcome": "success",
        "stages": {},
        "backup": {"hex": ":00000001FF\n", "sha256": "same", "size_bytes": 12,
                   "saved_path": "/x", "scope": "flash_only"},
    }
    await run_flash_job(
        conn_factory=ctx["conn_factory"], blobs_root=ctx["blobs_root"],
        flash_id=a, client=_StubClient(resp), port="COM3", firmware="hex",
        test_command=None, expected_response=None, skip_backup=False,
    )
    await run_flash_job(
        conn_factory=ctx["conn_factory"], blobs_root=ctx["blobs_root"],
        flash_id=b, client=_StubClient(resp), port="COM3", firmware="hex",
        test_command=None, expected_response=None, skip_backup=False,
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
            conn, client="c", port_name="COM3", port_snapshot={},
            source_kind="firmware", source_id="fw-1",
            firmware_sha256="abc", firmware_name="x",
            test_command_used=None, expected_response_used=None, skip_backup=False,
        )
    stub = _StubClient(UpstreamUnreachable(detail="connection refused"))
    await run_flash_job(
        conn_factory=ctx["conn_factory"], blobs_root=ctx["blobs_root"],
        flash_id=fid, client=stub, port="COM3", firmware="hex",
        test_command=None, expected_response=None, skip_backup=False,
    )
    async with connect(ctx["db_path"]) as conn:
        row = await get_flash(conn, flash_id=fid)
    assert row["status"] == "error"
    assert row["error_code"] == "upstream unreachable"
```

Remove the `pytestmark = pytest.mark.skip(...)` line from this file.

- [ ] **Step 2: Run; expect failures (old signature)**

From `services/flasher/`: `uv run pytest tests/test_flash.py -v`
Expected: failures — function signature doesn't match yet.

- [ ] **Step 3: Rewrite `app/flash.py`**

Replace `services/flasher/app/flash.py` entirely with:
```python
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from app.backups import capture_or_reuse_backup
from app.flashes import set_terminal_done, set_terminal_error
from app.serialhop import SerialHopError, UpstreamErrorResponse, UpstreamUnreachable


class _SerialHopLike(Protocol):
    async def disconnect_devices(self) -> dict: ...
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
        await client.disconnect_devices()
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
                    "SELECT client, port_name, port_snapshot_json "
                    "FROM flashes WHERE id = ?",
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
                conn, flash_id=flash_id,
                error_code=exc.error_code, error_detail=exc.detail,
                duration_ms=duration_ms,
            )
    except UpstreamUnreachable as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn, flash_id=flash_id,
                error_code="upstream unreachable", error_detail=exc.detail,
                duration_ms=duration_ms,
            )
    except SerialHopError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn, flash_id=flash_id,
                error_code="upstream error", error_detail=str(exc),
                duration_ms=duration_ms,
            )
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        async with conn_factory() as conn:
            await set_terminal_error(
                conn, flash_id=flash_id,
                error_code="internal error",
                error_detail=str(exc) or type(exc).__name__,
                duration_ms=duration_ms,
            )
```

- [ ] **Step 4: Run tests**

From `services/flasher/`: `uv run pytest tests/test_flash.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/app/flash.py services/flasher/tests/test_flash.py
git commit -m "feat(flasher): flash runner persists to DB; auto-saves dedup'd backups"
```

---

### Task 5.3: Flash HTTP routes — `POST /api/flash`, polling, list, note, replay

**Files:**
- Create: `services/flasher/app/routes/flashes.py`
- Modify: `services/flasher/app/routes/__init__.py`
- Append tests to: `services/flasher/tests/test_flashes.py`

- [ ] **Step 1: Write failing HTTP tests**

Append to `services/flasher/tests/test_flashes.py`:
```python
from fastapi.testclient import TestClient
import respx
import httpx
import sqlite3


@pytest.fixture
def http_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    # one online client wired into roster
    (tmp_path / "clients.json").write_text(
        '{"khamit": {"port": 9000, "password_sha256": ""}}', encoding="utf-8"
    )
    import importlib, app.main as m
    importlib.reload(m)
    with TestClient(m.app) as c:
        yield c, tmp_path


def _seed_firmware(http_app) -> str:
    client, _ = http_app
    return client.post("/flash/api/firmware",
                       json={"name": "fw", "firmware": ":00000001FF\n"}).json()["id"]


def _stub_serialhop(respx_mock) -> None:
    """Match all SerialHop calls in tests; return a happy success."""
    respx_mock.post(host="chisel", port=9000, path="/devices/disconnect").mock(
        return_value=httpx.Response(200, json={"released": 0})
    )
    respx_mock.post(host="chisel", port=9000, path__regex=r"/flash/.*").mock(
        return_value=httpx.Response(200, json={
            "outcome": "success",
            "port": "COM3",
            "stages": {"preflight": {"status": "ok"}},
        })
    )


def test_post_flash_inserts_running_row(http_app) -> None:
    client, tmp_path = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post("/flash/api/flash", json={
            "client": "khamit", "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        })
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    with sqlite3.connect(tmp_path / "flasher.db") as conn:
        row = conn.execute("SELECT status, source_id, firmware_name FROM flashes WHERE id = ?",
                           (job_id,)).fetchone()
    assert row[1] == fid


def test_post_flash_with_test_override_saves_back_when_flag_set(http_app) -> None:
    client, tmp_path = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post("/flash/api/flash", json={
            "client": "khamit", "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
            "test_override": {"command": "01", "expected_response": "aa"},
            "save_test_to_record": True,
        })
    assert r.status_code == 200
    # The firmware record now carries the saved test pair.
    r = client.get(f"/flash/api/firmware/{fid}")
    body = r.json()
    assert body["test_command"] == "01"
    assert body["expected_response"] == "aa"


def test_post_flash_unknown_source(http_app) -> None:
    client, _ = http_app
    r = client.post("/flash/api/flash", json={
        "client": "khamit", "port": "COM3",
        "source": {"kind": "firmware", "id": "no-such"},
    })
    assert r.status_code == 404
    assert r.json()["error"] == "unknown source"


def test_get_flash_current_and_by_id(http_app) -> None:
    client, _ = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        r = client.post("/flash/api/flash", json={
            "client": "khamit", "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        })
    job_id = r.json()["job_id"]
    # Poll until terminal.
    for _ in range(20):
        body = client.get(f"/flash/api/flash/{job_id}").json()
        if body.get("status") in {"done", "error"}:
            break
        time.sleep(0.05)
    assert body["status"] in {"done", "error"}


def test_list_flashes_with_filters(http_app) -> None:
    client, _ = http_app
    fid = _seed_firmware(http_app)
    with respx.mock(assert_all_called=False) as respx_mock:
        _stub_serialhop(respx_mock)
        for _ in range(2):
            client.post("/flash/api/flash", json={
                "client": "khamit", "port": "COM3",
                "source": {"kind": "firmware", "id": fid},
            })
    for _ in range(20):
        body = client.get("/flash/api/flashes").json()
        if all(x["status"] in {"done", "error"} for x in body["items"]):
            break
        time.sleep(0.05)
    r = client.get("/flash/api/flashes?client=khamit")
    assert len(r.json()["items"]) == 2


def test_patch_note_rejected_while_running(http_app, tmp_path) -> None:
    client, _ = http_app
    # Hand-seed a running flash row.
    import sqlite3
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, started_at) "
            "VALUES ('jx', 'running', 'c', 'COM3', '{}', 'firmware', 'fid', 'sha', 'n', 0, '2026-01-01T00:00:00Z')"
        )
        conn.commit()
    r = client.patch("/flash/api/flashes/jx/note", json={"note": "x"})
    assert r.status_code == 400


def test_patch_note_after_terminal(http_app, tmp_path) -> None:
    client, _ = http_app
    import sqlite3
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, outcome, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, skip_backup, "
            "started_at, finished_at) "
            "VALUES ('jx', 'done', 'success', 'c', 'COM3', '{}', 'firmware', "
            "'fid', 'sha', 'n', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:05Z')"
        )
        conn.commit()
    r = client.patch("/flash/api/flashes/jx/note", json={"note": "hello"})
    assert r.status_code == 200
    r = client.get("/flash/api/flash/jx")
    assert r.json()["operator_note"] == "hello"


def test_replay_410_when_source_deleted(http_app, tmp_path) -> None:
    client, _ = http_app
    import sqlite3
    db = tmp_path / "flasher.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO flashes (id, status, outcome, client, port_name, port_snapshot_json, "
            "source_kind, source_id, firmware_sha256, firmware_name, "
            "test_command_used, expected_response_used, skip_backup, started_at, finished_at) "
            "VALUES ('jx', 'done', 'success', 'khamit', 'COM3', '{}', 'firmware', "
            "'gone-fid', 'sha', 'fw', NULL, NULL, 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:05Z')"
        )
        conn.commit()
    r = client.post("/flash/api/flashes/jx/replay", json={})
    assert r.status_code == 410
    assert r.json()["error"] == "source deleted"
```

Add `respx>=0.21,<0.22` to the dev deps in `services/flasher/pyproject.toml`:
```toml
dev = [
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<0.25",
    "ruff>=0.6,<0.13",
    "respx>=0.21,<0.22",
]
```
Then run `uv lock` from `services/flasher/`.

- [ ] **Step 2: Run; expect failures**

From `services/flasher/`: `uv run pytest tests/test_flashes.py -v -k http_app`
Expected: route module does not exist.

- [ ] **Step 3: Implement `routes/flashes.py`**

Create `services/flasher/app/routes/flashes.py`:
```python
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.backups import get_backup, download_backup_bytes
from app.clients import load_roster
from app.config import Settings
from app.firmware import (
    FirmwareNotFound,
    download_firmware_bytes,
    get_firmware,
    update_firmware,
)
from app.flash import run_flash_job
from app.flashes import (
    FlashNotFound,
    FlashStillRunning,
    create_running_flash,
    get_flash,
    get_running_flash,
    list_flashes,
    set_note,
)
from app.serialhop import SerialHopClient


_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_background_tasks: set[asyncio.Task[None]] = set()


class _Source(BaseModel):
    kind: str
    id: str


class _TestOverride(BaseModel):
    command: str
    expected_response: str


class _FlashPost(BaseModel):
    client: str = Field(min_length=1, max_length=128)
    port: str = Field(min_length=1, max_length=128)
    source: _Source
    test_override: _TestOverride | None = None
    save_test_to_record: bool = False
    skip_backup: bool = False


class _NotePatch(BaseModel):
    note: str


class _ReplayPost(BaseModel):
    client: str | None = None
    port: str | None = None


def _validate_hex(value: str) -> None:
    if not value or len(value) % 2 != 0 or not _HEX_RE.match(value):
        raise HTTPException(status_code=400, detail={
            "error": "invalid request", "detail": f"not a valid hex string: {value!r}",
        })


def make_router(settings: Settings, conn_factory, blobs_root: Path) -> APIRouter:
    router = APIRouter()
    f_blobs = blobs_root / "firmware"
    b_blobs = blobs_root / "backups"

    async def _resolve_source(conn, source: _Source) -> tuple[str, str, str | None, str | None, str]:
        """Returns (firmware_name, firmware_sha256, test_command, expected_response, hex_text)."""
        if source.kind == "firmware":
            row = await get_firmware(conn, firmware_id=source.id)
            if row is None:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown source", "detail": source.id,
                })
            hex_text = await download_firmware_bytes(f_blobs, firmware_id=source.id)
            return (row["name"], row["sha256"], row["test_command"],
                    row["expected_response"], hex_text)
        if source.kind == "backup":
            row = await get_backup(conn, backup_id=source.id)
            if row is None:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown source", "detail": source.id,
                })
            hex_text = await download_backup_bytes(b_blobs, backup_id=source.id)
            return (row["name"], row["sha256"], row["test_command"],
                    row["expected_response"], hex_text)
        raise HTTPException(status_code=400, detail={
            "error": "invalid request", "detail": f"unknown source.kind: {source.kind!r}",
        })

    @router.post("/api/flash")
    async def post_flash(body: _FlashPost) -> dict[str, str]:
        if body.test_override is not None:
            _validate_hex(body.test_override.command)
            _validate_hex(body.test_override.expected_response)

        # Look up the lab machine roster entry.
        roster = load_roster(settings.clients_file)
        entry = roster.get(body.client)
        if entry is None:
            raise HTTPException(status_code=400, detail={
                "error": "unknown client", "detail": body.client,
            })

        # Pull port snapshot from a fresh SerialHop call.
        sh = SerialHopClient(host=settings.chisel_host, port=entry["port"])
        try:
            ports_body = await sh.get_ports_detailed()
        except Exception:  # validation continues — port_snapshot may be empty
            ports_body = {"ports": []}
        snap = next(
            (p for p in ports_body.get("ports", []) if p.get("name") == body.port),
            None,
        )
        port_snapshot = {
            "vid": (snap or {}).get("vid", ""),
            "pid": (snap or {}).get("pid", ""),
            "serial_number": (snap or {}).get("serial_number", ""),
            "product": (snap or {}).get("product", ""),
        }

        async with conn_factory() as conn:
            (fw_name, fw_sha, src_tcmd, src_eresp, hex_text) = await _resolve_source(
                conn, body.source
            )

            if body.test_override is not None:
                tcmd = body.test_override.command.lower()
                eresp = body.test_override.expected_response.lower()
                if body.save_test_to_record and body.source.kind == "firmware":
                    try:
                        await update_firmware(
                            conn, firmware_id=body.source.id,
                            test_command=tcmd, expected_response=eresp,
                        )
                    except FirmwareNotFound:
                        # already handled by _resolve_source above, defensive
                        raise HTTPException(status_code=404, detail={
                            "error": "unknown source", "detail": body.source.id,
                        })
                # NOTE: save-back for backup source is intentionally not supported here —
                # the spec wires the explicit save toggle on firmware records only.
            else:
                tcmd = src_tcmd
                eresp = src_eresp

            flash_id = await create_running_flash(
                conn, client=body.client, port_name=body.port,
                port_snapshot=port_snapshot,
                source_kind=body.source.kind, source_id=body.source.id,
                firmware_sha256=fw_sha, firmware_name=fw_name,
                test_command_used=tcmd, expected_response_used=eresp,
                skip_backup=body.skip_backup,
            )

        task = asyncio.create_task(
            run_flash_job(
                conn_factory=conn_factory, blobs_root=blobs_root,
                flash_id=flash_id, client=sh, port=body.port,
                firmware=hex_text, test_command=tcmd, expected_response=eresp,
                skip_backup=body.skip_backup,
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return {"job_id": flash_id}

    @router.get("/api/flash/current")
    async def current() -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_running_flash(conn)
        return row or {}

    @router.get("/api/flash/{flash_id}")
    async def get_one(flash_id: str) -> dict[str, Any]:
        async with conn_factory() as conn:
            row = await get_flash(conn, flash_id=flash_id)
        if row is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown flash", "detail": flash_id,
            })
        return row

    @router.get("/api/flashes")
    async def list_(
        client: list[str] = Query(default_factory=list),
        outcome: list[str] = Query(default_factory=list),
        source_kind: str | None = None,
        source_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        before: str | None = None,
    ) -> dict[str, Any]:
        async with conn_factory() as conn:
            return await list_flashes(
                conn, client=client or None, outcome=outcome or None,
                source_kind=source_kind, source_id=source_id,
                since=since, until=until, limit=limit, before=before,
            )

    @router.patch("/api/flashes/{flash_id}/note")
    async def patch_note(flash_id: str, body: _NotePatch) -> dict[str, str]:
        async with conn_factory() as conn:
            try:
                await set_note(conn, flash_id=flash_id, note=body.note)
            except FlashNotFound:
                raise HTTPException(status_code=404, detail={
                    "error": "unknown flash", "detail": flash_id,
                })
            except FlashStillRunning:
                raise HTTPException(status_code=400, detail={
                    "error": "invalid request",
                    "detail": "cannot annotate while flash is running",
                })
        return {"note": body.note}

    @router.post("/api/flashes/{flash_id}/replay")
    async def replay(flash_id: str, body: _ReplayPost) -> dict[str, str]:
        async with conn_factory() as conn:
            original = await get_flash(conn, flash_id=flash_id)
        if original is None:
            raise HTTPException(status_code=404, detail={
                "error": "unknown flash", "detail": flash_id,
            })
        # Verify source still exists.
        async with conn_factory() as conn:
            if original["source_kind"] == "firmware":
                src = await get_firmware(conn, firmware_id=original["source_id"])
            elif original["source_kind"] == "backup":
                src = await get_backup(conn, backup_id=original["source_id"])
            else:
                src = None
        if src is None:
            raise HTTPException(status_code=410, detail={
                "error": "source deleted",
                "detail": f"{original['source_kind']} {original['source_id']} no longer exists",
            })
        # Reconstruct a POST body and call it.
        return await post_flash(_FlashPost(
            client=body.client or original["client"],
            port=body.port or original["port_name"],
            source=_Source(kind=original["source_kind"], id=original["source_id"]),
            test_override=(
                _TestOverride(command=original["test_command_used"],
                              expected_response=original["expected_response_used"])
                if original["test_command_used"] else None
            ),
            save_test_to_record=False,
            skip_backup=bool(original["skip_backup"]),
        ))

    return router
```

Also add the `/api/firmware/{id}/flashes` and `/api/backups/{id}/flashes` endpoints to the existing route modules — straightforward wrappers around `list_flashes`. Add to `services/flasher/app/routes/firmware.py` inside `make_router`:
```python
    @router.get("/api/firmware/{firmware_id}/flashes")
    async def operator_flashes(
        firmware_id: str, limit: int = 50, before: str | None = None
    ) -> dict[str, Any]:
        from app.flashes import list_flashes
        async with conn_factory() as conn:
            return await list_flashes(
                conn, source_kind="firmware", source_id=firmware_id,
                limit=limit, before=before,
            )
```

And the matching block in `services/flasher/app/routes/backups.py`:
```python
    @router.get("/api/backups/{backup_id}/flashes")
    async def backup_flashes(
        backup_id: str, limit: int = 50, before: str | None = None
    ) -> dict[str, Any]:
        from app.flashes import list_flashes
        async with conn_factory() as conn:
            return await list_flashes(
                conn, source_kind="backup", source_id=backup_id,
                limit=limit, before=before,
            )
```

- [ ] **Step 4: Wire flash routes into the aggregator**

Edit `services/flasher/app/routes/__init__.py` to include the new module:
```python
from app.routes import flashes as flashes_routes
# ...
router.include_router(flashes_routes.make_router(settings, conn_factory, blobs_root))
```

- [ ] **Step 5: Run tests; expect pass**

From `services/flasher/`: `uv run pytest tests/test_flashes.py -v`
Expected: all flash tests pass (module + HTTP).

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/routes/flashes.py services/flasher/app/routes/firmware.py services/flasher/app/routes/backups.py services/flasher/app/routes/__init__.py services/flasher/pyproject.toml services/flasher/uv.lock services/flasher/tests/test_flashes.py
git commit -m "feat(flasher): flash HTTP routes (start/poll/list/note/replay)"
```

---

## Phase 6 — Clients endpoint update and final route cleanup

### Task 6.1: Clients endpoint returns full roster with `online: bool`

**Files:**
- Create: `services/flasher/app/routes/clients.py`
- Modify: `services/flasher/app/routes/__init__.py`
- Modify: `services/flasher/tests/test_clients.py`

- [ ] **Step 1: Rewrite `test_clients.py` for the new shape**

Replace `services/flasher/tests/test_clients.py` with:
```python
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_clients_all_with_online_flags(monkeypatch, tmp_path: Path) -> None:
    roster = {"a": {"port": 9100, "password_sha256": ""},
              "b": {"port": 9101, "password_sha256": ""}}
    (tmp_path / "clients.json").write_text(json.dumps(roster), encoding="utf-8")
    monkeypatch.setenv("FLASHER_CLIENTS_FILE", str(tmp_path / "clients.json"))
    monkeypatch.setenv("FLASHER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FLASHER_UPLOAD_TOKEN", "test-token")
    # Force every TCP probe to "offline" by pointing chisel host at a black hole.
    monkeypatch.setenv("FLASHER_CHISEL_HOST", "127.0.0.1")
    import importlib, app.main as m
    importlib.reload(m)
    with TestClient(m.app) as c:
        body = c.get("/flash/api/clients").json()
    assert {x["name"] for x in body["clients"]} == {"a", "b"}
    assert all(x["online"] is False for x in body["clients"])
    assert all("port" in x for x in body["clients"])
```

- [ ] **Step 2: Run; expect failure (no `/api/clients` route mounted yet)**

From `services/flasher/`: `uv run pytest tests/test_clients.py -v`
Expected: 404 or schema mismatch.

- [ ] **Step 3: Implement `routes/clients.py`**

Create `services/flasher/app/routes/clients.py`:
```python
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam

from app.clients import load_roster, probe_tcp
from app.config import Settings
from app.serialhop import (
    SerialHopClient,
    UpstreamErrorResponse,
    UpstreamUnreachable,
)


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/clients")
    async def get_clients() -> dict[str, Any]:
        roster = load_roster(settings.clients_file)
        items = sorted(roster.items())
        # Concurrent TCP probes — slow/offline clients shouldn't stall the rest.
        results = await asyncio.gather(
            *(asyncio.to_thread(probe_tcp, settings.chisel_host, e["port"]) for _, e in items)
        )
        return {
            "clients": [
                {"name": name, "port": entry["port"], "online": bool(online)}
                for (name, entry), online in zip(items, results, strict=True)
            ]
        }

    @router.get("/api/clients/{name}/ports")
    async def get_ports(
        name: str = PathParam(..., min_length=1, max_length=128),
    ) -> dict[str, Any]:
        roster = load_roster(settings.clients_file)
        entry = roster.get(name)
        if entry is None:
            raise HTTPException(status_code=404, detail="unknown client")
        client = SerialHopClient(host=settings.chisel_host, port=entry["port"])
        try:
            return await client.get_ports_detailed()
        except UpstreamErrorResponse as exc:
            raise HTTPException(status_code=502, detail={
                "error": exc.error_code, "detail": exc.detail,
            })
        except UpstreamUnreachable as exc:
            raise HTTPException(status_code=502, detail={
                "error": "upstream unreachable", "detail": exc.detail,
            })

    return router
```

- [ ] **Step 4: Wire into aggregator**

Edit `services/flasher/app/routes/__init__.py`:
```python
from app.routes import clients as clients_routes
# ...
router.include_router(clients_routes.make_router(settings))
```

- [ ] **Step 5: Run tests**

From `services/flasher/`: `uv run pytest tests/test_clients.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add services/flasher/app/routes/clients.py services/flasher/app/routes/__init__.py services/flasher/tests/test_clients.py
git commit -m "feat(flasher): /api/clients returns full roster with online flag"
```

---

### Task 6.2: Delete the legacy `services/flasher/app/routes.py` and `test_routes.py`

**Files:**
- Delete: `services/flasher/app/routes.py`
- Delete: `services/flasher/tests/test_routes.py`

The old `routes.py` is now superseded by the `routes/` package. The old `test_routes.py` was skip-marked in Task 1.6; its coverage is replicated by the per-module HTTP tests added in Phases 3-6.

- [ ] **Step 1: Delete the files**

```bash
git rm services/flasher/app/routes.py services/flasher/tests/test_routes.py
```

- [ ] **Step 2: Run the full unit suite to verify nothing imports the deleted files**

From `services/flasher/`: `uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(flasher): drop legacy routes.py (split into routes/ package)"
```

---

## Phase 7 — Frontend foundation

This phase replaces the v1 single-page wizard with a tabbed shell. It introduces:

- Top-level state in `App.tsx` for the running flash id (lifted out of `FlashTab` so polling continues across tab switches).
- A `TabBar` and four empty tab placeholders.
- A unified `api.ts` covering every new endpoint plus the existing flash/ports/clients endpoints.
- New shared types in `types.ts`.

UI test discipline: per the spec, frontend unit tests are deferred. The e2e tests in Phase 10 cover the full flow end-to-end through a real container.

### Task 7.1: Replace `web/src/types.ts`

**Files:**
- Modify: `services/flasher/web/src/types.ts`

- [ ] **Step 1: Replace types**

Replace `services/flasher/web/src/types.ts` with:
```typescript
export interface ClientEntry {
  name: string;
  port: number;
  online: boolean;
}

export interface PortRow {
  name: string;
  is_usb: boolean;
  vid: string;
  pid: string;
  serial_number: string;
  product: string;
  discovered: boolean;
  device_id: string;
}

export interface Tag { id: string; name: string; created_at: string; firmware_count?: number; }

export interface FlashStats {
  total: number;
  successes: number;
  rollbacks: number;
  failures: number;
  last_flashed_at: string | null;
  last_flashed_client: string | null;
  last_flashed_port: string | null;
}

export interface FirmwareRecord {
  id: string;
  name: string;
  description: string;
  sha256: string;
  size_bytes: number;
  original_filename: string | null;
  test_command: string | null;
  expected_response: string | null;
  source_backup_id: string | null;
  created_at: string;
  tags: Tag[];
  stats: FlashStats;
}

export interface BackupRecord {
  id: string;
  name: string;
  description: string;
  sha256: string;
  size_bytes: number;
  client: string;
  port_name: string;
  vid: string | null;
  pid: string | null;
  serial_number: string | null;
  product: string | null;
  serialhop_saved_path: string | null;
  test_command: string | null;
  expected_response: string | null;
  source_flash_id: string;
  captured_at: string;
  stats: FlashStats;
}

export type FlashStatus = "running" | "done" | "error" | "interrupted";

export interface FlashRowSummary {
  id: string;
  status: FlashStatus;
  outcome: string | null;
  client: string;
  port_name: string;
  source_kind: "firmware" | "backup";
  source_id: string;
  firmware_name: string;
  firmware_sha256: string;
  started_at: string;
  duration_ms: number | null;
  operator_note: string;
}

export interface FlashRowDetail extends FlashRowSummary {
  port_snapshot: Record<string, string>;
  test_command_used: string | null;
  expected_response_used: string | null;
  skip_backup: boolean;
  finished_at: string | null;
  result: any | null;
  error_code: string | null;
  error_detail: string | null;
  backup_id: string | null;
}

export interface FlashFilters {
  client?: string[];
  outcome?: string[];
  source_kind?: "firmware" | "backup";
  source_id?: string;
  since?: string;
  until?: string;
}

export type TabId = "flash" | "firmware" | "backups" | "logs";
```

- [ ] **Step 2: Commit**

```bash
git add services/flasher/web/src/types.ts
git commit -m "feat(flasher/web): typed shapes for library + history"
```

---

### Task 7.2: Replace `web/src/api.ts` with the full surface

**Files:**
- Modify: `services/flasher/web/src/api.ts`

- [ ] **Step 1: Replace api.ts**

Replace `services/flasher/web/src/api.ts` with:
```typescript
import {
  BackupRecord,
  ClientEntry,
  FirmwareRecord,
  FlashFilters,
  FlashRowDetail,
  FlashRowSummary,
  PortRow,
  Tag,
} from "./types";

const BASE = "/flash/api";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw Object.assign(new Error(body.error ?? `HTTP ${r.status}`), { status: r.status, body });
  }
  return r.json() as Promise<T>;
}

// Clients
export const listClients = () => http<{ clients: ClientEntry[] }>("/clients");
export const listPorts = (name: string) => http<{ ports: PortRow[] }>(`/clients/${encodeURIComponent(name)}/ports`);

// Firmware
export const listFirmware = (params: { tag?: string[]; q?: string; limit?: number; before?: string } = {}) => {
  const qs = new URLSearchParams();
  (params.tag ?? []).forEach(t => qs.append("tag", t));
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.before) qs.set("before", params.before);
  const s = qs.toString();
  return http<{ items: FirmwareRecord[]; next_before: string | null }>("/firmware" + (s ? `?${s}` : ""));
};
export const getFirmware = (id: string) => http<FirmwareRecord>(`/firmware/${id}`);
export const createFirmware = (body: any) => http<FirmwareRecord>("/firmware", { method: "POST", body: JSON.stringify(body) });
export const patchFirmware = (id: string, body: any) => http<FirmwareRecord>(`/firmware/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteFirmware = (id: string) => http<{ status: string }>(`/firmware/${id}`, { method: "DELETE" });
export const downloadFirmwareUrl = (id: string) => `${BASE}/firmware/${id}/download`;
export const listFirmwareFlashes = (id: string, limit = 50, before?: string) => {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/firmware/${id}/flashes?${qs}`);
};

// Backups
export const listBackups = (params: { client?: string; q?: string; limit?: number; before?: string } = {}) => {
  const qs = new URLSearchParams();
  if (params.client) qs.set("client", params.client);
  if (params.q) qs.set("q", params.q);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.before) qs.set("before", params.before);
  const s = qs.toString();
  return http<{ items: BackupRecord[]; next_before: string | null }>("/backups" + (s ? `?${s}` : ""));
};
export const getBackup = (id: string) => http<BackupRecord>(`/backups/${id}`);
export const patchBackup = (id: string, body: any) => http<BackupRecord>(`/backups/${id}`, { method: "PATCH", body: JSON.stringify(body) });
export const deleteBackup = (id: string) => http<{ status: string }>(`/backups/${id}`, { method: "DELETE" });
export const bulkDeleteBackups = (ids: string[]) => http<{ deleted: number; refused: { id: string; reason: string }[] }>("/backups/bulk-delete", { method: "POST", body: JSON.stringify({ ids }) });
export const promoteBackup = (id: string, body: any) => http<FirmwareRecord>(`/backups/${id}/promote`, { method: "POST", body: JSON.stringify(body) });
export const downloadBackupUrl = (id: string) => `${BASE}/backups/${id}/download`;
export const listBackupFlashes = (id: string, limit = 50, before?: string) => {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/backups/${id}/flashes?${qs}`);
};

// Tags
export const listTags = () => http<{ items: Tag[] }>("/tags");
export const createTag = (name: string) => http<Tag>("/tags", { method: "POST", body: JSON.stringify({ name }) });
export const renameTag = (id: string, name: string) => http<Tag>(`/tags/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
export const deleteTag = (id: string) => http<{ status: string }>(`/tags/${id}`, { method: "DELETE" });

// Flashes
export const postFlash = (body: any) => http<{ job_id: string }>("/flash", { method: "POST", body: JSON.stringify(body) });
export const getFlash = (id: string) => http<FlashRowDetail>(`/flash/${id}`);
export const getCurrentFlash = () => http<FlashRowDetail | {}>("/flash/current");
export const listFlashes = (filters: FlashFilters = {}, limit = 50, before?: string) => {
  const qs = new URLSearchParams();
  (filters.client ?? []).forEach(c => qs.append("client", c));
  (filters.outcome ?? []).forEach(o => qs.append("outcome", o));
  if (filters.source_kind) qs.set("source_kind", filters.source_kind);
  if (filters.source_id) qs.set("source_id", filters.source_id);
  if (filters.since) qs.set("since", filters.since);
  if (filters.until) qs.set("until", filters.until);
  qs.set("limit", String(limit));
  if (before) qs.set("before", before);
  return http<{ items: FlashRowSummary[]; next_before: string | null }>(`/flashes?${qs}`);
};
export const patchFlashNote = (id: string, note: string) => http<{ note: string }>(`/flashes/${id}/note`, { method: "PATCH", body: JSON.stringify({ note }) });
export const replayFlash = (id: string, body: { client?: string; port?: string } = {}) => http<{ job_id: string }>(`/flashes/${id}/replay`, { method: "POST", body: JSON.stringify(body) });
```

- [ ] **Step 2: Commit**

```bash
git add services/flasher/web/src/api.ts
git commit -m "feat(flasher/web): full API client surface"
```

---

### Task 7.3: `TabBar` component

**Files:**
- Create: `services/flasher/web/src/components/TabBar.tsx`

- [ ] **Step 1: Create the component**

Create `services/flasher/web/src/components/TabBar.tsx`:
```typescript
import { TabId } from "../types";

interface TabBarProps {
  active: TabId;
  onChange: (next: TabId) => void;
}

const TABS: { id: TabId; label: string }[] = [
  { id: "flash", label: "Flash" },
  { id: "firmware", label: "Firmware" },
  { id: "backups", label: "Backups" },
  { id: "logs", label: "Logs" },
];

export function TabBar({ active, onChange }: TabBarProps) {
  return (
    <nav className="tab-bar" role="tablist">
      {TABS.map(t => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`tab-bar-button ${active === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add services/flasher/web/src/components/TabBar.tsx
git commit -m "feat(flasher/web): TabBar component"
```

---

### Task 7.4: Refactor `App.tsx` to host four tabs with lifted polling

**Files:**
- Modify: `services/flasher/web/src/App.tsx`
- Create: `services/flasher/web/src/tabs/FlashTab.tsx` (stub; Phase 9 fills in)
- Create: `services/flasher/web/src/tabs/FirmwareTab.tsx` (stub; Phase 8 fills in)
- Create: `services/flasher/web/src/tabs/BackupsTab.tsx` (stub)
- Create: `services/flasher/web/src/tabs/LogsTab.tsx` (stub)

- [ ] **Step 1: Create empty tab stubs**

Create `services/flasher/web/src/tabs/FirmwareTab.tsx`:
```typescript
export function FirmwareTab() {
  return <div className="tab-pane"><h2>Firmware</h2><p>(coming in Phase 8)</p></div>;
}
```

Create `services/flasher/web/src/tabs/BackupsTab.tsx`:
```typescript
export function BackupsTab() {
  return <div className="tab-pane"><h2>Backups</h2><p>(coming in Phase 8)</p></div>;
}
```

Create `services/flasher/web/src/tabs/LogsTab.tsx`:
```typescript
export function LogsTab() {
  return <div className="tab-pane"><h2>Logs</h2><p>(coming in Phase 8)</p></div>;
}
```

For Phase 7, the FlashTab keeps the current v1 wizard mostly intact; we'll fully rewrite it in Phase 9. Create `services/flasher/web/src/tabs/FlashTab.tsx` as a thin wrapper around what's in `App.tsx` today — for now, just re-export the existing `App` body content:
```typescript
// Phase 7 stub — Phase 9 rewrites this to consume the new picker and
// render running/result views always-below-the-form.
import { useEffect, useState } from "react";
import { getCurrentFlash } from "../api";
import { FlashRowDetail } from "../types";

interface FlashTabProps {
  runningFlashId: string | null;
  setRunningFlashId: (id: string | null) => void;
}

export function FlashTab({ runningFlashId, setRunningFlashId }: FlashTabProps) {
  return (
    <div className="tab-pane">
      <h2>Flash</h2>
      <p>Form goes here (Phase 9). Running flash id: {runningFlashId ?? "none"}.</p>
    </div>
  );
}
```

- [ ] **Step 2: Rewrite `App.tsx`**

Replace `services/flasher/web/src/App.tsx` with:
```typescript
import { useEffect, useState } from "react";
import { TabBar } from "./components/TabBar";
import { FlashTab } from "./tabs/FlashTab";
import { FirmwareTab } from "./tabs/FirmwareTab";
import { BackupsTab } from "./tabs/BackupsTab";
import { LogsTab } from "./tabs/LogsTab";
import { getCurrentFlash, getFlash } from "./api";
import { FlashRowDetail, TabId } from "./types";

export default function App() {
  const [tab, setTab] = useState<TabId>("flash");
  const [runningFlashId, setRunningFlashId] = useState<string | null>(null);
  const [, setBeat] = useState(0);

  // On mount, see if there's already a running flash.
  useEffect(() => {
    (async () => {
      const body = await getCurrentFlash().catch(() => ({} as any));
      if ((body as FlashRowDetail).id && (body as FlashRowDetail).status === "running") {
        setRunningFlashId((body as FlashRowDetail).id);
      }
    })();
  }, []);

  // Polling: any time a running id is set, poll until terminal.
  useEffect(() => {
    if (!runningFlashId) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const row = await getFlash(runningFlashId);
        if (cancelled) return;
        setBeat(b => b + 1);
        if (row.status !== "running") {
          setRunningFlashId(null);
        }
      } catch {
        // Network blips — keep polling. A 404 (e.g. the row was deleted) would
        // throw; recover by clearing the running id.
        setRunningFlashId(null);
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runningFlashId]);

  return (
    <div className="app">
      <TabBar active={tab} onChange={setTab} />
      <main>
        {tab === "flash" && (
          <FlashTab runningFlashId={runningFlashId} setRunningFlashId={setRunningFlashId} />
        )}
        {tab === "firmware" && <FirmwareTab />}
        {tab === "backups" && <BackupsTab />}
        {tab === "logs" && <LogsTab />}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: Add tab styles**

Append to `services/flasher/web/src/components/styles.css`:
```css
.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  border-bottom: 1px solid #d0d0d0;
  background: #fafafa;
}
.tab-bar-button {
  padding: 8px 16px;
  border: 1px solid transparent;
  background: none;
  cursor: pointer;
  font-weight: 500;
}
.tab-bar-button.active {
  background: #fff;
  border: 1px solid #d0d0d0;
  border-bottom-color: #fff;
  margin-bottom: -1px;
}
.tab-pane {
  padding: 16px;
}
```

- [ ] **Step 4: Build the frontend**

From `services/flasher/web/`: `npm install && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/web/src/App.tsx services/flasher/web/src/tabs/ services/flasher/web/src/components/styles.css
git commit -m "feat(flasher/web): tabbed shell with lifted running-flash polling"
```

---

## Phase 8 — Firmware, Backups, and Logs tabs

Each tab is one task. Frontend coverage relies on the Phase 10 e2e suite running the SPA against a real container. The components below are sized to one focused responsibility each per the design principles in `docs/superpowers/specs/2026-05-16-flasher-library-design.md`.

### Task 8.1: Shared components — `StatsCard`, `TagChip`, `TagManager`

**Files:**
- Create: `services/flasher/web/src/components/StatsCard.tsx`
- Create: `services/flasher/web/src/components/TagChip.tsx`
- Create: `services/flasher/web/src/components/TagManager.tsx`

- [ ] **Step 1: `StatsCard.tsx`**

Create `services/flasher/web/src/components/StatsCard.tsx`:
```typescript
import { FlashStats } from "../types";

export function StatsCard({ stats }: { stats: FlashStats }) {
  const denom = stats.total || 0;
  const pct = denom > 0 ? Math.round((stats.successes / denom) * 100) : null;
  return (
    <div className="stats-card">
      <dl>
        <dt>Total flashes</dt><dd>{stats.total}</dd>
        <dt>Successes</dt><dd>{stats.successes}</dd>
        <dt>Rolled back</dt><dd>{stats.rollbacks}</dd>
        <dt>Failures</dt><dd>{stats.failures}</dd>
        <dt>Success rate</dt><dd>{pct === null ? "—" : `${pct}%`}</dd>
        <dt>Last flashed</dt>
        <dd>
          {stats.last_flashed_at
            ? `${stats.last_flashed_at} · ${stats.last_flashed_client} · ${stats.last_flashed_port}`
            : "—"}
        </dd>
      </dl>
    </div>
  );
}
```

- [ ] **Step 2: `TagChip.tsx`**

Create `services/flasher/web/src/components/TagChip.tsx`:
```typescript
import { Tag } from "../types";

interface Props {
  tag: Tag;
  onRemove?: (id: string) => void;
  selected?: boolean;
  onClick?: () => void;
}

export function TagChip({ tag, onRemove, selected, onClick }: Props) {
  return (
    <span
      className={`tag-chip ${selected ? "selected" : ""}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      {tag.name}
      {onRemove ? (
        <button className="tag-chip-remove" onClick={(e) => { e.stopPropagation(); onRemove(tag.id); }}>
          ×
        </button>
      ) : null}
    </span>
  );
}
```

- [ ] **Step 3: `TagManager.tsx`**

Create `services/flasher/web/src/components/TagManager.tsx`:
```typescript
import { useEffect, useState } from "react";
import { createTag, deleteTag, listTags, renameTag } from "../api";
import { Tag } from "../types";

interface Props { open: boolean; onClose: () => void; }

export function TagManager({ open, onClose }: Props) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() { setTags((await listTags()).items); }
  useEffect(() => { if (open) refresh(); }, [open]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <header><h3>Tags</h3><button onClick={onClose}>Close</button></header>
        {error ? <div className="error">{error}</div> : null}
        <div className="tag-create-row">
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="new tag name" />
          <button
            disabled={!newName.trim()}
            onClick={async () => {
              try { await createTag(newName.trim()); setNewName(""); setError(null); await refresh(); }
              catch (e: any) { setError(e.body?.detail ?? String(e)); }
            }}
          >Create</button>
        </div>
        <ul className="tag-list">
          {tags.map(t => (
            <li key={t.id}>
              {editingId === t.id ? (
                <>
                  <input value={editingName} onChange={e => setEditingName(e.target.value)} />
                  <button onClick={async () => {
                    try { await renameTag(t.id, editingName.trim()); setEditingId(null); setError(null); await refresh(); }
                    catch (e: any) { setError(e.body?.detail ?? String(e)); }
                  }}>Save</button>
                  <button onClick={() => setEditingId(null)}>Cancel</button>
                </>
              ) : (
                <>
                  <span className="tag-name">{t.name}</span>
                  <span className="tag-count">{t.firmware_count ?? 0}</span>
                  <button onClick={() => { setEditingId(t.id); setEditingName(t.name); }}>Rename</button>
                  <button onClick={async () => {
                    if (!confirm(`Delete tag "${t.name}"? This removes it from all firmware records.`)) return;
                    await deleteTag(t.id); await refresh();
                  }}>Delete</button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Build**

From `services/flasher/web/`: `npm run build`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add services/flasher/web/src/components/StatsCard.tsx services/flasher/web/src/components/TagChip.tsx services/flasher/web/src/components/TagManager.tsx
git commit -m "feat(flasher/web): StatsCard, TagChip, TagManager"
```

---

### Task 8.2: Firmware tab (list, detail, upload form)

**Files:**
- Create: `services/flasher/web/src/components/FirmwareUploadForm.tsx`
- Create: `services/flasher/web/src/components/FirmwareList.tsx`
- Create: `services/flasher/web/src/components/FirmwareDetail.tsx`
- Modify: `services/flasher/web/src/tabs/FirmwareTab.tsx`

- [ ] **Step 1: `FirmwareUploadForm.tsx`**

Create `services/flasher/web/src/components/FirmwareUploadForm.tsx`:
```typescript
import { useEffect, useState } from "react";
import { createFirmware, listTags } from "../api";
import { FirmwareRecord, Tag } from "../types";

interface Props {
  initialFirmware?: string;
  initialFilename?: string;
  onCreated: (row: FirmwareRecord) => void;
  onCancel?: () => void;
}

export function FirmwareUploadForm({ initialFirmware = "", initialFilename, onCreated, onCancel }: Props) {
  const [name, setName] = useState(initialFilename?.replace(/\.hex$/, "") ?? "");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [firmware, setFirmware] = useState(initialFirmware);
  const [originalFilename, setOriginalFilename] = useState(initialFilename ?? null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [chosenTagIds, setChosenTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  async function onFile(file: File) {
    const text = await file.text();
    setFirmware(text);
    setOriginalFilename(file.name);
    if (!name) setName(file.name.replace(/\.hex$/, ""));
  }

  return (
    <form
      className="firmware-upload-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          const row = await createFirmware({
            name, description,
            test_command: tcmd || null,
            expected_response: eresp || null,
            firmware,
            original_filename: originalFilename,
            tags: chosenTagIds,
          });
          onCreated(row);
        } catch (e: any) { setError(e.body?.detail ?? String(e)); }
        finally { setBusy(false); }
      }}
    >
      <label>Name <input required value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
      <label>Firmware (.hex)
        <input type="file" accept=".hex" onChange={e => e.target.files?.[0] && onFile(e.target.files[0])} />
      </label>
      {firmware ? <p className="muted">{firmware.length} chars loaded.</p> : null}
      <label>Test command (hex, optional) <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
      <label>Expected response (hex, optional) <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
      <fieldset>
        <legend>Tags</legend>
        {tags.map(t => (
          <label key={t.id}>
            <input
              type="checkbox"
              checked={chosenTagIds.includes(t.id)}
              onChange={e => setChosenTagIds(s =>
                e.target.checked ? [...s, t.id] : s.filter(x => x !== t.id))}
            />
            {t.name}
          </label>
        ))}
      </fieldset>
      {error ? <div className="error">{error}</div> : null}
      <div className="actions">
        <button type="submit" disabled={busy || !firmware || !name.trim()}>Upload</button>
        {onCancel ? <button type="button" onClick={onCancel}>Cancel</button> : null}
      </div>
    </form>
  );
}
```

- [ ] **Step 2: `FirmwareList.tsx`**

Create `services/flasher/web/src/components/FirmwareList.tsx`:
```typescript
import { useEffect, useState } from "react";
import { deleteFirmware, downloadFirmwareUrl, listFirmware, listTags } from "../api";
import { FirmwareRecord, Tag } from "../types";
import { TagChip } from "./TagChip";

interface Props {
  onSelect: (row: FirmwareRecord) => void;
  selectedId: string | null;
}

export function FirmwareList({ onSelect, selectedId }: Props) {
  const [items, setItems] = useState<FirmwareRecord[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [q, setQ] = useState("");

  async function refresh() {
    const r = await listFirmware({ tag: tagFilter, q: q || undefined, limit: 200 });
    setItems(r.items);
  }
  useEffect(() => { refresh(); }, [tagFilter.join(","), q]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="record-list">
      <div className="filter-bar">
        <input placeholder="search by name" value={q} onChange={e => setQ(e.target.value)} />
        <div className="tag-filter-chips">
          {tags.map(t => (
            <TagChip
              key={t.id} tag={t}
              selected={tagFilter.includes(t.id)}
              onClick={() => setTagFilter(s =>
                s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id])}
            />
          ))}
        </div>
      </div>
      <ul>
        {items.map(row => (
          <li key={row.id} className={selectedId === row.id ? "active" : ""}
              onClick={() => onSelect(row)}>
            <div className="row-name">{row.name}</div>
            <div className="row-tags">{row.tags.map(t => <TagChip key={t.id} tag={t} />)}</div>
            <div className="row-meta">
              {row.sha256.slice(0, 12)} · {row.size_bytes} B · flashes: {row.stats.total}
            </div>
            <div className="row-actions">
              <a href={downloadFirmwareUrl(row.id)} download>Download</a>
              <button onClick={async (e) => {
                e.stopPropagation();
                const refs = row.stats.total;
                if (!confirm(
                  refs === 0
                    ? `Delete firmware "${row.name}"?`
                    : `Delete firmware "${row.name}"? It was used in ${refs} flashes — replay on those rows will fail.`
                )) return;
                try { await deleteFirmware(row.id); await refresh(); }
                catch (e: any) { alert(e.body?.detail ?? String(e)); }
              }}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: `FirmwareDetail.tsx`**

Create `services/flasher/web/src/components/FirmwareDetail.tsx`:
```typescript
import { useEffect, useState } from "react";
import { getFirmware, listFirmwareFlashes, listTags, patchFirmware } from "../api";
import { FirmwareRecord, FlashRowSummary, Tag } from "../types";
import { StatsCard } from "./StatsCard";
import { TagChip } from "./TagChip";

interface Props {
  firmwareId: string;
  onOpenFlash: (flashId: string) => void;
}

export function FirmwareDetail({ firmwareId, onOpenFlash }: Props) {
  const [row, setRow] = useState<FirmwareRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);

  async function refresh() {
    const r = await getFirmware(firmwareId);
    setRow(r);
    setName(r.name); setDescription(r.description);
    setTcmd(r.test_command ?? ""); setEresp(r.expected_response ?? "");
    setTagIds(r.tags.map(t => t.id));
    const f = await listFirmwareFlashes(firmwareId);
    setFlashes(f.items);
  }
  useEffect(() => { refresh(); }, [firmwareId]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  if (!row) return <div>Loading…</div>;
  return (
    <div className="record-detail">
      <h3>{row.name}</h3>
      <p className="muted">sha256 {row.sha256} · {row.size_bytes} B · created {row.created_at}</p>
      <StatsCard stats={row.stats} />
      <form onSubmit={async (e) => {
        e.preventDefault();
        await patchFirmware(firmwareId, {
          name, description,
          test_command: tcmd || null,
          expected_response: eresp || null,
          tags: tagIds,
        });
        await refresh();
      }}>
        <label>Name <input value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
        <label>Test command <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
        <label>Expected response <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
        <fieldset>
          <legend>Tags</legend>
          {tags.map(t => (
            <label key={t.id}>
              <input type="checkbox" checked={tagIds.includes(t.id)}
                     onChange={e => setTagIds(s => e.target.checked
                       ? [...s, t.id] : s.filter(x => x !== t.id))} />
              {t.name}
            </label>
          ))}
        </fieldset>
        <button type="submit">Save</button>
      </form>
      <h4>Flash history</h4>
      <ul className="flash-mini-list">
        {flashes.map(f => (
          <li key={f.id} onClick={() => onOpenFlash(f.id)}>
            {f.started_at} · {f.client} · {f.port_name} · {f.outcome ?? f.status}
            {f.duration_ms ? ` · ${(f.duration_ms / 1000).toFixed(1)}s` : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: `FirmwareTab.tsx` assembly**

Replace `services/flasher/web/src/tabs/FirmwareTab.tsx`:
```typescript
import { useState } from "react";
import { FirmwareDetail } from "../components/FirmwareDetail";
import { FirmwareList } from "../components/FirmwareList";
import { FirmwareUploadForm } from "../components/FirmwareUploadForm";
import { TagManager } from "../components/TagManager";
import { LogDetailDrawer } from "../components/LogDetailDrawer";

export function FirmwareTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [tagsOpen, setTagsOpen] = useState(false);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  return (
    <div className="tab-pane firmware-tab two-pane">
      <header className="pane-header">
        <button onClick={() => setUploadOpen(true)}>Upload firmware</button>
        <button onClick={() => setTagsOpen(true)}>Manage tags</button>
      </header>
      <div className="two-pane-body">
        <div className="pane-left">
          <FirmwareList onSelect={r => setSelectedId(r.id)} selectedId={selectedId} />
        </div>
        <div className="pane-right">
          {selectedId
            ? <FirmwareDetail firmwareId={selectedId} onOpenFlash={setOpenFlashId} />
            : <p className="muted">Select a firmware record on the left.</p>}
        </div>
      </div>
      {uploadOpen ? (
        <div className="modal-backdrop" onClick={() => setUploadOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Upload firmware</h3>
            <FirmwareUploadForm
              onCreated={row => { setUploadOpen(false); setSelectedId(row.id); }}
              onCancel={() => setUploadOpen(false)}
            />
          </div>
        </div>
      ) : null}
      <TagManager open={tagsOpen} onClose={() => setTagsOpen(false)} />
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
```

(LogDetailDrawer is created in Task 8.4.)

- [ ] **Step 5: Build and commit**

From `services/flasher/web/`: `npm run build`
Expected: success.

```bash
git add services/flasher/web/src/components/FirmwareUploadForm.tsx services/flasher/web/src/components/FirmwareList.tsx services/flasher/web/src/components/FirmwareDetail.tsx services/flasher/web/src/tabs/FirmwareTab.tsx
git commit -m "feat(flasher/web): Firmware tab (list/detail/upload)"
```

---

### Task 8.3: Backups tab (list, detail, promote)

**Files:**
- Create: `services/flasher/web/src/components/BackupList.tsx`
- Create: `services/flasher/web/src/components/BackupDetail.tsx`
- Create: `services/flasher/web/src/components/PromoteBackupModal.tsx`
- Modify: `services/flasher/web/src/tabs/BackupsTab.tsx`

- [ ] **Step 1: `BackupList.tsx`**

Create `services/flasher/web/src/components/BackupList.tsx`:
```typescript
import { useEffect, useState } from "react";
import { bulkDeleteBackups, deleteBackup, downloadBackupUrl, listBackups, listClients } from "../api";
import { BackupRecord, ClientEntry } from "../types";

interface Props {
  onSelect: (row: BackupRecord) => void;
  onPromote: (row: BackupRecord) => void;
  selectedId: string | null;
}

export function BackupList({ onSelect, onPromote, selectedId }: Props) {
  const [items, setItems] = useState<BackupRecord[]>([]);
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [clientFilter, setClientFilter] = useState<string | "">("");
  const [q, setQ] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  async function refresh() {
    const r = await listBackups({ client: clientFilter || undefined, q: q || undefined, limit: 200 });
    setItems(r.items); setSelectedIds(new Set());
  }
  useEffect(() => { refresh(); }, [clientFilter, q]);
  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);

  return (
    <div className="record-list">
      <div className="filter-bar">
        <input placeholder="search by name" value={q} onChange={e => setQ(e.target.value)} />
        <select value={clientFilter} onChange={e => setClientFilter(e.target.value)}>
          <option value="">(any client)</option>
          {clients.map(c => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>
        <button
          disabled={selectedIds.size === 0}
          onClick={async () => {
            if (!confirm(`Delete ${selectedIds.size} backups?`)) return;
            const result = await bulkDeleteBackups(Array.from(selectedIds));
            if (result.refused.length) alert(
              `Refused:\n${result.refused.map(r => `${r.id}: ${r.reason}`).join("\n")}`,
            );
            await refresh();
          }}
        >Delete selected ({selectedIds.size})</button>
      </div>
      <ul>
        {items.map(row => (
          <li key={row.id} className={selectedId === row.id ? "active" : ""}
              onClick={() => onSelect(row)}>
            <input type="checkbox" checked={selectedIds.has(row.id)}
                   onClick={e => e.stopPropagation()}
                   onChange={e => setSelectedIds(s => {
                     const n = new Set(s);
                     e.target.checked ? n.add(row.id) : n.delete(row.id);
                     return n;
                   })} />
            <div className="row-name">{row.name}</div>
            <div className="row-meta">
              {row.captured_at} · {row.client} · {row.port_name} ·
              {row.product ?? `${row.vid}:${row.pid}`} ·
              sha {row.sha256.slice(0, 12)} ·
              flashes: {row.stats.total}
            </div>
            <div className="row-actions">
              <a href={downloadBackupUrl(row.id)} download>Download</a>
              <button onClick={e => { e.stopPropagation(); onPromote(row); }}>Promote</button>
              <button onClick={async e => {
                e.stopPropagation();
                if (!confirm(`Delete backup "${row.name}"?`)) return;
                try { await deleteBackup(row.id); await refresh(); }
                catch (e: any) { alert(e.body?.detail ?? String(e)); }
              }}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: `BackupDetail.tsx`**

Create `services/flasher/web/src/components/BackupDetail.tsx`:
```typescript
import { useEffect, useState } from "react";
import { getBackup, listBackupFlashes, patchBackup } from "../api";
import { BackupRecord, FlashRowSummary } from "../types";
import { StatsCard } from "./StatsCard";

interface Props {
  backupId: string;
  onOpenFlash: (flashId: string) => void;
}

export function BackupDetail({ backupId, onOpenFlash }: Props) {
  const [row, setRow] = useState<BackupRecord | null>(null);
  const [flashes, setFlashes] = useState<FlashRowSummary[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");

  async function refresh() {
    const r = await getBackup(backupId);
    setRow(r);
    setName(r.name); setDescription(r.description);
    setTcmd(r.test_command ?? ""); setEresp(r.expected_response ?? "");
    setFlashes((await listBackupFlashes(backupId)).items);
  }
  useEffect(() => { refresh(); }, [backupId]);
  if (!row) return <div>Loading…</div>;

  return (
    <div className="record-detail">
      <h3>{row.name}</h3>
      <p className="muted">
        sha256 {row.sha256} · {row.size_bytes} B · captured {row.captured_at}
      </p>
      <dl className="meta-grid">
        <dt>Client</dt><dd>{row.client}</dd>
        <dt>Port</dt><dd>{row.port_name}</dd>
        <dt>VID:PID</dt><dd>{row.vid}:{row.pid}</dd>
        <dt>Serial #</dt><dd>{row.serial_number || "—"}</dd>
        <dt>Product</dt><dd>{row.product || "—"}</dd>
        <dt>SerialHop path</dt><dd>{row.serialhop_saved_path}</dd>
      </dl>
      <StatsCard stats={row.stats} />
      <form onSubmit={async (e) => {
        e.preventDefault();
        await patchBackup(backupId, {
          name, description,
          test_command: tcmd || null,
          expected_response: eresp || null,
        });
        await refresh();
      }}>
        <label>Name <input value={name} onChange={e => setName(e.target.value)} /></label>
        <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
        <label>Test command <input value={tcmd} onChange={e => setTcmd(e.target.value)} /></label>
        <label>Expected response <input value={eresp} onChange={e => setEresp(e.target.value)} /></label>
        <button type="submit">Save</button>
      </form>
      <h4>Used by flashes</h4>
      <ul className="flash-mini-list">
        {flashes.map(f => (
          <li key={f.id} onClick={() => onOpenFlash(f.id)}>
            {f.started_at} · {f.client} · {f.port_name} · {f.outcome ?? f.status}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: `PromoteBackupModal.tsx`**

Create `services/flasher/web/src/components/PromoteBackupModal.tsx`:
```typescript
import { useEffect, useState } from "react";
import { listTags, promoteBackup } from "../api";
import { BackupRecord, FirmwareRecord, Tag } from "../types";

interface Props {
  backup: BackupRecord;
  onCreated: (firmware: FirmwareRecord) => void;
  onClose: () => void;
}

export function PromoteBackupModal({ backup, onCreated, onClose }: Props) {
  const [name, setName] = useState(backup.name);
  const [description, setDescription] = useState(backup.description);
  const [copyPair, setCopyPair] = useState(true);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Promote to firmware</h3>
        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            const fw = await promoteBackup(backup.id, {
              name, description, copy_test_pair: copyPair, tags: tagIds,
            });
            onCreated(fw);
          } catch (e: any) { setError(e.body?.detail ?? String(e)); }
        }}>
          <label>Name <input required value={name} onChange={e => setName(e.target.value)} /></label>
          <label>Description <textarea value={description} onChange={e => setDescription(e.target.value)} /></label>
          <label>
            <input type="checkbox" checked={copyPair} onChange={e => setCopyPair(e.target.checked)} />
            Copy test pair
          </label>
          <fieldset>
            <legend>Tags</legend>
            {tags.map(t => (
              <label key={t.id}>
                <input type="checkbox" checked={tagIds.includes(t.id)}
                       onChange={e => setTagIds(s => e.target.checked
                         ? [...s, t.id] : s.filter(x => x !== t.id))} />
                {t.name}
              </label>
            ))}
          </fieldset>
          {error ? <div className="error">{error}</div> : null}
          <div className="actions">
            <button type="submit">Create firmware</button>
            <button type="button" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `BackupsTab.tsx` assembly**

Replace `services/flasher/web/src/tabs/BackupsTab.tsx`:
```typescript
import { useState } from "react";
import { BackupDetail } from "../components/BackupDetail";
import { BackupList } from "../components/BackupList";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { PromoteBackupModal } from "../components/PromoteBackupModal";
import { BackupRecord } from "../types";

export function BackupsTab() {
  const [selected, setSelected] = useState<BackupRecord | null>(null);
  const [promoting, setPromoting] = useState<BackupRecord | null>(null);
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);

  return (
    <div className="tab-pane backups-tab two-pane">
      <div className="two-pane-body">
        <div className="pane-left">
          <BackupList
            onSelect={setSelected}
            onPromote={setPromoting}
            selectedId={selected?.id ?? null}
          />
        </div>
        <div className="pane-right">
          {selected
            ? <BackupDetail backupId={selected.id} onOpenFlash={setOpenFlashId} />
            : <p className="muted">Select a backup on the left.</p>}
        </div>
      </div>
      {promoting ? (
        <PromoteBackupModal
          backup={promoting}
          onClose={() => setPromoting(null)}
          onCreated={() => setPromoting(null)}
        />
      ) : null}
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Build and commit**

```bash
git add services/flasher/web/src/components/BackupList.tsx services/flasher/web/src/components/BackupDetail.tsx services/flasher/web/src/components/PromoteBackupModal.tsx services/flasher/web/src/tabs/BackupsTab.tsx
git commit -m "feat(flasher/web): Backups tab with promote-to-firmware"
```

---

### Task 8.4: Logs tab + `LogDetailDrawer`

**Files:**
- Create: `services/flasher/web/src/components/LogFilters.tsx`
- Create: `services/flasher/web/src/components/LogTable.tsx`
- Create: `services/flasher/web/src/components/LogDetailDrawer.tsx`
- Modify: `services/flasher/web/src/tabs/LogsTab.tsx`

- [ ] **Step 1: `LogFilters.tsx`**

Create `services/flasher/web/src/components/LogFilters.tsx`:
```typescript
import { useEffect, useState } from "react";
import { listClients, listFirmware } from "../api";
import { ClientEntry, FirmwareRecord, FlashFilters } from "../types";

const OUTCOMES = [
  "success", "rolled_back_verify_failed", "rolled_back_test_failed",
  "failed_preflight", "failed_backup", "failed_no_recovery",
  "error", "interrupted",
];

interface Props {
  value: FlashFilters;
  onChange: (next: FlashFilters) => void;
}

export function LogFilters({ value, onChange }: Props) {
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [firmware, setFirmware] = useState<FirmwareRecord[]>([]);

  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);
  useEffect(() => { listFirmware({ limit: 500 }).then(r => setFirmware(r.items)); }, []);

  return (
    <div className="log-filters">
      <fieldset>
        <legend>Client</legend>
        {clients.map(c => (
          <label key={c.name}>
            <input type="checkbox"
                   checked={(value.client ?? []).includes(c.name)}
                   onChange={e => onChange({
                     ...value,
                     client: e.target.checked
                       ? [...(value.client ?? []), c.name]
                       : (value.client ?? []).filter(x => x !== c.name),
                   })} />
            {c.name}{c.online ? "" : " (offline)"}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Outcome</legend>
        {OUTCOMES.map(o => (
          <label key={o}>
            <input type="checkbox"
                   checked={(value.outcome ?? []).includes(o)}
                   onChange={e => onChange({
                     ...value,
                     outcome: e.target.checked
                       ? [...(value.outcome ?? []), o]
                       : (value.outcome ?? []).filter(x => x !== o),
                   })} />
            {o}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>Source</legend>
        <select value={value.source_kind ?? ""}
                onChange={e => onChange({
                  ...value,
                  source_kind: (e.target.value || undefined) as any,
                  source_id: undefined,
                })}>
          <option value="">(any)</option>
          <option value="firmware">firmware</option>
          <option value="backup">backup</option>
        </select>
        {value.source_kind === "firmware" ? (
          <select value={value.source_id ?? ""}
                  onChange={e => onChange({ ...value, source_id: e.target.value || undefined })}>
            <option value="">(any firmware)</option>
            {firmware.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        ) : null}
      </fieldset>
      <fieldset>
        <legend>Date range</legend>
        <label>Since <input type="date" value={value.since?.slice(0, 10) ?? ""}
                            onChange={e => onChange({
                              ...value,
                              since: e.target.value ? `${e.target.value}T00:00:00Z` : undefined,
                            })} /></label>
        <label>Until <input type="date" value={value.until?.slice(0, 10) ?? ""}
                            onChange={e => onChange({
                              ...value,
                              until: e.target.value ? `${e.target.value}T23:59:59Z` : undefined,
                            })} /></label>
      </fieldset>
      <button onClick={() => onChange({})}>Clear all</button>
    </div>
  );
}
```

- [ ] **Step 2: `LogTable.tsx`**

Create `services/flasher/web/src/components/LogTable.tsx`:
```typescript
import { useEffect, useState } from "react";
import { listFlashes } from "../api";
import { FlashFilters, FlashRowSummary } from "../types";

interface Props {
  filters: FlashFilters;
  onOpen: (flashId: string) => void;
}

export function LogTable({ filters, onOpen }: Props) {
  const [items, setItems] = useState<FlashRowSummary[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);

  async function refresh() {
    const r = await listFlashes(filters, 50);
    setItems(r.items); setNextBefore(r.next_before);
  }
  useEffect(() => { refresh(); }, [JSON.stringify(filters)]);

  async function loadMore() {
    if (!nextBefore) return;
    const r = await listFlashes(filters, 50, nextBefore);
    setItems(prev => [...prev, ...r.items]); setNextBefore(r.next_before);
  }

  return (
    <div className="log-table">
      <table>
        <thead>
          <tr>
            <th>Started</th><th>Client</th><th>Port</th>
            <th>Source</th><th>Outcome</th><th>Duration</th><th>Note</th>
          </tr>
        </thead>
        <tbody>
          {items.map(r => (
            <tr key={r.id} onClick={() => onOpen(r.id)}>
              <td>{r.started_at}</td>
              <td>{r.client}</td>
              <td>{r.port_name}</td>
              <td>{r.source_kind}: {r.firmware_name}</td>
              <td>{r.outcome ?? r.status}</td>
              <td>{r.duration_ms != null ? `${(r.duration_ms/1000).toFixed(1)}s` : ""}</td>
              <td className="muted">{r.operator_note.slice(0, 60)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {nextBefore ? <button onClick={loadMore}>Load more</button> : null}
    </div>
  );
}
```

- [ ] **Step 3: `LogDetailDrawer.tsx`**

Create `services/flasher/web/src/components/LogDetailDrawer.tsx`:
```typescript
import { useEffect, useState } from "react";
import { getFlash, listClients, patchFlashNote, replayFlash } from "../api";
import { ClientEntry, FlashRowDetail } from "../types";
import { StageStrip } from "./StageStrip";
import { HexDiff } from "./HexDiff";

interface Props {
  flashId: string;
  onClose: () => void;
}

export function LogDetailDrawer({ flashId, onClose }: Props) {
  const [row, setRow] = useState<FlashRowDetail | null>(null);
  const [note, setNote] = useState("");
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [replayClient, setReplayClient] = useState<string>("");
  const [replayPort, setReplayPort] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const r = await getFlash(flashId);
    setRow(r); setNote(r.operator_note);
    setReplayClient(r.client); setReplayPort(r.port_name);
  }
  useEffect(() => { refresh(); }, [flashId]);
  useEffect(() => { listClients().then(r => setClients(r.clients)); }, []);

  if (!row) return null;
  const stages = (row.result && (row.result as any).stages) || {};
  const testResult = row.result && (row.result as any).test_result;

  return (
    <aside className="drawer">
      <header><h3>Flash {row.id.slice(0, 8)}</h3><button onClick={onClose}>Close</button></header>
      <dl className="meta-grid">
        <dt>Started</dt><dd>{row.started_at}</dd>
        <dt>Status</dt><dd>{row.status} ({row.outcome ?? "—"})</dd>
        <dt>Client / port</dt><dd>{row.client} · {row.port_name}</dd>
        <dt>Firmware</dt><dd>{row.firmware_name} (sha {row.firmware_sha256.slice(0, 12)})</dd>
        <dt>Source kind</dt><dd>{row.source_kind}</dd>
      </dl>
      <StageStrip stages={stages} />
      {testResult ? (
        <HexDiff expected={testResult.expected} received={testResult.received} />
      ) : null}
      <details><summary>Raw JSON</summary><pre>{JSON.stringify(row.result ?? {}, null, 2)}</pre></details>
      <form onSubmit={async (e) => {
        e.preventDefault();
        try { await patchFlashNote(flashId, note); await refresh(); }
        catch (e: any) { setError(e.body?.detail ?? String(e)); }
      }}>
        <label>Operator note <textarea value={note} onChange={e => setNote(e.target.value)} /></label>
        <button type="submit">Save note</button>
        {error ? <div className="error">{error}</div> : null}
      </form>
      <h4>Repeat this flash</h4>
      <div className="replay-controls">
        <label>Client <select value={replayClient} onChange={e => setReplayClient(e.target.value)}>
          {clients.map(c => <option key={c.name} value={c.name} disabled={!c.online}>
            {c.name}{c.online ? "" : " (offline)"}
          </option>)}
        </select></label>
        <label>Port <input value={replayPort} onChange={e => setReplayPort(e.target.value)} /></label>
        <button onClick={async () => {
          try {
            await replayFlash(flashId, { client: replayClient, port: replayPort });
            onClose();
          } catch (e: any) {
            if (e.status === 410) alert("Source firmware/backup has been deleted — cannot replay.");
            else alert(e.body?.detail ?? String(e));
          }
        }}>Repeat</button>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: `LogsTab.tsx` assembly**

Replace `services/flasher/web/src/tabs/LogsTab.tsx`:
```typescript
import { useState } from "react";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { LogFilters } from "../components/LogFilters";
import { LogTable } from "../components/LogTable";
import { FlashFilters } from "../types";

export function LogsTab() {
  const [filters, setFilters] = useState<FlashFilters>({});
  const [openFlashId, setOpenFlashId] = useState<string | null>(null);
  return (
    <div className="tab-pane logs-tab">
      <LogFilters value={filters} onChange={setFilters} />
      <LogTable filters={filters} onOpen={setOpenFlashId} />
      {openFlashId ? (
        <LogDetailDrawer flashId={openFlashId} onClose={() => setOpenFlashId(null)} />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Build and commit**

```bash
git add services/flasher/web/src/components/LogFilters.tsx services/flasher/web/src/components/LogTable.tsx services/flasher/web/src/components/LogDetailDrawer.tsx services/flasher/web/src/tabs/LogsTab.tsx
git commit -m "feat(flasher/web): Logs tab with filters and detail drawer"
```

---

## Phase 9 — Flash tab rework

### Task 9.1: `ClientPicker` renders offline rows muted

**Files:**
- Modify: `services/flasher/web/src/components/ClientPicker.tsx`

- [ ] **Step 1: Replace ClientPicker**

Replace `services/flasher/web/src/components/ClientPicker.tsx` with:
```typescript
import { useEffect, useState } from "react";
import { listClients } from "../api";
import { ClientEntry } from "../types";

interface Props {
  value: string | null;
  onChange: (name: string | null) => void;
}

export function ClientPicker({ value, onChange }: Props) {
  const [items, setItems] = useState<ClientEntry[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try { setItems((await listClients()).clients); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="client-picker">
      <label>
        Lab machine:
        <select
          value={value ?? ""}
          onChange={e => onChange(e.target.value || null)}
        >
          <option value="">(select…)</option>
          {items.map(c => (
            <option key={c.name} value={c.name} disabled={!c.online}>
              {c.name}{c.online ? "" : " — offline"}
            </option>
          ))}
        </select>
      </label>
      <button onClick={refresh} disabled={loading}>Retry probe</button>
    </div>
  );
}
```

- [ ] **Step 2: Build and commit**

```bash
git add services/flasher/web/src/components/ClientPicker.tsx
git commit -m "feat(flasher/web): ClientPicker shows offline rows disabled"
```

---

### Task 9.2: `FirmwareSourcePicker` — unified firmware + backup picker, plus inline "Create new firmware"

**Files:**
- Create: `services/flasher/web/src/components/FirmwareSourcePicker.tsx`

This component owns its own search state. It surfaces the selected source via `value` / `onChange`. The "Create new firmware" path opens an inline modal containing `FirmwareUploadForm`; on success it selects the newly-created record.

- [ ] **Step 1: Create the component**

Create `services/flasher/web/src/components/FirmwareSourcePicker.tsx`:
```typescript
import { useEffect, useState } from "react";
import { listBackups, listFirmware, listTags } from "../api";
import { BackupRecord, FirmwareRecord, Tag } from "../types";
import { FirmwareUploadForm } from "./FirmwareUploadForm";
import { TagChip } from "./TagChip";

export type FlashSource =
  | { kind: "firmware"; record: FirmwareRecord }
  | { kind: "backup"; record: BackupRecord };

interface Props {
  value: FlashSource | null;
  onChange: (next: FlashSource | null) => void;
}

export function FirmwareSourcePicker({ value, onChange }: Props) {
  const [segment, setSegment] = useState<"firmware" | "backups">("firmware");
  const [firmwareItems, setFirmwareItems] = useState<FirmwareRecord[]>([]);
  const [backupItems, setBackupItems] = useState<BackupRecord[]>([]);
  const [q, setQ] = useState("");
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const [uploadOpen, setUploadOpen] = useState(false);

  async function refresh() {
    if (segment === "firmware") {
      setFirmwareItems((await listFirmware({
        q: q || undefined, tag: tagFilter, limit: 200,
      })).items);
    } else {
      setBackupItems((await listBackups({ q: q || undefined, limit: 200 })).items);
    }
  }
  useEffect(() => { refresh(); }, [segment, q, tagFilter.join(",")]);
  useEffect(() => { listTags().then(r => setTags(r.items)); }, []);

  return (
    <div className="firmware-source-picker">
      <div className="segment-bar">
        <button className={segment === "firmware" ? "active" : ""}
                onClick={() => setSegment("firmware")}>Firmware</button>
        <button className={segment === "backups" ? "active" : ""}
                onClick={() => setSegment("backups")}>Backups</button>
        <button onClick={() => setUploadOpen(true)}>+ Create new firmware</button>
      </div>
      <input className="search" placeholder="search by name"
             value={q} onChange={e => setQ(e.target.value)} />
      {segment === "firmware" ? (
        <div className="tag-filter-chips">
          {tags.map(t => (
            <TagChip key={t.id} tag={t}
                     selected={tagFilter.includes(t.id)}
                     onClick={() => setTagFilter(s =>
                       s.includes(t.id) ? s.filter(x => x !== t.id) : [...s, t.id])} />
          ))}
        </div>
      ) : null}
      <ul className="source-list">
        {segment === "firmware" ? firmwareItems.map(f => (
          <li key={f.id}
              className={value?.kind === "firmware" && value.record.id === f.id ? "active" : ""}
              onClick={() => onChange({ kind: "firmware", record: f })}>
            <div className="row-name">{f.name}</div>
            <div className="row-tags">{f.tags.map(t => <TagChip key={t.id} tag={t} />)}</div>
            <div className="row-meta">sha {f.sha256.slice(0,12)} · {f.size_bytes} B</div>
          </li>
        )) : backupItems.map(b => (
          <li key={b.id}
              className={value?.kind === "backup" && value.record.id === b.id ? "active" : ""}
              onClick={() => onChange({ kind: "backup", record: b })}>
            <div className="row-name">{b.name}</div>
            <div className="row-meta">
              {b.captured_at} · {b.client}/{b.port_name} · sha {b.sha256.slice(0,12)}
            </div>
          </li>
        ))}
      </ul>
      {value ? (
        <div className="selected-source">
          <strong>Selected:</strong> {value.kind} — {value.record.name}
          <button onClick={() => onChange(null)}>Clear</button>
        </div>
      ) : null}
      {uploadOpen ? (
        <div className="modal-backdrop" onClick={() => setUploadOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create new firmware</h3>
            <FirmwareUploadForm
              onCreated={row => {
                setUploadOpen(false);
                onChange({ kind: "firmware", record: row });
              }}
              onCancel={() => setUploadOpen(false)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add services/flasher/web/src/components/FirmwareSourcePicker.tsx
git commit -m "feat(flasher/web): unified firmware/backup source picker"
```

---

### Task 9.3: Strip buttons from `ResultView`

**Files:**
- Modify: `services/flasher/web/src/components/ResultView.tsx`

- [ ] **Step 1: Replace component**

Read the current `ResultView.tsx` to preserve the badge / stage strip / hex-diff / raw JSON rendering, then remove the `onFlashAnother` and `onDone` props plus their buttons. The remaining surface is purely render-only.

Open `services/flasher/web/src/components/ResultView.tsx` and:
1. Delete the `onFlashAnother` and `onDone` props from the component's `Props` interface.
2. Delete the `<div className="result-actions">…</div>` block at the bottom (containing the two buttons).
3. If `Props` had `onFlashAnother: () => void` and `onDone: () => void`, callers in `App.tsx` (now in the soon-to-be-rewritten `FlashTab`) will stop passing them.

- [ ] **Step 2: Commit**

```bash
git add services/flasher/web/src/components/ResultView.tsx
git commit -m "refactor(flasher/web): drop ResultView buttons (form-always-at-top)"
```

---

### Task 9.4: Rewrite `FlashTab.tsx` — form always at top, running/result below

**Files:**
- Modify: `services/flasher/web/src/tabs/FlashTab.tsx`

- [ ] **Step 1: Replace FlashTab**

Replace `services/flasher/web/src/tabs/FlashTab.tsx`:
```typescript
import { useEffect, useState } from "react";
import { getFlash, patchFirmware, postFlash } from "../api";
import { ClientPicker } from "../components/ClientPicker";
import { FlashButton } from "../components/FlashButton";
import { FlashOptions } from "../components/FlashOptions";
import { FirmwareSourcePicker, FlashSource } from "../components/FirmwareSourcePicker";
import { PortTable } from "../components/PortTable";
import { ResultView } from "../components/ResultView";
import { RunningView } from "../components/RunningView";
import { TestPairEditor } from "../components/TestPairEditor";
import { FlashRowDetail, PortRow } from "../types";

interface Props {
  runningFlashId: string | null;
  setRunningFlashId: (id: string | null) => void;
}

export function FlashTab({ runningFlashId, setRunningFlashId }: Props) {
  const [client, setClient] = useState<string | null>(null);
  const [ports, setPorts] = useState<PortRow[]>([]);
  const [selectedPort, setSelectedPort] = useState<string | null>(null);
  const [source, setSource] = useState<FlashSource | null>(null);
  const [tcmd, setTcmd] = useState("");
  const [eresp, setEresp] = useState("");
  const [runTest, setRunTest] = useState(true);
  const [skipBackup, setSkipBackup] = useState(false);
  const [savePairToRecord, setSavePairToRecord] = useState(false);
  const [latestFlash, setLatestFlash] = useState<FlashRowDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reset test pair / save-back checkbox whenever the source changes.
  useEffect(() => {
    if (!source) { setTcmd(""); setEresp(""); setRunTest(true); setSavePairToRecord(false); return; }
    const r = source.record as any;
    setTcmd(r.test_command ?? "");
    setEresp(r.expected_response ?? "");
    setRunTest(Boolean(r.test_command));
    setSavePairToRecord(false);
  }, [source?.kind, source?.record.id]);

  // Whenever the running id changes (or polling reports terminal), fetch the
  // full flash row so the result view below has data.
  useEffect(() => {
    let cancelled = false;
    async function fetchOne(id: string) {
      try {
        const row = await getFlash(id);
        if (!cancelled) setLatestFlash(row);
      } catch { /* ignore */ }
    }
    if (runningFlashId) fetchOne(runningFlashId);
    // also re-poll latest at 1.5s while running so the result view appears as soon as it terminates
    const tick = window.setInterval(() => {
      if (runningFlashId) fetchOne(runningFlashId);
    }, 1500);
    return () => { cancelled = true; window.clearInterval(tick); };
  }, [runningFlashId]);

  const canFlash = client && selectedPort && source && (!runTest || (tcmd && eresp));

  async function onSubmit() {
    if (!canFlash || !source) return;
    setError(null);
    try {
      const body: any = {
        client, port: selectedPort,
        source: { kind: source.kind, id: source.record.id },
        skip_backup: skipBackup,
      };
      if (runTest) {
        body.test_override = { command: tcmd, expected_response: eresp };
        body.save_test_to_record = savePairToRecord && source.kind === "firmware";
      }
      const r = await postFlash(body);
      setRunningFlashId(r.job_id);
    } catch (e: any) {
      setError(e.body?.detail ?? String(e));
    }
  }

  const isRunning = latestFlash?.status === "running";

  return (
    <div className="tab-pane flash-tab">
      <section className="flash-form">
        <ClientPicker value={client} onChange={setClient} />
        {client ? (
          <PortTable client={client} value={selectedPort} onChange={setSelectedPort}
                     onPortsLoaded={setPorts} />
        ) : null}
        <FirmwareSourcePicker value={source} onChange={setSource} />
        {source ? (
          <>
            <TestPairEditor
              command={tcmd} expectedResponse={eresp}
              onCommandChange={v => { setTcmd(v); }}
              onExpectedChange={v => { setEresp(v); }}
              runTest={runTest} onRunTestChange={setRunTest}
            />
            {source.kind === "firmware" ? (
              <label>
                <input type="checkbox" checked={savePairToRecord}
                       onChange={e => setSavePairToRecord(e.target.checked)} />
                Save edits to record
              </label>
            ) : null}
          </>
        ) : null}
        <FlashOptions skipBackup={skipBackup} onSkipBackupChange={setSkipBackup} />
        <FlashButton disabled={!canFlash} onClick={onSubmit} />
        {error ? <div className="error">{error}</div> : null}
      </section>

      <section className="flash-output">
        {latestFlash ? (
          isRunning ? (
            <RunningView started={latestFlash.started_at}
                         client={latestFlash.client}
                         port={latestFlash.port_name}
                         firmwareName={latestFlash.firmware_name} />
          ) : (
            <ResultView row={latestFlash} />
          )
        ) : null}
      </section>
    </div>
  );
}
```

Note: the props passed to `PortTable`, `RunningView`, `ResultView`, `TestPairEditor`, `FlashOptions`, and `FlashButton` should match the existing components' interfaces. Where signatures changed (e.g., `ResultView` no longer takes `onFlashAnother`/`onDone`), the call sites here are already updated. If a prop name in an existing component doesn't match the one used here, adjust the component prop names rather than the call site — these names reflect the renamed callbacks the new layout needs.

- [ ] **Step 2: Build and commit**

From `services/flasher/web/`: `npm run build`
Expected: build succeeds.

```bash
git add services/flasher/web/src/tabs/FlashTab.tsx
git commit -m "feat(flasher/web): rewrite Flash tab — form on top, running/result below"
```

---

### Task 9.5: Frontend styles polish

**Files:**
- Modify: `services/flasher/web/src/components/styles.css`

- [ ] **Step 1: Append layout styles**

Append to `services/flasher/web/src/components/styles.css`:
```css
.two-pane .two-pane-body {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  padding: 16px;
}
.record-list ul { list-style: none; padding: 0; margin: 0; }
.record-list li { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
.record-list li.active { background: #eef5ff; }
.firmware-source-picker .segment-bar button.active { font-weight: bold; }
.firmware-source-picker .source-list { max-height: 200px; overflow-y: auto; }
.tag-chip { display: inline-block; padding: 2px 6px; background: #eef; border-radius: 8px; margin-right: 4px; }
.tag-chip.selected { background: #ccf; }
.tag-chip-remove { border: none; background: none; color: #a00; cursor: pointer; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal { background: #fff; padding: 16px; min-width: 400px; max-width: 80vw; max-height: 90vh; overflow: auto; }
.drawer { position: fixed; top: 0; right: 0; width: 50vw; height: 100vh; background: #fff; padding: 16px; box-shadow: -2px 0 8px rgba(0,0,0,0.1); overflow: auto; z-index: 20; }
.log-table table { width: 100%; border-collapse: collapse; }
.log-table th, .log-table td { padding: 6px; border-bottom: 1px solid #eee; text-align: left; }
.log-table tbody tr { cursor: pointer; }
.log-table tbody tr:hover { background: #f6f6f6; }
.muted { color: #888; }
.error { color: #a00; }
.flash-tab .flash-form { padding: 16px; }
.flash-tab .flash-output { padding: 16px; border-top: 1px solid #ddd; }
```

- [ ] **Step 2: Build and commit**

```bash
git add services/flasher/web/src/components/styles.css
git commit -m "style(flasher/web): tab/picker/modal/drawer layout"
```

---

## Phase 10 — Deployment, e2e tests, integration smoke

### Task 10.1: Compose template — add `flasher_data` volume + bearer token file + env

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`

- [ ] **Step 1: Update the flasher service block**

Open `compose/docker-compose.yml.tmpl`. The current `flasher:` block (around line 85) looks like:
```yaml
flasher:
  image: __FLASHER_IMAGE__
  restart: unless-stopped
  environment:
    FLASHER_CLIENTS_FILE: /etc/flasher/clients.json
    FLASHER_CHISEL_HOST: chisel
  volumes:
    - ./siteapp/clients.json:/etc/flasher/clients.json:ro
  networks: [labnet]
```

Replace it with:
```yaml
flasher:
  image: __FLASHER_IMAGE__
  restart: unless-stopped
  environment:
    FLASHER_CLIENTS_FILE: /etc/flasher/clients.json
    FLASHER_CHISEL_HOST: chisel
    FLASHER_DATA_DIR: /var/lib/flasher
    FLASHER_UPLOAD_TOKEN__FILE: /run/secrets/flasher_upload_token
  volumes:
    - ./siteapp/clients.json:/etc/flasher/clients.json:ro
    - ./flasher_data:/var/lib/flasher
  secrets:
    - flasher_upload_token
  networks: [labnet]
```

And under the file-level `secrets:` block at the bottom of the template, alongside the existing `grafana_admin_password` / `agent_upload_token` entries, add:
```yaml
flasher_upload_token:
  file: ./flasher/upload_token
```

- [ ] **Step 2: Commit**

```bash
git add compose/docker-compose.yml.tmpl
git commit -m "feat(compose): flasher gains flasher_data volume + bearer token"
```

---

### Task 10.2: Caddyfile — ordered handle blocks (bearer first, basic_auth second)

**Files:**
- Modify: `compose/Caddyfile.tmpl`

- [ ] **Step 1: Update Caddyfile**

Find the existing block:
```caddy
handle /flash* {
    basic_auth {
        admin __ADMIN_BCRYPT_HASH__
    }
    reverse_proxy flasher:8000
}
```

Replace it with:
```caddy
# Flasher bearer-auth automation. Caddy passes through; flasher verifies the token.
handle /flash/api/v1/* {
    reverse_proxy flasher:8000
}
# Flasher operator UI + operator API. Caddy enforces basic_auth.
handle /flash* {
    basic_auth {
        admin __ADMIN_BCRYPT_HASH__
    }
    reverse_proxy flasher:8000
}
```

The order matters — Caddy's `handle` is first-match-wins. The narrower `/flash/api/v1/*` matcher must come before `/flash*`.

- [ ] **Step 2: Commit**

```bash
git add compose/Caddyfile.tmpl
git commit -m "feat(caddy): bearer endpoint at /flash/api/v1/* bypasses basic_auth"
```

---

### Task 10.3: Render script — write `compose/flasher/upload_token`

**Files:**
- Modify: `scripts/lib/render.sh`
- Modify: `compose/config.ci.yaml.tmpl` (or wherever ci-only config is sourced from)
- Modify: `scripts/secrets.sh`

The siteapp pattern (`agent_upload_token`) is the model: rendered into a file under `compose/`, mounted into the container as a Docker secret. The CI config carries a placeholder so the `LDS_REQUIRE_VAULT` guard is satisfied.

- [ ] **Step 1: Add a `_render_flasher_upload_token` helper in `scripts/lib/render.sh`**

Inspect `scripts/lib/render.sh` for the existing `_render_agent_upload_token` (or similarly-named) helper. Mirror it for the flasher token. The helper:
1. Reads `secrets.flasher_upload_token` from `LDS_CONFIG` via `yq`.
2. If empty, dies with an actionable message.
3. Writes the value to `compose/flasher/upload_token` with `chmod 600`.

Add a call to this helper alongside the existing render-secrets entry points (the script that's invoked from `scripts/deploy.sh`).

For CI deployment: the deploy workflow (`.github/workflows/deploy.yml` or the release-please deploy step) injects `FLASHER_UPLOAD_TOKEN` from GH secrets into the rendering env. The render helper should prefer an `LDS_FLASHER_UPLOAD_TOKEN_FILE` env var (if set) over the yaml — matching how `LDS_AGENT_TOKEN_FILE` works for siteapp.

- [ ] **Step 2: Add a `rotate-flasher-upload-token` command in `scripts/secrets.sh`**

Open `scripts/secrets.sh`. Mirror `rotate-agent-upload-token`:
```bash
rotate-flasher-upload-token)
    new=$(openssl rand -hex 32)
    yq -i ".secrets.flasher_upload_token = \"$new\"" "$LDS_CONFIG"
    echo "Updated local config: secrets.flasher_upload_token"
    if command -v gh >/dev/null 2>&1; then
        printf '%s' "$new" | gh secret set FLASHER_UPLOAD_TOKEN
        echo "Mirrored to GH repo secret FLASHER_UPLOAD_TOKEN"
    else
        echo "(gh CLI not installed — set FLASHER_UPLOAD_TOKEN in GitHub Secrets manually)"
    fi
    echo "Run 'task deploy' to roll out."
    ;;
```

- [ ] **Step 3: Add `compose/flasher/.gitignore`**

Create `compose/flasher/.gitignore`:
```
upload_token
```

So rendered tokens never get committed.

- [ ] **Step 4: Add Taskfile entry**

Edit `Taskfile.yml`. Under the `# --- Secrets ---` section, after `secrets:rotate-agent-upload-token`, add:
```yaml
  "secrets:rotate-flasher-upload-token":
    desc: Generate a new bearer token for the flasher upload API; mirrors to GH repo secret
    cmd: bash scripts/secrets.sh rotate-flasher-upload-token
```

- [ ] **Step 5: Add `secrets.flasher_upload_token` placeholder to CI config template**

If `compose/config.ci.yaml.tmpl` (or the equivalent) has a top-level `secrets:` block, add `flasher_upload_token: ""` under it. The deploy workflow overrides this from the GH secret.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/render.sh scripts/secrets.sh Taskfile.yml compose/flasher/.gitignore compose/config.ci.yaml.tmpl
git commit -m "feat(secrets): rotate-flasher-upload-token; render-and-mount"
```

---

### Task 10.4: CI deploy workflow — inject `FLASHER_UPLOAD_TOKEN` from GH secret

**Files:**
- Modify: `.github/workflows/deploy.yml` (or `.github/workflows/release-please.yml` if deploy is a step within it)

- [ ] **Step 1: Inspect the workflow that performs deploy**

Look at `.github/workflows/` for the workflow that calls `scripts/deploy.sh`. It already plumbs `FLASHER_VERSION_FILE` and other secrets through the env. Mirror the agent-upload-token plumbing:

In the deploy job's `env:` block (or via `with:` for a reusable action), add:
```yaml
FLASHER_UPLOAD_TOKEN: ${{ secrets.FLASHER_UPLOAD_TOKEN }}
```

And in the step that calls `deploy.sh`, write the env value to a file first:
```yaml
- name: Render flasher upload token
  run: |
    mkdir -p tmp
    printf '%s' "$FLASHER_UPLOAD_TOKEN" > tmp/flasher_upload_token
    chmod 600 tmp/flasher_upload_token
    echo "LDS_FLASHER_UPLOAD_TOKEN_FILE=$PWD/tmp/flasher_upload_token" >> "$GITHUB_ENV"
  env:
    FLASHER_UPLOAD_TOKEN: ${{ secrets.FLASHER_UPLOAD_TOKEN }}
```

`scripts/lib/render.sh::_render_flasher_upload_token` reads `LDS_FLASHER_UPLOAD_TOKEN_FILE` and copies it to `compose/flasher/upload_token` before rsync.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): inject FLASHER_UPLOAD_TOKEN from GH secret"
```

---

### Task 10.5: e2e — extend test compose stack with `FLASHER_DATA_DIR` and bearer token

**Files:**
- Modify: `services/flasher/tests/e2e/compose.yaml`
- Modify: `services/flasher/tests/e2e/conftest.py`

- [ ] **Step 1: Update `compose.yaml`**

Open `services/flasher/tests/e2e/compose.yaml`. Add to the `flasher` service:
```yaml
environment:
  FLASHER_DATA_DIR: /var/lib/flasher
  FLASHER_UPLOAD_TOKEN: e2e-token
volumes:
  - flasher_data:/var/lib/flasher
```

And at the top level, declare the volume:
```yaml
volumes:
  flasher_data:
```

- [ ] **Step 2: Update `conftest.py`**

Add a `bearer_headers` fixture for tests that hit `/flash/api/v1/`:
```python
@pytest.fixture(scope="session")
def bearer_headers() -> dict:
    return {"Authorization": "Bearer e2e-token"}
```

- [ ] **Step 3: Commit**

```bash
git add services/flasher/tests/e2e/compose.yaml services/flasher/tests/e2e/conftest.py
git commit -m "test(flasher-e2e): mount flasher_data; bearer token in container env"
```

---

### Task 10.6: e2e — firmware library full lifecycle

**Files:**
- Create: `services/flasher/tests/e2e/test_firmware_lifecycle.py`

- [ ] **Step 1: Create the test**

Create `services/flasher/tests/e2e/test_firmware_lifecycle.py`:
```python
def test_create_get_patch_delete(http) -> None:
    r = http.post("/flash/api/firmware",
                  json={"name": "fw-1", "firmware": ":00000001FF\n"})
    assert r.status_code == 200
    fid = r.json()["id"]

    r = http.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200
    assert r.json()["name"] == "fw-1"

    r = http.patch(f"/flash/api/firmware/{fid}",
                   json={"name": "fw-1-renamed", "description": "d"})
    assert r.status_code == 200
    assert r.json()["name"] == "fw-1-renamed"

    r = http.delete(f"/flash/api/firmware/{fid}")
    assert r.status_code == 200

    r = http.get(f"/flash/api/firmware/{fid}")
    assert r.status_code == 404


def test_download_returns_bytes(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "fw-2", "firmware": ":00000001FF\n",
                          "original_filename": "fw-2.hex"}).json()["id"]
    r = http.get(f"/flash/api/firmware/{fid}/download")
    assert r.status_code == 200
    assert r.text == ":00000001FF\n"
    assert "fw-2.hex" in r.headers.get("content-disposition", "")
    http.delete(f"/flash/api/firmware/{fid}")


def test_tag_lifecycle(http) -> None:
    tid = http.post("/flash/api/tags", json={"name": "e2e-pump"}).json()["id"]
    fid = http.post("/flash/api/firmware",
                    json={"name": "f-with-tag", "firmware": ":00000001FF\n",
                          "tags": [tid]}).json()["id"]
    body = http.get(f"/flash/api/firmware/{fid}").json()
    assert [t["name"] for t in body["tags"]] == ["e2e-pump"]
    # Deleting the tag CASCADEs to firmware_tags but leaves the firmware row.
    http.delete(f"/flash/api/tags/{tid}")
    body = http.get(f"/flash/api/firmware/{fid}").json()
    assert body["tags"] == []
    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 2: Run**

From `services/flasher/`: `uv run pytest tests/e2e/test_firmware_lifecycle.py -v`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add services/flasher/tests/e2e/test_firmware_lifecycle.py
git commit -m "test(flasher-e2e): firmware library lifecycle"
```

---

### Task 10.7: e2e — flash from firmware record + flash from backup + promote + bulk delete + delete-while-running + replay-after-delete

**Files:**
- Create: `services/flasher/tests/e2e/test_flash_from_record.py`
- Create: `services/flasher/tests/e2e/test_flash_from_backup.py`
- Create: `services/flasher/tests/e2e/test_promote_backup.py`
- Create: `services/flasher/tests/e2e/test_bulk_delete_backups.py`
- Create: `services/flasher/tests/e2e/test_delete_refused_while_running.py`
- Create: `services/flasher/tests/e2e/test_replay_after_source_deletion.py`

- [ ] **Step 1: `test_flash_from_record.py`**

```python
from conftest import wait_for_terminal


def test_flash_from_firmware_record_writes_audit_row(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "boot", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    body = wait_for_terminal(http, job["job_id"])
    assert body["status"] == "done"
    # Logs page surfaces this row.
    r = http.get(f"/flash/api/flashes?client=khamit_desktop&limit=10")
    assert any(x["id"] == job["job_id"] for x in r.json()["items"])
    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 2: `test_flash_from_backup.py`**

```python
from conftest import wait_for_terminal


def test_flash_from_backup_source(http) -> None:
    # Seed a backup by first running a flash with default (success) outcome.
    fid = http.post("/flash/api/firmware",
                    json={"name": "seed", "firmware": ":00000001FF\n"}).json()["id"]
    first = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, first["job_id"])
    backup_id = http.get(f"/flash/api/flash/{first['job_id']}").json()["backup_id"]
    assert backup_id is not None

    # Flash from the captured backup.
    second = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "backup", "id": backup_id},
    }).json()
    body = wait_for_terminal(http, second["job_id"])
    assert body["status"] == "done"

    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 3: `test_promote_backup.py`**

```python
from conftest import wait_for_terminal


def test_promote_backup_to_firmware(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "src", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, job["job_id"])
    bid = http.get(f"/flash/api/flash/{job['job_id']}").json()["backup_id"]

    promoted = http.post(f"/flash/api/backups/{bid}/promote", json={
        "name": "promoted-fw",
    }).json()
    assert promoted["source_backup_id"] == bid
    assert promoted["sha256"]  # bytes were cloned

    http.delete(f"/flash/api/firmware/{promoted['id']}")
    http.delete(f"/flash/api/backups/{bid}")
    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 4: `test_bulk_delete_backups.py`**

```python
from conftest import wait_for_terminal


def test_bulk_delete_partial_outcomes(http) -> None:
    # Build two backups by flashing two different firmwares.
    fids = []
    bids = []
    for i in range(2):
        fid = http.post("/flash/api/firmware",
                        json={"name": f"bd-{i}", "firmware": f":000000{i:02d}FF\n"}).json()["id"]
        fids.append(fid)
        job = http.post("/flash/api/flash", json={
            "client": "khamit_desktop", "port": "COM3",
            "source": {"kind": "firmware", "id": fid},
        }).json()
        wait_for_terminal(http, job["job_id"])
        bids.append(http.get(f"/flash/api/flash/{job['job_id']}").json()["backup_id"])

    r = http.post("/flash/api/backups/bulk-delete",
                  json={"ids": [*bids, "no-such"]})
    body = r.json()
    assert body["deleted"] == 2
    assert any(x["id"] == "no-such" for x in body["refused"])

    for fid in fids: http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 5: `test_delete_refused_while_running.py`**

```python
import time


def test_delete_firmware_refused_during_in_flight_flash(http, set_stub_outcome) -> None:
    # Force a slow flash by switching the stub's outcome — we just need any row.
    # Schedule the flash and immediately attempt a delete; the stub typically
    # finishes in ~0.5s. If your stub completes faster than the test window,
    # increase its sleep via env override.
    fid = http.post("/flash/api/firmware",
                    json={"name": "race", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    # Polling: while status is running, delete should be refused with 409.
    refused = False
    for _ in range(30):
        s = http.get(f"/flash/api/flash/{job['job_id']}").json().get("status")
        if s == "running":
            r = http.delete(f"/flash/api/firmware/{fid}")
            if r.status_code == 409:
                refused = True
                break
        time.sleep(0.05)
    # Wait out the flash.
    for _ in range(60):
        s = http.get(f"/flash/api/flash/{job['job_id']}").json().get("status")
        if s in {"done", "error"}: break
        time.sleep(0.1)
    assert refused, "expected at least one 409 while the flash was running"
    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 6: `test_replay_after_source_deletion.py`**

```python
from conftest import wait_for_terminal


def test_replay_returns_410_after_source_deleted(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "ephemeral", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, job["job_id"])
    http.delete(f"/flash/api/firmware/{fid}")
    r = http.post(f"/flash/api/flashes/{job['job_id']}/replay", json={})
    assert r.status_code == 410
    assert r.json()["error"] == "source deleted"
```

- [ ] **Step 7: Run all the new e2e tests**

From `services/flasher/`: `uv run pytest tests/e2e/ -v`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add services/flasher/tests/e2e/test_flash_from_record.py services/flasher/tests/e2e/test_flash_from_backup.py services/flasher/tests/e2e/test_promote_backup.py services/flasher/tests/e2e/test_bulk_delete_backups.py services/flasher/tests/e2e/test_delete_refused_while_running.py services/flasher/tests/e2e/test_replay_after_source_deletion.py
git commit -m "test(flasher-e2e): library + history flows"
```

---

### Task 10.8: e2e — bearer upload happy path + 401s + sha256 idempotency

**Files:**
- Create: `services/flasher/tests/e2e/test_bearer_upload.py`

- [ ] **Step 1: Create the test**

```python
def test_bearer_post_succeeds(http, bearer_headers) -> None:
    r = http.post("/flash/api/v1/firmware",
                  json={"name": "ci-1", "firmware": ":00000001FF\n"},
                  headers=bearer_headers)
    assert r.status_code == 200
    fid = r.json()["id"]
    sha = r.json()["sha256"]
    # Idempotency probe finds it.
    r = http.get(f"/flash/api/v1/firmware?sha256={sha}", headers=bearer_headers)
    assert r.status_code == 200
    assert r.json()["id"] == fid
    http.delete(f"/flash/api/firmware/{fid}")


def test_bearer_missing_token_401(http) -> None:
    r = http.post("/flash/api/v1/firmware",
                  json={"name": "x", "firmware": ":00000001FF\n"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer required"


def test_bearer_wrong_token_401(http) -> None:
    r = http.post("/flash/api/v1/firmware",
                  json={"name": "x", "firmware": ":00000001FF\n"},
                  headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
    assert r.json()["error"] == "bearer invalid"
```

- [ ] **Step 2: Run and commit**

```bash
git add services/flasher/tests/e2e/test_bearer_upload.py
git commit -m "test(flasher-e2e): bearer upload + sha256 idempotency"
```

---

### Task 10.9: e2e — logs filters

**Files:**
- Create: `services/flasher/tests/e2e/test_logs_filters.py`

- [ ] **Step 1: Create the test**

```python
from conftest import wait_for_terminal


def test_logs_filter_by_client_and_outcome(http) -> None:
    fid = http.post("/flash/api/firmware",
                    json={"name": "logs", "firmware": ":00000001FF\n"}).json()["id"]
    job = http.post("/flash/api/flash", json={
        "client": "khamit_desktop", "port": "COM3",
        "source": {"kind": "firmware", "id": fid},
    }).json()
    wait_for_terminal(http, job["job_id"])

    r = http.get("/flash/api/flashes?client=khamit_desktop&outcome=success")
    body = r.json()
    assert any(x["id"] == job["job_id"] for x in body["items"])

    # A bogus client filters everything out.
    r = http.get("/flash/api/flashes?client=__no_such_client__")
    assert r.json()["items"] == []

    http.delete(f"/flash/api/firmware/{fid}")
```

- [ ] **Step 2: Run and commit**

```bash
git add services/flasher/tests/e2e/test_logs_filters.py
git commit -m "test(flasher-e2e): logs filters"
```

---

### Task 10.10: bats integration — bearer endpoint bypasses basic_auth

**Files:**
- Modify: `tests/integration/test_routes_smoke.bats`

- [ ] **Step 1: Append two cases**

Add at the bottom of `tests/integration/test_routes_smoke.bats`:

```bats
@test "/flash/api/v1/firmware reaches flasher without basic_auth (401, not 401-Basic)" {
    # No Authorization header: flasher rejects with `bearer required` (401).
    # If Caddy were still gating with basic_auth, we'd see a WWW-Authenticate Basic
    # header instead of a JSON error body. Check the body.
    body="$(docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -O - \"https://127.0.0.1/flash/api/v1/firmware?sha256=deadbeef\" 2>/dev/null
        '
    " || true)"
    # Either the bearer 401 with the expected JSON, or empty (wget eats 401 body).
    # Confirm Caddy did not intercept by curling and checking the header.
    headers="$(docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -S -O /dev/null \"https://127.0.0.1/flash/api/v1/firmware?sha256=deadbeef\" 2>&1
        '
    " || true)"
    # Caddy basic_auth issues WWW-Authenticate: Basic ...; flasher's 401 does not.
    [[ "$headers" != *"WWW-Authenticate: Basic"* ]] || { echo "$headers"; false; }
}

@test "/flash/ is still gated by basic_auth (the SPA path)" {
    headers="$(docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            wget --no-check-certificate -q -S -O /dev/null \"https://127.0.0.1/flash/\" 2>&1
        '
    " || true)"
    [[ "$headers" == *"WWW-Authenticate: Basic"* ]] || { echo "$headers"; false; }
}
```

- [ ] **Step 2: Run the bats suite**

`bats tests/integration/test_routes_smoke.bats`
Expected: all assertions pass; new cases observe the WWW-Authenticate header difference.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_routes_smoke.bats
git commit -m "test(integration): bearer endpoint reaches flasher without basic_auth"
```

---

### Task 10.11: Verify branch-protection check list is up to date

**Files:**
- None to change in code; this is a one-line check + a follow-up commit message.

- [ ] **Step 1: List the workflows that should be required**

From the project root:
```bash
ls .github/workflows
```

Per CLAUDE.md, branch protection's required-check list must include `pr-flasher / flasher`. After this implementation lands, the flasher workflow's e2e step grows (Phase 10 adds new tests), but the required-check name does not change — so no branch-protection change is needed. If a maintainer added new test cells (matrix entries) anywhere, update the protection list in lockstep. This task is the explicit "we checked" step.

- [ ] **Step 2: No code commit needed**

This is purely a verification task. If the team later adds new workflows whose names become load-bearing, update branch protection. Skip the commit step.

---

## Self-review notes (run by the plan author)

After the plan was drafted, the author ran the self-review checklist:

**Spec coverage:** Every requirement in `docs/superpowers/specs/2026-05-16-flasher-library-design.md` maps to at least one task in this plan:

- Firmware library (immutable bytes, editable labels, tags) → Tasks 3.1, 3.2, 8.1, 8.2
- Backup library (auto-save on flash, sha256 dedup, bulk delete, no soft-delete) → Tasks 4.1, 4.2, 5.2, 8.3
- Flash history (insert-at-start, immutable audit log, operator note) → Tasks 5.1, 5.2, 5.3
- Promote backup → firmware → Task 4.2 (`/promote` endpoint), Task 8.3 (modal)
- Flash from firmware or backup → Task 5.3 (`_resolve_source`), Task 9.2 (`FirmwareSourcePicker`)
- Re-flash from history → Task 5.3 (`/replay`), Task 8.4 (drawer Repeat button)
- Download/export → Tasks 3.2, 4.2 (`/download`), 7.2 (URL helpers)
- Tags + filter → Tasks 2.1, 3.3 (CRUD + routes), 8.1 (TagManager, TagChip), 8.2 (list filter)
- Operator note on flash row → Task 5.3 (`/note`), Task 8.4 (drawer note editor)
- Tabs (Flash/Firmware/Backups/Logs) → Tasks 7.3, 7.4, 8.2, 8.3, 8.4, 9.4
- Per-firmware and per-backup stats → Task 3.1 (`_row_to_dict` stats SQL), 4.1, 8.1 (StatsCard)
- Bearer CI endpoint with idempotency probe → Task 3.2 (`/api/v1/firmware`), 10.10 (bats verifies Caddy bypass)
- Logs filters (client/outcome/source/date) → Task 5.1 (`list_flashes`), 5.3 (route), 8.4 (`LogFilters`)
- Form always at top, no Done/Flash-another buttons → Task 9.3, 9.4
- Lab machine picker shows offline rows muted → Task 6.1 (API), 9.1 (component)
- No soft-delete; refuse during running flash → Tasks 3.1, 4.1 (DB layer), 3.2, 4.2 (routes)
- Migrations + on-boot interrupted sweep → Tasks 1.4, 1.5, 1.6
- Compose volume + Caddy ordering + secrets flow → Tasks 10.1, 10.2, 10.3, 10.4
- e2e coverage of every flow listed in spec's Testing section → Tasks 10.6 through 10.10

**Placeholder scan:** No "TBD", "TODO", "fill in" placeholders. Every step has the actual code or command an engineer needs.

**Type consistency:**
- `create_firmware` signature in `firmware.py` (Task 3.1) matches its callers in `routes/firmware.py` (Task 3.2), `routes/backups.py::promote` (Task 4.2), and the bearer post route (Task 3.2).
- `capture_or_reuse_backup` in `backups.py` (Task 4.1) is called from `flash.py::run_flash_job` (Task 5.2) with the same kw-args.
- `create_running_flash` in `flashes.py` (Task 5.1) is called from `routes/flashes.py::post_flash` (Task 5.3) with matching positional/keyword args.
- `set_terminal_done` / `set_terminal_error` (Task 5.1) are called from `flash.py` (Task 5.2) with matching kw-args.
- The frontend `FirmwareRecord`, `BackupRecord`, `FlashRowSummary`, `FlashRowDetail` types in `types.ts` (Task 7.1) match the JSON shapes the backend routes emit.

**Scope:** Cohesive — one plan, one running test suite at the end of each phase, one merged branch.

**Ambiguity:** None observed. Where the design left a discretionary detail (e.g., bearer-endpoint path being `/api/v1/...` vs `/api-v1/...`), the plan picks one and uses it consistently.

---

## Final aggregate run after Phase 10

Before declaring the implementation complete, the engineer runs the full suite end-to-end:

- [ ] `cd services/flasher && uv run pytest -v` — all unit tests pass.
- [ ] `cd services/flasher && uv run pytest tests/e2e/ -v` — all e2e tests pass.
- [ ] `cd services/flasher/web && npm run build` — frontend builds cleanly.
- [ ] `bats tests/integration/test_routes_smoke.bats` — bearer + basic_auth assertions pass.

If any step fails, fix the underlying issue (do not skip or `xfail` — those are red flags per the verification-before-completion skill) and re-run.

---

**Plan complete.**











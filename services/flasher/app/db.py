from __future__ import annotations

import re
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
        # PRAGMAs are non-transactional; no commit needed.
        yield conn
    finally:
        await conn.close()


_MIGRATION_RE = re.compile(r"^(\d+)_.+\.sql$")


async def migrate(db_path: Path, *, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Apply pending .sql migrations in numeric order.

    File naming: `NNNN_<slug>.sql` (any digit count, leading zeros OK). The
    numeric prefix is the migration's version. The first migration MUST
    create the `schema_version` table and INSERT a single row (any value)
    so subsequent migrations have somewhere to update.

    Idempotent: re-runs are no-ops once every file is applied. A failing
    migration leaves the schema_version unchanged and rolls back its DDL.

    Migration files MUST NOT contain semicolons except as statement
    terminators — no semicolons inside SQL comments, string literals, or
    trigger bodies. The runner splits on `;` and a stray semicolon will
    produce a misleading parse error.
    """
    files: list[tuple[int, Path]] = []
    for p in migrations_dir.glob("*.sql"):
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
            # Split SQL into individual statements (executescript issues an implicit
            # COMMIT before running, which defeats our BEGIN/ROLLBACK; running each
            # statement individually lets us control the transaction boundary).
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            try:
                await conn.execute("BEGIN")
                for stmt in statements:
                    await conn.execute(stmt)
                await conn.execute("UPDATE schema_version SET version = ?", (version,))
                if not has_table:
                    has_table = True
                await conn.commit()
                current = version
            except Exception:
                await conn.rollback()
                raise

        return current

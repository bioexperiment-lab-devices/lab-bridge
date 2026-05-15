# siteapp Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the `/admin/*` UI surface from siteapp, switch docs to a read-only repo-tracked `public_docs/` deployed by a new docs-only CI workflow, and sweep the stale references the admin removal leaves behind.

**Architecture:** Single squash-merge PR with 10 commits in dependency order. Commits 1-3 install the new docs path (mount + env + e2e wiring) without touching admin code, so the tree is always green. Commits 4-7 delete admin (code, Caddy block, deploy probe, e2e). Commits 8-10 finish READMEs, integration tests, and the new docs-deploy workflow.

**Tech Stack:** FastAPI (siteapp), Docker Compose, Caddy v2, release-please, GitHub Actions, pytest + httpx, bats.

**Reference spec:** `docs/superpowers/specs/2026-05-16-siteapp-simplification-design.md`

**Working directory:** Run all commands from the repo root (`/Users/khamitovdr/lab_devices_server`) unless a step states otherwise.

---

## Pre-flight

- [ ] **Pre-flight 1: confirm clean tree**

Run: `git status`
Expected: working tree clean, on `main`. If not, stop and resolve before proceeding.

- [ ] **Pre-flight 2: confirm dev tools available**

Run: `uv --version && docker --version && bats --version && yq --version`
Expected: all four print versions.

---

## Task 1: Move `default_docs/` → top-level `public_docs/`

**Files:**
- Move: `services/siteapp/app/default_docs/**` → `public_docs/**` (10 files: 6 `.md`, 4 `.svg`)
- Verify: no remaining `default_docs` references in code (`docs/` literal mentions in CHANGELOG/specs stay; those are historical).

**Why:** Step 1 of the spec's commit order. The directory move is a no-op semantically — `app/config.py:73-81` still seeds from this directory; we'll cut over in Task 2. Doing the move first keeps every later commit smaller.

- [ ] **Step 1: Verify current contents**

Run: `find services/siteapp/app/default_docs -type f | sort`
Expected output (10 files):
```
services/siteapp/app/default_docs/icons/github.svg
services/siteapp/app/default_docs/icons/grafana.svg
services/siteapp/app/default_docs/icons/jupyter.svg
services/siteapp/app/default_docs/icons/windows.svg
services/siteapp/app/default_docs/index.md
services/siteapp/app/default_docs/index.ru.md
services/siteapp/app/default_docs/system-overview.md
services/siteapp/app/default_docs/system-overview.ru.md
services/siteapp/app/default_docs/technical-overview.md
services/siteapp/app/default_docs/technical-overview.ru.md
```

- [ ] **Step 2: Move the tree using `git mv`**

Run:
```bash
mkdir -p public_docs
git mv services/siteapp/app/default_docs/* public_docs/
rmdir services/siteapp/app/default_docs
```

- [ ] **Step 3: Verify move**

Run: `find public_docs -type f | sort && test ! -e services/siteapp/app/default_docs`
Expected: same 10 files now under `public_docs/`. Last command exits 0.

- [ ] **Step 4: Update `app/config.py` to point seeding loop at `public_docs/` (transitional)**

The seeding loop in `services/siteapp/app/config.py:73` reads from `Path(__file__).parent / "default_docs"`. Update it to read from a path we can pass in via env (since `public_docs/` lives outside the image). For this commit only, point at the runtime repo location — `Path("/repo/public_docs")` — using an env var with a fallback. **However, the simpler approach for this transitional commit is to skip seeding when the source dir is missing** (which is now true in the image, since we just deleted it).

Replace `config.py` lines 73-81 with:

```python
    # Seed default_docs/ so the public /docs/ landing page returns 200
    # and any assets referenced by the seeded index (icons, etc.) resolve.
    # Per-file gating: each default file is copied iff its destination
    # is missing — so an operator who has authored their own index.md or
    # edited an icon is never overwritten, and a deleted file gets
    # re-seeded on next boot (matching today's behavior for index.md).
    default_dir = Path(__file__).parent / "default_docs"
    if default_dir.is_dir():
        for src in default_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(default_dir)
                dst = site_data / "docs" / rel
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(src.read_bytes())
```

The `default_dir.is_dir()` guard is already present, so after the move the loop becomes a no-op at runtime. **No code change needed for this commit** — the guard handles it.

- [ ] **Step 5: Update the in-test seeding expectations**

`services/siteapp/tests/test_config.py` has three tests that rely on the seed: `test_seeds_default_index_when_missing`, `test_does_not_overwrite_existing_index`, `test_seeds_default_icons_when_missing`. They'll all fail after the move because there's no longer a `default_docs/` directory next to `config.py`.

These tests are obsolete and will be deleted in Task 5 (admin removal). For this commit, **mark them xfail** so the green tree assertion holds:

Edit `services/siteapp/tests/test_config.py`, add at the top of each of those three test functions:

```python
import pytest
pytest.skip("default_docs/ moved to public_docs/; seeding behaviour removed in subsequent commit", allow_module_level=False)
```

Use a single `import pytest` at the top of the file (it's already imported). For each test, add as its first line:

```python
def test_seeds_default_index_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.skip("default_docs/ moved to public_docs/; seeding behaviour removed in next commit")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    ...
```

Same for `test_does_not_overwrite_existing_index` and `test_seeds_default_icons_when_missing`.

- [ ] **Step 6: Similarly skip `test_default_index_smoke` in `test_routes_docs.py`**

`services/siteapp/tests/test_routes_docs.py:125` (`test_default_index_smoke`) relies on the seed. Add as its first line after the docstring:

```python
def test_default_index_smoke(tmp_path: Path, monkeypatch) -> None:
    """The shipped default_docs/index.md must render with all four
    extensions active: alert div, mermaid pre, sanitized <img>, and
    a working /docs/icons/jupyter.svg URL."""
    pytest.skip("default_docs/ moved to public_docs/; seeding behaviour removed in next commit")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    ...
```

(Note: `pytest` is already imported in this file at line 5.)

- [ ] **Step 7: Run unit tests**

Run: `cd services/siteapp && uv run pytest -x -q`
Expected: all tests pass (the 4 skipped tests show as `s`).

- [ ] **Step 8: Commit**

```bash
cd /Users/khamitovdr/lab_devices_server
git add public_docs/ services/siteapp/app/default_docs services/siteapp/tests/test_config.py services/siteapp/tests/test_routes_docs.py
git status   # sanity check what's staged
git commit -m "$(cat <<'EOF'
feat: move siteapp default_docs/ to top-level public_docs/

First step toward docs-as-code: relocate the in-image seed corpus to a
repo-level public_docs/ directory so it can be deployed by CI on push
to main without rebuilding the siteapp image.

This commit is a pure file move plus skip-markers on the four tests
that exercise the seeding loop; the loop itself is unchanged and
becomes a no-op at runtime because its source directory no longer
exists inside the image. Next commit removes the loop entirely and
switches Settings.docs_root to read from SITEAPP_DOCS_DIR.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Switch `Settings.docs_root` to `SITEAPP_DOCS_DIR`

**Files:**
- Modify: `services/siteapp/app/config.py`
- Modify: `services/siteapp/tests/conftest.py`
- Modify: `services/siteapp/tests/test_config.py`
- Modify: `services/siteapp/tests/test_routes_docs.py`

**Why:** Spec §2.2 — read docs root from a new env var, delete the seeding loop, delete the `csrf_secret` field. The `SITE_DATA` mount continues to host the agent binary only.

- [ ] **Step 1: Write failing test for new env var requirement**

Add to `services/siteapp/tests/test_config.py` (append to the end of the file):

```python
def test_docs_dir_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.delenv("SITEAPP_DOCS_DIR", raising=False)
    with pytest.raises(RuntimeError, match="SITEAPP_DOCS_DIR"):
        load_settings()


def test_docs_dir_stored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docs = tmp_path / "srv-docs"
    docs.mkdir()
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(docs))
    settings = load_settings()
    assert settings.docs_root == docs


def test_docs_dir_must_exist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "tok")
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(tmp_path / "does-not-exist"))
    with pytest.raises(RuntimeError, match="SITEAPP_DOCS_DIR"):
        load_settings()
```

- [ ] **Step 2: Run the new tests — expect FAIL**

Run: `cd services/siteapp && uv run pytest tests/test_config.py::test_docs_dir_required tests/test_config.py::test_docs_dir_stored tests/test_config.py::test_docs_dir_must_exist -v`
Expected: 3 FAILs.

- [ ] **Step 3: Rewrite `app/config.py` to satisfy the new contract**

Replace the entire body of `services/siteapp/app/config.py` with:

```python
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    site_data: Path
    agent_upload_token: str
    clients_file: Path
    chisel_listen_port: int
    docs_root: Path
    version: str = "dev"
    git_sha: str = "unknown"

    @property
    def agent_root(self) -> Path:
        return self.site_data / "agent"


def load_settings() -> Settings:
    data = os.environ.get("SITE_DATA")
    if not data:
        raise RuntimeError("SITE_DATA env var is required")
    site_data = Path(data).resolve()
    (site_data / "agent" / "windows").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / ".tmp").mkdir(parents=True, exist_ok=True)

    docs_env = os.environ.get("SITEAPP_DOCS_DIR")
    if not docs_env:
        raise RuntimeError("SITEAPP_DOCS_DIR env var is required")
    docs_root = Path(docs_env)
    if not docs_root.is_dir():
        raise RuntimeError(
            f"SITEAPP_DOCS_DIR must point to an existing directory; got: {docs_root}"
        )

    clients_env = os.environ.get("SITEAPP_CLIENTS_FILE")
    if not clients_env:
        raise RuntimeError("SITEAPP_CLIENTS_FILE env var is required")
    # Not .resolve()'d — this is a reference to an externally-mounted file,
    # not a data root we own. The route reads it on each request.
    clients_file = Path(clients_env)

    port_env = os.environ.get("SITEAPP_CHISEL_LISTEN_PORT")
    if not port_env:
        raise RuntimeError("SITEAPP_CHISEL_LISTEN_PORT env var is required")
    # int() raises ValueError on garbage like "abc"; surface as a boot crash —
    # a misrendered template should never produce a "port 0" runtime fallback.
    chisel_listen_port = int(port_env)

    token_file = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN__FILE")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    else:
        token = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN", "").strip()
    if not token:
        # Local-dev convenience: synthesize a per-process token so the app boots.
        token = secrets.token_urlsafe(32)

    version = os.environ.get("LAB_BRIDGE_VERSION", "dev").strip() or "dev"
    git_sha = os.environ.get("LAB_BRIDGE_GIT_SHA", "unknown").strip() or "unknown"

    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        clients_file=clients_file,
        chisel_listen_port=chisel_listen_port,
        docs_root=docs_root,
        version=version,
        git_sha=git_sha,
    )
```

Notes on the rewrite:
- `docs_root` becomes a constructor arg, not a property. `agent_root` stays a property over `site_data`.
- The seeding loop is deleted.
- `csrf_secret` field + env read, `max_upload_mb_doc`, and `max_upload_mb_agent` are deleted. The `max_upload_*` fields were never read by any caller (`api.py` uses a local `MAX_AGENT_BYTES` literal; `admin.py` used `MAX_DOC_BYTES` similarly).
- `(site_data / "docs").mkdir(...)` is deleted (we no longer manage that directory).

- [ ] **Step 4: Add autouse fixture for `SITEAPP_DOCS_DIR` to `tests/conftest.py`**

Modify `services/siteapp/tests/conftest.py`. Replace the entire file with:

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def site_data(tmp_path: Path) -> Path:
    """Fresh, empty site_data/ tree for a single test."""
    (tmp_path / "agent" / "windows").mkdir(parents=True)
    return tmp_path


@pytest.fixture(autouse=True)
def _docs_dir_default(tmp_path: Path, monkeypatch) -> Path:
    """Set SITEAPP_DOCS_DIR to a fresh empty docs root for every test.

    Tests that need actual doc content can write into the returned path
    or override the env var explicitly. Tests asserting the env var is
    *absent* (e.g. test_docs_dir_required) must call
    ``monkeypatch.delenv("SITEAPP_DOCS_DIR", raising=False)`` themselves.
    """
    p = tmp_path / "docs-root"
    p.mkdir()
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(p))
    return p


@pytest.fixture(autouse=True)
def _clients_file_default(tmp_path: Path, monkeypatch) -> Path:
    """Set SITEAPP_CLIENTS_FILE to a fresh empty roster for every test."""
    p = tmp_path / "clients.json"
    p.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SITEAPP_CLIENTS_FILE", str(p))
    return p


@pytest.fixture(autouse=True)
def _chisel_listen_port_default(monkeypatch) -> int:
    """Set SITEAPP_CHISEL_LISTEN_PORT to a fixed test value."""
    monkeypatch.setenv("SITEAPP_CHISEL_LISTEN_PORT", "8080")
    return 8080
```

The old `site_data` fixture created `docs/` under tmp_path; that's no longer the docs source, so we drop that mkdir.

- [ ] **Step 5: Delete the now-stale seed-related tests from `tests/test_config.py`**

Delete these three test functions entirely (they have `pytest.skip()` markers from Task 1):
- `test_seeds_default_index_when_missing`
- `test_does_not_overwrite_existing_index`
- `test_seeds_default_icons_when_missing`

Also update `test_creates_subdirs` — it currently asserts `(s.site_data / "docs").is_dir()` which is no longer the contract. Rewrite it as:

```python
def test_creates_subdirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    s = load_settings()
    assert (s.site_data / "agent" / "windows").is_dir()
    assert isinstance(s, Settings)
```

- [ ] **Step 6: Update `tests/test_routes_docs.py` fixture to write docs under the new path**

Replace the `client` fixture in `services/siteapp/tests/test_routes_docs.py` with:

```python
@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    docs = tmp_path / "docs-root"
    # _docs_dir_default (conftest autouse) already created docs and set
    # SITEAPP_DOCS_DIR=tmp_path/docs-root for us; we just populate it.
    (docs / "index.md").write_text("# Home\n\nWelcome\n", encoding="utf-8")
    (docs / "intro.md").write_text("# Intro\n\nhello world\n", encoding="utf-8")
    (docs / "intro.ru.md").write_text("# Введение\n\nпривет\n", encoding="utf-8")
    (docs / "diagram.md").write_text(
        "# Diagram\n\n```mermaid\nflowchart LR\n  A --> B\n```\n",
        encoding="utf-8",
    )
    section = docs / "section"
    section.mkdir()
    (section / "index.md").write_text("# Section\n", encoding="utf-8")
    (section / "page.md").write_text("# Page\n", encoding="utf-8")
    icons = docs / "icons"
    icons.mkdir()
    (icons / "jupyter.svg").write_bytes(
        b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
        b'width="28" height="28"><circle r="14" cx="14" cy="14" fill="orange"/></svg>'
    )
    (icons / "secret.exe").write_bytes(b"MZ\x90\x00")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)
```

Then update `test_orphan_ru_only_returns_404`:

```python
def test_orphan_ru_only_returns_404(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs-root" / "only.ru.md").write_text("# Только\n", encoding="utf-8")
    assert client.get("/docs/only").status_code == 404
```

And delete `test_default_index_smoke` entirely — it depended on the seed; the e2e suite covers the equivalent (rendering the actual `public_docs/` content) via the docker mount.

- [ ] **Step 7: Run all siteapp unit tests**

Run: `cd services/siteapp && uv run pytest -x -q`
Expected: all pass (no skips this time).

- [ ] **Step 8: Commit**

```bash
cd /Users/khamitovdr/lab_devices_server
git add services/siteapp/app/config.py services/siteapp/tests/conftest.py services/siteapp/tests/test_config.py services/siteapp/tests/test_routes_docs.py
git status
git commit -m "$(cat <<'EOF'
feat(siteapp): read docs from SITEAPP_DOCS_DIR

Settings.docs_root now reads from a new SITEAPP_DOCS_DIR env var instead
of being derived from SITE_DATA. The default-docs seeding loop is gone;
the source of truth is now the mounted directory.

SITE_DATA continues to host the writable agent binary at /data/agent/.
csrf_secret and max_upload_mb_doc fields removed (admin-only) ahead of
the admin removal in a later commit.

Unit-test fixtures updated: conftest sets SITEAPP_DOCS_DIR to a tmp dir
for every test; tests that intentionally check the env var being absent
delenv it themselves. The four obsolete seed tests are removed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Wire `SITEAPP_DOCS_DIR` through compose + e2e harness

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Modify: `services/siteapp/tests/e2e/compose.yaml`
- Modify: `services/siteapp/tests/e2e/conftest.py`
- Modify: `services/siteapp/tests/e2e/fixtures/` (add a docs subdir)

**Why:** Spec §2.3, §3.7. The container needs the new env var + mount; the e2e harness needs to mount a fixture docs corpus so all e2e tests (including the rewritten safety test) run against real files.

- [ ] **Step 1: Add `SITEAPP_DOCS_DIR` + docs mount to `compose/docker-compose.yml.tmpl`**

Edit `compose/docker-compose.yml.tmpl`. Find the `siteapp:` service block (around line 70). The env block currently looks like:

```yaml
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_CHISEL_LISTEN_PORT: __CHISEL_LISTEN_PORT__
```

Change it to:

```yaml
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_CHISEL_LISTEN_PORT: __CHISEL_LISTEN_PORT__
      SITEAPP_DOCS_DIR: /srv/docs
```

The volumes block currently looks like:

```yaml
    volumes:
      - ./site_data:/data
      - ./siteapp/clients.json:/etc/siteapp/clients.json:ro
```

Change it to:

```yaml
    volumes:
      - ./site_data:/data
      - ./siteapp/clients.json:/etc/siteapp/clients.json:ro
      - ./siteapp/docs:/srv/docs:ro
```

- [ ] **Step 2: Create a docs fixture corpus for the e2e harness**

The e2e harness mounts a fixture clients.json; do the same for docs. Create the fixture directory and a minimal-but-realistic corpus:

```bash
mkdir -p services/siteapp/tests/e2e/fixtures/docs/icons
```

Write `services/siteapp/tests/e2e/fixtures/docs/index.md`:

```markdown
# Test landing

This is the e2e fixture landing page.
```

Write `services/siteapp/tests/e2e/fixtures/docs/intro.md`:

```markdown
# Intro

hello world

![icon](icons/jupyter.svg)
```

Write `services/siteapp/tests/e2e/fixtures/docs/xss-test.md` (the safety test will render this):

```markdown
# XSS Test

<script>alert('xss')</script>

End of test.
```

Write `services/siteapp/tests/e2e/fixtures/docs/icons/jupyter.svg`:

```xml
<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="28" height="28"><circle r="14" cx="14" cy="14" fill="orange"/></svg>
```

- [ ] **Step 3: Update e2e compose to mount the fixture docs + set the env var**

Edit `services/siteapp/tests/e2e/compose.yaml`. The `environment:` block currently has:

```yaml
    environment:
      LAB_BRIDGE_VERSION: "e2e-test"
      LAB_BRIDGE_GIT_SHA: "test"
      SITEAPP_CHISEL_LISTEN_PORT: "7000"
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITE_DATA: /data
```

Add `SITEAPP_DOCS_DIR`:

```yaml
    environment:
      LAB_BRIDGE_VERSION: "e2e-test"
      LAB_BRIDGE_GIT_SHA: "test"
      SITEAPP_CHISEL_LISTEN_PORT: "7000"
      SITEAPP_CLIENTS_FILE: /etc/siteapp/clients.json
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
      SITEAPP_DOCS_DIR: /srv/docs
      SITE_DATA: /data
```

The `volumes:` block currently has:

```yaml
    volumes:
      - ./fixtures/clients.json:/etc/siteapp/clients.json:ro
      - ./fixtures/agent_upload_token:/run/secrets/agent_upload_token:ro
      - siteapp_data:/data
```

Add the docs mount:

```yaml
    volumes:
      - ./fixtures/clients.json:/etc/siteapp/clients.json:ro
      - ./fixtures/agent_upload_token:/run/secrets/agent_upload_token:ro
      - ./fixtures/docs:/srv/docs:ro
      - siteapp_data:/data
```

- [ ] **Step 4: Build the siteapp e2e image locally**

Run: `docker build -t lab-bridge-siteapp:e2e services/siteapp`
Expected: build succeeds.

- [ ] **Step 5: Run the existing e2e tests** (these should all pass; `test_admin_upload.py` will fail — that's covered in Task 5)

Run: `cd services/siteapp && uv run pytest tests/e2e/test_health.py tests/e2e/test_public_clients.py tests/e2e/test_server_info.py -v`
Expected: all pass. Container boots cleanly with the new env var + mount.

If health/public/server-info pass, the new wiring works. We don't run `test_safety.py` (uses /admin routes) or `test_admin_upload.py` until Task 6 rewrites them.

- [ ] **Step 6: Commit**

```bash
cd /Users/khamitovdr/lab_devices_server
git add compose/docker-compose.yml.tmpl services/siteapp/tests/e2e/compose.yaml services/siteapp/tests/e2e/fixtures/docs/
git status
git commit -m "$(cat <<'EOF'
feat: mount SITEAPP_DOCS_DIR=/srv/docs in compose + e2e harness

compose/docker-compose.yml.tmpl: wires SITEAPP_DOCS_DIR=/srv/docs and
bind-mounts ./siteapp/docs:/srv/docs:ro on the siteapp service.

services/siteapp/tests/e2e/: adds a fixture docs corpus (index, intro
with an icon, an xss-test page, one SVG) mounted into /srv/docs for the
e2e harness so existing and forthcoming e2e tests can hit real markdown.

Deploy plumbing for the host-side ./siteapp/docs path lands in the next
commit; the e2e harness already supplies a docs corpus via its own
fixtures path, so this commit's tree is green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Stage `public_docs/` into `$stage/siteapp/docs/` in `deploy.sh`

**Files:**
- Modify: `scripts/deploy.sh`

**Why:** Spec §2.4. The existing rsync already ships `$stage/` → `~/lab-bridge/` on the VPS, so all we need is a `cp -R public_docs/. $stage/siteapp/docs/` line before the rsync step. The compose mount added in Task 3 will resolve `./siteapp/docs` to the rsync target on the VPS.

- [ ] **Step 1: Add the docs staging step**

Edit `scripts/deploy.sh`. Find the block (around line 62-63) that ends with:

```bash
    install -m 644 "$tokfile" "$stage/siteapp/agent_upload_token"
```

After that line and the blank line that follows, add:

```bash
    # Public docs — tracked in git at repo root, copied into the staged
    # tree so the existing rsync ships them to ~/lab-bridge/siteapp/docs/
    # on the VPS, where compose mounts them read-only at /srv/docs.
    mkdir -p "$stage/siteapp/docs"
    cp -R "$REPO_ROOT/public_docs/." "$stage/siteapp/docs/"
```

- [ ] **Step 2: Smoke-test the staging step**

Run from repo root:

```bash
mkdir -p /tmp/lds-stage-test/siteapp
cp -R public_docs/. /tmp/lds-stage-test/siteapp/docs/
find /tmp/lds-stage-test -type f | sort
rm -rf /tmp/lds-stage-test
```

Expected: lists the same 10 files as `find public_docs -type f`, under `/tmp/lds-stage-test/siteapp/docs/`.

- [ ] **Step 3: Run shellcheck on deploy.sh**

Run: `shellcheck scripts/deploy.sh`
Expected: no new warnings vs. pre-edit output. (If shellcheck isn't installed, skip — bats tests will catch syntax errors.)

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "$(cat <<'EOF'
feat(deploy): stage public_docs/ into siteapp/docs/ for rsync

The existing rsync already ships $stage/ to ~/lab-bridge/ on the VPS;
adding a recursive copy of public_docs/ into $stage/siteapp/docs/ lets
the new ./siteapp/docs:/srv/docs:ro compose mount resolve on first
deploy. Mirrors how clients.json and agent_upload_token already flow
under $stage/siteapp/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Delete admin code, templates, tests, and dependencies

**Files:**
- Delete: `services/siteapp/app/admin.py`
- Delete: `services/siteapp/app/templates/admin/` (whole subtree)
- Delete: `services/siteapp/tests/test_routes_admin.py`
- Delete: `services/siteapp/tests/e2e/test_admin_upload.py`
- Delete: `services/siteapp/agent_upload_token.example`
- Modify: `services/siteapp/app/main.py`
- Modify: `services/siteapp/app/paths.py`
- Modify: `services/siteapp/tests/test_paths.py`
- Modify: `services/siteapp/pyproject.toml`
- Regenerate: `services/siteapp/uv.lock`

**Why:** Spec §3.1, §3.2. Drop the entire `/admin/*` surface and its dependencies. `sanitize_filename` becomes dead code (only admin called it); `itsdangerous` becomes unused.

- [ ] **Step 1: Delete admin source + templates + tests**

```bash
git rm services/siteapp/app/admin.py
git rm -r services/siteapp/app/templates/admin
git rm services/siteapp/tests/test_routes_admin.py
git rm services/siteapp/tests/e2e/test_admin_upload.py
git rm services/siteapp/agent_upload_token.example
```

- [ ] **Step 2: Drop the admin router from `main.py`**

Edit `services/siteapp/app/main.py`. Current content:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin import make_router as make_admin_router
from app.agent import make_router as make_agent_router
from app.api import make_router as make_api_router
from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.public_clients import make_router as make_public_clients_router
from app.server_info import make_router as make_server_info_router
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_docs_router(settings))
app.include_router(make_agent_router(settings))
app.include_router(make_api_router(settings))
app.include_router(make_admin_router(settings))
app.include_router(make_public_clients_router(settings))
app.include_router(make_server_info_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

Delete the `make_admin_router` import line and the `app.include_router(make_admin_router(settings))` call. Final file:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent import make_router as make_agent_router
from app.api import make_router as make_api_router
from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.public_clients import make_router as make_public_clients_router
from app.server_info import make_router as make_server_info_router
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_docs_router(settings))
app.include_router(make_agent_router(settings))
app.include_router(make_api_router(settings))
app.include_router(make_public_clients_router(settings))
app.include_router(make_server_info_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 3: Drop `sanitize_filename` from `paths.py`**

Edit `services/siteapp/app/paths.py`. Replace the entire file with:

```python
from __future__ import annotations

from pathlib import Path


def safe_join(base: Path, *parts: str) -> Path:
    """Join `parts` under `base` and verify the result is inside `base`.

    Resolves symlinks. Raises ValueError on any escape attempt.
    """
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError as e:
        raise ValueError(f"path escapes base: {target} not under {base_resolved}") from e
    return target
```

The `re`-based helpers (`_VALID`, `_COLLAPSE`, `MAX_LEN`, `sanitize_filename`) are gone.

- [ ] **Step 4: Drop `sanitize_filename` tests from `test_paths.py`**

Edit `services/siteapp/tests/test_paths.py`. Replace the entire file with:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import safe_join


class TestSafeJoin:
    def test_simple(self, tmp_path: Path) -> None:
        result = safe_join(tmp_path, "docs", "intro.md")
        assert result == (tmp_path / "docs" / "intro.md").resolve()

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            safe_join(tmp_path, "..", "etc", "passwd")

    def test_rejects_absolute(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            safe_join(tmp_path, "/etc/passwd")

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape-target"
        outside.mkdir(exist_ok=True)
        link = tmp_path / "link"
        link.symlink_to(outside)
        with pytest.raises(ValueError):
            safe_join(tmp_path, "link", "secret.txt")
```

- [ ] **Step 5: Drop `itsdangerous` from `pyproject.toml`**

Edit `services/siteapp/pyproject.toml`. The `dependencies` block currently has:

```toml
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "jinja2>=3.1,<4",
    "markdown-it-py[linkify]>=3.0,<4",
    "mdit-py-plugins>=0.4,<0.5",
    "pygments>=2.18,<3",
    "python-multipart>=0.0.9,<0.1",
    "itsdangerous>=2.2,<3",
    "bleach>=6,<7",
    "httpx>=0.27,<0.29",
]
```

Delete the `"itsdangerous>=2.2,<3",` line. Final:

```toml
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "jinja2>=3.1,<4",
    "markdown-it-py[linkify]>=3.0,<4",
    "mdit-py-plugins>=0.4,<0.5",
    "pygments>=2.18,<3",
    "python-multipart>=0.0.9,<0.1",
    "bleach>=6,<7",
    "httpx>=0.27,<0.29",
]
```

- [ ] **Step 6: Regenerate `uv.lock`**

Run: `cd services/siteapp && uv lock`
Expected: `uv.lock` updates, `itsdangerous` entries removed.

- [ ] **Step 7: Run unit tests + e2e tests still in scope**

Run: `cd services/siteapp && uv run pytest -x -q`
Expected: all pass.

Then rebuild and run e2e (still skipping the safety test, rewritten in Task 6):

```bash
docker build -t lab-bridge-siteapp:e2e services/siteapp
cd services/siteapp && uv run pytest tests/e2e/test_health.py tests/e2e/test_public_clients.py tests/e2e/test_server_info.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/khamitovdr/lab_devices_server
git add services/siteapp/
git status
git commit -m "$(cat <<'EOF'
refactor(siteapp): remove /admin UI surface

Drops the /admin/* router (docs file manager + agent admin + rotate-
token), its Jinja templates, CSRF infrastructure, and the itsdangerous
dependency. Agent uploads continue to flow through the bearer-auth
/api/agent/upload route used by SerialHop CI; docs are served from
the read-only public_docs/ mount wired in earlier commits.

sanitize_filename was only used by admin upload code; deleted along
with its tests. safe_join stays — docs.py and translations.py use it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Rewrite `test_safety.py` for the static fixture corpus

**Files:**
- Modify: `services/siteapp/tests/e2e/test_safety.py`

**Why:** Spec §3.7. The old file tested path-traversal on admin upload (gone) and XSS escape on rendered markdown (stays). Retarget (b) to the static fixture; delete (a) entirely.

- [ ] **Step 1: Replace the file**

Replace the contents of `services/siteapp/tests/e2e/test_safety.py` with:

```python
"""HTML-escape on rendered markdown.

The siteapp markdown renderer must strip raw <script> tags from rendered
documents (defence-in-depth even though public_docs/ is now repo-tracked).
This test renders the xss-test.md fixture and asserts the script tag
does not appear in the rendered HTML.
"""

from __future__ import annotations


def test_rendered_markdown_strips_script_tag(http) -> None:
    rendered = http.get("/docs/xss-test")
    assert rendered.status_code == 200
    body = rendered.text
    # The raw <script> must be absent — bleach strips it entirely (strip=True).
    assert "<script>" not in body, "raw <script> tag leaked into rendered HTML"
```

The fixture `xss-test.md` was added in Task 3 Step 2.

- [ ] **Step 2: Run the rewritten safety test**

Run: `cd services/siteapp && uv run pytest tests/e2e/test_safety.py -v`
Expected: PASS.

- [ ] **Step 3: Run the full e2e suite to confirm nothing else regressed**

Run: `cd services/siteapp && uv run pytest tests/e2e/ -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add services/siteapp/tests/e2e/test_safety.py
git commit -m "$(cat <<'EOF'
test(siteapp): refocus safety e2e on render-time escape

The admin path-traversal portion of test_safety.py is gone with the
admin UI. The XSS-escape portion is retargeted to the static
xss-test.md fixture under tests/e2e/fixtures/docs/, so the test now
exercises the same property (rendered markdown strips raw <script>)
without going through any upload route.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Drop `/admin/*` from Caddy + deploy probe + secrets prompt

**Files:**
- Modify: `compose/Caddyfile.tmpl`
- Modify: `scripts/deploy.sh`
- Modify: `scripts/secrets.sh`

**Why:** Spec §3.3, §3.4, §3.5. The Caddy block routing `/admin/*` to siteapp is dead weight once the routes return 404. The deploy probe that asserts `/admin/` returns 401 must drop too — otherwise post-deploy health-check times out. The basic_auth hash itself stays in render.sh (flasher uses it); only the wording in secrets.sh updates.

- [ ] **Step 1: Delete the `/admin/*` block from `Caddyfile.tmpl`**

Edit `compose/Caddyfile.tmpl`. The block currently at lines 32-40 reads:

```
    # Admin panel — basic_auth scoped here ONLY. Mobile-WS issue does not
    # apply: this surface is plain HTTP file uploads, no kernels.
    handle /admin* {
        basic_auth {
            admin __ADMIN_BCRYPT_HASH__
        }
        reverse_proxy siteapp:8000
    }
```

Delete the block, including its leading comment. The `/flash*` block immediately below stays (mobile-WS comment used to apply to both; trim it down). Verify the surrounding context — the line immediately above and below the delete:

Before:
```
    handle /docs* {
        reverse_proxy siteapp:8000
    }
    ...etc...
    handle /admin* {
        basic_auth { admin __ADMIN_BCRYPT_HASH__ }
        reverse_proxy siteapp:8000
    }

    # Flasher service — operator firmware-flashing UI. Same single-admin
    # basic_auth boundary as /admin/*; the flasher itself trusts whoever
    # Caddy let through.
    handle /flash* {
```

After:
```
    handle /docs* {
        reverse_proxy siteapp:8000
    }
    ...etc...

    # Flasher service — operator firmware-flashing UI. Caddy basic_auth
    # is the single trust boundary; the flasher itself trusts whoever
    # Caddy let through.
    handle /flash* {
```

(Also update the flasher block's comment to drop the `/admin/*` reference, as shown.)

- [ ] **Step 2: Drop the `/admin/` probe from `scripts/deploy.sh`**

Edit `scripts/deploy.sh`. Around lines 114-152. Remove:
- `admin_status` from the `local` declaration on line 116.
- The `admin_status="$(curl ...)"` line (line 122).
- The `&& [[ "$admin_status" == "401" ]]` condition (line 142).
- The `admin $admin_status,` substring in the log line (line 147).
- The `admin:$admin_status` substring in the warn line (line 152).
- The comment line 137 (`# /admin/ MUST be 401 without creds. A 200 here is a security regression.`).

The post-edit block should look like:

```bash
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond..."
        local i jupyter_status grafana_status docs_status download_status flash_status static_status public_status server_info_status
        for ((i=0; i<60; i++)); do
            jupyter_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            grafana_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/grafana/login" || true)"
            docs_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/docs/" || true)"
            download_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/download/agent" || true)"
            flash_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/flash/" || true)"
            # /_static/site.css must reach siteapp (not the jupyter catchall) or
            # every siteapp page renders unstyled. Probe one known asset.
            static_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/_static/site.css" || true)"
            # /api/public/health is unauthenticated and always returns 200; a
            # non-200 means Caddy's /api/public* handle is misconfigured or
            # siteapp didn't restart cleanly. Confirms the new public surface
            # is wired before we declare the deploy successful.
            public_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/api/public/health" || true)"
            # /api/public/server-info publishes the chisel listen port + loki/tunnel
            # topology. A non-200 means SITEAPP_CHISEL_LISTEN_PORT didn't reach
            # siteapp or the router wasn't mounted. Probed alongside /api/public/health
            # so a broken render fails the deploy.
            server_info_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/api/public/server-info" || true)"
            if [[ "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "200" ]] \
                && [[ "$docs_status" == "200" ]] \
                && [[ "$download_status" == "200" ]] \
                && [[ "$flash_status" == "401" ]] \
                && [[ "$static_status" == "200" ]] \
                && [[ "$public_status" == "200" ]] \
                && [[ "$server_info_status" == "200" ]]; then
                log "deployed: jupyter $jupyter_status, grafana $grafana_status, docs $docs_status, download $download_status, flash $flash_status, static $static_status, public $public_status, server_info $server_info_status"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (jupyter:$jupyter_status grafana:$grafana_status docs:$docs_status download:$download_status flash:$flash_status static:$static_status public:$public_status server_info:$server_info_status). Check: task logs"
        return 1
    fi
    log "deployed (healthcheck skipped)"
}
```

- [ ] **Step 3: Update the secrets.sh prompt copy**

Edit `scripts/secrets.sh`. Line 69 currently:

```bash
    pw="$(prompt_password "Admin panel password (used at /admin/*)")"
```

Change to:

```bash
    pw="$(prompt_password "Operator password (used at /flash/*)")"
```

- [ ] **Step 4: Commit**

```bash
git add compose/Caddyfile.tmpl scripts/deploy.sh scripts/secrets.sh
git commit -m "$(cat <<'EOF'
refactor: drop /admin/* from Caddy + deploy probe

Caddyfile.tmpl: remove the /admin/* handle block. __ADMIN_BCRYPT_HASH__
substitution stays — /flash/* still uses the same basic_auth credential.

scripts/deploy.sh: drop the /admin/ post-deploy probe (the route is
gone, a 401 expectation would never resolve).

scripts/secrets.sh: update the prompt copy to reflect that the
credential now gates /flash/* only. Task name and config key unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update integration tests

**Files:**
- Modify: `tests/integration/test_routes_smoke.bats`
- Modify: `tests/integration/test_render.bats`

**Why:** Spec §3.6. `test_routes_smoke.bats` asserts `/admin/` returns 401; that test fails now that the route is gone (404 not 401). `test_render.bats` asserts `basic_auth` appears near `/admin` in the rendered Caddyfile; retarget to `/flash` for equivalent coverage.

- [ ] **Step 1: Remove the `/admin/` smoke test**

Edit `tests/integration/test_routes_smoke.bats`. Delete this test (lines 85-88):

```
@test "/admin/ is gated by basic_auth (401)" {
    code="$(_through_caddy 'https://127.0.0.1/admin/')"
    [[ "$code" == "401" ]] || { echo "got: $code"; false; }
}
```

The `/flash/` test on the immediately-following lines stays.

- [ ] **Step 2: Update the `basic_auth`/`/admin` assertion in `test_render.bats`**

Edit `tests/integration/test_render.bats`. Find the block around lines 50-55:

```bash
    # basic_auth must ONLY appear inside the /admin* handle block (mobile WebSocket
    # upgrades break under top-level basic_auth on JupyterLab). Verify that every
    # basic_auth occurrence is preceded by "handle /admin" within a few lines.
    grep -q 'basic_auth' <<< "$output" && \
        grep -B 5 'basic_auth' <<< "$output" | grep -q '/admin'
```

Replace with:

```bash
    # basic_auth must ONLY appear inside the /flash* handle block (mobile WebSocket
    # upgrades break under top-level basic_auth on JupyterLab). Verify that every
    # basic_auth occurrence is preceded by "handle /flash" within a few lines.
    grep -q 'basic_auth' <<< "$output" && \
        grep -B 5 'basic_auth' <<< "$output" | grep -q '/flash'
```

- [ ] **Step 3: Run the affected bats files locally if Docker is available**

The fake-VPS bats tests are heavy (~7 min each on CI). For local sanity, run only the render bats (no fake-VPS needed):

```bash
bats tests/integration/test_render.bats
```

Expected: all pass.

`test_routes_smoke.bats` requires the fake-VPS — it's exercised in CI's `pr-platform` matrix. Skipping local run is fine.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_routes_smoke.bats tests/integration/test_render.bats
git commit -m "$(cat <<'EOF'
test: drop /admin from integration suite

test_routes_smoke.bats: delete the "/admin/ is gated by basic_auth"
case; the route is gone.

test_render.bats: retarget the "basic_auth lives only in the admin
handle block" assertion to /flash. Same property — basic_auth must
not appear at the top-level of the Caddyfile — now anchored on its
surviving consumer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Rewrite READMEs and operator-facing copy

**Files:**
- Modify: `README.md`
- Modify: `services/siteapp/README.md`
- Modify: `config.example.yaml`
- Modify: `Taskfile.yml`

**Why:** Spec §3.8, §3.9, §3.10. After the admin removal, multiple operator-facing strings claim a UI that no longer exists.

- [ ] **Step 1: Read the current repo README**

Run: `cat README.md`
Note the lines that mention `/admin/*`, "admin panel", "admin upload UI", `task secrets:set-admin-password`.

- [ ] **Step 2: Rewrite the repo README**

Edit `README.md`. For each admin-mention site, rewrite to reflect:
- Public docs auto-deployed from `public_docs/` on push to main (new docs-only workflow).
- Agent binary uploaded by SerialHop CI via `/api/agent/upload` (bearer auth).
- No admin upload UI; `/flash/*` is the only operator-gated surface.
- `task secrets:set-admin-password` still exists but is now described as "the bcrypt hash for `/flash/*` basic_auth (operator gate)".

Concrete edit targets (current line numbers — verify by re-reading the file before each edit since prior commits may have shifted them):

- Line ~5: `admin panel, public docs, and a Windows-agent download page in front.` →
  `public docs (deployed from git), a Windows-agent download page, and an operator firmware-flashing UI (/flash/*) in front.`
- Line ~33: `/admin/* → siteapp behind basic_auth (single user 'admin')` → delete this bullet.
- Line ~42: paragraph about operator-only admin upload UI → rewrite to: "Public docs live in `public_docs/` at the repo root and ship to the VPS via the `deploy-public-docs` workflow on every push to main. CI uploads the Windows agent binary via the bearer-token-auth `/api/agent/upload` endpoint."
- Line ~54: `task secrets:set-admin-password               # password for the admin upload UI` →
  `task secrets:set-admin-password               # bcrypt hash for /flash/* operator gate`
- Line ~69: `https://<vps-host>/admin/ — operator admin panel (basic_auth)` → delete this bullet.
- Line ~108: `Operator uploads markdown via /admin/* (Caddy basic_auth).` →
  `Operator commits markdown to public_docs/ on main; the deploy-public-docs workflow rsyncs to the VPS.`

After editing, run: `grep -n 'admin' README.md`. Expected remaining hits: only the `secrets:set-admin-password` task name (legitimate, not renamed) and any mention of Grafana's admin_password (unrelated).

- [ ] **Step 3: Rewrite the siteapp README**

Edit `services/siteapp/README.md`. Replace the whole file with:

```markdown
# siteapp

Tiny FastAPI service serving the lab-bridge VPS public surface:

- **`/docs/*`** — public Markdown docs, read-only from a mounted
  `public_docs/` (deployed by the `deploy-public-docs` CI workflow).
- **`/download/agent`** + **`/download/agent/windows/agent.exe`** —
  Windows-agent download page and binary.
- **`/api/agent/upload`** — bearer-token-auth upload endpoint used by
  SerialHop CI to publish a new agent build.
- **`/api/clients/`** — internal chisel-client roster (consumed by
  Jupyter notebooks running on the same VPS).
- **`/api/public/clients/{username}`**, **`/api/public/health`**,
  **`/api/public/server-info`** — SerialHop agent bootstrap APIs.

See `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md`
for the original design and `docs/superpowers/specs/2026-05-16-siteapp-simplification-design.md`
for the admin-removal / docs-as-code rework.

## Local development

```bash
cd services/siteapp
uv sync
SITE_DATA=$(pwd)/sample_data \
SITEAPP_DOCS_DIR=$(pwd)/../../public_docs \
SITEAPP_CLIENTS_FILE=$(pwd)/sample_data/clients.json \
SITEAPP_CHISEL_LISTEN_PORT=8080 \
  uv run uvicorn app.main:app --reload
```
```

- [ ] **Step 4: Fix `config.example.yaml` line 18**

Edit `config.example.yaml`. The block currently:

```yaml
siteapp:
  # bcrypt hash for the admin panel — set via `task secrets:set-admin-password`.
  admin_password_hash: "<run task secrets:set-admin-password>"
```

Change the comment:

```yaml
siteapp:
  # bcrypt hash for the operator-gated /flash/* UI — set via `task secrets:set-admin-password`.
  admin_password_hash: "<run task secrets:set-admin-password>"
```

- [ ] **Step 5: Fix `Taskfile.yml` description**

Edit `Taskfile.yml`. Lines 35-37:

```yaml
  "secrets:set-admin-password":
    desc: Set or rotate the /admin/* basic-auth password (prompts; deploy to apply)
    cmd: bash scripts/secrets.sh set-admin-password
```

Change the `desc:` line:

```yaml
  "secrets:set-admin-password":
    desc: Set or rotate the /flash/* basic-auth password (operator gate; prompts; deploy to apply)
    cmd: bash scripts/secrets.sh set-admin-password
```

- [ ] **Step 6: Sanity-check the changes**

Run:

```bash
grep -nH '/admin' README.md services/siteapp/README.md config.example.yaml Taskfile.yml
```

Expected: no hits, OR only hits in unrelated lines (grafana admin password, secrets task name). Investigate any survivors.

- [ ] **Step 7: Commit**

```bash
git add README.md services/siteapp/README.md config.example.yaml Taskfile.yml
git commit -m "$(cat <<'EOF'
docs: rewrite operator-facing strings for admin-UI removal

README files, config.example.yaml comment, and Taskfile description
updated to reflect: public docs deployed from public_docs/ via CI,
agent binary uploaded by SerialHop CI, no admin panel. The
admin_password_hash credential is documented as the /flash/* operator
gate (it always was, since flasher shipped; the comments lagged).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Add docs-only CI workflow + release-please exclude

**Files:**
- Create: `.github/workflows/deploy-public-docs.yml`
- Modify: `release-please-config.json`

**Why:** Spec §2.5, §2.6. Push to main with changes under `public_docs/**` triggers an SSH+rsync of `public_docs/` → `~/lab-bridge/siteapp/docs/`. Platform's release-please component must exclude `public_docs/` so a docs commit doesn't bump platform version.

- [ ] **Step 1: Create the new workflow**

Create `.github/workflows/deploy-public-docs.yml`:

```yaml
name: deploy-public-docs

on:
  push:
    branches: [main]
    paths:
      - 'public_docs/**'

concurrency:
  group: deploy-public-docs-${{ github.ref }}
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  deploy-docs:
    name: rsync public_docs to VPS
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: install rsync
        run: |
          sudo apt-get update
          sudo apt-get install -y rsync

      - name: load SSH key
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.VPS_SSH_KEY }}

      - name: rsync public_docs to VPS
        env:
          VPS_HOST: ${{ vars.VPS_HOST }}
          VPS_SSH_USER: ${{ vars.VPS_SSH_USER }}
        run: |
          # Mirror public_docs/ to ~/lab-bridge/siteapp/docs/ on the VPS.
          # The siteapp container mounts this directory read-only at /srv/docs
          # and re-reads markdown on each request, so no service restart is
          # needed — rsync alone makes new content live.
          ssh -o StrictHostKeyChecking=accept-new "$VPS_SSH_USER@$VPS_HOST" \
            "mkdir -p ~/lab-bridge/siteapp/docs"
          rsync -az --delete \
            -e "ssh -o StrictHostKeyChecking=accept-new" \
            public_docs/ \
            "$VPS_SSH_USER@$VPS_HOST:~/lab-bridge/siteapp/docs/"
```

Notes on the workflow:
- Trigger gated on `public_docs/**` via top-level `paths:`. A non-docs push to main does not trigger this workflow at all (compare: per-service workflows use `dorny/paths-filter` to skip *internal* steps; this one is single-purpose and a workflow-level path filter is the cleaner choice).
- Reuses `VPS_SSH_KEY`, `VPS_HOST`, `VPS_SSH_USER` secrets/vars from the release-please deploy. No new credential setup needed.
- `--delete` removes server-side files that no longer exist in the repo — matches the source-of-truth-is-git contract.
- Concurrency by branch prevents two pushes from racing; `cancel-in-progress: false` lets each push finish (rsync is fast and idempotent; aborting mid-sync could leave a half-deleted tree).

- [ ] **Step 2: Add `public_docs` to platform exclude-paths**

Edit `release-please-config.json`. The platform component currently:

```json
    ".": {
      "package-name": "platform",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [
        { "type": "generic", "path": "compose/VERSION" }
      ],
      "exclude-paths": ["services/siteapp", "services/flasher"]
    }
```

Add `"public_docs"` to `exclude-paths`:

```json
    ".": {
      "package-name": "platform",
      "release-type": "simple",
      "include-component-in-tag": true,
      "tag-separator": "-",
      "extra-files": [
        { "type": "generic", "path": "compose/VERSION" }
      ],
      "exclude-paths": ["services/siteapp", "services/flasher", "public_docs"]
    }
```

- [ ] **Step 3: Lint the JSON**

Run: `python3 -m json.tool release-please-config.json > /dev/null`
Expected: no output (valid JSON).

- [ ] **Step 4: Lint the workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-public-docs.yml'))"`
Expected: no output. (If yaml isn't installed, skip — GitHub will validate on push.)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy-public-docs.yml release-please-config.json
git commit -m "$(cat <<'EOF'
ci: docs-only deploy workflow + release-please exclude

.github/workflows/deploy-public-docs.yml: new workflow triggered on
push to main with paths under public_docs/. SSH + rsync the docs tree
to ~/lab-bridge/siteapp/docs/ on the VPS. No image rebuild, no version
bump, no docker compose restart — the siteapp container re-reads
markdown on each request.

release-please-config.json: add public_docs to the platform component's
exclude-paths so docs-only commits don't open a platform release PR.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Post-flight

- [ ] **Post-flight 1: full test sweep**

```bash
cd services/siteapp && uv run pytest -q
docker build -t lab-bridge-siteapp:e2e services/siteapp
cd services/siteapp && uv run pytest tests/e2e/ -v
bats tests/integration/test_render.bats
```

Expected: all pass.

- [ ] **Post-flight 2: commit count + summary**

```bash
git log --oneline main..HEAD
```

Expected: exactly 10 commits (the spec sketches 7 coarser commits; this plan splits a couple for cleaner subagent-per-task review): (1) public_docs move, (2) SITEAPP_DOCS_DIR, (3) compose+e2e, (4) deploy stage, (5) admin removal, (6) safety test rewrite, (7) Caddy+deploy probe, (8) integration tests, (9) READMEs, (10) docs workflow + release-please exclude.

- [ ] **Post-flight 3: open the PR**

```bash
git push -u origin HEAD
# … then create a PR via gh pr create using the spec as the summary
```

Title: `refactor(siteapp): remove admin UI + docs-as-code via public_docs/`
Body should reference the spec at `docs/superpowers/specs/2026-05-16-siteapp-simplification-design.md`.

**VPS migration note for the PR description:** after this PR's deploy runs, the orphaned `~/lab-bridge/site_data/docs/` directory on the VPS can be removed manually with `ssh <vps> rm -rf ~/lab-bridge/site_data/docs/`. Not automated to keep the deploy idempotent.

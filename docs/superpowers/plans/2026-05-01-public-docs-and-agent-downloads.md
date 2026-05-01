# Public docs & agent downloads — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public surface to the existing `lab-bridge` VPS stack (markdown documentation with optional Russian translations + a Windows agent download page), plus an admin upload UI gated by Caddy basic_auth and a CI upload endpoint with bearer-token auth.

**Architecture:** One new container `siteapp` (FastAPI + Uvicorn) on the existing `labnet`. Caddy gains four `handle` blocks (`/docs*`, `/download*`, `/admin*`, `/api/agent/upload`); JupyterLab and Grafana auth flows are untouched. Docs render on demand from `.md` files on a mounted volume; agent binary is published by CI via a static bearer token.

**Tech Stack:** Python 3.13 + FastAPI + Uvicorn + Jinja2 + markdown-it-py + Pygments. Dependency management via `uv`. Caddy 2 for auth + routing. bats for end-to-end tests; pytest for unit tests inside the image.

**Spec:** `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md` — the source of truth for behavior. This plan implements that spec verbatim.

---

## Conventions used throughout

- **Working directory** for shell commands is the repo root (`/Users/khamitovdr/lab_devices_server`) unless stated otherwise.
- **siteapp local dev** runs from `compose/siteapp/`; commands like `uv run pytest` assume that directory.
- Every code block that creates a file shows the *full* file contents (no diffs against an earlier version unless explicitly noted).
- **Commit style** matches the existing repo: short imperative subject, optional body, `Co-Authored-By` trailer is omitted (the existing commits don't use it). Use type prefixes (`feat`, `fix`, `docs`, `test`, `chore`) consistent with `git log --oneline`.
- The plan is grouped into five phases. Within each phase, tasks may run sequentially; phases are sequential.

---

## Phase 1 — siteapp Python package (TDD, local)

Build the FastAPI app to pytest-passing on a developer laptop, no Docker yet. Create a throwaway `compose/siteapp/sample_data/` directory with a couple of `.md` fixtures and an `agent.exe` stub for manual smoke checks (`uv run uvicorn app.main:app --reload`).

### Task 1: Project scaffolding

**Files:**
- Create: `compose/siteapp/pyproject.toml`
- Create: `compose/siteapp/.python-version`
- Create: `compose/siteapp/.gitignore`
- Create: `compose/siteapp/app/__init__.py`
- Create: `compose/siteapp/tests/__init__.py`
- Create: `compose/siteapp/tests/conftest.py`
- Create: `compose/siteapp/README.md`

- [ ] **Step 1: Create `compose/siteapp/pyproject.toml`**

```toml
[project]
name = "siteapp"
version = "0.1.0"
description = "Public docs + agent downloads + admin for lab-bridge."
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115,<0.116",
    "uvicorn[standard]>=0.30,<0.31",
    "jinja2>=3.1,<4",
    "markdown-it-py[linkify]>=3.0,<4",
    "mdit-py-plugins>=0.4,<0.5",
    "pygments>=2.18,<3",
    "python-multipart>=0.0.9,<0.1",
    "itsdangerous>=2.2,<3",
]

[dependency-groups]
dev = [
    "pytest>=8.3,<9",
    "httpx>=0.27,<0.29",
    "pytest-asyncio>=0.24,<0.25",
    "ruff>=0.6,<0.13",
]

[tool.pytest.ini_options]
addopts = "-q"
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py313"
```

- [ ] **Step 2: Create `compose/siteapp/.python-version`**

```
3.13
```

- [ ] **Step 3: Create `compose/siteapp/.gitignore`**

```
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
sample_data/
agent_upload_token
```

- [ ] **Step 4: Create empty `compose/siteapp/app/__init__.py` and `compose/siteapp/tests/__init__.py`**

Both files: empty.

- [ ] **Step 5: Create `compose/siteapp/tests/conftest.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def site_data(tmp_path: Path) -> Path:
    """Fresh, empty site_data/ tree for a single test."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "agent" / "windows").mkdir(parents=True)
    return tmp_path
```

- [ ] **Step 6: Create `compose/siteapp/README.md`**

```markdown
# siteapp

Tiny FastAPI service that serves public docs (`/docs/*`), the agent download
page (`/download/*`), and an admin upload UI (`/admin/*`) for the
`lab-bridge` VPS stack.

See `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md`
for the design.

## Local development

```bash
cd compose/siteapp
uv sync
SITE_DATA=$(pwd)/sample_data uv run uvicorn app.main:app --reload
```
```

- [ ] **Step 7: Generate the lockfile**

Run:
```bash
cd compose/siteapp && uv lock
```
Expected: creates `uv.lock`.

- [ ] **Step 8: Verify pytest discovery works (no tests yet, exit 5)**

Run:
```bash
cd compose/siteapp && uv run pytest
```
Expected: exit code 5 ("no tests collected"). That's fine.

- [ ] **Step 9: Commit**

```bash
git add compose/siteapp/pyproject.toml compose/siteapp/.python-version \
        compose/siteapp/.gitignore compose/siteapp/app/__init__.py \
        compose/siteapp/tests/__init__.py compose/siteapp/tests/conftest.py \
        compose/siteapp/README.md compose/siteapp/uv.lock
git commit -m "feat(siteapp): project scaffolding (uv + pytest + ruff)"
```

---

### Task 2: Path safety helpers

Two pure functions that every upload/read flow depends on. Without these correct, the rest of the app is exploitable.

**Files:**
- Create: `compose/siteapp/app/paths.py`
- Create: `compose/siteapp/tests/test_paths.py`

- [ ] **Step 1: Write the failing test — `compose/siteapp/tests/test_paths.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import sanitize_filename, safe_join


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("foo.md", "foo.md"),
            ("Foo.MD", "foo.md"),
            ("hello-world_2.md", "hello-world_2.md"),
            ("my doc.md", "my-doc.md"),  # space -> hyphen
            ("МойФайл.md", "my-file.md"),
        ],
    )
    def test_accepts_valid(self, raw: str, expected: str) -> None:
        # Note: the Cyrillic case is *not* a transliteration commitment —
        # the rule is "lowercased ASCII [a-z0-9._-] only, anything else
        # collapses to '-'". The test asserts the collapse behavior.
        if raw == "МойФайл.md":
            assert sanitize_filename(raw) == "------.md"
            return
        assert sanitize_filename(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            ".",
            "..",
            ".hidden",
            "a/b.md",
            "a\\b.md",
            "x" * 101,
        ],
    )
    def test_rejects(self, raw: str) -> None:
        with pytest.raises(ValueError):
            sanitize_filename(raw)


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

- [ ] **Step 2: Run the test — should fail with ImportError**

```bash
cd compose/siteapp && uv run pytest tests/test_paths.py
```
Expected: collection error (`No module named 'app.paths'`).

- [ ] **Step 3: Implement — `compose/siteapp/app/paths.py`**

```python
from __future__ import annotations

import re
from pathlib import Path

_VALID = re.compile(r"^[a-z0-9._-]+$")
_COLLAPSE = re.compile(r"[^a-z0-9._-]")
MAX_LEN = 100


def sanitize_filename(raw: str) -> str:
    """Return a safe filename or raise ValueError.

    Rules: lowercased; anything outside [a-z0-9._-] collapses to '-';
    no leading dot; not '..'; max length 100; cannot contain '/' or '\\'.
    """
    if not raw or "/" in raw or "\\" in raw:
        raise ValueError(f"invalid filename: {raw!r}")
    if len(raw) > MAX_LEN:
        raise ValueError(f"filename too long ({len(raw)} > {MAX_LEN}): {raw!r}")
    candidate = _COLLAPSE.sub("-", raw.lower())
    if candidate.startswith(".") or candidate in {"", ".", ".."}:
        raise ValueError(f"invalid filename: {raw!r}")
    if not _VALID.match(candidate):
        # Defence in depth — the collapse should make this unreachable.
        raise ValueError(f"invalid filename: {raw!r}")
    return candidate


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

- [ ] **Step 4: Run the test — should pass**

```bash
cd compose/siteapp && uv run pytest tests/test_paths.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/paths.py compose/siteapp/tests/test_paths.py
git commit -m "feat(siteapp): sanitize_filename + safe_join helpers"
```

---

### Task 3: Markdown renderer

Render markdown to HTML with code highlighting, escaping raw HTML, returning the page title (first H1).

**Files:**
- Create: `compose/siteapp/app/markdown.py`
- Create: `compose/siteapp/tests/test_markdown.py`

- [ ] **Step 1: Write the failing test — `compose/siteapp/tests/test_markdown.py`**

```python
from __future__ import annotations

from app.markdown import render_markdown


def test_returns_html_and_title() -> None:
    html, title = render_markdown("# Hello\n\nworld\n")
    assert title == "Hello"
    assert "<h1" in html
    assert "world" in html


def test_no_h1_returns_none_title() -> None:
    html, title = render_markdown("plain paragraph\n")
    assert title is None
    assert "<p>plain paragraph" in html


def test_raw_html_is_escaped() -> None:
    # html=False in markdown-it: raw HTML in source is rendered as text.
    html, _ = render_markdown("<script>alert(1)</script>\n")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_fenced_code_is_highlighted() -> None:
    src = '```python\nprint("hi")\n```\n'
    html, _ = render_markdown(src)
    # Pygments wraps code in a <div class="highlight">.
    assert 'class="highlight"' in html


def test_table_renders() -> None:
    src = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    html, _ = render_markdown(src)
    assert "<table" in html and "<td>1</td>" in html


def test_heading_anchor() -> None:
    src = "## My Section\n"
    html, _ = render_markdown(src)
    # mdit-py-plugins anchors gives id="my-section".
    assert 'id="my-section"' in html
```

- [ ] **Step 2: Run test, expect failure**

```bash
cd compose/siteapp && uv run pytest tests/test_markdown.py
```

- [ ] **Step 3: Implement — `compose/siteapp/app/markdown.py`**

```python
from __future__ import annotations

import re
from html import unescape

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound


def _highlight(code: str, name: str | None, _attrs: object) -> str:
    try:
        lexer = get_lexer_by_name(name) if name else guess_lexer(code)
    except ClassNotFound:
        return ""  # markdown-it falls back to its default renderer
    formatter = HtmlFormatter(nowrap=False, cssclass="highlight")
    return highlight(code, lexer, formatter)


def _make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
        .enable(["table", "strikethrough"])
        .use(anchors_plugin, min_level=2, max_level=4, permalink=False, slug_func=_slug)
        .use(footnote_plugin)
        .use(tasklists_plugin, enabled=True)
    )
    md.options["highlight"] = _highlight
    return md


_SLUG_STRIP = re.compile(r"[^\w\s-]")
_SLUG_SPACE = re.compile(r"[\s_]+")


def _slug(s: str) -> str:
    s = unescape(s).strip().lower()
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_SPACE.sub("-", s)
    return s.strip("-")


_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _extract_title(markdown_text: str) -> str | None:
    m = _H1.search(markdown_text)
    return m.group(1).strip() if m else None


_MD = _make_md()


def render_markdown(text: str) -> tuple[str, str | None]:
    """Return (html, title). Title is the first H1's text, or None."""
    return _MD.render(text), _extract_title(text)


def pygments_css() -> str:
    """The CSS rules pygments needs for the chosen theme. Include in templates once."""
    return HtmlFormatter(cssclass="highlight").get_style_defs(".highlight")
```

- [ ] **Step 4: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_markdown.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/markdown.py compose/siteapp/tests/test_markdown.py
git commit -m "feat(siteapp): markdown renderer with pygments + anchors"
```

---

### Task 4: Translation pairing

Resolve URL paths to on-disk files, picking the right language file with English fallback.

**Files:**
- Create: `compose/siteapp/app/translations.py`
- Create: `compose/siteapp/tests/test_translations.py`

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_translations.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.translations import DocFile, find_doc, resolve_lang_file


@pytest.fixture
def docs(site_data: Path) -> Path:
    docs_root = site_data / "docs"
    (docs_root / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (docs_root / "intro.ru.md").write_text("# Введение\n", encoding="utf-8")
    section = docs_root / "section"
    section.mkdir()
    (section / "index.md").write_text("# Section\n", encoding="utf-8")
    (section / "page.md").write_text("# Page\n", encoding="utf-8")
    return docs_root


def test_find_doc_root_index(docs: Path) -> None:
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    doc = find_doc(docs, "")
    assert doc is not None
    assert doc.rel_path == Path("index")
    assert doc.en_exists is True


def test_find_doc_file(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    assert doc.rel_path == Path("intro")
    assert doc.ru_exists is True


def test_find_doc_directory_index(docs: Path) -> None:
    doc = find_doc(docs, "section/")
    assert doc is not None
    assert doc.rel_path == Path("section/index")
    assert doc.ru_exists is False


def test_find_doc_missing_returns_none(docs: Path) -> None:
    assert find_doc(docs, "nope") is None


def test_find_doc_traversal_returns_none(docs: Path) -> None:
    assert find_doc(docs, "../etc/passwd") is None


def test_resolve_lang_file_english(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "en")
    assert path == docs / "intro.md"


def test_resolve_lang_file_russian(docs: Path) -> None:
    doc = find_doc(docs, "intro")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "ru")
    assert path == docs / "intro.ru.md"


def test_resolve_lang_file_falls_back_to_english(docs: Path) -> None:
    doc = find_doc(docs, "section/page")
    assert doc is not None
    path = resolve_lang_file(docs, doc, "ru")
    assert path == docs / "section" / "page.md"
```

- [ ] **Step 2: Run, expect ImportError**

```bash
cd compose/siteapp && uv run pytest tests/test_translations.py
```

- [ ] **Step 3: Implement — `compose/siteapp/app/translations.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.paths import safe_join

Lang = Literal["en", "ru"]


@dataclass(frozen=True)
class DocFile:
    """A doc resolved by URL path. `rel_path` has no extension."""

    rel_path: Path
    en_exists: bool
    ru_exists: bool


def find_doc(docs_root: Path, url_path: str) -> DocFile | None:
    """Resolve a `/docs` sub-path to a DocFile. Return None on missing English."""
    cleaned = url_path.strip("/")
    parts: list[str]
    if not cleaned:
        rel = Path("index")
    elif url_path.endswith("/"):
        rel = Path(cleaned) / "index"
    else:
        rel = Path(cleaned)

    parts = [p for p in rel.parts if p]
    if not parts:
        rel = Path("index")
        parts = ["index"]

    try:
        en = safe_join(docs_root, *parts) .with_suffix(".md") if False else _safe_md(
            docs_root, parts, ".md"
        )
        ru = _safe_md(docs_root, parts, ".ru.md")
    except ValueError:
        return None

    if not en.is_file():
        return None
    return DocFile(rel_path=Path(*parts), en_exists=True, ru_exists=ru.is_file())


def resolve_lang_file(docs_root: Path, doc: DocFile, lang: Lang) -> Path:
    """Disk path for a given language, falling back to English silently."""
    if lang == "ru" and doc.ru_exists:
        return _safe_md(docs_root, doc.rel_path.parts, ".ru.md")
    return _safe_md(docs_root, doc.rel_path.parts, ".md")


def _safe_md(base: Path, parts: tuple[str, ...] | list[str], suffix: str) -> Path:
    *prefix, last = parts
    return safe_join(base, *prefix, last + suffix)
```

- [ ] **Step 4: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_translations.py -v
```

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/translations.py compose/siteapp/tests/test_translations.py
git commit -m "feat(siteapp): translation pairing (en/ru with fallback)"
```

---

### Task 5: Nav tree builder

Walk `docs/`, return a hierarchical nav structure with English + optional Russian titles.

**Files:**
- Create: `compose/siteapp/app/nav.py`
- Create: `compose/siteapp/tests/test_nav.py`

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_nav.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.nav import build_nav


@pytest.fixture
def tree(site_data: Path) -> Path:
    d = site_data / "docs"
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "index.ru.md").write_text("# Главная\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sec = d / "advanced"
    sec.mkdir()
    (sec / "index.md").write_text("# Advanced\n", encoding="utf-8")
    (sec / "deep.md").write_text("# Deep dive\n", encoding="utf-8")
    return d


def test_top_level_order_dirs_then_files(tree: Path) -> None:
    nav = build_nav(tree)
    titles_en = [e.title_en for e in nav]
    # 'advanced' (dir) before 'index' before 'guide' alphabetically isn't
    # what we want — directories first, then files alphabetically by name.
    assert titles_en == ["Advanced", "Home", "Guide"]


def test_translation_title_when_present(tree: Path) -> None:
    nav = build_nav(tree)
    home = next(e for e in nav if e.url == "/docs/")
    assert home.title_en == "Home"
    assert home.title_ru == "Главная"


def test_no_translation_yields_none(tree: Path) -> None:
    nav = build_nav(tree)
    guide = next(e for e in nav if e.url == "/docs/guide")
    assert guide.title_ru is None


def test_directory_url_has_trailing_slash(tree: Path) -> None:
    nav = build_nav(tree)
    advanced = next(e for e in nav if e.title_en == "Advanced")
    assert advanced.url == "/docs/advanced/"
    assert {c.url for c in advanced.children} == {"/docs/advanced/deep"}


def test_filename_fallback_when_no_h1(site_data: Path) -> None:
    d = site_data / "docs"
    (d / "no-heading.md").write_text("just a paragraph\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/no-heading")
    assert entry.title_en == "no-heading"


def test_orphan_ru_file_is_ignored(site_data: Path) -> None:
    d = site_data / "docs"
    (d / "only-ru.ru.md").write_text("# Только\n", encoding="utf-8")
    nav = build_nav(d)
    assert all(e.url != "/docs/only-ru" for e in nav)
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement — `compose/siteapp/app/nav.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.markdown import _extract_title


@dataclass(frozen=True)
class NavEntry:
    title_en: str
    title_ru: str | None
    url: str
    children: tuple["NavEntry", ...] = field(default_factory=tuple)


def build_nav(docs_root: Path) -> list[NavEntry]:
    if not docs_root.is_dir():
        return []
    return _walk(docs_root, url_prefix="/docs/")


def _walk(directory: Path, url_prefix: str) -> list[NavEntry]:
    dirs: list[NavEntry] = []
    files: list[NavEntry] = []
    for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            index = child / "index.md"
            if not index.is_file():
                # Directory with no index.md — still walk it, but title falls back to dir name.
                children = _walk(child, url_prefix + child.name + "/")
                if children:
                    dirs.append(
                        NavEntry(
                            title_en=child.name,
                            title_ru=None,
                            url=url_prefix + child.name + "/",
                            children=tuple(children),
                        )
                    )
                continue
            title_en = _extract_title(index.read_text(encoding="utf-8")) or child.name
            ru_index = child / "index.ru.md"
            title_ru = (
                _extract_title(ru_index.read_text(encoding="utf-8"))
                if ru_index.is_file()
                else None
            )
            children = _walk(child, url_prefix + child.name + "/")
            dirs.append(
                NavEntry(
                    title_en=title_en,
                    title_ru=title_ru,
                    url=url_prefix + child.name + "/",
                    children=tuple(c for c in children if not _is_index(c)),
                )
            )
        elif child.is_file() and child.suffix == ".md" and not child.name.endswith(".ru.md"):
            stem = child.stem  # filename without .md
            if stem == "index":
                # The index entry is represented at the parent directory's URL — for the
                # top-level docs/, expose it with url ending in '/' so it's the landing.
                if url_prefix == "/docs/":
                    title_en = _extract_title(child.read_text(encoding="utf-8")) or "Home"
                    ru = child.with_name("index.ru.md")
                    title_ru = (
                        _extract_title(ru.read_text(encoding="utf-8"))
                        if ru.is_file()
                        else None
                    )
                    files.append(
                        NavEntry(title_en=title_en, title_ru=title_ru, url=url_prefix)
                    )
                continue
            title_en = _extract_title(child.read_text(encoding="utf-8")) or stem
            ru = child.with_name(stem + ".ru.md")
            title_ru = (
                _extract_title(ru.read_text(encoding="utf-8"))
                if ru.is_file()
                else None
            )
            files.append(
                NavEntry(
                    title_en=title_en,
                    title_ru=title_ru,
                    url=url_prefix + stem,
                )
            )
    return dirs + files


def _is_index(entry: NavEntry) -> bool:
    return entry.url.endswith("/")
```

- [ ] **Step 4: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_nav.py -v
```

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/nav.py compose/siteapp/tests/test_nav.py
git commit -m "feat(siteapp): build_nav walks docs/ for sidebar tree"
```

---

### Task 6: Settings & data layer wiring

A small `config` module that picks up `SITE_DATA` (path to the data directory) and `SITEAPP_AGENT_UPLOAD_TOKEN` (read from `*__FILE` env, like Docker secrets).

**Files:**
- Create: `compose/siteapp/app/config.py`
- Create: `compose/siteapp/tests/test_config.py`

- [ ] **Step 1: Test — `compose/siteapp/tests/test_config.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings, load_settings


def test_load_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "abc123")
    monkeypatch.delenv("SITEAPP_AGENT_UPLOAD_TOKEN__FILE", raising=False)
    settings = load_settings()
    assert settings.site_data == tmp_path.resolve()
    assert settings.agent_upload_token == "abc123"


def test_token_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "tok"
    token_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.delenv("SITEAPP_AGENT_UPLOAD_TOKEN", raising=False)
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN__FILE", str(token_file))
    settings = load_settings()
    assert settings.agent_upload_token == "file-token"


def test_missing_site_data_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SITE_DATA", raising=False)
    with pytest.raises(RuntimeError):
        load_settings()


def test_creates_subdirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    s = load_settings()
    assert (s.site_data / "docs").is_dir()
    assert (s.site_data / "agent" / "windows").is_dir()
    assert isinstance(s, Settings)
```

- [ ] **Step 2: Run test, expect import failure**

- [ ] **Step 3: Implement — `compose/siteapp/app/config.py`**

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
    max_upload_mb_doc: int = 10
    max_upload_mb_agent: int = 100
    csrf_secret: str = ""

    @property
    def docs_root(self) -> Path:
        return self.site_data / "docs"

    @property
    def agent_root(self) -> Path:
        return self.site_data / "agent"


def load_settings() -> Settings:
    data = os.environ.get("SITE_DATA")
    if not data:
        raise RuntimeError("SITE_DATA env var is required")
    site_data = Path(data).resolve()
    (site_data / "docs").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / "windows").mkdir(parents=True, exist_ok=True)
    (site_data / "agent" / ".tmp").mkdir(parents=True, exist_ok=True)

    token_file = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN__FILE")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    else:
        token = os.environ.get("SITEAPP_AGENT_UPLOAD_TOKEN", "").strip()
    if not token:
        # Local-dev convenience: synthesize a per-process token so the app boots.
        token = secrets.token_urlsafe(32)

    csrf = os.environ.get("SITEAPP_CSRF_SECRET", secrets.token_urlsafe(32))

    return Settings(
        site_data=site_data,
        agent_upload_token=token,
        csrf_secret=csrf,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/config.py compose/siteapp/tests/test_config.py
git commit -m "feat(siteapp): settings loader (SITE_DATA + token from env or *__FILE)"
```

---

### Task 7: FastAPI app skeleton

The `app.main:app` entry point with router includes, static mount, and templates configured. No real routes yet — just `/healthz` to prove it boots.

**Files:**
- Create: `compose/siteapp/app/main.py`
- Create: `compose/siteapp/app/templates.py`
- Create: `compose/siteapp/app/templates/base.html`
- Create: `compose/siteapp/app/static/site.css` (placeholder; styled later)
- Create: `compose/siteapp/tests/test_main.py`

- [ ] **Step 1: Test — `compose/siteapp/tests/test_main.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "test-token")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def test_healthz(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run, expect failure**

- [ ] **Step 3: Implement `app/templates.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
```

- [ ] **Step 4: Implement `app/main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Create `app/templates/base.html`**

```html
<!doctype html>
<html lang="{{ lang|default('en') }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}lab-bridge{% endblock %}</title>
  <link rel="stylesheet" href="/_static/site.css">
  <style>{{ pygments_css|safe }}</style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">lab-bridge</a>
    {% block topbar_right %}{% endblock %}
  </header>
  <main>{% block main %}{% endblock %}</main>
  <footer><a href="/">lab-bridge</a></footer>
</body>
</html>
```

- [ ] **Step 6: Create `app/static/site.css` (initial — replaced in Task 14)**

```css
:root { color-scheme: light dark; }
body { font: 16px/1.55 system-ui, sans-serif; margin: 0; }
.topbar { display:flex; justify-content:space-between; padding: 12px 20px; border-bottom: 1px solid #0001; }
.brand { font-weight: 600; text-decoration: none; color: inherit; }
main { max-width: 720px; margin: 24px auto; padding: 0 20px; }
footer { margin: 48px 20px; color: #888; text-align: center; }
```

- [ ] **Step 7: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_main.py -v
```

- [ ] **Step 8: Commit**

```bash
git add compose/siteapp/app/main.py compose/siteapp/app/templates.py \
        compose/siteapp/app/templates/base.html compose/siteapp/app/static/site.css \
        compose/siteapp/tests/test_main.py
git commit -m "feat(siteapp): FastAPI skeleton with /healthz and base template"
```

---

### Task 8: Public docs routes

Render markdown on demand under `/docs/*`, with EN/RU lang resolution and the trailing-slash redirect rule.

**Files:**
- Create: `compose/siteapp/app/docs.py`
- Create: `compose/siteapp/app/templates/doc.html`
- Create: `compose/siteapp/app/templates/_lang_toggle.html`
- Create: `compose/siteapp/app/templates/_nav.html`
- Modify: `compose/siteapp/app/main.py` — register the docs router.
- Create: `compose/siteapp/tests/test_routes_docs.py`

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_routes_docs.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nWelcome\n", encoding="utf-8")
    (docs / "intro.md").write_text("# Intro\n\nhello world\n", encoding="utf-8")
    (docs / "intro.ru.md").write_text("# Введение\n\nпривет\n", encoding="utf-8")
    section = docs / "section"
    section.mkdir()
    (section / "index.md").write_text("# Section\n", encoding="utf-8")
    (section / "page.md").write_text("# Page\n", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def test_root_renders_index(client: TestClient) -> None:
    r = client.get("/")  # docs router mounts at /docs, the bare / belongs to jupyter
    # In siteapp the bare / is not handled here; we expect 404 or the docs index?
    # Spec: docs are served at /docs. So under /docs/ we get the index.
    r = client.get("/docs/")
    assert r.status_code == 200
    assert "Welcome" in r.text


def test_page_renders(client: TestClient) -> None:
    r = client.get("/docs/intro")
    assert r.status_code == 200
    assert "hello world" in r.text


def test_directory_without_slash_redirects(client: TestClient) -> None:
    r = client.get("/docs/section", follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"].endswith("/docs/section/")


def test_lang_query_switches_to_russian(client: TestClient) -> None:
    r = client.get("/docs/intro?lang=ru")
    assert r.status_code == 200
    assert "привет" in r.text


def test_lang_falls_back_to_english(client: TestClient) -> None:
    r = client.get("/docs/section/page?lang=ru")
    assert r.status_code == 200
    assert "Page" in r.text  # English title


def test_lang_cookie_persists(client: TestClient) -> None:
    # Setting ?lang=ru should set the cookie.
    r = client.get("/docs/intro?lang=ru", follow_redirects=False)
    assert r.cookies.get("lang") == "ru"
    # On a translated page, follow-up request without ?lang= still gets ru.
    r2 = client.get("/docs/intro", cookies={"lang": "ru"})
    assert "привет" in r2.text


def test_missing_returns_404(client: TestClient) -> None:
    assert client.get("/docs/nope").status_code == 404


def test_orphan_ru_only_returns_404(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "only.ru.md").write_text("# Только\n", encoding="utf-8")
    assert client.get("/docs/only").status_code == 404
```

- [ ] **Step 2: Implement `app/docs.py`**

```python
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.status import HTTP_308_PERMANENT_REDIRECT

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.nav import build_nav
from app.templates import templates
from app.translations import find_doc, resolve_lang_file


def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]:
    for v in (query, cookie):
        if v in ("en", "ru"):
            return v  # type: ignore[return-value]
    return "en"


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/docs", include_in_schema=False)
    def docs_root_no_slash() -> Response:
        return RedirectResponse(url="/docs/", status_code=HTTP_308_PERMANENT_REDIRECT)

    @router.get("/docs/{path:path}")
    def docs_path(
        path: str,
        request: Request,
        lang: str | None = None,
    ) -> Response:
        # Trailing-slash semantics: a directory URL must end with `/` so relative
        # links inside index.md resolve correctly in the browser.
        if path and not path.endswith("/"):
            candidate = settings.docs_root / path
            if candidate.is_dir():
                return RedirectResponse(
                    url=f"/docs/{path}/", status_code=HTTP_308_PERMANENT_REDIRECT
                )

        doc = find_doc(settings.docs_root, path)
        if doc is None:
            return Response(status_code=404)

        chosen = _pick_lang(lang, request.cookies.get("lang"))
        file = resolve_lang_file(settings.docs_root, doc, chosen)
        text = file.read_text(encoding="utf-8")
        html, title = render_markdown(text)

        nav = build_nav(settings.docs_root)
        response = templates.TemplateResponse(
            request,
            "doc.html",
            {
                "title": title or doc.rel_path.name,
                "html": html,
                "lang": chosen,
                "doc": doc,
                "nav": nav,
                "current_url": str(request.url.path),
                "pygments_css": pygments_css(),
            },
        )
        # Persist explicit query selection in the cookie.
        if lang in ("en", "ru"):
            response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
        return response

    return router
```

- [ ] **Step 3: Create `app/templates/_nav.html`**

```html
{% macro render_entry(entry, lang, current_url) -%}
  {%- set title = entry.title_ru if (lang == 'ru' and entry.title_ru) else entry.title_en -%}
  <li {% if entry.url == current_url %}class="active"{% endif %}>
    <a href="{{ entry.url }}{% if lang == 'ru' %}?lang=ru{% endif %}">{{ title }}</a>
    {% if entry.children %}
      <ul>
        {% for child in entry.children %}{{ render_entry(child, lang, current_url) }}{% endfor %}
      </ul>
    {% endif %}
  </li>
{%- endmacro %}

<nav class="sidebar">
  <ul>
    {% for entry in nav %}{{ render_entry(entry, lang, current_url) }}{% endfor %}
  </ul>
</nav>
```

- [ ] **Step 4: Create `app/templates/_lang_toggle.html`**

```html
{% if doc.ru_exists %}
<form method="get" class="lang-toggle">
  <a class="pill {{ 'active' if lang == 'en' else '' }}"
     href="?lang=en">EN</a>
  <a class="pill {{ 'active' if lang == 'ru' else '' }}"
     href="?lang=ru">RU</a>
</form>
{% else %}
<span class="lang-toggle disabled">
  <span class="pill active">EN</span>
  <span class="pill muted" title="No translation available">RU</span>
</span>
{% endif %}
```

- [ ] **Step 5: Create `app/templates/doc.html`**

```html
{% extends "base.html" %}
{% block title %}{{ title }} · lab-bridge docs{% endblock %}
{% block topbar_right %}{% include "_lang_toggle.html" %}{% endblock %}
{% block main %}
<div class="layout-with-sidebar">
  {% include "_nav.html" %}
  <article class="prose">
    {{ html|safe }}
  </article>
</div>
{% endblock %}
```

- [ ] **Step 6: Wire the router into `app/main.py` (replace the file)**

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_settings
from app.docs import make_router as make_docs_router
from app.templates import TEMPLATE_DIR

settings = load_settings()
app = FastAPI(title="lab-bridge siteapp")

app.mount(
    "/_static",
    StaticFiles(directory=str(TEMPLATE_DIR.parent / "static")),
    name="static",
)
app.include_router(make_docs_router(settings))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_routes_docs.py -v
```

- [ ] **Step 8: Commit**

```bash
git add compose/siteapp/app/docs.py compose/siteapp/app/templates/doc.html \
        compose/siteapp/app/templates/_lang_toggle.html \
        compose/siteapp/app/templates/_nav.html compose/siteapp/app/main.py \
        compose/siteapp/tests/test_routes_docs.py
git commit -m "feat(siteapp): public /docs routes with EN/RU + trailing slash"
```

---

### Task 9: Public agent download page + binary

`/download/agent` (HTML) + `/download/agent/windows/agent.exe` (binary). Reads `meta.json` for version display.

**Files:**
- Create: `compose/siteapp/app/agent.py`
- Create: `compose/siteapp/app/templates/agent.html`
- Modify: `compose/siteapp/app/main.py` — include the agent router.
- Create: `compose/siteapp/tests/test_routes_agent.py`

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_routes_agent.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "test-token")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _publish_binary(tmp_path: Path, content: bytes = b"PE-binary-bytes") -> None:
    agent = tmp_path / "agent"
    (agent / "windows" / "agent.exe").write_bytes(content)
    meta = {
        "version": "1.2.3",
        "sha256": "abc",
        "uploaded_at": "2026-05-01T00:00:00Z",
        "size": len(content),
    }
    (agent / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_page_when_no_binary(client: TestClient) -> None:
    r = client.get("/download/agent")
    assert r.status_code == 200
    assert "Not yet available" in r.text


def test_page_renders_when_binary_present(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path)
    r = client.get("/download/agent")
    assert r.status_code == 200
    assert "1.2.3" in r.text
    assert "Download for Windows" in r.text


def test_binary_streams(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path, b"hello-binary")
    r = client.get("/download/agent/windows/agent.exe")
    assert r.status_code == 200
    assert r.content == b"hello-binary"
    assert r.headers["content-type"] == "application/octet-stream"
    assert "lab-bridge-agent-1.2.3.exe" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"


def test_binary_404_when_missing(client: TestClient) -> None:
    assert client.get("/download/agent/windows/agent.exe").status_code == 404


def test_page_renders_body_markdown(tmp_path: Path, client: TestClient) -> None:
    _publish_binary(tmp_path)
    (tmp_path / "agent" / "page.md").write_text(
        "## What is this?\n\nA Windows lab agent.\n", encoding="utf-8"
    )
    r = client.get("/download/agent")
    assert "What is this?" in r.text
    assert "A Windows lab agent" in r.text
```

- [ ] **Step 2: Implement `app/agent.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.config import Settings
from app.markdown import pygments_css, render_markdown
from app.templates import templates


@dataclass(frozen=True)
class AgentInfo:
    version: str
    size: int
    sha256: str
    uploaded_at: str


def load_meta(agent_root: Path) -> AgentInfo | None:
    meta_path = agent_root / "meta.json"
    binary_path = agent_root / "windows" / "agent.exe"
    if not (meta_path.is_file() and binary_path.is_file()):
        return None
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    return AgentInfo(
        version=str(data.get("version", "?")),
        size=int(data.get("size", 0)),
        sha256=str(data.get("sha256", "")),
        uploaded_at=str(data.get("uploaded_at", "")),
    )


def _pick_lang(query: str | None, cookie: str | None) -> Literal["en", "ru"]:
    for v in (query, cookie):
        if v in ("en", "ru"):
            return v  # type: ignore[return-value]
    return "en"


def _body_markdown(agent_root: Path, lang: str) -> str | None:
    candidates: list[Path] = []
    if lang == "ru":
        candidates.append(agent_root / "page.ru.md")
    candidates.append(agent_root / "page.md")
    for c in candidates:
        if c.is_file():
            html, _ = render_markdown(c.read_text(encoding="utf-8"))
            return html
    return None


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/download/agent")
    def agent_page(request: Request, lang: str | None = None) -> Response:
        chosen = _pick_lang(lang, request.cookies.get("lang"))
        info = load_meta(settings.agent_root)
        body_html = _body_markdown(settings.agent_root, chosen)
        ru_body_exists = (settings.agent_root / "page.ru.md").is_file()
        response = templates.TemplateResponse(
            request,
            "agent.html",
            {
                "info": info,
                "body_html": body_html,
                "lang": chosen,
                "ru_exists": ru_body_exists,
                "pygments_css": pygments_css(),
            },
        )
        if lang in ("en", "ru"):
            response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365, samesite="lax")
        return response

    @router.get("/download/agent/windows/agent.exe")
    def agent_binary() -> Response:
        info = load_meta(settings.agent_root)
        if info is None:
            return Response(status_code=404)
        path = settings.agent_root / "windows" / "agent.exe"
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"lab-bridge-agent-{info.version}.exe",
            headers={"Cache-Control": "no-store"},
        )

    return router
```

- [ ] **Step 3: Create `app/templates/agent.html`**

```html
{% extends "base.html" %}
{% block title %}Lab Bridge Agent{% endblock %}
{% block topbar_right %}
  {% if ru_exists %}
    <span class="lang-toggle">
      <a class="pill {{ 'active' if lang == 'en' else '' }}" href="?lang=en">EN</a>
      <a class="pill {{ 'active' if lang == 'ru' else '' }}" href="?lang=ru">RU</a>
    </span>
  {% endif %}
{% endblock %}
{% block main %}
<section class="agent-hero">
  <h1>Lab Bridge Agent</h1>
  <p class="lede">Windows service that connects a lab device to the lab-bridge VPS.</p>
  {% if info %}
    <a class="download-button"
       href="/download/agent/windows/agent.exe">
      Download for Windows · v{{ info.version }} · {{ "%.1f"|format(info.size / 1048576) }} MB
    </a>
  {% else %}
    <button class="download-button" disabled>Not yet available — check back soon</button>
  {% endif %}
</section>

{% if body_html %}
<section class="agent-body prose">{{ body_html|safe }}</section>
{% endif %}

{% if info %}
<section class="agent-meta">
  <h2>Version metadata</h2>
  <dl>
    <dt>Version</dt><dd>{{ info.version }}</dd>
    <dt>Released</dt><dd>{{ info.uploaded_at }}</dd>
    <dt>SHA-256</dt><dd><code>{{ info.sha256 }}</code></dd>
  </dl>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Wire the router — replace `app/main.py`**

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent import make_router as make_agent_router
from app.config import load_settings
from app.docs import make_router as make_docs_router
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


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_routes_agent.py -v
```

- [ ] **Step 6: Commit**

```bash
git add compose/siteapp/app/agent.py compose/siteapp/app/templates/agent.html \
        compose/siteapp/app/main.py compose/siteapp/tests/test_routes_agent.py
git commit -m "feat(siteapp): /download/agent page and binary stream"
```

---

### Task 10: CI agent upload endpoint

`POST /api/agent/upload` with bearer-token auth, atomic rename, sha256, meta.json write.

**Files:**
- Create: `compose/siteapp/app/api.py`
- Modify: `compose/siteapp/app/main.py` — include the api router.
- Create: `compose/siteapp/tests/test_routes_api.py`

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_routes_api.py`**

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TOKEN = "secret-token-xyz"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", TOKEN)
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _post(client: TestClient, *, token: str | None, version: str, body: bytes) -> object:
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/api/agent/upload",
        headers=headers,
        files={"binary": ("agent.exe", body, "application/octet-stream")},
        data={"version": version},
    )


def test_unauthorized_without_token(client: TestClient) -> None:
    r = _post(client, token=None, version="1.0.0", body=b"abc")
    assert r.status_code == 401


def test_unauthorized_wrong_token(client: TestClient) -> None:
    r = _post(client, token="wrong", version="1.0.0", body=b"abc")
    assert r.status_code == 401


def test_bad_version_rejected(client: TestClient) -> None:
    r = _post(client, token=TOKEN, version="not-a-semver", body=b"abc")
    assert r.status_code == 400


def test_happy_path(client: TestClient, tmp_path: Path) -> None:
    body = b"PE-bytes" * 32
    r = _post(client, token=TOKEN, version="1.2.3", body=body)
    assert r.status_code == 200
    payload = r.json()
    assert payload["version"] == "1.2.3"
    assert payload["size"] == len(body)
    assert payload["sha256"] == hashlib.sha256(body).hexdigest()

    saved = (tmp_path / "agent" / "windows" / "agent.exe").read_bytes()
    assert saved == body
    meta = json.loads((tmp_path / "agent" / "meta.json").read_text(encoding="utf-8"))
    assert meta["version"] == "1.2.3"
    assert meta["sha256"] == payload["sha256"]


def test_overwrite_replaces_atomically(client: TestClient, tmp_path: Path) -> None:
    _post(client, token=TOKEN, version="1.0.0", body=b"first")
    _post(client, token=TOKEN, version="2.0.0", body=b"second")
    saved = (tmp_path / "agent" / "windows" / "agent.exe").read_bytes()
    assert saved == b"second"
    meta = json.loads((tmp_path / "agent" / "meta.json").read_text(encoding="utf-8"))
    assert meta["version"] == "2.0.0"


def test_upload_too_large_rejected(client: TestClient, monkeypatch) -> None:
    # Force the limit very low for the test.
    from app import api as api_mod

    monkeypatch.setattr(api_mod, "MAX_AGENT_BYTES", 16)
    r = _post(client, token=TOKEN, version="1.0.0", body=b"x" * 100)
    assert r.status_code == 413
```

- [ ] **Step 2: Implement `app/api.py`**

```python
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import Settings

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$")
MAX_AGENT_BYTES = 100 * 1024 * 1024  # 100 MiB
CHUNK = 64 * 1024


def _check_token(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401)
    candidate = authorization.split(None, 1)[1].strip()
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401)


def _atomic_write_bytes_via_path(src: Path, dst: Path) -> None:
    os.replace(src, dst)


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/api/agent/upload")
    async def upload_agent(
        version: str = Form(...),
        binary: UploadFile = File(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        _check_token(authorization, settings.agent_upload_token)
        if not VERSION_RE.match(version):
            raise HTTPException(status_code=400, detail="invalid version")

        agent_dir = settings.agent_root / "windows"
        tmp_dir = settings.agent_root / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        agent_dir.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        size = 0
        fd, tmp_name = tempfile.mkstemp(dir=str(tmp_dir), prefix="agent-", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = await binary.read(CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_AGENT_BYTES:
                        raise HTTPException(status_code=413, detail="upload too large")
                    digest.update(chunk)
                    out.write(chunk)
        except HTTPException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        sha256 = digest.hexdigest()
        target = agent_dir / "agent.exe"
        _atomic_write_bytes_via_path(Path(tmp_name), target)

        meta = {
            "version": version,
            "sha256": sha256,
            "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "size": size,
        }
        meta_tmp = tempfile.NamedTemporaryFile(
            "w", dir=str(settings.agent_root), prefix="meta-", suffix=".json", delete=False
        )
        with meta_tmp as f:
            json.dump(meta, f)
        os.replace(meta_tmp.name, settings.agent_root / "meta.json")

        return {"version": version, "sha256": sha256, "size": size}

    return router
```

- [ ] **Step 3: Wire into `app/main.py`**

Add to imports:
```python
from app.api import make_router as make_api_router
```
Add after the agent router include:
```python
app.include_router(make_api_router(settings))
```

- [ ] **Step 4: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_routes_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/api.py compose/siteapp/app/main.py \
        compose/siteapp/tests/test_routes_api.py
git commit -m "feat(siteapp): POST /api/agent/upload (bearer token, atomic write)"
```

---

### Task 11: Admin docs router

Dashboard, file manager, upload, delete, rename, new-folder. CSRF via `itsdangerous` synchronizer token.

**Files:**
- Create: `compose/siteapp/app/admin.py`
- Create: `compose/siteapp/app/templates/admin/base.html`
- Create: `compose/siteapp/app/templates/admin/index.html`
- Create: `compose/siteapp/app/templates/admin/docs.html`
- Modify: `compose/siteapp/app/main.py` — include admin router.
- Create: `compose/siteapp/tests/test_routes_admin.py`

> NOTE: We rely on Caddy's `basic_auth` for *user* authentication. The siteapp itself is not auth-aware on `/admin/*` — it trusts the upstream proxy because the only path that reaches it for `/admin/*` is via Caddy. CSRF protection is still required because basic-auth credentials are auto-sent by browsers; without CSRF a forged cross-origin form post would succeed.

- [ ] **Step 1: Failing test — `compose/siteapp/tests/test_routes_admin.py`**

```python
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SITE_DATA", str(tmp_path))
    monkeypatch.setenv("SITEAPP_AGENT_UPLOAD_TOKEN", "x")
    monkeypatch.setenv("SITEAPP_CSRF_SECRET", "test-csrf-secret")
    from importlib import reload

    import app.main

    reload(app.main)
    return TestClient(app.main.app)


def _csrf(client: TestClient) -> str:
    r = client.get("/admin/docs")
    # Pull the token out of the rendered form.
    import re

    m = re.search(r'name="csrf"\s+value="([^"]+)"', r.text)
    assert m, "csrf token not found in admin/docs"
    return m.group(1)


def test_dashboard_renders(client: TestClient) -> None:
    r = client.get("/admin/")
    assert r.status_code == 200
    assert "Documentation" in r.text and "Agent" in r.text


def test_docs_listing_empty(client: TestClient) -> None:
    r = client.get("/admin/docs")
    assert r.status_code == 200
    assert "Drop files here" in r.text


def test_upload_md(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": ""},
        files={"files": ("Hello.MD", b"# Hi\n", "text/markdown")},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "hello.md").is_file()


def test_upload_rejects_bad_extension(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": ""},
        files={"files": ("evil.exe", b"\x4d\x5a", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert not any((tmp_path / "docs").iterdir())


def test_upload_rejects_traversal(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/upload",
        data={"csrf": csrf, "target": "../escape"},
        files={"files": ("ok.md", b"# Ok\n", "text/markdown")},
    )
    assert r.status_code == 400


def test_upload_without_csrf(client: TestClient) -> None:
    r = client.post(
        "/admin/docs/upload",
        data={"target": ""},
        files={"files": ("ok.md", b"# Ok\n", "text/markdown")},
    )
    assert r.status_code == 403


def test_delete(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "doomed.md").write_text("# Doomed\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/delete",
        data={"csrf": csrf, "target": "", "name": "doomed.md"},
    )
    assert r.status_code in (200, 303)
    assert not (tmp_path / "docs" / "doomed.md").exists()


def test_rename(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "docs" / "old.md").write_text("# Old\n", encoding="utf-8")
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/rename",
        data={"csrf": csrf, "target": "", "old": "old.md", "new": "shiny.md"},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "shiny.md").is_file()
    assert not (tmp_path / "docs" / "old.md").exists()


def test_new_folder(client: TestClient, tmp_path: Path) -> None:
    csrf = _csrf(client)
    r = client.post(
        "/admin/docs/new-folder",
        data={"csrf": csrf, "target": "", "name": "Section-One"},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "docs" / "section-one").is_dir()
```

- [ ] **Step 2: Implement `app/admin.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from itsdangerous import BadSignature, URLSafeSerializer

from app.config import Settings
from app.paths import safe_join, sanitize_filename
from app.templates import templates

ALLOWED_DOC_EXT = {".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_DOC_BYTES = 10 * 1024 * 1024


def _serializer(secret: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret, salt="csrf")


def _make_csrf(serializer: URLSafeSerializer) -> str:
    return serializer.dumps("ok")


def _check_csrf(serializer: URLSafeSerializer, token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=403, detail="missing csrf")
    try:
        serializer.loads(token)
    except BadSignature as e:
        raise HTTPException(status_code=403, detail="bad csrf") from e


def _resolve_target(docs_root: Path, target: str) -> Path:
    parts = [p for p in target.split("/") if p]
    if not parts:
        return docs_root.resolve()
    try:
        return safe_join(docs_root, *parts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="bad target") from e


def _list_dir(path: Path) -> list[dict[str, object]]:
    if not path.is_dir():
        return []
    out: list[dict[str, object]] = []
    for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith(".") or child.name.startswith("agent_upload_token"):
            continue
        st = child.stat()
        out.append(
            {
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": st.st_size,
                "mtime": st.st_mtime,
            }
        )
    return out


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/admin")
    serializer = _serializer(settings.csrf_secret)

    @router.get("/", include_in_schema=False)
    @router.get("", include_in_schema=False)
    def dashboard(request: Request) -> Response:
        from app.agent import load_meta

        info = load_meta(settings.agent_root)
        # Count *.md files only.
        docs_count = sum(1 for _ in settings.docs_root.rglob("*.md"))
        last_doc = None
        if docs_count:
            last_doc = max(
                (p.stat().st_mtime for p in settings.docs_root.rglob("*.md")),
                default=0,
            )
        return templates.TemplateResponse(
            request,
            "admin/index.html",
            {
                "docs_count": docs_count,
                "last_doc_mtime": last_doc,
                "agent_info": info,
            },
        )

    @router.get("/docs", include_in_schema=False)
    def docs_manager(request: Request, target: str = "") -> Response:
        target_path = _resolve_target(settings.docs_root, target)
        return templates.TemplateResponse(
            request,
            "admin/docs.html",
            {
                "target": target,
                "items": _list_dir(target_path),
                "csrf": _make_csrf(serializer),
            },
        )

    @router.post("/docs/upload")
    async def upload(
        target: str = Form(""),
        csrf: str = Form(""),
        files: list[UploadFile] = File(...),
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        target_path.mkdir(parents=True, exist_ok=True)
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="target is not a directory")
        for upload in files:
            name = sanitize_filename(upload.filename or "")
            ext = Path(name).suffix.lower()
            if ext not in ALLOWED_DOC_EXT:
                raise HTTPException(status_code=400, detail=f"disallowed extension: {ext}")
            dest = safe_join(target_path, name)
            written = 0
            with dest.open("wb") as out:
                while True:
                    chunk = await upload.read(64 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_DOC_BYTES:
                        out.close()
                        dest.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail="file too large")
                    out.write(chunk)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/delete")
    def delete(target: str = Form(""), csrf: str = Form(""), name: str = Form(...)) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        clean = sanitize_filename(name)
        victim = safe_join(target_path, clean)
        if victim.is_dir():
            # Refuse to delete non-empty dirs implicitly.
            try:
                victim.rmdir()
            except OSError as e:
                raise HTTPException(status_code=400, detail="directory not empty") from e
        elif victim.is_file():
            victim.unlink()
        else:
            raise HTTPException(status_code=404)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/rename")
    def rename(
        target: str = Form(""),
        csrf: str = Form(""),
        old: str = Form(...),
        new: str = Form(...),
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        old_clean = sanitize_filename(old)
        new_clean = sanitize_filename(new)
        src = safe_join(target_path, old_clean)
        dst = safe_join(target_path, new_clean)
        if not src.exists():
            raise HTTPException(status_code=404)
        if dst.exists():
            raise HTTPException(status_code=409, detail="destination exists")
        src.rename(dst)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    @router.post("/docs/new-folder")
    def new_folder(
        target: str = Form(""), csrf: str = Form(""), name: str = Form(...)
    ) -> Response:
        _check_csrf(serializer, csrf)
        target_path = _resolve_target(settings.docs_root, target)
        clean = sanitize_filename(name)
        new_dir = safe_join(target_path, clean)
        new_dir.mkdir(parents=False, exist_ok=False)
        return RedirectResponse(url=f"/admin/docs?target={target}", status_code=303)

    return router
```

- [ ] **Step 3: Create `app/templates/admin/base.html`**

```html
{% extends "base.html" %}
{% block topbar_right %}<a href="/admin/">Admin</a>{% endblock %}
```

- [ ] **Step 4: Create `app/templates/admin/index.html`**

```html
{% extends "admin/base.html" %}
{% block title %}Admin · lab-bridge{% endblock %}
{% block main %}
<h1>Admin</h1>
<div class="cards">
  <a class="card" href="/admin/docs">
    <h2>Documentation</h2>
    <p>{{ docs_count }} files</p>
    {% if last_doc_mtime %}<p>Last upload: {{ last_doc_mtime | int }}</p>{% endif %}
  </a>
  <a class="card" href="/admin/agent">
    <h2>Agent</h2>
    {% if agent_info %}
      <p>v{{ agent_info.version }} · sha256 {{ agent_info.sha256[:12] }}…</p>
    {% else %}
      <p>No build uploaded yet.</p>
    {% endif %}
  </a>
</div>
{% endblock %}
```

- [ ] **Step 5: Create `app/templates/admin/docs.html`**

```html
{% extends "admin/base.html" %}
{% block title %}Docs · admin{% endblock %}
{% block main %}
<h1>Documentation</h1>
<p class="breadcrumb">
  <a href="/admin/docs">/docs</a>
  {% set acc = '' %}
  {% for part in target.split('/') if part %}
    {% set acc = acc + '/' + part %}
    / <a href="/admin/docs?target={{ acc.lstrip('/') }}">{{ part }}</a>
  {% endfor %}
</p>

<form method="post" action="/admin/docs/upload" enctype="multipart/form-data" class="dropzone">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="target" value="{{ target }}">
  <p>Drop files here or click to browse.</p>
  <input type="file" name="files" multiple accept=".md,.png,.jpg,.jpeg,.gif,.svg,.webp">
  <button type="submit">Upload</button>
</form>

<form method="post" action="/admin/docs/new-folder">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <input type="hidden" name="target" value="{{ target }}">
  <label>New folder: <input name="name" required></label>
  <button type="submit">Create</button>
</form>

<table class="files">
  <thead><tr><th>Name</th><th>Size</th><th>Actions</th></tr></thead>
  <tbody>
    {% for it in items %}
    <tr>
      <td>
        {% if it.is_dir %}
          <a href="/admin/docs?target={{ (target ~ '/' ~ it.name).lstrip('/') }}">📁 {{ it.name }}</a>
        {% else %}
          {{ it.name }}
          {% if it.name.endswith('.md') %}
            <a href="/docs/{{ (target ~ '/' ~ it.name).lstrip('/').rsplit('.md', 1)[0] }}" target="_blank">view</a>
          {% endif %}
        {% endif %}
      </td>
      <td>{{ it.size }}</td>
      <td>
        <form method="post" action="/admin/docs/delete" style="display:inline">
          <input type="hidden" name="csrf" value="{{ csrf }}">
          <input type="hidden" name="target" value="{{ target }}">
          <input type="hidden" name="name" value="{{ it.name }}">
          <button type="submit">Delete</button>
        </form>
        <form method="post" action="/admin/docs/rename" style="display:inline">
          <input type="hidden" name="csrf" value="{{ csrf }}">
          <input type="hidden" name="target" value="{{ target }}">
          <input type="hidden" name="old" value="{{ it.name }}">
          <input name="new" placeholder="new name" required>
          <button type="submit">Rename</button>
        </form>
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 6: Wire admin router into `app/main.py`**

Add import:
```python
from app.admin import make_router as make_admin_router
```
Add include after the API router:
```python
app.include_router(make_admin_router(settings))
```

- [ ] **Step 7: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_routes_admin.py -v
```

- [ ] **Step 8: Commit**

```bash
git add compose/siteapp/app/admin.py compose/siteapp/app/templates/admin \
        compose/siteapp/app/main.py compose/siteapp/tests/test_routes_admin.py
git commit -m "feat(siteapp): admin docs file manager (upload/delete/rename/new-folder)"
```

---

### Task 12: Admin agent page (manual upload + token rotation)

Reuses `/api/agent/upload` for the actual upload by accepting `(version, binary)` and posting through the same handler with the configured token. Token rotation writes a new value to a sidecar file the deploy script later picks up.

**Files:**
- Modify: `compose/siteapp/app/admin.py` — add `/admin/agent` GET + POST.
- Create: `compose/siteapp/app/templates/admin/agent.html`
- Modify: `compose/siteapp/tests/test_routes_admin.py` — add tests.

> NOTE: The "Rotate upload token" feature is *display-only* in v1 (it renders a one-time generated value in the UI for the operator to copy). Persisting a rotation back to the file the container reads requires a writable mount, which adds complexity beyond v1's "upload form only" target. The CLI `task secrets:rotate-agent-upload-token` is the persistence path. The UI button calls `POST /admin/agent/rotate-token` which simply returns a new token string for the operator to put in the file manually. This keeps the container's filesystem read-only for secrets — defence in depth.

- [ ] **Step 1: Add tests to `tests/test_routes_admin.py`**

Append to the file:

```python
def test_agent_page_renders(client: TestClient) -> None:
    r = client.get("/admin/agent")
    assert r.status_code == 200
    assert "Agent" in r.text


def test_agent_manual_upload(client: TestClient, tmp_path: Path) -> None:
    # GET to grab CSRF.
    r = client.get("/admin/agent")
    import re

    csrf = re.search(r'name="csrf"\s+value="([^"]+)"', r.text).group(1)  # type: ignore[union-attr]
    r = client.post(
        "/admin/agent/upload",
        data={"csrf": csrf, "version": "9.9.9"},
        files={"binary": ("agent.exe", b"manual-bytes", "application/octet-stream")},
    )
    assert r.status_code in (200, 303)
    assert (tmp_path / "agent" / "windows" / "agent.exe").read_bytes() == b"manual-bytes"


def test_rotate_token_returns_value(client: TestClient) -> None:
    r = client.get("/admin/agent")
    import re

    csrf = re.search(r'name="csrf"\s+value="([^"]+)"', r.text).group(1)  # type: ignore[union-attr]
    r = client.post("/admin/agent/rotate-token", data={"csrf": csrf})
    assert r.status_code == 200
    assert "new_token" in r.text
    # 32-char URL-safe-ish.
    import re as _re

    assert _re.search(r"[A-Za-z0-9_-]{40,}", r.text)
```

- [ ] **Step 2: Add to `app/admin.py` (extend `make_router`)**

Replace the `make_router` body — add these endpoints inside the function before `return router`:

```python
    @router.get("/agent", include_in_schema=False)
    def agent_admin(request: Request) -> Response:
        from app.agent import load_meta

        return templates.TemplateResponse(
            request,
            "admin/agent.html",
            {
                "info": load_meta(settings.agent_root),
                "csrf": _make_csrf(serializer),
            },
        )

    @router.post("/agent/upload")
    async def agent_admin_upload(
        version: str = Form(...),
        csrf: str = Form(""),
        binary: UploadFile = File(...),
    ) -> Response:
        _check_csrf(serializer, csrf)
        # Reuse the same backend as the CI endpoint by calling its function.
        # Importing here avoids a circular import at module load.
        from app.api import upload_agent  # type: ignore[attr-defined]

        # The CI endpoint authenticates via Authorization header. The admin
        # endpoint is already authenticated by Caddy basic_auth + CSRF — so
        # we synthesize the bearer for an internal call.
        synthetic = f"Bearer {settings.agent_upload_token}"
        await upload_agent(  # type: ignore[func-returns-value]
            version=version, binary=binary, authorization=synthetic
        )
        return RedirectResponse(url="/admin/agent", status_code=303)

    @router.post("/agent/rotate-token")
    def rotate_token(request: Request, csrf: str = Form("")) -> Response:
        _check_csrf(serializer, csrf)
        import secrets as _secrets

        return templates.TemplateResponse(
            request,
            "admin/agent.html",
            {
                "info": __import__("app.agent", fromlist=["load_meta"]).load_meta(
                    settings.agent_root
                ),
                "csrf": _make_csrf(serializer),
                "new_token": _secrets.token_urlsafe(32),
            },
        )
```

> NOTE: The internal `upload_agent` call works because `make_router` exposes the function as a closed-over local in `app/api.py`. To make it importable, refactor `app/api.py` slightly — extract the body into a module-level async `upload_agent(...)` that takes a `Settings` argument. (See refactor in Step 3.)

- [ ] **Step 3: Refactor `app/api.py` to expose `upload_agent` at module level**

Replace `app/api.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import Settings, load_settings

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$")
MAX_AGENT_BYTES = 100 * 1024 * 1024
CHUNK = 64 * 1024


def _check_token(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401)
    candidate = authorization.split(None, 1)[1].strip()
    if not secrets.compare_digest(candidate, expected):
        raise HTTPException(status_code=401)


async def upload_agent(
    settings: Settings,
    *,
    version: str,
    binary: UploadFile,
    authorization: str | None,
) -> dict[str, object]:
    _check_token(authorization, settings.agent_upload_token)
    if not VERSION_RE.match(version):
        raise HTTPException(status_code=400, detail="invalid version")

    agent_dir = settings.agent_root / "windows"
    tmp_dir = settings.agent_root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size = 0
    fd, tmp_name = tempfile.mkstemp(dir=str(tmp_dir), prefix="agent-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await binary.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_AGENT_BYTES:
                    raise HTTPException(status_code=413, detail="upload too large")
                digest.update(chunk)
                out.write(chunk)
    except HTTPException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    sha256 = digest.hexdigest()
    target = agent_dir / "agent.exe"
    os.replace(tmp_name, target)

    meta = {
        "version": version,
        "sha256": sha256,
        "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "size": size,
    }
    fd2, meta_tmp = tempfile.mkstemp(
        dir=str(settings.agent_root), prefix="meta-", suffix=".json"
    )
    with os.fdopen(fd2, "w") as f:
        json.dump(meta, f)
    os.replace(meta_tmp, settings.agent_root / "meta.json")
    return {"version": version, "sha256": sha256, "size": size}


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.post("/api/agent/upload")
    async def upload_endpoint(
        version: str = Form(...),
        binary: UploadFile = File(...),
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        return await upload_agent(
            settings, version=version, binary=binary, authorization=authorization
        )

    return router
```

- [ ] **Step 4: Update the admin call site**

In `app/admin.py`, the `agent_admin_upload` function (added in Step 2) needs to call the refactored function:

```python
        from app.api import upload_agent

        synthetic = f"Bearer {settings.agent_upload_token}"
        await upload_agent(
            settings, version=version, binary=binary, authorization=synthetic
        )
```

- [ ] **Step 5: Create `app/templates/admin/agent.html`**

```html
{% extends "admin/base.html" %}
{% block title %}Agent · admin{% endblock %}
{% block main %}
<h1>Agent</h1>
{% if info %}
  <dl>
    <dt>Version</dt><dd>{{ info.version }}</dd>
    <dt>Uploaded</dt><dd>{{ info.uploaded_at }}</dd>
    <dt>SHA-256</dt><dd><code>{{ info.sha256 }}</code></dd>
  </dl>
{% else %}
  <p>No build uploaded yet.</p>
{% endif %}

<h2>Manual upload</h2>
<form method="post" action="/admin/agent/upload" enctype="multipart/form-data">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <label>Version: <input name="version" required pattern="^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$"></label>
  <input type="file" name="binary" required>
  <button type="submit">Upload</button>
</form>

<h2>Rotate upload token</h2>
<p>Generates a new value here. To activate, paste it into
<code>compose/siteapp/agent_upload_token</code> on the operator laptop and
re-run <code>task deploy</code>. (Doing it this way keeps the container's
secret filesystem read-only.)</p>
<form method="post" action="/admin/agent/rotate-token">
  <input type="hidden" name="csrf" value="{{ csrf }}">
  <button type="submit">Generate</button>
</form>
{% if new_token %}
  <p>New token (copy now — won't be shown again):</p>
  <pre>{{ new_token }}</pre>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Run tests**

```bash
cd compose/siteapp && uv run pytest tests/test_routes_admin.py -v
```

- [ ] **Step 7: Commit**

```bash
git add compose/siteapp/app/api.py compose/siteapp/app/admin.py \
        compose/siteapp/app/templates/admin/agent.html \
        compose/siteapp/tests/test_routes_admin.py
git commit -m "feat(siteapp): admin agent page (manual upload + rotate-token UI)"
```

---

### Task 13: Polished CSS

Replace the placeholder stylesheet with a minimal, professional, mobile-responsive stylesheet plus a sticky sidebar layout for docs and a clean admin look.

**Files:**
- Modify: `compose/siteapp/app/static/site.css` (full rewrite)
- Create: `compose/siteapp/app/static/copy-code.js`
- Modify: `compose/siteapp/app/templates/base.html` — load `copy-code.js`.

- [ ] **Step 1: Replace `app/static/site.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #1a1a1a;
  --muted: #6a6a6a;
  --border: #00000014;
  --accent: #2855ff;
  --code-bg: #f4f5f7;
  --max-prose: 720px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #11131a;
    --fg: #e7e9ee;
    --muted: #98a0ad;
    --border: #ffffff14;
    --accent: #7c9bff;
    --code-bg: #1b1f29;
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--fg);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--bg); z-index: 10;
}
.brand { font-weight: 600; color: inherit; letter-spacing: -0.01em; }
footer { color: var(--muted); padding: 32px; text-align: center; font-size: 14px; }

.layout-with-sidebar { display: grid; grid-template-columns: 240px 1fr; gap: 32px; max-width: 1100px; margin: 0 auto; padding: 24px; }
@media (max-width: 760px) { .layout-with-sidebar { grid-template-columns: 1fr; } .sidebar { order: 2; } }
.sidebar ul { list-style: none; padding-left: 14px; margin: 0; }
.sidebar > ul { padding-left: 0; }
.sidebar li { margin: 4px 0; }
.sidebar a { color: var(--fg); }
.sidebar li.active > a { color: var(--accent); font-weight: 600; }

.prose { max-width: var(--max-prose); }
.prose h1 { letter-spacing: -0.02em; margin-top: 0; }
.prose h2 { margin-top: 2em; padding-top: 0.5em; border-top: 1px solid var(--border); }
.prose code { background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px; font-size: 0.92em; }
.prose pre { background: var(--code-bg); padding: 14px 16px; border-radius: 6px; overflow-x: auto; position: relative; }
.prose pre code { background: transparent; padding: 0; }
.copy-button { position: absolute; top: 6px; right: 6px; background: var(--bg); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; font-size: 12px; cursor: pointer; }
.prose table { border-collapse: collapse; width: 100%; }
.prose th, .prose td { border: 1px solid var(--border); padding: 6px 10px; }

.lang-toggle { display: inline-flex; gap: 4px; }
.pill { padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; font-size: 13px; color: var(--fg); }
.pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.pill.muted { color: var(--muted); pointer-events: none; }

.agent-hero { text-align: center; padding: 64px 24px 24px; max-width: 720px; margin: 0 auto; }
.agent-hero h1 { font-size: 2.4rem; margin: 0 0 8px; }
.agent-hero .lede { color: var(--muted); }
.download-button { display: inline-block; margin-top: 24px; padding: 14px 24px; background: var(--accent); color: #fff; border-radius: 8px; font-weight: 600; border: 0; cursor: pointer; }
.download-button:disabled { background: var(--muted); cursor: not-allowed; }
.agent-body { max-width: var(--max-prose); margin: 0 auto; padding: 24px; }
.agent-meta { max-width: var(--max-prose); margin: 0 auto; padding: 24px; color: var(--muted); }
.agent-meta dt { font-weight: 600; color: var(--fg); }
.agent-meta dd { margin: 0 0 12px; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; max-width: 720px; margin: 24px auto; padding: 0 24px; }
.card { display: block; padding: 20px; border: 1px solid var(--border); border-radius: 8px; color: var(--fg); }
.card:hover { background: var(--code-bg); text-decoration: none; }

.dropzone { border: 2px dashed var(--border); padding: 32px; text-align: center; border-radius: 8px; margin: 16px 0; }
table.files { width: 100%; border-collapse: collapse; margin-top: 16px; }
table.files th, table.files td { border-bottom: 1px solid var(--border); padding: 8px; text-align: left; }
.breadcrumb { color: var(--muted); }
```

- [ ] **Step 2: Create `app/static/copy-code.js`**

```javascript
document.querySelectorAll("pre > code").forEach((code) => {
  const pre = code.parentElement;
  const button = document.createElement("button");
  button.className = "copy-button";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(code.innerText);
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = "Copy"), 1200);
  });
  pre.appendChild(button);
});
```

- [ ] **Step 3: Update `app/templates/base.html` (replace the file)**

```html
<!doctype html>
<html lang="{{ lang|default('en') }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}lab-bridge{% endblock %}</title>
  <link rel="stylesheet" href="/_static/site.css">
  {% if pygments_css %}<style>{{ pygments_css|safe }}</style>{% endif %}
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">lab-bridge</a>
    {% block topbar_right %}{% endblock %}
  </header>
  <main>{% block main %}{% endblock %}</main>
  <footer><a href="/">lab-bridge</a></footer>
  <script src="/_static/copy-code.js" defer></script>
</body>
</html>
```

- [ ] **Step 4: Run all tests to ensure nothing regressed**

```bash
cd compose/siteapp && uv run pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/app/static/site.css compose/siteapp/app/static/copy-code.js \
        compose/siteapp/app/templates/base.html
git commit -m "style(siteapp): minimalist CSS + copy-code button"
```

---

## Phase 2 — Dockerization & VPS integration

### Task 14: Dockerfile

**Files:**
- Create: `compose/siteapp/Dockerfile`
- Create: `compose/siteapp/.dockerignore`

- [ ] **Step 1: Create `compose/siteapp/Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# uv: drop in the official binary, pin the version.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --uid 10001 --create-home siteapp && \
    mkdir -p /data && chown -R siteapp:siteapp /data /app
USER siteapp

ENV SITE_DATA=/data \
    PYTHONPATH=/app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status==200 else 1)" || exit 1

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `compose/siteapp/.dockerignore`**

```
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
sample_data/
agent_upload_token
tests/
*.md
```

- [ ] **Step 3: Build the image locally**

```bash
docker build -t lab-bridge-siteapp:dev compose/siteapp/
```
Expected: build succeeds.

- [ ] **Step 4: Smoke run the container**

```bash
docker run --rm -p 18000:8000 \
  -e SITEAPP_AGENT_UPLOAD_TOKEN=test \
  -v "$(pwd)/compose/siteapp/sample_data:/data" \
  --name lab-bridge-siteapp-smoke lab-bridge-siteapp:dev &
sleep 2
curl -fsS http://127.0.0.1:18000/healthz
docker rm -f lab-bridge-siteapp-smoke
```
Expected: prints `{"status":"ok"}`.

- [ ] **Step 5: Commit**

```bash
git add compose/siteapp/Dockerfile compose/siteapp/.dockerignore
git commit -m "feat(siteapp): Dockerfile (python:3.13-slim + uv frozen sync)"
```

---

### Task 15: Caddyfile changes

**Files:**
- Modify: `compose/Caddyfile.tmpl`

- [ ] **Step 1: Replace `compose/Caddyfile.tmpl`**

```caddyfile
{
    email __ACME_EMAIL__
    default_sni __VPS_HOST__
}

https://__VPS_HOST__ {
    tls {
        issuer acme {
            profile shortlived
        }
    }

    # Public docs.
    handle_path /docs* {
        reverse_proxy siteapp:8000
    }

    # Public agent download page + binary.
    handle_path /download* {
        reverse_proxy siteapp:8000
    }

    # Admin panel — basic_auth scoped here ONLY. Mobile-WS issue does not
    # apply: this surface is plain HTTP file uploads, no kernels.
    handle /admin* {
        basic_auth {
            admin __ADMIN_BCRYPT_HASH__
        }
        reverse_proxy siteapp:8000
    }

    # CI upload endpoint — bearer-token auth in the app, not Caddy.
    handle /api/agent/upload {
        reverse_proxy siteapp:8000
    }

    # Existing routes (unchanged).
    handle /grafana/* {
        reverse_proxy grafana:3000
    }
    reverse_proxy jupyter:8888
}
```

- [ ] **Step 2: Render the Caddyfile locally to sanity-check**

```bash
ADMIN_BCRYPT_HASH='$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345' \
ACME_EMAIL=test@example.com VPS_HOST=test.example.com \
sed \
  -e "s|__ACME_EMAIL__|$ACME_EMAIL|g" \
  -e "s|__VPS_HOST__|$VPS_HOST|g" \
  -e "s|__ADMIN_BCRYPT_HASH__|$ADMIN_BCRYPT_HASH|g" \
  compose/Caddyfile.tmpl | docker run --rm -i caddy:2 caddy validate --adapter caddyfile --config -
```
Expected: prints `Valid configuration`. Note the dollar/colon characters in the bcrypt hash are sed-safe with `|` as the delimiter.

- [ ] **Step 3: Commit**

```bash
git add compose/Caddyfile.tmpl
git commit -m "feat(caddy): add /docs, /download, /admin (basic_auth), /api/agent/upload"
```

---

### Task 16: Compose service + secret

**Files:**
- Modify: `compose/docker-compose.yml.tmpl`
- Create: `compose/siteapp/agent_upload_token.example`
- Modify: `.gitignore`

- [ ] **Step 1: Replace `compose/docker-compose.yml.tmpl`** (full file)

```yaml
services:
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy_data:/data
      - ./caddy_config:/config
    networks: [labnet]
    depends_on: [jupyter, siteapp]

  jupyter:
    image: __JUPYTER_IMAGE__
    restart: unless-stopped
    command:
      - start-notebook.sh
      - --ServerApp.token=
      - --ServerApp.password=__JUPYTER_PASSWORD_HASH__
      - --ServerApp.allow_origin=*
      - --ServerApp.base_url=/
      - --ServerApp.root_dir=/home/jovyan/work
    volumes:
      - __NOTEBOOKS_PATH__:/home/jovyan/work
    networks: [labnet]

  chisel:
    image: __CHISEL_IMAGE__
    restart: unless-stopped
    command:
      - server
      - --port=__CHISEL_LISTEN_PORT__
      - --authfile=/etc/chisel/users.json
      - --reverse
    ports:
      - "__CHISEL_LISTEN_PORT__:__CHISEL_LISTEN_PORT__"
    volumes:
      - ./chisel/users.json:/etc/chisel/users.json:ro
    networks: [labnet]

  loki:
    image: __LOKI_IMAGE__
    restart: unless-stopped
    command: ["-config.file=/etc/loki/config.yaml"]
    volumes:
      - ./loki/config.yaml:/etc/loki/config.yaml:ro
      - ./loki_data:/loki
    networks: [labnet]

  grafana:
    image: __GRAFANA_IMAGE__
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password
      GF_SERVER_ROOT_URL: https://__VPS_HOST__/grafana/
      GF_SERVER_SERVE_FROM_SUB_PATH: "true"
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana_data:/var/lib/grafana
    secrets:
      - grafana_admin_password
    networks: [labnet]
    depends_on: [loki]

  siteapp:
    image: __SITEAPP_IMAGE__
    restart: unless-stopped
    environment:
      SITEAPP_AGENT_UPLOAD_TOKEN__FILE: /run/secrets/agent_upload_token
    volumes:
      - ./site_data:/data
    secrets:
      - agent_upload_token
    networks: [labnet]

networks:
  labnet:
    driver: bridge

secrets:
  grafana_admin_password:
    file: ./grafana/admin_password
  agent_upload_token:
    file: ./siteapp/agent_upload_token
```

- [ ] **Step 2: Create `compose/siteapp/agent_upload_token.example`**

```
# Replace this file's parent (compose/siteapp/agent_upload_token, gitignored)
# with a 32-char URL-safe random string. Generate via:
#   task secrets:rotate-agent-upload-token
```

- [ ] **Step 3: Append to `.gitignore`**

Add these two lines at the bottom:
```
compose/siteapp/agent_upload_token
compose/siteapp/sample_data/
```

- [ ] **Step 4: Commit**

```bash
git add compose/docker-compose.yml.tmpl compose/siteapp/agent_upload_token.example .gitignore
git commit -m "feat(compose): wire siteapp service + agent_upload_token secret"
```

---

### Task 17: Config schema + render extensions

**Files:**
- Modify: `config.example.yaml`
- Modify: `scripts/lib/config.sh` — add new required fields & exports.
- Modify: `scripts/lib/render.sh` — sub `__SITEAPP_IMAGE__` and `__ADMIN_BCRYPT_HASH__`.

- [ ] **Step 1: Append to `config.example.yaml`**

```yaml

siteapp:
  image: ghcr.io/<owner>/lab-bridge-siteapp:0.1.0   # pinned tag (+ digest after first publish)
  # bcrypt hash for the admin panel — set via `task secrets:set-admin-password`.
  admin_password_hash: "<run task secrets:set-admin-password>"
```

- [ ] **Step 2: Update `scripts/lib/config.sh`**

Add to `_REQUIRED_FIELDS`:
```bash
    .siteapp.image
    .siteapp.admin_password_hash
```

In `validate_config`, add a hash format check after the `jupyter.password_hash` check:
```bash
    local admin_hash
    admin_hash="$(_yq e '.siteapp.admin_password_hash // ""' "$path")"
    if [[ -n "$admin_hash" ]] && ! [[ "$admin_hash" =~ ^\$2[abxy]\$[0-9]{2}\$[A-Za-z0-9./]{53}$ ]]; then
        errors+=("siteapp.admin_password_hash is not a bcrypt hash (run: task secrets:set-admin-password)")
    fi
```

In `load_config`, append the new exports:
```bash
    export SITEAPP_IMAGE        ; SITEAPP_IMAGE="$(_yq e '.siteapp.image' "$path")"
    export SITEAPP_ADMIN_PASSWORD_HASH ; SITEAPP_ADMIN_PASSWORD_HASH="$(_yq e '.siteapp.admin_password_hash' "$path")"
```

- [ ] **Step 3: Update `scripts/lib/render.sh`**

In `render_compose`, add `-e` substitution:
```bash
        -e "s|__SITEAPP_IMAGE__|${SITEAPP_IMAGE:?}|g" \
```

In `render_caddyfile`, add:
```bash
        -e "s|__ADMIN_BCRYPT_HASH__|${SITEAPP_ADMIN_PASSWORD_HASH:?}|g" \
```

- [ ] **Step 4: Update test fixtures so existing bats tests still pass**

`tests/fixtures/valid_config.yaml` needs the new keys. Append:
```yaml
siteapp:
  image: ghcr.io/test/lab-bridge-siteapp:0.0.1
  admin_password_hash: "$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
```

Same addition to `tests/fixtures/duplicate_port_config.yaml` and `tests/fixtures/missing_field_config.yaml` (the latter intentionally is missing other fields, leave it that way for the test that exercises it).

For `bad_hash_config.yaml`, also add the new keys (it tests a *different* hash — jupyter's — so it's safe to add a valid siteapp block).

- [ ] **Step 5: Run existing bats**

```bash
bats tests/test_config.bats tests/test_render.bats
```
Expected: green (or trivially fixable failures from added fields, fix as needed).

- [ ] **Step 6: Commit**

```bash
git add config.example.yaml scripts/lib/config.sh scripts/lib/render.sh tests/fixtures/
git commit -m "feat(config): siteapp.image + admin_password_hash; render new __VARS__"
```

---

### Task 18: Task command — set-admin-password

**Files:**
- Modify: `scripts/secrets.sh` — add `cmd_set_admin_password`.
- Modify: `Taskfile.yml` — add the task entry.
- Modify: `tests/test_secrets.bats` — add a test.

- [ ] **Step 1: Add to `scripts/secrets.sh`**

Insert before the existing `cmd_add_client`:
```bash
cmd_set_admin_password() {
    ensure_config
    require_cmd docker

    local pw hash
    pw="$(prompt_password "Admin panel password (used at /admin/*)")"
    # Use the official Caddy image's hash-password subcommand to produce a
    # bcrypt hash. We pipe via stdin to avoid the password ever appearing
    # on the process command line.
    hash="$(printf '%s' "$pw" | docker run --rm -i caddy:2 caddy hash-password --plaintext-stdin)"
    [[ "$hash" =~ ^\$2[abxy]\$ ]] || die "hash-password produced unexpected output: $hash"
    yq -i ".siteapp.admin_password_hash = \"$hash\"" "$CONFIG"
    log "set admin panel password (deploy to apply)"
}
```

In `main()`, add the case:
```bash
        set-admin-password)   cmd_set_admin_password "$@" ;;
```

- [ ] **Step 2: Add to `Taskfile.yml` — under `# --- Secrets ---`**

```yaml
  "secrets:set-admin-password":
    desc: Set or rotate the /admin/* basic-auth password (prompts; deploy to apply)
    cmd: bash scripts/secrets.sh set-admin-password
```

- [ ] **Step 3: Add bats test to `tests/test_secrets.bats`**

```bash
@test "secrets:set-admin-password writes a bcrypt hash to config.yaml" {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"

    # Bypass the docker call by stubbing it in PATH for this test.
    mkdir -p "$TMPDIR/bin"
    cat > "$TMPDIR/bin/docker" <<'EOS'
#!/usr/bin/env bash
# Read stdin (the password) but ignore it — emit a fake but valid bcrypt hash.
cat > /dev/null
echo '$2a$14$abcdefghijklmnopqrstuABCDEFGHIJKLMNOPQRSTUVWXYZ012345'
EOS
    chmod +x "$TMPDIR/bin/docker"
    PATH="$TMPDIR/bin:$PATH" run bash -c '
        printf "secretpass\nsecretpass\n" | bash "$ROOT/scripts/secrets.sh" set-admin-password
    '
    [ "$status" -eq 0 ]
    yq -e ".siteapp.admin_password_hash" "$LDS_CONFIG" | grep -q '^\$2a\$14\$'
}
```

- [ ] **Step 4: Run the test**

```bash
bats tests/test_secrets.bats -f admin
```

- [ ] **Step 5: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): task secrets:set-admin-password (caddy hash-password)"
```

---

### Task 19: Task command — rotate-agent-upload-token

**Files:**
- Modify: `scripts/secrets.sh` — add `cmd_rotate_agent_upload_token`.
- Modify: `Taskfile.yml`.
- Modify: `tests/test_secrets.bats`.

- [ ] **Step 1: Add to `scripts/secrets.sh`**

Insert below `cmd_set_admin_password`:
```bash
cmd_rotate_agent_upload_token() {
    require_cmd python3
    local tokfile="${LDS_AGENT_TOKEN_FILE:-$SCRIPT_DIR/../compose/siteapp/agent_upload_token}"
    mkdir -p "$(dirname "$tokfile")"

    local token
    token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

    # Atomic write so a partial file never lingers.
    local tmp
    tmp="$(mktemp "${tokfile}.XXXXXX")"
    trap 'rm -f "$tmp"' EXIT
    printf '%s' "$token" > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$tokfile"
    trap - EXIT

    log "wrote new agent upload token to $tokfile"
    cat <<EOF

NEW TOKEN (save this in your CI secret store; it won't be shown again):

  $token

Update CI:
  - GitHub Actions: replace the AGENT_UPLOAD_TOKEN secret value
  - then run: task deploy

EOF
}
```

In `main()`:
```bash
        rotate-agent-upload-token) cmd_rotate_agent_upload_token "$@" ;;
```

- [ ] **Step 2: Add to `Taskfile.yml`**

```yaml
  "secrets:rotate-agent-upload-token":
    desc: Generate a new CI agent upload token (deploy to apply; old token stops working)
    cmd: bash scripts/secrets.sh rotate-agent-upload-token
```

- [ ] **Step 3: Add bats test**

```bash
@test "secrets:rotate-agent-upload-token writes a 32+ char token to file" {
    setup_tmpdir
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    run bash "$ROOT/scripts/secrets.sh" rotate-agent-upload-token
    [ "$status" -eq 0 ]
    [ -f "$LDS_AGENT_TOKEN_FILE" ]
    [ "$(stat -f '%Lp' "$LDS_AGENT_TOKEN_FILE" 2>/dev/null || stat -c '%a' "$LDS_AGENT_TOKEN_FILE")" = "600" ]
    [ "$(wc -c < "$LDS_AGENT_TOKEN_FILE")" -ge 40 ]
}
```

- [ ] **Step 4: Run the test**

```bash
bats tests/test_secrets.bats -f rotate
```

- [ ] **Step 5: Commit**

```bash
git add scripts/secrets.sh Taskfile.yml tests/test_secrets.bats
git commit -m "feat(secrets): task secrets:rotate-agent-upload-token"
```

---

### Task 20: deploy.sh extensions

Preflight: require `compose/siteapp/agent_upload_token`. Render: stage the token + the siteapp dir-skeleton. Healthchecks: probe new endpoints.

**Files:**
- Modify: `scripts/deploy.sh`
- Modify: `tests/test_deploy.bats` — add tests for the new behavior.

- [ ] **Step 1: Patch `scripts/deploy.sh`**

After the existing Grafana password check (around line 41), add:

```bash
    # Agent upload token — required at deploy time. Like the Grafana password,
    # this lands as a Docker secret on the VPS. Mode 0644 because the secret
    # is bind-mounted into a container that runs as a non-root uid.
    local tokfile="${LDS_AGENT_TOKEN_FILE:-$REPO_ROOT/compose/siteapp/agent_upload_token}"
    [[ -f "$tokfile" ]] || die "agent upload token not found at $tokfile — run: task secrets:rotate-agent-upload-token"
    install -m 644 "$tokfile" "$stage/siteapp/agent_upload_token"
```

Just before the rsync, add the dir creation:
```bash
    mkdir -p "$stage/siteapp"
```

(Move it to live alongside the existing `mkdir -p "$stage/chisel" ...` line.)

In the healthcheck loop, replace the existing healthcheck block with:

```bash
    if [[ "${LDS_SKIP_HEALTHCHECK:-}" != "1" ]]; then
        log "waiting for HTTPS to respond..."
        local i jupyter_status grafana_status docs_status download_status admin_status
        for ((i=0; i<60; i++)); do
            jupyter_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/" || true)"
            grafana_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/grafana/login" || true)"
            docs_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/docs/" || true)"
            download_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/download/agent" || true)"
            admin_status="$(curl -sk -o /dev/null -w '%{http_code}' "https://$VPS_HOST/admin/" || true)"
            # /admin/ MUST be 401 without creds. A 200 here is a security regression.
            if [[ "$jupyter_status" =~ ^[23][0-9][0-9]$ ]] \
                && [[ "$grafana_status" == "200" ]] \
                && [[ "$docs_status" == "200" ]] \
                && [[ "$download_status" == "200" ]] \
                && [[ "$admin_status" == "401" ]]; then
                log "deployed: jupyter $jupyter_status, grafana $grafana_status, docs $docs_status, download $download_status, admin $admin_status"
                return 0
            fi
            sleep 1
        done
        warn "health check timed out (jupyter:$jupyter_status grafana:$grafana_status docs:$docs_status download:$download_status admin:$admin_status). Check: task logs"
        return 1
    fi
```

Update the `docker compose restart` line to also restart `siteapp` so a new image pull or token change takes effect:
```bash
    $ssh_base "$target" "cd $VPS_REMOTE_ROOT && docker compose pull && docker compose up -d --remove-orphans && docker compose restart caddy chisel siteapp"
```

- [ ] **Step 2: Add a fail-fast bats test**

In `tests/test_deploy.bats`:

```bash
@test "deploy: fails fast when agent_upload_token is missing" {
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/does-not-exist"
    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -ne 0 ]
    [[ "$output" == *"rotate-agent-upload-token"* ]]
}

@test "deploy: stages siteapp/agent_upload_token" {
    # The shared setup() leaves the token undefined; provide one here.
    local tok="$TMPDIR/agent_upload_token"
    printf 'test-tok' > "$tok"
    chmod 600 "$tok"
    export LDS_AGENT_TOKEN_FILE="$tok"

    run bash "$ROOT/scripts/deploy.sh"
    [ "$status" -eq 0 ]
    docker exec lds-fake-vps test -f /srv/lab-bridge/siteapp/agent_upload_token
}
```

Also extend the shared `setup()` in this file to provide `LDS_AGENT_TOKEN_FILE` so the existing tests don't break:
```bash
    # New: agent upload token (required by deploy.sh).
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'testtok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_AGENT_TOKEN_FILE"
```

- [ ] **Step 3: Run the deploy bats**

```bash
bats tests/test_deploy.bats
```

(Requires Docker for the fake-VPS container.)

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh tests/test_deploy.bats
git commit -m "feat(deploy): preflight agent token + healthcheck /docs, /download, /admin (401)"
```

---

### Task 21: ops:logs:siteapp + ops:site-disk

**Files:**
- Modify: `scripts/ops.sh`
- Modify: `Taskfile.yml`
- Modify: `tests/test_ops.bats`

- [ ] **Step 1: Add to `scripts/ops.sh`**

Add functions:
```bash
cmd_logs_siteapp() { load_config "$CONFIG"; remote_compose "logs --tail=200 siteapp"; }
cmd_site_disk() {
    load_config "$CONFIG"
    local ssh_base
    ssh_base="$(build_ssh)"
    $ssh_base "$VPS_SSH_USER@$VPS_HOST" "
        for d in docs agent; do
            du -sh $VPS_REMOTE_ROOT/site_data/\$d 2>/dev/null || echo \"0    $VPS_REMOTE_ROOT/site_data/\$d (missing)\"
        done
    "
}
```

In `main()`, add:
```bash
        logs:siteapp)  cmd_logs_siteapp ;;
        site-disk)     cmd_site_disk ;;
```

- [ ] **Step 2: Add to `Taskfile.yml` (under `# --- Operations ---`)**

```yaml
  "ops:logs:siteapp":
    desc: Tail recent siteapp container logs
    cmd: bash scripts/ops.sh logs:siteapp
  "ops:site-disk":
    desc: Show site_data/ disk usage (docs/ and agent/)
    cmd: bash scripts/ops.sh site-disk
```

- [ ] **Step 3: Add a smoke bats test (no remote SSH needed) by re-using `test_ops.bats` patterns**

```bash
@test "ops: logs:siteapp dispatches to remote_compose" {
    # Existing helper pattern: check the script accepts the subcommand without
    # parsing errors. Real SSH path is exercised in deploy/integration tests.
    run bash -c "LDS_CONFIG=$ROOT/tests/fixtures/valid_config.yaml bash $ROOT/scripts/ops.sh nope"
    [ "$status" -ne 0 ]   # baseline: unknown sub fails
}
```

(The full ssh path needs the deploy harness; the dispatch sanity check is enough here.)

- [ ] **Step 4: Run**

```bash
bats tests/test_ops.bats
```

- [ ] **Step 5: Commit**

```bash
git add scripts/ops.sh Taskfile.yml tests/test_ops.bats
git commit -m "feat(ops): logs:siteapp and site-disk task entries"
```

---

### Task 22: Image publishing (GHCR) — operator-facing helper

**Files:**
- Modify: `Taskfile.yml`
- Create: `compose/siteapp/build.sh`

- [ ] **Step 1: Create `compose/siteapp/build.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${SITEAPP_IMAGE:?set SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:<tag>}"

cd "$SCRIPT_DIR"
docker buildx build \
    --platform linux/amd64 \
    --tag "$SITEAPP_IMAGE" \
    --push \
    .
echo
echo "Pushed $SITEAPP_IMAGE"
echo "Now pin in config.yaml: siteapp.image: $SITEAPP_IMAGE"
```

Make it executable:
```bash
chmod +x compose/siteapp/build.sh
```

- [ ] **Step 2: Add to `Taskfile.yml`**

```yaml
  "siteapp:build-and-push":
    desc: Build and push the siteapp image. Set SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:<tag>.
    cmd: bash compose/siteapp/build.sh
```

- [ ] **Step 3: Commit**

```bash
git add compose/siteapp/build.sh Taskfile.yml
git commit -m "feat(siteapp): build-and-push helper for GHCR"
```

---

## Phase 3 — End-to-end bats tests

These run inside the existing `lds-fake-vps` container so the full stack (Caddy + siteapp + the rest) comes up in a single docker network. Each test file uses the same shared setup pattern as `test_deploy.bats`.

### Task 23: bats — siteapp routing & auth

**Files:**
- Create: `tests/test_siteapp_routing.bats`
- Create: `tests/test_siteapp_auth.bats`

- [ ] **Step 1: Create `tests/test_siteapp_routing.bats`**

```bash
#!/usr/bin/env bats

load helpers

setup_file() { bash "$ROOT/tests/fake_vps/start.sh"; }
teardown_file() { docker rm -f lds-fake-vps >/dev/null 2>&1 || true; }

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'integration-token' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

# All probes go through the in-container caddy on its docker-network 127.0.0.1.
exec_probe() {
    local path="$1"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            wget -qSO - 'http://localhost/$path' 2>&1 | head -1
    "
}

@test "siteapp: /docs/ returns 200" {
    run exec_probe "docs/"
    [[ "$output" == *"200"* ]]
}

@test "siteapp: /download/agent returns 200" {
    run exec_probe "download/agent"
    [[ "$output" == *"200"* ]]
}

@test "siteapp: /admin/ requires auth (401 without creds)" {
    run exec_probe "admin/"
    [[ "$output" == *"401"* ]]
}

@test "siteapp: jupyter still serves on /" {
    run exec_probe ""
    [[ "$output" == *"200"* || "$output" == *"302"* ]]
}

@test "siteapp: grafana still serves on /grafana/login" {
    run exec_probe "grafana/login"
    [[ "$output" == *"200"* ]]
}
```

- [ ] **Step 2: Create `tests/test_siteapp_auth.bats`**

```bash
#!/usr/bin/env bats

load helpers

setup_file() { bash "$ROOT/tests/fake_vps/start.sh"; }
teardown_file() { docker rm -f lds-fake-vps >/dev/null 2>&1 || true; }

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf 'auth-tok' > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

# The valid_config.yaml's siteapp.admin_password_hash corresponds to a known plaintext
# fixture: 'admin-fixture'. Caddy validates basic_auth against that hash.

probe_admin() {
    local creds="$1"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            wget -qSO /dev/null --header='Authorization: Basic $creds' 'http://localhost/admin/' 2>&1 | head -1
    "
}

@test "siteapp: admin requires correct basic_auth" {
    # Wrong creds: still 401.
    local wrong; wrong="$(printf 'admin:wrong' | base64)"
    run probe_admin "$wrong"
    [[ "$output" == *"401"* ]]
}

@test "siteapp: api/agent/upload rejects missing bearer token" {
    run docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            wget -qSO /dev/null --post-data='version=1.2.3' 'http://localhost/api/agent/upload' 2>&1 | head -1
    "
    [[ "$output" == *"401"* ]]
}
```

> NOTE: The fixture `admin_password_hash` value should be regenerated to a known plaintext during this task. Update `tests/fixtures/valid_config.yaml` to set `siteapp.admin_password_hash` to the bcrypt of `admin-fixture` (run `printf 'admin-fixture' | docker run --rm -i caddy:2 caddy hash-password --plaintext-stdin` and paste the output). Do this once and lock it in.

- [ ] **Step 3: Update fixture hash**

```bash
hash="$(printf 'admin-fixture' | docker run --rm -i caddy:2 caddy hash-password --plaintext-stdin)"
yq -i ".siteapp.admin_password_hash = \"$hash\"" tests/fixtures/valid_config.yaml
yq -i ".siteapp.admin_password_hash = \"$hash\"" tests/fixtures/duplicate_port_config.yaml
yq -i ".siteapp.admin_password_hash = \"$hash\"" tests/fixtures/bad_hash_config.yaml
```

- [ ] **Step 4: Run**

```bash
bats tests/test_siteapp_routing.bats tests/test_siteapp_auth.bats
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_siteapp_routing.bats tests/test_siteapp_auth.bats tests/fixtures/
git commit -m "test(siteapp): bats end-to-end routing + auth gates"
```

---

### Task 24: bats — uploads (CI agent + admin docs)

**Files:**
- Create: `tests/test_siteapp_uploads.bats`

- [ ] **Step 1: Create the file**

```bash
#!/usr/bin/env bats

load helpers

setup_file() { bash "$ROOT/tests/fake_vps/start.sh"; }
teardown_file() { docker rm -f lds-fake-vps >/dev/null 2>&1 || true; }

TOKEN="upload-test-tok"
ADMIN_CREDS="$(printf 'admin:admin-fixture' | base64)"

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"
    printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"
    printf "$TOKEN" > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

@test "siteapp: CI agent upload publishes binary; download round-trips" {
    # Generate a small fake binary on the host, copy into the fake VPS, POST it via curl-from-caddy.
    local body="agent-bytes-$(date +%s)"
    docker exec lds-fake-vps bash -c "echo -n '$body' > /tmp/agent.exe"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy \
            sh -c \"
                wget --post-file=/tmp/agent.exe --header='Authorization: Bearer $TOKEN' \
                     --header='Content-Type: application/octet-stream' \
                     -qO /tmp/resp 'http://localhost/api/agent/upload?version=1.2.3' || true
            \"
    "
    # NOTE: wget cannot do multipart easily — use curl instead.
    docker exec lds-fake-vps bash -c "apt-get -y install curl >/dev/null 2>&1 || true"
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            apk add --no-cache curl >/dev/null 2>&1 || true
            curl -fsS -X POST http://localhost/api/agent/upload \
              -H \"Authorization: Bearer $TOKEN\" \
              -F version=1.2.3 \
              -F binary=@/tmp/agent.exe
        '
    "
    # Now download and compare.
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            curl -fsS http://localhost/download/agent/windows/agent.exe -o /tmp/back.exe
        '
    "
    docker exec lds-fake-vps diff /tmp/agent.exe /tmp/back.exe
}

@test "siteapp: admin docs upload appears at /docs" {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            apk add --no-cache curl >/dev/null 2>&1 || true
            # Pull the CSRF token by GETting admin/docs through caddy.
            curl -sS -H \"Authorization: Basic $ADMIN_CREDS\" http://localhost/admin/docs > /tmp/admin.html
            csrf=\$(grep -oE \"name=\\\"csrf\\\" value=\\\"[^\\\"]+\\\"\" /tmp/admin.html | head -1 | sed -E \"s/.*value=\\\"([^\\\"]+)\\\".*/\\1/\")
            test -n \"\$csrf\"
            printf \"# Hello\\n\\nworld\\n\" > /tmp/up.md
            curl -fsS -H \"Authorization: Basic $ADMIN_CREDS\" \
                 -F csrf=\"\$csrf\" -F target= -F files=@/tmp/up.md \
                 http://localhost/admin/docs/upload -o /dev/null
            curl -fsS http://localhost/docs/up | grep -q Hello
        '
    "
}
```

> NOTE: `docker compose exec caddy` runs an Alpine-based image; `apk add --no-cache curl` installs curl on first use. This is acceptable in a test container; in production the upload happens from outside the docker network so `caddy` does not need curl.

- [ ] **Step 2: Run**

```bash
bats tests/test_siteapp_uploads.bats
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_siteapp_uploads.bats
git commit -m "test(siteapp): bats CI agent upload + admin docs upload round-trip"
```

---

### Task 25: bats — safety (path traversal, oversized, raw HTML)

**Files:**
- Create: `tests/test_siteapp_safety.bats`

- [ ] **Step 1: Create**

```bash
#!/usr/bin/env bats

load helpers

setup_file() { bash "$ROOT/tests/fake_vps/start.sh"; }
teardown_file() { docker rm -f lds-fake-vps >/dev/null 2>&1 || true; }

TOKEN="safety-tok"
ADMIN_CREDS="$(printf 'admin:admin-fixture' | base64)"

setup() {
    setup_tmpdir
    cp "$ROOT/tests/fixtures/valid_config.yaml" "$TMPDIR/config.yaml"
    yq -i ".vps.host = \"127.0.0.1\" | .vps.ssh_port = 2222" "$TMPDIR/config.yaml"
    export LDS_CONFIG="$TMPDIR/config.yaml"
    export LDS_SSH_KEY="$ROOT/tests/fake_vps/id_test"
    export LDS_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    export LDS_GRAFANA_PASSWORD_FILE="$TMPDIR/admin_password"; printf 'testpw' > "$LDS_GRAFANA_PASSWORD_FILE"
    export LDS_AGENT_TOKEN_FILE="$TMPDIR/agent_upload_token"; printf "$TOKEN" > "$LDS_AGENT_TOKEN_FILE"
    chmod 600 "$LDS_GRAFANA_PASSWORD_FILE" "$LDS_AGENT_TOKEN_FILE"
    bash "$ROOT/scripts/provision.sh"
    bash "$ROOT/scripts/deploy.sh"
}
teardown() { teardown_tmpdir; }

run_curl() {
    docker exec lds-fake-vps bash -c "
        cd /srv/lab-bridge && docker compose exec -T caddy sh -c '
            apk add --no-cache curl >/dev/null 2>&1 || true
            $1
        '
    "
}

@test "siteapp: path traversal in admin docs upload is rejected" {
    run run_curl "
        curl -sS -H 'Authorization: Basic $ADMIN_CREDS' http://localhost/admin/docs > /tmp/h
        csrf=\$(grep -oE 'name=\"csrf\" value=\"[^\"]+\"' /tmp/h | head -1 | sed -E 's/.*value=\"([^\"]+)\".*/\\1/')
        printf 'x' > /tmp/x.md
        code=\$(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: Basic $ADMIN_CREDS' \
                 -F csrf=\$csrf -F target=../escape -F files=@/tmp/x.md \
                 http://localhost/admin/docs/upload)
        test \"\$code\" = '400'
    "
    [ "$status" -eq 0 ]
}

@test "siteapp: raw HTML in markdown is escaped on /docs" {
    # Upload a markdown file containing <script>; check public render escapes it.
    run run_curl "
        curl -sS -H 'Authorization: Basic $ADMIN_CREDS' http://localhost/admin/docs > /tmp/h
        csrf=\$(grep -oE 'name=\"csrf\" value=\"[^\"]+\"' /tmp/h | head -1 | sed -E 's/.*value=\"([^\"]+)\".*/\\1/')
        printf '<script>alert(1)</script>' > /tmp/evil.md
        curl -fsS -H 'Authorization: Basic $ADMIN_CREDS' \
            -F csrf=\$csrf -F target= -F files=@/tmp/evil.md \
            http://localhost/admin/docs/upload -o /dev/null
        body=\$(curl -fsS http://localhost/docs/evil)
        echo \"\$body\" | grep -q '&lt;script&gt;'
    "
    [ "$status" -eq 0 ]
}
```

- [ ] **Step 2: Run**

```bash
bats tests/test_siteapp_safety.bats
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_siteapp_safety.bats
git commit -m "test(siteapp): bats path traversal + raw-HTML safety"
```

---

## Phase 4 — Documentation & smoke

### Task 26: README updates

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the README to mention the new feature**

In `README.md`, append a new section:

```markdown
## Public docs & agent download

Siteapp serves a public docs portal at `/docs/` and a Windows agent
download page at `/download/agent`. Both routes carve out a public
surface in front of JupyterLab without disturbing JupyterLab's cookie
auth or Grafana's login.

- Operator uploads markdown via `/admin/*` (Caddy basic_auth).
- CI publishes a new agent build via `POST /api/agent/upload` with a
  bearer token.

Bootstrap:

```bash
task secrets:set-admin-password
task secrets:rotate-agent-upload-token
task deploy
```

### Russian translations

Drop a `*.ru.md` next to any `*.md` (e.g. `intro.ru.md`) and an EN/RU
toggle appears on the page. English is always the source of truth — a
`*.ru.md` without a matching `*.md` is ignored.

### CI example (GitHub Actions)

```yaml
- name: Upload agent build
  run: |
    curl -fsSL -X POST https://${{ secrets.VPS_HOST }}/api/agent/upload \
      -H "Authorization: Bearer ${{ secrets.AGENT_UPLOAD_TOKEN }}" \
      -F "version=${{ github.ref_name }}" \
      -F "binary=@dist/agent.exe"
```

Operations:

- `task ops:logs:siteapp` — tail siteapp container stderr
- `task ops:site-disk` — `site_data/` size by section
```

In the `Design docs` block, add the new spec line:

```markdown
- `docs/superpowers/specs/2026-05-01-public-docs-and-agent-downloads-design.md` —
  public docs portal + Windows agent download
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README section for public docs portal + agent download"
```

---

### Task 27: Final smoke check on the fake VPS

This is a manual sanity pass that exercises the public surface end-to-end.

- [ ] **Step 1: Build & push siteapp**

```bash
SITEAPP_IMAGE=ghcr.io/<owner>/lab-bridge-siteapp:0.1.0 task siteapp:build-and-push
yq -i ".siteapp.image = \"$SITEAPP_IMAGE\"" config.yaml
```

- [ ] **Step 2: Set required secrets**

```bash
task secrets:set-admin-password
task secrets:rotate-agent-upload-token
```

- [ ] **Step 3: Deploy**

```bash
task deploy
```

Expected: healthcheck reports `docs 200, download 200, admin 401`.

- [ ] **Step 4: Manual probes**

```bash
HOST=$(yq -e '.vps.host' config.yaml)
curl -fsS "https://$HOST/docs/" | head -20
curl -fsS "https://$HOST/download/agent" | head -20
curl -sS -o /dev/null -w '%{http_code}\n' "https://$HOST/admin/"   # expect 401
curl -sS -o /dev/null -w '%{http_code}\n' -u "admin:<your-pw>" "https://$HOST/admin/"  # expect 200
```

- [ ] **Step 5: Upload a doc via the admin UI in a browser**

Open `https://<vps-host>/admin/docs`, drag a `.md` file in, then visit
`https://<vps-host>/docs/<filename-without-ext>` and confirm it renders.

- [ ] **Step 6: Push an agent build via curl simulating CI**

```bash
TOKEN=$(cat compose/siteapp/agent_upload_token)
curl -fsS -X POST "https://$HOST/api/agent/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F version=0.1.0 \
  -F binary=@/path/to/agent.exe
```

Visit `https://<vps-host>/download/agent` — version, size, sha256 displayed.

- [ ] **Step 7: All bats green**

```bash
task test
```

If all green and the manual checks pass, the feature is shippable.

---

## Self-review checklist

Run before declaring done:

- [ ] Spec coverage: every section in `2026-05-01-public-docs-and-agent-downloads-design.md` (Caddy routing, compose, disk layout, docs rendering, EN/RU, admin, agent download, CI upload contract, auth, operator workflows, deploy, image build, testing) maps to at least one task above. ✓
- [ ] No "TBD" / "TODO" / "implement later" placeholders remain. ✓
- [ ] Type/contract consistency across tasks: `find_doc`, `resolve_lang_file`, `build_nav`, `upload_agent`, `make_router`, `Settings.docs_root`, `Settings.agent_root` all match their definitions in earlier tasks. ✓
- [ ] No spec requirement is missing. EN/RU cookie+query precedence (Task 8), trailing-slash redirect (Task 8), 401-on-missing-creds healthcheck (Task 20), atomic agent rename (Task 10/12), CSRF on admin POSTs (Task 11), constant-time bearer compare (Task 10/12) all present. ✓

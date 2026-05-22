# Docs sidebar — manifest-driven nav (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `services/siteapp/app/nav.py`'s alphabetic walk with a strict, manifest-driven sidebar nav, controlled by per-directory `_nav.yaml` files under `public_docs/`.

**Architecture:** A new pure-function module `app/docs_manifest.py` parses and validates `_nav.yaml`. `app/nav.py` shells out to it on every `build_nav()` call. Strict mode at startup (call `build_nav(settings.docs_root)` at module-import time in `app/main.py`) means a malformed manifest crashes uvicorn. A new `app/docs_lint.py` CLI runs the same validator in CI before the e2e step.

**Tech Stack:** Python 3.13, FastAPI, PyYAML, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-05-22-docs-nav-manifest-design.md`

**File map:**

| File | Purpose |
|---|---|
| `services/siteapp/app/docs_manifest.py` | **New.** YAML parser, `ManifestEntry` dataclass, `DocsNavError`, directory validator. |
| `services/siteapp/app/nav.py` | Modified. `build_nav` uses manifest when present (Task 4); fallback removed in Task 7. |
| `services/siteapp/app/main.py` | Modified. Call `build_nav` at import time (Task 8). |
| `services/siteapp/app/docs_lint.py` | **New.** CLI: `python -m app.docs_lint <docs_root>`. |
| `services/siteapp/pyproject.toml`, `uv.lock` | Modified. Add `PyYAML`. |
| `public_docs/_nav.yaml` | **New.** Root manifest. |
| `public_docs/operator/_nav.yaml`, `researcher/_nav.yaml` | **New.** Section manifests (admin, reference don't need one — only `index.md`). |
| `services/siteapp/tests/test_docs_manifest.py` | **New.** Unit tests for parser + validator. |
| `services/siteapp/tests/test_nav.py` | Modified. Existing fixtures updated for strict mode (Task 7). |
| `services/siteapp/tests/test_docs_lint.py` | **New.** CLI tests. |
| `services/siteapp/tests/test_main_startup.py` | **New.** Startup-validation assertion. |
| `services/siteapp/tests/e2e/fixtures/docs/_nav.yaml`, plus icons subdir | **New.** Fixture manifest for e2e docs. |
| `.github/workflows/pr-siteapp.yml` | Modified. Add `public_docs/**` to paths-filter, add `docs_lint` step. |

---

## Task 1: Add PyYAML dependency

**Files:**
- Modify: `services/siteapp/pyproject.toml`
- Modify: `services/siteapp/uv.lock` (regenerated)

- [ ] **Step 1: Add PyYAML to dependencies**

Edit `services/siteapp/pyproject.toml`, add to the `dependencies` list (preserve alphabetical order; insert after `python-multipart`):

```toml
    "pyyaml>=6,<7",
```

- [ ] **Step 2: Regenerate lock**

Run from `services/siteapp/`:

```
uv lock
```

Expected: `uv.lock` updates with PyYAML and its transitive deps (none — PyYAML is pure-C optional).

- [ ] **Step 3: Sync and smoke-import**

Run from `services/siteapp/`:

```
uv sync --frozen
uv run python -c "import yaml; print(yaml.safe_load('a: 1'))"
```

Expected output: `{'a': 1}`

- [ ] **Step 4: Commit**

```
git add services/siteapp/pyproject.toml services/siteapp/uv.lock
git commit -m "build(siteapp): add PyYAML for docs manifest parser"
```

---

## Task 2: Manifest YAML parser (pure functions)

Pure parser with no filesystem access. All it does is take raw YAML text and produce typed entries or raise `DocsNavError`.

**Files:**
- Create: `services/siteapp/app/docs_manifest.py`
- Create: `services/siteapp/tests/test_docs_manifest.py`

- [ ] **Step 1: Write the failing tests**

Create `services/siteapp/tests/test_docs_manifest.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app.docs_manifest import (
    DocsNavError,
    ManifestEntry,
    parse_manifest_yaml,
)


SRC = Path("public_docs/_nav.yaml")


def test_parses_minimal_entry() -> None:
    entries = parse_manifest_yaml("- name: intro\n", SRC)
    assert entries == [ManifestEntry(name="intro", title=None, hidden=False)]


def test_parses_full_entry() -> None:
    text = """
- name: admin
  title: Administrator guide
  hidden: false
- name: draft
  hidden: true
"""
    entries = parse_manifest_yaml(text, SRC)
    assert entries == [
        ManifestEntry(name="admin", title="Administrator guide", hidden=False),
        ManifestEntry(name="draft", title=None, hidden=True),
    ]


def test_empty_list_is_valid() -> None:
    assert parse_manifest_yaml("[]\n", SRC) == []


def test_empty_file_is_valid() -> None:
    # Treat a file that parses to None (empty document) as an empty list.
    assert parse_manifest_yaml("", SRC) == []


def test_root_must_be_list() -> None:
    with pytest.raises(DocsNavError, match="must be a YAML list"):
        parse_manifest_yaml("name: intro\n", SRC)


def test_entry_must_be_mapping() -> None:
    with pytest.raises(DocsNavError, match="entry #1 must be a mapping"):
        parse_manifest_yaml("- intro\n", SRC)


def test_missing_name_field() -> None:
    with pytest.raises(DocsNavError, match="entry #1 is missing required 'name'"):
        parse_manifest_yaml("- title: foo\n", SRC)


def test_unknown_field_rejected() -> None:
    with pytest.raises(DocsNavError, match="unknown field 'order'"):
        parse_manifest_yaml("- name: intro\n  order: 5\n", SRC)


def test_duplicate_name_rejected() -> None:
    text = "- name: intro\n- name: intro\n"
    with pytest.raises(DocsNavError, match="duplicate entry 'intro'"):
        parse_manifest_yaml(text, SRC)


def test_name_must_be_string() -> None:
    with pytest.raises(DocsNavError, match="'name' must be a string"):
        parse_manifest_yaml("- name: 5\n", SRC)


def test_title_must_be_string() -> None:
    with pytest.raises(DocsNavError, match="'title' must be a string"):
        parse_manifest_yaml("- name: intro\n  title: 5\n", SRC)


def test_hidden_must_be_bool() -> None:
    with pytest.raises(DocsNavError, match="'hidden' must be a bool"):
        parse_manifest_yaml("- name: intro\n  hidden: yes-please\n", SRC)


def test_invalid_yaml_syntax() -> None:
    with pytest.raises(DocsNavError, match="invalid YAML"):
        parse_manifest_yaml("- name: [unclosed\n", SRC)


def test_error_includes_source_path() -> None:
    with pytest.raises(DocsNavError, match=str(SRC)):
        parse_manifest_yaml("- name: 5\n", SRC)
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `services/siteapp/`:

```
uv run pytest tests/test_docs_manifest.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.docs_manifest'`.

- [ ] **Step 3: Implement the parser**

Create `services/siteapp/app/docs_manifest.py`:

```python
"""Manifest parser + validator for the docs sidebar nav.

Each docs directory under ``public_docs/`` carries a ``_nav.yaml`` listing
its children in display order. This module owns the schema, parsing, and
validation; ``app.nav`` consumes the resulting entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_ALLOWED_FIELDS: frozenset[str] = frozenset({"name", "title", "hidden"})


class DocsNavError(Exception):
    """Raised on any manifest schema or filesystem-agreement violation."""


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    title: str | None
    hidden: bool


def parse_manifest_yaml(text: str, source: Path) -> list[ManifestEntry]:
    """Parse YAML manifest text. Raise DocsNavError on any schema violation.

    ``source`` is included in error messages so authors can find the offending
    file without grepping. The parser does not touch the filesystem.
    """
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise DocsNavError(f"{source}: invalid YAML — {e}") from e

    if raw is None:
        return []
    if not isinstance(raw, list):
        raise DocsNavError(f"{source}: manifest must be a YAML list, got {type(raw).__name__}")

    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for i, item in enumerate(raw, start=1):
        entries.append(_parse_entry(item, i, source, seen))
    return entries


def _parse_entry(
    item: object,
    index: int,
    source: Path,
    seen: set[str],
) -> ManifestEntry:
    if not isinstance(item, dict):
        raise DocsNavError(
            f"{source}: entry #{index} must be a mapping, got {type(item).__name__}"
        )

    unknown = set(item.keys()) - _ALLOWED_FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        raise DocsNavError(
            f"{source}: entry #{index} has unknown field '{bad}' "
            f"— schema is name/title/hidden"
        )

    if "name" not in item:
        raise DocsNavError(f"{source}: entry #{index} is missing required 'name'")

    name = item["name"]
    if not isinstance(name, str):
        raise DocsNavError(
            f"{source}: entry #{index} 'name' must be a string, got {type(name).__name__}"
        )

    title = item.get("title")
    if title is not None and not isinstance(title, str):
        raise DocsNavError(
            f"{source}: entry #{index} 'title' must be a string, got {type(title).__name__}"
        )

    hidden = item.get("hidden", False)
    if not isinstance(hidden, bool):
        raise DocsNavError(
            f"{source}: entry #{index} 'hidden' must be a bool, got {type(hidden).__name__}"
        )

    if name in seen:
        raise DocsNavError(f"{source}: duplicate entry '{name}'")
    seen.add(name)

    return ManifestEntry(name=name, title=title, hidden=hidden)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run pytest tests/test_docs_manifest.py -v
```

Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```
git add services/siteapp/app/docs_manifest.py services/siteapp/tests/test_docs_manifest.py
git commit -m "feat(siteapp): docs manifest YAML parser with strict schema"
```

---

## Task 3: Directory validator (filesystem agreement)

Walks one directory, reads its `_nav.yaml`, and validates that the manifest agrees with what's on disk. Returns the validated entries or raises `DocsNavError` with **all** violations collected (not just the first).

**Files:**
- Modify: `services/siteapp/app/docs_manifest.py`
- Modify: `services/siteapp/tests/test_docs_manifest.py`

- [ ] **Step 1: Append validator tests**

Append to `services/siteapp/tests/test_docs_manifest.py`:

```python
from app.docs_manifest import (
    has_md_descendants,
    load_dir_manifest,
)


def _w(path: Path, content: str = "# H\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_dir_returns_entries_in_manifest_order(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: beta\n- name: alpha\n")
    _w(tmp_path / "alpha.md")
    _w(tmp_path / "beta.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["beta", "alpha"]


def test_load_dir_missing_manifest_raises(tmp_path: Path) -> None:
    _w(tmp_path / "alpha.md")
    with pytest.raises(DocsNavError, match="_nav.yaml not found"):
        load_dir_manifest(tmp_path)


def test_load_dir_no_manifest_required_when_only_index(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    assert load_dir_manifest(tmp_path) == []


def test_load_dir_no_manifest_required_for_asset_only_dir(tmp_path: Path) -> None:
    _w(tmp_path / "logo.svg", "<svg/>")
    assert load_dir_manifest(tmp_path) == []


def test_load_dir_unknown_entry_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: ghost\n")
    with pytest.raises(DocsNavError, match="ghost.*no ghost.md or ghost/index.md"):
        load_dir_manifest(tmp_path)


def test_load_dir_unlisted_file_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: alpha\n")
    _w(tmp_path / "alpha.md")
    _w(tmp_path / "beta.md")
    with pytest.raises(DocsNavError, match="beta.md exists but is not in _nav.yaml"):
        load_dir_manifest(tmp_path)


def test_load_dir_unlisted_subdir_raises(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "[]\n")
    _w(tmp_path / "sub" / "index.md")
    with pytest.raises(DocsNavError, match="sub/ exists but is not in _nav.yaml"):
        load_dir_manifest(tmp_path)


def test_load_dir_resolves_entry_to_subdir(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: section\n")
    _w(tmp_path / "section" / "index.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["section"]


def test_load_dir_resolves_entry_to_file_when_both_exist(tmp_path: Path) -> None:
    # Ambiguous on disk: foo.md and foo/index.md both exist. The validator
    # picks the file. This is a corner case (authors shouldn't do this); the
    # rule exists so the lookup is deterministic.
    _w(tmp_path / "_nav.yaml", "- name: foo\n")
    _w(tmp_path / "foo.md")
    _w(tmp_path / "foo" / "index.md")
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["foo"]


def test_load_dir_ignores_translation_files(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: intro\n")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "intro.ru.md", "# Введение\n")
    # Translation file does not need its own manifest entry.
    entries = load_dir_manifest(tmp_path)
    assert [e.name for e in entries] == ["intro"]


def test_load_dir_collects_all_errors(tmp_path: Path) -> None:
    _w(tmp_path / "_nav.yaml", "- name: ghost\n")
    _w(tmp_path / "real.md")
    # Two violations: unknown 'ghost' and unlisted 'real.md'. Both should
    # surface in the same exception so authors fix everything at once.
    with pytest.raises(DocsNavError) as excinfo:
        load_dir_manifest(tmp_path)
    msg = str(excinfo.value)
    assert "ghost" in msg
    assert "real.md" in msg


def test_has_md_descendants_true_for_section(tmp_path: Path) -> None:
    _w(tmp_path / "sub" / "index.md")
    assert has_md_descendants(tmp_path) is True


def test_has_md_descendants_false_for_assets(tmp_path: Path) -> None:
    _w(tmp_path / "logo.svg", "<svg/>")
    assert has_md_descendants(tmp_path) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run pytest tests/test_docs_manifest.py -v
```

Expected: import errors for `load_dir_manifest` and `has_md_descendants`.

- [ ] **Step 3: Implement the validator**

Append to `services/siteapp/app/docs_manifest.py`:

```python
MANIFEST_FILENAME = "_nav.yaml"


def has_md_descendants(directory: Path) -> bool:
    """Does this directory contain any .md content (anywhere in the subtree)?

    Used to decide whether the directory needs a manifest. ``.ru.md`` translation
    files don't count — a directory containing only translations is considered
    asset-only (it can't be navigated to without a canonical English doc).
    """
    if not directory.is_dir():
        return False
    for child in directory.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".md" and not child.name.endswith(".ru.md"):
            return True
        if child.is_dir() and has_md_descendants(child):
            return True
    return False


def _listable_children(directory: Path) -> tuple[set[str], set[str]]:
    """Return (file_stems, subdir_names) that a manifest in ``directory`` must cover.

    File rules: include ``.md`` files except ``index.md`` and ``*.ru.md``.
    Directory rules: include subdirs that have any ``.md`` descendants (asset-only
    subdirs are excluded).
    """
    files: set[str] = set()
    dirs: set[str] = set()
    for child in directory.iterdir():
        if child.name.startswith("."):
            continue
        if (
            child.is_file()
            and child.suffix == ".md"
            and child.stem != "index"
            and not child.name.endswith(".ru.md")
        ):
            files.add(child.stem)
        elif child.is_dir() and has_md_descendants(child):
            dirs.add(child.name)
    return files, dirs


def _resolve_entry(directory: Path, name: str) -> Path | None:
    """Return the on-disk target of an entry, or None if it doesn't exist.

    File ``<name>.md`` wins over directory ``<name>/`` when both exist —
    deterministic tie-break for the rare case where an author has both.
    """
    f = directory / f"{name}.md"
    if f.is_file():
        return f
    d = directory / name
    if d.is_dir() and (d / "index.md").is_file():
        return d
    return None


def load_dir_manifest(directory: Path) -> list[ManifestEntry]:
    """Read + validate ``directory``'s manifest. Raise DocsNavError on any violation.

    Directories with no listable children (only ``index.md``, translations, or
    asset files) need no manifest and return ``[]``. Directories with content
    but no manifest raise.
    """
    files, dirs = _listable_children(directory)
    needs_manifest = bool(files or dirs)
    manifest_path = directory / MANIFEST_FILENAME

    if not manifest_path.is_file():
        if needs_manifest:
            raise DocsNavError(f"{manifest_path}: _nav.yaml not found")
        return []

    text = manifest_path.read_text(encoding="utf-8")
    entries = parse_manifest_yaml(text, manifest_path)

    errors: list[str] = []
    listed: set[str] = set()
    for entry in entries:
        listed.add(entry.name)
        if _resolve_entry(directory, entry.name) is None:
            errors.append(
                f"{manifest_path}: entry '{entry.name}' has no "
                f"{entry.name}.md or {entry.name}/index.md"
            )

    for f in sorted(files - listed):
        errors.append(f"{manifest_path}: {f}.md exists but is not in _nav.yaml")
    for d in sorted(dirs - listed):
        errors.append(f"{manifest_path}: {d}/ exists but is not in _nav.yaml")

    if errors:
        raise DocsNavError("\n".join(errors))

    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run pytest tests/test_docs_manifest.py -v
```

Expected: all tests pass (parser + validator, ~25 tests total).

- [ ] **Step 5: Commit**

```
git add services/siteapp/app/docs_manifest.py services/siteapp/tests/test_docs_manifest.py
git commit -m "feat(siteapp): docs manifest validator with multi-error aggregation"
```

---

## Task 4: Manifest-driven `build_nav` (with fallback)

Rewire `build_nav` so it uses the manifest when `_nav.yaml` is present, and falls back to the current alphabetic `_walk` when it's absent. The fallback keeps existing tests and existing `public_docs/` working through this commit; Task 7 will remove it.

**Files:**
- Modify: `services/siteapp/app/nav.py`
- Modify: `services/siteapp/tests/test_nav.py`

- [ ] **Step 1: Write the manifest-path tests**

Append to `services/siteapp/tests/test_nav.py`:

```python
def test_manifest_drives_root_order(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: guide\n- name: alpha\n", encoding="utf-8")
    nav = build_nav(d)
    assert [e.title_en for e in nav] == ["Home", "Guide", "Alpha"]


def test_manifest_title_override(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "intro.md").write_text("# Long intro heading\n", encoding="utf-8")
    (d / "_nav.yaml").write_text(
        '- name: intro\n  title: "Intro"\n', encoding="utf-8"
    )
    nav = build_nav(d)
    intro = next(e for e in nav if e.url == "/docs/intro")
    assert intro.title_en == "Intro"


def test_manifest_hidden_omits_from_nav(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "draft.md").write_text("# Draft\n", encoding="utf-8")
    (d / "_nav.yaml").write_text(
        "- name: intro\n- name: draft\n  hidden: true\n", encoding="utf-8"
    )
    nav = build_nav(d)
    urls = [e.url for e in nav]
    assert "/docs/intro" in urls
    assert "/docs/draft" not in urls


def test_manifest_home_pinned_first(tmp_path: Path) -> None:
    # Even if the root manifest lists other things first, Home (the root
    # index.md) is implicit and pinned at position 0.
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    nav = build_nav(d)
    assert nav[0].url == "/docs/"
    assert nav[1].url == "/docs/intro"


def test_manifest_section_walks_subdir_manifest(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    sec = d / "researcher"
    sec.mkdir(parents=True)
    (d / "_nav.yaml").write_text("- name: researcher\n", encoding="utf-8")
    (sec / "index.md").write_text("# Researcher\n", encoding="utf-8")
    (sec / "first-notebook.md").write_text("# First notebook\n", encoding="utf-8")
    (sec / "_nav.yaml").write_text("- name: first-notebook\n", encoding="utf-8")
    nav = build_nav(d)
    researcher = next(e for e in nav if e.url == "/docs/researcher/")
    assert [c.url for c in researcher.children] == ["/docs/researcher/first-notebook"]


def test_fallback_still_works_when_no_manifest(tmp_path: Path) -> None:
    # Transitional: while the fallback is in place, a docs root with no
    # manifests at any level still renders via the alphabetic walk. Task 7
    # removes this behavior.
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    nav = build_nav(d)
    assert {e.url for e in nav} == {"/docs/", "/docs/alpha"}
```

- [ ] **Step 2: Run new tests to verify they fail**

Run:

```
uv run pytest tests/test_nav.py -v -k "manifest"
```

Expected: failures (manifest path not implemented yet).

- [ ] **Step 3: Rewire `build_nav`**

Replace the contents of `services/siteapp/app/nav.py` with:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.docs_manifest import (
    MANIFEST_FILENAME,
    ManifestEntry,
    has_md_descendants,
    load_dir_manifest,
)

# Best-effort first-H1 extractor. Intentionally simpler than the markdown
# parser so this module stays dependency-free; can diverge from the rendered
# title for setext headings and `#` lines inside fenced code blocks. For
# sidebar labels this is acceptable.
_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _first_h1(text: str) -> str | None:
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else None


def _read_titles(en_path: Path, ru_path: Path, fallback: str) -> tuple[str, str | None]:
    title_en = _first_h1(en_path.read_text(encoding="utf-8")) or fallback
    title_ru = _first_h1(ru_path.read_text(encoding="utf-8")) if ru_path.is_file() else None
    return title_en, title_ru


@dataclass(frozen=True)
class NavEntry:
    title_en: str
    title_ru: str | None
    url: str
    children: tuple["NavEntry", ...] = field(default_factory=tuple)


def build_nav(docs_root: Path) -> list[NavEntry]:
    if not docs_root.is_dir():
        return []
    return _build_level(docs_root, url_prefix="/docs/", is_root=True)


def _build_level(directory: Path, url_prefix: str, is_root: bool) -> list[NavEntry]:
    manifest_path = directory / MANIFEST_FILENAME
    if manifest_path.is_file():
        entries = load_dir_manifest(directory)
        return _from_manifest(directory, entries, url_prefix, is_root)
    # Fallback: no manifest in this directory. Used during transition (Task 4)
    # and by tests written before manifests existed. Task 7 removes this branch
    # and makes a missing manifest an error.
    return _from_alphabetic(directory, url_prefix, is_root)


def _from_manifest(
    directory: Path,
    entries: list[ManifestEntry],
    url_prefix: str,
    is_root: bool,
) -> list[NavEntry]:
    result: list[NavEntry] = []
    if is_root:
        home = _maybe_home(directory, url_prefix)
        if home is not None:
            result.append(home)
    for entry in entries:
        if entry.hidden:
            continue
        result.append(_entry_to_nav(directory, entry, url_prefix))
    return result


def _entry_to_nav(directory: Path, entry: ManifestEntry, url_prefix: str) -> NavEntry:
    file_path = directory / f"{entry.name}.md"
    if file_path.is_file():
        title_en, title_ru = _read_titles(
            file_path, file_path.with_name(f"{entry.name}.ru.md"), entry.name
        )
        return NavEntry(
            title_en=entry.title or title_en,
            title_ru=title_ru,
            url=url_prefix + entry.name,
        )
    sub = directory / entry.name
    index = sub / "index.md"
    title_en, title_ru = _read_titles(index, sub / "index.ru.md", entry.name)
    children = _build_level(sub, url_prefix + entry.name + "/", is_root=False)
    return NavEntry(
        title_en=entry.title or title_en,
        title_ru=title_ru,
        url=url_prefix + entry.name + "/",
        children=tuple(children),
    )


def _maybe_home(directory: Path, url_prefix: str) -> NavEntry | None:
    index = directory / "index.md"
    if not index.is_file():
        return None
    title_en, title_ru = _read_titles(index, directory / "index.ru.md", "Home")
    return NavEntry(title_en=title_en, title_ru=title_ru, url=url_prefix)


def _from_alphabetic(directory: Path, url_prefix: str, is_root: bool) -> list[NavEntry]:
    """Pre-manifest behavior. Removed in Task 7."""
    dirs: list[NavEntry] = []
    files: list[NavEntry] = []
    home_entry: NavEntry | None = _maybe_home(directory, url_prefix) if is_root else None

    for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        if child.name == MANIFEST_FILENAME:
            continue
        if child.is_dir():
            index = child / "index.md"
            children = _build_level(child, url_prefix + child.name + "/", is_root=False)
            if not index.is_file():
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
            title_en, title_ru = _read_titles(index, child / "index.ru.md", child.name)
            dirs.append(
                NavEntry(
                    title_en=title_en,
                    title_ru=title_ru,
                    url=url_prefix + child.name + "/",
                    children=tuple(children),
                )
            )
        elif (
            child.is_file()
            and child.suffix == ".md"
            and not child.name.endswith(".ru.md")
            and child.stem != "index"
        ):
            stem = child.stem
            title_en, title_ru = _read_titles(child, child.with_name(stem + ".ru.md"), stem)
            files.append(
                NavEntry(title_en=title_en, title_ru=title_ru, url=url_prefix + stem)
            )

    result: list[NavEntry] = []
    if home_entry is not None:
        result.append(home_entry)
    result.extend(dirs)
    result.extend(files)
    return result
```

- [ ] **Step 4: Run all nav tests**

Run:

```
uv run pytest tests/test_nav.py tests/test_docs_manifest.py -v
```

Expected: all existing tests still pass (fallback path) plus the new manifest tests pass.

- [ ] **Step 5: ruff format**

Run from `services/siteapp/`:

```
uv run ruff format app tests
uv run ruff check app tests
```

Expected: no changes / no errors.

- [ ] **Step 6: Commit**

```
git add services/siteapp/app/nav.py services/siteapp/tests/test_nav.py
git commit -m "feat(siteapp): build_nav uses _nav.yaml when present (fallback retained)"
```

---

## Task 5: Populate `public_docs/_nav.yaml` files

Real docs get their manifests. Order reflects the narrative the user wants: `system-overview → researcher → operator → admin → reference`.

**Files:**
- Create: `public_docs/_nav.yaml`
- Create: `public_docs/operator/_nav.yaml`
- Create: `public_docs/researcher/_nav.yaml`

`admin/` and `reference/` have only `index.md` — no manifest needed.

- [ ] **Step 1: Root manifest**

Create `public_docs/_nav.yaml`:

```yaml
# Sidebar order for /docs/. Home (index.md) is pinned at the top automatically.
- name: system-overview
- name: technical-overview
- name: researcher
- name: operator
- name: admin
- name: reference
```

- [ ] **Step 2: Operator manifest**

Create `public_docs/operator/_nav.yaml`:

```yaml
- name: setup-lab-pc
```

- [ ] **Step 3: Researcher manifest**

Create `public_docs/researcher/_nav.yaml`:

```yaml
- name: first-notebook
```

- [ ] **Step 4: Verify locally with `build_nav`**

Run from `services/siteapp/`:

```
uv run python -c "
from pathlib import Path
from app.nav import build_nav
nav = build_nav(Path('../../public_docs'))
for e in nav:
    print(e.url, e.title_en)
    for c in e.children:
        print(' ', c.url, c.title_en)
"
```

Expected output (titles depend on each `index.md`'s H1):

```
/docs/ Home
/docs/system-overview System overview
/docs/technical-overview ...
/docs/researcher/ ...
  /docs/researcher/first-notebook ...
/docs/operator/ ...
  /docs/operator/setup-lab-pc ...
/docs/admin/ ...
/docs/reference/ ...
```

If the order does not match the spec, fix `public_docs/_nav.yaml` before committing.

- [ ] **Step 5: Run unit tests (sanity)**

Run:

```
uv run pytest -v
```

Expected: all pass — `public_docs/` is not used by unit tests.

- [ ] **Step 6: Commit**

```
git add public_docs/_nav.yaml public_docs/operator/_nav.yaml public_docs/researcher/_nav.yaml
git commit -m "docs(public): add _nav.yaml manifests for sidebar order"
```

---

## Task 6: e2e fixture manifest

The e2e suite mounts `services/siteapp/tests/e2e/fixtures/docs/` into the container. With strict mode coming in Task 7, this fixture also needs `_nav.yaml` files. Adding them now (before flipping strict) keeps e2e green across the transition.

**Files:**
- Create: `services/siteapp/tests/e2e/fixtures/docs/_nav.yaml`

- [ ] **Step 1: Inspect the fixture**

Run:

```
ls services/siteapp/tests/e2e/fixtures/docs/
```

Expected: `icons/  index.md  intro.md  xss-test.md`

- [ ] **Step 2: Add manifest**

Create `services/siteapp/tests/e2e/fixtures/docs/_nav.yaml`:

```yaml
- name: intro
- name: xss-test
```

(`icons/` is asset-only — no manifest needed there.)

- [ ] **Step 3: Verify build_nav still works against the fixture**

Run from `services/siteapp/`:

```
uv run python -c "
from pathlib import Path
from app.nav import build_nav
nav = build_nav(Path('tests/e2e/fixtures/docs'))
print([(e.url, e.title_en) for e in nav])
"
```

Expected: `[('/docs/', 'Home'), ('/docs/intro', '...'), ('/docs/xss-test', '...')]`.

- [ ] **Step 4: Commit**

```
git add services/siteapp/tests/e2e/fixtures/docs/_nav.yaml
git commit -m "test(siteapp): add _nav.yaml to e2e docs fixture"
```

---

## Task 7: Flip to strict (remove fallback)

Remove `_from_alphabetic`. Missing or malformed manifest = `DocsNavError`. Existing unit-test fixtures get `_nav.yaml` files inline. This is the breaking change — isolated commit so revert is mechanical.

**Files:**
- Modify: `services/siteapp/app/nav.py`
- Modify: `services/siteapp/tests/test_nav.py`

- [ ] **Step 1: Remove the fallback branch**

In `services/siteapp/app/nav.py`, replace `_build_level` with:

```python
def _build_level(directory: Path, url_prefix: str, is_root: bool) -> list[NavEntry]:
    entries = load_dir_manifest(directory)
    return _from_manifest(directory, entries, url_prefix, is_root)
```

Delete the `_from_alphabetic` function entirely.

- [ ] **Step 2: Update the existing `tree` fixture in `test_nav.py`**

In `services/siteapp/tests/test_nav.py`, update the `tree` fixture to include a manifest:

```python
@pytest.fixture
def tree(tmp_path: Path) -> Path:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "index.md").write_text("# Home\n", encoding="utf-8")
    (d / "index.ru.md").write_text("# Главная\n", encoding="utf-8")
    (d / "alpha.md").write_text("# Alpha\n", encoding="utf-8")
    (d / "guide.md").write_text("# Guide\n", encoding="utf-8")
    sec = d / "advanced"
    sec.mkdir()
    (sec / "index.md").write_text("# Advanced\n", encoding="utf-8")
    (sec / "deep.md").write_text("# Deep dive\n", encoding="utf-8")
    (sec / "_nav.yaml").write_text("- name: deep\n", encoding="utf-8")
    (d / "_nav.yaml").write_text(
        "- name: advanced\n- name: alpha\n- name: guide\n", encoding="utf-8"
    )
    return d
```

- [ ] **Step 3: Update tests that used implicit alphabetic ordering**

Rename `test_top_level_order_home_dirs_then_files` to `test_top_level_order_follows_manifest`. The assertion is the same shape (manifest is `advanced, alpha, guide`):

```python
def test_top_level_order_follows_manifest(tree: Path) -> None:
    nav = build_nav(tree)
    titles_en = [e.title_en for e in nav]
    assert titles_en == ["Home", "Advanced", "Alpha", "Guide"]
```

Update `test_filename_fallback_when_no_h1` to add a manifest:

```python
def test_filename_fallback_when_no_h1(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "no-heading.md").write_text("just a paragraph\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: no-heading\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/no-heading")
    assert entry.title_en == "no-heading"
```

Update `test_orphan_ru_file_is_ignored` — orphan ru means asset-only dir, no manifest needed:

```python
def test_orphan_ru_file_is_ignored(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "only-ru.ru.md").write_text("# Только\n", encoding="utf-8")
    nav = build_nav(d)
    assert all(e.url != "/docs/only-ru" for e in nav)
```

Update `test_section_title_falls_back_to_dir_name`:

```python
def test_section_title_falls_back_to_dir_name(tmp_path: Path) -> None:
    d = tmp_path / "docs-root"
    d.mkdir()
    sec = d / "untitled"
    sec.mkdir()
    (sec / "index.md").write_text("just a paragraph\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: untitled\n", encoding="utf-8")
    nav = build_nav(d)
    entry = next(e for e in nav if e.url == "/docs/untitled/")
    assert entry.title_en == "untitled"
```

**Delete `test_dir_without_index_uses_dir_name`** entirely. Under the manifest model, an entry that resolves to a directory **must** have `index.md` (per `_resolve_entry` in Task 3). A directory without `index.md` can no longer be reached via a manifest entry — the rule is now strict, not lenient.

Update `test_empty_dir_is_skipped`:

```python
def test_empty_dir_is_skipped(tmp_path: Path) -> None:
    # An asset-only / empty subdirectory needs no manifest entry. The parent
    # also doesn't need a manifest if nothing is listable at its level.
    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "empty").mkdir()
    nav = build_nav(d)
    assert all(e.url != "/docs/empty/" for e in nav)
```

- [ ] **Step 4: Delete the `test_fallback_still_works_when_no_manifest` test**

It was a transitional check. Strict mode removes the behavior.

- [ ] **Step 5: Add strict-mode tests**

Append to `test_nav.py`:

```python
def test_strict_mode_missing_manifest_raises(tmp_path: Path) -> None:
    from app.docs_manifest import DocsNavError

    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    with pytest.raises(DocsNavError, match="_nav.yaml not found"):
        build_nav(d)


def test_strict_mode_unlisted_file_raises(tmp_path: Path) -> None:
    from app.docs_manifest import DocsNavError

    d = tmp_path / "docs-root"
    d.mkdir()
    (d / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (d / "extra.md").write_text("# Extra\n", encoding="utf-8")
    (d / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    with pytest.raises(DocsNavError, match="extra.md exists but is not in _nav.yaml"):
        build_nav(d)
```

- [ ] **Step 6: Run all tests**

Run from `services/siteapp/`:

```
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 7: ruff**

```
uv run ruff format app tests
uv run ruff check app tests
```

Expected: clean.

- [ ] **Step 8: Commit**

```
git add services/siteapp/app/nav.py services/siteapp/tests/test_nav.py
git commit -m "feat(siteapp)!: require _nav.yaml in every docs directory"
```

---

## Task 8: Startup validation

Make a malformed `public_docs/` crash uvicorn at boot, not at first request. Call `build_nav` at module import in `app/main.py`. If it raises, FastAPI never assembles and the container exits non-zero.

**Files:**
- Modify: `services/siteapp/app/main.py`
- Create: `services/siteapp/tests/test_main_startup.py`

- [ ] **Step 1: Write the failing test**

Create `services/siteapp/tests/test_main_startup.py`:

```python
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _isolate_main(monkeypatch, docs_root: Path) -> None:
    """Drop cached app.main + app.config so re-import picks up the new docs_root."""
    monkeypatch.setenv("SITEAPP_DOCS_DIR", str(docs_root))
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.config", None)


def test_startup_succeeds_with_valid_docs(tmp_path: Path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n", encoding="utf-8")
    _isolate_main(monkeypatch, docs)
    # Importing app.main must not raise. It will call build_nav at import time.
    importlib.import_module("app.main")


def test_startup_fails_on_malformed_manifest(tmp_path: Path, monkeypatch) -> None:
    from app.docs_manifest import DocsNavError

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (docs / "extra.md").write_text("# Extra\n", encoding="utf-8")
    (docs / "_nav.yaml").write_text("- name: intro\n", encoding="utf-8")
    _isolate_main(monkeypatch, docs)
    with pytest.raises(DocsNavError):
        importlib.import_module("app.main")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```
uv run pytest tests/test_main_startup.py -v
```

Expected: `test_startup_fails_on_malformed_manifest` fails (no startup validation yet).

- [ ] **Step 3: Add startup validation**

In `services/siteapp/app/main.py`, after the existing `settings = load_settings()` line (line 19), add:

```python
from app.nav import build_nav

# Fail fast at import: malformed docs manifest crashes uvicorn before it
# starts serving, so a bad deploy can't silently 500 every doc page.
build_nav(settings.docs_root)
```

Place the new `from app.nav import build_nav` with the other `from app.*` imports near the top, in alphabetical order (between `from app.labs import ...` and `from app.public_clients import ...`).

- [ ] **Step 4: Run all tests**

Run:

```
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 5: ruff**

```
uv run ruff format app tests
uv run ruff check app tests
```

Expected: clean.

- [ ] **Step 6: Commit**

```
git add services/siteapp/app/main.py services/siteapp/tests/test_main_startup.py
git commit -m "feat(siteapp): validate docs manifest at startup"
```

---

## Task 9: `docs_lint` CLI

Same validator behind a CLI so authors get a friendlier failure mode in CI than "the e2e container failed to come up."

**Files:**
- Create: `services/siteapp/app/docs_lint.py`
- Create: `services/siteapp/tests/test_docs_lint.py`

- [ ] **Step 1: Write the failing tests**

Create `services/siteapp/tests/test_docs_lint.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.docs_lint import lint_docs_root


def _w(path: Path, content: str = "# H\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_clean_root_yields_no_errors(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "_nav.yaml", "- name: intro\n")
    errors = lint_docs_root(tmp_path)
    assert errors == []


def test_collects_errors_across_directories(tmp_path: Path) -> None:
    # Root has an unlisted file; section has a missing manifest. Both errors
    # should appear in a single lint run.
    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "extra.md")
    _w(tmp_path / "_nav.yaml", "- name: intro\n- name: sub\n")
    _w(tmp_path / "sub" / "index.md")
    _w(tmp_path / "sub" / "deep.md")
    errors = lint_docs_root(tmp_path)
    joined = "\n".join(errors)
    assert "extra.md exists but is not in _nav.yaml" in joined
    assert "sub/_nav.yaml" in joined


def test_skips_dot_directories(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    _w(tmp_path / ".git" / "config", "")
    assert lint_docs_root(tmp_path) == []


def test_main_exits_0_on_clean(tmp_path: Path, capsys) -> None:
    from app.docs_lint import main

    _w(tmp_path / "index.md")
    rc = main([str(tmp_path)])
    assert rc == 0


def test_main_exits_1_on_errors(tmp_path: Path, capsys) -> None:
    from app.docs_lint import main

    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    # No manifest, so this is a missing-manifest error.
    rc = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "_nav.yaml not found" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```
uv run pytest tests/test_docs_lint.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the CLI**

Create `services/siteapp/app/docs_lint.py`:

```python
"""CLI: validate every `_nav.yaml` under a docs root.

Same validator as ``build_nav`` calls at startup, but walks the whole tree
collecting all errors before reporting. Useful as a pre-build CI step so PRs
that break the docs nav fail with a readable diff against `_nav.yaml`, rather
than dying inside the e2e step.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.docs_manifest import DocsNavError, load_dir_manifest


def lint_docs_root(root: Path) -> list[str]:
    """Walk ``root`` and validate every directory's manifest.

    Returns a list of error strings (empty = clean). Each `_nav.yaml`
    is checked independently, so a broken section doesn't hide errors in
    other sections.
    """
    errors: list[str] = []
    for directory in _iter_dirs(root):
        try:
            load_dir_manifest(directory)
        except DocsNavError as e:
            errors.append(str(e))
    return errors


def _iter_dirs(root: Path):
    yield root
    for child in sorted(root.rglob("*")):
        if child.is_dir() and not any(part.startswith(".") for part in child.relative_to(root).parts):
            yield child


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m app.docs_lint <docs_root>", file=sys.stderr)
        return 2
    root = Path(argv[0])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    errors = lint_docs_root(root)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\n{len(errors)} docs nav error(s)", file=sys.stderr)
        return 1
    print(f"docs nav clean: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```
uv run pytest tests/test_docs_lint.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Smoke-test against `public_docs/`**

Run from `services/siteapp/`:

```
uv run python -m app.docs_lint ../../public_docs
```

Expected output: `docs nav clean: ../../public_docs`.

- [ ] **Step 6: ruff**

```
uv run ruff format app tests
uv run ruff check app tests
```

Expected: clean.

- [ ] **Step 7: Commit**

```
git add services/siteapp/app/docs_lint.py services/siteapp/tests/test_docs_lint.py
git commit -m "feat(siteapp): docs_lint CLI for manifest validation"
```

---

## Task 10: Wire `docs_lint` into `pr-siteapp.yml`

Path filter widens to include `public_docs/**`. New step runs `docs_lint` before the e2e build.

**Files:**
- Modify: `.github/workflows/pr-siteapp.yml`

- [ ] **Step 1: Update the paths-filter**

In `.github/workflows/pr-siteapp.yml`, change the `src:` filter from:

```yaml
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - '.github/workflows/pr-siteapp.yml'
```

to:

```yaml
        with:
          filters: |
            src:
              - 'services/siteapp/**'
              - 'public_docs/**'
              - '.github/workflows/pr-siteapp.yml'
```

- [ ] **Step 2: Add the `docs_lint` step**

Insert a new step after `ruff format check` and before `pytest (unit)`:

```yaml
      - name: docs_lint
        if: steps.should-run.outputs.run == 'true'
        working-directory: services/siteapp
        run: uv run python -m app.docs_lint ../../public_docs
```

- [ ] **Step 3: Verify the YAML parses**

Run:

```
python -c "import yaml; yaml.safe_load(open('.github/workflows/pr-siteapp.yml'))"
```

Expected: silent (no exception).

- [ ] **Step 4: Commit**

```
git add .github/workflows/pr-siteapp.yml
git commit -m "ci(siteapp): run docs_lint and watch public_docs/**"
```

---

## Task 11: Documentation touch-up

Update the `docs/adding-a-service.md` adjacent note about docs structure if one exists, and add a short note to the spec doc directory describing the manifest schema for future readers. (Skip if no related docs touch this surface — this is a one-step task.)

**Files:**
- Modify: `docs/adding-a-service.md` if it references the docs nav (verify first).
- Modify: `CLAUDE.md` if it references the alphabetic nav (verify first).

- [ ] **Step 1: Check for references**

Run:

```
grep -rn "alphabetic\|build_nav\|sidebar.*order\|nav.py" docs/ CLAUDE.md 2>/dev/null
```

If matches exist that describe pre-manifest behavior, update them to point at the spec at `docs/superpowers/specs/2026-05-22-docs-nav-manifest-design.md`. If no matches, skip the rest of this task.

- [ ] **Step 2: Commit any edits**

```
git add docs/ CLAUDE.md
git commit -m "docs: note manifest-driven sidebar in onboarding guides"
```

(Skip if no changes.)

---

## Verification — end-to-end

After all tasks land, run the full siteapp suite locally:

- [ ] `cd services/siteapp && uv run pytest -v` — all unit tests green
- [ ] `cd services/siteapp && uv run pytest tests/e2e/ -v` — e2e suite passes against a built image (requires Docker)
- [ ] `cd services/siteapp && uv run python -m app.docs_lint ../../public_docs` — clean
- [ ] `cd services/siteapp && uv run python -c "from app.nav import build_nav; from pathlib import Path; [print(e.url, e.title_en) for e in build_nav(Path('../../public_docs'))]"` — sidebar order matches spec: `Home, system-overview, technical-overview, researcher, operator, admin, reference`
- [ ] Push the worktree branch and confirm `pr-siteapp` passes in GH Actions, including the new `docs_lint` step

---

## Risks logged in spec, mitigated by plan

- **PyYAML as new dep** → added in Task 1, smoke-imported.
- **Author forgets `_nav.yaml`** → strict mode at startup (Task 8) and `docs_lint` in CI (Tasks 9-10) both block.
- **URL stability** → not touched. Manifest controls order only.

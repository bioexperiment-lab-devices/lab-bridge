from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.docs_manifest import (
    ManifestEntry,
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
    entries = load_dir_manifest(directory)
    return _from_manifest(directory, entries, url_prefix, is_root)


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


def flatten_nav(nav: list[NavEntry]) -> list[NavEntry]:
    """Pre-order DFS walk of the nav tree.

    Returns every NavEntry in reading order: each entry appears before its
    own children. Used by `prev_next` to advance from a section index into
    its first child, and from the last child of one section into the next
    top section's index.
    """
    out: list[NavEntry] = []

    def walk(entries: list[NavEntry]) -> None:
        for e in entries:
            out.append(e)
            if e.children:
                walk(list(e.children))

    walk(nav)
    return out


def _maybe_home(directory: Path, url_prefix: str) -> NavEntry | None:
    index = directory / "index.md"
    if not index.is_file():
        return None
    title_en, title_ru = _read_titles(index, directory / "index.ru.md", "Home")
    return NavEntry(title_en=title_en, title_ru=title_ru, url=url_prefix)

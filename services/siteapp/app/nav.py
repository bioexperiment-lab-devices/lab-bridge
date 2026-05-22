from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.docs_manifest import (
    MANIFEST_FILENAME,
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
            files.append(NavEntry(title_en=title_en, title_ru=title_ru, url=url_prefix + stem))

    result: list[NavEntry] = []
    if home_entry is not None:
        result.append(home_entry)
    result.extend(dirs)
    result.extend(files)
    return result

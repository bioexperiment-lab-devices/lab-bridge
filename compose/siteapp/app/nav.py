from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _first_h1(text: str) -> str | None:
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else None


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
    home_entry: NavEntry | None = None
    for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            index = child / "index.md"
            children = _walk(child, url_prefix + child.name + "/")
            if not index.is_file():
                # Directory with no index.md — still walk it. Title falls back to dir name.
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
            title_en = _first_h1(index.read_text(encoding="utf-8")) or child.name
            ru_index = child / "index.ru.md"
            title_ru = (
                _first_h1(ru_index.read_text(encoding="utf-8"))
                if ru_index.is_file()
                else None
            )
            dirs.append(
                NavEntry(
                    title_en=title_en,
                    title_ru=title_ru,
                    url=url_prefix + child.name + "/",
                    children=tuple(c for c in children if not _is_index_url(c.url)),
                )
            )
        elif child.is_file() and child.suffix == ".md" and not child.name.endswith(".ru.md"):
            stem = child.stem
            if stem == "index":
                # The root-level index.md is exposed as a sidebar entry pointing at /docs/.
                # For sub-directory index.md files, the section's NavEntry already represents
                # the index — don't duplicate it here.
                if url_prefix == "/docs/":
                    title_en = _first_h1(child.read_text(encoding="utf-8")) or "Home"
                    ru = child.with_name("index.ru.md")
                    title_ru = (
                        _first_h1(ru.read_text(encoding="utf-8"))
                        if ru.is_file()
                        else None
                    )
                    home_entry = NavEntry(
                        title_en=title_en, title_ru=title_ru, url=url_prefix
                    )
                continue
            title_en = _first_h1(child.read_text(encoding="utf-8")) or stem
            ru = child.with_name(stem + ".ru.md")
            title_ru = (
                _first_h1(ru.read_text(encoding="utf-8"))
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
    if home_entry is not None:
        files.insert(0, home_entry)
    return dirs + files


def _is_index_url(url: str) -> bool:
    return url.endswith("/")

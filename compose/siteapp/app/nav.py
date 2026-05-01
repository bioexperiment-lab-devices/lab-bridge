from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

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
    title_ru = (
        _first_h1(ru_path.read_text(encoding="utf-8")) if ru_path.is_file() else None
    )
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
            title_en, title_ru = _read_titles(
                index, child / "index.ru.md", child.name
            )
            dirs.append(
                NavEntry(
                    title_en=title_en,
                    title_ru=title_ru,
                    url=url_prefix + child.name + "/",
                    children=tuple(children),
                )
            )
        elif child.is_file() and child.suffix == ".md" and not child.name.endswith(".ru.md"):
            stem = child.stem
            if stem == "index":
                # The root-level index.md is exposed as a sidebar entry pointing at /docs/.
                # For sub-directory index.md files, the section's NavEntry already represents
                # the index — don't duplicate it here.
                if url_prefix == "/docs/":
                    title_en, title_ru = _read_titles(
                        child, child.with_name("index.ru.md"), "Home"
                    )
                    home_entry = NavEntry(
                        title_en=title_en, title_ru=title_ru, url=url_prefix
                    )
                continue
            title_en, title_ru = _read_titles(
                child, child.with_name(stem + ".ru.md"), stem
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

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
        en = _safe_md(docs_root, parts, ".md")
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

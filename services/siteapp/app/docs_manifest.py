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
        raise DocsNavError(f"{source}: entry #{index} must be a mapping, got {type(item).__name__}")

    unknown = set(item.keys()) - _ALLOWED_FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        raise DocsNavError(
            f"{source}: entry #{index} has unknown field '{bad}' — schema is name/title/hidden"
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

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

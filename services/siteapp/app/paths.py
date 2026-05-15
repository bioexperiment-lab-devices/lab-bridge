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

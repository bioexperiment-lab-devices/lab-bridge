from __future__ import annotations

from pathlib import Path


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

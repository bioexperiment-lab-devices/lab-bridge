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
        if child.is_dir() and not any(
            part.startswith(".") for part in child.relative_to(root).parts
        ):
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

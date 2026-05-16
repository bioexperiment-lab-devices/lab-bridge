from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import safe_join


class TestSafeJoin:
    def test_simple(self, tmp_path: Path) -> None:
        result = safe_join(tmp_path, "docs", "intro.md")
        assert result == (tmp_path / "docs" / "intro.md").resolve()

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            safe_join(tmp_path, "..", "etc", "passwd")

    def test_rejects_absolute(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            safe_join(tmp_path, "/etc/passwd")

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape-target"
        outside.mkdir(exist_ok=True)
        link = tmp_path / "link"
        link.symlink_to(outside)
        with pytest.raises(ValueError):
            safe_join(tmp_path, "link", "secret.txt")

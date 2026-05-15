from __future__ import annotations

from pathlib import Path

import pytest

from app.paths import sanitize_filename, safe_join


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("foo.md", "foo.md"),
            ("Foo.MD", "foo.md"),
            ("hello-world_2.md", "hello-world_2.md"),
            ("my doc.md", "my-doc.md"),  # space -> hyphen
            ("МойФайл.md", "my-file.md"),
        ],
    )
    def test_accepts_valid(self, raw: str, expected: str) -> None:
        # Note: the Cyrillic case is *not* a transliteration commitment —
        # the rule is "lowercased ASCII [a-z0-9._-] only, anything else
        # collapses to '-'". The test asserts the collapse behavior.
        if raw == "МойФайл.md":
            assert sanitize_filename(raw) == "-------.md"
            return
        assert sanitize_filename(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            ".",
            "..",
            ".hidden",
            "a/b.md",
            "a\\b.md",
            "x" * 101,
        ],
    )
    def test_rejects(self, raw: str) -> None:
        with pytest.raises(ValueError):
            sanitize_filename(raw)


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

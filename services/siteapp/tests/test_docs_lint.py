from __future__ import annotations

from pathlib import Path

from app.docs_lint import lint_docs_root


def _w(path: Path, content: str = "# H\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_clean_root_yields_no_errors(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "_nav.yaml", "- name: intro\n")
    errors = lint_docs_root(tmp_path)
    assert errors == []


def test_collects_errors_across_directories(tmp_path: Path) -> None:
    # Root has an unlisted file; section has a missing manifest. Both errors
    # should appear in a single lint run.
    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    _w(tmp_path / "extra.md")
    _w(tmp_path / "_nav.yaml", "- name: intro\n- name: sub\n")
    _w(tmp_path / "sub" / "index.md")
    _w(tmp_path / "sub" / "deep.md")
    errors = lint_docs_root(tmp_path)
    joined = "\n".join(errors)
    assert "extra.md exists but is not in _nav.yaml" in joined
    assert "sub/_nav.yaml" in joined


def test_skips_dot_directories(tmp_path: Path) -> None:
    _w(tmp_path / "index.md")
    _w(tmp_path / ".git" / "config", "")
    assert lint_docs_root(tmp_path) == []


def test_main_exits_0_on_clean(tmp_path: Path, capsys) -> None:
    from app.docs_lint import main

    _w(tmp_path / "index.md")
    rc = main([str(tmp_path)])
    assert rc == 0


def test_main_exits_1_on_errors(tmp_path: Path, capsys) -> None:
    from app.docs_lint import main

    _w(tmp_path / "index.md")
    _w(tmp_path / "intro.md")
    # No manifest, so this is a missing-manifest error.
    rc = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "_nav.yaml not found" in captured.err

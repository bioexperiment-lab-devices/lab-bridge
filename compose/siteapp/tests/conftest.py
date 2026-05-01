from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def site_data(tmp_path: Path) -> Path:
    """Fresh, empty site_data/ tree for a single test."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "agent" / "windows").mkdir(parents=True)
    return tmp_path

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.public_clients import (
    _load_roster,
    _parse_bearer,
    _verify,
)


# ----- _parse_bearer ------------------------------------------------------

def test_parse_bearer_returns_token() -> None:
    assert _parse_bearer("Bearer abc123") == "abc123"


def test_parse_bearer_is_case_insensitive_for_scheme() -> None:
    assert _parse_bearer("bearer abc123") == "abc123"
    assert _parse_bearer("BEARER abc123") == "abc123"


def test_parse_bearer_strips_trailing_whitespace() -> None:
    assert _parse_bearer("Bearer abc123   ") == "abc123"


def test_parse_bearer_none_returns_empty() -> None:
    assert _parse_bearer(None) == ""


def test_parse_bearer_wrong_scheme_returns_empty() -> None:
    assert _parse_bearer("Basic abc123") == ""


def test_parse_bearer_empty_string_returns_empty() -> None:
    assert _parse_bearer("") == ""


# ----- _load_roster -------------------------------------------------------

def test_load_roster_returns_raw_dict(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text('{"a": {"port": 1, "password_sha256": "aa"}}', encoding="utf-8")
    assert _load_roster(f) == {"a": {"port": 1, "password_sha256": "aa"}}


def test_load_roster_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        _load_roster(tmp_path / "nope.json")


def test_load_roster_malformed_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


def test_load_roster_non_object_raises(tmp_path: Path) -> None:
    f = tmp_path / "r.json"
    f.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_roster(f)


# ----- _verify ------------------------------------------------------------

def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_verify_hit_returns_entry() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "s3cret", roster) == roster["alice"]


def test_verify_wrong_password_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "wrong", roster) is None


def test_verify_unknown_user_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("eve", "anything", roster) is None


def test_verify_empty_bearer_returns_none() -> None:
    roster = {"alice": {"port": 8089, "password_sha256": _hash("s3cret")}}
    assert _verify("alice", "", roster) is None


def test_verify_entry_missing_hash_returns_none() -> None:
    # Malformed roster: entry has no password_sha256. Should fail closed.
    roster = {"alice": {"port": 8089}}
    assert _verify("alice", "anything", roster) is None


def test_verify_entry_malformed_hash_returns_none() -> None:
    # Non-hex hash. Should fail closed without raising.
    roster = {"alice": {"port": 8089, "password_sha256": "not-hex!"}}
    assert _verify("alice", "anything", roster) is None

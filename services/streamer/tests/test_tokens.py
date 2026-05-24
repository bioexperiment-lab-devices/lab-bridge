from __future__ import annotations


import pytest

from app.tokens import generate_whip_token


def test_generate_returns_distinct_tokens() -> None:
    a = generate_whip_token(validity_s=60.0)
    b = generate_whip_token(validity_s=60.0)
    assert a.value != b.value
    assert a.value.startswith("tk_")
    assert len(a.value) > 30


def test_token_validates_correct_bearer() -> None:
    t = generate_whip_token(validity_s=60.0)
    assert t.matches(t.value) is True


def test_token_rejects_wrong_bearer() -> None:
    t = generate_whip_token(validity_s=60.0)
    assert t.matches("tk_wrong") is False


def test_token_rejects_after_burn() -> None:
    t = generate_whip_token(validity_s=60.0)
    t.burn()
    assert t.matches(t.value) is False


def test_token_burn_is_idempotent() -> None:
    t = generate_whip_token(validity_s=60.0)
    t.burn()
    t.burn()
    assert t.matches(t.value) is False


def test_token_rejects_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_now = [1000.0]
    monkeypatch.setattr("app.tokens.time.monotonic", lambda: fake_now[0])
    t = generate_whip_token(validity_s=60.0)
    fake_now[0] = 1059.9
    assert t.matches(t.value) is True
    fake_now[0] = 1060.1
    assert t.matches(t.value) is False


def test_token_constant_time_compare() -> None:
    # Smoke check that we use secrets.compare_digest under the hood:
    # different-length comparisons must not raise.
    t = generate_whip_token(validity_s=60.0)
    assert t.matches("") is False
    assert t.matches("tk_") is False

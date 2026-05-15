"""Tests for /api/public/clients/<username>. The fixture roster has
``alice_machine`` with port 9001 and password 'password' (sha256 of
'password' is in the fixture).
"""
from __future__ import annotations


VALID_USER = "alice_machine"
VALID_PASSWORD = "password"  # plaintext for which the fixture stores sha256


def test_public_clients_happy_path(http) -> None:
    r = http.get(
        f"/api/public/clients/{VALID_USER}",
        headers={"Authorization": f"Bearer {VALID_PASSWORD}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["port"] == 9001
    # chisel isn't running in the harness, so connected is False
    assert body["connected"] is False


def test_public_clients_wrong_password_returns_401(http) -> None:
    r = http.get(
        f"/api/public/clients/{VALID_USER}",
        headers={"Authorization": "Bearer wrong-password"},
    )
    assert r.status_code == 401


def test_public_clients_unknown_user_returns_401(http) -> None:
    r = http.get(
        "/api/public/clients/nobody",
        headers={"Authorization": f"Bearer {VALID_PASSWORD}"},
    )
    assert r.status_code == 401


def test_public_clients_no_auth_header_returns_401(http) -> None:
    r = http.get(f"/api/public/clients/{VALID_USER}")
    assert r.status_code == 401

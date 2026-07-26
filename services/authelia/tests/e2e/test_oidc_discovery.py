"""OIDC well-known endpoint advertises the expected shape."""

from __future__ import annotations

import httpx


def test_openid_configuration_returns_expected_endpoints(http: httpx.Client) -> None:
    r = http.get("/.well-known/openid-configuration")
    assert r.status_code == 200
    doc = r.json()
    for key in (
        "issuer",
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
    ):
        assert key in doc, f"missing {key}: {doc}"
    assert "9091" in doc["issuer"]  # local fixture issuer includes port 9091


def test_jwks_endpoint_returns_keys(http: httpx.Client) -> None:
    r = http.get("/jwks.json")
    assert r.status_code == 200
    assert "keys" in r.json()

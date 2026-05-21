"""OIDC authorize for the grafana client must NOT redirect to /consent.

Authelia's React SPA is broken under our `/auth/` sub-path (its assets are
absolute-pathed to `/static/...` and `/manifest.json`), so any redirect to
`/consent` lands the user on an unrouted URL and the auth code never reaches
Grafana. The configuration template sets `consent_mode: implicit` for the
grafana client so Authelia skips the consent prompt and redirects directly
back to the Grafana callback with `code=...`.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from .test_forward_auth import _login


def test_authorize_redirects_to_client_not_consent(http: httpx.Client) -> None:
    cookie = _login(http, "bob", "bob-password")
    params = {
        "client_id": "grafana",
        "response_type": "code",
        "scope": "openid profile email groups",
        "redirect_uri": "https://test.local/grafana/login/generic_oauth",
        "state": "regression-test-state-1234567890",
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
    }
    r = http.get(
        "/api/oidc/authorization",
        params=params,
        headers={
            "Cookie": cookie,
            "X-Forwarded-Host": "test.local",
            "X-Forwarded-Proto": "https",
        },
        follow_redirects=False,
    )
    # Implicit consent → 30x straight back to the Grafana callback with `code`.
    # Without `consent_mode: implicit`, this would 30x to /consent?id=... which
    # falls through Caddy's routing and silently breaks the OIDC handshake.
    assert r.status_code in (302, 303), r.text
    location = r.headers["location"]
    parsed = urlparse(location)
    assert parsed.path == "/grafana/login/generic_oauth", (
        f"expected redirect back to grafana callback, got {location!r}"
    )
    qs = parse_qs(parsed.query)
    assert "code" in qs, f"no auth code in callback redirect: {location!r}"
    assert qs.get("state") == ["regression-test-state-1234567890"]

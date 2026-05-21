"""End-to-end coverage for the redesigned Home page."""

from __future__ import annotations

import httpx


def _login_cookie(http: httpx.Client, username: str, password: str) -> str:
    r = http.post(
        "/api/auth/firstfactor",
        json={
            "username": username,
            "password": password,
            "targetURL": "/",
            "keepMeLoggedIn": True,
        },
    )
    r.raise_for_status()
    return r.headers.get_list("set-cookie")[0].split(";", 1)[0]


def test_root_returns_home_page(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    assert "lab-bridge" in body
    assert 'class="lb-home-header"' in body
    assert 'class="lb-intro-stmt"' in body
    assert 'class="lb-equip"' in body
    assert 'class="lb-topo' in body
    assert 'class="lb-quick' in body
    assert 'class="lb-start' in body


def test_lang_query_param_sets_cookie_and_flips_strings(http: httpx.Client) -> None:
    r = http.get("/?lang=ru", follow_redirects=False)
    assert r.status_code == 200
    assert "Зарегистрированные лаборатории" in r.text
    assert r.cookies.get("lang") == "ru"


def test_api_public_labs_returns_list(http: httpx.Client) -> None:
    r = http.get("/api/public/labs")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_root_is_not_a_redirect(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "Location" not in r.headers


def test_anonymous_home_hides_labs_panel_behind_signin_cta(http: httpx.Client) -> None:
    r = http.get("/", follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    # Hidden-state placeholder is rendered…
    assert "data-labs-hidden" in body
    assert 'class="lb-equip__hidden-cta"' in body
    assert 'href="/login?rd=/"' in body
    assert "Sign in to view lab status" in body
    # …and the actual lab list is not. The "updated Ns ago" timestamp lives
    # in a <span class="lb-equip__meta">; the string "data-labs-updated" on
    # its own also appears in the polling JS, so match the rendered span.
    assert "lb-labrow" not in body
    assert 'class="lb-equip__meta"' not in body
    # Topology stays visible — it's generic schematic content.
    assert 'class="lb-topo' in body


def test_anonymous_home_hidden_state_localized_in_ru(http: httpx.Client) -> None:
    r = http.get("/?lang=ru", follow_redirects=False)
    assert r.status_code == 200
    assert "Войдите, чтобы видеть состояние лабораторий" in r.text


def test_signed_in_home_renders_labs_panel(http: httpx.Client) -> None:
    cookie = _login_cookie(http, "alice", "alice-password")
    r = http.get("/", headers={"Cookie": cookie}, follow_redirects=False)
    assert r.status_code == 200
    body = r.text
    # The hidden-state placeholder is gone…
    assert "data-labs-hidden" not in body
    assert "lb-equip__hidden-cta" not in body
    # …and the real labs panel chrome is back. (No fixture agents are wired
    # up, so the online/offline lists are empty — the group headers and the
    # "updated Ns ago" meta span still render.)
    assert 'class="lb-equip__meta"' in body
    assert 'data-group="online"' in body
    assert 'data-group="offline"' in body


def test_panel_poll_respects_signed_in_state(http: httpx.Client) -> None:
    # The 5s polling endpoint that swaps .lb-labs-section must apply the
    # same gating as the initial render — otherwise a signed-out visitor's
    # poll would replace the hidden state with a fresh labs panel.
    anon = http.get("/?_panel=1", follow_redirects=False)
    assert anon.status_code == 200
    assert "data-labs-hidden" in anon.text
    assert "lb-labrow" not in anon.text

    cookie = _login_cookie(http, "alice", "alice-password")
    auth = http.get("/?_panel=1", headers={"Cookie": cookie}, follow_redirects=False)
    assert auth.status_code == 200
    assert "data-labs-hidden" not in auth.text
    assert 'class="lb-equip__meta"' in auth.text

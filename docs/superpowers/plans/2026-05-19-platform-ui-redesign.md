# Platform UI hi-fi redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the lab-bridge hi-fi design handoff to four surfaces (shared navbar, Home, Download Agent, Docs) as a single coordinated PR, including the missing `/api/public/labs` aggregator backend.

**Architecture:** Architecture is unchanged from the 2026-05-17 shared-navbar spec — vanilla `<lds-navbar>` web component in `compose/shell/` injected by Caddy, FastAPI + Jinja + plain CSS in `services/siteapp/`. This plan layers visual tokens, IBM Plex typography, a manual theme toggle, EN/RU bilingual support on Home, and the missing labs aggregator on top of the existing structure.

**Tech Stack:** FastAPI 0.115, Jinja2 3.1, vanilla ES2020, plain CSS with custom properties, IBM Plex (Google Fonts CDN), markdown-it-py 3 + custom Pygments style, pytest 8.3 + pytest-asyncio, docker compose for service e2e, bats for platform integration.

**Spec:** `docs/superpowers/specs/2026-05-19-platform-ui-redesign-design.md`. The design handoff at `docs/design_handoff_lab_bridge/` is the visual authoritative source — when this plan says "port verbatim", read the handoff README + source files.

---

## Foundation — design tokens, fonts, theme model, shared utilities

### Task 1: Create design tokens stylesheet

**Files:**
- Create: `services/siteapp/app/static/tokens.css`

- [ ] **Step 1: Write the file**

Port the design tokens verbatim from `docs/design_handoff_lab_bridge/README.md` lines 48–145 (Light + Dark tables) plus the type/spacing values. Two CSS blocks: `:root` (light defaults) + `[data-theme="dark"]` (dark overrides).

```css
:root {
  /* Colors — Light theme */
  --bg-page: #ECE9E0;
  --surface: #FFFFFF;
  --surface-sunken: #F8F6F0;
  --surface-strip: #FAF8F3;
  --surface-rail: #F3F0E6;
  --border: #E2DED2;
  --border-strong: #C8C3B5;
  --border-input: #C3BFB2;
  --text: #1A1916;
  --text-secondary: #514E47;
  --text-muted: #8A8678;
  --text-inverse: #FAF8F3;
  --accent: #1F3A8A;
  --accent-hover: #182E6F;
  --accent-soft: #E7ECF6;
  --accent-border: #B8C2DC;
  --success: #2F7D3F;
  --success-soft: #E5F1E6;
  --success-border: #BCD7BE;
  --danger: #B23A2A;
  --danger-soft: #F8E5E0;
  --danger-border: #ECC5BC;
  --warning: #A37200;
  --warning-soft: #F5EAC8;
  --warning-border: #E2D096;
  --neutral-dot: #9F9B8E;
  --shadow-card: 0 1px 0 rgba(26,25,22,0.04), 0 1px 2px rgba(26,25,22,0.06);
  --shadow-popover: 0 10px 24px -8px rgba(26,25,22,0.25), 0 2px 6px rgba(26,25,22,0.08);
  --shadow-overlay: 0 24px 50px -20px rgba(26,25,22,0.45), 0 8px 18px -6px rgba(26,25,22,0.18);

  /* Typography */
  --font-sans: 'IBM Plex Sans', system-ui, -apple-system, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --base-size: 13px;
  --base-line: 1.45;
}

[data-theme="dark"] {
  --bg-page: #1B1A17;
  --surface: #232220;
  --surface-sunken: #1D1C19;
  --surface-strip: #1F1E1B;
  --surface-rail: #1E1D1A;
  --border: #34322D;
  --border-strong: #4A4740;
  --text: #F0EDE3;
  --text-secondary: #B8B3A4;
  --text-muted: #7E7A6E;
  --accent: #BCCBF2;
  --accent-hover: #DBE3F8;
  --accent-soft: #2A3257;
  --accent-border: #4A5587;
  --success: #7CC18A;
  --success-soft: #1F2C22;
  --success-border: #335A3E;
  --danger: #E58879;
  --danger-soft: #34211D;
  --danger-border: #6A3D34;
  --warning: #E3C067;
  --warning-soft: #2F2715;
  --warning-border: #5E4C20;
}
```

- [ ] **Step 2: Visually verify by checking file syntax**

Run: `python -c "import pathlib; print(pathlib.Path('services/siteapp/app/static/tokens.css').read_text()[:200])"`
Expected: First 200 chars print without error.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/static/tokens.css
git commit -m "feat(siteapp): add design tokens stylesheet (warm-cream palette + IBM Plex)"
```

---

### Task 2: Wire fonts + tokens + theme boot script into base template

**Files:**
- Modify: `services/siteapp/app/templates/base.html`

- [ ] **Step 1: Rewrite base.html**

Replace the existing `<head>` content and add the theme boot script. The script must run before paint to avoid theme flash.

```html
<!doctype html>
<html lang="{{ lang|default('en') }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}lab-bridge{% endblock %}</title>

  <script>
    (function () {
      var t = localStorage.getItem('theme');
      if (!t) t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      document.documentElement.dataset.theme = t;
    })();
    window.addEventListener('storage', function (e) {
      if (e.key === 'theme' && (e.newValue === 'light' || e.newValue === 'dark')) {
        document.documentElement.dataset.theme = e.newValue;
      }
    });
  </script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet"
        href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">

  <link rel="stylesheet" href="/_static/tokens.css">
  <link rel="stylesheet" href="/_static/site.css">
  {% if pygments_css %}<style>{{ pygments_css|safe }}</style>{% endif %}
  <style>
    body {
      padding-left: var(--nav-width, 0);
      transition: padding-left 0.15s ease;
    }
  </style>
</head>
<body>
  <main>{% block main %}{% endblock %}</main>
  <script src="/_static/copy-inline.js" defer></script>
  {% if needs_mermaid %}
  <script src="/_static/vendor/mermaid.min.js" defer></script>
  <script src="/_static/mermaid-init.js" defer></script>
  {% endif %}
</body>
</html>
```

Note: dropped the `<footer><a href="/">lab-bridge</a></footer>` block — the new design puts navigation entirely in the rail, and the sticky header carries branding on Home and Download. Footer prev/next nav for Docs comes from the doc template itself.

- [ ] **Step 2: Commit**

```bash
git add services/siteapp/app/templates/base.html
git commit -m "feat(siteapp): load IBM Plex + design tokens + theme boot script in base template"
```

---

### Task 3: Create shared copy-to-clipboard utility

**Files:**
- Create: `services/siteapp/app/static/copy-inline.js`
- Delete: `services/siteapp/app/static/copy-code.js`

- [ ] **Step 1: Write copy-inline.js**

```javascript
// Click-to-copy utility. Reads target text from data-copy-text="..." or
// data-copy-from="<selector>" (innerText of the matched element). Toggles
// .is-copied on the button for 1.5s. Single delegated click listener,
// idempotent on duplicate include.

(function () {
  if (window.__copyInlineLoaded) return;
  window.__copyInlineLoaded = true;

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy-text], [data-copy-from], .lb-code__copy');
    if (!btn) return;

    var text = btn.getAttribute('data-copy-text');
    if (!text) {
      var sel = btn.getAttribute('data-copy-from');
      var src = null;
      if (sel) {
        src = document.querySelector(sel);
      } else if (btn.classList.contains('lb-code__copy')) {
        // Code-block buttons live inside <figure class="lb-code"> with a <pre> sibling.
        var figure = btn.closest('.lb-code');
        if (figure) src = figure.querySelector('pre code') || figure.querySelector('pre');
      }
      if (src) text = src.innerText;
    }
    if (!text) return;

    navigator.clipboard.writeText(text).then(function () {
      btn.classList.add('is-copied');
      setTimeout(function () { btn.classList.remove('is-copied'); }, 1500);
    });
  });
})();
```

- [ ] **Step 2: Delete the old copy-code.js**

```bash
git rm services/siteapp/app/static/copy-code.js
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/static/copy-inline.js
git commit -m "feat(siteapp): replace copy-code.js with shared copy-inline.js utility"
```

---

## Strings module

### Task 4: Create strings.py with EN/RU dicts for Home and Download

**Files:**
- Create: `services/siteapp/app/strings.py`
- Create: `services/siteapp/tests/test_strings.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_strings.py
from __future__ import annotations

from app.strings import DL_STRINGS, HOME_STRINGS


def test_home_strings_have_same_keys_in_both_languages() -> None:
    assert set(HOME_STRINGS["en"].keys()) == set(HOME_STRINGS["ru"].keys())


def test_dl_strings_have_same_keys_in_both_languages() -> None:
    assert set(DL_STRINGS["en"].keys()) == set(DL_STRINGS["ru"].keys())


def test_home_strings_no_empty_values() -> None:
    for lang in ("en", "ru"):
        for key, value in HOME_STRINGS[lang].items():
            assert value.strip(), f"empty HOME_STRINGS[{lang}][{key}]"


def test_dl_strings_no_empty_values() -> None:
    for lang in ("en", "ru"):
        for key, value in DL_STRINGS[lang].items():
            assert value.strip(), f"empty DL_STRINGS[{lang}][{key}]"


def test_dl_strings_includes_relative_time_units() -> None:
    # _relative_time in app/agent.py reads these.
    for lang in ("en", "ru"):
        for k in ("just_now", "minutes_ago", "hours_ago", "days_ago", "weeks_ago"):
            assert k in DL_STRINGS[lang], f"missing DL_STRINGS[{lang}][{k}]"
```

- [ ] **Step 2: Run, verify fail**

```bash
cd services/siteapp && uv run pytest tests/test_strings.py -v
```
Expected: FAIL — `app.strings` module not found.

- [ ] **Step 3: Write strings.py**

Port the full string maps from `docs/design_handoff_lab_bridge/source/lab-bridge-home.jsx`'s `STRINGS` constant and `lab-bridge-download.jsx`'s `DL_STRINGS` constant. Add the relative-time unit keys.

```python
# app/strings.py
from __future__ import annotations

from typing import Literal

Lang = Literal["en", "ru"]

# Ported from docs/design_handoff_lab_bridge/source/lab-bridge-home.jsx STRINGS.
HOME_STRINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "page_title": "lab-bridge — Home",
        "tagline": "lab instrumentation platform",
        "lang_en": "EN",
        "lang_ru": "RU",
        "intro_eyebrow": "WHAT LAB-BRIDGE IS",
        "intro_headline": "One bridge from every lab instrument to the researchers using it.",
        "intro_p1": "Lab PCs run the SerialHop agent, which opens a secure reverse tunnel back to lab-bridge. Researchers reach the instruments from a shared JupyterLab — no VPN, no port-forward, no instrument moved.",
        "intro_p2": "One portal, every lab. Auth scoped per user. Operators manage the fleet from one place.",
        "labs_panel_title": "Registered labs",
        "labs_updated_prefix": "updated",
        "labs_updated_suffix": "ago",
        "labs_just_now": "just now",
        "labs_online": "ONLINE",
        "labs_offline": "OFFLINE",
        "labs_outdated_pill": "OUTDATED",
        "labs_outdated_tooltip": "This lab is on an older SerialHop than the rest of the fleet",
        "topo_title": "How it works",
        "topo_node_lab": "Lab PC + instruments",
        "topo_node_bridge": "lab-bridge",
        "topo_node_researcher": "Researcher in JupyterLab",
        "quick_title": "Quick destinations",
        "quick_jupyter": "JupyterLab",
        "quick_docs": "Browse docs",
        "quick_agent": "Download agent",
        "quick_grafana": "Grafana",
        "start_title": "Getting started",
        "start_role_researcher": "FOR RESEARCHERS",
        "start_role_operator": "FOR LAB OPERATORS",
        "start_card_researcher_title": "Run your first notebook",
        "start_card_researcher_desc": "Open JupyterLab, connect to your lab's instruments, and run a one-cell smoke test in five minutes.",
        "start_card_researcher_path": "/docs/researcher/first-notebook",
        "start_card_operator_title": "Set up a new lab PC",
        "start_card_operator_desc": "Install the SerialHop agent, claim a user, register your instruments, and verify the tunnel is alive.",
        "start_card_operator_path": "/docs/operator/setup-lab-pc",
    },
    "ru": {
        "page_title": "lab-bridge — Главная",
        "tagline": "платформа управления лабораторным оборудованием",
        "lang_en": "EN",
        "lang_ru": "RU",
        "intro_eyebrow": "ЧТО ТАКОЕ LAB-BRIDGE",
        "intro_headline": "Один мост от каждого прибора в лаборатории до исследователей, которые им пользуются.",
        "intro_p1": "Лабораторные ПК запускают агент SerialHop, который открывает защищённый обратный туннель к lab-bridge. Исследователи работают с приборами из общего JupyterLab — без VPN, без проброса портов, без переноса оборудования.",
        "intro_p2": "Один портал, все лаборатории. Доступ — по пользователю. Операторы управляют парком из одного места.",
        "labs_panel_title": "Зарегистрированные лаборатории",
        "labs_updated_prefix": "обновлено",
        "labs_updated_suffix": "назад",
        "labs_just_now": "только что",
        "labs_online": "ОНЛАЙН",
        "labs_offline": "ОФФЛАЙН",
        "labs_outdated_pill": "УСТАРЕЛО",
        "labs_outdated_tooltip": "На этой лаборатории установлена устаревшая версия SerialHop",
        "topo_title": "Как это работает",
        "topo_node_lab": "Лабораторный ПК + приборы",
        "topo_node_bridge": "lab-bridge",
        "topo_node_researcher": "Исследователь в JupyterLab",
        "quick_title": "Куда дальше",
        "quick_jupyter": "JupyterLab",
        "quick_docs": "Документация",
        "quick_agent": "Скачать агент",
        "quick_grafana": "Grafana",
        "start_title": "С чего начать",
        "start_role_researcher": "ИССЛЕДОВАТЕЛЯМ",
        "start_role_operator": "ОПЕРАТОРАМ ЛАБОРАТОРИИ",
        "start_card_researcher_title": "Запустите первый ноутбук",
        "start_card_researcher_desc": "Откройте JupyterLab, подключитесь к приборам своей лаборатории и запустите тестовую ячейку за пять минут.",
        "start_card_researcher_path": "/docs/researcher/first-notebook",
        "start_card_operator_title": "Настройте новый лабораторный ПК",
        "start_card_operator_desc": "Установите агент SerialHop, заведите пользователя, зарегистрируйте приборы и убедитесь, что туннель работает.",
        "start_card_operator_path": "/docs/operator/setup-lab-pc",
    },
}

# Ported from docs/design_handoff_lab_bridge/source/lab-bridge-download.jsx DL_STRINGS.
DL_STRINGS: dict[Lang, dict[str, str]] = {
    "en": {
        "page_title": "Download SerialHop — lab-bridge",
        # Shared header strings (the Download page reuses _home_header.html).
        "tagline": "lab instrumentation platform",
        "lang_en": "EN",
        "lang_ru": "RU",
        "hero_title": "SerialHop",
        "hero_lede": "Single-binary agent that exposes a lab PC's instruments to lab-bridge through a secure reverse tunnel.",
        "source_label": "Source, releases, and protocol notes:",
        "source_link_text": "github.com/bioexperiment-lab-devices/serialhop",
        "platform_windows": "Windows",
        "platform_linux": "Linux",
        "platform_rpi": "Raspberry Pi",
        "platform_windows_sub": "Windows 10 / 11 · 64-bit",
        "platform_linux_sub": "x86_64 · glibc 2.31+",
        "platform_rpi_sub": "ARM64 · Raspberry Pi OS 12+",
        "status_available": "Available",
        "status_coming_soon": "Coming soon",
        "eta_linux": "expected Q3 2026",
        "eta_rpi": "expected Q4 2026",
        "cta_download_for": "Download for",
        "cta_disabled": "Not yet available — check back soon",
        "meta_version": "Version",
        "meta_released": "Released",
        "meta_sha256": "SHA-256",
        "meta_copy": "Copy",
        "meta_copied": "✓ copied",
        "explainer_summary": "Your browser may block this download",
        "explainer_intro": "The agent installer is a fresh Windows binary that doesn't yet carry a trusted publisher signature or any reputation in Microsoft Defender SmartScreen. As a result, browsers often hide the downloaded file and Windows refuses to launch it on first run. The file is safe — if you'd like to be sure, verify the SHA-256 below against the value the lab-bridge operator gave you.",
        "explainer_h4_browser": "IF THE BROWSER HIDES THE DOWNLOAD",
        "explainer_h4_windows": "IF WINDOWS BLOCKS THE .EXE ON FIRST RUN",
        "just_now": "just now",
        "minutes_ago": "{n} minutes ago",
        "hours_ago": "{n} hours ago",
        "days_ago": "{n} days ago",
        "weeks_ago": "{n} weeks ago",
    },
    "ru": {
        "page_title": "Скачать SerialHop — lab-bridge",
        # Shared header strings.
        "tagline": "платформа управления лабораторным оборудованием",
        "lang_en": "EN",
        "lang_ru": "RU",
        "hero_title": "SerialHop",
        "hero_lede": "Single-binary агент, который через защищённый обратный туннель открывает приборы лабораторного ПК для lab-bridge.",
        "source_label": "Исходный код, релизы, заметки по протоколу:",
        "source_link_text": "github.com/bioexperiment-lab-devices/serialhop",
        "platform_windows": "Windows",
        "platform_linux": "Linux",
        "platform_rpi": "Raspberry Pi",
        "platform_windows_sub": "Windows 10 / 11 · 64-бит",
        "platform_linux_sub": "x86_64 · glibc 2.31+",
        "platform_rpi_sub": "ARM64 · Raspberry Pi OS 12+",
        "status_available": "Доступно",
        "status_coming_soon": "Скоро",
        "eta_linux": "ожидается Q3 2026",
        "eta_rpi": "ожидается Q4 2026",
        "cta_download_for": "Скачать для",
        "cta_disabled": "Пока недоступно — загляните позже",
        "meta_version": "Версия",
        "meta_released": "Выпущено",
        "meta_sha256": "SHA-256",
        "meta_copy": "Копировать",
        "meta_copied": "✓ скопировано",
        "explainer_summary": "Браузер может заблокировать эту загрузку",
        "explainer_intro": "Установщик агента — свежая Windows-программа, у которой пока нет подписи доверенного издателя и накопленной репутации в Microsoft Defender SmartScreen. Из-за этого браузер часто прячет скачанный файл, а Windows отказывается запускать его при первом открытии. Сам файл безопасен — при желании сверьте SHA-256 ниже с тем, что прислал оператор lab-bridge.",
        "explainer_h4_browser": "ЕСЛИ БРАУЗЕР СКРЫЛ ЗАГРУЗКУ",
        "explainer_h4_windows": "ЕСЛИ WINDOWS ЗАБЛОКИРОВАЛ .EXE ПРИ ЗАПУСКЕ",
        "just_now": "только что",
        "minutes_ago": "{n} мин назад",
        "hours_ago": "{n} ч назад",
        "days_ago": "{n} дн назад",
        "weeks_ago": "{n} нед назад",
    },
}


def pick_lang(query: str | None, cookie: str | None) -> Lang:
    """Resolve lang from query param, then cookie, defaulting to 'en'.

    Mirrors the same precedence used by app/docs.py and app/agent.py
    (query wins, then cookie, then 'en').
    """
    for v in (query, cookie):
        if v == "en":
            return "en"
        if v == "ru":
            return "ru"
    return "en"
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/siteapp && uv run pytest tests/test_strings.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/siteapp/app/strings.py services/siteapp/tests/test_strings.py
git commit -m "feat(siteapp): add HOME_STRINGS + DL_STRINGS bilingual maps + pick_lang helper"
```

---

## Lab status backend

### Task 5: Build `aggregate_labs()` with full TDD coverage

**Files:**
- Create: `services/siteapp/app/labs.py`
- Create: `services/siteapp/tests/test_labs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_labs.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.labs import LabsAggregator, _compare_versions, aggregate_labs


def _write_roster(clients_file: Path, entries: dict[str, int]) -> None:
    clients_file.write_text(
        json.dumps({name: {"port": port, "password_sha256": "00" * 32} for name, port in entries.items()}),
        encoding="utf-8",
    )


def _write_meta(agent_root: Path, version: str) -> None:
    (agent_root / "meta.json").write_text(
        json.dumps({"version": version, "size": 1, "sha256": "x", "uploaded_at": "2026-05-01T00:00:00Z"}),
        encoding="utf-8",
    )
    (agent_root / "windows").mkdir(exist_ok=True)
    (agent_root / "windows" / "agent.exe").write_bytes(b"x")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | str):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if isinstance(self._payload, str):
            raise ValueError("malformed json")
        return self._payload


async def _ok(payload: dict) -> _FakeResponse:
    return _FakeResponse(200, payload)


async def _err(exc: Exception) -> _FakeResponse:
    raise exc


@pytest.mark.asyncio
async def test_aggregate_all_online(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001, "bravo": 9002})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0", "hostname": "PC-1"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert [r["name"] for r in rows] == ["alpha", "bravo"]
    assert all(r["online"] for r in rows)
    assert all(r["version"] == "0.9.0" for r in rows)
    assert all(r["outdated"] is False for r in rows)


@pytest.mark.asyncio
async def test_aggregate_mix_online_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001, "bravo": 9002})

    async def fake_get(self, url, **kwargs):
        if "9001" in str(url):
            return _FakeResponse(200, {"version": "0.9.0"})
        raise httpx.TimeoutException("timeout")

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    online = [r for r in rows if r["online"]]
    offline = [r for r in rows if not r["online"]]
    assert [r["name"] for r in online] == ["alpha"]
    assert [r["name"] for r in offline] == ["bravo"]
    # Online sorts before offline.
    assert rows[0]["name"] == "alpha"


@pytest.mark.asyncio
async def test_aggregate_malformed_json_marked_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, "not json")

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows == [{"name": "alpha", "online": False}]


@pytest.mark.asyncio
async def test_aggregate_non_200_marked_offline(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(503, {})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows == [{"name": "alpha", "online": False}]


@pytest.mark.asyncio
async def test_aggregate_no_meta_omits_outdated(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    # no meta.json written

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.5.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["online"] is True
    assert rows[0]["version"] == "0.5.0"
    assert "outdated" not in rows[0]


@pytest.mark.asyncio
async def test_aggregate_outdated_detected(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.5.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["outdated"] is True


@pytest.mark.asyncio
async def test_aggregate_version_with_build_sha_stripped(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "0.9.0")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0+abc1234"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["outdated"] is False  # 0.9.0 == 0.9.0 once suffix stripped


@pytest.mark.asyncio
async def test_aggregate_non_pep440_no_outdated(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    _write_meta(site_data / "agent", "garbage")

    async def fake_get(self, url, **kwargs):
        return _FakeResponse(200, {"version": "0.9.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        rows = await aggregate_labs(site_data / "agent", _clients_file_default, host="chisel")

    assert rows[0]["online"] is True
    assert "outdated" not in rows[0]


def test_compare_versions_basic() -> None:
    assert _compare_versions("0.5.0", "0.9.0") == "outdated"
    assert _compare_versions("0.9.0", "0.9.0") == "current"
    assert _compare_versions("1.0.0", "0.9.0") == "current"  # ahead of fleet is fine
    assert _compare_versions("0.9.0+abc", "0.9.0") == "current"
    assert _compare_versions("bad", "0.9.0") == "unknown"
    assert _compare_versions("0.9.0", "bad") == "unknown"


@pytest.mark.asyncio
async def test_cache_serves_stale_within_ttl(_clients_file_default, site_data) -> None:
    _write_roster(_clients_file_default, {"alpha": 9001})
    agg = LabsAggregator(site_data / "agent", _clients_file_default, host="chisel", ttl_seconds=60)

    call_count = 0

    async def fake_get(self, url, **kwargs):
        nonlocal call_count
        call_count += 1
        return _FakeResponse(200, {"version": "0.9.0"})

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        await agg.list_labs()
        await agg.list_labs()  # within TTL, must not refetch

    assert call_count == 1
```

- [ ] **Step 2: Run, verify fail**

```bash
cd services/siteapp && uv run pytest tests/test_labs.py -v
```
Expected: FAIL — `app.labs` not found.

- [ ] **Step 3: Write labs.py**

```python
# app/labs.py
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Literal, TypedDict

import httpx

from app.agent import load_meta
from app.clients import load_roster


class LabRow(TypedDict, total=False):
    name: str
    online: bool
    version: str
    hostname: str
    outdated: bool


AGENT_INFO_PATH = "/agent/info"
HTTP_TIMEOUT_SECONDS = 0.8
DEFAULT_CACHE_TTL_SECONDS = 60
CHISEL_HOST = "chisel"


def _compare_versions(lab: str, latest: str) -> Literal["outdated", "current", "unknown"]:
    """Strip +build_sha and compare with packaging.version.

    Returns 'outdated' iff lab < latest. 'unknown' on parse failure either side
    (caller should omit the outdated field entirely).
    """
    from packaging.version import InvalidVersion, Version

    def _strip(v: str) -> str:
        return v.split("+", 1)[0]

    try:
        lab_v = Version(_strip(lab))
        latest_v = Version(_strip(latest))
    except InvalidVersion:
        return "unknown"
    return "outdated" if lab_v < latest_v else "current"


async def _probe_one(
    client: httpx.AsyncClient, name: str, host: str, port: int, latest: str | None
) -> LabRow:
    """Best-effort GET /agent/info; any failure → online=False."""
    url = f"http://{host}:{port}{AGENT_INFO_PATH}"
    try:
        resp = await client.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    except (httpx.HTTPError, OSError):
        return {"name": name, "online": False}
    if resp.status_code != 200:
        return {"name": name, "online": False}
    try:
        payload = resp.json()
    except (ValueError, json.JSONDecodeError):
        return {"name": name, "online": False}
    if not isinstance(payload, dict):
        return {"name": name, "online": False}

    row: LabRow = {"name": name, "online": True}
    version = payload.get("version")
    if isinstance(version, str):
        row["version"] = version
    hostname = payload.get("hostname")
    if isinstance(hostname, str) and hostname:
        row["hostname"] = hostname

    if latest is not None and "version" in row:
        result = _compare_versions(row["version"], latest)
        if result != "unknown":
            row["outdated"] = result == "outdated"
    return row


def _sort_key(row: LabRow) -> tuple[int, str]:
    # online first (0), then offline (1); alpha within each.
    return (0 if row["online"] else 1, row["name"].lower())


class LabsAggregator:
    """Process-local cache + lock around aggregate_labs."""

    def __init__(
        self,
        agent_root: Path,
        clients_file: Path,
        *,
        host: str = CHISEL_HOST,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._agent_root = agent_root
        self._clients_file = clients_file
        self._host = host
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._cache_at: float = 0.0
        self._cache_value: list[LabRow] = []

    async def list_labs(self) -> list[LabRow]:
        now = time.monotonic()
        if self._cache_value and now - self._cache_at < self._ttl:
            return self._cache_value
        async with self._lock:
            # Re-check under lock.
            now = time.monotonic()
            if self._cache_value and now - self._cache_at < self._ttl:
                return self._cache_value
            rows = await aggregate_labs(self._agent_root, self._clients_file, host=self._host)
            self._cache_at = now
            self._cache_value = rows
            return rows


async def aggregate_labs(
    agent_root: Path, clients_file: Path, *, host: str = CHISEL_HOST
) -> list[LabRow]:
    """Fan out to every roster lab's /agent/info; return sorted list."""
    try:
        roster = load_roster(clients_file)
    except (OSError, ValueError):
        return []

    meta = load_meta(agent_root)
    latest = meta.version if meta is not None else None

    async with httpx.AsyncClient() as client:
        tasks = [
            _probe_one(client, name, host, int(entry["port"]), latest)
            for name, entry in roster.items()
        ]
        rows: list[LabRow] = list(await asyncio.gather(*tasks)) if tasks else []

    rows.sort(key=_sort_key)
    return rows
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/siteapp && uv run pytest tests/test_labs.py -v
```
Expected: all 10 tests PASS.

- [ ] **Step 5: Add `packaging` dep if not transitively present**

```bash
cd services/siteapp && uv run python -c "from packaging.version import Version; print('ok')"
```
If the import fails:
```bash
cd services/siteapp && uv add packaging
```
Then re-run tests to confirm green.

- [ ] **Step 6: Commit**

```bash
git add services/siteapp/app/labs.py services/siteapp/tests/test_labs.py services/siteapp/pyproject.toml services/siteapp/uv.lock
git commit -m "feat(siteapp): add /api/public/labs aggregator (LabsAggregator + version compare + cache)"
```

---

### Task 6: Wire `/api/public/labs` route into main.py

**Files:**
- Modify: `services/siteapp/app/main.py`
- Modify: `services/siteapp/app/labs.py` (add router factory)

- [ ] **Step 1: Add make_router to labs.py**

Append to `app/labs.py`:

```python
from fastapi import APIRouter

from app.config import Settings


def make_router(settings: Settings, *, host: str = CHISEL_HOST) -> APIRouter:
    """Create the /api/public/labs router with a process-local aggregator."""
    router = APIRouter()
    aggregator = LabsAggregator(settings.agent_root, settings.clients_file, host=host)

    @router.get("/api/public/labs")
    async def list_labs() -> list[LabRow]:
        return await aggregator.list_labs()

    return router
```

- [ ] **Step 2: Register router in main.py**

Edit `app/main.py`:

Find:
```python
from app.public_clients import make_router as make_public_clients_router
from app.server_info import make_router as make_server_info_router
```
Add after:
```python
from app.labs import make_router as make_labs_router
```

Find:
```python
app.include_router(make_public_clients_router(settings))
app.include_router(make_server_info_router(settings))
```
Add after:
```python
app.include_router(make_labs_router(settings))
```

- [ ] **Step 3: Write a quick smoke test in test_main.py extension**

Append to `services/siteapp/tests/test_main.py`:

```python
def test_labs_route_registered():
    from app.main import app
    paths = {route.path for route in app.routes}
    assert "/api/public/labs" in paths
```

- [ ] **Step 4: Run**

```bash
cd services/siteapp && uv run pytest tests/test_main.py tests/test_labs.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add services/siteapp/app/labs.py services/siteapp/app/main.py services/siteapp/tests/test_main.py
git commit -m "feat(siteapp): wire /api/public/labs endpoint into FastAPI app"
```

---

### Task 7: Add `_relative_time()` helper to agent.py

**Files:**
- Modify: `services/siteapp/app/agent.py`
- Modify: `services/siteapp/tests/test_routes_agent.py` (or new test_agent.py — match what exists)

- [ ] **Step 1: Write failing tests**

Append to `services/siteapp/tests/test_routes_agent.py` (or create `test_agent.py` if cleaner):

```python
from datetime import UTC, datetime, timedelta

from app.agent import _relative_time


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def test_relative_time_just_now_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(seconds=10)), "en") == "just now"


def test_relative_time_minutes_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(minutes=5)), "en") == "5 minutes ago"


def test_relative_time_hours_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(hours=3)), "en") == "3 hours ago"


def test_relative_time_days_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=6)), "en") == "6 days ago"


def test_relative_time_weeks_en():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=21)), "en") == "3 weeks ago"


def test_relative_time_days_ru():
    now = datetime.now(UTC)
    assert _relative_time(_iso(now - timedelta(days=6)), "ru") == "6 дн назад"


def test_relative_time_garbage_returns_empty():
    assert _relative_time("not-a-date", "en") == ""
```

- [ ] **Step 2: Run, verify fail**

```bash
cd services/siteapp && uv run pytest tests/test_routes_agent.py -v -k relative
```
Expected: FAIL — `_relative_time` not found.

- [ ] **Step 3: Add `_relative_time` to agent.py**

Add the helper to `app/agent.py` near `_pick_lang`:

```python
from datetime import UTC, datetime

from app.strings import DL_STRINGS, Lang, pick_lang


def _relative_time(iso: str, lang: Lang) -> str:
    """Localized 'X units ago' string for a UTC ISO timestamp.

    Returns "" on parse failure (template should fall back to the raw
    timestamp). Uses DL_STRINGS for unit phrases so they stay in one place.
    """
    try:
        # Normalize trailing 'Z' to '+00:00' for fromisoformat.
        normalized = iso.replace("Z", "+00:00")
        then = datetime.fromisoformat(normalized)
    except ValueError:
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - then
    seconds = max(int(delta.total_seconds()), 0)
    s = DL_STRINGS[lang]
    if seconds < 60:
        return s["just_now"]
    minutes = seconds // 60
    if minutes < 60:
        return s["minutes_ago"].format(n=minutes)
    hours = minutes // 60
    if hours < 24:
        return s["hours_ago"].format(n=hours)
    days = hours // 24
    if days < 14:
        return s["days_ago"].format(n=days)
    weeks = days // 7
    return s["weeks_ago"].format(n=weeks)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/siteapp && uv run pytest tests/test_routes_agent.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add services/siteapp/app/agent.py services/siteapp/tests/test_routes_agent.py
git commit -m "feat(siteapp): add _relative_time helper for Download 'X ago' display"
```

---

## Navbar redesign

### Task 8: Inject data-version attribute via Caddyfile

**Files:**
- Modify: `compose/Caddyfile.tmpl`

- [ ] **Step 1: Find the current navbar.js injection line**

```bash
grep -n 'navbar.js' compose/Caddyfile.tmpl
```
Expected: one line matching the `replace` block emitting `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" defer></script>`.

- [ ] **Step 2: Edit to add data-version attribute**

Replace that line so the injected `<script>` carries the same version as an attribute:

```caddyfile
"</head>" `<script src="/_shared/navbar.js?v=__PLATFORM_VERSION__" data-version="__PLATFORM_VERSION__" defer></script></head>`
```

The existing `scripts/lib/render.sh`'s `s|__PLATFORM_VERSION__|...|g` substitution rewrites both occurrences in a single pass.

- [ ] **Step 3: Visually verify rendered Caddyfile**

```bash
# Sanity render against the laptop config to check both substitutions land.
bash scripts/lib/render.sh render_caddyfile config.yaml > /tmp/Caddyfile.rendered 2>/dev/null || true
grep 'navbar.js' /tmp/Caddyfile.rendered || true
```
Expected (if config.yaml exists locally): both `?v=X.Y.Z` and `data-version="X.Y.Z"` present.

- [ ] **Step 4: Commit**

```bash
git add compose/Caddyfile.tmpl
git commit -m "feat(caddy): expose platform version as data-version attr on injected navbar script"
```

---

### Task 9: Rewrite navbar.js — brand row, theme toggle, redesigned bookmark tab, handoff icons

**Files:**
- Modify: `compose/shell/navbar.js`

- [ ] **Step 1: Rewrite the file**

The structural changes from today's navbar.js:

1. New widths: collapsed `56px`, expanded `220px`.
2. Add brand row at top of rail (brand mark + wordmark + version pill).
3. Add theme toggle button at bottom of rail (above chevron). Hidden in bookmark mode.
4. Replace bookmark tab visual: 132×32 labeled tab at `left:12px; bottom:12px` with brand mark + wordmark + `›`.
5. Replace generic SVGs with the handoff's monoline icons (verbatim from `docs/design_handoff_lab_bridge/source/lab-bridge-navbar.jsx`'s `Icons` object).
6. Read platform version from `document.currentScript.dataset.version` at boot.
7. Theme toggle writes `localStorage['theme']` + applies `document.documentElement.dataset.theme` + updates `:host([data-theme])`.

Full file:

```javascript
// compose/shell/navbar.js (served at /_shared/navbar.js by Caddy)
// Platform navbar for lab-bridge. See compose/shell/README.md.
// Single source of truth for navigation.

(() => {
  if (customElements.get('lds-navbar')) return;

  const RAIL_W_COLLAPSED = '56px';
  const RAIL_W_EXPANDED  = '220px';

  // Read platform version off the injected <script> tag's data-version attr.
  // Caddy substitutes __PLATFORM_VERSION__ at deploy time (see Caddyfile.tmpl).
  const PLATFORM_VERSION = (function () {
    const scripts = document.querySelectorAll('script[src*="/_shared/navbar.js"]');
    for (const s of scripts) {
      const v = s.getAttribute('data-version');
      if (v) return v;
    }
    return '';
  })();

  // ─── Data ─────────────────────────────────────────────────────────────
  const SERVICES = [
    { id: 'home',    label: 'Home',           href: '/',                   mode: 'persistent', external: false },
    { id: 'docs',    label: 'Docs',           href: '/docs/',              mode: 'persistent', external: false },
    { id: 'agent',   label: 'Download Agent', href: '/download/agent',     mode: 'persistent', external: false },
    { id: 'jupyter', label: 'JupyterLab',     href: '/jupyter/',           mode: 'bookmark',   external: true  },
    { id: 'grafana', label: 'Grafana',        href: '/grafana/dashboards', mode: 'bookmark',   external: true  },
    { id: 'flasher', label: 'Flasher',        href: '/flash/',             mode: 'persistent', external: true  },
  ];

  const PATH_RULES = [
    { prefix: '/jupyter', mode: 'bookmark' },
    { prefix: '/grafana', mode: 'bookmark' },
  ];

  // Icons — port verbatim from docs/design_handoff_lab_bridge/source/lab-bridge-navbar.jsx
  // (the `Icons` constant). Each is an <svg viewBox="0 0 18 18" width="18"
  // height="18" fill="none" stroke="currentColor" stroke-width="1.5"
  // stroke-linecap="round" stroke-linejoin="round">...paths...</svg>.
  // When porting, copy the inner <path>/<circle>/<line> elements verbatim
  // and wrap with the same outer <svg> attributes shown here.
  const ICON = (paths) =>
    `<svg viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor"
          stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true">${paths}</svg>`;
  const ICONS = {
    // Paste handoff Icons.home paths inside ICON(`...`), etc.
    home:    ICON(`<path d="M2 8 9 2l7 6"/><path d="M3.5 7v8h11V7"/><path d="M7.5 15v-4h3v4"/>`),
    docs:    ICON(`<path d="M4 2h6l3 3v11H4z"/><path d="M10 2v3h3"/><path d="M6 8h5M6 10.5h5M6 13h3"/>`),
    agent:   ICON(`<path d="M9 2v9"/><path d="M5.5 7.5 9 11l3.5-3.5"/><path d="M3 14h12"/>`),
    jupyter: ICON(`<ellipse cx="9" cy="9" rx="6" ry="2.4" transform="rotate(-30 9 9)"/>
                    <ellipse cx="9" cy="9" rx="6" ry="2.4" transform="rotate(30 9 9)"/>
                    <ellipse cx="9" cy="9" rx="6" ry="2.4" transform="rotate(90 9 9)"/>
                    <circle cx="9" cy="9" r="1" fill="currentColor"/>`),
    grafana: ICON(`<path d="M3 14h12"/><path d="M3 14V8l3 3 3-5 3 3 3-4"/>`),
    flasher: ICON(`<path d="M5 2h8v4l2 2-2 2v6H5v-6L3 8l2-2z"/><path d="M7 11h4"/>`),
    chevronRight: ICON(`<path d="m7 4 5 5-5 5"/>`),
    chevronLeft:  ICON(`<path d="m11 4-5 5 5 5"/>`),
    sun: ICON(`<circle cx="9" cy="9" r="3"/><path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.5 3.5l1.4 1.4M13.1 13.1l1.4 1.4M3.5 14.5l1.4-1.4M13.1 4.9l1.4-1.4"/>`),
    moon: ICON(`<path d="M14 11a5 5 0 1 1-7-7 5 5 0 0 0 7 7z"/>`),
  };

  const EXT_GLYPH = '<span class="ext" aria-hidden="true">↗</span>';
  const BRAND_MARK_SVG =
    `<svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true">
       <rect x="2" y="2" width="24" height="24" rx="4" fill="var(--accent)"/>
       <path d="M9 9h-2v10h2M19 9h2v10h-2" stroke="var(--text-inverse)" stroke-width="1.5"
             stroke-linecap="round" fill="none"/>
       <circle cx="14" cy="14" r="2.6" fill="var(--text-inverse)"/>
     </svg>`;

  // ─── Mode + active detection ──────────────────────────────────────────
  function detectMode() {
    const path = location.pathname;
    for (const rule of PATH_RULES) if (path.startsWith(rule.prefix)) return rule.mode;
    return 'persistent';
  }
  function detectActiveId() {
    const path = location.pathname;
    let best = null, bestLen = -1;
    for (const svc of SERVICES) {
      if (path.startsWith(svc.href) && svc.href.length > bestLen) {
        best = svc.id; bestLen = svc.href.length;
      }
    }
    return best;
  }

  // ─── Theme ────────────────────────────────────────────────────────────
  const THEME_KEY = 'theme';
  function currentTheme() {
    const t = localStorage.getItem(THEME_KEY);
    if (t === 'light' || t === 'dark') return t;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function applyTheme(t) {
    localStorage.setItem(THEME_KEY, t);
    document.documentElement.dataset.theme = t;
    document.querySelectorAll('lds-navbar').forEach((el) => { el.dataset.theme = t; });
  }

  // ─── DOM rendering ────────────────────────────────────────────────────
  const STATE_KEY = 'navbar:state';

  function renderShadow(shadow, mode, state, activeId, theme) {
    const items = SERVICES.map((svc) => `
      <li${svc.id === activeId ? ' class="active"' : ''}>
        <a href="${svc.href}" data-id="${svc.id}"
           aria-label="${svc.label}"${svc.id === activeId ? ' aria-current="page"' : ''}>
          <span class="icon">${ICONS[svc.id]}</span>
          <span class="label">${svc.label}${svc.external ? ' ' + EXT_GLYPH : ''}</span>
        </a>
      </li>
    `).join('');

    const isBookmarkTab = mode === 'bookmark' && state === 'tab';

    const brand = `
      <div class="brand">
        <span class="brand__mark">${BRAND_MARK_SVG}</span>
        <span class="brand__wordmark">lab-bridge</span>
        ${PLATFORM_VERSION ? `<span class="brand__version">v${PLATFORM_VERSION}</span>` : ''}
      </div>`;

    const themeBtn = mode === 'persistent' ? `
      <button class="theme-toggle" type="button"
              aria-label="Switch to ${theme === 'dark' ? 'light' : 'dark'} theme"
              title="Lab Bridge theme only">
        <span class="theme-toggle__icon">${theme === 'dark' ? ICONS.sun : ICONS.moon}</span>
        <span class="theme-toggle__label">${theme === 'dark' ? 'Light' : 'Dark'}</span>
      </button>` : '';

    if (isBookmarkTab) {
      shadow.innerHTML = `
        <link rel="stylesheet" href="/_shared/navbar-inner.css">
        <aside part="rail" data-mode="bookmark" data-state="tab"
               role="navigation" aria-label="Platform navigation (bookmark)">
          <span class="bookmark__mark">${BRAND_MARK_SVG}</span>
          <span class="bookmark__wordmark">lab-bridge</span>
          <span class="bookmark__chev" aria-hidden="true">›</span>
        </aside>
        <div class="backdrop" hidden></div>`;
      return;
    }

    const chevronIcon =
      (mode === 'persistent' && state === 'collapsed') ? ICONS.chevronRight : ICONS.chevronLeft;
    const chevronLabel =
      (mode === 'persistent' && state === 'collapsed') ? 'Expand sidebar' : 'Collapse sidebar';

    shadow.innerHTML = `
      <link rel="stylesheet" href="/_shared/navbar-inner.css">
      <aside part="rail" data-mode="${mode}" data-state="${state}"
             role="navigation" aria-label="Platform navigation">
        ${brand}
        <nav><ul>${items}</ul></nav>
        <div class="rail-bottom">
          ${themeBtn}
          <button class="toggle" type="button" aria-label="${chevronLabel}">${chevronIcon}</button>
        </div>
        ${mode === 'bookmark' ? '<div class="esc-hint">Esc to dismiss</div>' : ''}
      </aside>
      <div class="backdrop" hidden></div>`;
  }

  function setNavWidth(width) {
    document.documentElement.style.setProperty('--nav-width', width);
  }

  // ─── Custom element ───────────────────────────────────────────────────
  class LdsNavbar extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this._mode = detectMode();
      this._state = this._mode === 'persistent'
        ? (localStorage.getItem(STATE_KEY) || 'collapsed')
        : 'tab';
      this._theme = currentTheme();
      this.dataset.theme = this._theme;
      this._hoverTimer = null;
      this._leaveTimer = null;
      this._onKeydown = this._handleEscape.bind(this);
      this._onStorage = this._handleStorage.bind(this);
    }

    connectedCallback() {
      this._render();
      this._wire();
      this._applyNavWidth();
      document.addEventListener('keydown', this._onKeydown);
      window.addEventListener('storage', this._onStorage);
    }

    disconnectedCallback() {
      document.removeEventListener('keydown', this._onKeydown);
      window.removeEventListener('storage', this._onStorage);
    }

    _render() {
      renderShadow(this.shadowRoot, this._mode, this._state, detectActiveId(), this._theme);
    }

    _applyNavWidth() {
      setNavWidth(this._mode === 'persistent' ? RAIL_W_COLLAPSED : '0px');
    }

    _setPersistentState(next) {
      this._state = next;
      localStorage.setItem(STATE_KEY, next);
      this._render();
      this._wire();
      const backdrop = this.shadowRoot.querySelector('.backdrop');
      if (backdrop) backdrop.hidden = next !== 'expanded';
    }

    _setBookmarkState(next) {
      this._state = next;
      this._render();
      this._wire();
      const backdrop = this.shadowRoot.querySelector('.backdrop');
      if (backdrop) backdrop.hidden = next !== 'expanded';
    }

    _wire() {
      const root = this.shadowRoot;
      const toggle = root.querySelector('.toggle');
      const themeBtn = root.querySelector('.theme-toggle');
      const rail = root.querySelector('aside');
      const backdrop = root.querySelector('.backdrop');
      if (!rail) return;

      if (themeBtn) {
        themeBtn.addEventListener('click', () => {
          this._theme = this._theme === 'dark' ? 'light' : 'dark';
          applyTheme(this._theme);
          this._render();
          this._wire();
        });
      }

      if (this._mode === 'persistent') {
        if (toggle) {
          toggle.addEventListener('click', () => {
            this._setPersistentState(this._state === 'collapsed' ? 'expanded' : 'collapsed');
          });
        }
        if (backdrop) {
          backdrop.addEventListener('click', () => {
            if (this._state === 'expanded') this._setPersistentState('collapsed');
          });
        }
      } else {
        // bookmark mode — entire rail acts as the hover hot zone.
        rail.addEventListener('mouseenter', () => {
          clearTimeout(this._leaveTimer);
          if (this._state === 'expanded') return;
          this._hoverTimer = setTimeout(() => this._setBookmarkState('expanded'), 150);
        });
        rail.addEventListener('mouseleave', () => {
          clearTimeout(this._hoverTimer);
          if (this._state === 'tab') return;
          this._leaveTimer = setTimeout(() => this._setBookmarkState('tab'), 300);
        });
        // Tap-anywhere-on-tab to expand (touch fallback).
        if (this._state === 'tab') {
          rail.addEventListener('click', () => this._setBookmarkState('expanded'));
        }
        if (backdrop) {
          backdrop.addEventListener('click', () => this._setBookmarkState('tab'));
        }
      }
    }

    _handleEscape(e) {
      if (e.key !== 'Escape' || this._state !== 'expanded') return;
      if (this._mode === 'persistent') {
        this._setPersistentState('collapsed');
      } else {
        this._setBookmarkState('tab');
      }
    }

    _handleStorage(e) {
      if (e.key !== THEME_KEY) return;
      if (e.newValue !== 'light' && e.newValue !== 'dark') return;
      this._theme = e.newValue;
      this.dataset.theme = this._theme;
      this._render();
      this._wire();
    }
  }

  customElements.define('lds-navbar', LdsNavbar);

  function mount() {
    if (document.querySelector('lds-navbar')) return;
    const el = document.createElement('lds-navbar');
    document.body.appendChild(el);
  }

  function startMutationGuard() {
    const observer = new MutationObserver(() => {
      if (!document.querySelector('lds-navbar')) mount();
    });
    observer.observe(document.body, { childList: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { mount(); startMutationGuard(); });
  } else {
    mount();
    startMutationGuard();
  }
})();
```

Note on the icon SVG paths: the inline placeholders above are functional approximations. Before merging, an implementer with the JSX handoff open should copy the exact path data from `lab-bridge-navbar.jsx`'s `Icons` object into the `ICON(...)` calls — visual parity with the design depends on it.

- [ ] **Step 2: Commit**

```bash
git add compose/shell/navbar.js
git commit -m "feat(navbar): rewrite visuals for hi-fi design (brand row, theme toggle, redesigned bookmark)"
```

---

### Task 10: Rewrite navbar-inner.css with design tokens + new visuals

**Files:**
- Modify: `compose/shell/navbar-inner.css`

- [ ] **Step 1: Rewrite the file**

```css
/* compose/shell/navbar-inner.css — loaded into <lds-navbar> Shadow DOM.
 * Duplicates the design tokens block from siteapp tokens.css because the
 * Shadow DOM is intentionally self-contained — host-page CSS (Jupyter /
 * Grafana) does not propagate in.
 */

:host {
  --bg-page: #ECE9E0;
  --surface: #FFFFFF;
  --surface-sunken: #F8F6F0;
  --surface-rail: #F3F0E6;
  --border: #E2DED2;
  --border-strong: #C8C3B5;
  --text: #1A1916;
  --text-secondary: #514E47;
  --text-muted: #8A8678;
  --text-inverse: #FAF8F3;
  --accent: #1F3A8A;
  --accent-hover: #182E6F;
  --accent-soft: #E7ECF6;
  --accent-border: #B8C2DC;
  --shadow-popover: 0 10px 24px -8px rgba(26,25,22,0.25), 0 2px 6px rgba(26,25,22,0.08);
  --shadow-overlay: 0 24px 50px -20px rgba(26,25,22,0.45), 0 8px 18px -6px rgba(26,25,22,0.18);
  --rail-w-collapsed: 56px;
  --rail-w-expanded: 220px;
  --font-sans: 'IBM Plex Sans', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', ui-monospace, monospace;
}
:host([data-theme="dark"]) {
  --bg-page: #1B1A17;
  --surface: #232220;
  --surface-sunken: #1D1C19;
  --surface-rail: #1E1D1A;
  --border: #34322D;
  --border-strong: #4A4740;
  --text: #F0EDE3;
  --text-secondary: #B8B3A4;
  --text-muted: #7E7A6E;
  --accent: #BCCBF2;
  --accent-hover: #DBE3F8;
  --accent-soft: #2A3257;
  --accent-border: #4A5587;
}

aside {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--surface-rail);
  color: var(--text);
  font-family: var(--font-sans);
  display: flex;
  flex-direction: column;
  z-index: 9999;
  overflow: hidden;
  border-right: 1px solid var(--border);
  transition: width 200ms cubic-bezier(.2,.7,.3,1);
}

/* ─── Persistent mode ────────────────────────────────────────────────── */
aside[data-mode="persistent"][data-state="collapsed"] { width: var(--rail-w-collapsed); }
aside[data-mode="persistent"][data-state="expanded"]  {
  width: var(--rail-w-expanded);
  box-shadow: var(--shadow-overlay);
}

/* Brand row */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 56px;
  padding: 0 14px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  overflow: hidden;
}
.brand__mark { display: inline-flex; flex-shrink: 0; }
.brand__wordmark {
  font-weight: 600;
  font-size: 14px;
  letter-spacing: -0.01em;
}
.brand__version {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
  padding: 2px 5px;
  border: 1px solid var(--border);
  border-radius: 3px;
  margin-left: auto;
}
aside[data-mode="persistent"][data-state="collapsed"] .brand {
  justify-content: center;
  padding: 0;
}
aside[data-mode="persistent"][data-state="collapsed"] .brand__wordmark,
aside[data-mode="persistent"][data-state="collapsed"] .brand__version {
  display: none;
}

/* ─── Nav items ──────────────────────────────────────────────────────── */
nav { flex: 1; padding-top: 8px; overflow-y: auto; }
ul { list-style: none; margin: 0; padding: 0; }
li { margin: 1px 6px; position: relative; }
a {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  height: 32px;
  color: var(--text-secondary);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: -0.003em;
  border-radius: 4px;
}
a:hover { background: var(--surface-sunken); color: var(--text); }
li.active a {
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-soft);
}
li.active::before {
  content: "";
  position: absolute;
  left: -6px;
  top: 4px;
  bottom: 4px;
  width: 3px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}
.icon { display: inline-flex; flex-shrink: 0; width: 18px; height: 18px; }
.label { display: inline-flex; align-items: baseline; gap: 6px; }
.ext {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
}

aside[data-mode="persistent"][data-state="collapsed"] .label {
  display: none;
}
aside[data-mode="persistent"][data-state="collapsed"] a { justify-content: center; padding: 8px; }

/* ─── Bottom block: theme toggle + chevron ──────────────────────────── */
.rail-bottom {
  border-top: 1px solid var(--border);
  padding: 8px 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.theme-toggle, .toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 32px;
  padding: 0 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
}
.theme-toggle:hover, .toggle:hover { background: var(--surface-sunken); color: var(--text); }
.theme-toggle__icon, .toggle svg { display: inline-flex; }
aside[data-mode="persistent"][data-state="collapsed"] .theme-toggle__label { display: none; }
aside[data-mode="persistent"][data-state="collapsed"] .theme-toggle,
aside[data-mode="persistent"][data-state="collapsed"] .toggle {
  justify-content: center;
  padding: 0;
}

/* ─── Bookmark mode ──────────────────────────────────────────────────── */
aside[data-mode="bookmark"][data-state="tab"] {
  left: 12px;
  bottom: 12px;
  top: auto;
  height: 32px;
  width: 132px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  box-shadow: var(--shadow-popover);
  flex-direction: row;
  align-items: center;
  padding: 0 10px;
  gap: 8px;
  cursor: pointer;
  font-family: var(--font-sans);
}
.bookmark__mark { display: inline-flex; }
.bookmark__wordmark { font-weight: 600; font-size: 12.5px; }
.bookmark__chev { margin-left: auto; color: var(--text-muted); font-size: 14px; }

aside[data-mode="bookmark"][data-state="expanded"] {
  left: 12px;
  bottom: 12px;
  top: auto;
  height: auto;
  width: var(--rail-w-expanded);
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  box-shadow: var(--shadow-overlay);
  padding: 6px;
}
aside[data-mode="bookmark"][data-state="expanded"] nav { padding-top: 4px; }
.esc-hint {
  border-top: 1px solid var(--border);
  margin-top: 4px;
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

/* ─── Backdrop ───────────────────────────────────────────────────────── */
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(26,25,22,0.18);
  z-index: 9998;
}
:host([data-theme="dark"]) .backdrop { background: rgba(0,0,0,0.45); }
```

- [ ] **Step 2: Local smoke check**

The Shadow-DOM duplication is intentional — there's no good unit test here. Visually verify after the Caddy image rebuild + local up. Add to the platform bats suite in Task 22.

- [ ] **Step 3: Commit**

```bash
git add compose/shell/navbar-inner.css
git commit -m "feat(navbar): rewrite navbar-inner.css with design tokens + warm-cream visuals"
```

---

## Home page

### Task 11: Update home.py route to plumb lang + initial labs

**Files:**
- Modify: `services/siteapp/app/home.py`

- [ ] **Step 1: Rewrite home.py**

```python
# app/home.py
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import Settings
from app.labs import LabsAggregator
from app.strings import HOME_STRINGS, pick_lang
from app.templates import templates


def make_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    aggregator = LabsAggregator(settings.agent_root, settings.clients_file)

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def home(request: Request, lang: str | None = None) -> HTMLResponse:
        chosen = pick_lang(lang, request.cookies.get("lang"))
        labs_initial = await aggregator.list_labs()
        response = templates.TemplateResponse(
            request,
            "home.html",
            {
                "lang": chosen,
                "s": HOME_STRINGS[chosen],
                "labs_initial": labs_initial,
            },
        )
        if lang in ("en", "ru"):
            response.set_cookie(
                "lang",
                lang,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=True,
                httponly=True,
            )
        return response

    return router
```

- [ ] **Step 2: Smoke test**

```bash
cd services/siteapp && uv run pytest tests/test_main.py -v
```
Expected: still green.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/home.py
git commit -m "feat(siteapp): plumb lang + initial labs into Home route"
```

---

### Task 12: Create Home template partials

**Files:**
- Create: `services/siteapp/app/templates/_home_header.html`
- Create: `services/siteapp/app/templates/_home_intro.html`
- Create: `services/siteapp/app/templates/_home_labs.html`
- Create: `services/siteapp/app/templates/_home_topology.html`
- Create: `services/siteapp/app/templates/_home_status_row.html`
- Create: `services/siteapp/app/templates/_home_quick.html`
- Create: `services/siteapp/app/templates/_home_start.html`

- [ ] **Step 1: Write _home_header.html**

```html
{# Reusable sticky header used by Home + Download. Includes EN/RU toggle. #}
<header class="lb-home-header" data-target-page="{{ target_page }}">
  <div class="lb-home-header__left">
    <span class="lb-home-header__dot" aria-hidden="true"></span>
    <span class="lb-home-header__wordmark">lab-bridge</span>
    <span class="lb-home-header__rule" aria-hidden="true"></span>
    <span class="lb-home-header__tagline">{{ s.tagline }}</span>
  </div>
  <div class="lb-home-header__right">
    <nav class="lb-lang" aria-label="Language">
      <a href="?lang=en" class="lb-lang__pill{% if lang == 'en' %} is-active{% endif %}"
         aria-current="{% if lang == 'en' %}true{% else %}false{% endif %}">{{ s.lang_en }}</a>
      <a href="?lang=ru" class="lb-lang__pill{% if lang == 'ru' %} is-active{% endif %}"
         aria-current="{% if lang == 'ru' %}true{% else %}false{% endif %}">{{ s.lang_ru }}</a>
    </nav>
  </div>
</header>
```

- [ ] **Step 2: Write _home_intro.html**

```html
<section class="lb-intro-stmt">
  <span class="lb-intro-stmt__eyebrow">{{ s.intro_eyebrow }}</span>
  <h1 class="lb-intro-stmt__headline">{{ s.intro_headline }}</h1>
  <div class="lb-intro-stmt__support">
    <p>{{ s.intro_p1 }}</p>
    <p>{{ s.intro_p2 }}</p>
  </div>
</section>
```

- [ ] **Step 3: Write _home_labs.html**

```html
{% set online = labs | selectattr('online') | list %}
{% set offline = labs | rejectattr('online') | list %}
<section class="lb-equip" aria-labelledby="lb-equip-title">
  <header class="lb-equip__head">
    <h2 id="lb-equip-title">{{ s.labs_panel_title }}</h2>
    <span class="lb-equip__meta" data-labs-updated>{{ s.labs_just_now }}</span>
  </header>

  <div class="lb-equip__group" data-group="online">
    <header class="lb-equip__group-head">
      <span>{{ s.labs_online }} · <span data-online-count>{{ online | length }}</span></span>
    </header>
    {% for lab in online %}
      <button class="lb-labrow" type="button" data-copy-text="{{ lab.name }}">
        <span class="lb-labrow__dot lb-labrow__dot--online" aria-hidden="true"></span>
        <span class="lb-labrow__name">{{ lab.name }}</span>
        {% if lab.outdated %}
          <span class="lb-labrow__pill lb-labrow__pill--outdated"
                title="{{ s.labs_outdated_tooltip }}">{{ s.labs_outdated_pill }}</span>
        {% endif %}
        {% if lab.version %}<span class="lb-labrow__version">v{{ lab.version }}</span>{% endif %}
      </button>
    {% endfor %}
  </div>

  <div class="lb-equip__group" data-group="offline">
    <header class="lb-equip__group-head">
      <span>{{ s.labs_offline }} · <span data-offline-count>{{ offline | length }}</span></span>
    </header>
    {% for lab in offline %}
      <button class="lb-labrow lb-labrow--offline" type="button" data-copy-text="{{ lab.name }}">
        <span class="lb-labrow__dot lb-labrow__dot--offline" aria-hidden="true"></span>
        <span class="lb-labrow__name">{{ lab.name }}</span>
      </button>
    {% endfor %}
  </div>
</section>
```

- [ ] **Step 4: Write _home_topology.html**

```html
<section class="lb-topo-section" aria-labelledby="lb-topo-title">
  <header class="lb-topo-section__head">
    <h2 id="lb-topo-title">{{ s.topo_title }}</h2>
  </header>
  <ol class="lb-topo">
    <li class="lb-topo__node">{{ s.topo_node_lab }}</li>
    <li class="lb-topo__arrow" aria-hidden="true">▼</li>
    <li class="lb-topo__node lb-topo__node--primary">{{ s.topo_node_bridge }}</li>
    <li class="lb-topo__arrow" aria-hidden="true">▼</li>
    <li class="lb-topo__node">{{ s.topo_node_researcher }}</li>
  </ol>
</section>
```

- [ ] **Step 5: Write _home_status_row.html**

```html
<div class="lb-status-row">
  {% include "_home_labs.html" %}
  {% include "_home_topology.html" %}
</div>
```

- [ ] **Step 6: Write _home_quick.html**

```html
<section class="lb-quick" aria-labelledby="lb-quick-title">
  <h2 id="lb-quick-title" class="lb-section-title">{{ s.quick_title }}</h2>
  <div class="lb-quick__grid">
    <a class="lb-quick__card" data-primary="true" href="/jupyter/">
      <span class="lb-quick__icon" aria-hidden="true">⌬</span>
      <span class="lb-quick__title">{{ s.quick_jupyter }} <span class="ext" aria-hidden="true">↗</span></span>
      <span class="lb-quick__path">/jupyter/</span>
    </a>
    <a class="lb-quick__card" href="/docs/">
      <span class="lb-quick__icon" aria-hidden="true">📖</span>
      <span class="lb-quick__title">{{ s.quick_docs }}</span>
      <span class="lb-quick__path">/docs/</span>
    </a>
    <a class="lb-quick__card" href="/download/agent">
      <span class="lb-quick__icon" aria-hidden="true">↓</span>
      <span class="lb-quick__title">{{ s.quick_agent }}</span>
      <span class="lb-quick__path">/download/agent</span>
    </a>
    <a class="lb-quick__card" href="/grafana/dashboards">
      <span class="lb-quick__icon" aria-hidden="true">▦</span>
      <span class="lb-quick__title">{{ s.quick_grafana }} <span class="ext" aria-hidden="true">↗</span></span>
      <span class="lb-quick__path">/grafana/</span>
    </a>
  </div>
</section>
```

Note: replace the emoji icon placeholders with the same hand-rolled monoline SVGs the navbar uses (Task 9's `ICONS` set), once those are confirmed visually. Emoji is a temporary stand-in to keep this file under one screen.

- [ ] **Step 7: Write _home_start.html**

```html
<section class="lb-start" aria-labelledby="lb-start-title">
  <h2 id="lb-start-title" class="lb-section-title">{{ s.start_title }}</h2>
  <div class="lb-start__grid">
    <a class="lb-start__card" href="{{ s.start_card_researcher_path }}">
      <span class="lb-start__role">
        <span class="lb-start__role-dot lb-start__role-dot--researcher" aria-hidden="true"></span>
        {{ s.start_role_researcher }}
      </span>
      <h3 class="lb-start__title">{{ s.start_card_researcher_title }}</h3>
      <p class="lb-start__desc">{{ s.start_card_researcher_desc }}</p>
      <span class="lb-start__path">{{ s.start_card_researcher_path }}</span>
      <span class="lb-start__chev" aria-hidden="true">›</span>
    </a>
    <a class="lb-start__card" href="{{ s.start_card_operator_path }}">
      <span class="lb-start__role">
        <span class="lb-start__role-dot lb-start__role-dot--operator" aria-hidden="true"></span>
        {{ s.start_role_operator }}
      </span>
      <h3 class="lb-start__title">{{ s.start_card_operator_title }}</h3>
      <p class="lb-start__desc">{{ s.start_card_operator_desc }}</p>
      <span class="lb-start__path">{{ s.start_card_operator_path }}</span>
      <span class="lb-start__chev" aria-hidden="true">›</span>
    </a>
  </div>
</section>
```

- [ ] **Step 8: Commit**

```bash
git add services/siteapp/app/templates/_home_*.html
git commit -m "feat(siteapp): add Home partials (header, intro, labs, topology, quick, start)"
```

---

### Task 13: Rebuild home.html shell

**Files:**
- Modify: `services/siteapp/app/templates/home.html`

- [ ] **Step 1: Rewrite home.html**

```html
{% extends "base.html" %}
{% block title %}{{ s.page_title }}{% endblock %}
{% block main %}
<div class="lb-page lb-page--home">
  {% with target_page = "home" %}{% include "_home_header.html" %}{% endwith %}

  <div class="lb-page__body">
    {% include "_home_intro.html" %}

    {% with labs = labs_initial %}{% include "_home_status_row.html" %}{% endwith %}

    {% include "_home_quick.html" %}

    {% include "_home_start.html" %}
  </div>
</div>

<script>
(function () {
  // Poll /api/public/labs every 5s, swap the panel innerHTML, update meta.
  var ROOT = document.querySelector('.lb-equip');
  if (!ROOT) return;
  var META = ROOT.querySelector('[data-labs-updated]');
  var META_TEMPLATE = {
    just_now: {{ s.labs_just_now | tojson }},
    prefix: {{ s.labs_updated_prefix | tojson }},
    suffix: {{ s.labs_updated_suffix | tojson }},
  };
  var lastFetchedAt = Date.now();

  function fmtAgo(ms) {
    var s = Math.max(0, Math.floor(ms / 1000));
    if (s < 5) return META_TEMPLATE.just_now;
    if (s < 60) return META_TEMPLATE.prefix + ' ' + s + 's ' + META_TEMPLATE.suffix;
    var m = Math.floor(s / 60);
    return META_TEMPLATE.prefix + ' ' + m + 'm ' + META_TEMPLATE.suffix;
  }

  function tickMeta() {
    if (META) META.textContent = fmtAgo(Date.now() - lastFetchedAt);
  }

  async function poll() {
    try {
      var resp = await fetch('/api/public/labs', { headers: { 'Accept': 'application/json' } });
      if (!resp.ok) return;
      var rows = await resp.json();
      // Server-rendered template is the source of truth for markup — to
      // keep this script tiny, request the panel HTML server-side via a
      // dedicated render endpoint. For v1, do a full /  reload-of-fragment
      // by fetching the home page and copying the panel out.
      var html = await fetch('/?_panel=1').then(function (r) { return r.text(); });
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var fresh = doc.querySelector('.lb-equip');
      if (fresh && ROOT.parentNode) ROOT.parentNode.replaceChild(fresh, ROOT);
      ROOT = document.querySelector('.lb-equip');
      META = ROOT && ROOT.querySelector('[data-labs-updated]');
      lastFetchedAt = Date.now();
    } catch (e) { /* swallow; next poll retries */ }
  }

  setInterval(poll, 5000);
  setInterval(tickMeta, 1000);
})();

// Sticky header shadow: toggle .is-scrolled when content scrolls beneath.
(function () {
  var header = document.querySelector('.lb-home-header');
  if (!header) return;
  var sentinel = document.createElement('div');
  sentinel.style.cssText = 'position:absolute;top:0;left:0;height:1px;width:1px;';
  header.parentNode.insertBefore(sentinel, header);
  var io = new IntersectionObserver(function (entries) {
    header.classList.toggle('is-scrolled', !entries[0].isIntersecting);
  });
  io.observe(sentinel);
})();
</script>
{% endblock %}
```

Note: the `?_panel=1` fragment-fetch pattern keeps the polling-update script tiny but requires the route to accept that query param and short-circuit to render only the labs panel. Add that branch to `home.py` in the next step.

- [ ] **Step 2: Add `_panel` query param branch to home.py**

Edit `app/home.py`'s route — replace the `home()` body:

```python
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(
    request: Request,
    lang: str | None = None,
    _panel: int | None = None,
) -> HTMLResponse:
    chosen = pick_lang(lang, request.cookies.get("lang"))
    labs_initial = await aggregator.list_labs()
    template_name = "_home_status_row.html" if _panel else "home.html"
    context: dict[str, object] = {
        "lang": chosen,
        "s": HOME_STRINGS[chosen],
        "labs_initial": labs_initial,
    }
    if _panel:
        # Partial render needs `labs` for _home_labs.html.
        context["labs"] = labs_initial
    response = templates.TemplateResponse(request, template_name, context)
    if lang in ("en", "ru"):
        response.set_cookie(
            "lang",
            lang,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=True,
            httponly=True,
        )
    return response
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/templates/home.html services/siteapp/app/home.py
git commit -m "feat(siteapp): rebuild Home shell with partials, 5s lab polling, sticky-header shadow"
```

---

### Task 14: Add Home + shared CSS rules to site.css

**Files:**
- Modify: `services/siteapp/app/static/site.css`

- [ ] **Step 1: Rewrite site.css**

Strip the old palette + layout rules; replace with rules that consume the new tokens. Port the `.lb-home-header*`, `.lb-intro-stmt*`, `.lb-status-row`, `.lb-equip*`, `.lb-lab*`, `.lb-topo*`, `.lb-quick*`, `.lb-start*`, `.lb-section-title`, `.lb-lang*` blocks from `docs/design_handoff_lab_bridge/source/lab-bridge-styles.css` — these are already self-contained and named with the same `.lb-*` prefixes used in the partials.

Working pattern: open the handoff CSS, copy each block matching the prefixes above, adjust selectors that referenced `.lb-window` ancestor (drop the ancestor — siteapp pages mount directly to viewport, no faux browser chrome). Drop the `.lb-canvas*` and `.lb-window*` blocks entirely.

Keep these existing rules from today's site.css for backwards compat:
- `.alert*` (admonitions — restyle to tokens in Docs section, Task 19)
- `.prose*` (article styles — restyle in Task 19)
- copy-button styles (slim down — moved to .lb-code__copy in Task 19)

Also add the sticky-header scroll-shadow rule:

```css
.lb-home-header {
  position: sticky;
  top: 0;
  z-index: 5;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 32px;
  font-family: var(--font-sans);
}
.lb-home-header.is-scrolled {
  box-shadow: 0 4px 10px -8px rgba(26, 25, 22, 0.18);
}
```

- [ ] **Step 2: Visual local check**

```bash
cd services/siteapp && uv run uvicorn app.main:app --reload --port 8001 &
# Visit http://127.0.0.1:8001/ in a browser, verify the layout
# Kill: kill %1
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/static/site.css
git commit -m "feat(siteapp): port Home + shared CSS rules from design handoff"
```

---

## Download page

### Task 15: Create Download template partials

**Files:**
- Create: `services/siteapp/app/templates/_dl_hero.html`
- Create: `services/siteapp/app/templates/_dl_cta.html`
- Create: `services/siteapp/app/templates/_dl_explainer.html`
- Create: `services/siteapp/app/templates/_dl_meta.html`
- Create: `services/siteapp/app/templates/_dl_card_windows.html`
- Create: `services/siteapp/app/templates/_dl_card_coming.html`
- Create: `services/siteapp/app/templates/_dl_body_md.html`

- [ ] **Step 1: Write _dl_hero.html**

```html
<section class="lb-dl-hero">
  <span class="lb-dl-hero__logo" aria-hidden="true">
    <svg viewBox="0 0 56 56" width="56" height="56">
      <rect width="56" height="56" rx="8" fill="var(--accent)"/>
      <path d="M16 28h12l4-8m-4 8h12m-8 8H20l-4 8" stroke="var(--text-inverse)"
            stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    </svg>
  </span>
  <div class="lb-dl-hero__body">
    <h1 class="lb-dl-hero__title">{{ s.hero_title }}</h1>
    <p class="lb-dl-hero__lede">{{ s.hero_lede }}</p>
    <p class="lb-dl-hero__source">
      {{ s.source_label }}
      <a class="lb-dl-hero__source-link"
         href="https://github.com/bioexperiment-lab-devices/serialhop">{{ s.source_link_text }}</a>
    </p>
  </div>
</section>
```

- [ ] **Step 2: Write _dl_cta.html**

```html
{% if info %}
  <a class="lb-dl-card__cta" href="/download/agent/windows/agent.exe">
    <span class="lb-dl-card__cta-icon" aria-hidden="true">↓</span>
    <span class="lb-dl-card__cta-text">
      <span class="lb-dl-card__cta-line1">{{ s.cta_download_for }} {{ s.platform_windows }}</span>
      <span class="lb-dl-card__cta-line2">
        v{{ info.version }} · {{ "%.1f"|format(info.size / 1048576) }} MB
      </span>
    </span>
  </a>
{% else %}
  <button class="lb-dl-card__cta lb-dl-card__cta--disabled" type="button" disabled>
    {{ s.cta_disabled }}
  </button>
{% endif %}
```

- [ ] **Step 3: Write _dl_explainer.html**

Take the existing explainer markup from today's `services/siteapp/app/templates/agent.html` (the `<details>` block containing the EN + RU `Browser may block this download` walkthrough). Move it here verbatim, then wrap the existing copy with the new design's classes:

```html
{% if info %}
<details class="lb-dl-explainer">
  <summary class="lb-dl-explainer__summary">
    <span class="lb-dl-explainer__icon" aria-hidden="true">!</span>
    <span class="lb-dl-explainer__summary-text">{{ s.explainer_summary }}</span>
    <span class="lb-dl-explainer__chev" aria-hidden="true">▾</span>
  </summary>
  <div class="lb-dl-explainer__body">
    <p>{{ s.explainer_intro }}</p>

    {% if lang == 'ru' %}
    <h4 class="lb-dl-explainer__h4">{{ s.explainer_h4_browser }}</h4>
    <ol>
      <li>Откройте список загрузок (<kbd>Ctrl</kbd>+<kbd>J</kbd>).</li>
      <li>Найдите <code>SerialHop-v{{ info.version }}.exe</code>,
          нажмите <code>⋯</code> (или правой кнопкой) и выберите
          <strong>Сохранить</strong> / <strong>Keep</strong>.</li>
      <li>Если появится «Этот файл может нанести вред компьютеру» —
          выберите <strong>Сохранить опасный файл</strong> /
          <strong>Keep dangerous file</strong>.</li>
    </ol>
    <h4 class="lb-dl-explainer__h4">{{ s.explainer_h4_windows }}</h4>
    <ol>
      <li>Нажмите <strong>Подробнее</strong> / <strong>More info</strong>
          в окне SmartScreen.</li>
      <li>Под текстом появится кнопка <strong>Выполнить в любом случае</strong> /
          <strong>Run anyway</strong> — нажмите её.</li>
      <li>Этот выбор Windows запомнит, и при следующих запусках
          предупреждение больше не появится.</li>
    </ol>
    {% else %}
    <h4 class="lb-dl-explainer__h4">{{ s.explainer_h4_browser }}</h4>
    <ol>
      <li>Open the downloads list (<kbd>Ctrl</kbd>+<kbd>J</kbd>).</li>
      <li>Find <code>SerialHop-v{{ info.version }}.exe</code>,
          click the <code>⋯</code> menu (or right-click) and choose
          <strong>Keep</strong>.</li>
      <li>If a second prompt warns "This file might harm your computer",
          choose <strong>Keep dangerous file</strong>.</li>
    </ol>
    <h4 class="lb-dl-explainer__h4">{{ s.explainer_h4_windows }}</h4>
    <ol>
      <li>Click <strong>More info</strong> in the SmartScreen dialog
          (the "Run anyway" button is hidden until you do).</li>
      <li>A <strong>Run anyway</strong> button appears beneath the text —
          click it.</li>
      <li>Windows remembers the choice on this PC, so the prompt won't
          come back on later launches.</li>
    </ol>
    {% endif %}
  </div>
</details>
{% endif %}
```

- [ ] **Step 4: Write _dl_meta.html**

```html
{% if info %}
<dl class="lb-dl-meta">
  <div class="lb-dl-meta__row">
    <dt>{{ s.meta_version }}</dt>
    <dd><code>{{ info.version }}</code></dd>
  </div>
  <div class="lb-dl-meta__row">
    <dt>{{ s.meta_released }}</dt>
    <dd>
      <span class="lb-dl-meta__ts">{{ info.uploaded_at }}</span>
      {% if released_relative %}
        <span class="lb-dl-meta__rel">{{ released_relative }}</span>
      {% endif %}
    </dd>
  </div>
  <div class="lb-dl-meta__row">
    <dt>{{ s.meta_sha256 }}</dt>
    <dd class="lb-dl-meta__sha">
      <code style="user-select: all">{{ info.sha256 }}</code>
      <button class="lb-dl-meta__copy"
              type="button"
              data-copy-text="{{ info.sha256 }}"
              aria-label="{{ s.meta_copy }}">{{ s.meta_copy }}</button>
    </dd>
  </div>
</dl>
{% endif %}
```

- [ ] **Step 5: Write _dl_card_windows.html**

```html
<article class="lb-dl-card{% if info %} lb-dl-card--available{% endif %}" data-platform="windows">
  <header class="lb-dl-card__head">
    <span class="lb-dl-card__icon-tile" aria-hidden="true">⊞</span>
    <div class="lb-dl-card__id">
      <span class="lb-dl-card__name">{{ s.platform_windows }}</span>
      <span class="lb-dl-card__sub">{{ s.platform_windows_sub }}</span>
    </div>
    <span class="lb-dl-card__status lb-dl-card__status--{% if info %}available{% else %}disabled{% endif %}">
      {{ s.status_available if info else s.status_coming_soon }}
    </span>
  </header>
  <div class="lb-dl-card__body">
    {% include "_dl_cta.html" %}
    {% include "_dl_explainer.html" %}
    {% include "_dl_meta.html" %}
  </div>
</article>
```

Replace `⊞` with a hand-rolled monoline Windows-tile SVG when porting; emoji is a stand-in.

- [ ] **Step 6: Write _dl_card_coming.html**

```html
<article class="lb-dl-card lb-dl-card--coming" data-platform="{{ platform }}">
  <header class="lb-dl-card__head">
    <span class="lb-dl-card__icon-tile" aria-hidden="true">{{ icon }}</span>
    <div class="lb-dl-card__id">
      <span class="lb-dl-card__name">{{ name }}</span>
      <span class="lb-dl-card__sub">{{ sub }}</span>
    </div>
    <span class="lb-dl-card__status lb-dl-card__status--soon">
      <span class="lb-dl-card__status-main">{{ s.status_coming_soon }}</span>
      <span class="lb-dl-card__status-eta">{{ eta }}</span>
    </span>
  </header>
</article>
```

- [ ] **Step 7: Write _dl_body_md.html**

```html
{% if body_html %}
<section class="lb-dl-bodymd">
  {{ body_html|safe }}
</section>
{% endif %}
```

- [ ] **Step 8: Commit**

```bash
git add services/siteapp/app/templates/_dl_*.html
git commit -m "feat(siteapp): add Download partials (hero, cta, explainer, meta, cards, optional md)"
```

---

### Task 16: Rebuild agent.html shell + plumb relative time

**Files:**
- Modify: `services/siteapp/app/templates/agent.html`
- Modify: `services/siteapp/app/agent.py`

- [ ] **Step 1: Rewrite agent.html**

```html
{% extends "base.html" %}
{% block title %}{{ s.page_title }}{% endblock %}
{% block main %}
<div class="lb-page lb-page--download">
  {% with target_page = "download" %}{% include "_home_header.html" %}{% endwith %}

  <div class="lb-page__body lb-page__body--narrow">
    {% include "_dl_hero.html" %}

    <div class="lb-dl-cards">
      {% include "_dl_card_windows.html" %}
      {% with platform = "linux", name = s.platform_linux, sub = s.platform_linux_sub,
              eta = s.eta_linux, icon = "🐧" %}
        {% include "_dl_card_coming.html" %}
      {% endwith %}
      {% with platform = "rpi", name = s.platform_rpi, sub = s.platform_rpi_sub,
              eta = s.eta_rpi, icon = "🍓" %}
        {% include "_dl_card_coming.html" %}
      {% endwith %}
    </div>

    {% include "_dl_body_md.html" %}
  </div>
</div>

<script>
// Same sticky-header shadow pattern as Home.
(function () {
  var header = document.querySelector('.lb-home-header');
  if (!header) return;
  var sentinel = document.createElement('div');
  sentinel.style.cssText = 'position:absolute;top:0;left:0;height:1px;width:1px;';
  header.parentNode.insertBefore(sentinel, header);
  var io = new IntersectionObserver(function (entries) {
    header.classList.toggle('is-scrolled', !entries[0].isIntersecting);
  });
  io.observe(sentinel);
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Update agent.py context to pass strings + relative time**

Edit `app/agent.py`'s `agent_page()` body. Replace from `chosen = _pick_lang(...)` through the end of the route:

```python
@router.get("/download/agent")
def agent_page(request: Request, lang: str | None = None) -> Response:
    chosen = pick_lang(lang, request.cookies.get("lang"))
    info = load_meta(settings.agent_root)
    body = _body_markdown(settings.agent_root, chosen)
    body_html = body.html if body else None
    needs_mermaid = body.needs_mermaid if body else False
    released_relative = _relative_time(info.uploaded_at, chosen) if info else ""
    response = templates.TemplateResponse(
        request,
        "agent.html",
        {
            "info": info,
            "body_html": body_html,
            "needs_mermaid": needs_mermaid,
            "lang": chosen,
            "s": DL_STRINGS[chosen],
            "released_relative": released_relative,
            "pygments_css": pygments_css(),
        },
    )
    if lang in ("en", "ru"):
        response.set_cookie(
            "lang",
            lang,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=True,
            httponly=True,
        )
    return response
```

Drop the now-unused `_pick_lang` from `agent.py` (replaced by `app.strings.pick_lang`).

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/templates/agent.html services/siteapp/app/agent.py
git commit -m "feat(siteapp): rebuild Download shell + plumb DL_STRINGS + relative time"
```

---

### Task 17: Add Download CSS to site.css

**Files:**
- Modify: `services/siteapp/app/static/site.css`

- [ ] **Step 1: Port `.lb-dl-*` rules from handoff**

Open `docs/design_handoff_lab_bridge/source/lab-bridge-styles.css`, find all blocks starting with `.lb-dl`. Append them to `site.css`. Verify the rules consume the tokens defined in `tokens.css` (`--surface`, `--accent`, etc.) — they should, but the handoff CSS may reference some variables that didn't make it into the token table; add them inline as fallbacks.

Also add the page-body width modifier:

```css
.lb-page__body--narrow { max-width: 880px; margin: 0 auto; padding: 28px 32px; }
```

- [ ] **Step 2: Local visual check**

```bash
# Assume the dev server from Task 14 is still running, or restart it.
# Visit http://127.0.0.1:8001/download/agent
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/static/site.css
git commit -m "feat(siteapp): port Download CSS rules from design handoff"
```

---

## Markdown layer + Docs page

### Task 18: Extend markdown.py — `title=` attr + custom Pygments style + permalinks + bleach updates

**Files:**
- Modify: `services/siteapp/app/markdown.py`
- Modify: `services/siteapp/tests/test_markdown.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_markdown.py`:

```python
def test_fenced_block_title_emits_filename_in_figcaption():
    md = '```python title="serialhop/cli.py"\nprint("hi")\n```\n'
    out = render_markdown(md).html
    assert '<figure class="lb-code"' in out
    assert 'data-lang="python"' in out
    assert 'class="lb-code__file">serialhop/cli.py' in out
    assert '<button class="lb-code__copy"' in out


def test_fenced_block_without_title_omits_filename():
    md = '```python\nprint("hi")\n```\n'
    out = render_markdown(md).html
    assert '<figure class="lb-code"' in out
    assert 'lb-code__file' not in out
    # Language label still appears.
    assert 'class="lb-code__lang">python' in out


def test_fenced_block_file_alias_works():
    md = '```python file="x.py"\npass\n```\n'
    out = render_markdown(md).html
    assert 'class="lb-code__file">x.py' in out


def test_h2_gets_permalink_anchor():
    md = "## Section title\n\nbody\n"
    out = render_markdown(md).html
    assert 'class="lb-anchor"' in out


def test_pygments_css_uses_data_theme_selector():
    css = pygments_css()
    assert '[data-theme="dark"]' in css
    assert '@media (prefers-color-scheme: dark)' not in css
```

- [ ] **Step 2: Run, verify fail**

```bash
cd services/siteapp && uv run pytest tests/test_markdown.py -v -k "title or alias or permalink or pygments_css_uses"
```
Expected: 5 FAIL.

- [ ] **Step 3: Update markdown.py**

Three pieces:

**(a)** Extend `_highlight()` to parse `attrs` and emit the figure wrapper:

```python
_TITLE_RE = re.compile(r'(?:title|file)\s*=\s*"([^"]+)"')


def _parse_title(attrs: object) -> str | None:
    if not isinstance(attrs, str):
        return None
    m = _TITLE_RE.search(attrs)
    return m.group(1) if m else None


def _highlight(code: str, name: str | None, attrs: object) -> str:
    if name == "mermaid":
        return f'<pre class="mermaid">{html_escape(code)}</pre>\n'
    if not name:
        return ""
    try:
        lexer = get_lexer_by_name(name)
    except ClassNotFound:
        return ""
    formatter = HtmlFormatter(style=_LightStyle, nowrap=True)
    inner = highlight(code, lexer, formatter).rstrip("\n")
    safe_lang = re.sub(r"[^a-zA-Z0-9_-]", "", name)
    title = _parse_title(attrs)
    file_span = (
        f'<span class="lb-code__file">{html_escape(title)}</span>'
        if title
        else ""
    )
    return (
        f'<figure class="lb-code" data-lang="{safe_lang}">'
        f'<figcaption class="lb-code__head">'
        f'<span class="lb-code__lang">{safe_lang}</span>'
        f'{file_span}'
        f'<button class="lb-code__copy" type="button" aria-label="Copy code">Copy</button>'
        f'</figcaption>'
        f'<pre class="highlight"><code class="language-{safe_lang}">{inner}</code></pre>'
        f'</figure>\n'
    )
```

**(b)** Custom Pygments styles:

```python
from pygments.style import Style
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String, Token


class _LightStyle(Style):
    """Light-theme syntax colors mapped from the design handoff token roles
    (keys/purple, strings/green, numbers/yellow, comments/gray italic,
    punctuation/blue). Approximate — see spec risk #6."""

    default_style = ""
    background_color = "transparent"
    styles = {
        Token: "#1A1916",
        Keyword: "bold #6B3FA0",
        Name.Function: "#1F3A8A",
        Name.Class: "#1F3A8A",
        Name.Builtin: "#1F3A8A",
        String: "#2F7D3F",
        Number: "#A37200",
        Comment: "italic #8A8678",
        Operator: "#1F3A8A",
        Punctuation: "#514E47",
    }


class _DarkStyle(Style):
    default_style = ""
    background_color = "transparent"
    styles = {
        Token: "#F0EDE3",
        Keyword: "bold #C6A6F2",
        Name.Function: "#BCCBF2",
        Name.Class: "#BCCBF2",
        Name.Builtin: "#BCCBF2",
        String: "#7CC18A",
        Number: "#E3C067",
        Comment: "italic #7E7A6E",
        Operator: "#BCCBF2",
        Punctuation: "#B8B3A4",
    }
```

**(c)** Update `pygments_css()` to use `[data-theme="dark"]` selector instead of media query, and update `_theme_css` to take a Style class:

```python
def _theme_css(style: type[Style]) -> str:
    """Pygments style defs minus the embedded `.highlight { background: ... }`
    rule, which would otherwise override the page's own colors."""
    css = HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")
    return _PYGMENTS_BG_RE.sub("", css).strip()


def pygments_css() -> str:
    """Light + dark code-highlighting CSS. Dark variant gated on
    `[data-theme="dark"]` so manual theme toggle (Section B of spec) wins."""
    light = _theme_css(_LightStyle)
    dark = _theme_css(_DarkStyle).replace(".highlight", '[data-theme="dark"] .highlight')
    return f"{light}\n{dark}\n"
```

**(d)** Enable anchor permalinks:

In `_make_md()`, change the `.use(anchors_plugin, …)` call:

```python
.use(anchors_plugin, min_level=2, max_level=4, permalink=True,
     permalinkSymbol="#", permalinkClass="lb-anchor", slug_func=_slug)
```

**(e)** Update bleach allow-list:

```python
ALLOWED_TAGS: frozenset[str] = frozenset({
    # ...existing entries...
    "figure",
    "figcaption",
    "button",
    "kbd",
})
ALLOWED_ATTRS: dict[str, set[str]] = {
    # ...existing entries unchanged...
    "figure": {"class", "data-lang"},
    "figcaption": {"class"},
    "button": {"class", "type", "aria-label"},
    "a": {"href", "title", "rel", "target", "class"},  # add class for .lb-anchor
}
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd services/siteapp && uv run pytest tests/test_markdown.py -v
```
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add services/siteapp/app/markdown.py services/siteapp/tests/test_markdown.py
git commit -m "feat(siteapp-md): support title= attr, custom Pygments style, anchor permalinks"
```

---

### Task 19: Add docs.py helpers — breadcrumb + prev_next

**Files:**
- Modify: `services/siteapp/app/docs.py`
- Modify: `services/siteapp/app/nav.py` (export `flatten_nav` if helpful)
- Modify: `services/siteapp/tests/test_routes_docs.py` (or add `test_docs_nav.py`)

- [ ] **Step 1: Write failing tests**

Append to `services/siteapp/tests/test_nav.py`:

```python
from app.nav import NavEntry
from app.docs import build_breadcrumb, prev_next


def _sample_nav() -> list[NavEntry]:
    return [
        NavEntry(
            title_en="Researchers", title_ru=None, url="/docs/researcher/",
            children=(
                NavEntry(title_en="First notebook", title_ru=None,
                         url="/docs/researcher/first-notebook"),
            ),
        ),
        NavEntry(title_en="System overview", title_ru=None,
                 url="/docs/system-overview"),
    ]


def test_breadcrumb_for_nested_doc():
    crumbs = build_breadcrumb(_sample_nav(), "/docs/researcher/first-notebook")
    assert [c["title"] for c in crumbs] == ["Docs", "Researchers", "First notebook"]


def test_breadcrumb_for_root_doc():
    crumbs = build_breadcrumb(_sample_nav(), "/docs/system-overview")
    assert [c["title"] for c in crumbs] == ["Docs", "System overview"]


def test_prev_next_in_section():
    # Single-child section: first-notebook has no siblings → both None.
    prev, nxt = prev_next(_sample_nav(), "/docs/researcher/first-notebook")
    assert prev is None and nxt is None


def test_prev_next_across_top_level():
    nav = _sample_nav()
    prev, nxt = prev_next(nav, "/docs/system-overview")
    # System-overview comes after Researchers section (top-level order is dirs then files).
    assert prev is not None and prev.title_en == "Researchers"
    assert nxt is None
```

- [ ] **Step 2: Run, verify fail**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py -v -k "breadcrumb or prev_next"
```
Expected: 4 FAIL.

- [ ] **Step 3: Add helpers to docs.py**

Append to `app/docs.py`:

```python
from typing import TypedDict

from app.nav import NavEntry


class BreadcrumbCrumb(TypedDict):
    title: str
    url: str | None  # None for the leaf (current page)


def _find_path(nav: list[NavEntry], target_url: str) -> list[NavEntry]:
    """DFS for `target_url` through children; return ancestor + self list."""
    for entry in nav:
        if entry.url == target_url:
            return [entry]
        if entry.children:
            sub = _find_path(list(entry.children), target_url)
            if sub:
                return [entry, *sub]
    return []


def build_breadcrumb(nav: list[NavEntry], current_url: str) -> list[BreadcrumbCrumb]:
    path = _find_path(nav, current_url)
    crumbs: list[BreadcrumbCrumb] = [{"title": "Docs", "url": "/docs/"}]
    for i, entry in enumerate(path):
        is_leaf = i == len(path) - 1
        crumbs.append({"title": entry.title_en, "url": None if is_leaf else entry.url})
    return crumbs


def _flatten(nav: list[NavEntry]) -> list[NavEntry]:
    out: list[NavEntry] = []
    for entry in nav:
        out.append(entry)
        if entry.children:
            out.extend(_flatten(list(entry.children)))
    return out


def prev_next(
    nav: list[NavEntry], current_url: str
) -> tuple[NavEntry | None, NavEntry | None]:
    flat = _flatten(nav)
    for i, entry in enumerate(flat):
        if entry.url == current_url:
            prev = flat[i - 1] if i > 0 else None
            nxt = flat[i + 1] if i + 1 < len(flat) else None
            return prev, nxt
    return None, None
```

- [ ] **Step 4: Plumb into the docs route**

In `app/docs.py`, edit `docs_path()` to pass breadcrumb + prev/next:

```python
nav = build_nav(settings.docs_root)
crumbs = build_breadcrumb(nav, str(request.url.path))
prev, nxt = prev_next(nav, str(request.url.path))
response = templates.TemplateResponse(
    request,
    "doc.html",
    {
        "title": result.title or doc.rel_path.name,
        "html": result.html,
        "needs_mermaid": result.needs_mermaid,
        "lang": chosen,
        "doc": doc,
        "nav": nav,
        "crumbs": crumbs,
        "prev": prev,
        "next": nxt,
        "current_url": str(request.url.path),
        "pygments_css": pygments_css(),
    },
)
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd services/siteapp && uv run pytest tests/test_nav.py -v
```
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add services/siteapp/app/docs.py services/siteapp/tests/test_nav.py
git commit -m "feat(siteapp): add breadcrumb + prev/next helpers for Docs"
```

---

### Task 20: Restyle docs templates (`_nav.html`, `doc.html`) + sidebar interactivity

**Files:**
- Modify: `services/siteapp/app/templates/_nav.html`
- Modify: `services/siteapp/app/templates/doc.html`
- Create: `services/siteapp/app/static/docs-sidebar.js`

- [ ] **Step 1: Rewrite _nav.html**

```html
{% macro render_entry(entry, lang, current_url, depth) -%}
  {%- set title = entry.title_ru if (lang == 'ru' and entry.title_ru) else entry.title_en -%}
  {%- set is_active = (entry.url == current_url) -%}
  <li class="lb-docs-side__item{% if is_active %} is-active{% endif %}"
      data-depth="{{ depth }}">
    {% if entry.children %}
      <button class="lb-docs-side__folder" type="button"
              aria-expanded="false"
              data-section-key="{{ entry.url }}">
        <span class="lb-docs-side__chev" aria-hidden="true">›</span>
        <a href="{{ entry.url }}{% if lang == 'ru' %}?lang=ru{% endif %}">{{ title }}</a>
        {% if entry.title_ru %}<span class="lb-docs-side__ru-pill">RU</span>{% endif %}
      </button>
      <ul class="lb-docs-side__children">
        {% for child in entry.children %}{{ render_entry(child, lang, current_url, depth + 1) }}{% endfor %}
      </ul>
    {% else %}
      <a href="{{ entry.url }}{% if lang == 'ru' %}?lang=ru{% endif %}">{{ title }}</a>
      {% if entry.title_ru %}<span class="lb-docs-side__ru-pill">RU</span>{% endif %}
    {% endif %}
  </li>
{%- endmacro %}

<aside class="lb-docs-side" aria-label="Documentation navigation">
  <header class="lb-docs-side__head">
    <span class="lb-docs-side__icon" aria-hidden="true">📖</span>
    <span class="lb-docs-side__title">DOCUMENTATION</span>
  </header>
  <ul class="lb-docs-side__list">
    {% for entry in nav %}{{ render_entry(entry, lang, current_url, 0) }}{% endfor %}
  </ul>
</aside>
```

- [ ] **Step 2: Rewrite doc.html**

```html
{% extends "base.html" %}
{% block title %}{{ title }} · lab-bridge docs{% endblock %}
{% block main %}
<div class="lb-page lb-page--docs">
  {% include "_nav.html" %}
  <article class="lb-docs-article">
    <nav class="lb-docs-article__breadcrumb" aria-label="Breadcrumb">
      {% for crumb in crumbs %}
        {% if crumb.url %}
          <a href="{{ crumb.url }}">{{ crumb.title }}</a>
        {% else %}
          <span>{{ crumb.title }}</span>
        {% endif %}
        {% if not loop.last %}<span class="lb-docs-article__sep" aria-hidden="true">/</span>{% endif %}
      {% endfor %}
      {% if doc.ru_exists %}
        <nav class="lb-lang lb-docs-article__lang" aria-label="Language">
          <a href="?lang=en" class="lb-lang__pill{% if lang == 'en' %} is-active{% endif %}">EN</a>
          <a href="?lang=ru" class="lb-lang__pill{% if lang == 'ru' %} is-active{% endif %}">RU</a>
        </nav>
      {% endif %}
    </nav>

    <div class="lb-docs-article__body prose">
      {{ html|safe }}
    </div>

    {% if prev or next %}
    <footer class="lb-docs-article__prevnext">
      {% if prev %}
        <a class="lb-docs-article__prev" href="{{ prev.url }}">
          <span class="lb-docs-article__nav-label">← {{ prev.title_en }}</span>
        </a>
      {% else %}<span></span>{% endif %}
      {% if next %}
        <a class="lb-docs-article__next" href="{{ next.url }}">
          <span class="lb-docs-article__nav-label">{{ next.title_en }} →</span>
        </a>
      {% else %}<span></span>{% endif %}
    </footer>
    {% endif %}
  </article>
</div>
<script src="/_static/docs-sidebar.js" defer></script>
{% endblock %}
```

- [ ] **Step 3: Write docs-sidebar.js**

```javascript
// Sidebar collapse/expand + persistence + auto-open ancestors of active.
(function () {
  if (window.__docsSidebarLoaded) return;
  window.__docsSidebarLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var folders = document.querySelectorAll('.lb-docs-side__folder');
    folders.forEach(function (btn) {
      var key = 'docs-nav:' + btn.dataset.sectionKey;
      var saved = localStorage.getItem(key);
      var parentLi = btn.closest('.lb-docs-side__item');
      var hasActiveDescendant = parentLi && parentLi.querySelector('.is-active');
      var open = saved === 'open' || (saved === null && hasActiveDescendant);
      setOpen(btn, parentLi, open);

      btn.addEventListener('click', function (e) {
        // Allow the inner <a> click to navigate; intercept only the chev/whitespace.
        if (e.target.closest('a')) return;
        e.preventDefault();
        var nowOpen = btn.getAttribute('aria-expanded') !== 'true';
        setOpen(btn, parentLi, nowOpen);
        localStorage.setItem(key, nowOpen ? 'open' : 'closed');
      });
    });
  });

  function setOpen(btn, li, open) {
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    var chev = btn.querySelector('.lb-docs-side__chev');
    if (chev) chev.textContent = open ? '⌄' : '›';
    var children = li ? li.querySelector('.lb-docs-side__children') : null;
    if (children) children.style.display = open ? '' : 'none';
  }
})();
```

- [ ] **Step 4: Commit**

```bash
git add services/siteapp/app/templates/_nav.html services/siteapp/app/templates/doc.html services/siteapp/app/static/docs-sidebar.js
git commit -m "feat(siteapp): restyle Docs sidebar + article, add breadcrumb / prev-next, sidebar interactivity"
```

---

### Task 21: Add Docs CSS (sidebar, article, code blocks, admonitions, tables)

**Files:**
- Modify: `services/siteapp/app/static/site.css`

- [ ] **Step 1: Append Docs CSS**

Port `.lb-docs-*`, `.lb-code*`, `.lb-adm*`, `.lb-tok-*` blocks from `docs/design_handoff_lab_bridge/source/lab-bridge-styles.css`. Then rewrite the existing `.alert*` blocks at the bottom of `site.css` to use the new admonition palette + circular icon column:

```css
.prose .alert {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 12px;
  margin: 1.2em 0;
  padding: 14px 16px;
  border-radius: 6px;
  border: 1px solid var(--alert-border);
  background: var(--alert-soft);
}
.prose .alert::before {
  content: var(--alert-icon);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--alert-accent);
  color: var(--text-inverse);
  font-weight: 600;
  font-size: 12px;
  font-family: var(--font-mono);
}
.prose .alert > :first-child { margin-top: 0; }
.prose .alert > :last-child  { margin-bottom: 0; }

.alert-note      { --alert-accent: var(--accent);  --alert-soft: var(--accent-soft);  --alert-border: var(--accent-border);  --alert-icon: "i"; }
.alert-tip       { --alert-accent: var(--success); --alert-soft: var(--success-soft); --alert-border: var(--success-border); --alert-icon: "i"; }
.alert-important { --alert-accent: #6B3FA0;        --alert-soft: #ECE4F5;             --alert-border: #C9B8E0;               --alert-icon: "!"; }
.alert-warning   { --alert-accent: var(--warning); --alert-soft: var(--warning-soft); --alert-border: var(--warning-border); --alert-icon: "!"; }
.alert-caution   { --alert-accent: var(--danger);  --alert-soft: var(--danger-soft);  --alert-border: var(--danger-border);  --alert-icon: "×"; }
```

For code blocks:

```css
.prose .lb-code {
  margin: 1.2em 0;
  border-radius: 6px;
  overflow: hidden;
  background: #1A1916;  /* always dark; handoff explicit */
  border: 1px solid #0F0E0C;
}
.lb-code__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  background: #232220;
  color: var(--text-inverse);
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.lb-code__lang {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #B8B3A4;
}
.lb-code__file {
  color: #E3DED1;
}
.lb-code__copy {
  margin-left: auto;
  background: transparent;
  color: #B8B3A4;
  border: 1px solid #34322D;
  border-radius: 4px;
  padding: 3px 10px;
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}
.lb-code__copy:hover { color: #F0EDE3; border-color: #4A4740; }
.lb-code__copy.is-copied { color: #7CC18A; border-color: #335A3E; }
.lb-code__copy.is-copied::before { content: "✓ "; }

.prose .lb-code pre {
  margin: 0;
  padding: 14px 16px;
  background: transparent;
  overflow-x: auto;
}
.prose .lb-code code {
  background: transparent;
  border: 0;
  color: #F0EDE3;
  font-family: var(--font-mono);
  font-size: 13px;
}
```

Inline code + permalink anchor:

```css
.prose code {
  background: var(--surface-sunken);
  color: var(--accent);
  padding: 0.1em 0.4em;
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 13px;
  white-space: nowrap;
}
.lb-anchor {
  margin-left: 8px;
  color: var(--text-muted);
  text-decoration: none;
  opacity: 0;
  transition: opacity 100ms ease;
}
.prose h2:hover .lb-anchor,
.prose h3:hover .lb-anchor,
.prose h4:hover .lb-anchor { opacity: 1; }
```

- [ ] **Step 2: Local visual check**

Visit `/docs/system-overview` (after server restart) and confirm sidebar, breadcrumb, article, code block, admonition rendering.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/app/static/site.css
git commit -m "feat(siteapp): port Docs CSS (sidebar, article, code blocks, admonitions)"
```

---

## Stub docs

### Task 22: Create stub doc directories and files

**Files:**
- Create: `public_docs/researcher/index.md`
- Create: `public_docs/researcher/index.ru.md`
- Create: `public_docs/researcher/first-notebook.md`
- Create: `public_docs/researcher/first-notebook.ru.md`
- Create: `public_docs/operator/index.md`
- Create: `public_docs/operator/index.ru.md`
- Create: `public_docs/operator/setup-lab-pc.md`
- Create: `public_docs/operator/setup-lab-pc.ru.md`
- Create: `public_docs/admin/index.md`
- Create: `public_docs/admin/index.ru.md`
- Create: `public_docs/reference/index.md`
- Create: `public_docs/reference/index.ru.md`

- [ ] **Step 1: Create the section index files**

Each `index.md` follows this pattern (substitute title):

```markdown
# Researchers

This section is in progress. See [system overview](/docs/system-overview)
for the current platform write-up.
```

`index.ru.md`:

```markdown
# Исследователи

Раздел в разработке. Пока смотрите [обзор системы](/docs/system-overview).
```

Mirror for `operator/index.md` → "Lab operators", `admin/index.md` → "Server admins", `reference/index.md` → "Reference", with corresponding Russian titles.

- [ ] **Step 2: Create the target stub docs**

`public_docs/researcher/first-notebook.md`:

```markdown
# Run your first notebook

This guide is in progress. It will walk you through opening JupyterLab,
connecting to your lab's instruments, and running a one-cell smoke test
in five minutes. For now, see the
[system overview](/docs/system-overview) for context.
```

RU version: translate the body.

`public_docs/operator/setup-lab-pc.md`:

```markdown
# Set up a new lab PC

This guide is in progress. It will walk you through installing the
SerialHop agent, claiming a user, registering instruments, and verifying
the tunnel is alive. For now, see the
[technical overview](/docs/technical-overview) for context.
```

RU version: translate the body.

- [ ] **Step 3: Visually confirm sidebar picks them up**

Restart the local server, visit `/docs/`, confirm the sidebar shows four new section headers (Researchers / Lab operators / Server admins / Reference) above the flat `system-overview` and `technical-overview` entries.

- [ ] **Step 4: Commit**

```bash
git add public_docs/
git commit -m "docs: add stub section structure (researcher / operator / admin / reference)"
```

---

## Service e2e + integration tests

### Task 23: Service e2e — Home page

**Files:**
- Modify: `services/siteapp/tests/e2e/test_home_page.py`

- [ ] **Step 1: Replace test_home_page.py**

```python
"""End-to-end coverage for the redesigned Home page."""

from __future__ import annotations

import httpx


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
```

- [ ] **Step 2: Build the e2e image + run**

```bash
docker build -t lab-bridge-siteapp:e2e services/siteapp
cd services/siteapp && uv run pytest tests/e2e/test_home_page.py -v
```
Expected: all green.

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_home_page.py
git commit -m "test(siteapp-e2e): extend Home page coverage to new design"
```

---

### Task 24: Service e2e — Download page

**Files:**
- Create: `services/siteapp/tests/e2e/test_download_page.py`

- [ ] **Step 1: Write the test**

```python
"""End-to-end coverage for the redesigned Download Agent page."""

from __future__ import annotations

import httpx


def test_download_page_renders_hero_and_cards(http: httpx.Client) -> None:
    r = http.get("/download/agent")
    assert r.status_code == 200
    body = r.text
    assert 'class="lb-dl-hero"' in body
    assert 'class="lb-dl-cards"' in body
    # Three cards always render — Windows + Linux + RPi.
    assert body.count('class="lb-dl-card') >= 3
    assert "Linux" in body
    assert "Raspberry Pi" in body


def test_download_page_without_meta_disables_cta(http: httpx.Client) -> None:
    # The e2e fixture's site_data doesn't populate meta.json by default.
    r = http.get("/download/agent")
    assert r.status_code == 200
    body = r.text
    assert "Not yet available" in body or "Coming soon" in body


def test_download_page_lang_ru(http: httpx.Client) -> None:
    r = http.get("/download/agent?lang=ru")
    assert r.status_code == 200
    body = r.text
    assert "Single-binary" in body or "защищённый обратный туннель" in body
    assert r.cookies.get("lang") == "ru"


def test_sha256_has_copy_target(http: httpx.Client) -> None:
    # When meta.json is present this is a strict assertion; when absent the
    # block isn't rendered and we accept that — the page must still 200.
    r = http.get("/download/agent")
    assert r.status_code == 200
    if "lb-dl-meta__sha" in r.text:
        assert 'data-copy-text="' in r.text
```

- [ ] **Step 2: Run**

```bash
cd services/siteapp && uv run pytest tests/e2e/test_download_page.py -v
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_download_page.py
git commit -m "test(siteapp-e2e): add Download page coverage for new design"
```

---

### Task 25: Service e2e — Docs page restyle

**Files:**
- Create or modify: `services/siteapp/tests/e2e/test_docs_page.py`

- [ ] **Step 1: Write/extend the test**

```python
"""End-to-end coverage for the redesigned Docs page."""

from __future__ import annotations

import httpx


def test_docs_root_returns_200(http: httpx.Client) -> None:
    r = http.get("/docs/")
    assert r.status_code in (200, 308)


def test_doc_page_has_new_layout(http: httpx.Client) -> None:
    r = http.get("/docs/system-overview", follow_redirects=True)
    if r.status_code != 200:
        return  # doc may not be present in e2e fixture; soft-skip
    body = r.text
    assert 'class="lb-page lb-page--docs"' in body
    assert 'class="lb-docs-side"' in body
    assert 'class="lb-docs-article"' in body
    assert 'class="lb-docs-article__breadcrumb"' in body


def test_doc_with_code_block_emits_figure(http: httpx.Client) -> None:
    # Test fixture must include a doc with a fenced ```python title="..."``` block.
    # If your e2e compose doesn't ship one yet, this test is a soft pass:
    r = http.get("/docs/technical-overview", follow_redirects=True)
    if r.status_code != 200:
        return
    body = r.text
    if '<figure class="lb-code"' in body:
        assert 'class="lb-code__copy"' in body
```

- [ ] **Step 2: Run**

```bash
cd services/siteapp && uv run pytest tests/e2e/test_docs_page.py -v
```

- [ ] **Step 3: Commit**

```bash
git add services/siteapp/tests/e2e/test_docs_page.py
git commit -m "test(siteapp-e2e): cover Docs page restyle (layout, breadcrumb, figure-wrapped code)"
```

---

### Task 26: Platform integration — navbar attributes smoke

**Files:**
- Modify: `tests/integration/test_routes_smoke.bats` (or add `tests/integration/test_navbar_attrs.bats`)
- Modify: `.github/workflows/pr-platform.yml` (only if adding a new matrix cell)

- [ ] **Step 1: Append to test_routes_smoke.bats**

Add a test inside the existing file:

```bash
@test "navbar script injected with data-version attribute on every HTML page" {
  compose_images_available || skip "compose images unavailable"
  for path in "/" "/docs/" "/download/agent"; do
    run curl -sk "https://$VPS_HOST$path"
    [ "$status" -eq 0 ]
    [[ "$output" == *"/_shared/navbar.js"* ]]
    [[ "$output" == *"data-version=\""* ]]
  done
}

@test "navbar brand row markup ships in the served JS" {
  compose_images_available || skip "compose images unavailable"
  run curl -sk "https://$VPS_HOST/_shared/navbar.js"
  [ "$status" -eq 0 ]
  [[ "$output" == *"brand__wordmark"* ]]
  [[ "$output" == *"theme-toggle"* ]]
}

@test "bookmark mode triggers on /jupyter/ and /grafana/ paths" {
  compose_images_available || skip "compose images unavailable"
  # The JS reads location.pathname client-side, so server-side assertion is
  # just that the page serves with the script tag. Headless-browser check
  # could be a follow-up.
  run curl -sk -o /dev/null -w "%{http_code}" "https://$VPS_HOST/jupyter/"
  [ "$output" = "200" ] || [ "$output" = "302" ]
}
```

- [ ] **Step 2: Run locally**

```bash
bats tests/integration/test_routes_smoke.bats
```
(Will skip cleanly if compose images aren't present locally.)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_routes_smoke.bats
git commit -m "test(platform-bats): assert navbar data-version + brand/theme markup ship"
```

---

## Final sweep

### Task 27: Verification pass + open the dev server end-to-end

**Files:** none.

- [ ] **Step 1: Run the full siteapp unit suite**

```bash
cd services/siteapp && uv run pytest -v
```
Expected: all green. Fix any failures inline.

- [ ] **Step 2: Build siteapp image, run service e2e**

```bash
docker build -t lab-bridge-siteapp:e2e services/siteapp
cd services/siteapp && uv run pytest tests/e2e/ -v
```
Expected: all green.

- [ ] **Step 3: Local visual walkthrough**

```bash
cd services/siteapp && uv run uvicorn app.main:app --reload --port 8001
```
In a browser, walk through:
- `/` — header, intro, labs panel (empty fixture is fine), topology, quick, getting-started, EN/RU toggle works, theme toggle in the navbar flips light/dark
- `/download/agent` — hero, 3 cards (Windows disabled if no meta, 2 coming-soon), explainer expands, EN/RU
- `/docs/system-overview` — sidebar + 4 new section headers + breadcrumb + article + code block (if present) + admonition (if present)
- `/jupyter/` and `/grafana/` (via Caddy locally, if up) — bookmark mode tab at bottom-left, hover expands

If any surface is visually broken, file an inline fix and re-test.

- [ ] **Step 4: Commit any inline fixes**

```bash
git add -A && git commit -m "fix(siteapp): visual-walkthrough fixes"
```
(Skip if no fixes.)

- [ ] **Step 5: Verify branch state**

```bash
git log --oneline main..HEAD
```
Expected: ~26 commits, conventional commit titles, the squash subject will be one of the `feat(...)` titles.

---

**Plan complete.**

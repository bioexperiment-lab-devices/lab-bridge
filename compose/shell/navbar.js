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

  // Icons — monoline SVGs at 18×18 viewBox, stroke-width 1.5, currentColor.
  // These are functional approximations of the handoff icons. For pixel-perfect
  // fidelity, copy the exact path data from
  // docs/design_handoff_lab_bridge/source/lab-bridge-navbar.jsx's Icons object
  // into the ICON(...) calls below.
  const ICON = (paths) =>
    `<svg viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor"
          stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true">${paths}</svg>`;
  // Path data ported from docs/design_handoff_lab_bridge/source/lab-bridge-navbar.jsx Icons.
  const ICONS = {
    home:    ICON(`<path d="M2.5 8L9 3l6.5 5"/><path d="M4 8v6.5h4v-4h2v4h4V8"/>`),
    docs:    ICON(`<path d="M3.5 3h7.5l3 3v8.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-11A.5.5 0 0 1 3.5 3z"/>
                    <path d="M11 3v3.5h3"/>
                    <path d="M6 9h6M6 11.5h6M6 13.5h4"/>`),
    agent:   ICON(`<path d="M9 2.5v8.5"/>
                    <path d="M5.5 8L9 11.5 12.5 8"/>
                    <path d="M3 12.5v2A.5.5 0 0 0 3.5 15h11a.5.5 0 0 0 .5-.5v-2"/>`),
    jupyter: `<svg viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor"
                stroke-width="1.4" stroke-linecap="round" aria-hidden="true">
                <ellipse cx="9" cy="9" rx="6.5" ry="2.6"/>
                <ellipse cx="9" cy="9" rx="6.5" ry="2.6" transform="rotate(60 9 9)"/>
                <ellipse cx="9" cy="9" rx="6.5" ry="2.6" transform="rotate(120 9 9)"/>
                <circle cx="9" cy="9" r="1.5" fill="currentColor" stroke="none"/>
              </svg>`,
    grafana: ICON(`<path d="M2.5 14.5h13"/>
                    <rect x="3.5"  y="9"    width="2"   height="4.5" rx="0.4"/>
                    <rect x="7"    y="6"    width="2"   height="7.5" rx="0.4"/>
                    <rect x="10.5" y="10.5" width="2"   height="3"   rx="0.4"/>
                    <rect x="14"   y="7.5"  width="1.5" height="6"   rx="0.4"/>
                    <path d="M4 5.5l3.5-2 3.5 3 4-2.5"/>`),
    flasher: ICON(`<path d="M9.5 2L4 10h4l-1 6 5.5-8H8.5l1-6z"/>`),
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
        <span class="brand__text">
          <span class="brand__wordmark">lab-bridge</span>
          ${PLATFORM_VERSION ? `<span class="brand__version">v${PLATFORM_VERSION}</span>` : ''}
        </span>
      </div>`;

    const themeBtn = mode === 'persistent' ? `
      <button class="theme-toggle" type="button"
              aria-label="Switch to ${theme === 'dark' ? 'light' : 'dark'} theme"
              title="Lab Bridge theme only">
        <span class="theme-toggle__icon">${theme === 'dark' ? ICONS.sun : ICONS.moon}</span>
        <span class="theme-toggle__label">${theme === 'dark' ? 'Light theme' : 'Dark theme'}</span>
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

    const chevronLabel =
      (mode === 'persistent' && state === 'collapsed') ? 'Expand sidebar' : 'Collapse sidebar';
    const chevronLabelShort =
      (mode === 'persistent' && state === 'collapsed') ? 'Expand' : 'Collapse';

    shadow.innerHTML = `
      <link rel="stylesheet" href="/_shared/navbar-inner.css">
      <aside part="rail" data-mode="${mode}" data-state="${state}"
             role="navigation" aria-label="Platform navigation">
        ${brand}
        <nav><ul>${items}</ul></nav>
        <div class="rail-bottom">
          ${themeBtn}
          <button class="toggle" type="button" aria-label="${chevronLabel}">
            ${ICONS.chevronLeft}
            <span class="toggle__label">${chevronLabelShort}</span>
          </button>
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
      this._hoverTimer = null;
      this._leaveTimer = null;
      this._onKeydown = this._handleEscape.bind(this);
      this._onStorage = this._handleStorage.bind(this);
    }

    connectedCallback() {
      this.dataset.theme = this._theme;
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

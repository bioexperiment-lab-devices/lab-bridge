// compose/shell/navbar.js (served at /_shared/navbar.js by Caddy)
// Platform navbar for lab-bridge. See compose/shell/README.md.
// Single source of truth for navigation.

(() => {
  if (customElements.get('lds-navbar')) return;

  const RAIL_W_COLLAPSED = '56px';
  const RAIL_W_EXPANDED  = '180px';

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

  // Icons — Lucide outline icons (lucide.dev) for UI, Simple Icons (simpleicons.org)
  // for brand marks. UI icons follow Lucide's defaults: 24×24 viewBox, stroke-width 2,
  // currentColor. Brand marks use fill="currentColor" on a 24×24 viewBox.
  const ICON = (paths) =>
    `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true">${paths}</svg>`;
  const BRAND = (paths) =>
    `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"
          aria-hidden="true">${paths}</svg>`;
  const ICONS = {
    // Lucide: house
    home:    ICON(`<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/>
                    <path d="M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>`),
    // Lucide: book-open
    docs:    ICON(`<path d="M12 7v14"/>
                    <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>`),
    // Lucide: download
    agent:   ICON(`<path d="M12 15V3"/>
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <path d="m7 10 5 5 5-5"/>`),
    // Simple Icons: Jupyter
    jupyter: BRAND(`<path d="M7.157 22.201A1.784 1.799 0 0 1 5.374 24a1.784 1.799 0 0 1-1.784-1.799 1.784 1.799 0 0 1 1.784-1.799 1.784 1.799 0 0 1 1.783 1.799zM20.582 1.427a1.415 1.427 0 0 1-1.415 1.428 1.415 1.427 0 0 1-1.416-1.428A1.415 1.427 0 0 1 19.167 0a1.415 1.427 0 0 1 1.415 1.427zM4.992 3.336A1.047 1.056 0 0 1 3.946 4.39a1.047 1.056 0 0 1-1.047-1.055A1.047 1.056 0 0 1 3.946 2.28a1.047 1.056 0 0 1 1.046 1.056zm7.336 1.517c3.769 0 7.06 1.38 8.768 3.424a9.363 9.363 0 0 0-3.393-4.547 9.238 9.238 0 0 0-5.377-1.728A9.238 9.238 0 0 0 6.95 3.73a9.363 9.363 0 0 0-3.394 4.547c1.713-2.04 5.004-3.424 8.772-3.424zm.001 13.295c-3.768 0-7.06-1.381-8.768-3.425a9.363 9.363 0 0 0 3.394 4.547A9.238 9.238 0 0 0 12.33 21a9.238 9.238 0 0 0 5.377-1.729 9.363 9.363 0 0 0 3.393-4.547c-1.712 2.044-5.003 3.425-8.772 3.425Z"/>`),
    // Simple Icons: Grafana
    grafana: BRAND(`<path d="M23.02 10.59a8.578 8.578 0 0 0-.862-3.034 8.911 8.911 0 0 0-1.789-2.445c.337-1.342-.413-2.505-.413-2.505-1.292-.08-2.113.4-2.416.62-.052-.02-.102-.044-.154-.064-.22-.089-.446-.172-.677-.247-.231-.073-.47-.14-.711-.197a9.867 9.867 0 0 0-.875-.161C14.557.753 12.94 0 12.94 0c-1.804 1.145-2.147 2.744-2.147 2.744l-.018.093c-.098.029-.2.057-.298.088-.138.042-.275.094-.413.143-.138.055-.275.107-.41.166a8.869 8.869 0 0 0-1.557.87l-.063-.029c-2.497-.955-4.716.195-4.716.195-.203 2.658.996 4.33 1.235 4.636a11.608 11.608 0 0 0-.607 2.635C1.636 12.677.953 15.014.953 15.014c1.926 2.214 4.171 2.351 4.171 2.351.003-.002.006-.002.006-.005.285.509.615.994.986 1.446.156.19.32.371.488.548-.704 2.009.099 3.68.099 3.68 2.144.08 3.553-.937 3.849-1.173a9.784 9.784 0 0 0 3.164.501h.08l.055-.003.107-.002.103-.005.003.002c1.01 1.44 2.788 1.646 2.788 1.646 1.264-1.332 1.337-2.653 1.337-2.94v-.058c0-.02-.003-.039-.003-.06.265-.187.52-.387.758-.6a7.875 7.875 0 0 0 1.415-1.7c1.43.083 2.437-.885 2.437-.885-.236-1.49-1.085-2.216-1.264-2.354l-.018-.013-.016-.013a.217.217 0 0 1-.031-.02c.008-.092.016-.18.02-.27.011-.162.016-.323.016-.48v-.253l-.005-.098-.008-.135a1.891 1.891 0 0 0-.01-.13c-.003-.042-.008-.083-.013-.125l-.016-.124-.018-.122a6.215 6.215 0 0 0-2.032-3.73 6.015 6.015 0 0 0-3.222-1.46 6.292 6.292 0 0 0-.85-.048l-.107.002h-.063l-.044.003-.104.008a4.777 4.777 0 0 0-3.335 1.695c-.332.4-.592.84-.768 1.297a4.594 4.594 0 0 0-.312 1.817l.003.091c.005.055.007.11.013.164a3.615 3.615 0 0 0 .698 1.82 3.53 3.53 0 0 0 1.827 1.282c.33.098.66.14.971.137.039 0 .078 0 .114-.002l.063-.003c.02 0 .041-.003.062-.003.034-.002.065-.007.099-.01.007 0 .018-.003.028-.003l.031-.005.06-.008a1.18 1.18 0 0 0 .112-.02c.036-.008.072-.013.109-.024a2.634 2.634 0 0 0 .914-.415c.028-.02.056-.041.085-.065a.248.248 0 0 0 .039-.35.244.244 0 0 0-.309-.06l-.078.042c-.09.044-.184.083-.283.116a2.476 2.476 0 0 1-.475.096c-.028.003-.054.006-.083.006l-.083.002c-.026 0-.054 0-.08-.002l-.102-.006h-.012l-.024.006c-.016-.003-.031-.003-.044-.006-.031-.002-.06-.007-.091-.01a2.59 2.59 0 0 1-.724-.213 2.557 2.557 0 0 1-.667-.438 2.52 2.52 0 0 1-.805-1.475 2.306 2.306 0 0 1-.029-.444l.006-.122v-.023l.002-.031c.003-.021.003-.04.005-.06a3.163 3.163 0 0 1 1.352-2.29 3.12 3.12 0 0 1 .937-.43 2.946 2.946 0 0 1 .776-.101h.06l.07.002.045.003h.026l.07.005a4.041 4.041 0 0 1 1.635.49 3.94 3.94 0 0 1 1.602 1.662 3.77 3.77 0 0 1 .397 1.414l.005.076.003.075c.002.026.002.05.002.075 0 .024.003.052 0 .07v.065l-.002.073-.008.174a6.195 6.195 0 0 1-.08.639 5.1 5.1 0 0 1-.267.927 5.31 5.31 0 0 1-.624 1.13 5.052 5.052 0 0 1-3.237 2.014 4.82 4.82 0 0 1-.649.066l-.039.003h-.287a6.607 6.607 0 0 1-1.716-.265 6.776 6.776 0 0 1-3.4-2.274 6.75 6.75 0 0 1-.746-1.15 6.616 6.616 0 0 1-.714-2.596l-.005-.083-.002-.02v-.056l-.003-.073v-.096l-.003-.104v-.07l.003-.163c.008-.22.026-.45.054-.678a8.707 8.707 0 0 1 .28-1.355c.128-.444.286-.872.473-1.277a7.04 7.04 0 0 1 1.456-2.1 5.925 5.925 0 0 1 .953-.763c.169-.111.343-.213.524-.306.089-.05.182-.091.273-.135.047-.02.093-.042.138-.062a7.177 7.177 0 0 1 .714-.267l.145-.045c.049-.015.098-.026.148-.041.098-.029.197-.052.296-.076.049-.013.1-.02.15-.033l.15-.032.151-.028.076-.013.075-.01.153-.024c.057-.01.114-.013.171-.023l.169-.021c.036-.003.073-.008.106-.01l.073-.008.036-.003.042-.002c.057-.003.114-.008.171-.01l.086-.006h.023l.037-.003.145-.007a7.999 7.999 0 0 1 1.708.125 7.917 7.917 0 0 1 2.048.68 8.253 8.253 0 0 1 1.672 1.09l.09.077.089.078c.06.052.114.107.171.159.057.052.112.106.166.16.052.055.107.107.159.164a8.671 8.671 0 0 1 1.41 1.978c.012.026.028.052.04.078l.04.078.075.156c.023.051.05.1.07.153l.065.15a8.848 8.848 0 0 1 .45 1.34.19.19 0 0 0 .201.142.186.186 0 0 0 .172-.184c.01-.246.002-.532-.024-.856z"/>`),
    // Lucide: zap
    flasher: ICON(`<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>`),
    // Lucide: chevron-right / chevron-left
    chevronRight: ICON(`<path d="m9 18 6-6-6-6"/>`),
    chevronLeft:  ICON(`<path d="m15 18-6-6 6-6"/>`),
    // Lucide: sun
    sun: ICON(`<circle cx="12" cy="12" r="4"/>
                <path d="M12 2v2"/><path d="M12 20v2"/>
                <path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>
                <path d="M2 12h2"/><path d="M20 12h2"/>
                <path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>`),
    // Lucide: moon
    moon: ICON(`<path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401"/>`),
    // Lucide: log-in
    signin: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                aria-hidden="true">
                <path d="m10 17 5-5-5-5"/>
                <path d="M15 12H3"/>
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
              </svg>`,
    // Lucide: log-out
    logoutBig: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                  aria-hidden="true">
                  <path d="m16 17 5-5-5-5"/>
                  <path d="M21 12H9"/>
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                </svg>`,
    // Lucide: x
    closeX: `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
               aria-hidden="true">
               <path d="M18 6 6 18"/>
               <path d="m6 6 12 12"/>
             </svg>`,
  };

  const BRAND_MARK_SVG =
    `<svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true">
       <rect x="2" y="2" width="24" height="24" rx="4" fill="var(--accent)"/>
       <path d="M9 9h-2v10h2M19 9h2v10h-2" stroke="var(--accent-on)" stroke-width="1.5"
             stroke-linecap="round" fill="none"/>
       <circle cx="14" cy="14" r="2.6" fill="var(--accent-on)"/>
     </svg>`;

  // ─── Mode + active detection ──────────────────────────────────────────
  function detectMode() {
    const path = location.pathname;
    for (const rule of PATH_RULES) if (path.startsWith(rule.prefix)) return rule.mode;
    return 'persistent';
  }
  function detectActiveId() {
    // On /login the navbar should keep highlighting the service the user was
    // trying to reach, not /login itself (which would always resolve to Home
    // via the leading '/'). The rd= query param carries the original target.
    let path = location.pathname;
    if (path === '/login') {
      const rd = new URLSearchParams(location.search).get('rd');
      if (rd) {
        try { path = new URL(rd, location.origin).pathname; } catch (_) { /* malformed rd — fall back to /login */ }
      }
    }
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
  const BOOKMARK_POS_KEY = 'navbar:bookmark-pos';
  const DRAG_THRESHOLD_PX = 4;

  function loadBookmarkPos() {
    try {
      const raw = localStorage.getItem(BOOKMARK_POS_KEY);
      if (!raw) return null;
      const p = JSON.parse(raw);
      if (typeof p.left === 'number' && typeof p.bottom === 'number') return p;
    } catch (_) { /* ignore parse errors — fall back to default */ }
    return null;
  }

  function saveBookmarkPos(pos) {
    try { localStorage.setItem(BOOKMARK_POS_KEY, JSON.stringify(pos)); } catch (_) { /* quota / private mode */ }
  }

  function applyBookmarkPos(host, pos) {
    if (!pos) {
      host.style.removeProperty('--bookmark-left');
      host.style.removeProperty('--bookmark-bottom');
      return;
    }
    host.style.setProperty('--bookmark-left', pos.left + 'px');
    host.style.setProperty('--bookmark-bottom', pos.bottom + 'px');
  }

  function renderShadow(shadow, mode, state, activeId, theme) {
    const items = SERVICES.map((svc) => `
      <li${svc.id === activeId ? ' class="active"' : ''}>
        <a href="${svc.href}" data-id="${svc.id}"
           aria-label="${svc.label}"${svc.id === activeId ? ' aria-current="page"' : ''}>
          <span class="icon">${ICONS[svc.id]}</span>
          <span class="label">${svc.label}</span>
        </a>
      </li>
    `).join('');

    const isBookmarkTab = mode === 'bookmark' && state === 'tab';

    const brand = `
      <a class="brand" href="/" aria-label="lab-bridge home">
        <span class="brand__mark">${BRAND_MARK_SVG}</span>
        <span class="brand__text">
          <span class="brand__wordmark">lab-bridge</span>
          ${PLATFORM_VERSION ? `<span class="brand__version">v${PLATFORM_VERSION}</span>` : ''}
        </span>
      </a>`;

    const themeBtn = `
      <button class="theme-toggle" type="button"
              aria-label="Switch to ${theme === 'dark' ? 'light' : 'dark'} theme"
              title="Lab Bridge theme only">
        <span class="theme-toggle__icon">${theme === 'dark' ? ICONS.sun : ICONS.moon}</span>
        <span class="theme-toggle__label">${theme === 'dark' ? 'Light theme' : 'Dark theme'}</span>
      </button>`;

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

    const chevronLabel = state === 'collapsed' ? 'Expand sidebar' : 'Collapse sidebar';
    const chevronLabelShort = state === 'collapsed' ? 'Expand' : 'Collapse';

    const railBottom = mode === 'persistent' ? `
      <div class="rail-bottom">
        <div class="auth-slot"></div>
        ${themeBtn}
        <button class="toggle" type="button" aria-label="${chevronLabel}">
          ${ICONS.chevronLeft}
          <span class="toggle__label">${chevronLabelShort}</span>
        </button>
      </div>` : `
      <div class="rail-bottom">
        <div class="auth-slot"></div>
        ${themeBtn}
      </div>`;

    shadow.innerHTML = `
      <link rel="stylesheet" href="/_shared/navbar-inner.css">
      <aside part="rail" data-mode="${mode}" data-state="${state}"
             role="navigation" aria-label="Platform navigation">
        ${brand}
        <nav><ul>${items}</ul></nav>
        ${railBottom}
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
      this._bookmarkPos = loadBookmarkPos();
      this._suppressClick = false;
      this._onKeydown = this._handleEscape.bind(this);
      this._onStorage = this._handleStorage.bind(this);
    }

    connectedCallback() {
      this.dataset.theme = this._theme;
      applyBookmarkPos(this, this._bookmarkPos);
      this._render();
      this._wire();
      this._applyNavWidth();
      // _wire() already calls renderAuthSlot — no need to call it again here.
      document.addEventListener('keydown', this._onKeydown);
      window.addEventListener('storage', this._onStorage);
    }

    disconnectedCallback() {
      document.removeEventListener('keydown', this._onKeydown);
      window.removeEventListener('storage', this._onStorage);
    }

    _render() {
      // If the modal is open when we rebuild the shadow tree, close it first
      // so its node is removed cleanly and _modalEl is nulled — otherwise the
      // detached div would block reopening (the open guard checks _modalEl).
      if (this._modalEl) this._closeSignOutModal();
      renderShadow(this.shadowRoot, this._mode, this._state, detectActiveId(), this._theme);
    }

    _applyNavWidth() {
      if (this._mode !== 'persistent') {
        setNavWidth('0px');
        return;
      }
      setNavWidth(this._state === 'expanded' ? RAIL_W_EXPANDED : RAIL_W_COLLAPSED);
    }

    _setPersistentState(next) {
      this._state = next;
      localStorage.setItem(STATE_KEY, next);
      this._applyNavWidth();
      this._render();
      this._wire();
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
          toggle.addEventListener('click', (e) => {
            // Stop the click from bubbling to the rail handler below — otherwise
            // the rail's "click empty space to expand" logic would fight the
            // toggle when collapsing from expanded.
            e.stopPropagation();
            this._setPersistentState(this._state === 'collapsed' ? 'expanded' : 'collapsed');
          });
        }
        // Click on empty rail space (not a link/button) expands when collapsed.
        // When expanded, clicks on empty space do nothing — only the chevron
        // collapses the rail, so the user can't accidentally close it while
        // moving between links.
        rail.addEventListener('click', (e) => {
          if (this._state !== 'collapsed') return;
          if (e.target.closest('a, button')) return;
          this._setPersistentState('expanded');
        });
      } else {
        // Bookmark mode: click-driven (no hover). Tab is also draggable so the
        // user can park it anywhere on screen; the chosen position is persisted.
        if (this._state === 'tab') {
          this._wireBookmarkDrag(rail);
          rail.addEventListener('click', (e) => {
            if (this._suppressClick) {
              // Click followed a drag — swallow it so the rail doesn't expand.
              this._suppressClick = false;
              e.stopPropagation();
              return;
            }
            this._setBookmarkState('expanded');
          });
        }
        if (backdrop) {
          backdrop.addEventListener('click', () => this._setBookmarkState('tab'));
        }
      }

      // Repopulate the auth slot — _render() rebuilt the shadow tree and the
      // .auth-slot inside it is empty until we fetch whoami again.
      renderAuthSlot(this.shadowRoot, this);
    }

    _wireBookmarkDrag(rail) {
      let startX, startY, startLeft, startBottom, dragging = false, pointerId = null;

      const onMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        if (!dragging && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
          dragging = true;
          rail.setPointerCapture(pointerId);
          rail.style.cursor = 'grabbing';
        }
        if (dragging) {
          ev.preventDefault();
          const rect = rail.getBoundingClientRect();
          const newLeft = Math.max(0, Math.min(window.innerWidth - rect.width, startLeft + dx));
          const newBottom = Math.max(0, Math.min(window.innerHeight - rect.height, startBottom - dy));
          this.style.setProperty('--bookmark-left', newLeft + 'px');
          this.style.setProperty('--bookmark-bottom', newBottom + 'px');
          this._bookmarkPos = { left: newLeft, bottom: newBottom };
        }
      };

      const onUp = () => {
        rail.removeEventListener('pointermove', onMove);
        rail.removeEventListener('pointerup', onUp);
        rail.removeEventListener('pointercancel', onUp);
        rail.style.cursor = '';
        if (dragging) {
          saveBookmarkPos(this._bookmarkPos);
          // Defer suppression flag clear until after the trailing click event fires.
          this._suppressClick = true;
        }
        dragging = false;
        pointerId = null;
      };

      rail.addEventListener('pointerdown', (e) => {
        if (e.button !== 0) return;
        const rect = rail.getBoundingClientRect();
        startX = e.clientX;
        startY = e.clientY;
        startLeft = rect.left;
        startBottom = window.innerHeight - rect.bottom;
        pointerId = e.pointerId;
        dragging = false;
        rail.addEventListener('pointermove', onMove);
        rail.addEventListener('pointerup', onUp);
        rail.addEventListener('pointercancel', onUp);
      });
    }

    _openSignOutModal(user) {
      if (this._modalEl) return;  // already open
      this._modalFocusReturn = this.shadowRoot.activeElement || null;

      const modal = document.createElement('div');
      modal.className = 'modal';
      modal.setAttribute('role', 'dialog');
      modal.setAttribute('aria-modal', 'true');
      modal.setAttribute('aria-labelledby', 'lb-signout-title');
      modal.innerHTML = `
        <div class="modal__backdrop" data-action="cancel"></div>
        <div class="modal__card">
          <header class="modal__head">
            <div class="modal__ico" aria-hidden="true">${ICONS.logoutBig}</div>
            <h2 id="lb-signout-title" class="modal__title">Sign out?</h2>
            <button type="button" class="modal__close" aria-label="Close" data-action="cancel">
              ${ICONS.closeX}
            </button>
          </header>
          <div class="modal__body">
            <p class="modal__lede">You'll be signed out of lab-bridge. Open sessions to JupyterLab, Grafana, and Flasher will end.</p>
            <div class="modal__user">
              <span class="user__avatar" aria-hidden="true">${escapeHtml(user.initials)}</span>
              <div class="modal__user-text"><b>${escapeHtml(user.name)}</b></div>
            </div>
          </div>
          <footer class="modal__foot">
            <button type="button" class="modal__btn" data-action="cancel">Cancel</button>
            <button type="button" class="modal__btn modal__btn--danger" data-action="confirm">Sign out</button>
          </footer>
        </div>`;
      this.shadowRoot.appendChild(modal);
      this._modalEl = modal;

      modal.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]')?.dataset?.action;
        if (action === 'cancel') this._closeSignOutModal();
        else if (action === 'confirm') this._confirmSignOut();
      });

      this._modalFocusTrap = (e) => {
        if (!this._modalEl) return;
        const card = this._modalEl.querySelector('.modal__card');
        if (!card.contains(e.target)) {
          e.stopPropagation();
          const first = card.querySelector('button');
          if (first) first.focus();
        }
      };
      this.shadowRoot.addEventListener('focusin', this._modalFocusTrap);

      // Keydown trap on the card — handles Tab/Shift+Tab cycling explicitly
      // so focus can't escape to the Light DOM through the shadow boundary
      // (where focusin on the shadow root wouldn't fire).
      const card = modal.querySelector('.modal__card');
      this._modalKeydown = (e) => {
        if (e.key !== 'Tab') return;
        const focusable = [...card.querySelectorAll('button:not([disabled])')];
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = this.shadowRoot.activeElement;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      };
      card.addEventListener('keydown', this._modalKeydown);

      // Focus the Cancel button (the safer default for a destructive dialog).
      const cancelBtn = modal.querySelector('.modal__btn[data-action="cancel"]');
      if (cancelBtn) cancelBtn.focus();
    }

    _closeSignOutModal() {
      if (!this._modalEl) return;
      this.shadowRoot.removeEventListener('focusin', this._modalFocusTrap);
      const card = this._modalEl.querySelector('.modal__card');
      if (card && this._modalKeydown) card.removeEventListener('keydown', this._modalKeydown);
      this._modalEl.remove();
      this._modalEl = null;
      this._modalFocusTrap = null;
      this._modalKeydown = null;
      if (this._modalFocusReturn && typeof this._modalFocusReturn.focus === 'function') {
        this._modalFocusReturn.focus();
      }
      this._modalFocusReturn = null;
    }

    _confirmSignOut() {
      // Disable the confirm button so a slow network can't be double-clicked.
      const btn = this._modalEl?.querySelector('.modal__btn--danger');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Signing out…';
      }
      // POST /logout invalidates the Authelia session server-side and expires
      // the cookie client-side; the assign(/) reload then re-fetches whoami.
      // We assign(/) regardless of the POST outcome so the user is never
      // stranded — if logout silently failed the next page will show them
      // signed in and they can retry.
      fetch('/logout', { method: 'POST', credentials: 'include' })
        .catch(() => {})
        .finally(() => { location.assign('/'); });
    }

    _handleEscape(e) {
      if (e.key !== 'Escape') return;
      // Modal takes priority — closing it must not also collapse the rail.
      if (this._modalEl) {
        this._closeSignOutModal();
        return;
      }
      if (this._state !== 'expanded') return;
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

  function deriveInitials(source) {
    if (!source) return '?';
    const parts = String(source).trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return '?';
    return parts.slice(0, 2).map((s) => s[0]).join('').toUpperCase();
  }

  async function renderAuthSlot(root, host) {
    let data = { user: null };
    try {
      const r = await fetch('/api/auth/whoami', { credentials: 'include' });
      if (r.ok) data = await r.json();
    } catch (_) {
      // Network error — render as logged-out, no surprises.
    }
    // Re-query after await — a re-render (theme toggle, collapse) during the
    // in-flight fetch may have replaced the shadow tree; the slot we captured
    // before the await would be a detached node.
    const slot = root.querySelector('.auth-slot');
    if (!slot) return;
    if (data.user) {
      const name = data.display_name || data.user || 'Account';
      const initials = deriveInitials(data.display_name || data.user);
      slot.innerHTML = `
        <button class="user" type="button" aria-label="Account menu: ${escapeAttr(name)}">
          <span class="user__avatar" aria-hidden="true">${escapeHtml(initials)}</span>
          <span class="user__text">
            <span class="user__name">${escapeHtml(name)}</span>
          </span>
        </button>`;
      const btn = slot.querySelector('.user');
      btn.addEventListener('click', () => host._openSignOutModal({ name, initials }));
    } else {
      const rd = encodeURIComponent(location.pathname + location.search);
      slot.innerHTML = `
        <a class="signin-cta" href="/login?rd=${rd}" aria-label="Sign in">
          ${ICONS.signin}
          <span class="signin-cta__label">Sign in</span>
        </a>`;
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
  function escapeAttr(s) {
    return escapeHtml(s);
  }

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

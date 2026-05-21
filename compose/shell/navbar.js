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
    signin: `<svg viewBox="0 0 14 14" width="14" height="14" fill="none" stroke="currentColor"
                stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
                aria-hidden="true">
                <circle cx="4.5" cy="7" r="2.25"/>
                <path d="M6.75 7h5.25"/>
                <path d="M10 7v1.75M12 7v2"/>
              </svg>`,
    logoutBig: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
                  stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
                  aria-hidden="true">
                  <path d="M14 8V6.5A1.5 1.5 0 0 0 12.5 5h-6A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19h6a1.5 1.5 0 0 0 1.5-1.5V16"/>
                  <path d="M19 12H10"/>
                  <path d="M16 9l3 3-3 3"/>
                </svg>`,
    closeX: `<svg viewBox="0 0 14 14" width="12" height="12" fill="none" stroke="currentColor"
               stroke-width="1.6" stroke-linecap="round"
               aria-hidden="true">
               <path d="M3 3l8 8M11 3l-8 8"/>
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
      <div class="brand">
        <span class="brand__mark">${BRAND_MARK_SVG}</span>
        <span class="brand__text">
          <span class="brand__wordmark">lab-bridge</span>
          ${PLATFORM_VERSION ? `<span class="brand__version">v${PLATFORM_VERSION}</span>` : ''}
        </span>
      </div>`;

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

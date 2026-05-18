// compose/shell/navbar.js (served at /_shared/navbar.js by Caddy)
// Platform navbar for lab-bridge. See compose/shell/README.md.
// Single source of truth for navigation.

(() => {
  if (customElements.get('lds-navbar')) return;  // idempotent on duplicate load

  // Single source of truth for nav-width sizes. The CSS in
  // navbar-inner.css carries the same values as `--rail-w-collapsed`
  // and `--rail-w-expanded`; if these change, update both files.
  const RAIL_W_COLLAPSED = '52px';
  const RAIL_W_EXPANDED  = '240px';

  // ─── Data ─────────────────────────────────────────────────────────────
  const SERVICES = [
    { id: 'home',    label: 'Home',           href: '/',          mode: 'persistent' },
    { id: 'docs',    label: 'Docs',           href: '/docs/',     mode: 'persistent' },
    { id: 'agent',   label: 'Download Agent', href: '/download/agent',     mode: 'persistent' },
    { id: 'jupyter', label: 'JupyterLab',     href: '/jupyter/',           mode: 'bookmark' },
    { id: 'grafana', label: 'Grafana',        href: '/grafana/dashboards', mode: 'bookmark' },
    { id: 'flasher', label: 'Flasher',        href: '/flash/',    mode: 'persistent' },
  ];

  const PATH_RULES = [
    { prefix: '/jupyter', mode: 'bookmark' },
    { prefix: '/grafana', mode: 'bookmark' },
  ];

  // Inline SVGs (hand-rolled, ~150 chars each). Icon library swap is an
  // implementation detail tracked in the spec's "Open implementation
  // details" section — replacement can land in a follow-up PR.
  const ICONS = {
    home:    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12 12 3l9 9M5 10v10h14V10"/></svg>',
    docs:    '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2h9l5 5v15H6zM14 2v6h6"/></svg>',
    agent:   '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/></svg>',
    jupyter: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M7 14a5 5 0 0 0 10 0"/></svg>',
    grafana: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 14a8 8 0 1 1 16 0M8 18l2-2 2 2 2-2 2 2"/></svg>',
    flasher: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 2h10v6l3 3-3 3v8H7v-8L4 11l3-3zM10 14h4"/></svg>',
    chevronRight: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>',
    chevronLeft:  '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 6-6 6 6 6"/></svg>',
  };

  // ─── Mode detection ───────────────────────────────────────────────────
  function detectMode() {
    const path = location.pathname;
    for (const rule of PATH_RULES) {
      if (path.startsWith(rule.prefix)) return rule.mode;
    }
    return 'persistent';
  }

  function detectActiveId() {
    const path = location.pathname;
    let best = null;
    let bestLen = -1;
    for (const svc of SERVICES) {
      if (path.startsWith(svc.href) && svc.href.length > bestLen) {
        best = svc.id;
        bestLen = svc.href.length;
      }
    }
    return best;
  }

  // ─── DOM rendering ────────────────────────────────────────────────────
  function renderShadow(shadow, mode, state, activeId) {
    const items = SERVICES.map((svc) => `
      <li${svc.id === activeId ? ' class="active"' : ''}>
        <a href="${svc.href}" data-id="${svc.id}"
           aria-label="${svc.label}"${svc.id === activeId ? ' aria-current="page"' : ''}>
          <span class="icon">${ICONS[svc.id]}</span>
          <span class="label">${svc.label}</span>
        </a>
      </li>
    `).join('');

    shadow.innerHTML = `
      <link rel="stylesheet" href="/_shared/navbar-inner.css">
      <aside part="rail" data-mode="${mode}" data-state="${state}"
             role="navigation" aria-label="Platform navigation">
        <nav><ul>${items}</ul></nav>
        <button class="toggle" type="button" aria-label="${
          state === 'collapsed' ? 'Expand sidebar' : 'Collapse sidebar'
        }">${state === 'collapsed' ? ICONS.chevronRight : ICONS.chevronLeft}</button>
      </aside>
      <div class="backdrop" hidden></div>
    `;
  }

  // ─── State management ─────────────────────────────────────────────────
  const STATE_KEY = 'navbar:state';

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
      this._hoverTimer = null;
      this._leaveTimer = null;
      this._onKeydown = this._handleEscape.bind(this);
    }

    connectedCallback() {
      this._render();
      this._wire();
      this._applyNavWidth();
    }

    _render() {
      renderShadow(this.shadowRoot, this._mode, this._state, detectActiveId());
    }

    _applyNavWidth() {
      if (this._mode === 'persistent') {
        setNavWidth(RAIL_W_COLLAPSED);
      } else {
        setNavWidth('0px');
      }
    }

    _wire() {
      const root = this.shadowRoot;
      const toggle = root.querySelector('.toggle');
      const rail = root.querySelector('aside');
      const backdrop = root.querySelector('.backdrop');

      if (this._mode === 'persistent') {
        toggle.addEventListener('click', () => {
          this._state = this._state === 'collapsed' ? 'expanded' : 'collapsed';
          localStorage.setItem(STATE_KEY, this._state);
          rail.dataset.state = this._state;
          backdrop.hidden = this._state !== 'expanded';
          toggle.setAttribute('aria-label',
            this._state === 'collapsed' ? 'Expand sidebar' : 'Collapse sidebar');
          toggle.innerHTML = this._state === 'collapsed' ? ICONS.chevronRight : ICONS.chevronLeft;
        });
        backdrop.addEventListener('click', () => {
          if (this._state === 'expanded') toggle.click();
        });
      } else {
        // bookmark mode
        rail.addEventListener('mouseenter', () => {
          clearTimeout(this._leaveTimer);
          this._hoverTimer = setTimeout(() => {
            this._state = 'expanded';
            rail.dataset.state = 'expanded';
            backdrop.hidden = false;
          }, 150);
        });
        rail.addEventListener('mouseleave', () => {
          clearTimeout(this._hoverTimer);
          this._leaveTimer = setTimeout(() => {
            this._state = 'tab';
            rail.dataset.state = 'tab';
            backdrop.hidden = true;
          }, 300);
        });
        backdrop.addEventListener('click', () => {
          clearTimeout(this._hoverTimer);
          this._state = 'tab';
          rail.dataset.state = 'tab';
          backdrop.hidden = true;
        });
      }

      document.addEventListener('keydown', this._onKeydown);
    }

    _handleEscape(e) {
      if (e.key !== 'Escape' || this._state !== 'expanded') return;
      const root = this.shadowRoot;
      const rail = root.querySelector('aside');
      const backdrop = root.querySelector('.backdrop');
      if (this._mode === 'persistent') {
        this._state = 'collapsed';
        localStorage.setItem(STATE_KEY, 'collapsed');
      } else {
        this._state = 'tab';
      }
      rail.dataset.state = this._state;
      backdrop.hidden = true;
    }

    disconnectedCallback() {
      document.removeEventListener('keydown', this._onKeydown);
    }
  }

  customElements.define('lds-navbar', LdsNavbar);

  // ─── Boot ─────────────────────────────────────────────────────────────
  function mount() {
    if (document.querySelector('lds-navbar')) return;
    const el = document.createElement('lds-navbar');
    document.body.appendChild(el);
  }

  function startMutationGuard() {
    const observer = new MutationObserver(() => {
      if (!document.querySelector('lds-navbar')) {
        mount();
      }
    });
    observer.observe(document.body, { childList: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      mount();
      startMutationGuard();
    });
  } else {
    mount();
    startMutationGuard();
  }
})();

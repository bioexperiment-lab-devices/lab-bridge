// Lab Bridge — navbar (side rail + bookmark) + browser shell
/* global React */

const { useState } = React;

// ============================================================
// Icons — fresh minimal set, 18px viewBox
// ============================================================
const Icons = {
  home: (
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 8L9 3l6.5 5" />
      <path d="M4 8v6.5h4v-4h2v4h4V8" />
    </svg>
  ),
  docs: (
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3.5 3h7.5l3 3v8.5a.5.5 0 01-.5.5h-10a.5.5 0 01-.5-.5v-11A.5.5 0 013.5 3z" />
      <path d="M11 3v3.5h3" />
      <path d="M6 9h6M6 11.5h6M6 13.5h4" />
    </svg>
  ),
  download: (
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2.5v8.5" />
      <path d="M5.5 8L9 11.5 12.5 8" />
      <path d="M3 12.5v2A.5.5 0 003.5 15h11a.5.5 0 00.5-.5v-2" />
    </svg>
  ),
  jupyter: (
    // abstract atom-like — three orbits around a node. Generic, not branded.
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
      <ellipse cx="9" cy="9" rx="6.5" ry="2.6" />
      <ellipse cx="9" cy="9" rx="6.5" ry="2.6" transform="rotate(60 9 9)" />
      <ellipse cx="9" cy="9" rx="6.5" ry="2.6" transform="rotate(120 9 9)" />
      <circle cx="9" cy="9" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  ),
  grafana: (
    // abstract bar+line chart — generic, not the Grafana mark
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 14.5h13" />
      <rect x="3.5"  y="9"  width="2" height="4.5" rx="0.4" />
      <rect x="7"    y="6"  width="2" height="7.5" rx="0.4" />
      <rect x="10.5" y="10.5" width="2" height="3" rx="0.4" />
      <rect x="14"   y="7.5" width="1.5" height="6" rx="0.4" />
      <path d="M4 5.5l3.5-2 3.5 3 4-2.5" strokeDasharray="0 0" />
    </svg>
  ),
  flasher: (
    // lightning + chip combo — represents firmware flashing
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2L4 10h4l-1 6 5.5-8H8.5l1-6z" />
    </svg>
  ),
  chevronLeft: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 3.5L4.5 7 9 10.5" />
    </svg>
  ),
  sun: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="7" r="2.5" />
      <path d="M7 1.5v1.5M7 11v1.5M1.5 7h1.5M11 7h1.5M3 3l1 1M10 10l1 1M3 11l1-1M10 4l1-1" />
    </svg>
  ),
  moon: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11.5 8.5A5 5 0 015.5 2.5a5 5 0 106 6z" />
    </svg>
  ),
  copy: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3.5" y="2.5" width="6" height="6" rx="1" />
      <path d="M5.5 8.5v2a.5.5 0 00.5.5h5a.5.5 0 00.5-.5v-5a.5.5 0 00-.5-.5h-2" />
    </svg>
  ),
  arrowRight: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3.5 7h7M7 3.5L10.5 7 7 10.5" />
    </svg>
  ),
};

// ============================================================
// Nav items — fixed order per brief
// ============================================================
const NAV_ITEMS = [
  { id: "home",     label: "Home",           path: "/",                    icon: Icons.home,     ext: false },
  { id: "docs",     label: "Docs",           path: "/docs/",               icon: Icons.docs,     ext: false },
  { id: "download", label: "Download Agent", path: "/download/agent",      icon: Icons.download, ext: false },
  { id: "jupyter",  label: "JupyterLab",     path: "/jupyter/",            icon: Icons.jupyter,  ext: true  },
  { id: "grafana",  label: "Grafana",        path: "/grafana/dashboards",  icon: Icons.grafana,  ext: true  },
  { id: "flasher",  label: "Flasher",        path: "/flash/",              icon: Icons.flasher,  ext: true  },
];

// ============================================================
// Browser shell (matches Flasher's FlBrowser)
// ============================================================
function LBBrowser({ host = "lab-bridge.internal", path = "/", children }) {
  return (
    <div className="lb-window">
      <div className="lb-chrome">
        <div className="lb-traffic"><i /><i /><i /></div>
        <div className="lb-addr">
          <span className="lb-addr__lock">⌬</span>
          <span><span className="lb-muted">https://</span>{host}<span className="lb-addr__path">{path}</span></span>
        </div>
        <div style={{ width: 60, opacity: 0 }}>spacer</div>
      </div>
      <div className="lb-body">
        {children}
      </div>
    </div>
  );
}

// ============================================================
// Side rail (Mode 1) — expanded or collapsed
// ============================================================
function LBBrandMark({ size = 28 }) {
  // Compact wordmark: two terminal-bracket bars around a tunnel node
  return (
    <span className="lb-rail__mark" style={{ width: size, height: size, borderRadius: size > 24 ? 6 : 5, fontSize: size > 24 ? 13 : 11 }}>
      <span />
    </span>
  );
}

function LBRailNavItem({ item, active, theme = "light" }) {
  return (
    <a className="lb-nav-item" data-active={active || undefined} aria-current={active ? "page" : undefined}
       href={item.path}>
      <span className="lb-nav-item__ico" aria-hidden="true">{item.icon}</span>
      <span className="lb-nav-item__label">{item.label}</span>
      {item.ext && <span className="lb-nav-item__ext" aria-label="opens external app">↗</span>}
    </a>
  );
}

function LBRail({ mode = "expanded", active = "home", theme = "light" }) {
  return (
    <nav className="lb-rail" data-mode={mode} aria-label="Platform navigation">
      <div className="lb-rail__brand">
        <LBBrandMark />
        <div className="lb-rail__wordmark">
          <b>lab-bridge</b>
          <small>v3.4</small>
        </div>
      </div>
      <div className="lb-rail__nav">
        {NAV_ITEMS.map((it) => (
          <LBRailNavItem key={it.id} item={it} active={it.id === active} />
        ))}
      </div>
      <div className="lb-rail__bottom">
        <button className="lb-icon-btn" aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                style={{ width: "100%", display: "flex", justifyContent: "center", gap: 8, height: 30 }}>
          {theme === "dark" ? Icons.sun : Icons.moon}
          {mode === "expanded" && (
            <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)" }}>
              {theme === "dark" ? "Light theme" : "Dark theme"}
            </span>
          )}
        </button>
        <button className="lb-rail__chevron"
                aria-label={mode === "expanded" ? "Collapse sidebar" : "Expand sidebar"}>
          {Icons.chevronLeft}
          <span>Collapse</span>
        </button>
      </div>
    </nav>
  );
}

// ============================================================
// Bookmark mode (over JupyterLab / Grafana) — collapsed tab + hover overlay
// ============================================================
function LBBookmarkTab() {
  return (
    <div className="lb-bookmark" role="button" aria-label="Open lab-bridge navigation">
      <span className="lb-bookmark__mark">L</span>
      <span className="lb-bookmark__text">lab-bridge</span>
      <span className="lb-bookmark__hint">›</span>
    </div>
  );
}

function LBBookmarkOverlay({ active = "jupyter", theme = "light" }) {
  return (
    <div className="lb-bookmark-overlay">
      <div className="lb-bookmark-overlay__head">
        <LBBrandMark size={24} />
        <div className="lb-rail__wordmark">
          <b>lab-bridge</b>
          <small>v3.4</small>
        </div>
      </div>
      <div className="lb-bookmark-overlay__nav">
        {NAV_ITEMS.map((it) => (
          <LBRailNavItem key={it.id} item={it} active={it.id === active} />
        ))}
      </div>
      <div className="lb-bookmark-overlay__foot">
        <button className="lb-icon-btn" aria-label="Switch theme">
          {theme === "dark" ? Icons.sun : Icons.moon}
        </button>
        <span style={{ flex: 1, fontSize: 11, color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}>
          Esc to dismiss
        </span>
      </div>
    </div>
  );
}

// ============================================================
// Faux Jupyter / Grafana app body — placeholder for bookmark artboard
// (intentionally abstract; we do not recreate their UIs)
// ============================================================
function LBFauxApp({ label = "JupyterLab" }) {
  return (
    <div className="lb-faux">
      <div className="lb-faux__bar">
        <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{label}</span>
        <div className="lb-faux__menu">
          <span>File</span><span>Edit</span><span>View</span><span>Run</span><span>Help</span>
        </div>
      </div>
      <div className="lb-faux__body">
        <div className="lb-faux__sidebar">
          <i /><i /><i /><i />
        </div>
        <div className="lb-faux__main">
          <div className="lb-faux__placeholder">
            <div style={{ textAlign: "center" }}>
              <b>{label === "JupyterLab" ? "notebook surface" : "monitoring dashboards"}</b>
              <div style={{ marginTop: 8, fontSize: 10, opacity: 0.7 }}>third-party app — out of scope</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  LBBrowser, LBRail, LBBookmarkTab, LBBookmarkOverlay, LBFauxApp, LBBrandMark,
  LB_NAV_ITEMS: NAV_ITEMS, LB_ICONS: Icons,
});

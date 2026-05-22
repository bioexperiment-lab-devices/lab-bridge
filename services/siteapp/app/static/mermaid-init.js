// Loaded only on pages that contain at least one <pre class="mermaid">.
// Pairs with the vendored UMD bundle (mermaid.min.js), which exposes
// `window.mermaid`. Both <script> tags are `defer`, so this runs after
// the bundle has been parsed but before DOMContentLoaded fires.

// Match the site's theme (set on <html data-theme> by the inline script
// in base.html), not the OS preference — the two can disagree when the
// user has chosen a theme that differs from prefers-color-scheme.
function currentMermaidTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "default";
}

// Mermaid rewrites each <pre class="mermaid"> in place (replaces the source
// text with an <svg> and sets data-processed="true"). To re-render with a
// new theme we need to restore the source first; capture it on first sight.
function renderAll() {
  document.querySelectorAll("pre.mermaid").forEach((el) => {
    if (el.dataset.source === undefined) {
      el.dataset.source = el.textContent;
    } else {
      el.textContent = el.dataset.source;
      el.removeAttribute("data-processed");
    }
  });
  window.mermaid.initialize({
    startOnLoad: false,
    theme: currentMermaidTheme(),
    securityLevel: "strict",
  });
  window.mermaid.run({ querySelector: "pre.mermaid" });
}

renderAll();

// Re-render when the site theme flips. Observing <html data-theme> instead
// of listening for a navbar-specific event covers both in-tab toggles
// (navbar writes data-theme directly) and cross-tab sync (the storage
// handler in base.html mirrors the change onto data-theme).
new MutationObserver((mutations) => {
  for (const m of mutations) {
    if (m.attributeName === "data-theme") {
      renderAll();
      return;
    }
  }
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-theme"],
});

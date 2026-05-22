// Loaded only on pages that contain at least one <pre class="mermaid">.
// Pairs with the vendored UMD bundle (mermaid.min.js), which exposes
// `window.mermaid`. Both <script> tags are `defer`, so this runs after
// the bundle has been parsed but before DOMContentLoaded fires.
// Match the site's theme (set on <html data-theme> by the inline script
// in base.html), not the OS preference — the two can disagree when the
// user has chosen a theme that differs from prefers-color-scheme.
const dark = document.documentElement.dataset.theme === "dark";
window.mermaid.initialize({
  startOnLoad: false,
  theme: dark ? "dark" : "default",
  securityLevel: "strict",
});
window.mermaid.run({ querySelector: "pre.mermaid" });

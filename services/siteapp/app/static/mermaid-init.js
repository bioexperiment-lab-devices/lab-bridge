// Loaded only on pages that contain at least one <pre class="mermaid">.
// Pairs with the vendored UMD bundle (mermaid.min.js), which exposes
// `window.mermaid`. Both <script> tags are `defer`, so this runs after
// the bundle has been parsed but before DOMContentLoaded fires.
const dark = matchMedia("(prefers-color-scheme: dark)").matches;
window.mermaid.initialize({
  startOnLoad: false,
  theme: dark ? "dark" : "default",
  securityLevel: "strict",
});
window.mermaid.run({ querySelector: "pre.mermaid" });

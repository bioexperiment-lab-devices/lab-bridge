// Loaded only on pages that contain at least one <pre class="mermaid">.
// Dynamically imports the vendored Mermaid bundle, then renders all
// diagrams in place.
import("/_static/vendor/mermaid.min.js").then(() => {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  window.mermaid.initialize({
    startOnLoad: false,
    theme: dark ? "dark" : "default",
    securityLevel: "strict",
  });
  window.mermaid.run({ querySelector: "pre.mermaid" });
});

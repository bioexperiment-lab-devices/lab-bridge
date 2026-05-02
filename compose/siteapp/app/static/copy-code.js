// Attach an icon-only "copy code" button to every <pre><code> on the page.
// Clipboard glyph → checkmark on success, then reverts after a brief delay.

const COPY_SVG = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="4" width="9" height="11" rx="1.5"/><path d="M3 11V2.5A1.5 1.5 0 0 1 4.5 1H11"/></svg>`;

const CHECK_SVG = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m3.5 8.5 3 3L13 5"/></svg>`;

document.querySelectorAll("pre > code").forEach((code) => {
  const pre = code.parentElement;
  if (pre.querySelector(".copy-button")) return; // idempotent

  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy-button";
  button.setAttribute("aria-label", "Copy code");
  button.innerHTML = COPY_SVG;

  let resetTimer = null;
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(code.innerText);
      button.innerHTML = CHECK_SVG;
      button.classList.add("is-copied");
      button.setAttribute("aria-label", "Copied");
      clearTimeout(resetTimer);
      resetTimer = setTimeout(() => {
        button.innerHTML = COPY_SVG;
        button.classList.remove("is-copied");
        button.setAttribute("aria-label", "Copy code");
      }, 1400);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  });

  pre.appendChild(button);
});

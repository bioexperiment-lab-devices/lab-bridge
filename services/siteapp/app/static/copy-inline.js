// Click-to-copy utility. Reads target text from data-copy-text="..." or
// data-copy-from="<selector>" (innerText of the matched element). Toggles
// .is-copied on the button for 1.5s. Single delegated click listener,
// idempotent on duplicate include.

(function () {
  if (window.__copyInlineLoaded) return;
  window.__copyInlineLoaded = true;

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy-text], [data-copy-from], .lb-code__copy');
    if (!btn) return;

    var text = btn.getAttribute('data-copy-text');
    if (!text) {
      var sel = btn.getAttribute('data-copy-from');
      var src = null;
      if (sel) {
        src = document.querySelector(sel);
      } else if (btn.classList.contains('lb-code__copy')) {
        // Code-block buttons live inside <figure class="lb-code"> with a <pre> sibling.
        var figure = btn.closest('.lb-code');
        if (figure) src = figure.querySelector('pre code') || figure.querySelector('pre');
      }
      if (src) text = src.innerText;
    }
    if (!text) return;

    navigator.clipboard.writeText(text).then(function () {
      btn.classList.add('is-copied');
      setTimeout(function () { btn.classList.remove('is-copied'); }, 1500);
    });
  });
})();

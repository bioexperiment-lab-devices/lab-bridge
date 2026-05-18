// Sidebar collapse/expand + persistence + auto-open ancestors of active.
(function () {
  if (window.__docsSidebarLoaded) return;
  window.__docsSidebarLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var folders = document.querySelectorAll('.lb-docs-side__folder');
    folders.forEach(function (btn) {
      var key = 'docs-nav:' + btn.dataset.sectionKey;
      var saved = localStorage.getItem(key);
      var parentLi = btn.closest('.lb-docs-side__item');
      var hasActiveDescendant = parentLi && parentLi.querySelector('.is-active');
      var open = saved === 'open' || (saved === null && hasActiveDescendant);
      setOpen(btn, parentLi, open);

      btn.addEventListener('click', function (e) {
        // Allow the inner <a> click to navigate; intercept only the chev/whitespace.
        if (e.target.closest('a')) return;
        e.preventDefault();
        var nowOpen = btn.getAttribute('aria-expanded') !== 'true';
        setOpen(btn, parentLi, nowOpen);
        localStorage.setItem(key, nowOpen ? 'open' : 'closed');
      });
    });
  });

  function setOpen(btn, li, open) {
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    var chev = btn.querySelector('.lb-docs-side__chev');
    if (chev) chev.textContent = open ? '⌄' : '›';
    var children = li ? li.querySelector('.lb-docs-side__children') : null;
    if (children) children.style.display = open ? '' : 'none';
  }
})();

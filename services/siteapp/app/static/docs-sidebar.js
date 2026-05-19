// Expand/collapse nested folder rows in the docs sidebar.
//
// Each folder is an `<a class="lb-docs-side__item" data-folder>` followed by
// a sibling `<div class="lb-docs-side__children">`. We pair them via the
// shared `data-section-key` attribute, persist open/closed in localStorage,
// and auto-open ancestors of the active item so the current page is visible
// when the user lands on it.
(function () {
  if (window.__docsSidebarLoaded) return;
  window.__docsSidebarLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var folders = document.querySelectorAll('.lb-docs-side__item[data-folder]');
    folders.forEach(function (folder) {
      var key = 'docs-nav:' + folder.dataset.sectionKey;
      var children = childrenFor(folder);
      var saved = localStorage.getItem(key);
      var hasActiveDescendant = children && children.querySelector('[data-active="true"]');
      var open = saved === 'open' || (saved === null && hasActiveDescendant);
      setOpen(folder, children, open);

      folder.addEventListener('click', function (e) {
        // Holding modifier keys / middle-click / non-primary keeps default link
        // behavior (open in new tab, etc.). Plain primary clicks toggle.
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        var nowOpen = folder.dataset.folder !== 'open';
        setOpen(folder, children, nowOpen);
        localStorage.setItem(key, nowOpen ? 'open' : 'closed');
      });
    });
  });

  function childrenFor(folder) {
    var key = folder.dataset.sectionKey;
    if (!key) return null;
    return document.querySelector('.lb-docs-side__children[data-section-key="' + cssEscape(key) + '"]');
  }

  function setOpen(folder, children, open) {
    folder.dataset.folder = open ? 'open' : 'closed';
    if (children) {
      if (open) children.removeAttribute('hidden');
      else children.setAttribute('hidden', '');
    }
  }

  function cssEscape(s) {
    return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/"/g, '\\"');
  }
})();

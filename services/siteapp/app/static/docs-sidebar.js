// Expand/collapse nested folder rows in the docs sidebar.
//
// Each folder is a row containing a `<button class="lb-docs-side__toggle">`
// (the chevron) and an `<a class="lb-docs-side__item--folder">` (the label
// that navigates to the section's index page). A sibling
// `<div class="lb-docs-side__children">` holds the nested entries; we pair
// the toggle to its children via the shared `data-section-key` attribute.
// State is persisted in localStorage. Ancestors of the active item auto-open
// so the current page is visible on first load.
(function () {
  if (window.__docsSidebarLoaded) return;
  window.__docsSidebarLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var toggles = document.querySelectorAll('.lb-docs-side__toggle[data-section-key]');
    toggles.forEach(function (toggle) {
      var key = 'docs-nav:' + toggle.dataset.sectionKey;
      var children = childrenFor(toggle);
      var saved = localStorage.getItem(key);
      // Auto-open if EITHER the section's own index page is the current
      // page (sibling label inside .lb-docs-side__folder is active) OR a
      // descendant inside the children container is active.
      var folder = toggle.parentElement;
      var hasActiveOwn = !!(folder && folder.querySelector('.lb-docs-side__item[data-active="true"]'));
      var hasActiveDescendant = !!(children && children.querySelector('[data-active="true"]'));
      var open = saved === 'open' || (saved === null && (hasActiveOwn || hasActiveDescendant));
      setOpen(toggle, children, open);

      toggle.addEventListener('click', function () {
        var nowOpen = toggle.getAttribute('aria-expanded') !== 'true';
        setOpen(toggle, children, nowOpen);
        localStorage.setItem(key, nowOpen ? 'open' : 'closed');
      });

      // Clicking the section label persists 'open' before navigation so the
      // section appears expanded on the destination page even if the user had
      // previously collapsed it.
      var label = folder && folder.querySelector('.lb-docs-side__item--folder');
      if (label) {
        label.addEventListener('click', function () {
          localStorage.setItem(key, 'open');
        });
      }
    });
  });

  function childrenFor(toggle) {
    var key = toggle.dataset.sectionKey;
    if (!key) return null;
    return document.querySelector('.lb-docs-side__children[data-section-key="' + cssEscape(key) + '"]');
  }

  function setOpen(toggle, children, open) {
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.dataset.folder = open ? 'open' : 'closed';
    if (children) {
      if (open) children.removeAttribute('hidden');
      else children.setAttribute('hidden', '');
    }
  }

  function cssEscape(s) {
    return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/"/g, '\\"');
  }
})();

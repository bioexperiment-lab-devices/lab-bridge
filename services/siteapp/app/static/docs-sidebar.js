// Expand/collapse nested folder rows in the docs sidebar.
//
// Each folder is a row containing a `<button class="lb-docs-side__toggle">`
// (the chevron) and an `<a class="lb-docs-side__item--folder">` (the label
// that navigates to the section's index page). A sibling
// `<div class="lb-docs-side__children">` holds the nested entries; we pair
// the toggle to its children via the shared `data-section-key` attribute.
//
// State persistence rules:
//   * Per-section open/closed state is stored in localStorage under
//     `docs-nav:<section-key>`.
//   * When the user enters /docs/ from OUTSIDE /docs/ (or from a fresh
//     tab with no referrer), the stored state is wiped so the sidebar
//     opens collapsed. Within a continuous docs session, state persists
//     across page-to-page navigations as the user toggles sections.
//   * The section containing the active page is ALWAYS expanded on load,
//     regardless of any stored 'closed' value — direct-linked deep pages
//     must be visible in the nav so the reader can see where they are.
(function () {
  if (window.__docsSidebarLoaded) return;
  window.__docsSidebarLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    if (arrivedFromOutsideDocs()) clearStoredNavState();

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
      // Active-section auto-expand wins over a stored 'closed' so deep
      // links always reveal where the reader is in the tree.
      var open = hasActiveOwn || hasActiveDescendant || saved === 'open';
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

  // Returns true if the user landed on this /docs/ page from outside /docs/
  // (e.g., from the home page) or from a fresh tab with no referrer.
  // Same-origin docs-to-docs navigations return false, so toggling state
  // persists naturally while the reader stays within docs.
  function arrivedFromOutsideDocs() {
    var ref = document.referrer;
    if (!ref) return true;
    var docsPrefix = location.origin + '/docs/';
    return ref.indexOf(docsPrefix) !== 0;
  }

  function clearStoredNavState() {
    var prefix = 'docs-nav:';
    var keysToRemove = [];
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && k.indexOf(prefix) === 0) keysToRemove.push(k);
    }
    keysToRemove.forEach(function (k) { localStorage.removeItem(k); });
  }

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

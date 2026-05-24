// Scrollspy for the per-page TOC rail. Highlights the heading the reader
// is currently looking at and silently updates the URL hash so
// "copy URL" produces a deep link to the visible section.
//
// Anchors are taken from `data-toc-anchor` on the rail's links; matching
// heading elements (h2/h3) carry the same `id` (emitted server-side by
// markdown-it's anchors plugin). An IntersectionObserver tracks each
// heading's relationship to a narrow band at the top of the viewport.
//
// Active heading selection — when the user is deep in a section, the
// section's heading is scrolled OFF the top of the viewport, so a naive
// "topmost intersecting" check would highlight nothing. We track each
// heading's state as 'above' (scrolled past the top), 'in' (inside the
// top-of-viewport band), or 'below' (not yet reached). The active heading
// is the topmost 'in' heading; if no headings are 'in', fall back to the
// last 'above' heading in document order — i.e., the section the user is
// currently reading.
(function () {
  if (window.__docsTocLoaded) return;
  window.__docsTocLoaded = true;

  document.addEventListener('DOMContentLoaded', function () {
    var links = Array.prototype.slice.call(
      document.querySelectorAll('[data-toc-anchor]')
    );
    if (!links.length) return;

    var headingById = {};
    var idsInOrder = [];
    links.forEach(function (link) {
      var id = link.getAttribute('data-toc-anchor');
      var h = document.getElementById(id);
      if (h) {
        headingById[id] = h;
        idsInOrder.push(id);
      }
    });
    if (!idsInOrder.length) return;

    // Per-heading state: 'above' | 'in' | 'below'. Initialised from each
    // element's initial bounding rect so the very first paint shows the
    // correct active heading before the observer has fired any entries.
    var state = Object.create(null);
    idsInOrder.forEach(function (id) {
      var rect = headingById[id].getBoundingClientRect();
      // The intersection band is the top 25% of the viewport (see rootMargin
      // below). Compute initial state against that band.
      var bandBottom = window.innerHeight * 0.25;
      if (rect.top < 0) state[id] = 'above';
      else if (rect.top <= bandBottom) state[id] = 'in';
      else state[id] = 'below';
    });

    var currentActive = null;

    function setActive(id) {
      if (id === currentActive) return;
      currentActive = id;
      links.forEach(function (link) {
        if (link.getAttribute('data-toc-anchor') === id) {
          link.setAttribute('data-active', 'true');
        } else {
          link.removeAttribute('data-active');
        }
      });
      // No heading in view → leave existing hash rather than stripping it.
      if (id) {
        // replaceState (not pushState) so the back button isn't polluted
        // and Chrome doesn't auto-scroll on hash change.
        history.replaceState(null, '', '#' + id);
      }
    }

    function pickActive() {
      // Topmost heading currently in the band wins.
      for (var i = 0; i < idsInOrder.length; i++) {
        if (state[idsInOrder[i]] === 'in') return idsInOrder[i];
      }
      // No heading in the band — fall back to the last heading that has
      // scrolled past the top (the section the reader is inside).
      var lastAbove = null;
      for (var j = 0; j < idsInOrder.length; j++) {
        if (state[idsInOrder[j]] === 'above') lastAbove = idsInOrder[j];
      }
      return lastAbove;
    }

    setActive(pickActive());

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          var id = e.target.id;
          if (e.isIntersecting) {
            state[id] = 'in';
          } else {
            // boundingClientRect is provided even when not intersecting;
            // its sign tells us which side of the band the heading is on.
            state[id] = e.boundingClientRect.top < 0 ? 'above' : 'below';
          }
        });
        setActive(pickActive());
      },
      // Intersection root = top 25% of the viewport (bottom 75% shrunk
      // away by negative rootMargin). Empirically the most natural-feeling
      // activation point; matches MkDocs Material.
      { rootMargin: '0px 0px -75% 0px' }
    );

    idsInOrder.forEach(function (id) {
      observer.observe(headingById[id]);
    });
  });
})();

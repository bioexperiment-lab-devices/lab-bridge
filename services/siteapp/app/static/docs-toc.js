// Scrollspy for the per-page TOC rail. Highlights the heading the reader
// is currently looking at and silently updates the URL hash so
// "copy URL" produces a deep link to the visible section.
//
// Anchors are taken from `data-toc-anchor` on the rail's links; matching
// heading elements (h2/h3) carry the same `id` (emitted server-side by
// markdown-it's anchors plugin). An IntersectionObserver with a top-anchored
// rootMargin marks the topmost intersecting heading as active.
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

    var active = Object.create(null);
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
      if (id) {
        // replaceState (not pushState) so the back button isn't polluted
        // and Chrome doesn't auto-scroll on hash change.
        history.replaceState(null, '', '#' + id);
      }
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) active[e.target.id] = true;
          else delete active[e.target.id];
        });
        // Pick the topmost active heading in document order.
        var topId = null;
        for (var i = 0; i < idsInOrder.length; i++) {
          if (active[idsInOrder[i]]) {
            topId = idsInOrder[i];
            break;
          }
        }
        setActive(topId);
      },
      // Heading becomes active once it crosses into the top 25% of the
      // viewport — empirically the most natural-feeling threshold.
      { rootMargin: '0px 0px -75% 0px' }
    );

    idsInOrder.forEach(function (id) {
      observer.observe(headingById[id]);
    });
  });
})();

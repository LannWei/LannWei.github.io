(function () {
  "use strict";

  /* ---------- Publication filters ---------- */
  var filters = Array.prototype.slice.call(document.querySelectorAll(".filter"));
  var pubs = Array.prototype.slice.call(document.querySelectorAll(".pub"));
  var groups = Array.prototype.slice.call(document.querySelectorAll(".pub-group"));
  var empty = document.getElementById("pubs-empty");

  function matches(pub, key) {
    if (key === "all") return true;
    var tags = (pub.getAttribute("data-tags") || "").split(/\s+/);
    return tags.indexOf(key) !== -1;
  }

  filters.forEach(function (btn) {
    var key = btn.getAttribute("data-filter");
    var n = pubs.filter(function (p) { return matches(p, key); }).length;
    var c = document.createElement("span");
    c.className = "count";
    c.textContent = n;
    btn.appendChild(c);
  });

  function applyFilter(key) {
    var shown = 0;
    pubs.forEach(function (p) {
      var ok = matches(p, key);
      p.hidden = !ok;
      if (ok) shown++;
    });
    groups.forEach(function (g) {
      g.hidden = !g.querySelector(".pub:not([hidden])");
    });
    filters.forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-filter") === key));
    });
    if (empty) empty.hidden = shown !== 0;
  }

  filters.forEach(function (btn) {
    btn.addEventListener("click", function () { applyFilter(btn.getAttribute("data-filter")); });
  });

  // A link to a specific paper (e.g. from Research Highlights) must never land on a hidden item.
  function revealTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    var el = document.getElementById(id);
    if (el && el.classList.contains("pub") && el.hidden) {
      applyFilter("all");
      el.scrollIntoView();
    }
  }
  window.addEventListener("hashchange", revealTarget);
  revealTarget();

  /* ---------- Highlight the current section in the masthead ---------- */
  var navLinks = Array.prototype.slice.call(document.querySelectorAll(".masthead__menu a[href^='#']"));
  var sections = navLinks
    .map(function (a) { return document.getElementById(a.getAttribute("href").slice(1)); })
    .filter(Boolean);

  function setActive(id) {
    navLinks.forEach(function (a) {
      var on = a.getAttribute("href") === "#" + id;
      a.classList.toggle("is-active", on);
      if (on) {
        a.setAttribute("aria-current", "true");
        // Keep the active item visible in the horizontally scrolling mobile menu.
        var menu = a.parentElement;
        if (menu.scrollWidth > menu.clientWidth) {
          menu.scrollTo({ left: a.offsetLeft - menu.clientWidth / 2 + a.clientWidth / 2, behavior: "smooth" });
        }
      } else {
        a.removeAttribute("aria-current");
      }
    });
  }

  var ticking = false;
  function onScroll() {
    if (ticking || !sections.length) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      ticking = false;
      var offset = window.innerHeight * 0.3;
      var current = sections[0].id;
      for (var i = 0; i < sections.length; i++) {
        if (sections[i].getBoundingClientRect().top - offset <= 0) current = sections[i].id;
      }
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
        current = sections[sections.length - 1].id;
      }
      setActive(current);
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();
})();

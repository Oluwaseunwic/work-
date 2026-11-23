/* Job Recruitment Website - front-end behaviour | WIC Technologies */
(function () {
  "use strict";

  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- navbar: shrink on scroll + progress bar ---- */
  var nav = $("#nav"), bar = $("#scrollBar"), ticking = false;
  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    if (nav) nav.classList.toggle("scrolled", y > 12);
    if (bar) bar.style.transform = "scaleX(" + (max > 0 ? Math.min(y / max, 1) : 0) + ")";
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  onScroll();

  /* ---- mobile menu ---- */
  var burger = $("#burger"), menu = $("#menu"), backdrop = $("#backdrop");
  function setMenu(open) {
    if (!burger || !menu) return;
    menu.classList.toggle("open", open);
    backdrop.classList.toggle("show", open);
    burger.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
  }
  if (burger) {
    burger.addEventListener("click", function () { setMenu(burger.getAttribute("aria-expanded") !== "true"); });
    backdrop.addEventListener("click", function () { setMenu(false); });
    $$("a", menu).forEach(function (a) { a.addEventListener("click", function () { setMenu(false); }); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setMenu(false); });
    window.addEventListener("resize", function () { if (window.innerWidth > 860) setMenu(false); });
  }

  /* ---- reveal on scroll ---- */
  var reveals = $$(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          var el = en.target;
          el.classList.add("in");
          io.unobserve(el);
          // clear the stagger delay once revealed so hover effects respond instantly
          setTimeout(function () { el.style.setProperty("--d", "0ms"); }, 1300);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---- animated counters ---- */
  var counters = $$("[data-count]");
  function runCounter(el) {
    var target = parseInt(el.getAttribute("data-count"), 10) || 0;
    var suffix = el.getAttribute("data-suffix") || "";
    if (reduceMotion || target === 0) { el.textContent = target + suffix; return; }
    var start = null, dur = 1400;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  if (counters.length && "IntersectionObserver" in window) {
    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { runCounter(en.target); co.unobserve(en.target); }
      });
    }, { threshold: 0.6 });
    counters.forEach(function (c) { co.observe(c); });
  } else {
    counters.forEach(runCounter);
  }

  /* ---- hero rotating word ---- */
  var swap = $("#swap");
  if (swap && !reduceMotion) {
    var words = ["fits you", "pays well", "grows you", "you love"], i = 0;
    setInterval(function () {
      swap.classList.add("out");
      setTimeout(function () {
        i = (i + 1) % words.length;
        swap.textContent = words[i];
        swap.classList.remove("out");
      }, 420);
    }, 2600);
  }

  /* ---- subtle 3D tilt on job cards (desktop pointers only) ---- */
  if (!reduceMotion && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    $$(".job-card").forEach(function (card) {
      card.addEventListener("mousemove", function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5;
        var y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = "translateY(-7px) perspective(900px) rotateX(" + (-y * 4) + "deg) rotateY(" + (x * 5) + "deg)";
        card.style.transition = "transform .08s linear, box-shadow .35s, border-color .35s";
      });
      card.addEventListener("mouseleave", function () {
        card.style.transform = "";
        card.style.transition = "";
      });
    });
  }

  /* ---- toasts ---- */
  $$(".toast").forEach(function (t) {
    function close() {
      t.classList.add("leave");
      setTimeout(function () { t.remove(); }, 400);
    }
    var btn = $("button", t);
    if (btn) btn.addEventListener("click", close);
    setTimeout(close, 7000);
  });

  /* ---- file drop zones ---- */
  $$(".drop").forEach(function (zone) {
    var input = $("input[type=file]", zone), text = $(".drop-text", zone);
    if (!input) return;
    var original = text.innerHTML;
    function show() {
      if (input.files && input.files[0]) {
        var f = input.files[0];
        if (f.size > 5 * 1024 * 1024) {
          alert("That file is larger than 5 MB. Please choose a smaller CV.");
          input.value = "";
          zone.classList.remove("has-file");
          text.innerHTML = original;
          return;
        }
        zone.classList.add("has-file");
        text.innerHTML = "<b></b><small>" + Math.max(1, Math.round(f.size / 1024)) + " KB &middot; click to change</small>";
        $("b", text).textContent = f.name;
      }
    }
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function () { zone.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function () { zone.classList.remove("drag"); });
    });
  });

  /* ---- copy link buttons ---- */
  $$("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-copy"), old = btn.textContent;
      function done() { btn.textContent = "Copied!"; setTimeout(function () { btn.textContent = old; }, 1600); }
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done); else done();
    });
  });

  /* ---- stop double submits ---- */
  $$("form.form").forEach(function (form) {
    form.addEventListener("submit", function () {
      var b = $("button[type=submit]", form);
      if (b && form.checkValidity()) {
        setTimeout(function () { b.disabled = true; b.textContent = "Sending..."; }, 0);
      }
    });
  });
})();

/* q-timeline.js — The Q Collective
   Draws the "On the record" timeline from data/timeline.json.

   Put a placeholder where you want it, then load this file once per page:
       <div data-q-timeline="full"></div>    the whole timeline (timeline.html)
       <div data-q-timeline="home"></div>    what's next + latest, for the homepage
       <div data-q-timeline="strip"></div>   three compact cards, for the Hub
       <script src="q-timeline.js"></script>

   To add something to the timeline you only edit data/timeline.json.
   Dates sort themselves, and an item moves from "Coming up" to "Done"
   on its own once its date has passed. If the data file can't load,
   the placeholder quietly stays empty and nothing else on the page breaks. */
(function () {
  "use strict";

  var SRC = "data/timeline.json";
  var MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  var KIND = {
    filing:  "Public filing",
    bill:    "Our legislation",
    site:    "On this site",
    watch:   "Colorado law we're watching",
    session: "At the Capitol"
  };

  var CSS = [
    ".qt{--n:#122848;--n2:#1B3A6B;--g:#B8962E;--gl:#D4AF50;--gp:#F5EDD4;--bd:#E0D5BE;--ow:#F9F6F0;--tx:#1a1a1a;--tl:#4a4a4a;--tm:#5a5a5a;font-family:'Public Sans',-apple-system,BlinkMacSystemFont,sans-serif;color:var(--tx)}",
    ".qt a{color:var(--n2)}",
    ".qt-filters{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 30px}",
    ".qt-chip{font:inherit;font-size:14px;font-weight:600;background:#fff;color:var(--n);border:1px solid var(--bd);border-radius:20px;padding:7px 15px;cursor:pointer}",
    ".qt-chip[aria-pressed=true]{background:var(--n);color:#fff;border-color:var(--n)}",
    ".qt-group{font-family:'Source Serif 4',Georgia,serif;font-size:22px;font-weight:600;color:var(--n);margin:8px 0 18px}",
    ".qt-list{list-style:none;margin:0 0 34px;padding:0;position:relative}",
    ".qt-list:before{content:'';position:absolute;left:9px;top:8px;bottom:8px;width:2px;background:var(--bd)}",
    ".qt-item{position:relative;padding:0 0 26px 40px}",
    ".qt-item:last-child{padding-bottom:4px}",
    ".qt-dot{position:absolute;left:2px;top:5px;width:16px;height:16px;border-radius:50%;background:var(--n2);border:3px solid var(--ow);box-shadow:0 0 0 1px var(--n2)}",
    ".qt-item.up .qt-dot{background:var(--ow);box-shadow:0 0 0 2px var(--g)}",
    ".qt-item.feat .qt-dot{background:var(--g);box-shadow:0 0 0 2px var(--g)}",
    ".qt-meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;font-size:14px;color:var(--tm);margin-bottom:4px}",
    ".qt-date{font-weight:700;color:var(--n)}",
    ".qt-kind{font-size:12.5px;font-weight:600;color:#7a5f12;background:var(--gp);border-radius:4px;padding:2px 8px}",
    ".qt-soon{font-size:12.5px;font-weight:600;color:var(--n);border:1px solid var(--g);border-radius:4px;padding:1px 7px}",
    ".qt-title{font-family:'Source Serif 4',Georgia,serif;font-size:20px;font-weight:600;line-height:1.3;color:var(--n);margin:0 0 6px}",
    ".qt-sum{font-size:16px;line-height:1.72;color:var(--tl);margin:0;max-width:68ch}",
    ".qt-card{background:#fff;border:1px solid var(--bd);border-radius:8px;padding:20px 22px}",
    ".qt-item.feat .qt-card{border-left:4px solid var(--g)}",
    ".qt-item:target .qt-card,.qt-item.hl .qt-card{box-shadow:0 0 0 3px rgba(184,150,46,.35)}",
    ".qt-pts{margin:14px 0 0;padding:0 0 0 20px;max-width:66ch}",
    ".qt-pts li{font-size:15.5px;line-height:1.65;color:var(--tl);margin:0 0 7px}",
    ".qt-why{margin:14px 0 0;padding:12px 16px;background:var(--ow);border-radius:6px;font-size:15px;line-height:1.65;color:var(--tl);max-width:66ch}",
    ".qt-why b{color:var(--n)}",
    ".qt-links{display:flex;flex-wrap:wrap;gap:8px 18px;margin:14px 0 0}",
    ".qt-links a{font-size:15px;font-weight:600;text-decoration:none;border-bottom:1px solid var(--g)}",
    ".qt-today{position:relative;padding:0 0 26px 40px;font-size:14px;font-weight:700;color:var(--g)}",
    ".qt-today:before{content:'';position:absolute;left:0;top:10px;width:20px;height:2px;background:var(--g)}",
    ".qt-empty{font-size:15px;color:var(--tm);padding-left:40px;margin:-10px 0 30px}",
    /* homepage */
    ".qt-home{display:grid;grid-template-columns:1fr 1.45fr;gap:34px;margin-top:8px}",
    ".qt-col h3{font-family:'Source Serif 4',Georgia,serif;font-size:19px;font-weight:600;color:var(--n);margin:0 0 16px}",
    ".qt-home .qt-item{padding-bottom:20px}",
    ".qt-home .qt-title{font-size:18px}",
    ".qt-home .qt-sum{font-size:15px}",
    ".qt-more{display:inline-block;margin-top:6px;font-weight:600;font-size:15px;text-decoration:none;border-bottom:1px solid var(--g)}",
    /* hub strip */
    ".qt-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}",
    ".qt-sc{display:block;background:#fff;border:1px solid var(--bd);border-top:3px solid var(--n2);border-radius:6px;padding:14px 16px;text-decoration:none;color:inherit}",
    ".qt-sc.up{border-top-color:var(--g)}",
    ".qt-sc.feat{border-top-color:var(--g);background:#FCFAF3}",
    ".qt-sc:hover{border-color:var(--g)}",
    ".qt-sc .qt-meta{font-size:13px;margin-bottom:3px}",
    ".qt-sc .qt-title{font-size:16.5px;margin:0}",
    ".qt-strip-foot{margin:10px 0 0;font-size:14.5px}",
    "@media (max-width:820px){.qt-home{grid-template-columns:1fr;gap:10px}.qt-strip{grid-template-columns:1fr}}",
    "@media (max-width:520px){.qt-card{padding:16px}.qt-title{font-size:18px}.qt-sum{font-size:15.5px}}"
  ].join("");

  function injectCSS() {
    if (document.getElementById("qt-css")) return;
    var s = document.createElement("style");
    s.id = "qt-css";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function safeHref(h) {
    h = String(h || "");
    if (/^https:\/\//i.test(h) || /^[a-z0-9_\-./#?=&]+$/i.test(h)) return h;
    return "#";
  }
  function isExternal(h) { return /^https?:\/\//i.test(h); }

  function parse(d) {
    var p = String(d || "").split("-");
    return new Date(+p[0], (+p[1] || 1) - 1, +p[2] || 1);
  }
  function fmt(e) {
    var d = parse(e.date);
    if (e.precision === "month") return MONTHS[d.getMonth()] + " " + d.getFullYear();
    return MONTHS[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear();
  }
  function today() { var n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); }
  function daysUntil(e) { return Math.round((parse(e.date) - today()) / 86400000); }
  function untilLabel(e) {
    var n = daysUntil(e);
    if (n === 0) return "Today";
    if (n === 1) return "Tomorrow";
    if (n < 60) return "In " + n + " days";
    return null;
  }

  function split(entries) {
    var t = today(), up = [], done = [];
    entries.forEach(function (e) { (parse(e.date) >= t ? up : done).push(e); });
    up.sort(function (a, b) { return parse(a.date) - parse(b.date); });
    done.sort(function (a, b) { return parse(b.date) - parse(a.date); });
    return { up: up, done: done };
  }

  function linksHTML(e) {
    if (!e.links || !e.links.length) return "";
    return '<div class="qt-links">' + e.links.map(function (l) {
      var h = safeHref(l.href);
      var ext = isExternal(h) || /\.pdf$/i.test(h) ? ' target="_blank" rel="noopener"' : "";
      return '<a href="' + esc(h) + '"' + ext + ">" + esc(l.label) + (isExternal(h) ? " &#8599;" : "") + "</a>";
    }).join("") + "</div>";
  }

  function metaHTML(e, isUp) {
    var soon = isUp ? untilLabel(e) : null;
    return '<div class="qt-meta"><span class="qt-date">' + esc(fmt(e)) + "</span>" +
      '<span class="qt-kind">' + esc(KIND[e.kind] || "Update") + "</span>" +
      (soon ? '<span class="qt-soon">' + esc(soon) + "</span>" : "") + "</div>";
  }

  function itemHTML(e, isUp, full) {
    var cls = "qt-item" + (isUp ? " up" : "") + (e.featured ? " feat" : "");
    var body = '<p class="qt-sum">' + esc(e.summary) + "</p>";
    if (full) {
      if (e.points && e.points.length) {
        body += '<ul class="qt-pts">' + e.points.map(function (p) { return "<li>" + esc(p) + "</li>"; }).join("") + "</ul>";
      }
      if (e.why) body += '<p class="qt-why"><b>Why it matters.</b> ' + esc(e.why) + "</p>";
      body += linksHTML(e);
      return '<li class="' + cls + '" id="' + esc(e.id) + '"><span class="qt-dot"></span><div class="qt-card">' +
        metaHTML(e, isUp) + '<h3 class="qt-title">' + esc(e.title) + "</h3>" + body + "</div></li>";
    }
    return '<li class="' + cls + '"><span class="qt-dot"></span>' + metaHTML(e, isUp) +
      '<h4 class="qt-title"><a href="timeline.html#' + esc(e.id) + '" style="color:inherit;text-decoration:none">' + esc(e.title) + "</a></h4>" + body + "</li>";
  }

  /* ---------- full page ---------- */
  function renderFull(el, entries) {
    var kinds = ["all"];
    entries.forEach(function (e) { if (kinds.indexOf(e.kind) < 0) kinds.push(e.kind); });
    var current = "all";

    function draw() {
      var list = current === "all" ? entries : entries.filter(function (e) { return e.kind === current; });
      var s = split(list);
      var html = '<div class="qt-filters" role="group" aria-label="Filter the timeline">' + kinds.map(function (k) {
        return '<button type="button" class="qt-chip" data-k="' + esc(k) + '" aria-pressed="' + (k === current) + '">' +
          esc(k === "all" ? "Everything" : KIND[k] || k) + "</button>";
      }).join("") + "</div>";

      html += '<h2 class="qt-group">Coming up</h2><ol class="qt-list">';
      // Full page reads as one line through time: furthest-out date at the top,
      // flowing down to "Today", then back through what is done.
      html += s.up.length ? s.up.slice().reverse().map(function (e) { return itemHTML(e, true, true); }).join("")
                          : '<li class="qt-empty">Nothing scheduled in this category yet.</li>';
      html += '<li class="qt-today">Today, ' + esc(fmt({ date: isoToday() })) + "</li></ol>";

      html += '<h2 class="qt-group">Done</h2><ol class="qt-list">';
      html += s.done.length ? s.done.map(function (e) { return itemHTML(e, false, true); }).join("")
                            : '<li class="qt-empty">Nothing here yet.</li>';
      html += "</ol>";
      el.innerHTML = html;

      Array.prototype.forEach.call(el.querySelectorAll(".qt-chip"), function (b) {
        b.addEventListener("click", function () { current = b.getAttribute("data-k"); draw(); });
      });
    }
    draw();

    // Jump to a shared link like timeline.html#admt-comment
    var id = (location.hash || "").slice(1);
    if (id) {
      var t = document.getElementById(id);
      if (t) { t.classList.add("hl"); setTimeout(function () { t.scrollIntoView({ behavior: "smooth", block: "start" }); }, 60); }
    }
  }

  function isoToday() {
    var t = today();
    return t.getFullYear() + "-" + (t.getMonth() + 1) + "-" + t.getDate();
  }

  /* ---------- homepage ---------- */
  function renderHome(el, entries) {
    var s = split(entries);
    var next = s.up.slice(0, 2);
    var latest = s.done.slice(0, 3);
    var html = '<div class="qt-home">';
    html += '<div class="qt-col"><h3>Coming up</h3><ol class="qt-list">' +
      (next.length ? next.map(function (e) { return itemHTML(e, true, false); }).join("")
                   : '<li class="qt-empty">Nothing on the calendar right now.</li>') + "</ol></div>";
    html += '<div class="qt-col"><h3>What we just did</h3><ol class="qt-list">' +
      latest.map(function (e) { return itemHTML(e, false, false); }).join("") + "</ol>" +
      '<a class="qt-more" href="timeline.html">See the full timeline &rarr;</a></div>';
    html += "</div>";
    el.innerHTML = html;
  }

  /* ---------- hub strip ---------- */
  function renderStrip(el, entries) {
    var s = split(entries);
    var pick = s.up.slice(0, 1).concat(s.done.slice(0, 3)).slice(0, 3);
    if (!pick.length) return;
    el.innerHTML = '<div class="qt-strip">' + pick.map(function (e) {
      var isUp = s.up.indexOf(e) > -1;
      return '<a class="qt-sc' + (isUp ? " up" : "") + (e.featured ? " feat" : "") + '" href="timeline.html#' + esc(e.id) + '">' +
        metaHTML(e, isUp) + '<div class="qt-title">' + esc(e.title) + "</div></a>";
    }).join("") + '</div><p class="qt-strip-foot"><a href="timeline.html">Everything we have done, and what is next &rarr;</a></p>';
  }

  function run() {
    var spots = document.querySelectorAll("[data-q-timeline]");
    if (!spots.length) return;
    injectCSS();
    fetch(SRC + "?v=" + Date.now(), { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("timeline " + r.status); return r.json(); })
      .then(function (d) {
        var entries = (d && d.entries || []).filter(function (e) { return e && e.date && e.title; });
        Array.prototype.forEach.call(spots, function (el) {
          el.classList.add("qt");
          var mode = el.getAttribute("data-q-timeline");
          if (mode === "full") renderFull(el, entries);
          else if (mode === "strip") renderStrip(el, entries);
          else renderHome(el, entries);
          var wrap = el.closest("[data-q-timeline-wrap]");
          if (wrap) wrap.style.display = "";
        });
      })
      .catch(function () { /* stay quiet; the rest of the page is unaffected */ });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
})();

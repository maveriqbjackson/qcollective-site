/* q-status.js — The Q Collective
   Tells visitors how fresh the scores are.

   Loaded site-wide by site-chrome.js. It only does anything on the pages
   that show Q Scores (PAGES below).

   Normal week:   a quiet line, "Scores last updated October 4, 2026."
                  (the Hub and the homepage already print their own line,
                  so this adds one only where there isn't one)
   Glitch week:   a gold-edged notice under the top bar:
                  "Scores last updated September 27, 2026. We hit a mild
                  glitch on this week's refresh and we're on it."

   A glitch means either:
     - the engine's last run failed  (data/health.json has "ok": false), or
     - the last good update is more than STALE_DAYS old (the engine never ran).
   The notice clears by itself after the next good run. Nothing to switch off.

   To change the wording, edit MSG below and re-upload this one file. */
(function () {
  "use strict";
  if (window.__qStatusLoaded) return;
  window.__qStatusLoaded = 1;

  var PAGES = ["", "index.html", "hub.html", "legislator.html", "bill.html"];
  var STALE_DAYS = 9;   // the engine runs every Sunday; 9 days means a week was missed
  var MSG = "We hit a mild glitch on this week’s refresh and we’re on it. " +
            "Everything here is from our last completed update, and nothing is lost.";

  var here = (location.pathname.split("/").pop() || "").toLowerCase();
  if (PAGES.indexOf(here) === -1) return;

  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  // "September 27, 2026 at 3:33 PM MDT" -> Date (or null)
  function parseStamp(s) {
    var m = /^([A-Za-z]+ \d{1,2}, \d{4})(?: at (\d{1,2}):(\d{2}) ([AP]M))?/.exec(String(s || ""));
    if (!m) return null;
    var d = new Date(m[1]);
    if (isNaN(d.getTime())) return null;
    if (m[2]) {
      var h = parseInt(m[2], 10) % 12 + (m[4] === "PM" ? 12 : 0);
      d.setHours(h, parseInt(m[3], 10));
    }
    return d;
  }
  function dateOnly(s) { return String(s || "").replace(/\s+at\s+.*$/, ""); }
  function get(url) {
    return fetch(url + "?v=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function css() {
    if (document.getElementById("q-status-css")) return;
    var s = document.createElement("style");
    s.id = "q-status-css";
    s.textContent =
      ".q-status-note{background:#FBF6E6;border-bottom:1px solid #E0D5BE;border-left:5px solid #B8962E;" +
      "color:#122848;font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:14.5px;line-height:1.55;" +
      "padding:12px 20px}" +
      ".q-status-note .in{max-width:1100px;margin:0 auto}" +
      ".q-status-note b{font-weight:700}" +
      ".q-status-note a{color:#122848;font-weight:600;text-decoration:underline;white-space:nowrap}" +
      ".q-status-line{max-width:1100px;margin:0 auto;padding:18px 20px 6px;text-align:center;" +
      "font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:12.5px;color:#5a5a5a}" +
      ".q-status-line a{color:#8a6d1a;text-decoration:none}.q-status-line a:hover{text-decoration:underline}" +
      "@media print{.q-status-note,.q-status-line{display:none}}";
    document.head.appendChild(s);
  }

  function render(health, index) {
    health = health || {};
    index = index || {};
    var lastGood = health.last_success ||
                   (health.ok !== false ? health.last_run : "") ||
                   index.updated || "";
    var when = parseStamp(lastGood);
    var days = when ? (Date.now() - when.getTime()) / 86400000 : null;
    var glitch = health.ok === false || (days != null && days > STALE_DAYS);
    var shown = dateOnly(lastGood);
    if (!shown) return;

    window.qStatus = { lastUpdated: shown, glitch: glitch };
    css();

    if (glitch && !document.getElementById("q-status-note")) {
      var n = document.createElement("div");
      n.className = "q-status-note";
      n.id = "q-status-note";
      n.setAttribute("role", "status");
      n.innerHTML = '<div class="in"><b>Scores last updated ' + esc(shown) + ".</b> " + esc(MSG) +
                    ' <a href="audit.html">System status &rarr;</a></div>';
      var top = document.getElementById("q-chrome-top");
      if (top && top.parentNode) top.parentNode.insertBefore(n, top.nextSibling);
      else document.body.insertBefore(n, document.body.firstChild);
    }

    // Quiet line on score pages that don't already print the date themselves.
    var hasOwn = document.getElementById("hubUpdated") || document.getElementById("q-stamp");
    if (!hasOwn && !document.getElementById("q-status-line")) {
      var l = document.createElement("div");
      l.className = "q-status-line";
      l.id = "q-status-line";
      l.innerHTML = "Scores last updated " + esc(shown) +
                    ' &middot; <a href="audit.html">system status &rarr;</a>';
      var foot = document.getElementById("q-chrome-footer");
      if (foot && foot.parentNode) foot.parentNode.insertBefore(l, foot);
      else document.body.appendChild(l);
    }
  }

  function go() {
    Promise.all([get("data/health.json"), get("data/index.json")])
      .then(function (r) { render(r[0], r[1]); })
      .catch(function () {});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
  else go();
})();

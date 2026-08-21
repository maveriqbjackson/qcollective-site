/* profile-corrections.js — The Q Collective
   Publishes any correction made to this legislator's profile, on the profile itself.
   Reads data/corrections.json and injects into <div id="qcCorrections">.

   Principle: a correction records WHAT was changed and WHEN. It never discloses
   private information an official shared in the course of reporting the error. */
(function () {
  "use strict";
  function qp(k) { return new URLSearchParams(location.search).get(k); }
  var state = qp("state") || "CO", id = qp("id");
  if (!id) return;
  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  var css =
    ".qcx-wrap{background:#fff;border:1px solid #E0D5BE;border-left:4px solid #B8962E;border-radius:10px;padding:18px 20px;margin-top:14px}" +
    ".qcx-h{display:flex;align-items:center;gap:9px;margin-bottom:4px;flex-wrap:wrap}" +
    ".qcx-t{font-family:'Playfair Display',serif;font-size:16px;font-weight:700;color:#122848}" +
    ".qcx-badge{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;background:#fbe9e7;color:#a33f2b;border-radius:11px;padding:3px 9px}" +
    ".qcx-item{padding:11px 0;border-top:1px solid #f0ece2}.qcx-item:first-of-type{border-top:none;padding-top:6px}" +
    ".qcx-meta{font-family:'DM Mono',monospace;font-size:10.5px;letter-spacing:.5px;text-transform:uppercase;color:#5a5a5a;margin-bottom:5px}" +
    ".qcx-sum{font-size:14px;color:#2a2a2a;line-height:1.6}" +
    ".qcx-src{font-family:'DM Mono',monospace;font-size:11px;color:#5a5a5a;margin-top:5px}" +
    ".qcx-foot{font-size:12px;color:#5a5a5a;margin-top:12px;padding-top:10px;border-top:1px solid #f0ece2;line-height:1.55}" +
    ".qcx-foot a{color:#B8962E}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  fetch("data/corrections.json?v=" + Date.now())
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (D) {
      if (!D) return;
      var mine = (D.corrections || []).filter(function (c) {
        return String(c.id) === String(id) && (!c.state || c.state === state);
      });
      if (!mine.length) return;
      mine.sort(function (a, b) { return String(b.date).localeCompare(String(a.date)); });

      var items = mine.map(function (c) {
        return '<div class="qcx-item">' +
          '<div class="qcx-meta">' + esc(c.date || "") + (c.scope ? " &middot; " + esc(c.scope) : "") + "</div>" +
          '<div class="qcx-sum">' + esc(c.summary || "") + "</div>" +
          (c.affects ? '<div class="qcx-src">' + esc(c.affects) + "</div>" : "") +
          (c.source ? '<div class="qcx-src">Source: ' + esc(c.source) + "</div>" : "") +
          "</div>";
      }).join("");

      var tries = 0, poll = setInterval(function () {
        var host = document.getElementById("qcCorrections");
        if (!host) { if (++tries > 80) clearInterval(poll); return; }
        clearInterval(poll);
        host.innerHTML =
          '<div class="qcx-wrap">' +
            '<div class="qcx-h"><span class="qcx-t">Corrections</span>' +
            '<span class="qcx-badge">' + mine.length + (mine.length === 1 ? " correction" : " corrections") + "</span></div>" +
            items +
            '<div class="qcx-foot">We publish every correction we make. Corrections record what changed and when &mdash; they never disclose private information shared by an official. Every correction also appears in the <a href="audit.html">public audit log</a>.</div>' +
          "</div>";
      }, 150);
    })
    .catch(function () {});
})();

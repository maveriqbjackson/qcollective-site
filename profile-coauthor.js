/* profile-coauthor.js — The Q Collective
   "Who they work with" panel for a legislator profile page.
   Self-contained: reads ?state & ?id from the URL, pulls the scored roster and the bills
   file, builds this legislator's co-authorship circle, and injects it into <div id="qcCoauthor">.
   Taps/clicks on any collaborator open that person's profile. Updates weekly with the data. */
(function () {
  "use strict";
  function qp(k) { return new URLSearchParams(location.search).get(k); }
  var state = qp("state") || "CO", id = qp("id");
  if (!id) return;
  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function pcolor(p) { return p === "D" ? "#2E5BE6" : p === "R" ? "#BF0A30" : "#3FA45C"; }
  function last(s) { return String(s || "").split(" ").slice(-1)[0]; }

  var css =
    ".qc-sub{font-size:13px;color:#5a5a5a;margin:0 0 14px;line-height:1.55}" +
    ".qc-grid{display:grid;grid-template-columns:360px 1fr;gap:22px;align-items:start}" +
    "@media(max-width:680px){.qc-grid{grid-template-columns:1fr}}" +
    ".qc-web{background:#0e1f3a;border-radius:12px;overflow:hidden}.qc-web svg{width:100%;height:auto;display:block}" +
    ".qc-node{cursor:pointer}.qc-node-lab{cursor:pointer}" +
    ".qc-xa{background:#fbf7ea;border:1px solid #ecdca6;border-left:4px solid #B8962E;border-radius:9px;padding:12px 15px;margin-bottom:14px;font-size:13px;color:#5a4a1a}.qc-xa b{color:#7a5f12}" +
    ".qc-h{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#5a5a5a;margin:0 0 6px}" +
    ".qc-co{display:flex;align-items:center;gap:10px;padding:10px 8px;border-radius:8px;cursor:pointer;transition:.1s}.qc-co:hover{background:#f7f4ec}" +
    ".qc-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}" +
    ".qc-cn{font-size:14px;color:#122848;font-weight:500}" +
    ".qc-meta{margin-left:auto;font-family:'DM Mono',monospace;font-size:11.5px;color:#5a5a5a;white-space:nowrap}.qc-meta b{color:#122848}" +
    ".qc-empty{font-size:14px;color:#5a5a5a}";
  var stEl = document.createElement("style"); stEl.textContent = css; document.head.appendChild(stEl);

  Promise.all([
    fetch("data/" + state + ".json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("data/" + state + "_bills.json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (res) {
    var D = res[0], B = res[1]; if (!D || !B) return;
    var L = D.legislators || [], byid = {}; L.forEach(function (l) { byid[String(l.id)] = l; });
    var me = String(id); if (!byid[me]) return;
    var bo = B.bills || {}, bills = Array.isArray(bo) ? bo : Object.keys(bo).map(function (k) { return bo[k]; });
    var partners = {}, primc = {}, pair = {};
    bills.forEach(function (bl) {
      var sp = (bl && bl.sponsors) || [], prim = [];
      sp.forEach(function (s) { if (s && s.primary) { var i = String(s.people_id); if (byid[i] && prim.indexOf(i) < 0) prim.push(i); } });
      prim.sort();
      prim.forEach(function (i) { primc[i] = (primc[i] || 0) + 1; });
      for (var a = 0; a < prim.length; a++) for (var b = a + 1; b < prim.length; b++) { var x = prim[a], y = prim[b], k = x + "|" + y; pair[k] = (pair[k] || 0) + 1; var dx = partners[x] || (partners[x] = {}); dx[y] = (dx[y] || 0) + 1; var dy = partners[y] || (partners[y] = {}); dy[x] = (dy[x] || 0) + 1; }
    });
    var o = byid[me], pt = partners[me] || {};
    var tops = Object.keys(pt).filter(function (q) { return byid[q]; }).map(function (q) { return { id: q, n: byid[q].name, p: byid[q].party, w: pt[q], s: byid[q].score }; }).sort(function (a, b) { return b.w - a.w; }).slice(0, 8);
    var xparty = tops.filter(function (t) { return t.p !== o.party; });
    var ego = [me].concat(tops.map(function (t) { return t.id; }));
    var eedges = []; for (var a = 0; a < ego.length; a++) for (var b = a + 1; b < ego.length; b++) { var k = [ego[a], ego[b]].sort().join("|"); if (pair[k]) eedges.push({ a: ego[a], b: ego[b], w: pair[k] }); }
    var maxW = Math.max.apply(null, eedges.map(function (e) { return e.w; }).concat([1]));

    function go(i) { if (i === me) return; window.location.href = "legislator.html?state=" + encodeURIComponent(state) + "&id=" + encodeURIComponent(i); }
    function nd(i) { var l = byid[i]; return { id: i, n: l.name, p: l.party, s: l.score, b: primc[i] || 0 }; }

    function render(host) {
      var head = '<p class="section-label" style="margin-top:44px">Who they work with</p><h2 class="section-title" style="margin-bottom:6px">' + esc(last(o.name)) + "\u2019s working circle</h2><div class=\"section-divider\"></div>";
      if (!tops.length) { host.innerHTML = head + '<p class="qc-empty">No co-authorship recorded this session yet.</p>'; return; }
      var nodes = ego.map(nd), byn = {}; nodes.forEach(function (n) { byn[n.id] = n; });
      var W = 360, H = 320, cx = W / 2, cy = H / 2, R = 118;
      var others = nodes.filter(function (n) { return n.id !== me; });
      byn[me].x = cx; byn[me].y = cy;
      others.forEach(function (n, i) { var an = -Math.PI / 2 + i / others.length * 6.2831853; n.x = cx + Math.cos(an) * R; n.y = cy + Math.sin(an) * R; });
      function rr(n) { return n.id === me ? 15 : (6 + Math.sqrt(n.b / 50) * 8); }
      function curve(s, t) { var dx = t.x - s.x, dy = t.y - s.y, ln = Math.sqrt(dx * dx + dy * dy) || 1, off = ln * 0.12, mx = (s.x + t.x) / 2 + (-dy / ln) * off, my = (s.y + t.y) / 2 + (dx / ln) * off; return "M" + s.x.toFixed(1) + " " + s.y.toFixed(1) + " Q" + mx.toFixed(1) + " " + my.toFixed(1) + " " + t.x.toFixed(1) + " " + t.y.toFixed(1); }
      var svg = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg">';
      eedges.forEach(function (e) { var s = byn[e.a], t = byn[e.b]; if (!s || !t) return; var xp = s.p !== t.p, ctr = (e.a === me || e.b === me); svg += '<path d="' + curve(s, t) + '" fill="none" stroke="' + (xp ? "#B8962E" : "#9fbbe6") + '" stroke-opacity="' + (ctr ? (xp ? 0.7 : 0.4) : (xp ? 0.5 : 0.18)) + '" stroke-width="' + (0.8 + e.w / maxW * 3).toFixed(2) + '"/>'; });
      nodes.forEach(function (n) { var ch = n.s >= 80; svg += '<circle class="qc-node" data-id="' + esc(n.id) + '" cx="' + n.x.toFixed(1) + '" cy="' + n.y.toFixed(1) + '" r="' + rr(n).toFixed(1) + '" fill="' + pcolor(n.p) + '" stroke="' + (n.id === me ? "#fff" : ch ? "#D4AF50" : "rgba(255,255,255,.35)") + '" stroke-width="' + (n.id === me ? 3 : ch ? 2.4 : 1) + '"/>'; });
      nodes.forEach(function (n) { svg += '<text class="qc-node-lab" data-id="' + esc(n.id) + '" x="' + n.x.toFixed(1) + '" y="' + (n.y - rr(n) - 4).toFixed(1) + '" text-anchor="middle" font-family="DM Mono,monospace" font-size="' + (n.id === me ? 11 : 9.5) + '" fill="#fff"' + (n.id === me ? ' font-weight="700"' : "") + ">" + esc(last(n.n)) + "</text>"; });
      svg += "</svg>";
      var colist = tops.map(function (t) { return '<div class="qc-co" data-id="' + esc(t.id) + '"><span class="qc-dot" style="background:' + pcolor(t.p) + '"></span><span class="qc-cn">' + esc(t.n) + '</span><span class="qc-meta"><b>' + t.w + "</b> bills \u00b7 Q " + (t.s == null ? "\u2014" : t.s) + "</span></div>"; }).join("");
      var xa = xparty.length ? "Reaches across the aisle most with <b>" + esc(xparty[0].n) + " (" + xparty[0].p + ")</b> \u2014 " + xparty[0].w + " bills together." : "Works mostly within their own party this session.";
      host.innerHTML = head +
        '<p class="qc-sub">Drawn from who they co-author bills with \u2014 the same public data behind the Hub\u2019s web. Tap any name to open their profile.</p>' +
        '<div class="qc-grid"><div class="qc-web">' + svg + '</div><div class="qc-side"><div class="qc-xa">' + xa + '</div><h4 class="qc-h">Closest collaborators (' + primc[me] + ' bills led \u00b7 ' + Object.keys(pt).length + ' co-authors)</h4>' + colist + "</div></div>";
      host.querySelectorAll(".qc-co,.qc-node,.qc-node-lab").forEach(function (el) { el.addEventListener("click", function () { go(el.dataset.id); }); });
    }

    var tries = 0, poll = setInterval(function () { var host = document.getElementById("qcCoauthor"); if (!host) { if (++tries > 80) clearInterval(poll); return; } clearInterval(poll); render(host); }, 150);
  }).catch(function () {});
})();

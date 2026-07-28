/* bill-sponsors.js — The Q Collective
   "Who's behind this bill" accountability readout for a bill page.
   Additive: injects a party-balance + scores + champions + sponsor-network panel into
   <div id="qcBillSponsors"> (above the existing sponsor grid), and adds a Q-score badge to
   each existing sponsor card. Reads ?state & ?number from the URL. Everything else on the
   bill page is untouched. Updates weekly with the data. */
(function () {
  "use strict";
  function qp(k) { return new URLSearchParams(location.search).get(k); }
  var state = qp("state") || "CO", number = qp("number");
  if (!number) return;
  function norm(s) { return String(s || "").toUpperCase().replace(/[^A-Z0-9]/g, ""); }
  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function pcolor(p) { return p === "D" ? "#2E5BE6" : p === "R" ? "#BF0A30" : "#3FA45C"; }
  function last(s) { return String(s || "").split(" ").slice(-1)[0]; }

  var css =
    ".qcb-wrap{margin:2px 0 22px}" +
    ".qcb-balance{display:flex;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}" +
    ".qcb-bar{flex:1;min-width:160px;height:14px;border-radius:8px;overflow:hidden;display:flex;border:1px solid #e6e0d2}.qcb-bar span{display:block;height:100%}" +
    ".qcb-tag{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:.5px;text-transform:uppercase;padding:5px 11px;border-radius:12px;font-weight:600}.qcb-tag.bip{background:#eaf3ec;color:#2c6e49}.qcb-tag.solo{background:#f2efe8;color:#5a5a5a}" +
    ".qcb-chips{display:grid;grid-template-columns:repeat(auto-fit,minmax(84px,1fr));gap:10px;margin-bottom:16px}" +
    ".qcb-chip{background:#f9f7f1;border:1px solid #E0D5BE;border-radius:9px;padding:10px 8px;text-align:center}.qcb-chip .v{font-family:'Playfair Display',serif;font-size:21px;font-weight:800;color:#122848;line-height:1}.qcb-chip .k{font-family:'DM Mono',monospace;font-size:8.5px;letter-spacing:.5px;text-transform:uppercase;color:#5a5a5a;margin-top:5px}" +
    ".qcb-netrow{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}" +
    ".qcb-net{background:#0e1f3a;border-radius:12px;overflow:hidden;width:300px;max-width:100%}.qcb-net svg{width:100%;height:auto;display:block}" +
    ".qcb-netnote{flex:1;min-width:180px;font-size:12.5px;color:#4a4a4a;line-height:1.55}.qcb-netnote b{color:#122848}" +
    ".sp-q{display:inline-flex;align-items:center;gap:4px;margin-left:8px;font-family:'DM Mono',monospace;font-size:11px;color:#5a5a5a;background:#f2efe8;border-radius:10px;padding:2px 8px;white-space:nowrap}.sp-q b{color:#122848}.sp-q.champ{background:#fbf1cf;color:#8a6d12}.sp-q .st{color:#B8962E}";
  var stEl = document.createElement("style"); stEl.textContent = css; document.head.appendChild(stEl);

  Promise.all([
    fetch("data/" + state + ".json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
    fetch("data/" + state + "_bills.json?v=" + Date.now()).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
  ]).then(function (res) {
    var CO = res[0], BB = res[1]; if (!CO || !BB) return;
    var byid = {}; (CO.legislators || []).forEach(function (l) { byid[String(l.id)] = l; });
    var bo = BB.bills || {}, bills = Array.isArray(bo) ? bo : Object.keys(bo).map(function (k) { return bo[k]; });
    var want = norm(number), bill = bills.filter(function (b) { return norm(b.number) === want; })[0];
    if (!bill) return;

    // global co-authorship (primary sponsors) for the mini network
    var pair = {};
    bills.forEach(function (b) { var prim = []; (b.sponsors || []).forEach(function (s) { if (s && s.primary) { var i = String(s.people_id); if (byid[i] && prim.indexOf(i) < 0) prim.push(i); } }); prim.sort(); for (var a = 0; a < prim.length; a++) for (var c = a + 1; c < prim.length; c++) { var k = prim[a] + "|" + prim[c]; pair[k] = (pair[k] || 0) + 1; } });

    var sp = bill.sponsors || [];
    var primIds = [], seen = {};
    sp.forEach(function (s) { if (s && s.primary) { var i = String(s.people_id); if (byid[i] && !seen[i]) { seen[i] = 1; primIds.push(i); } } });
    if (!primIds.length) sp.forEach(function (s) { var i = String(s.people_id); if (byid[i] && !seen[i]) { seen[i] = 1; primIds.push(i); } });
    var prim = primIds.map(function (i) { var l = byid[i]; return { id: i, n: l.name, p: l.party, s: l.score, champ: (l.score || 0) >= 80 }; });
    if (!prim.length) return;

    var scored = prim.filter(function (r) { return typeof r.s === "number"; });
    var D = prim.filter(function (r) { return r.p === "D"; }).length, R = prim.filter(function (r) { return r.p === "R"; }).length, Ot = prim.length - D - R;
    var avg = scored.length ? Math.round(scored.reduce(function (a, b) { return a + b.s; }, 0) / scored.length) : "\u2014";
    var champs = prim.filter(function (r) { return r.champ; }).length;
    var cosp = Math.max(0, sp.length - prim.length);
    var bip = [D, R, Ot].filter(function (x) { return x > 0; }).length > 1;

    function render(host) {
      var tot = prim.length;
      var segs = "";
      if (D) segs += '<span style="width:' + (D / tot * 100) + '%;background:#2E5BE6"></span>';
      if (R) segs += '<span style="width:' + (R / tot * 100) + '%;background:#BF0A30"></span>';
      if (Ot) segs += '<span style="width:' + (Ot / tot * 100) + '%;background:#3FA45C"></span>';
      var tag = bip ? '<span class="qcb-tag bip">Bipartisan &middot; ' + D + " D, " + R + " R" + (Ot ? ", " + Ot + " I" : "") + "</span>" : '<span class="qcb-tag solo">Single-party &middot; ' + (D ? D + " D" : R ? R + " R" : Ot + " I") + "</span>";
      var chips = [[tot, prim === scored ? "Sponsors" : "Prime sponsors"], [avg, "Avg Q Score"], [champs, "Champions"], [cosp, "Co-sponsors"]].map(function (c) { return '<div class="qcb-chip"><div class="v">' + c[0] + '</div><div class="k">' + c[1] + "</div></div>"; }).join("");

      var net = "", note = "";
      if (prim.length >= 3 && prim.length <= 12) {
        var edges = []; for (var a = 0; a < primIds.length; a++) for (var b = a + 1; b < primIds.length; b++) { var k = [primIds[a], primIds[b]].sort().join("|"); if (pair[k]) edges.push({ a: primIds[a], b: primIds[b], w: pair[k] }); }
        var W = 300, H = 280, cx = W / 2, cy = H / 2, Rr = 96, n = prim.length, pos = {};
        prim.forEach(function (r, i) { var ang = -Math.PI / 2 + i / n * 6.2831853; r.x = cx + Math.cos(ang) * Rr; r.y = cy + Math.sin(ang) * Rr; pos[r.id] = r; });
        var maxW = Math.max.apply(null, edges.map(function (e) { return e.w; }).concat([1]));
        var svg = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg">';
        edges.forEach(function (e) { var s = pos[e.a], t = pos[e.b]; if (!s || !t) return; var xp = s.p !== t.p; svg += '<line x1="' + s.x.toFixed(1) + '" y1="' + s.y.toFixed(1) + '" x2="' + t.x.toFixed(1) + '" y2="' + t.y.toFixed(1) + '" stroke="' + (xp ? "#B8962E" : "#9fbbe6") + '" stroke-opacity="' + (xp ? 0.7 : 0.4) + '" stroke-width="' + (0.8 + e.w / maxW * 3).toFixed(2) + '"/>'; });
        prim.forEach(function (r) { svg += '<circle cx="' + r.x.toFixed(1) + '" cy="' + r.y.toFixed(1) + '" r="9" fill="' + pcolor(r.p) + '" stroke="' + (r.champ ? "#D4AF50" : "rgba(255,255,255,.4)") + '" stroke-width="' + (r.champ ? 2.4 : 1) + '"/>'; });
        prim.forEach(function (r) { var out = r.y < cy; svg += '<text x="' + r.x.toFixed(1) + '" y="' + (r.y + (out ? -14 : 20)).toFixed(1) + '" text-anchor="middle" font-family="DM Mono,monospace" font-size="9.5" fill="#fff">' + esc(last(r.n)) + "</text>"; });
        svg += "</svg>";
        var maxPairs = n * (n - 1) / 2, dens = edges.length / maxPairs;
        var msg = dens >= 0.7 ? "These sponsors <b>regularly work together</b> &mdash; a real coalition, not names assembled for one vote." : dens >= 0.3 ? "A <b>partial coalition</b> &mdash; several of these sponsors co-author often; others signed on for this bill." : "Mostly an <b>assembled coalition</b> &mdash; these sponsors don&rsquo;t usually co-author, so this bill brought them together.";
        net = '<div class="qcb-net">' + svg + "</div>";
        note = '<div class="qcb-netnote"><b>How the sponsors connect.</b> ' + msg + " Gold lines cross the aisle.</div>";
      }

      host.innerHTML = '<div class="qcb-wrap"><div class="qcb-balance"><div class="qcb-bar">' + segs + "</div>" + tag + '</div><div class="qcb-chips">' + chips + "</div>" + (net ? '<div class="qcb-netrow">' + net + note + "</div>" : "") + "</div>";
    }

    function badgeCards() {
      var cards = document.querySelectorAll("#b-body .sponsor[href]");
      cards.forEach(function (a) {
        if (a.querySelector(".sp-q")) return;
        var m = /[?&]id=([^&]+)/.exec(a.getAttribute("href") || ""); if (!m) return;
        var l = byid[decodeURIComponent(m[1])]; if (!l || typeof l.score !== "number") return;
        var champ = l.score >= 80;
        var b = document.createElement("span"); b.className = "sp-q" + (champ ? " champ" : "");
        b.innerHTML = "Q <b>" + l.score + "</b>" + (champ ? ' <span class="st">&#9733;</span>' : "");
        a.appendChild(b);
      });
    }

    var tries = 0, poll = setInterval(function () {
      var host = document.getElementById("qcBillSponsors");
      if (!host) { if (++tries > 80) clearInterval(poll); return; }
      clearInterval(poll); render(host); badgeCards();
    }, 150);
  }).catch(function () {});
})();

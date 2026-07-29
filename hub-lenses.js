/* hub-lenses.js — The Q Collective
   Multi-lens Accountability Hub: List (default, untouched) + Briefing + the co-authorship Web.
   Reads live globals CUR (legislators) and BILLSOBJ (bills) — auto-updates with the weekly run.
   Shareable: the current lens (and, on the Web, the pinned official) live in the URL, so any view
   can be shared as a deep link (?lens=web&pin=<id>) that reopens exactly as shared. */
(function () {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function legs() { return (window.CUR && window.CUR.legislators) || []; }
  function stateCode() { return (window.CUR && window.CUR.state) || (byId("hubState") && byId("hubState").value) || "CO"; }
  function num(v) { return typeof v === "number" ? v : (v == null ? null : (isNaN(+v) ? null : +v)); }
  function last(s) { return String(s || "").split(" ").slice(-1)[0]; }
  function pcolor(p) { return p === "D" ? "#2E5BE6" : p === "R" ? "#BF0A30" : "#3FA45C"; }
  function plabel(p) { return p === "D" ? "Democrat" : p === "R" ? "Republican" : p === "I" ? "Independent" : p === "U" ? "Unaffiliated" : p ? "Third party" : "\u2014"; }

  var current = "list", webPin = null;

  /* ---------- deep-link / share ---------- */
  function qs() { var o = {}; location.search.replace(/^\?/, "").split("&").forEach(function (kv) { if (!kv) return; var p = kv.split("="); o[decodeURIComponent(p[0])] = decodeURIComponent(p[1] || ""); }); return o; }
  function buildUrl(abs) { var p = qs(); p.lens = current; if (current === "web" && webPin) p.pin = webPin; else delete p.pin; var parts = Object.keys(p).filter(function (k) { return p[k] !== "" && p[k] != null; }).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(p[k]); }); return (abs ? location.origin : "") + location.pathname + (parts.length ? "?" + parts.join("&") : ""); }
  function syncUrl() { try { history.replaceState(null, "", buildUrl(false)); } catch (e) {} }
  function doShare() {
    var u = buildUrl(true);
    var label = current === "web" && webPin ? "this pinned view" : current === "web" ? "the co-authorship web" : current === "briefing" ? "the briefing" : "the Hub";
    if (navigator.share) { navigator.share({ title: "The Q Collective", url: u }).catch(function () {}); return; }
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(u).then(function () { toast("Link to " + label + " copied"); }).catch(function () { toast(u); }); }
    else { toast(u); }
  }
  var _tt;
  function toast(html) { var t = byId("qToast"); if (!t) { t = document.createElement("div"); t.id = "qToast"; document.body.appendChild(t); } t.innerHTML = html; t.className = "on"; clearTimeout(_tt); _tt = setTimeout(function () { t.className = ""; }, 3000); }

  /* ---------- styles ---------- */
  var css = "" +
    ".lens-tabs{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0 22px;padding:12px 14px;background:#fff;border:1px solid #E0D5BE;border-radius:12px;box-shadow:0 3px 12px rgba(18,40,72,.06)}" +
    ".lens-lead{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#B8962E;font-weight:600;margin-right:2px}" +
    ".lens-tab{font-family:'DM Sans',sans-serif;font-size:13.5px;font-weight:600;padding:9px 17px;border-radius:9px;border:1.5px solid #d8d2c4;background:#fff;color:#122848;cursor:pointer;transition:.12s}" +
    ".lens-tab:hover{border-color:#B8962E;background:#faf6ea}.lens-tab.active{background:#122848;color:#fff;border-color:#122848}" +
    ".lens-share{margin-left:auto;font-family:'DM Mono',monospace;font-size:11px;letter-spacing:.5px;text-transform:uppercase;color:#5a5a5a;background:none;border:1px solid #d8d2c4;border-radius:8px;padding:8px 12px;cursor:pointer}" +
    ".lens-share:hover{border-color:#B8962E;color:#122848}" +
    "@keyframes lensPulse{0%{box-shadow:0 0 0 0 rgba(184,150,46,.55)}70%{box-shadow:0 0 0 14px rgba(184,150,46,0)}100%{box-shadow:0 0 0 0 rgba(184,150,46,0)}}" +
    ".lens-tabs.pulse{animation:lensPulse 1.7s ease-out 2}" +
    ".lz-load{font-family:'DM Mono',monospace;font-size:13px;color:#5a5a5a;padding:30px 0;text-align:center}" +
    "#qToast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(18px);background:#0a1730;color:#fff;border:1px solid #B8962E;border-radius:9px;padding:11px 16px;font-family:'DM Mono',monospace;font-size:12px;opacity:0;transition:.2s;z-index:9999;max-width:90vw;pointer-events:none}#qToast.on{opacity:1;transform:translateX(-50%) translateY(0)}" +
    /* briefing */
    ".brief-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:20px}" +
    ".brief-stat{background:#fff;border:1px solid #E0D5BE;border-radius:10px;padding:14px 16px}.brief-stat .v{font-family:'Playfair Display',serif;font-size:27px;font-weight:800;color:#122848;line-height:1}.brief-stat .k{font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:1px;text-transform:uppercase;color:#5a5a5a;margin-top:6px}" +
    ".brief-read{background:#fff;border:1px solid #E0D5BE;border-left:4px solid #B8962E;border-radius:10px;padding:20px 22px}.brief-read p{font-size:15.5px;color:#2a2a2a;line-height:1.75;margin:0 0 12px}.brief-read p:last-child{margin:0}.brief-read b{color:#122848}" +
    /* web lens */
    ".qw-stage{background:#0e1f3a;border-radius:16px 16px 0 0;overflow:hidden;border:1px solid #0a1730;border-bottom:none}" +
    ".qw-head{display:flex;justify-content:space-between;align-items:baseline;padding:14px 18px 2px;color:#fff}.qw-head .t{font-family:'Playfair Display',serif;font-size:14px}.qw-head .r{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,.45)}" +
    ".qw-canvas{position:relative}.qw-canvas svg{width:100%;height:auto;display:block;touch-action:none;cursor:grab}.qw-searchbar{background:#0e1f3a;padding:2px 16px 12px}.qw-search{width:100%;max-width:340px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.22);border-radius:8px;color:#fff;font-family:'DM Sans',sans-serif;font-size:16px;padding:10px 12px;-webkit-appearance:none}.qw-search::placeholder{color:rgba(255,255,255,.5)}.qw-search:focus{outline:none;border-color:#B8962E;background:rgba(255,255,255,.12)}" +
    ".qw-edge{fill:none;stroke:#a9c5ec;stroke-opacity:.22}.qw-edge.xp{stroke:#B8962E;stroke-opacity:.55}" +
    ".qw-node{cursor:pointer}.qw-dim{opacity:.05!important}.qw-nlab{font-family:'DM Mono',monospace;font-size:9px;fill:#fff;pointer-events:none}.qw-nlab.me{font-size:11px;font-weight:600}" +
    ".qw-zoom{position:absolute;right:12px;bottom:12px;display:flex;flex-direction:column;gap:5px;z-index:6}.qw-zoom button{width:32px;height:32px;border-radius:8px;border:1px solid rgba(255,255,255,.25);background:rgba(10,23,48,.72);color:#fff;font-size:16px;line-height:1;cursor:pointer;font-family:'DM Mono',monospace}.qw-zoom button:hover{background:rgba(184,150,46,.9);color:#122848}" +
    ".qw-panel{background:#fff;border:1px solid #0a1730;border-top:1px solid #24406e;border-radius:0 0 16px 16px;overflow:hidden}" +
    ".qw-empty{padding:24px 22px;font-family:'DM Mono',monospace;font-size:12.5px;color:#5a5a5a;text-align:center}" +
    ".qw-body{display:none;grid-template-columns:1fr 1fr}.qw-body.on{display:grid}.qw-l{padding:18px 22px;border-right:1px solid #eee}.qw-r{padding:18px 22px}" +
    ".qw-tag{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:1px;text-transform:uppercase;margin-bottom:8px;color:#5a5a5a}.qw-tag .pin{background:#122848;color:#fff;padding:2px 8px;border-radius:10px}.qw-tag .x{cursor:pointer;border-bottom:1px dotted #5a5a5a;margin-left:6px}" +
    ".qw-name{font-family:'Playfair Display',serif;font-size:22px;font-weight:800;color:#122848;line-height:1.1}.qw-meta{font-family:'DM Mono',monospace;font-size:11.5px;color:#5a5a5a;margin:4px 0 12px}" +
    ".qw-score{display:flex;align-items:baseline;gap:10px}.qw-score .v{font-family:'Playfair Display',serif;font-size:38px;font-weight:900;color:#122848;line-height:1}.qw-score .lab{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:.5px;text-transform:uppercase;padding:3px 9px;border-radius:12px;background:#f2efe8;color:#5a5a5a}.qw-score .lab.champ{background:#fbf1cf;color:#8a6d12}" +
    ".qw-comp{margin-top:12px}.qw-comp .row{display:grid;grid-template-columns:68px 1fr 28px;align-items:center;gap:8px;margin-bottom:5px}.qw-comp .k{font-family:'DM Mono',monospace;font-size:10px;color:#5a5a5a}.qw-comp .bar{height:7px;background:#eee;border-radius:4px;overflow:hidden}.qw-comp .bar span{display:block;height:100%;background:#122848}.qw-comp .n{font-family:'DM Mono',monospace;font-size:11px;color:#122848;text-align:right}" +
    ".qw-acts{display:flex;gap:8px;margin-top:15px;flex-wrap:wrap}.qw-act{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:.5px;text-transform:uppercase;padding:9px 13px;border-radius:6px;cursor:pointer;border:1px solid #122848;background:#fff;color:#122848}.qw-act:hover{background:#122848;color:#fff}.qw-act.gold{background:#B8962E;border-color:#B8962E;color:#122848}.qw-act.gold:hover{background:#D4AF50}.qw-act.star.on{background:#fbf1cf;border-color:#B8962E;color:#8a6d12}" +
    ".qw-r h4{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#5a5a5a;margin-bottom:8px}.qw-co{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-top:1px solid #f0f0f0;cursor:pointer}.qw-co:first-of-type{border-top:none}.qw-co:hover .co-n{color:#B8962E;text-decoration:underline}.qw-co .co-n{font-size:13px;color:#122848}.qw-co .co-w{font-family:'DM Mono',monospace;font-size:11px;color:#5a5a5a}" +
    ".qw-note{background:#fff;border:1px solid #E0D5BE;border-left:3px solid #2E5BE6;border-radius:8px;padding:12px 16px;margin:16px 0;font-size:12.5px;color:#4a4a4a}.qw-note b{color:#122848}" +
    ".qw-key{background:#fff;border:1px solid #E0D5BE;border-radius:12px;padding:14px 18px}.qw-key h5{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:#5a5a5a;margin-bottom:10px}.qw-kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 20px}.qw-ki{display:flex;align-items:center;gap:10px;font-size:12.5px;color:#4a4a4a}.qw-ki b{color:#122848}@media(max-width:560px){.qw-body.on{grid-template-columns:1fr}.qw-l{border-right:none;border-bottom:1px solid #eee}}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  /* ---------- switcher ---------- */
  var TABS = [["list", "List"], ["briefing", "Briefing"], ["web", "Who works with whom"]];
  var listOnly = ["viewToggle", "hubParty", "hubSearch", "tagBar"];
  var normal = ["officesZone", "hubLeaders", "mySaved", "legSection", "billSection"];
  function setLens(name) {
    current = name;
    if (name !== "web") webPin = null;
    var tabs = byId("lensTabs");
    if (tabs) [].forEach.call(tabs.querySelectorAll(".lens-tab"), function (b) { b.classList.toggle("active", b.dataset.lens === name); });
    var la = byId("lensArea");
    if (name === "list") {
      if (la) la.style.display = "none";
      listOnly.forEach(function (id) { var e = byId(id); if (e) e.style.display = ""; });
      if (window.renderAll) window.renderAll();
    } else {
      normal.forEach(function (id) { var e = byId(id); if (e) e.style.display = "none"; });
      listOnly.forEach(function (id) { var e = byId(id); if (e) e.style.display = "none"; });
      if (la) { la.style.display = "block"; renderLens(name, la); }
    }
    syncUrl();
  }
  function renderLens(name, la) {
    if (!legs().length) { la.innerHTML = '<p class="lz-load">Loading the data&hellip;</p>'; return; }
    if (name === "briefing") return renderBriefing(la);
    if (name === "web") return renderWeb(la);
  }

  /* ---------- Briefing ---------- */
  function renderBriefing(la) {
    var L = legs(), n = L.length;
    var scored = L.filter(function (l) { return num(l.score) != null; });
    var avg = Math.round(scored.reduce(function (a, b) { return a + b.score; }, 0) / (scored.length || 1));
    var champs = scored.filter(function (l) { return l.score >= 80; }).length;
    var D = L.filter(function (l) { return l.party === "D"; }).length, R = L.filter(function (l) { return l.party === "R"; }).length, other = n - D - R;
    var house = L.filter(function (l) { return /House/.test(l.chamber || ""); }).length, sen = n - house;
    var comps = [["pillar", "Pillar alignment"], ["attendance", "Attendance"], ["impact", "Citizen impact"], ["sponsorship", "Sponsorship"]];
    var cavg = comps.map(function (c) { var v = L.map(function (l) { return num(l[c[0]]); }).filter(function (x) { return x != null; }); return { name: c[1], v: v.length ? Math.round(v.reduce(function (a, b) { return a + b; }, 0) / v.length) : null }; }).filter(function (c) { return c.v != null; });
    var best = cavg.slice().sort(function (a, b) { return b.v - a.v; })[0], weak = cavg.slice().sort(function (a, b) { return a.v - b.v; })[0];
    var srt = scored.slice().sort(function (a, b) { return b.score - a.score; }), top = srt[0], low = srt[srt.length - 1];
    var stName = (window.CUR && window.CUR.state_name) || "Colorado";
    var chips = [[n, "Scored"], [avg, "Avg score"], [champs, "Champions 80+"], [D + " / " + R + (other ? " / " + other : ""), "D / R" + (other ? " / other" : "")], [house + " / " + sen, "House / Senate"]].map(function (c) { return '<div class="brief-stat"><div class="v">' + esc(c[0]) + '</div><div class="k">' + esc(c[1]) + '</div></div>'; }).join("");
    var p1 = "<b>" + esc(stName) + "'s legislature</b> averages <b>" + avg + " out of 100</b> across " + n + " scored lawmakers. " + (champs ? "<b>" + champs + "</b> clear the 80-point Champion line" : "No lawmaker currently clears the 80-point Champion line") + ".";
    var p2 = best && weak ? "The chamber's strongest muscle is <b>" + esc(best.name) + "</b> (avg " + best.v + "); its weakest link is <b>" + esc(weak.name) + "</b> (avg " + weak.v + ")." : "";
    var p3 = top && low ? "<b>" + esc(top.name) + "</b> leads at <b>" + top.score + "</b>" + (top.label ? " (" + esc(top.label) + ")" : "") + "; <b>" + esc(low.name) + "</b> sits lowest at <b>" + low.score + "</b>." : "";
    la.innerHTML = '<div class="brief-cards">' + chips + '</div><div class="brief-read"><p>' + p1 + "</p>" + (p2 ? "<p>" + p2 + "</p>" : "") + (p3 ? "<p>" + p3 + "</p>" : "") + "<p>Every figure is drawn live from the same public data behind the scores.</p></div>";
  }

  /* ---------- saved reps (My Reps) ---------- */
  function getReps() { try { return JSON.parse(localStorage.getItem("qc_myreps") || "[]"); } catch (e) { return []; } }
  function isStarred(id) { return getReps().some(function (r) { return String(r.id) === String(id); }); }
  function toggleStar(nd) {
    var a = getReps(), i = -1; for (var j = 0; j < a.length; j++) if (String(a[j].id) === String(nd.id)) { i = j; break; }
    var saved = i >= 0;
    if (saved) a.splice(i, 1); else a.push({ id: nd.id, name: nd.n, chamber: nd.c === "H" ? "State House" : "State Senate", district: nd.d });
    try { localStorage.setItem("qc_myreps", JSON.stringify(a)); } catch (e) {}
    if (window.renderMyReps) window.renderMyReps();
    return !saved;
  }

  /* ---------- Web lens ---------- */
  var NETCACHE = null;
  function buildNetwork() {
    if (NETCACHE) return NETCACHE;
    var L = legs(), byId2 = {}; L.forEach(function (l) { byId2[String(l.id)] = l; });
    var bo = (window.BILLSOBJ && window.BILLSOBJ.bills) || {};
    var bills = Array.isArray(bo) ? bo : Object.keys(bo).map(function (k) { return bo[k]; });
    var pair = {}, primc = {}, partners = {};
    bills.forEach(function (bl) {
      var sp = (bl && bl.sponsors) || [], prim = [];
      sp.forEach(function (s) { if (s && s.primary) { var id = String(s.people_id); if (byId2[id] && prim.indexOf(id) < 0) prim.push(id); } });
      prim.sort();
      prim.forEach(function (id) { primc[id] = (primc[id] || 0) + 1; });
      for (var i = 0; i < prim.length; i++) for (var j = i + 1; j < prim.length; j++) { var a = prim[i], b = prim[j], k = a + "|" + b; pair[k] = (pair[k] || 0) + 1; (partners[a] = partners[a] || {})[b] = (partners[a][b] || 0) + 1; (partners[b] = partners[b] || {})[a] = (partners[b][a] || 0) + 1; }
    });
    var adj = {}; Object.keys(pair).forEach(function (k) { var pp = k.split("|"), w = pair[k]; (adj[pp[0]] = adj[pp[0]] || []).push([w, pp[1]]); (adj[pp[1]] = adj[pp[1]] || []).push([w, pp[0]]); });
    var keep = {}; Object.keys(adj).forEach(function (id) { adj[id].sort(function (a, b) { return b[0] - a[0]; }).slice(0, 3).forEach(function (x) { keep[[id, x[1]].sort().join("|")] = pair[[id, x[1]].sort().join("|")]; }); });
    var edges = Object.keys(keep).map(function (k) { var pp = k.split("|"); return { a: pp[0], b: pp[1], w: keep[k] }; });
    var nodes = L.map(function (l) { var id = String(l.id), pt = partners[id] || {}; var tops = Object.keys(pt).map(function (q) { return [byId2[q] ? byId2[q].name : q, q, pt[q]]; }).sort(function (a, b) { return b[2] - a[2]; }).slice(0, 6); return { id: id, n: l.name, p: l.party, c: /House/.test(l.chamber || "") ? "H" : "S", d: l.district, s: l.score, lab: l.label, b: primc[id] || 0, k: Object.keys(pt).length, pi: num(l.pillar), at: num(l.attendance), im: num(l.impact), sp: num(l.sponsorship), top: tops }; });
    NETCACHE = { nodes: nodes, edges: edges }; return NETCACHE;
  }

  function renderWeb(la) {
    la.innerHTML =
      '<div class="qw-stage"><div class="qw-head"><span class="t">' + esc((window.CUR && window.CUR.state_name) || "Colorado") + ' General Assembly &middot; co-authorship</span><span class="r">tap or hover to pin &middot; pinch or scroll to zoom</span></div><div class="qw-searchbar"><input class="qw-search" id="qwSearch" list="qwNames" placeholder="Find your legislator…" autocomplete="off"><datalist id="qwNames"></datalist></div>' +
      '<div class="qw-canvas"><div id="qwWeb"></div><div class="qw-zoom" id="qwZoom"><button data-z="in" title="zoom in">+</button><button data-z="out" title="zoom out">&minus;</button><button data-z="reset" title="reset">&#8635;</button></div></div></div>' +
      '<div class="qw-panel"><div class="qw-empty" id="qwEmpty">Hover a lawmaker to preview &mdash; click to pin their details here.</div>' +
      '<div class="qw-body" id="qwBody"><div class="qw-l"><div class="qw-tag" id="qwTag"></div><div class="qw-name" id="qwName"></div><div class="qw-meta" id="qwMeta"></div><div class="qw-score"><span class="v" id="qwScore"></span><span class="lab" id="qwLab"></span></div><div class="qw-comp" id="qwComp"></div><div class="qw-acts"><button class="qw-act star" id="qwStar">&#9734; Save</button><button class="qw-act gold" id="qwProf">Open full profile &rarr;</button></div></div>' +
      '<div class="qw-r"><h4 id="qwCoHead">Works most with</h4><div id="qwCo"></div></div></div></div>' +
      '<div class="qw-note"><b>Why it\u2019s laid out this way:</b> no one is placed by party. Position is set entirely by who they co-author bills with &mdash; write together, pull together. The clusters form on their own, so a dot among the other color genuinely works across the aisle.</div>' +
      '<div class="qw-key"><h5>How to read it</h5><div class="qw-kg" id="qwKey"></div></div>';

    var NET = buildNetwork();
    var W = 760, H = 520, cx = W / 2, cy = H / 2, CAP = 90, code = stateCode();
    var byId3 = {}; NET.nodes.forEach(function (n) { byId3[n.id] = n; });
    var maxW = Math.max.apply(null, NET.edges.map(function (e) { return e.w; }).concat([1]));
    function rad(n) { return 4.5 + Math.sqrt(Math.min(n.b, CAP) / CAP) * 11.5; }
    NET.nodes.forEach(function (n, i) { var a = i / NET.nodes.length * 6.2831853; n.x = cx + Math.cos(a) * 175; n.y = cy + Math.sin(a) * 150; n.vx = 0; n.vy = 0; });
    var E = NET.edges.map(function (e) { return { a: e.a, b: e.b, s: byId3[e.a], t: byId3[e.b], w: e.w, xp: byId3[e.a] && byId3[e.b] && byId3[e.a].p !== byId3[e.b].p }; }).filter(function (e) { return e.s && e.t; });
    for (var it = 0; it < 460; it++) {
      var k = 1 - it / 560;
      for (var i2 = 0; i2 < NET.nodes.length; i2++) { var A = NET.nodes[i2]; for (var j2 = i2 + 1; j2 < NET.nodes.length; j2++) { var B = NET.nodes[j2]; var dx = A.x - B.x, dy = A.y - B.y, d2 = dx * dx + dy * dy || 0.01, d = Math.sqrt(d2), rp = 3400 / d2, ux = dx / d, uy = dy / d; A.vx += ux * rp; A.vy += uy * rp; B.vx -= ux * rp; B.vy -= uy * rp; } A.vx += (cx - A.x) * 0.008; A.vy += (cy - A.y) * 0.008; }
      E.forEach(function (e) { var dx = e.t.x - e.s.x, dy = e.t.y - e.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, tg = 64 - e.w / maxW * 30, f = (d - tg) * 0.014 * (0.4 + e.w / maxW), ux = dx / d, uy = dy / d; e.s.vx += ux * f; e.s.vy += uy * f; e.t.vx -= ux * f; e.t.vy -= uy * f; });
      NET.nodes.forEach(function (n) { n.x += n.vx * 0.5 * k; n.y += n.vy * 0.5 * k; n.vx *= 0.8; n.vy *= 0.8; n.x = Math.max(20, Math.min(W - 20, n.x)); n.y = Math.max(20, Math.min(H - 20, n.y)); });
    }
    var nbrs = {}; NET.nodes.forEach(function (n) { nbrs[n.id] = {}; nbrs[n.id][n.id] = 1; }); E.forEach(function (e) { nbrs[e.a][e.b] = 1; nbrs[e.b][e.a] = 1; });
    function curve(e) { var x1 = e.s.x, y1 = e.s.y, x2 = e.t.x, y2 = e.t.y, dx = x2 - x1, dy = y2 - y1, ln = Math.sqrt(dx * dx + dy * dy) || 1, off = ln * 0.14, mx = (x1 + x2) / 2 + (-dy / ln) * off, my = (y1 + y2) / 2 + (dx / ln) * off; return "M" + x1.toFixed(1) + " " + y1.toFixed(1) + " Q" + mx.toFixed(1) + " " + my.toFixed(1) + " " + x2.toFixed(1) + " " + y2.toFixed(1); }
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg"><g id="qwvp">';
    E.slice().sort(function (a, b) { return (a.xp ? 1 : 0) - (b.xp ? 1 : 0); }).forEach(function (e) { s += '<path class="qw-edge' + (e.xp ? " xp" : "") + '" data-a="' + e.a + '" data-b="' + e.b + '" d="' + curve(e) + '" stroke-width="' + (0.9 + e.w / maxW * 2.2).toFixed(2) + '"/>'; });
    NET.nodes.forEach(function (n) { var ch = n.s >= 80; s += '<circle class="qw-node" data-id="' + n.id + '" cx="' + n.x.toFixed(1) + '" cy="' + n.y.toFixed(1) + '" r="' + rad(n).toFixed(1) + '" fill="' + pcolor(n.p) + '" stroke="' + (ch ? "#D4AF50" : "rgba(255,255,255,.28)") + '" stroke-width="' + (ch ? 2.6 : 1) + '"/>'; });
    s += '<g id="qwlabs"></g><g id="qwzlabs" style="display:none"></g></g></svg>';
    byId("qwWeb").innerHTML = s;

    // key
    function gd(r, f, ring) { return '<svg width="40" height="30" viewBox="0 0 40 30"><circle cx="20" cy="15" r="' + r + '" fill="' + f + '" stroke="' + (ring ? "#B8962E" : "rgba(0,0,0,.12)") + '" stroke-width="' + (ring ? 2.2 : 1) + '"/></svg>'; }
    byId("qwKey").innerHTML = [
      ['<svg width="70" height="30" viewBox="0 0 70 30"><circle cx="11" cy="15" r="4" fill="#9aa7bd"/><circle cx="32" cy="15" r="8" fill="#9aa7bd"/><circle cx="56" cy="15" r="12" fill="#9aa7bd"/></svg>', "<b>Dot size = bills they led</b>"],
      [gd(10, "#2E5BE6"), "<b>American blue = Democrat</b>"], [gd(10, "#BF0A30"), "<b>American red = Republican</b>"],
      [gd(10, "#3FA45C"), "<b>Colorado green = independent</b>"], [gd(9, "#2E5BE6", true), "<b>Gold ring = Champion (80+)</b>"],
      ['<svg width="70" height="16" viewBox="0 0 70 16"><path d="M4 8 Q35 4 66 8" fill="none" stroke="#7ba0d6" stroke-width="2.4"/></svg>', "<b>Line = co-authored together</b>"],
      ['<svg width="70" height="16" viewBox="0 0 70 16"><path d="M4 8 Q35 2 66 8" fill="none" stroke="#B8962E" stroke-width="2.4"/></svg>', "<b>Gold = crosses party</b>"]
    ].map(function (r) { return '<div class="qw-ki"><span>' + r[0] + "</span><span>" + r[1] + "</span></div>"; }).join("");

    var svg = byId("qwWeb").querySelector("svg"), circles = svg.querySelectorAll(".qw-node"), paths = svg.querySelectorAll(".qw-edge"), labs = svg.querySelector("#qwlabs"), zlabs = svg.querySelector("#qwzlabs");
    var vp = svg.querySelector("#qwvp"), zmode = -1, vpS = 1, vpX = 0, vpY = 0;
    function applyVp() { vp.setAttribute("transform", "translate(" + vpX.toFixed(1) + "," + vpY.toFixed(1) + ") scale(" + vpS.toFixed(3) + ")"); }
    function svgPt(x, y) { var p = svg.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(svg.getScreenCTM().inverse()); }
    function zLabels() { var m = vpS >= 2.6 ? 2 : vpS >= 1.5 ? 1 : 0; if (m === 0) { if (zmode !== 0) { zlabs.style.display = "none"; zlabs.innerHTML = ""; zmode = 0; } return; } if (m !== zmode) { zlabs.innerHTML = NET.nodes.map(function (n) { var t = m === 2 ? last(n.n) + " \u00b7 " + n.s : last(n.n); return '<text x="' + n.x.toFixed(1) + '" y="' + (n.y - rad(n) - 3).toFixed(1) + '" text-anchor="middle" fill="#fff" stroke="#0e1f3a" stroke-width="0.6" paint-order="stroke">' + esc(t) + "</text>"; }).join(""); zlabs.style.display = ""; zmode = m; } zlabs.setAttribute("font-size", (10 / vpS).toFixed(2)); zlabs.setAttribute("font-family", "DM Mono,monospace"); }
    function zoomAt(px, py, f) { var ns = Math.max(1, Math.min(4, vpS * f)), wx = (px - vpX) / vpS, wy = (py - vpY) / vpS; vpS = ns; vpX = px - wx * vpS; vpY = py - wy * vpS; if (vpS <= 1) { vpS = 1; vpX = 0; vpY = 0; } applyVp(); zLabels(); }
    svg.addEventListener("wheel", function (e) { e.preventDefault(); var p = svgPt(e.clientX, e.clientY); zoomAt(p.x, p.y, e.deltaY < 0 ? 1.15 : 1 / 1.15); }, { passive: false });
    var drag = false, lx, ly;
    svg.addEventListener("mousedown", function (e) { if (e.target.closest(".qw-node")) return; drag = true; lx = e.clientX; ly = e.clientY; svg.style.cursor = "grabbing"; });
    window.addEventListener("mousemove", function (e) { if (!drag) return; var a = svgPt(lx, ly), b = svgPt(e.clientX, e.clientY); vpX += b.x - a.x; vpY += b.y - a.y; lx = e.clientX; ly = e.clientY; applyVp(); });
    window.addEventListener("mouseup", function () { if (drag) { drag = false; svg.style.cursor = "grab"; } });
    byId("qwZoom").addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; var r = svg.getBoundingClientRect(), c = svgPt(r.left + r.width / 2, r.top + r.height / 2); if (b.dataset.z === "in") zoomAt(c.x, c.y, 1.3); else if (b.dataset.z === "out") zoomAt(c.x, c.y, 1 / 1.3); else { vpS = 1; vpX = 0; vpY = 0; applyVp(); zLabels(); } });
    var tPan=false,tPinch=false,tTapId=null,tLX=0,tLY=0,tD0=0,tS0=1,tMX=0,tMY=0,tMoved=0;
    function tDist(t){var dx=t[0].clientX-t[1].clientX,dy=t[0].clientY-t[1].clientY;return Math.sqrt(dx*dx+dy*dy);}
    svg.addEventListener("touchstart",function(e){if(e.touches.length===2){tPinch=true;tPan=false;tTapId=null;tD0=tDist(e.touches);tS0=vpS;var m=svgPt((e.touches[0].clientX+e.touches[1].clientX)/2,(e.touches[0].clientY+e.touches[1].clientY)/2);tMX=m.x;tMY=m.y;return;}var t=e.touches[0],el=document.elementFromPoint(t.clientX,t.clientY),nd=el&&el.closest?el.closest(".qw-node"):null;if(nd){tTapId=nd.dataset.id;tMoved=0;tLX=t.clientX;tLY=t.clientY;}else{tPan=true;tLX=t.clientX;tLY=t.clientY;}},{passive:false});
    svg.addEventListener("touchmove",function(e){if(tPinch&&e.touches.length===2){e.preventDefault();var d=tDist(e.touches),ns=Math.max(1,Math.min(4,tS0*(d/(tD0||1)))),wx=(tMX-vpX)/vpS,wy=(tMY-vpY)/vpS;vpS=ns;vpX=tMX-wx*vpS;vpY=tMY-wy*vpS;if(vpS<=1){vpS=1;vpX=0;vpY=0;}applyVp();zLabels();return;}var t=e.touches[0];if(!t)return;if(tTapId){tMoved+=Math.abs(t.clientX-tLX)+Math.abs(t.clientY-tLY);tLX=t.clientX;tLY=t.clientY;}else if(tPan){e.preventDefault();var a=svgPt(tLX,tLY),b=svgPt(t.clientX,t.clientY);vpX+=b.x-a.x;vpY+=b.y-a.y;tLX=t.clientX;tLY=t.clientY;applyVp();}},{passive:false});
    svg.addEventListener("touchend",function(e){if(tTapId&&tMoved<12){e.preventDefault();pin(tTapId);}if(!e.touches.length){tPan=false;tPinch=false;tTapId=null;}},{passive:false});

    var state = { pinned: null };
    function highlight(id) { var nb = nbrs[id]; circles.forEach(function (x) { x.classList.toggle("qw-dim", !nb[x.dataset.id]); }); paths.forEach(function (p) { p.classList.toggle("qw-dim", !(nb[p.dataset.a] && (p.dataset.a === id || p.dataset.b === id))); }); var g = ""; Object.keys(nb).forEach(function (q) { var n = byId3[q]; g += '<text class="qw-nlab' + (q === id ? " me" : "") + '" x="' + (n.x + rad(n) + 3).toFixed(1) + '" y="' + (n.y + 3).toFixed(1) + '">' + esc(last(n.n)) + "</text>"; }); labs.innerHTML = g; }
    function clearHi() { circles.forEach(function (x) { x.classList.remove("qw-dim"); }); paths.forEach(function (p) { p.classList.remove("qw-dim"); }); labs.innerHTML = ""; }
    function fill(id) {
      var n = byId3[id]; byId("qwEmpty").style.display = "none"; byId("qwBody").classList.add("on");
      var tag = byId("qwTag"); tag.innerHTML = state.pinned === id ? '<span class="pin">&#128204; Pinned</span><span class="x" id="qwUnpin">clear</span>' : "<span>Preview &middot; click the dot to pin</span>";
      if (state.pinned === id) { var u = byId("qwUnpin"); if (u) u.onclick = function () { state.pinned = null; webPin = null; syncUrl(); clearHi(); fill(id); }; }
      byId("qwName").textContent = n.n;
      byId("qwMeta").textContent = plabel(n.p) + " \u00b7 " + (n.c === "H" ? "House" : "Senate") + (n.d ? " \u00b7 District " + n.d : "") + " \u00b7 led " + n.b + " bills \u00b7 " + n.k + " co-authors";
      byId("qwScore").textContent = n.s; var lab = byId("qwLab"); lab.textContent = n.lab || "Scored"; lab.className = "lab" + (n.s >= 80 ? " champ" : "");
      byId("qwComp").innerHTML = [["Pillar", n.pi], ["Attend", n.at], ["Impact", n.im], ["Spons", n.sp]].map(function (c) { var v = c[1] == null ? 0 : c[1]; return '<div class="row"><span class="k">' + c[0] + '</span><span class="bar"><span style="width:' + v + '%"></span></span><span class="n">' + (c[1] == null ? "\u2014" : c[1]) + "</span></div>"; }).join("");
      byId("qwCoHead").textContent = "Works most with \u2014 " + last(n.n);
      byId("qwCo").innerHTML = (n.top || []).map(function (t) { return '<div class="qw-co" data-id="' + t[1] + '"><span class="co-n">' + esc(t[0]) + '</span><span class="co-w">' + t[2] + " bills</span></div>"; }).join("");
      byId("qwCo").querySelectorAll(".qw-co").forEach(function (el) { el.addEventListener("click", function () { pin(el.dataset.id); }); });
      var starBtn = byId("qwStar"); function paint() { var on = isStarred(id); starBtn.classList.toggle("on", on); starBtn.innerHTML = on ? "&#9733; Saved" : "&#9734; Save"; } paint();
      starBtn.onclick = function () { toggleStar(n); paint(); toast(isStarred(id) ? "&#9733; Saved <b>" + esc(n.n) + "</b> to My Reps" : "Removed <b>" + esc(n.n) + "</b>"); };
      byId("qwProf").onclick = function () { window.location.href = "legislator.html?state=" + encodeURIComponent(code) + "&id=" + encodeURIComponent(id); };
    }
    function preview(id) { if (state.pinned) return; fill(id); highlight(id); }
    function pin(id) { state.pinned = id; webPin = id; syncUrl(); fill(id); highlight(id); }
    circles.forEach(function (c) { var id = c.dataset.id; c.addEventListener("mouseenter", function () { preview(id); }); c.addEventListener("mouseleave", function () { if (!state.pinned) clearHi(); }); c.addEventListener("click", function () { pin(id); }); });
    var qNames = byId("qwNames"); if (qNames) qNames.innerHTML = NET.nodes.map(function (n) { return '<option value="' + esc(n.n) + '"></option>'; }).join("");
    function focusNode(fid) { var n = byId3[fid]; if (!n) return; var Z = 2.4; vpS = Z; vpX = W / 2 - n.x * Z; vpY = H / 2 - n.y * Z; applyVp(); zLabels(); pin(fid); }
    var qSearch = byId("qwSearch"); if (qSearch) { var doFind = function () { var v = (qSearch.value || "").trim().toLowerCase(); if (!v) return; var hit = NET.nodes.filter(function (n) { return n.n.toLowerCase() === v; })[0] || NET.nodes.filter(function (n) { return n.n.toLowerCase().indexOf(v) >= 0; })[0]; if (hit) focusNode(hit.id); }; qSearch.addEventListener("change", doFind); qSearch.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); doFind(); } }); }
    if (webPin && byId3[webPin]) pin(webPin); // deep-link: open with this official pinned
  }

  /* ---------- boot ---------- */
  function buildTabs() {
    var tabs = byId("lensTabs"); if (!tabs) return;
    tabs.innerHTML = '<span class="lens-lead">See this data your way &rarr;</span>' + TABS.map(function (t) { return '<button class="lens-tab' + (t[0] === "list" ? " active" : "") + '" data-lens="' + t[0] + '">' + esc(t[1]) + "</button>"; }).join("") + '<button class="lens-share" id="lensShare">&#8599; Share this view</button>';
    tabs.addEventListener("click", function (e) { var b = e.target.closest(".lens-tab"); if (b) { setLens(b.dataset.lens); return; } if (e.target.closest("#lensShare")) doShare(); });
    var vt = byId("viewToggle"); if (vt) [].forEach.call(vt.querySelectorAll(".vt-btn"), function (b) { b.addEventListener("click", function () { if (current !== "list") setLens("list"); }); });
    var applied = false;
    var poll = setInterval(function () {
      if (!legs().length) return;
      tabs.style.display = "flex"; tabs.classList.add("pulse"); setTimeout(function () { tabs.classList.remove("pulse"); }, 3800);
      if (!applied) { applied = true; var p = qs(); if (p.pin) webPin = p.pin; if (p.lens && p.lens !== "list") setLens(p.lens); }
      clearInterval(poll);
    }, 300);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", buildTabs); else buildTabs();
})();

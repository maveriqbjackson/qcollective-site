/* hub-lenses.js — The Q Collective
   Multi-lens view-switcher for the Accountability Hub.
   Additive: your existing "List" view is untouched and stays the default.
   New lenses read the already-loaded globals CUR (legislators) and BILLSOBJ (bills).
   Wave 1: List + Briefing + Fingerprints. (Web / Floor / Map / Movement / Card wall follow.) */
(function () {
  "use strict";
  function byId(id) { return document.getElementById(id); }
  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function legs() { return (window.CUR && window.CUR.legislators) || []; }
  function stateCode() { return (window.CUR && window.CUR.state) || (byId("hubState") && byId("hubState").value) || "CO"; }
  function num(v) { return typeof v === "number" ? v : (v == null ? null : (isNaN(+v) ? null : +v)); }
  function last(s) { return String(s || "").split(" ").slice(-1)[0]; }
  function pcolor(p) { return p === "D" ? "#2E5BE6" : p === "R" ? "#BF0A30" : "#3FA45C"; }
  function plabel(p) { return p === "D" ? "Democrat" : p === "R" ? "Republican" : p === "I" ? "Independent" : p === "U" ? "Unaffiliated" : p ? "Third party" : "—"; }

  /* ---------- styles (kept here so hub.html stays nearly untouched) ---------- */
  var css = "" +
    ".lens-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 18px}" +
    ".lens-tab{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase;padding:9px 15px;border-radius:8px;border:1px solid #E0D5BE;background:#fff;color:#5a5a5a;cursor:pointer}" +
    ".lens-tab:hover{border-color:#B8962E;color:#122848}" +
    ".lens-tab.active{background:#122848;color:#fff;border-color:#122848}" +
    ".lz-load{font-family:'DM Mono',monospace;font-size:13px;color:#5a5a5a;padding:30px 0;text-align:center}" +
    /* briefing */
    ".brief-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin-bottom:20px}" +
    ".brief-stat{background:#fff;border:1px solid #E0D5BE;border-radius:10px;padding:14px 16px}" +
    ".brief-stat .v{font-family:'Playfair Display',serif;font-size:27px;font-weight:800;color:#122848;line-height:1}" +
    ".brief-stat .k{font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:1px;text-transform:uppercase;color:#5a5a5a;margin-top:6px}" +
    ".brief-read{background:#fff;border:1px solid #E0D5BE;border-left:4px solid #B8962E;border-radius:10px;padding:20px 22px}" +
    ".brief-read p{font-size:15.5px;color:#2a2a2a;line-height:1.75;margin:0 0 12px}" +
    ".brief-read p:last-child{margin:0}" +
    ".brief-read b{color:#122848}" +
    /* fingerprints */
    ".fp-intro{background:#fff;border:1px solid #E0D5BE;border-left:4px solid #B8962E;border-radius:10px;padding:15px 18px;margin-bottom:18px;font-size:13.5px;color:#4a4a4a;line-height:1.65}" +
    ".fp-intro b{color:#122848}" +
    ".fp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:10px}" +
    ".fp-card{background:#fff;border:1px solid #E0D5BE;border-radius:11px;padding:10px 6px 8px;cursor:pointer;text-align:center;transition:.12s}" +
    ".fp-card:hover{border-color:#B8962E;box-shadow:0 4px 14px rgba(18,40,72,.1);transform:translateY(-2px)}" +
    ".fp-card svg{width:74px;height:74px;display:block;margin:0 auto}" +
    ".fp-name{font-family:'DM Mono',monospace;font-size:10.5px;color:#122848;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
    ".fp-score{font-family:'DM Mono',monospace;font-size:11px;color:#5a5a5a}" +
    ".fp-score.champ{color:#8a6d12;font-weight:600}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  /* ---------- switcher ---------- */
  var current = "list";
  var TABS = [["list", "List"], ["briefing", "Briefing"], ["fingerprint", "Fingerprints"]];
  var listOnly = ["viewToggle", "hubParty", "hubSearch", "tagBar"];
  var normal = ["stateOffices", "hubLeaders", "mySaved", "legSection", "billSection"];

  function setLens(name) {
    current = name;
    var tabs = byId("lensTabs");
    if (tabs) [].forEach.call(tabs.children, function (b) { b.classList.toggle("active", b.dataset.lens === name); });
    var la = byId("lensArea");
    if (name === "list") {
      if (la) la.style.display = "none";
      listOnly.forEach(function (id) { var e = byId(id); if (e) e.style.display = ""; });
      if (window.renderAll) window.renderAll(); // restores proper leg/bills state
    } else {
      normal.forEach(function (id) { var e = byId(id); if (e) e.style.display = "none"; });
      listOnly.forEach(function (id) { var e = byId(id); if (e) e.style.display = "none"; });
      if (la) { la.style.display = "block"; renderLens(name, la); }
    }
  }
  function renderLens(name, la) {
    if (!legs().length) { la.innerHTML = '<p class="lz-load">Loading the data&hellip;</p>'; return; }
    if (name === "briefing") return renderBriefing(la);
    if (name === "fingerprint") return renderFingerprint(la);
  }

  /* ---------- Briefing (plain-language summary) ---------- */
  function renderBriefing(la) {
    var L = legs(), n = L.length;
    var scored = L.filter(function (l) { return num(l.score) != null; });
    var avg = Math.round(scored.reduce(function (a, b) { return a + b.score; }, 0) / (scored.length || 1));
    var champs = scored.filter(function (l) { return l.score >= 80; }).length;
    var D = L.filter(function (l) { return l.party === "D"; }).length;
    var R = L.filter(function (l) { return l.party === "R"; }).length;
    var other = n - D - R;
    var house = L.filter(function (l) { return /House/.test(l.chamber || ""); }).length;
    var sen = n - house;
    var comps = [["pillar", "Pillar alignment"], ["attendance", "Attendance"], ["impact", "Citizen impact"], ["sponsorship", "Sponsorship"]];
    var cavg = comps.map(function (c) { var vals = L.map(function (l) { return num(l[c[0]]); }).filter(function (v) { return v != null; }); return { name: c[1], v: vals.length ? Math.round(vals.reduce(function (a, b) { return a + b; }, 0) / vals.length) : null }; }).filter(function (c) { return c.v != null; });
    var best = cavg.slice().sort(function (a, b) { return b.v - a.v; })[0];
    var weak = cavg.slice().sort(function (a, b) { return a.v - b.v; })[0];
    var srt = scored.slice().sort(function (a, b) { return b.score - a.score; });
    var top = srt[0], low = srt[srt.length - 1];
    var stName = (window.CUR && window.CUR.state_name) || "Colorado";

    var cards = [[n, "Scored"], [avg, "Avg score"], [champs, "Champions 80+"], [D + " / " + R + (other ? " / " + other : ""), "D / R" + (other ? " / other" : "")], [house + " / " + sen, "House / Senate"]];
    var chips = cards.map(function (c) { return '<div class="brief-stat"><div class="v">' + esc(c[0]) + '</div><div class="k">' + esc(c[1]) + '</div></div>'; }).join("");

    var p1 = "<b>" + esc(stName) + "'s legislature</b> averages <b>" + avg + " out of 100</b> across " + n + " scored lawmakers. " +
      (champs ? "<b>" + champs + "</b> clear the 80-point Accountability Champion line" : "No lawmaker currently clears the 80-point Champion line") + ".";
    var p2 = best && weak ? "The chamber's strongest muscle is <b>" + esc(best.name) + "</b> (avg " + best.v + "); its weakest link is <b>" + esc(weak.name) + "</b> (avg " + weak.v + ") — the clearest place records fall short." : "";
    var p3 = top && low ? "<b>" + esc(top.name) + "</b> leads the whole assembly at <b>" + top.score + "</b>" + (top.label ? " (" + esc(top.label) + ")" : "") + ", while <b>" + esc(low.name) + "</b> sits lowest at <b>" + low.score + "</b>." : "";
    var p4 = "Every one of these figures is drawn live from the same public data behind the scores — nothing here is editorial.";

    la.innerHTML = '<div class="brief-cards">' + chips + "</div>" +
      '<div class="brief-read"><p>' + p1 + "</p>" + (p2 ? "<p>" + p2 + "</p>" : "") + (p3 ? "<p>" + p3 + "</p>" : "") + "<p>" + p4 + "</p></div>";
  }

  /* ---------- Fingerprints (component shape per lawmaker) ---------- */
  function renderFingerprint(la) {
    var L = legs().slice().filter(function (l) { return num(l.score) != null; }).sort(function (a, b) { return b.score - a.score; });
    var code = stateCode();
    function shape(l) {
      var v = [num(l.pillar) || 0, num(l.attendance) || 0, num(l.impact) || 0, num(l.sponsorship) || 0].map(function (x) { return Math.max(0, Math.min(100, x)); });
      var cx = 37, cy = 37, R = 30, col = pcolor(l.party);
      var pts = [[cx, cy - R * v[0] / 100], [cx + R * v[1] / 100, cy], [cx, cy + R * v[2] / 100], [cx - R * v[3] / 100, cy]];
      var poly = pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
      var ring = function (f) { return '<polygon points="' + [[cx, cy - R * f], [cx + R * f, cy], [cx, cy + R * f], [cx - R * f, cy]].map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") + '" fill="none" stroke="#e6e0d0" stroke-width="1"/>'; };
      var champ = l.score >= 80;
      return '<button class="fp-card" data-id="' + esc(l.id) + '" title="' + esc(l.name) + ' — ' + esc(l.score) + '">' +
        '<svg viewBox="0 0 74 74">' + ring(1) + ring(0.5) +
        '<line x1="37" y1="7" x2="37" y2="67" stroke="#eee" stroke-width="1"/><line x1="7" y1="37" x2="67" y2="37" stroke="#eee" stroke-width="1"/>' +
        '<polygon points="' + poly + '" fill="' + col + '30" stroke="' + col + '" stroke-width="1.6"/>' +
        (champ ? '<circle cx="37" cy="37" r="33" fill="none" stroke="#D4AF50" stroke-width="1.6"/>' : "") +
        '</svg><div class="fp-name">' + esc(last(l.name)) + '</div><div class="fp-score' + (champ ? ' champ' : '') + '">' + esc(l.score) + '</div></button>';
    }
    la.innerHTML = '<div class="fp-intro">Two lawmakers can share a score and look nothing alike. Each diamond is one lawmaker\'s four score components — <b>Pillar</b> (top), <b>Attendance</b> (right), <b>Impact</b> (bottom), <b>Sponsorship</b> (left). A balanced diamond is well-rounded; a lopsided one leans on one strength. Gold ring = Champion. <b>Click any shape to open that profile.</b></div>' +
      '<div class="fp-grid">' + L.map(shape).join("") + "</div>";
    la.querySelectorAll(".fp-card").forEach(function (c) {
      c.addEventListener("click", function () { window.location.href = "legislator.html?state=" + encodeURIComponent(code) + "&id=" + encodeURIComponent(c.dataset.id); });
    });
  }

  /* ---------- boot ---------- */
  function buildTabs() {
    var tabs = byId("lensTabs");
    if (!tabs) return;
    tabs.innerHTML = TABS.map(function (t) { return '<button class="lens-tab' + (t[0] === "list" ? " active" : "") + '" data-lens="' + t[0] + '">' + esc(t[1]) + "</button>"; }).join("");
    tabs.addEventListener("click", function (e) { var b = e.target.closest(".lens-tab"); if (b) setLens(b.dataset.lens); });
    // if the built-in Legislators/Bills/All toggle is used, snap back to the List lens
    var vt = byId("viewToggle");
    if (vt) [].forEach.call(vt.querySelectorAll(".vt-btn"), function (b) { b.addEventListener("click", function () { if (current !== "list") setLens("list"); }); });
    // reveal the tabs once the data has loaded
    var poll = setInterval(function () { if (legs().length) { tabs.style.display = "flex"; clearInterval(poll); } }, 350);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", buildTabs);
  else buildTabs();
})();

/* q-tax-poll.js — The Q Collective
   "Which CESA taxes would you vote yes on?" An informal, anonymous poll.

   Put <div data-q-tax-poll data-src="cesa-note"></div> where it should appear,
   then load q-config.js and this file. Each answer is Yes / No / Not sure; a
   ZIP code is optional. Cloudflare Turnstile confirms a person before a vote
   counts (same key as the Sunday Update sign-up). After voting, or on a return
   visit, the reader sees the live totals.

   To change a question's wording, edit QUESTIONS below. The keys must match the
   database list in cesa_tax_poll_keys(). */
(function () {
  "use strict";
  var FN = "https://asjvyhppqclglafueppb.supabase.co/functions/v1/cesa-tax-poll";
  var KEY = "sb_publishable_75yNLzcnQV-C08DLKwbHiQ_YXrMI92C";
  var DONE = "qc_taxpoll_done_v1";

  var QUESTIONS = [
    ["sugary_drinks", "Sugary drinks", "5¢ per ounce on soda, energy drinks and other sugar-sweetened drinks. About 60¢ on a 12-ounce can."],
    ["junk_food", "High-sugar, high-fat foods", "An extra 8% sales tax on things like candy, chips, cookies and ice cream."],
    ["ultra_processed", "Ultra-processed foods", "An extra 5% sales tax on heavily processed foods."],
    ["chain_restaurant", "Chain-restaurant meals", "An extra 3% sales tax on prepared food from chain restaurants."],
    ["alcohol", "Alcohol", "A 15% sales tax on beer, wine, spirits and canned cocktails, with the money going first to mental health and addiction care. (Proposed for the next version of CESA.)"],
    ["general_sales", "A general sales tax increase instead", "Not in CESA. Would you rather pay for it with a small sales tax increase on most purchases?"],
    ["income_backup", "Income tax, only as a last-resort backup", "Only if CESA's fees fall short, and only if voters approve it first."]
  ];
  var LABEL = { yes: "Yes", no: "No", unsure: "Not sure" };

  var CSS = [
    ".tp{font-family:'Public Sans',-apple-system,BlinkMacSystemFont,sans-serif;background:#fff;border:1px solid #E0D5BE;border-top:4px solid #B8962E;border-radius:10px;padding:22px 22px 18px;margin:26px 0;color:#1a1a1a}",
    ".tp h3{font-family:'Source Serif 4',Georgia,serif;font-size:23px;font-weight:600;color:#122848;margin:0 0 6px;line-height:1.25}",
    ".tp-intro{font-size:15.5px;line-height:1.6;color:#4a4a4a;margin:0 0 14px}",
    ".tp-q{border-top:1px solid #EFE7D4;padding:12px 0;display:grid;grid-template-columns:1fr auto;gap:6px 14px;align-items:center}",
    ".tp-t{font-weight:700;color:#122848;font-size:15.5px}",
    ".tp-d{font-size:14px;color:#5a5a5a;line-height:1.5;margin-top:2px}",
    ".tp-b{display:flex;gap:6px}",
    ".tp-b button{font:inherit;font-size:14px;font-weight:600;border:1px solid #E0D5BE;background:#F9F6F0;color:#122848;border-radius:6px;padding:8px 12px;cursor:pointer;min-width:58px}",
    ".tp-b button[aria-pressed=true]{background:#122848;color:#fff;border-color:#122848}",
    ".tp-foot{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:14px;padding-top:14px;border-top:1px solid #EFE7D4}",
    ".tp-zip{font:inherit;font-size:15px;border:1px solid #E0D5BE;border-radius:6px;padding:10px 12px;width:150px}",
    ".tp-go{font:inherit;font-size:15px;font-weight:700;background:#B8962E;color:#122848;border:none;border-radius:6px;padding:11px 20px;cursor:pointer}",
    ".tp-go[disabled]{opacity:.55;cursor:default}",
    ".tp-msg{font-size:14px;color:#7a5f12;width:100%}",
    ".tp-fine{font-size:13px;color:#5a5a5a;line-height:1.55;margin:12px 0 0}",
    ".tp-r{border-top:1px solid #EFE7D4;padding:10px 0}",
    ".tp-r .tp-t{font-size:15px}",
    ".tp-bar{display:flex;height:12px;border-radius:6px;overflow:hidden;background:#EFE7D4;margin:7px 0 4px}",
    ".tp-bar .y{background:#122848}.tp-bar .n{background:#B8962E}.tp-bar .u{background:#CFC6B2}",
    ".tp-nums{font-size:13.5px;color:#4a4a4a}",
    ".tp-key{display:flex;gap:14px;font-size:13px;color:#4a4a4a;margin:4px 0 6px}",
    ".tp-key i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}",
    "@media (max-width:620px){.tp{padding:18px 16px 14px}.tp-q{grid-template-columns:1fr}.tp-b button{flex:1}}"
  ].join("");

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function seen() { try { return localStorage.getItem(DONE) === "1"; } catch (e) { return false; } }
  function markSeen() { try { localStorage.setItem(DONE, "1"); } catch (e) {} }

  var tsLoading = null;
  function loadTurnstile() {
    if (window.turnstile) return Promise.resolve(window.turnstile);
    if (tsLoading) return tsLoading;
    tsLoading = new Promise(function (ok, no) {
      var sc = document.createElement("script");
      sc.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
      sc.async = true;
      sc.onload = function () { window.turnstile ? ok(window.turnstile) : no(new Error("no turnstile")); };
      sc.onerror = function () { no(new Error("turnstile blocked")); };
      document.head.appendChild(sc);
    });
    return tsLoading;
  }
  function humanToken(host) {
    return loadTurnstile().then(function (ts) {
      return new Promise(function (ok, no) {
        var box = document.createElement("div");
        box.style.marginTop = "10px";
        host.appendChild(box);
        var id = ts.render(box, {
          sitekey: window.Q_TURNSTILE_SITEKEY,
          appearance: "interaction-only",
          callback: function (t) { setTimeout(function () { try { ts.remove(id); } catch (e) {} if (box.parentNode) box.parentNode.removeChild(box); }, 300); ok(t); },
          "error-callback": function () { no(new Error("turnstile error")); },
          "timeout-callback": function () { no(new Error("turnstile timeout")); }
        });
      });
    });
  }

  function renderResults(el, data, note) {
    var total = (data && data.total) || 0;
    var q = (data && data.questions) || {};
    var html = '<h3>Where people stand on CESA\'s taxes</h3>' +
      (note ? '<p class="tp-intro">' + esc(note) + '</p>' : '') +
      '<p class="tp-intro"><strong>' + total + '</strong> ' + (total === 1 ? 'person has' : 'people have') + ' answered so far.</p>' +
      '<div class="tp-key"><span><i style="background:#122848"></i>Yes</span><span><i style="background:#B8962E"></i>No</span><span><i style="background:#CFC6B2"></i>Not sure</span></div>';
    QUESTIONS.forEach(function (x) {
      var r = q[x[0]] || { yes: 0, no: 0, unsure: 0 };
      var n = r.yes + r.no + r.unsure;
      var p = function (v) { return n ? Math.round(100 * v / n) : 0; };
      html += '<div class="tp-r"><div class="tp-t">' + esc(x[1]) + '</div>' +
        '<div class="tp-bar" role="img" aria-label="' + p(r.yes) + '% yes, ' + p(r.no) + '% no, ' + p(r.unsure) + '% not sure">' +
        (n ? '<span class="y" style="width:' + p(r.yes) + '%"></span><span class="n" style="width:' + p(r.no) + '%"></span><span class="u" style="width:' + p(r.unsure) + '%"></span>' : '') +
        '</div><div class="tp-nums">' + (n ? p(r.yes) + '% yes · ' + p(r.no) + '% no · ' + p(r.unsure) + '% not sure (' + n + ')' : 'No answers yet') + '</div></div>';
    });
    html += '<p class="tp-fine">An informal poll, not a scientific survey. Answers are anonymous, and one response per person per day counts. In CESA\'s next version, every new tax goes to voters as its own ballot question. <a href="cesa-explained.html">How CESA is paid for</a>.</p>';
    el.innerHTML = html;
  }

  function renderForm(el) {
    var picks = {};
    var html = '<h3>Which CESA taxes would you vote yes on?</h3>' +
      '<p class="tp-intro">CESA runs mostly on fees. In its next version, every new tax in it goes to Colorado voters as its own question, so you would decide each one. Tell us where you stand. Fresh fruits and vegetables would be tax-free under the bill.</p>';
    QUESTIONS.forEach(function (x) {
      html += '<div class="tp-q" data-k="' + x[0] + '"><div><div class="tp-t">' + esc(x[1]) + '</div><div class="tp-d">' + esc(x[2]) + '</div></div>' +
        '<div class="tp-b" role="group" aria-label="' + esc(x[1]) + '">' +
        ['yes', 'no', 'unsure'].map(function (v) { return '<button type="button" data-v="' + v + '" aria-pressed="false">' + LABEL[v] + '</button>'; }).join('') +
        '</div></div>';
    });
    html += '<div class="tp-foot"><input class="tp-zip" inputmode="numeric" maxlength="5" placeholder="ZIP (optional)" aria-label="ZIP code, optional">' +
      '<button type="button" class="tp-go" disabled>Add my answers</button><div class="tp-msg" aria-live="polite"></div></div>' +
      '<p class="tp-fine">Anonymous. Your ZIP is optional and only helps show where support is. We don\'t store your IP address.</p>';
    el.innerHTML = html;

    var go = el.querySelector(".tp-go"), msg = el.querySelector(".tp-msg");
    Array.prototype.forEach.call(el.querySelectorAll(".tp-q"), function (row) {
      var k = row.getAttribute("data-k");
      Array.prototype.forEach.call(row.querySelectorAll("button"), function (b) {
        b.addEventListener("click", function () {
          picks[k] = b.getAttribute("data-v");
          Array.prototype.forEach.call(row.querySelectorAll("button"), function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
          go.disabled = false;
        });
      });
    });
    go.addEventListener("click", function () {
      if (!window.Q_TURNSTILE_SITEKEY) { msg.textContent = "The poll isn't switched on yet. Please check back soon."; return; }
      go.disabled = true; msg.textContent = "Checking you're a person…";
      var zip = (el.querySelector(".tp-zip").value || "").trim();
      humanToken(el.querySelector(".tp-foot")).then(function (token) {
        msg.textContent = "Saving…";
        return fetch(FN, {
          method: "POST",
          headers: { "apikey": KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ answers: picks, zip: /^\d{5}$/.test(zip) ? zip : "", src: el.getAttribute("data-src") || "", token: token })
        });
      }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, status: r.status, d: d }; }); })
        .then(function (res) {
          if (res.status === 403) { msg.textContent = "We couldn't confirm you're a person. Refresh and try again."; go.disabled = false; return; }
          if (!res.ok || !res.d || !res.d.results) { throw new Error("bad reply"); }
          markSeen();
          renderResults(el, res.d.results, res.d.status === "already" ? "Looks like you already answered today, so we counted your first response. Here are the totals." : "Thanks. Your answers are in.");
        })
        .catch(function () { msg.textContent = "Something went wrong saving your answers. Please try again in a minute."; go.disabled = false; });
    });
  }

  function load(el) {
    if (!seen()) { renderForm(el); return; }
    fetch(FN, { headers: { "apikey": KEY } }).then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (d) { renderResults(el, d, "You've already answered. Here are the latest totals."); })
      .catch(function () { renderForm(el); });
  }

  function run() {
    var spots = document.querySelectorAll("[data-q-tax-poll]");
    if (!spots.length) return;
    if (!document.getElementById("tp-css")) { var s = document.createElement("style"); s.id = "tp-css"; s.textContent = CSS; document.head.appendChild(s); }
    Array.prototype.forEach.call(spots, function (el) { el.classList.add("tp"); load(el); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();

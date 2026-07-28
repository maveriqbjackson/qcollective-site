/* q-announce.js — The Q Collective
   A tasteful, one-time announcement modal: new features + weekly-update signup.
   Install: add ONE line before </body> on any page (index.html, hub.html, ...):
       <script src="q-announce.js"></script>
   Shows once per ANNOUNCE_VERSION (remembered in localStorage). Bump the version
   string to re-announce to everyone. Newsletter signup routes through Web3Forms
   to team@theQcollective.org (the Sunday Update). */
(function () {
  "use strict";
  var ANNOUNCE_VERSION = "2026-08"; // bump to re-show the popup to everyone
  var WEB3FORMS_KEY = "da0f4760-ac24-433c-b27f-52058241488e";
  var STORE_KEY = "qc_announce_seen";
  var DELAY_MS = 900;

  function seen() { try { return localStorage.getItem(STORE_KEY) === ANNOUNCE_VERSION; } catch (e) { return false; } }
  function markSeen() { try { localStorage.setItem(STORE_KEY, ANNOUNCE_VERSION); } catch (e) {} }
  if (seen()) return;

  var css =
    "#qa-back{position:fixed;inset:0;background:rgba(10,23,48,.55);backdrop-filter:blur(3px);z-index:9998;opacity:0;transition:opacity .25s;display:flex;align-items:center;justify-content:center;padding:20px}" +
    "#qa-back.on{opacity:1}" +
    "#qa-card{background:#fff;max-width:440px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 24px 60px rgba(10,23,48,.4);transform:translateY(14px) scale(.98);transition:transform .25s;font-family:'DM Sans',system-ui,sans-serif}" +
    "#qa-back.on #qa-card{transform:none}" +
    "#qa-top{background:#122848;color:#fff;padding:22px 24px 18px;position:relative}" +
    "#qa-top .q{position:absolute;right:-8px;top:-26px;font-family:'Playfair Display',serif;font-weight:900;font-size:120px;color:rgba(255,255,255,.06);pointer-events:none}" +
    "#qa-kick{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#D4AF50;margin-bottom:6px}" +
    "#qa-top h3{font-family:'Playfair Display',serif;font-size:22px;font-weight:800;line-height:1.15;margin:0;position:relative}" +
    "#qa-x{position:absolute;top:14px;right:16px;width:28px;height:28px;border:0;background:rgba(255,255,255,.12);color:#fff;border-radius:50%;font-size:16px;line-height:1;cursor:pointer}" +
    "#qa-x:hover{background:rgba(255,255,255,.25)}" +
    "#qa-body{padding:20px 24px 24px}" +
    "#qa-list{list-style:none;margin:0 0 18px;padding:0}" +
    "#qa-list li{display:flex;gap:10px;font-size:14px;color:#3a3a3a;line-height:1.5;margin-bottom:9px}" +
    "#qa-list li span{color:#B8962E;font-weight:700;flex:0 0 auto}" +
    "#qa-list li b{color:#122848}" +
    "#qa-sub{border-top:1px solid #eee;padding-top:16px}" +
    "#qa-sub p{font-size:13.5px;color:#4a4a4a;margin:0 0 10px}#qa-sub p b{color:#122848}" +
    "#qa-form{display:flex;gap:8px}" +
    "#qa-email{flex:1;border:1px solid #d8d2c4;border-radius:8px;padding:11px 12px;font-size:14px;font-family:inherit}" +
    "#qa-email:focus{outline:none;border-color:#B8962E}" +
    "#qa-go{border:0;background:#B8962E;color:#122848;font-family:'DM Mono',monospace;font-size:12px;letter-spacing:.5px;text-transform:uppercase;font-weight:600;padding:0 16px;border-radius:8px;cursor:pointer}" +
    "#qa-go:hover{background:#D4AF50}#qa-go:disabled{opacity:.6;cursor:default}" +
    "#qa-msg{font-size:13px;margin-top:9px;min-height:18px}" +
    "#qa-msg.ok{color:#1f7a44}#qa-msg.err{color:#b23b3b}" +
    "#qa-later{display:block;width:100%;text-align:center;margin-top:14px;background:none;border:0;color:#8a8a8a;font-size:12px;cursor:pointer;font-family:'DM Mono',monospace}" +
    "#qa-later:hover{color:#122848}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  var back = document.createElement("div"); back.id = "qa-back";
  back.innerHTML =
    '<div id="qa-card" role="dialog" aria-label="What\'s new">' +
      '<div id="qa-top"><div class="q">Q</div><button id="qa-x" aria-label="Close">&times;</button>' +
        '<div id="qa-kick">New on The Q Collective</div>' +
        '<h3>See your legislature in ways you never could before.</h3></div>' +
      '<div id="qa-body">' +
        '<ul id="qa-list">' +
          '<li><span>&rarr;</span><div><b>New Hub views.</b> Read a plain-language briefing of the whole legislature, or explore it visually &mdash; the same scores, your way.</div></li>' +
          '<li><span>&rarr;</span><div><b>Follow any bill</b> and get an email the moment it moves.</div></li>' +
          '<li><span>&rarr;</span><div><b>Save your representatives</b> for quick check-ins on where they stand.</div></li>' +
          '<li><span>&rarr;</span><div><b>Coming soon:</b> see who works with whom, and find your rep on a Colorado map.</div></li>' +
        '</ul>' +
        '<div id="qa-sub"><p><b>Get the Sunday Update.</b> The Q Score refreshes every Sunday &mdash; we\'ll send the recap straight to your inbox.</p>' +
          '<div id="qa-form"><input id="qa-email" type="email" placeholder="you@email.com" autocomplete="email"><button id="qa-go">Sign me up</button></div>' +
          '<div id="qa-msg" aria-live="polite"></div>' +
          '<button id="qa-later">Maybe later</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  function close() { back.classList.remove("on"); markSeen(); setTimeout(function () { if (back.parentNode) back.parentNode.removeChild(back); }, 260); document.removeEventListener("keydown", onKey); }
  function onKey(e) { if (e.key === "Escape") close(); }

  function mount() {
    document.body.appendChild(back);
    requestAnimationFrame(function () { back.classList.add("on"); });
    document.addEventListener("keydown", onKey);
    back.addEventListener("click", function (e) { if (e.target === back) close(); });
    document.getElementById("qa-x").addEventListener("click", close);
    document.getElementById("qa-later").addEventListener("click", close);
    var go = document.getElementById("qa-go"), email = document.getElementById("qa-email"), msg = document.getElementById("qa-msg");
    function submit() {
      var v = (email.value || "").trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { msg.className = "err"; msg.textContent = "Please enter a valid email."; return; }
      go.disabled = true; msg.className = ""; msg.textContent = "Signing you up\u2026";
      fetch("https://api.web3forms.com/submit", {
        method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ access_key: WEB3FORMS_KEY, subject: "Sunday Update signup", from_name: "The Q Collective site", email: v, message: "New Sunday Update subscriber: " + v })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d && d.success) { msg.className = "ok"; msg.textContent = "You're in \u2014 see you Sunday."; document.getElementById("qa-form").style.display = "none"; markSeen(); }
        else { go.disabled = false; msg.className = "err"; msg.textContent = "Something went wrong \u2014 please try again."; }
      }).catch(function () { go.disabled = false; msg.className = "err"; msg.textContent = "Network error \u2014 please try again."; });
    }
    go.addEventListener("click", submit);
    email.addEventListener("keydown", function (e) { if (e.key === "Enter") submit(); });
  }

  function boot() { setTimeout(mount, DELAY_MS); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();

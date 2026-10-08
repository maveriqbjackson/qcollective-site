/* q-sunday-band.js — The Q Collective
   The "Get the Sunday Update" sign-up band, in one place.

   DROP-IN: put this where the band should appear, then load this file:
     <div data-q-sunday-band data-src="hub"></div>
     <script src="q-sunday-band.js"></script>

   data-src   optional label so we can see where sign-ups come from
              (hub, profile, ...). A ?src= on the page link wins over it.
   data-text  optional sentence under the heading.

   Sign-ups go straight onto the Sunday Update list through q-sunday.js
   (loaded here automatically), the same as the homepage form. */
(function () {
  "use strict";
  if (window.__qSundayBand) return;
  window.__qSundayBand = 1;

  var DEFAULT_TEXT = "Every Sunday evening: what moved in the Colorado legislature, whose record changed, and the dates that matter. Free. Unsubscribe anytime.";

  function css() {
    if (document.getElementById("q-sband-css")) return;
    var s = document.createElement("style");
    s.id = "q-sband-css";
    s.textContent =
      ".q-sband{display:flex;flex-wrap:wrap;gap:16px 22px;align-items:center;justify-content:space-between;" +
      "background:#122848;border-radius:12px;border-left:5px solid #B8962E;padding:22px 24px;margin:30px auto;max-width:1100px;box-sizing:border-box}" +
      ".q-sband-txt{flex:1 1 280px;min-width:0}" +
      ".q-sband-h{font-family:Georgia,'Source Serif 4',serif;font-size:20px;font-weight:700;color:#fff;margin:0 0 4px}" +
      ".q-sband-p{font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:14px;line-height:1.5;color:rgba(255,255,255,.8);margin:0}" +
      ".q-sband-form{flex:1 1 300px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}" +
      ".q-sband-form input{flex:1 1 190px;min-width:0;font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:15px;padding:12px 13px;" +
      "border:1px solid rgba(255,255,255,.3);border-radius:8px;background:rgba(255,255,255,.08);color:#fff}" +
      ".q-sband-form input::placeholder{color:rgba(255,255,255,.5)}" +
      ".q-sband-form button{flex:0 0 auto;font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:14px;font-weight:700;" +
      "background:#B8962E;color:#122848;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}" +
      ".q-sband-form button:disabled{opacity:.6;cursor:default}" +
      ".q-sband-msg{flex:1 1 100%;margin:2px 0 0;font-family:'Public Sans',Helvetica,Arial,sans-serif;font-size:13.5px;color:#E9D9A3;min-height:1em}" +
      "@media print{.q-sband{display:none}}";
    document.head.appendChild(s);
  }

  function withSignup(cb) {
    if (window.qcSundaySignup) return cb();
    var sc = document.querySelector('script[src^="q-sunday.js"]');
    if (!sc) {
      sc = document.createElement("script");
      sc.src = "q-sunday.js";
      document.body.appendChild(sc);
    }
    sc.addEventListener("load", cb);
  }

  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function mount(slot) {
    if (slot.getAttribute("data-mounted")) return;
    slot.setAttribute("data-mounted", "1");
    var src = slot.getAttribute("data-src") || "";
    var text = slot.getAttribute("data-text") || DEFAULT_TEXT;
    slot.innerHTML =
      '<div class="q-sband"><div class="q-sband-txt"><p class="q-sband-h">Get the Sunday Update</p>' +
      '<p class="q-sband-p">' + esc(text) + '</p></div>' +
      '<form class="q-sband-form" novalidate><input type="email" required placeholder="you@email.com" aria-label="Your email" autocomplete="email">' +
      '<button type="submit">Sign me up</button><p class="q-sband-msg" role="status"></p></form></div>';
    var f = slot.querySelector("form"), inp = f.querySelector("input"), btn = f.querySelector("button"),
        m = f.querySelector(".q-sband-msg");
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = (inp.value || "").trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { m.textContent = "Please enter a valid email."; return; }
      btn.disabled = true;
      m.textContent = "Signing you up…";
      withSignup(function () {
        window.qcSundaySignup(v, src).then(function (res) {
          m.textContent = window.qcSundayMessage(res);
          if (res === "ok" || res === "confirm" || res === "already" || res === "queued") inp.disabled = true;
          else btn.disabled = false;
        });
      });
    });
  }

  function go() {
    css();
    var slots = document.querySelectorAll("[data-q-sunday-band]");
    for (var i = 0; i < slots.length; i++) mount(slots[i]);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go);
  else go();
})();

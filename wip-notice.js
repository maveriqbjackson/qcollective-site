/* ============================================================
   Q Collective — WIP Notice  (wip-notice.js)
   A small, on-brand "this section is still in progress" toast.

   DROP-IN: add ONE line to any page (usually right before </body>):

     <script src="wip-notice.js"
             data-id="hub-federal"
             data-msg="Federal offices — the President, Vice President, and U.S. Supreme Court — aren't scored yet. Colorado is live first; the national level is coming next."
             data-link="how-q-scores-work.html"
             data-linktext="How scoring works"></script>

   Attributes:
     data-id        required — unique per notice; used to remember dismissal
     data-msg       required — the short, specific message
     data-link      optional — a URL for a "learn more" link
     data-linktext  optional — the link label (default: "Learn more")
     data-remember  optional — "true" (default) remembers dismissal; "false" shows every visit
     data-delay     optional — ms before it slides up (default 700)

   Edit the styling/behavior HERE once and it updates on every page.
   ============================================================ */
(function () {
  var script = document.currentScript;
  if (!script) return;

  var cfg = {
    id:       script.getAttribute("data-id") || "wip",
    msg:      script.getAttribute("data-msg") || "Some sections of this page are still in progress.",
    link:     script.getAttribute("data-link") || "",
    linkText: script.getAttribute("data-linktext") || "Learn more",
    remember: (script.getAttribute("data-remember") || "true") !== "false",
    delay:    parseInt(script.getAttribute("data-delay") || "700", 10)
  };
  var KEY = "qc_wip_dismissed_" + cfg.id;

  function dismissed() {
    if (!cfg.remember) return false;
    try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; }
  }
  function remember() {
    if (!cfg.remember) return;
    try { localStorage.setItem(KEY, "1"); } catch (e) {}
  }

  function injectCSS() {
    if (document.getElementById("qc-wip-css")) return;
    var css = ''
      + '.qc-wip{position:fixed;left:18px;bottom:18px;z-index:9999;max-width:360px;'
      + 'background:#0a2540;color:#eaf0f7;border:1px solid #1c3c5e;border-left:4px solid #c9a23a;'
      + 'border-radius:10px;box-shadow:0 10px 30px rgba(6,20,40,.28);'
      + 'font-family:Cambria,Georgia,serif;font-size:13.5px;line-height:1.5;'
      + 'padding:12px 14px 12px 14px;transform:translateY(140%);opacity:0;'
      + 'transition:transform .35s ease,opacity .35s ease}'
      + '.qc-wip.show{transform:translateY(0);opacity:1}'
      + '.qc-wip-row{display:flex;gap:10px;align-items:flex-start}'
      + '.qc-wip-dot{flex:0 0 auto;width:20px;height:20px;border-radius:50%;background:#c9a23a;'
      + 'color:#0a2540;font-weight:700;display:grid;place-items:center;font-size:13px;margin-top:1px}'
      + '.qc-wip-body{flex:1 1 auto}'
      + '.qc-wip-tag{display:block;font-size:10.5px;letter-spacing:.5px;text-transform:uppercase;'
      + 'color:#c9a23a;font-weight:700;margin-bottom:2px}'
      + '.qc-wip-body a{color:#e9d9a3;text-decoration:underline;white-space:nowrap}'
      + '.qc-wip-x{flex:0 0 auto;background:none;border:none;color:#9db4d0;font-size:18px;'
      + 'line-height:1;cursor:pointer;padding:0 2px;margin:-2px -2px 0 4px}'
      + '.qc-wip-x:hover{color:#fff}'
      + '@media(max-width:520px){.qc-wip{left:12px;right:12px;bottom:12px;max-width:none}}'
      + '@media(prefers-reduced-motion:reduce){.qc-wip{transition:opacity .2s ease}.qc-wip{transform:none}}';
    var s = document.createElement("style");
    s.id = "qc-wip-css";
    s.textContent = css;
    document.head.appendChild(s);
  }

  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function build() {
    if (dismissed()) return;
    if (document.getElementById("qc-wip-" + cfg.id)) return;
    injectCSS();

    var linkHTML = cfg.link
      ? ' <a href="' + esc(cfg.link) + '">' + esc(cfg.linkText) + ' &rarr;</a>'
      : '';

    var el = document.createElement("div");
    el.className = "qc-wip";
    el.id = "qc-wip-" + cfg.id;
    el.setAttribute("role", "status");
    el.innerHTML =
      '<div class="qc-wip-row">'
      + '<span class="qc-wip-dot" aria-hidden="true">i</span>'
      + '<div class="qc-wip-body"><span class="qc-wip-tag">In progress</span>'
      + esc(cfg.msg) + linkHTML + '</div>'
      + '<button class="qc-wip-x" aria-label="Dismiss notice">&times;</button>'
      + '</div>';

    document.body.appendChild(el);
    el.querySelector(".qc-wip-x").addEventListener("click", function () {
      el.classList.remove("show");
      remember();
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 400);
    });
    setTimeout(function () { el.classList.add("show"); }, cfg.delay);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();

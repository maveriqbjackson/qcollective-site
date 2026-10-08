/* q-sunday.js — The Q Collective
   Sunday Update sign-up. Used by the homepage form and the announcement popup.

   window.qcSundaySignup(email) -> Promise resolving to one of:
     "ok"       on the list, no confirmation needed. A welcome email follows
                and the next Sunday Update arrives that Sunday evening.
     "confirm"  on the list but NOT active until they confirm by email. This
                only happens when sign-ups are flooding in (the database
                switches confirmation back on by itself) or when the address
                was already waiting on a confirmation. A pop-up opens that
                spells out exactly what to look for.
     "already"  this email is already on the list
     "invalid"  not a usable email address
     "queued"   the list was unreachable, so the sign-up was emailed to the
                team instead. Nothing is lost; add it by hand.
   Every successful sign-up also sends team@theQcollective.org a heads-up
   through Web3Forms, same as before. PUBLIC keys only in this file. */
(function () {
  "use strict";
  if (window.qcSundaySignup) return;

  var SUPABASE_URL = "https://asjvyhppqclglafueppb.supabase.co";
  var SUPABASE_KEY = "sb_publishable_75yNLzcnQV-C08DLKwbHiQ_YXrMI92C";
  var WEB3FORMS_KEY = "da0f4760-ac24-433c-b27f-52058241488e";

  function notifyTeam(email, note) {
    try {
      return fetch("https://api.web3forms.com/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          access_key: WEB3FORMS_KEY,
          subject: "Sunday Update signup",
          from_name: "The Q Collective site",
          email: email,
          message: "New Sunday Update subscriber: " + email + (note ? "\n\n" + note : "")
        })
      }).then(function (r) { return r.json(); }).catch(function () { return null; });
    } catch (e) { return Promise.resolve(null); }
  }

  // Must match the subject in send_sunday_update.py (confirmation email).
  var CONFIRM_SUBJECT = "Confirm your Sunday Update";
  var CONFIRM_SENDER = "noreply@auth.theqcollective.org";

  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Shown only when confirmation is switched on. Make the next step impossible to miss.
  function showConfirmPopup(email) {
    try {
      var old = document.getElementById("qs-confirm");
      if (old) old.parentNode.removeChild(old);
      var w = document.createElement("div");
      w.id = "qs-confirm";
      w.setAttribute("role", "dialog");
      w.setAttribute("aria-modal", "true");
      w.setAttribute("aria-labelledby", "qs-confirm-h");
      w.setAttribute("style", "position:fixed;inset:0;z-index:2147483600;background:rgba(10,22,44,.72);display:flex;align-items:center;justify-content:center;padding:16px;overflow:auto");
      w.innerHTML =
        '<div style="background:#fff;max-width:440px;width:100%;border-radius:14px;border-top:6px solid #B8962E;box-shadow:0 18px 50px rgba(0,0,0,.35);padding:26px 24px 22px;font-family:\'Public Sans\',Helvetica,Arial,sans-serif;color:#2a3242;text-align:left">' +
          '<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#B8962E;font-weight:700">One more step</div>' +
          '<h2 id="qs-confirm-h" style="font-family:Georgia,serif;font-size:23px;line-height:1.25;color:#122848;margin:6px 0 12px">Confirm your email to finish signing up</h2>' +
          '<p style="font-size:15px;line-height:1.6;margin:0 0 14px">You are <b>not signed up yet</b>. We\u2019re getting an unusual number of sign-ups right now, so we\u2019re asking everyone to confirm. It keeps strangers from signing you up.</p>' +
          '<div style="background:#FBF6E6;border:1px solid #E0D5BE;border-radius:10px;padding:14px 16px;margin:0 0 14px">' +
            '<div style="font-size:14.5px;line-height:1.6"><b>1.</b> We\u2019re sending an email to <b style="overflow-wrap:anywhere">' + esc(email) + '</b>.</div>' +
            '<div style="font-size:14.5px;line-height:1.6;margin-top:8px"><b>2.</b> Look for this subject line:</div>' +
            '<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#122848;margin:4px 0 2px">' + esc(CONFIRM_SUBJECT) + '</div>' +
            '<div style="font-size:13px;color:#5a5a5a">From The Q Collective (' + esc(CONFIRM_SENDER) + ')</div>' +
            '<div style="font-size:14.5px;line-height:1.6;margin-top:8px"><b>3.</b> Open it and press <b>Confirm my subscription</b>.</div>' +
          '</div>' +
          '<p style="font-size:14px;line-height:1.6;margin:0 0 6px"><b>Don\u2019t see it?</b> It can take an hour or two to arrive. Check your <b>spam or junk</b> folder, or search your mail for the subject line above.</p>' +
          '<p style="font-size:13px;line-height:1.6;color:#5a5a5a;margin:0 0 16px">Still nothing by tomorrow? Write to team@theQcollective.org and we\u2019ll add you by hand.</p>' +
          '<button type="button" id="qs-confirm-ok" style="background:#122848;color:#fff;border:0;border-radius:8px;padding:13px 22px;font-size:15px;font-weight:700;cursor:pointer;width:100%">Got it, I\u2019ll check my email</button>' +
        '</div>';
      document.body.appendChild(w);
      function close() { if (w.parentNode) w.parentNode.removeChild(w); document.removeEventListener("keydown", onKey); }
      function onKey(e) { if (e.key === "Escape") close(); }
      document.addEventListener("keydown", onKey);
      var b = document.getElementById("qs-confirm-ok");
      b.addEventListener("click", close);
      b.focus();
    } catch (e) {}
  }
  window.qcSundayConfirmPopup = showConfirmPopup;   // lets the team preview it from the browser console

  // Where a sign-up came from, so we can see which channels work.
  // A ?src= on the link wins (QR code, LinkedIn post...), then the form's own label, then the page name.
  function sourceOf(src) {
    var q = "";
    try { q = new URLSearchParams(location.search).get("src") || ""; } catch (e) {}
    var page = (location.pathname.split("/").pop() || "index.html").replace(/\.html$/, "") || "index";
    var s = String(q || src || page).toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 24);
    return s || "site";
  }

  window.qcSundaySignup = function (email, src) {
    var v = String(email || "").trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) return Promise.resolve("invalid");

    return fetch(SUPABASE_URL + "/rest/v1/rpc/subscribe_sunday", {
      method: "POST",
      headers: {
        "apikey": SUPABASE_KEY,
        "Authorization": "Bearer " + SUPABASE_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ e: v, src: sourceOf(src) })
    }).then(function (r) {
      if (!r.ok) throw new Error("status " + r.status);
      return r.json();
    }).then(function (res) {
      if (res === "ok") { notifyTeam(v); return "ok"; }
      if (res === "confirm") {
        notifyTeam(v, "Confirmation is ON for this sign-up (a flood of sign-ups, or this address was already waiting). They are not active until they confirm.");
        showConfirmPopup(v);
        return "confirm";
      }
      if (res === "already" || res === "invalid") return res;
      throw new Error("unexpected reply");
    }).catch(function () {
      // The list couldn't be reached. Don't lose the person: email the team.
      return notifyTeam(v, "NOTE: the subscriber list was unreachable, so this person is NOT on it yet. Add them by hand.")
        .then(function (d) { return d && d.success ? "queued" : "error"; });
    });
  };

  // Friendly message for each result, shared by every form on the site.
  window.qcSundayMessage = function (res) {
    switch (res) {
      case "ok":      return "You're in. Your first Sunday Update arrives this Sunday evening.";
      case "confirm": return "One more step: confirm by email. Subject line: \u201c" + CONFIRM_SUBJECT + "\u201d. Check spam too.";
      case "already": return "You're already on the list. See you Sunday.";
      case "invalid": return "Please enter a valid email.";
      case "queued":  return "Got it. We'll add you to the list shortly.";
      default:        return "Something went wrong. Please email team@theQcollective.org.";
    }
  };
})();

/* q-sunday.js — The Q Collective
   Sunday Update sign-up. Used by the homepage form and the announcement popup.

   window.qcSundaySignup(email) -> Promise resolving to one of:
     "ok"       saved; a confirmation email goes out within about 6 hours
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

  window.qcSundaySignup = function (email) {
    var v = String(email || "").trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) return Promise.resolve("invalid");

    return fetch(SUPABASE_URL + "/rest/v1/rpc/subscribe_sunday", {
      method: "POST",
      headers: {
        "apikey": SUPABASE_KEY,
        "Authorization": "Bearer " + SUPABASE_KEY,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ e: v })
    }).then(function (r) {
      if (!r.ok) throw new Error("status " + r.status);
      return r.json();
    }).then(function (res) {
      if (res === "ok") { notifyTeam(v); return "ok"; }
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
      case "ok":      return "You're in. Check your inbox for a one-click confirmation.";
      case "already": return "You're already on the list. See you Sunday.";
      case "invalid": return "Please enter a valid email.";
      case "queued":  return "Got it. We'll add you and send a confirmation shortly.";
      default:        return "Something went wrong. Please email team@theQcollective.org.";
    }
  };
})();

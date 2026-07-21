/* ============================================================================
   Q COLLECTIVE — AUTH  (Supabase magic-link sign-in)
   These are PUBLIC keys and are safe in the browser. Your database is protected
   by the row-level-security rules in the schema, not by hiding this key.
   NEVER put the sb_secret_... key in this file or any site file.
   ============================================================================ */
(function () {
  var SUPABASE_URL = "https://asjvyhppqclglafueppb.supabase.co";
  var SUPABASE_KEY = "sb_publishable_75yNLzcnQV-C08DLKwbHiQ_YXrMI92C";

  var resolveReady;
  window.qcReady = new Promise(function (r) { resolveReady = r; });

  function boot() {
    try {
      window.qc = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
      resolveReady(window.qc);
    } catch (e) {
      resolveReady(null);
    }
  }

  if (window.supabase && window.supabase.createClient) {
    boot();
  } else {
    var sc = document.createElement("script");
    sc.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
    sc.onload = boot;
    sc.onerror = function () { resolveReady(null); };
    document.head.appendChild(sc);
  }

  // Convenience helpers used by pages.
  window.qAuth = {
    ready: function () { return window.qcReady; },
    signIn: function (email) {
      return window.qcReady.then(function (qc) {
        if (!qc) return { error: { message: "Sign-in service unavailable." } };
        return qc.auth.signInWithOtp({
          email: email,
          options: { emailRedirectTo: location.origin + "/account.html" }
        });
      });
    },
    signOut: function () {
      return window.qcReady.then(function (qc) { return qc ? qc.auth.signOut() : null; });
    },
    user: function () {
      return window.qcReady.then(function (qc) {
        if (!qc) return null;
        return qc.auth.getUser().then(function (r) { return (r && r.data) ? r.data.user : null; });
      });
    }
  };
})();

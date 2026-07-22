/* ============================================================================
   Q COLLECTIVE — AUTH + SYNC  (Supabase magic-link)
   PUBLIC keys only. Database is protected by row-level security, not secrecy.
   NEVER put the sb_secret_... key in this or any site file.
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
    } catch (e) { resolveReady(null); }
  }
  if (window.supabase && window.supabase.createClient) { boot(); }
  else {
    var sc = document.createElement("script");
    sc.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
    sc.onload = boot;
    sc.onerror = function () { resolveReady(null); };
    document.head.appendChild(sc);
  }

  window.qAuth = {
    ready: function () { return window.qcReady; },
    signIn: function (email) {
      return window.qcReady.then(function (qc) {
        if (!qc) return { error: { message: "Sign-in service unavailable." } };
        return qc.auth.signInWithOtp({ email: email, options: { emailRedirectTo: location.origin + "/account.html" } });
      });
    },
    signOut: function () { return window.qcReady.then(function (qc) { return qc ? qc.auth.signOut() : null; }); },
    user: function () {
      return window.qcReady.then(function (qc) {
        if (!qc) return null;
        return qc.auth.getUser().then(function (r) { return (r && r.data) ? r.data.user : null; });
      });
    }
  };

  /* ---------------------------------------------------------------------
     qSync — keeps My Reps / My Bills in step with the signed-in account.
     localStorage stays the render source; this layer merges + writes through.
     Signed out: every method is a harmless no-op.
     --------------------------------------------------------------------- */
  function rd(k) { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch (e) { return []; } }
  function wr(k, a) { try { localStorage.setItem(k, JSON.stringify(a)); } catch (e) {} }

  window.qSync = {
    on: false,
    uid: null,

    addRep: function (id) {
      if (!this.on || !window.qc) return;
      window.qc.from("saved_reps").upsert({ user_id: this.uid, person_id: String(id) }, { onConflict: "user_id,person_id" }).then(function () {}, function () {});
    },
    delRep: function (id) {
      if (!this.on || !window.qc) return;
      window.qc.from("saved_reps").delete().eq("user_id", this.uid).eq("person_id", String(id)).then(function () {}, function () {});
    },
    addBill: function (n) {
      if (!this.on || !window.qc) return;
      window.qc.from("saved_bills").upsert({ user_id: this.uid, bill_number: String(n) }, { onConflict: "user_id,bill_number" }).then(function () {}, function () {});
    },
    delBill: function (n) {
      if (!this.on || !window.qc) return;
      window.qc.from("saved_bills").delete().eq("user_id", this.uid).eq("bill_number", String(n)).then(function () {}, function () {});
    },

    /* Merge account <-> device, then run onDone(signedIn).
       Union, never delete: we would rather over-preserve someone's list. */
    init: function (onDone) {
      var self = this;
      function done(v) { if (typeof onDone === "function") { try { onDone(v); } catch (e) {} } }
      window.qcReady.then(function (qc) {
        if (!qc) { done(false); return; }
        qc.auth.getUser().then(function (r) {
          var u = r && r.data ? r.data.user : null;
          if (!u) { self.on = false; done(false); return; }
          self.on = true; self.uid = u.id;

          Promise.all([
            qc.from("saved_reps").select("person_id").eq("user_id", u.id),
            qc.from("saved_bills").select("bill_number").eq("user_id", u.id)
          ]).then(function (res) {
            var remoteReps = (res[0] && res[0].data ? res[0].data : []).map(function (x) { return String(x.person_id); });
            var remoteBills = (res[1] && res[1].data ? res[1].data : []).map(function (x) { return String(x.bill_number); });

            var localReps = rd("qc_myreps");
            var haveRep = {}; localReps.forEach(function (x) { haveRep[String(x.id)] = true; });
            remoteReps.forEach(function (pid) { if (!haveRep[pid]) { localReps.push({ id: pid, name: "", score: "", chamber: "", district: "" }); haveRep[pid] = true; } });
            wr("qc_myreps", localReps);

            var localBills = rd("qc_mybills");
            var haveBill = {}; localBills.forEach(function (x) { haveBill[String(x.number)] = true; });
            remoteBills.forEach(function (bn) { if (!haveBill[bn]) { localBills.push({ number: bn, title: "" }); haveBill[bn] = true; } });
            wr("qc_mybills", localBills);

            // push anything this device had that the account did not
            var rSet = {}; remoteReps.forEach(function (x) { rSet[x] = true; });
            var bSet = {}; remoteBills.forEach(function (x) { bSet[x] = true; });
            var upReps = localReps.filter(function (x) { return !rSet[String(x.id)]; })
                                  .map(function (x) { return { user_id: u.id, person_id: String(x.id) }; });
            var upBills = localBills.filter(function (x) { return !bSet[String(x.number)]; })
                                    .map(function (x) { return { user_id: u.id, bill_number: String(x.number) }; });
            if (upReps.length) qc.from("saved_reps").upsert(upReps, { onConflict: "user_id,person_id" }).then(function () {}, function () {});
            if (upBills.length) qc.from("saved_bills").upsert(upBills, { onConflict: "user_id,bill_number" }).then(function () {}, function () {});

            done(true);
          }).catch(function () { done(true); });
        }).catch(function () { done(false); });
      });
    }
  };
})();

/* ============================================================
   Q Collective: admin sign-in gate (q-admin-gate.js)
   Used by hq.html and q-console.html.

   Real email sign-in through the site's existing Supabase accounts:
     1. You type your email and get a one-time sign-in link.
     2. The database checks your verified email against the admin
        list (public.hq_admins, readable by nobody from the site).
     3. Only then does the page open. Private HQ notes and to-dos are
        stored in public.hq_private, which the database only lets
        admins read or write, so they're protected even if someone
        opens the page's code.

   Needs q-auth.js loaded first. Pages call qAdmin.ready(fn) to run
   code once an admin is confirmed.
   ============================================================ */
(function () {
  var waiting = [], ok = false, AFTER = 'qc_after_login';
  var here = (location.pathname.split('/').pop() || 'hq.html');

  var css = document.createElement('style');
  css.textContent =
    '#qa-gate{position:fixed;inset:0;z-index:99999;background:#122848;display:flex;align-items:center;justify-content:center;padding:20px;font-family:"Public Sans",system-ui,sans-serif}' +
    '#qa-gate .bx{background:#fff;border-radius:12px;max-width:400px;width:100%;padding:28px 26px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.35)}' +
    '#qa-gate .q{font:700 46px/1 Georgia,serif;color:#B8962E}' +
    '#qa-gate h1{font:700 23px/1.3 Georgia,serif;color:#122848;margin:10px 0 6px}' +
    '#qa-gate p{color:#4a4a4a;font-size:15.5px;line-height:1.55;margin:0 0 14px}' +
    '#qa-gate input{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:12px;border:1.5px solid #E0D5BE;border-radius:6px;margin-bottom:10px}' +
    '#qa-gate input:focus{outline:none;border-color:#B8962E}' +
    '#qa-gate button{width:100%;font:inherit;font-weight:700;font-size:16px;background:#122848;color:#fff;border:0;border-radius:6px;padding:12px;cursor:pointer}' +
    '#qa-gate button.ghost{background:none;color:#122848;border:1px solid #E0D5BE;margin-top:8px}' +
    '#qa-gate .msg{font-size:14.5px;margin-top:10px;color:#4a4a4a}#qa-gate .err{color:#8b3a32}';
  document.head.appendChild(css);

  var gate = document.createElement('div');
  gate.id = 'qa-gate';
  gate.innerHTML = '<div class="bx"><div class="q">Q</div><h1>Admins only</h1><div id="qa-body"><p>Checking your sign-in&hellip;</p></div></div>';
  (document.body || document.documentElement).appendChild(gate);

  function body(html) { document.getElementById('qa-body').innerHTML = html; }
  function askEmail(note) {
    body((note ? '<p class="err">' + note + '</p>' : '') +
      '<p>Sign in with your admin email. We’ll send you a one-time link.</p>' +
      '<input id="qa-email" type="email" autocomplete="email" placeholder="you@email.com">' +
      '<button id="qa-send" type="button">Email me a sign-in link</button><div class="msg" id="qa-msg"></div>');
    var go = function () {
      var e = (document.getElementById('qa-email').value || '').trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) { document.getElementById('qa-msg').innerHTML = '<span class="err">That email doesn’t look right.</span>'; return; }
      try { localStorage.setItem(AFTER, JSON.stringify({ to: here, at: Date.now() })); } catch (x) {}
      document.getElementById('qa-send').disabled = true;
      window.qAuth.signIn(e).then(function (r) {
        if (r && r.error) { document.getElementById('qa-msg').innerHTML = '<span class="err">' + (r.error.message || 'That didn’t send. Try again.') + '</span>'; document.getElementById('qa-send').disabled = false; return; }
        body('<p><strong>Check your email.</strong> We sent a sign-in link to ' + e.replace(/</g, '&lt;') + '. Open it on this device and you’ll come straight back here.</p>');
      });
    };
    document.getElementById('qa-send').onclick = go;
    document.getElementById('qa-email').addEventListener('keydown', function (ev) { if (ev.key === 'Enter') go(); });
    document.getElementById('qa-email').focus();
  }
  function open() {
    ok = true; gate.remove();
    var w = waiting; waiting = []; w.forEach(function (f) { try { f(); } catch (e) {} });
  }

  window.qAdmin = {
    ready: function (fn) { if (ok) fn(); else waiting.push(fn); },
    load: function (key) {
      return window.qcReady.then(function (qc) {
        return qc.from('hq_private').select('body').eq('key', key).maybeSingle()
          .then(function (r) { return r && r.data ? r.data.body : null; });
      });
    },
    save: function (key, b) {
      return window.qcReady.then(function (qc) {
        return qc.from('hq_private').upsert({ key: key, body: b, updated_at: new Date().toISOString() });
      });
    },
    signOut: function () { return window.qAuth.signOut().then(function () { location.reload(); }); }
  };

  function check() {
    if (!window.qAuth) { body('<p class="err">Sign-in isn’t available right now. Refresh to try again.</p>'); return; }
    window.qAuth.user().then(function (u) {
      if (!u) return askEmail('');
      window.qcReady.then(function (qc) {
        qc.rpc('is_hq_admin').then(function (r) {
          if (r && r.data === true) return open();
          body('<p>You’re signed in as <strong>' + String(u.email || '').replace(/</g, '&lt;') + '</strong>, which isn’t on the admin list.</p>' +
            '<button type="button" id="qa-out">Sign out and use another email</button>');
          document.getElementById('qa-out').onclick = window.qAdmin.signOut;
        });
      });
    }).catch(function () { askEmail(''); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', check); else check();
})();

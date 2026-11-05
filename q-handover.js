/* ============================================================
   Q Collective: handover helper (q-handover.js)
   Reads data/transition_2027.json once and answers two questions
   for any page that shows an official:

     qHandover.office(o)   statewide offices. Before the swearing-in
                           date it adds o._incoming (the officeholder-
                           elect). From that date it returns the new
                           holder, unscored, with o._former set to the
                           person who left, so pages switch over on the
                           day itself without anyone pressing a button.

     qHandover.leaving(id) a legislator who is leaving: returns the
                           entry (successor, what's next) or null.

   Call qHandover.ready(fn) to run fn once the file has loaded.
   If the file can't load, everything falls back to "no change".
   ============================================================ */
(function () {
  var T = null, waiting = [], done = false;
  function today() {
    // Colorado's date, so the switch happens at midnight Mountain time
    try { return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Denver' }).format(new Date()); }
    catch (e) { return new Date().toISOString().slice(0, 10); }
  }
  function finish(d) { T = d; done = true; var w = waiting; waiting = []; w.forEach(function (f) { try { f(); } catch (e) {} }); }
  fetch('data/transition_2027.json?v=' + Date.now()).then(function (r) { return r.ok ? r.json() : null; })
    .then(finish).catch(function () { finish(null); });

  function fmt(iso) {
    var p = String(iso || '').split('-');
    var m = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    return p.length === 3 ? m[+p[1] - 1] + ' ' + (+p[2]) + ', ' + p[0] : iso;
  }

  window.qHandover = {
    ready: function (fn) { if (done) fn(); else waiting.push(fn); },
    fmt: fmt,
    office: function (o) {
      if (!T || !o) return o;
      var h = (T.statewide || []).filter(function (s) { return s.office === o.office; })[0];
      if (!h || (o.holder && h.incoming === o.holder)) return o;
      if (today() >= h.takes_office) {
        return { office: o.office, holder: h.incoming, status: 'new_in_office', score: null, label: '', components: {},
                 why: '', entries: [], _since: h.takes_office,
                 _former: { holder: o.holder, score: o.score, label: o.label } };
      }
      var c = {}; for (var k in o) c[k] = o[k];
      c._incoming = h; return c;
    },
    leaving: function (id) {
      if (!T) return null;
      if (T.dates && T.dates.legislature_last_day && today() > T.dates.legislature_last_day) return null;
      return (T.legislators_leaving || []).filter(function (x) { return String(x.id) === String(id); })[0] || null;
    },
    lastDay: function () { return T && T.dates ? T.dates.legislature_last_day : null; },
    data: function () { return T; }
  };
})();

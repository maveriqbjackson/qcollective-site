# ============================================================
# Session handover for the Q Score engine
# The Q Collective / Doctrine Policy Group
#
# Used by score.py. The scoring rubric and weights are not touched here.
#
# What it does when Colorado's legislature moves to a new session:
#   1. HOLD: the new session only takes over once LegiScan lists at least
#      90% of the seats. An early, half-filled dataset can never replace
#      the lawmakers on the site.
#   2. ARCHIVE: the finished session is saved for good in
#      data/archive/<ST>_<session>.json. It is never overwritten.
#   3. PAST OFFICIALS: everyone who left gets added to
#      data/past_officials.json with their final record. Entries are only
#      added, never edited or removed. That file feeds past-officials.html.
#   4. FIVE-VOTE RULE: no one gets a new score until they have at least
#      5 recorded votes in the session. Returning members keep showing last
#      session's final score, clearly marked, until then. Brand-new members
#      show "New member" with no number. Scoring a blank record is unfair.
# ============================================================
import os, re, json
from datetime import datetime, timezone

MIN_VOTES = 5
ROSTER_SEATS = {"CO": 100}
ROSTER_SHARE = 0.9
CARRY_FIELDS = ("score", "label", "pillar", "attendance", "attendance_raw", "impact",
                "sponsorship", "ai_spons", "enacted", "why")


def today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-") or "session"


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


def roster_ready(abbr, people_ids):
    """True when a new session lists enough seats to take over."""
    seats = ROSTER_SEATS.get(abbr)
    return (not seats) or len(people_ids) >= ROSTER_SHARE * seats


def archive_session(outdir, abbr, old):
    """Save a finished session's full record. Never overwrites an existing archive."""
    d = os.path.join(outdir, "archive")
    os.makedirs(d, exist_ok=True)
    name = "%s_%s.json" % (abbr, slug(old.get("session_name") or str(old.get("session"))))
    path = os.path.join(d, name)
    if not os.path.exists(path):
        _save(path, old)
    return "archive/" + name


def add_past_legislators(outdir, abbr, old, new_ids, archive_rel):
    """Add everyone from the finished session who isn't in the new one. Returns how many."""
    path = os.path.join(outdir, "past_officials.json")
    doc = _load(path, None) or {"note": "Officials who have left office, with their final Q Score record. "
                                        "Added automatically and never edited.", "officials": []}
    term = old.get("session_name") or str(old.get("session"))
    have = set((str(o.get("id")), o.get("term")) for o in doc["officials"])
    added = 0
    for L in old.get("legislators", []):
        lid = str(L.get("id"))
        if lid in new_ids or (lid, term) in have:
            continue
        doc["officials"].append({
            "id": lid, "name": L.get("name"), "branch": "legislative", "state": abbr,
            "office": L.get("chamber"), "district": L.get("district"), "party": L.get("party"),
            "term": term, "left": today_iso(), "score": L.get("score"), "label": L.get("label", ""),
            "why": L.get("why", ""), "pillar": L.get("pillar"), "attendance": L.get("attendance"),
            "impact": L.get("impact"), "sponsorship": L.get("sponsorship"), "enacted": L.get("enacted"),
            "record": archive_rel})
        added += 1
    _save(path, doc)
    return added


def begin(outdir, abbr, ds, people_ids, log):
    """Call after parsing a dataset, before scoring. Returns a context dict, or None to HOLD
    (keep the current file untouched this week)."""
    state_file = os.path.join(outdir, abbr + ".json")
    old = _load(state_file, {}) or {}
    tpath = os.path.join(outdir, "transition_state.json")
    tstate = _load(tpath, {}) or {}
    switching = bool(old.get("session")) and str(old.get("session")) != str(ds.get("session_id"))
    if switching:
        if not roster_ready(abbr, people_ids):
            log("  new session %s lists only %d seats - holding on the current session until it fills in."
                % (ds.get("session_name"), len(people_ids)))
            return None
        archive_rel = archive_session(outdir, abbr, old)
        n = add_past_legislators(outdir, abbr, old, set(people_ids), archive_rel)
        log("  new session: archived %s to data/%s; %d past legislators added" %
            (old.get("session_name"), archive_rel, n))
        tstate[abbr] = {"previous_session": old.get("session"),
                        "previous_session_name": old.get("session_name", ""),
                        "previous_archive": archive_rel, "switched": today_iso()}
        _save(tpath, tstate)
    prev = {}
    rel = tstate.get(abbr, {}).get("previous_archive")
    if rel:
        prev = {str(L.get("id")): L for L in (_load(os.path.join(outdir, rel), {}) or {}).get("legislators", [])}
    return {"switching": switching, "prev": prev,
            "prev_name": tstate.get(abbr, {}).get("previous_session_name", "")}


def early_record(ctx, base_rec, pid, votes_total):
    """If this member has fewer than MIN_VOTES votes, return the record to publish instead of a
    new score. Otherwise None (score them normally)."""
    if votes_total >= MIN_VOTES:
        return None
    prior = (ctx or {}).get("prev", {}).get(str(pid))
    rec = dict(base_rec)
    if prior and prior.get("score") is not None:
        for k in CARRY_FIELDS:
            rec[k] = prior.get(k)
        rec["carried"] = True
        rec["carried_from"] = (ctx or {}).get("prev_name") or "last session"
        rec["_h"] = "carried"
    else:
        rec.update({"score": None, "label": "New member", "unscored": True, "why": "", "enacted": 0,
                    "pillar": None, "attendance": None, "impact": None, "sponsorship": None, "_h": "new"})
    return rec


def sort_key(x):
    return (x.get("score") is None, -(x.get("score") or 0))

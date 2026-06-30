#!/usr/bin/env python3
# ============================================================
# The Q Score Engine  -  The Q Collective / Doctrine Policy Group
# version history (newest first):
#   v6.3 Phase 3.5a (additive; scoring UNCHANGED): writes data/<ST>_bills.json (rich per-bill
#        record - full action history, progress, sponsors with people_id for on-site linking,
#        and text/PDF references) to power the on-site bill detail page; data/<ST>_snapshots.json
#        (score history, appended only when a score moves); data/health.json run heartbeat so
#        "did it run and did it work?" is always answerable. No timestamp inside _bills.json so
#        unchanged bills produce no off-season commit churn.
#   v6.2 roster hygiene: drop former officeholders the data source still lists after a
#        mid-term seat change (EXCLUDE_PEOPLE); warn on any remaining duplicate seat.
#        No scoring change. (CO SD-21: kept current Benavidez, dropped Michaelson Jenet.)
#   v6.1 network resilience: retry + backoff on LegiScan calls (survives timeouts)
#   v6  DEFENSIBLE SPONSORSHIP
#       - Sponsorship score = 70% AI pillar-leadership judgment + 30% an
#         OBJECTIVE count of the member's prime-sponsored bills that became law
#         (hard number from official data; breaks ties, grounds the score)
#       - Stores ai_spons (raw judgment, for caching) + enacted count per member
#   v5  SHARPEN + LABELS
#       - Grader differentiates PRECISELY now: scores reflect how many
#         substantial pillar bills each member LED and got enacted; no more
#         clustered/bucket numbers, no two different records sharing a score
#       - Chamber labels: "State Senate" / "State House" (or Assembly /
#         House of Delegates) + state body name (e.g. "Colorado General Assembly")
#       - Photo field carried through for future portraits
#   v4  recalibrated so the genuine top ~10% earn 80+ (v3 was too harsh: 0)
#   v3  harsh recalibration (prime-sponsorship focus, attendance curve, chamber fix)
#   v2  all states, per-state files, caching, per-legislator bills
#   v1  Colorado only
#
# RUBRIC (legislative, LOCKED): Pillar 40% | Attendance 25% | Impact 25% | Sponsorship 10%
#   0-100; 80+ = "Accountability Champion"
# Secrets: LEGISCAN_KEY, ANTHROPIC_API_KEY | Env: STATES, MODEL, LIMIT
# ============================================================
import os, sys, json, base64, io, zipfile, time, re, hashlib
import urllib.request, urllib.parse, urllib.error

LEGISCAN_KEY  = os.environ.get("LEGISCAN_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
STATES_ENV    = os.environ.get("STATES", "ALL").strip()
MODEL         = os.environ.get("MODEL", "claude-sonnet-4-6")
LIMIT         = int(os.environ.get("LIMIT", "0"))
OUTDIR        = "data"

# Former officeholders the data source still lists after a mid-term seat change.
# Keyed by LegiScan people_id so the roster shows only the CURRENT officeholder.
# CO Senate 21: Dafna Michaelson Jenet (18713) resigned 2/13/26; Adrienne Benavidez (18710) holds it now.
EXCLUDE_PEOPLE = {"18713"}
SCORE_VERSION = "v6"          # bump to force a full re-score on the next run

PILLARS = ("Health, Income, Family, Housing, Food, Economic Opportunity, "
           "and Protection from Disruption")

STATE_ID = {1:("AL","Alabama"),2:("AK","Alaska"),3:("AZ","Arizona"),4:("AR","Arkansas"),
5:("CA","California"),6:("CO","Colorado"),7:("CT","Connecticut"),8:("DE","Delaware"),
9:("FL","Florida"),10:("GA","Georgia"),11:("HI","Hawaii"),12:("ID","Idaho"),13:("IL","Illinois"),
14:("IN","Indiana"),15:("IA","Iowa"),16:("KS","Kansas"),17:("KY","Kentucky"),18:("LA","Louisiana"),
19:("ME","Maine"),20:("MD","Maryland"),21:("MA","Massachusetts"),22:("MI","Michigan"),
23:("MN","Minnesota"),24:("MS","Mississippi"),25:("MO","Missouri"),26:("MT","Montana"),
27:("NE","Nebraska"),28:("NV","Nevada"),29:("NH","New Hampshire"),30:("NJ","New Jersey"),
31:("NM","New Mexico"),32:("NY","New York"),33:("NC","North Carolina"),34:("ND","North Dakota"),
35:("OH","Ohio"),36:("OK","Oklahoma"),37:("OR","Oregon"),38:("PA","Pennsylvania"),
39:("RI","Rhode Island"),40:("SC","South Carolina"),41:("SD","South Dakota"),42:("TN","Tennessee"),
43:("TX","Texas"),44:("UT","Utah"),45:("VT","Vermont"),46:("VA","Virginia"),47:("WA","Washington"),
48:("WV","West Virginia"),49:("WI","Wisconsin"),50:("WY","Wyoming"),52:("US","United States Congress")}
ABBR_TO_ID = {v[0]: k for k, v in STATE_ID.items()}
ABBR_SET = set(v[0] for v in STATE_ID.values())

# state legislature body names (default "Legislature")
LEG_BODY = {"CO":"General Assembly","CT":"General Assembly","DE":"General Assembly",
"GA":"General Assembly","IL":"General Assembly","IN":"General Assembly","IA":"General Assembly",
"KY":"General Assembly","MD":"General Assembly","MO":"General Assembly","NC":"General Assembly",
"OH":"General Assembly","PA":"General Assembly","RI":"General Assembly","SC":"General Assembly",
"TN":"General Assembly","VA":"General Assembly","VT":"General Assembly",
"MA":"General Court","NH":"General Court","OR":"Legislative Assembly","ND":"Legislative Assembly"}

STATUS = {1:"Introduced",2:"Engrossed",3:"Enrolled",4:"Passed/Enacted",5:"Vetoed",6:"Failed"}
PROGRESS_EVENT = {1:"Introduced",2:"Engrossed",3:"Enrolled",4:"Passed",5:"Vetoed",6:"Failed/Dead",7:"Veto Override",8:"Chaptered",9:"Referred",10:"Reported Favorably",11:"Reported Unfavorably",12:"Draft"}

def log(*a): print(*a, flush=True)
def clamp(v):
    try: v = int(round(float(v)))
    except Exception: return 0
    return max(0, min(100, v))

def stamp_now():
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        return datetime.now(ZoneInfo("America/Denver")).strftime("%B %-d, %Y at %-I:%M %p %Z")
    except Exception:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

def status_text(b):
    s = b.get("status")
    try: return STATUS.get(int(s), "")
    except Exception: return ""

def attendance_score(raw):
    return clamp(round((raw - 80) / 20.0 * 100))

def chamber_label(role, abbr):
    if abbr == "US":
        return "U.S. Senate" if role == "Senator" else "U.S. House"
    if role == "Senator": return "State Senate"
    if abbr in ("CA","NV","NY","WI"): return "State Assembly"
    if abbr in ("MD","VA","WV"): return "House of Delegates"
    return "State House"

# ---------------------------------------------------------------- LegiScan
def legiscan(op, **params):
    params["key"] = LEGISCAN_KEY; params["op"] = op
    url = "https://api.legiscan.com/?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            log("  LegiScan %s attempt %d/4 failed: %s" % (op, attempt + 1, str(e)[:120]))
            time.sleep(5 * (attempt + 1))
    raise last

def latest_datasets(states):
    dl = legiscan("getDatasetList")
    best = {}
    for d in dl.get("datasetlist", []):
        info = STATE_ID.get(d.get("state_id"))
        if not info or info[0] not in states: continue
        abbr = info[0]
        key = (d.get("year_end", 0), 0 if d.get("special") else 1, d.get("session_id", 0))
        if abbr not in best or key > best[abbr][0]:
            best[abbr] = (key, {"session_id": d.get("session_id"), "access_key": d.get("access_key"),
                                "session_name": d.get("session_name", "")})
    return {a: v[1] for a, v in best.items()}

def fetch_dataset(session_id, access_key):
    res = legiscan("getDataset", id=session_id, access_key=access_key)
    z = res.get("dataset", {}).get("zip", "")
    if not z: raise RuntimeError("no dataset archive returned")
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(z)))

def parse_dataset(zf):
    people, bills, votes = {}, {}, {}
    for name in zf.namelist():
        if not name.endswith(".json"): continue
        try: obj = json.loads(zf.read(name).decode("utf-8", "ignore"))
        except Exception: continue
        if "/people/" in name and "person" in obj: people[obj["person"].get("people_id")] = obj["person"]
        elif "/bill/" in name and "bill" in obj:   bills[obj["bill"].get("bill_id")] = obj["bill"]
        elif "/vote/" in name and "roll_call" in obj: votes[obj["roll_call"].get("roll_call_id")] = obj["roll_call"]
    return people, bills, votes

def aggregate(people, bills, votes):
    agg = {pid: {"person": people[pid], "sponsored": [], "votes_cast": 0, "votes_total": 0} for pid in people}
    for b in bills.values():
        for sp in b.get("sponsors", []):
            pid = sp.get("people_id")
            if pid in agg:
                agg[pid]["sponsored"].append({"bill_id": b.get("bill_id"), "number": b.get("bill_number"),
                    "title": b.get("title",""), "status": status_text(b),
                    "url": b.get("url") or b.get("state_link"), "primary": sp.get("sponsor_type_id") == 1})
    for v in votes.values():
        for iv in v.get("votes", []):
            pid = iv.get("people_id")
            if pid in agg:
                agg[pid]["votes_total"] += 1
                if (iv.get("vote_text") or "").strip().lower() in ("yea","nay","yes","no"):
                    agg[pid]["votes_cast"] += 1
    return agg

def extract_bill(b):
    """Rich per-bill record for the on-site bill detail page (Phase 3.5b)."""
    hist = [{"date": x.get("date"), "action": x.get("action"), "chamber": x.get("chamber")}
            for x in (b.get("history") or [])]
    prog = [{"date": x.get("date"), "event": PROGRESS_EVENT.get(x.get("event"), str(x.get("event","")))}
            for x in (b.get("progress") or [])]
    spons = [{"people_id": x.get("people_id"), "name": x.get("name",""), "party": x.get("party",""),
              "role": x.get("role",""), "primary": x.get("sponsor_type_id") == 1}
             for x in (b.get("sponsors") or [])]
    spons.sort(key=lambda z: 0 if z["primary"] else 1)
    texts = [{"type": x.get("type",""), "date": x.get("date"), "mime": x.get("mime",""),
              "doc_id": x.get("doc_id"), "url": x.get("url"), "state_link": x.get("state_link")}
             for x in (b.get("texts") or [])]
    return {"number": b.get("bill_number"), "title": b.get("title",""),
            "description": b.get("description",""), "status": status_text(b),
            "status_date": b.get("status_date"), "url": b.get("url"), "state_link": b.get("state_link"),
            "history": hist, "progress": prog, "sponsors": spons, "texts": texts,
            "subjects": [x.get("subject_name") for x in (b.get("subjects") or []) if x.get("subject_name")]}

def record_hash(sponsored, votes_total):
    key = SCORE_VERSION + "|" + ",".join(sorted(str(s["bill_id"]) for s in sponsored)) + "|" + str(votes_total)
    return hashlib.md5(key.encode()).hexdigest()

# ---------------------------------------------------------------- Claude
def anthropic_call(body):
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type":"application/json","x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            log("  Anthropic HTTP", e.code, e.read()[:200].decode("utf-8","ignore")); time.sleep(3*(attempt+1))
        except Exception as e:
            log("  Anthropic error:", str(e)); time.sleep(3*(attempt+1))
    return {}

def score_person(name, role, state_name, primary_bills, co_count):
    enacted = sum(1 for s in primary_bills if "Passed" in (s.get("status") or "") or "Enacted" in (s.get("status") or ""))
    if primary_bills:
        plines = "\n".join("- " + (s["number"] or "") + " " + (s["title"] or "")[:150]
                           + " [" + (s["status"] or "status unknown") + "]" for s in primary_bills[:25])
    else:
        plines = "(NONE - this legislator did not prime-sponsor any bills this session)"
    prompt = (
        "You are a demanding, strictly non-partisan accountability analyst. Score this state legislator "
        "ONLY on how their record advances the seven pillars of life stability: " + PILLARS +
        ". Never consider party.\n\n"
        "GRADING STANDARD - be discriminating but fair. Use the FULL scale, and make sure the genuine "
        "leaders of the session are recognized at the top:\n"
        "  80-100  STANDOUT - roughly the top 10%. Personally LED (prime-sponsored) multiple substantial "
        "bills that became law and clearly advance the pillars. Award this to the clear leaders.\n"
        "  60-79   Strong - led several meaningful pillar-aligned bills, some enacted.\n"
        "  40-59   AVERAGE - where most members land. A few prime sponsorships, modest impact.\n"
        "  20-39   Thin - little prime sponsorship; mostly symbolic, narrow, or unrelated bills.\n"
        "  0-19    Nothing that advances the pillars.\n\n"
        "Most members are average (40-59); do NOT inflate the middle. Co-sponsoring popular bills is easy "
        "and counts for little - judge mainly what they PRIME-SPONSORED and what BECAME LAW.\n\n"
        "SCORE PRECISELY AND INDIVIDUALLY. The number of substantial, pillar-advancing bills a member LED "
        "and got ENACTED is the strongest signal - more enacted, weightier bills means a higher score. "
        "Use the exact value each record warrants; do NOT output round bucket numbers (82, 80, 75...), and "
        "NEVER give two members with different records the same score. Small differences in record should "
        "produce small differences in score.\n\n"
        "Legislator: " + name + " (" + role + ", " + state_name + ")\n"
        "Bills they PRIME-SPONSORED / led (" + str(len(primary_bills)) + " total, " + str(enacted) + " became law):\n"
        + plines + "\n"
        "They also co-sponsored " + str(co_count) + " other bills (minor weight).\n\n"
        "Rate each 0-100 by the standard above:\n"
        "  pillar       - do their prime-sponsored, enacted bills advance the seven pillars?\n"
        "  impact       - real, broad benefit to everyday people from what they actually passed\n"
        "  sponsorship  - leadership: how many weighty pillar-aligned bills they prime-sponsored and enacted\n\n"
        'Return ONLY compact JSON, no prose: {"pillar":N,"impact":N,"sponsorship":N,"why":"one specific sentence about THIS member\'s record"}')
    data = anthropic_call({"model": MODEL, "max_tokens": 320, "messages":[{"role":"user","content":prompt}]})
    txt = "".join(c.get("text","") for c in data.get("content",[]) if c.get("type")=="text").strip().strip("`")
    m = re.search(r"\{.*\}", txt, re.S)
    try: return json.loads(m.group(0)) if m else {}
    except Exception: return {}

# ---------------------------------------------------------------- helpers
def person_name(p):
    return p.get("name") or (str(p.get("first_name","")) + " " + str(p.get("last_name",""))).strip()

def person_role(p, abbr=""):
    d = str(p.get("district","")).upper()
    if abbr != "US":
        if d.startswith("S"): return "Senator"
        if d.startswith("H"): return "Representative"
    r = (p.get("role") or "").lower()
    if "sen" in r: return "Senator"
    if "rep" in r: return "Representative"
    rid = p.get("role_id")
    if rid == 2: return "Senator"
    if rid == 1: return "Representative"
    if d.startswith("S"): return "Senator"
    if d.startswith("H"): return "Representative"
    return "Legislator"

def us_home_state(p):
    d = str(p.get("district","")).upper()
    for m in re.findall(r"[A-Z]{2}", d):
        if m in ABBR_SET and m != "US": return m
    return ""

def clean_district(p):
    m = re.search(r"(\d+)", str(p.get("district","")))
    return str(int(m.group(1))) if m else str(p.get("district",""))

def load_cache(path):
    try: return {str(l["id"]): l for l in json.load(open(path)).get("legislators", [])}
    except Exception: return {}

# ---------------------------------------------------------------- per state
def do_state(abbr, ds):
    name = STATE_ID[ABBR_TO_ID[abbr]][1]
    body = name if abbr == "US" else name + " " + LEG_BODY.get(abbr, "Legislature")
    log("\n=== %s (%s) session %s ===" % (name, abbr, ds["session_id"]))
    people, bills, votes = parse_dataset(fetch_dataset(ds["session_id"], ds["access_key"]))
    log("  parsed people=%d bills=%d roll_calls=%d" % (len(people), len(bills), len(votes)))
    if not people:
        log("  no legislators - skipping"); return None
    agg = aggregate(people, bills, votes)
    cache = load_cache(os.path.join(OUTDIR, abbr + ".json"))
    items = list(agg.items())
    if LIMIT: items = items[:LIMIT]
    reused = scored = no_primary = 0
    out = []
    for pid, a in items:
        if str(pid) in EXCLUDE_PEOPLE:   # former officeholder replaced mid-term — show only the current one
            continue
        p = a["person"]; nm = person_name(p); role = person_role(p, abbr)
        primary = [s for s in a["sponsored"] if s["primary"]]
        co_count = len(a["sponsored"]) - len(primary)
        if not primary: no_primary += 1
        h = record_hash(a["sponsored"], a["votes_total"])
        prior = cache.get(str(pid))
        if prior and prior.get("_h") == h and prior.get("pillar") is not None:
            pillar, impact, ai_spons, why = prior["pillar"], prior["impact"], prior.get("ai_spons", prior["sponsorship"]), prior.get("why","")
            reused += 1
        else:
            sc = score_person(nm, role, name, primary, co_count)
            pillar, impact, ai_spons = clamp(sc.get("pillar")), clamp(sc.get("impact")), clamp(sc.get("sponsorship"))
            why = sc.get("why",""); scored += 1; time.sleep(0.4)
        att_raw = round(100 * a["votes_cast"] / a["votes_total"]) if a["votes_total"] else 0
        att = attendance_score(att_raw)
        enacted_primary = sum(1 for s in primary if "Passed" in (s["status"] or "") or "Enacted" in (s["status"] or ""))
        obj_spons = clamp(round(enacted_primary / 10.0 * 100))   # objective: prime-sponsored bills enacted, full marks at 10
        spons = round(0.70*ai_spons + 0.30*obj_spons)
        total = round(0.40*pillar + 0.25*att + 0.25*impact + 0.10*spons)
        bills_list = [{"number": s["number"], "title": s["title"], "status": s["status"],
                       "url": s["url"], "primary": s["primary"]} for s in a["sponsored"][:60]]
        out.append({"id": str(pid), "name": nm, "role": role,
                    "chamber": chamber_label(role, abbr), "body": body, "home": (us_home_state(p) if abbr == "US" else abbr),
                    "party": p.get("party",""), "district": clean_district(p),
                    "photo": p.get("photo",""), "score": total,
                    "label": "Accountability Champion" if total >= 80 else "",
                    "pillar": pillar, "attendance": att, "attendance_raw": att_raw,
                    "impact": impact, "sponsorship": spons, "ai_spons": ai_spons, "enacted": enacted_primary, "why": why, "bills": bills_list, "_h": h})
    out.sort(key=lambda x: x["score"], reverse=True)
    seat_seen = {}
    for x in out:
        if not x["district"]: continue
        seat = (x["chamber"], x["district"])
        if seat in seat_seen:
            log("  WARNING duplicate seat: %s District %s lists both '%s' and '%s' - a seat may have changed hands; add the former member's id to EXCLUDE_PEOPLE." % (x["chamber"], x["district"], seat_seen[seat], x["name"]))
        else:
            seat_seen[seat] = x["name"]
    champs = sum(1 for x in out if x["score"] >= 80)
    top = out[0]["score"] if out else 0
    recent = sorted(bills.values(), key=lambda b: b.get("status_date",""), reverse=True)[:30]
    recent = [{"number": b.get("bill_number"), "title": b.get("title"), "status": status_text(b),
               "date": b.get("status_date"), "url": b.get("url") or b.get("state_link")} for b in recent]
    data = {"state": abbr, "state_name": name, "body": body, "session": ds["session_id"],
            "session_name": ds.get("session_name",""), "updated": stamp_now(),
            "count": len(out), "legislators": out, "recent_bills": recent}
    with open(os.path.join(OUTDIR, abbr + ".json"), "w") as f:
        json.dump(data, f, indent=1)
    # --- 3.5a: rich per-bill data for the on-site bill detail page (no timestamp inside -> no off-season churn) ---
    bills_out = {b.get("bill_number"): extract_bill(b) for b in bills.values() if b.get("bill_number")}
    with open(os.path.join(OUTDIR, abbr + "_bills.json"), "w") as f:
        json.dump({"state": abbr, "session": ds["session_id"], "count": len(bills_out), "bills": bills_out},
                  f, indent=1, sort_keys=True)
    # --- 3.5a: score snapshots, appended only when a score actually moved (feeds sparklines) ---
    snap_path = os.path.join(OUTDIR, abbr + "_snapshots.json")
    try: snaps = json.load(open(snap_path)).get("snapshots", {})
    except Exception: snaps = {}
    today_map = {x["id"]: x["score"] for x in out}
    last_key = max(snaps.keys()) if snaps else None
    if (not last_key) or snaps.get(last_key) != today_map:
        from datetime import datetime, timezone
        snaps[datetime.now(timezone.utc).strftime("%Y-%m-%d")] = today_map
        with open(snap_path, "w") as f:
            json.dump({"state": abbr, "snapshots": snaps}, f, indent=1, sort_keys=True)
    log("  %s: %d legislators (%d scored, %d cached) | %d champions (80+) | top score %d | %d had no prime-sponsored bills" %
        (abbr, len(out), scored, reused, champs, top, no_primary))
    return {"code": abbr, "name": name, "count": len(out)}

def _write_health(ok, states_ok, errors):
    health = {"last_run": stamp_now(), "scoring_version": SCORE_VERSION, "ok": bool(ok),
              "states_ok": states_ok, "errors": errors}
    try:
        with open(os.path.join(OUTDIR, "health.json"), "w") as f:
            json.dump(health, f, indent=1)
    except Exception as e:
        log("  could not write health.json:", e)

def main():
    if not LEGISCAN_KEY or not ANTHROPIC_KEY:
        raise SystemExit("Missing LEGISCAN_KEY or ANTHROPIC_API_KEY.")
    states = set(ABBR_TO_ID.keys()) if STATES_ENV.upper() == "ALL" else \
             set(s.strip().upper() for s in STATES_ENV.split(",") if s.strip())
    log("Requested states:", ", ".join(sorted(states)), "| model:", MODEL, "| scoring", SCORE_VERSION)
    os.makedirs(OUTDIR, exist_ok=True)
    chosen = latest_datasets(states)
    missing = states - set(chosen.keys())
    if missing: log("  no current dataset found for:", ", ".join(sorted(missing)))
    index = []; errors = []
    for abbr in sorted(chosen.keys()):
        try:
            r = do_state(abbr, chosen[abbr])
            if r: index.append(r)
        except Exception as e:
            log("  ERROR on %s: %s" % (abbr, e)); errors.append("%s: %s" % (abbr, str(e)[:200]))
    index.sort(key=lambda x: x["name"])
    with open(os.path.join(OUTDIR, "index.json"), "w") as f:
        json.dump({"updated": stamp_now(), "states": index}, f, indent=1)
    _write_health(len(errors) == 0 and len(index) > 0, [r["code"] for r in index], errors)
    log("\nWrote data/index.json (%d states) + data/health.json (ok=%s)." % (len(index), len(errors)==0 and len(index)>0))
    if not index:
        raise SystemExit("No states succeeded - run is visibly failed; existing data left untouched.")

if __name__ == "__main__":
    main()

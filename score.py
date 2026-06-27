#!/usr/bin/env python3
# ============================================================
# The Q Score Engine  -  The Q Collective / Doctrine Policy Group
# version history (newest first):
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
SCORE_VERSION = "v5"          # bump to force a full re-score on the next run

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
48:("WV","West Virginia"),49:("WI","Wisconsin"),50:("WY","Wyoming")}
ABBR_TO_ID = {v[0]: k for k, v in STATE_ID.items()}

# state legislature body names (default "Legislature")
LEG_BODY = {"CO":"General Assembly","CT":"General Assembly","DE":"General Assembly",
"GA":"General Assembly","IL":"General Assembly","IN":"General Assembly","IA":"General Assembly",
"KY":"General Assembly","MD":"General Assembly","MO":"General Assembly","NC":"General Assembly",
"OH":"General Assembly","PA":"General Assembly","RI":"General Assembly","SC":"General Assembly",
"TN":"General Assembly","VA":"General Assembly","VT":"General Assembly",
"MA":"General Court","NH":"General Court","OR":"Legislative Assembly","ND":"Legislative Assembly"}

STATUS = {1:"Introduced",2:"Engrossed",3:"Enrolled",4:"Passed/Enacted",5:"Vetoed",6:"Failed"}

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
    if role == "Senator": return "State Senate"
    if abbr in ("CA","NV","NY","WI"): return "State Assembly"
    if abbr in ("MD","VA","WV"): return "House of Delegates"
    return "State House"

# ---------------------------------------------------------------- LegiScan
def legiscan(op, **params):
    params["key"] = LEGISCAN_KEY; params["op"] = op
    url = "https://api.legiscan.com/?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())

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

def person_role(p):
    d = str(p.get("district","")).upper()
    if d.startswith("S"): return "Senator"
    if d.startswith("H"): return "Representative"
    r = (p.get("role") or "").lower()
    if "sen" in r: return "Senator"
    if "rep" in r: return "Representative"
    rid = p.get("role_id")
    if rid == 2: return "Senator"
    if rid == 1: return "Representative"
    return "Legislator"

def clean_district(p):
    m = re.search(r"(\d+)", str(p.get("district","")))
    return str(int(m.group(1))) if m else str(p.get("district",""))

def load_cache(path):
    try: return {str(l["id"]): l for l in json.load(open(path)).get("legislators", [])}
    except Exception: return {}

# ---------------------------------------------------------------- per state
def do_state(abbr, ds):
    name = STATE_ID[ABBR_TO_ID[abbr]][1]
    body = name + " " + LEG_BODY.get(abbr, "Legislature")
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
        p = a["person"]; nm = person_name(p); role = person_role(p)
        primary = [s for s in a["sponsored"] if s["primary"]]
        co_count = len(a["sponsored"]) - len(primary)
        if not primary: no_primary += 1
        h = record_hash(a["sponsored"], a["votes_total"])
        prior = cache.get(str(pid))
        if prior and prior.get("_h") == h and prior.get("pillar") is not None:
            pillar, impact, spons, why = prior["pillar"], prior["impact"], prior["sponsorship"], prior.get("why","")
            reused += 1
        else:
            sc = score_person(nm, role, name, primary, co_count)
            pillar, impact, spons = clamp(sc.get("pillar")), clamp(sc.get("impact")), clamp(sc.get("sponsorship"))
            why = sc.get("why",""); scored += 1; time.sleep(0.4)
        att_raw = round(100 * a["votes_cast"] / a["votes_total"]) if a["votes_total"] else 0
        att = attendance_score(att_raw)
        total = round(0.40*pillar + 0.25*att + 0.25*impact + 0.10*spons)
        bills_list = [{"number": s["number"], "title": s["title"], "status": s["status"],
                       "url": s["url"], "primary": s["primary"]} for s in a["sponsored"][:60]]
        out.append({"id": str(pid), "name": nm, "role": role,
                    "chamber": chamber_label(role, abbr), "body": body,
                    "party": p.get("party",""), "district": clean_district(p),
                    "photo": p.get("photo",""), "score": total,
                    "label": "Accountability Champion" if total >= 80 else "",
                    "pillar": pillar, "attendance": att, "attendance_raw": att_raw,
                    "impact": impact, "sponsorship": spons, "why": why, "bills": bills_list, "_h": h})
    out.sort(key=lambda x: x["score"], reverse=True)
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
    log("  %s: %d legislators (%d scored, %d cached) | %d champions (80+) | top score %d | %d had no prime-sponsored bills" %
        (abbr, len(out), scored, reused, champs, top, no_primary))
    return {"code": abbr, "name": name, "count": len(out)}

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
    index = []
    for abbr in sorted(chosen.keys()):
        try:
            r = do_state(abbr, chosen[abbr])
            if r: index.append(r)
        except Exception as e:
            log("  ERROR on %s: %s" % (abbr, e))
    index.sort(key=lambda x: x["name"])
    with open(os.path.join(OUTDIR, "index.json"), "w") as f:
        json.dump({"updated": stamp_now(), "states": index}, f, indent=1)
    log("\nWrote data/index.json with", len(index), "states.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
The Q Score Engine  -  The Q Collective / Doctrine Policy Group
-----------------------------------------------------------------
Pulls legislative sessions from LegiScan (one bulk download per state),
has Claude score every legislator on the Q Score rubric, and writes
per-state data files the website renders.  Supports all 50 states.

Rubric (legislative):
  Pillar Alignment 40%  (Claude) | Attendance 25% (computed)
  Citizen Impact   25%  (Claude) | Sponsorship 10% (Claude)
  Total 0-100;  80+ = "Accountability Champion"

CACHING: each run only re-scores legislators whose record changed
(bills sponsored + votes), so all-50-state upkeep stays cheap.

Repo secrets required:  LEGISCAN_KEY, ANTHROPIC_API_KEY
Environment options:
  STATES = "CO"  or  "CO,TX,CA"  or  "ALL"   (default ALL)
  MODEL  = claude-haiku-4-5-20251001 (default; cheap) or a Sonnet string
  LIMIT  = cap legislators per state for a test run (0 = all)
Standard library only.
"""

import os, sys, json, base64, io, zipfile, time, re, hashlib
import urllib.request, urllib.parse, urllib.error

LEGISCAN_KEY  = os.environ.get("LEGISCAN_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
STATES_ENV    = os.environ.get("STATES", "ALL").strip()
MODEL         = os.environ.get("MODEL", "claude-haiku-4-5-20251001")
LIMIT         = int(os.environ.get("LIMIT", "0"))
OUTDIR        = "data"

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
STATUS = {1:"Introduced",2:"Engrossed",3:"Enrolled",4:"Passed",5:"Vetoed",6:"Failed"}

def log(*a): print(*a, flush=True)

def clamp(v):
    try: v = int(round(float(v)))
    except Exception: return 0
    return max(0, min(100, v))

def status_text(b):
    s = b.get("status")
    try: return STATUS.get(int(s), "")
    except Exception: return ""

# ---------------------------------------------------------------- LegiScan
def legiscan(op, **params):
    params["key"] = LEGISCAN_KEY; params["op"] = op
    url = "https://api.legiscan.com/?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())

def latest_datasets(states):
    """Return {abbr: {session_id, access_key, session_name}} for the newest session per state."""
    dl = legiscan("getDatasetList")
    best = {}
    for d in dl.get("datasetlist", []):
        sid_state = d.get("state_id")
        info = STATE_ID.get(sid_state)
        if not info: continue
        abbr = info[0]
        if abbr not in states: continue
        key = (d.get("year_end", 0), 0 if d.get("special") else 1, d.get("session_id", 0))
        if abbr not in best or key > best[abbr][0]:
            best[abbr] = (key, {"session_id": d.get("session_id"),
                                "access_key": d.get("access_key"),
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
        if "/people/" in name and "person" in obj:
            p = obj["person"]; people[p.get("people_id")] = p
        elif "/bill/" in name and "bill" in obj:
            b = obj["bill"]; bills[b.get("bill_id")] = b
        elif "/vote/" in name and "roll_call" in obj:
            v = obj["roll_call"]; votes[v.get("roll_call_id")] = v
    return people, bills, votes

# ---------------------------------------------------------------- aggregate
def aggregate(people, bills, votes):
    agg = {pid: {"person": people[pid], "sponsored": [], "votes_cast": 0, "votes_total": 0}
           for pid in people}
    for b in bills.values():
        for sp in b.get("sponsors", []):
            pid = sp.get("people_id")
            if pid in agg:
                agg[pid]["sponsored"].append({
                    "bill_id": b.get("bill_id"), "number": b.get("bill_number"),
                    "title": b.get("title", ""), "desc": b.get("description", ""),
                    "status": status_text(b), "url": b.get("url") or b.get("state_link"),
                    "primary": sp.get("sponsor_type_id") == 1})
    for v in votes.values():
        for iv in v.get("votes", []):
            pid = iv.get("people_id")
            if pid in agg:
                agg[pid]["votes_total"] += 1
                if (iv.get("vote_text") or "").strip().lower() in ("yea","nay","yes","no"):
                    agg[pid]["votes_cast"] += 1
    return agg

def record_hash(sponsored, votes_total):
    key = ",".join(sorted(str(s["bill_id"]) for s in sponsored)) + "|" + str(votes_total)
    return hashlib.md5(key.encode()).hexdigest()

# ---------------------------------------------------------------- Claude
def anthropic_call(body):
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type":"application/json","x-api-key":ANTHROPIC_KEY,
                 "anthropic-version":"2023-06-01"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            log("  Anthropic HTTP", e.code, e.read()[:200].decode("utf-8","ignore")); time.sleep(3*(attempt+1))
        except Exception as e:
            log("  Anthropic error:", str(e)); time.sleep(3*(attempt+1))
    return {}

def score_person(name, role, state_name, sponsored):
    primary = sum(1 for s in sponsored if s["primary"])
    lines = "\n".join("- " + (s["title"] or s["desc"])[:160] for s in sponsored[:40]) \
            or "(no bills sponsored this session)"
    prompt = ("You are scoring a state legislator for a strictly non-partisan accountability "
        "project. Judge ONLY alignment with the seven pillars of life stability: " + PILLARS +
        ". Never consider party.\n\nLegislator: " + name + " (" + role + ", " + state_name + ")\n"
        "Bills sponsored this session (" + str(primary) + " as primary sponsor):\n" + lines +
        "\n\nRate each 0-100:\n  pillar - how strongly their sponsored bills advance the seven pillars\n"
        "  impact - how broadly their bills help everyday people\n"
        "  sponsorship - do they LEAD on pillar-aligned bills rather than just follow\n\n"
        'Respond with ONLY compact JSON: {"pillar":N,"impact":N,"sponsorship":N,"why":"one short sentence"}')
    data = anthropic_call({"model": MODEL, "max_tokens": 300,
                           "messages":[{"role":"user","content":prompt}]})
    txt = "".join(c.get("text","") for c in data.get("content",[]) if c.get("type")=="text").strip().strip("`")
    m = re.search(r"\{.*\}", txt, re.S)
    try: return json.loads(m.group(0)) if m else {}
    except Exception: return {}

# ---------------------------------------------------------------- helpers
def person_name(p):
    return p.get("name") or (str(p.get("first_name","")) + " " + str(p.get("last_name",""))).strip()

def person_role(p):
    r = (p.get("role") or "").lower()
    return "Senator" if (r.startswith("sen") or p.get("role_id") == 1) else "Representative"

def load_cache(path):
    try:
        d = json.load(open(path))
        return {str(l["id"]): l for l in d.get("legislators", [])}
    except Exception:
        return {}

# ---------------------------------------------------------------- per state
def do_state(abbr, ds):
    name = STATE_ID[ABBR_TO_ID[abbr]][1]
    log("\n=== %s (%s) session %s ===" % (name, abbr, ds["session_id"]))
    people, bills, votes = parse_dataset(fetch_dataset(ds["session_id"], ds["access_key"]))
    log("  parsed people=%d bills=%d roll_calls=%d" % (len(people), len(bills), len(votes)))
    if not people: 
        log("  no legislators - skipping"); return None
    agg = aggregate(people, bills, votes)
    cache = load_cache(os.path.join(OUTDIR, abbr + ".json"))
    items = list(agg.items())
    if LIMIT: items = items[:LIMIT]
    reused = scored = 0
    out = []
    for pid, a in items:
        p = a["person"]; nm = person_name(p); role = person_role(p)
        h = record_hash(a["sponsored"], a["votes_total"])
        prior = cache.get(str(pid))
        if prior and prior.get("_h") == h and prior.get("pillar") is not None:
            pillar, impact, spons, why = prior["pillar"], prior["impact"], prior["sponsorship"], prior.get("why","")
            reused += 1
        else:
            sc = score_person(nm, role, name, a["sponsored"])
            pillar, impact, spons = clamp(sc.get("pillar")), clamp(sc.get("impact")), clamp(sc.get("sponsorship"))
            why = sc.get("why",""); scored += 1; time.sleep(0.4)
        att = round(100 * a["votes_cast"] / a["votes_total"]) if a["votes_total"] else 0
        total = round(0.40*pillar + 0.25*att + 0.25*impact + 0.10*spons)
        bills_list = [{"number": s["number"], "title": s["title"], "status": s["status"],
                       "url": s["url"], "primary": s["primary"]} for s in a["sponsored"][:60]]
        out.append({"id": str(pid), "name": nm, "role": role, "party": p.get("party",""),
                    "district": str(p.get("district","")), "score": total,
                    "label": "Accountability Champion" if total >= 80 else "",
                    "pillar": pillar, "attendance": att, "impact": impact, "sponsorship": spons,
                    "why": why, "bills": bills_list, "_h": h})
    out.sort(key=lambda x: x["score"], reverse=True)
    recent = sorted(bills.values(), key=lambda b: b.get("status_date",""), reverse=True)[:30]
    recent = [{"number": b.get("bill_number"), "title": b.get("title"),
               "status": status_text(b), "date": b.get("status_date"),
               "url": b.get("url") or b.get("state_link")} for b in recent]
    data = {"state": abbr, "state_name": name, "session": ds["session_id"],
            "session_name": ds.get("session_name",""),
            "updated": time.strftime("%B %d, %Y at %H:%M UTC", time.gmtime()),
            "count": len(out), "legislators": out, "recent_bills": recent}
    with open(os.path.join(OUTDIR, abbr + ".json"), "w") as f:
        json.dump(data, f, indent=1)
    log("  wrote %s.json  (%d legislators: %d scored, %d reused from cache)" % (abbr, len(out), scored, reused))
    return {"code": abbr, "name": name, "count": len(out)}

def main():
    if not LEGISCAN_KEY or not ANTHROPIC_KEY:
        raise SystemExit("Missing LEGISCAN_KEY or ANTHROPIC_API_KEY.")
    if STATES_ENV.upper() == "ALL":
        states = set(ABBR_TO_ID.keys())
    else:
        states = set(s.strip().upper() for s in STATES_ENV.split(",") if s.strip())
    log("Requested states:", ", ".join(sorted(states)))
    os.makedirs(OUTDIR, exist_ok=True)
    log("Looking up newest session per state from LegiScan...")
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
        json.dump({"updated": time.strftime("%B %d, %Y at %H:%M UTC", time.gmtime()),
                   "states": index}, f, indent=1)
    log("\nWrote data/index.json with", len(index), "states.")

if __name__ == "__main__":
    main()

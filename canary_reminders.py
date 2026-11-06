"""
Canary reminders. Runs once a day from GitHub Actions (.github/workflows/canary-reminders.yml).

Checks both canaries (The Q Collective and SOVRAN) and emails the people on the
Q Collective canary list when one needs attention:
  * due soon  - 2 days before it's due
  * due       - past the renewal date, inside the grace period
  * overdue   - past the grace period (the public page shows red)

Each canary sends each kind of email at most once per signing, so nobody gets
the same reminder every day. Every email carries both canaries' status, a short
brief of what changed on the site (from the audit log), the sign-in link, and
the rule: if you're not sure, don't sign. Call Mav first.

Secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY
Optional: SOVRAN_OPEN_TO_ALL=1 once SOVRAN signing moves to the email sign-in
(until then SOVRAN reminders go to Mav only, because only he can sign it).
"""
import datetime as dt
import html
import json
import os
import sys
import urllib.request

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
RESEND_KEY = os.environ.get("RESEND_API_KEY") or ""
SEND_FROM = "The Q Collective <noreply@auth.theqcollective.org>"
REPLY_TO = "team@theqcollective.org"
MAV = ["maveriqbjackson@proton.me", "team@theqcollective.org"]
SOVRAN_OPEN = (os.environ.get("SOVRAN_OPEN_TO_ALL") or "").strip() in ("1", "true", "yes")
DRY = (os.environ.get("DRY_RUN") or "").strip() in ("1", "true", "yes")
STATE_PATH = "data/canary_reminder_state.json"
UA = "QCollective-canary-reminders/1.0"


def req(url, method="GET", headers=None, body=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode() or "null")


def parse_time(s):
    s = str(s).strip().replace(" ", "T", 1)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    t = dt.datetime.fromisoformat(s)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t


def stage(days, iv, gr):
    if days is None:
        return "never"
    if days > iv + gr:
        return "overdue"
    if days > iv:
        return "due"
    if days >= iv - 2:
        return "due_soon"
    return "ok"


def q_canary():
    sk = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY}
    d = req(SUPABASE_URL + "/rest/v1/rpc/canary_status", "POST", sk, {})
    people = req(SUPABASE_URL + "/rest/v1/canary_people?select=email,name,role", "GET", sk)
    s = (d.get("signings") or [None])[0]
    return {
        "key": "q", "name": "The Q Collective canary",
        "page": "https://theqcollective.org/canary.html",
        "sign": "https://theqcollective.org/canary-sign.html",
        "signed_at": s and s["signed_at"], "signed_by": s and s["signed_by"],
        "iv": d.get("interval_days") or 7, "gr": d.get("grace_days") or 3,
    }, [p["email"].lower() for p in people or []]


def sovran_canary():
    try:
        d = req("https://mysovran.online/api/canary")
    except Exception as e:
        print("  SOVRAN canary unreachable:", e)
        return None
    return {
        "key": "sovran", "name": "SOVRAN canary",
        "page": "https://mysovran.online/canary.html",
        "sign": "https://mysovran.online/sign.html",
        "signed_at": d.get("signed_at"), "signed_by": d.get("signed_by"),
        "iv": d.get("interval_days") or 14, "gr": d.get("grace_days") or 7,
    }


def brief(since_iso):
    """Up to 3 plain lines from the audit log since the last reminder."""
    try:
        runs = json.load(open("data/audit.json")).get("runs", [])
    except Exception:
        return []
    out = []
    for r in reversed(runs):
        if r.get("run_type") == "site_change" and r.get("note"):
            out.append((r.get("ts", ""), r["note"]))
        if len(out) >= 3:
            break
    return [f"{ts}: {note}" for ts, note in out]


LABEL = {"ok": "Signed and current", "due_soon": "Due in the next 2 days", "due": "Due now",
         "overdue": "OVERDUE (the public page shows red)", "never": "Not signed yet"}


def email(to, subject, lines_html):
    if DRY:
        print(f"  [dry run] would email {to}: {subject}")
        return
    body = {"from": SEND_FROM, "to": [to], "reply_to": REPLY_TO, "subject": subject,
            "html": "<div style=\"font-family:Arial,sans-serif;font-size:16px;line-height:1.6;color:#1a1a1a;max-width:560px\">"
                    + "".join(lines_html) + "</div>"}
    req("https://api.resend.com/emails", "POST", {"Authorization": "Bearer " + RESEND_KEY}, body)
    print("  emailed", to, "-", subject)


def main():
    if not (SUPABASE_URL and SERVICE_KEY and RESEND_KEY):
        print("Missing secrets."); sys.exit(1)
    try:
        state = json.load(open(STATE_PATH))
    except Exception:
        state = {}
    now = dt.datetime.now(dt.timezone.utc)
    q, people = q_canary()
    canaries = [q] + [c for c in [sovran_canary()] if c]
    for c in canaries:
        c["days"] = None if not c["signed_at"] else (now - parse_time(c["signed_at"])).days
        c["stage"] = stage(c["days"], c["iv"], c["gr"])

    status_html = "".join(
        f"<p style=\"margin:0 0 6px\"><b>{html.escape(c['name'])}:</b> {LABEL[c['stage']]}"
        + (f" (last signed {c['days']} day{'s' if c['days'] != 1 else ''} ago)" if c['days'] is not None else "")
        + f" &middot; <a href=\"{c['page']}\">see it</a></p>" for c in canaries)

    sent_any = False
    for c in canaries:
        if c["stage"] in ("ok",):
            continue
        tag = f"{c['signed_at']}|{c['stage']}"
        if state.get(c["key"]) == tag:
            continue
        to = people if ((c["key"] == "q" or SOVRAN_OPEN) and c["stage"] != "never") else MAV
        to = sorted(set(to + MAV))
        b = brief(state.get("last_sent"))
        first = {"due_soon": f"The {c['name']} is due in the next 2 days.",
                 "due": f"The {c['name']} is due for renewal.",
                 "overdue": f"The {c['name']} is overdue. The public page now shows red.",
                 "never": f"The {c['name']} hasn't been signed yet."}[c["stage"]]
        subject = {"due_soon": "Canary check: due soon", "due": "Canary check: due now",
                   "overdue": "Canary OVERDUE: please check now", "never": "Canary check: needs its first signing"}[c["stage"]]
        parts = [
            f"<p><b>{html.escape(first)}</b></p>",
            "<p>Please read the statement. If every word is still true today, sign it:</p>",
            f"<p><a href=\"{c['sign']}\" style=\"display:inline-block;background:#122848;color:#fff;text-decoration:none;font-weight:bold;padding:11px 18px;border-radius:6px\">Check and sign</a></p>",
            "<p style=\"background:#fdf3d4;padding:12px 14px;border-radius:6px\"><b>If you're not sure every line is still true, don't sign.</b> Call Mav first. If you've been told not to talk about something, don't sign and don't explain. Just let it lapse.</p>",
            "<p style=\"margin:18px 0 6px\"><b>Where both canaries stand</b></p>", status_html,
        ]
        if b:
            parts.append("<p style=\"margin:18px 0 6px\"><b>What changed on the site lately</b></p>")
            parts += [f"<p style=\"margin:0 0 6px;font-size:14.5px;color:#4a4a4a\">{html.escape(x)}</p>" for x in b]
        parts.append("<p style=\"margin-top:20px;font-size:13px;color:#777\">You're getting this because you're a canary signer for The Q Collective. Questions? Reply to this email or call Mav.</p>")
        for addr in to:
            email(addr, subject, parts)
        state[c["key"]] = tag
        sent_any = True
    if sent_any:
        state["last_sent"] = now.isoformat()
    if not DRY:
        json.dump(state, open(STATE_PATH, "w"), indent=1)
    for c in canaries:
        print(f"{c['name']}: {c['stage']} (days={c['days']})")


if __name__ == "__main__":
    main()

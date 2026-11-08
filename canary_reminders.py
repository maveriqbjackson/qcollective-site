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
SOVRAN reminders go to everyone on the list too (set SOVRAN_OPEN_TO_ALL=0 to send them to Mav only).
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
SOVRAN_OPEN = (os.environ.get("SOVRAN_OPEN_TO_ALL") or "1").strip() in ("1", "true", "yes")
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
        "key": "q", "name": "Q Collective canary",
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


ROW = {"ok": "Current", "due_soon": "Due soon", "due": "Due today", "overdue": "Overdue", "never": "Not signed yet"}
DOT = {"ok": "#2e7d4f", "due_soon": "#c9971c", "due": "#c9971c", "overdue": "#b23b2a", "never": "#b23b2a"}


def render(c, canaries, notes):
    """One clean, short email: what's needed, one button, the rule, both statuses."""
    e = html.escape
    first = {"due_soon": f"The {c['name']} is due in the next 2 days.",
             "due": f"The {c['name']} is due today.",
             "overdue": f"The {c['name']} is overdue. Its public page now shows red.",
             "never": f"The {c['name']} needs its first signing."}[c["stage"]]
    rows = "".join(
        f'<tr><td style="padding:7px 0;border-top:1px solid #eee9de"><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{DOT[x["stage"]]};margin-right:8px"></span>{e(x["name"])}</td>'
        f'<td style="padding:7px 0;border-top:1px solid #eee9de;text-align:right;color:#5a5a5a">{ROW[x["stage"]]}'
        + (f' &middot; {x["days"]}d ago' if x["days"] is not None else "") + "</td></tr>" for x in canaries)
    news = "".join(f'<p style="margin:0 0 6px;font-size:14px;color:#5a5a5a">{e(n)}</p>' for n in notes)
    html_out = f"""<div style="background:#F9F6F0;padding:28px 12px;font-family:-apple-system,Segoe UI,Arial,sans-serif;color:#1a1a1a">
<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #E0D5BE;border-radius:12px;overflow:hidden">
<div style="background:#122848;padding:16px 24px"><span style="font:700 24px Georgia,serif;color:#D4AF50">Q</span><span style="font:600 15px Arial,sans-serif;color:#fff;margin-left:10px">The Q Collective</span></div>
<div style="padding:26px 24px 8px">
<p style="margin:0 0 6px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#B8962E">Canary check</p>
<p style="margin:0 0 14px;font:600 21px/1.35 Georgia,serif;color:#122848">{e(first)}</p>
<p style="margin:0 0 20px;font-size:16px;line-height:1.6">Read the statement. If every word is still true today, sign it. It takes about a minute.</p>
<a href="{c['sign']}" style="display:inline-block;background:#122848;color:#fff;text-decoration:none;font-weight:700;font-size:16px;padding:13px 22px;border-radius:8px">Check and sign</a>
<p style="margin:22px 0 0;padding:12px 14px;background:#fdf3d4;border-radius:8px;font-size:14.5px;line-height:1.55"><b>Not sure every line is still true? Don't sign.</b> Call Mav first. If you've been told not to talk about something, don't sign and don't explain. Just let it lapse.</p>
<table style="width:100%;border-collapse:collapse;margin:22px 0 4px;font-size:14.5px">{rows}</table>
{('<p style="margin:18px 0 8px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#B8962E">Lately on the site</p>' + news) if news else ''}
</div>
<div style="padding:16px 24px 22px;font-size:12.5px;color:#777;line-height:1.5">You're getting this because you're a canary signer. Reply to this email with any question.<br>The Q Collective &middot; 6212 E Pine Ln, Unit 2159, Parker, CO 80138</div>
</div></div>"""
    text = (f"Canary check\n\n{first}\n\nRead the statement. If every word is still true today, sign it:\n{c['sign']}\n\n"
            "Not sure every line is still true? Don't sign. Call Mav first. If you've been told not to talk about something, don't sign and don't explain. Just let it lapse.\n\n"
            + "\n".join(f"{x['name']}: {LABEL[x['stage']]}" for x in canaries) + "\n\nThe Q Collective\n")
    return html_out, text


def email(to, subject, html_body, text_body):
    if DRY:
        print(f"  [dry run] would email {to}: {subject}")
        return
    body = {"from": SEND_FROM, "to": [to], "reply_to": REPLY_TO, "subject": subject, "html": html_body, "text": text_body}
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

    sent_any = False
    for c in canaries:
        if c["stage"] in ("ok",):
            continue
        tag = f"{c['signed_at']}|{c['stage']}"
        if state.get(c["key"]) == tag:
            continue
        to = people if ((c["key"] == "q" or SOVRAN_OPEN) and c["stage"] != "never") else MAV
        to = sorted(set(to + MAV))
        subject = {"due_soon": "Canary check: due in 2 days", "due": "Canary check: due today",
                   "overdue": "Canary overdue: please check now", "never": "Canary check: first signing"}[c["stage"]]
        h, t = render(c, canaries, [n[:150] for n in brief(state.get("last_sent"))[:2]])
        for addr in to:
            email(addr, subject, h, t)
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

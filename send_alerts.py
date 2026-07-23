#!/usr/bin/env python3
"""
THE Q COLLECTIVE — BILL ALERT SENDER
Runs in GitHub Actions right after score.py, in the same job.

What it does, in order:
  1. Reads the bill statuses the engine just wrote (data/<STATE>_bills.json).
  2. Compares them to data/alert_state.json (what we last told people).
  3. Sends a confirmation email to anyone who signed up but hasn't confirmed.
  4. Emails confirmed followers when a bill they follow has changed status.
  5. Saves the new statuses so we never send the same change twice.

Safety behaviour:
  • If the secrets aren't set yet, it prints a note and exits 0 — it will never
    fail your score run.
  • On the very first run it records a baseline and sends NO alerts, so nobody
    gets a flood of "changes" the first time.

Secrets (GitHub repository secrets):
  SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY
Optional env:
  ALERT_FROM  (default: The Q Collective <noreply@auth.theqcollective.org>)
  SITE_URL    (default: https://theqcollective.org)
  STATES      (default: CO)
"""

import json, os, sys, time, urllib.request, urllib.error, urllib.parse

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY") or ""
RESEND_KEY   = os.environ.get("RESEND_API_KEY") or ""
ALERT_FROM   = os.environ.get("ALERT_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
SITE         = (os.environ.get("SITE_URL") or "https://theqcollective.org").rstrip("/")
STATES       = [s.strip() for s in (os.environ.get("STATES") or "CO").split(",") if s.strip()]

STATE_FILE = os.path.join("data", "alert_state.json")


def log(m): print("[alerts] " + m, flush=True)


# --------------------------------------------------------------------------
# tiny HTTP helpers
# --------------------------------------------------------------------------
def _req(url, method="GET", headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            raw = resp.read().decode() or "null"
            try:
                return json.loads(raw)
            except Exception:
                return raw
    except urllib.error.HTTPError as e:
        log("HTTP %s on %s :: %s" % (e.code, url.split("?")[0], e.read().decode()[:300]))
        return None
    except Exception as e:
        log("request failed: %s" % e)
        return None


def sb(path, method="GET", body=None, prefer=None):
    h = {
        "apikey": SERVICE_KEY,
        "Authorization": "Bearer " + SERVICE_KEY,
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return _req(SUPABASE_URL + "/rest/v1/" + path, method, h, body)


def send_email(to, subject, html):
    res = _req(
        "https://api.resend.com/emails",
        "POST",
        {"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json"},
        {"from": ALERT_FROM, "to": [to], "subject": subject, "html": html},
    )
    return bool(res)


# --------------------------------------------------------------------------
# email bodies (branded to match the sign-in emails)
# --------------------------------------------------------------------------
def shell(title, intro, button_label, button_url, footer_extra=""):
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe8;padding:28px 0;font-family:Helvetica,Arial,sans-serif;"><tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #e4e0d6;border-radius:14px;overflow:hidden;">
<tr><td style="background:#122848;padding:22px 30px;"><span style="font-family:Georgia,serif;font-size:22px;font-weight:bold;color:#ffffff;">The Q Collective</span><span style="float:right;font-family:Georgia,serif;font-size:26px;font-weight:bold;color:#B8962E;">Q</span><div style="font-size:9px;letter-spacing:2px;color:#B8962E;text-transform:uppercase;margin-top:2px;">Doctrine Policy Group</div></td></tr>
<tr><td style="padding:32px 30px 10px;">
<h1 style="font-family:Georgia,serif;font-size:21px;color:#122848;margin:0 0 12px;">{title}</h1>
{intro}
<table cellpadding="0" cellspacing="0"><tr><td style="background:#B8962E;border-radius:8px;"><a href="{button_url}" style="display:inline-block;padding:13px 30px;font-size:14px;font-weight:bold;color:#122848;text-decoration:none;">{button_label}</a></td></tr></table>
</td></tr>
<tr><td style="border-top:1px solid #e4e0d6;padding:18px 30px;"><p style="font-size:11px;line-height:1.6;color:#9aa0ae;margin:0;">Nonpartisan. Citizen-powered. One standard for everyone.<br>The Q Collective LLC / Doctrine Policy Group &middot; theqcollective.org{footer_extra}</p></td></tr>
</table></td></tr></table>"""


def confirm_email(bill, token):
    url = f"{SITE}/alerts.html?do=confirm&token={urllib.parse.quote(token)}"
    intro = (f'<p style="font-size:15px;line-height:1.6;color:#2a3242;margin:0 0 22px;">'
             f'You asked to be notified when <b>{bill}</b> moves in the Colorado legislature. '
             f'Confirm below and we&rsquo;ll email you on a vote, a status change, or a hearing.</p>'
             f'<p style="font-size:13px;line-height:1.6;color:#7a808f;margin:0 0 22px;">'
             f'If you didn&rsquo;t request this, ignore this email &mdash; nothing will be sent.</p>')
    return shell(f"Confirm alerts for {bill}", intro, "Confirm alerts &rarr;", url)


def change_email(bill, title, old, new, token, state):
    url = f"{SITE}/bill.html?state={urllib.parse.quote(state)}&number={urllib.parse.quote(bill)}"
    unsub = f"{SITE}/alerts.html?do=unsubscribe&token={urllib.parse.quote(token)}"
    intro = (f'<p style="font-size:15px;line-height:1.6;color:#2a3242;margin:0 0 8px;">'
             f'<b>{bill}</b>{(" &mdash; " + title) if title else ""}</p>'
             f'<div style="background:#f2efe8;border:1px solid #e4e0d6;border-radius:9px;padding:14px 16px;margin:0 0 22px;">'
             f'<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#9aa0ae;">Was</div>'
             f'<div style="font-size:14px;color:#555;margin-bottom:8px;">{old or "not tracked"}</div>'
             f'<div style="font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#B8962E;">Now</div>'
             f'<div style="font-size:16px;color:#122848;font-weight:bold;">{new}</div></div>')
    foot = (f'<br><a href="{unsub}" style="color:#9aa0ae;">Unsubscribe from alerts for this bill</a>')
    return shell(f"{bill} just moved", intro, "See the bill &rarr;", url, foot)


# --------------------------------------------------------------------------
def load_bills():
    """{number: {'status':..., 'title':..., 'state':...}} across all states."""
    out = {}
    for st in STATES:
        p = os.path.join("data", f"{st}_bills.json")
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        bills = d.get("bills", d) if isinstance(d, dict) else d
        if isinstance(bills, dict):
            bills = list(bills.values())
        for b in bills or []:
            n = str(b.get("number") or "").strip()
            if n:
                out[n] = {"status": (b.get("status") or "").strip(),
                          "title": (b.get("title") or "").strip(),
                          "state": st}
    return out


def main():
    if not (SUPABASE_URL and SERVICE_KEY and RESEND_KEY):
        log("secrets not set yet (SUPABASE_URL / SUPABASE_SERVICE_KEY / RESEND_API_KEY) — skipping, nothing failed.")
        return 0

    now = load_bills()
    if not now:
        log("no bill data found — nothing to do.")
        return 0

    first_run = not os.path.exists(STATE_FILE)
    prev = {}
    if not first_run:
        try:
            prev = json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            prev = {}

    # ---- 1) confirmation emails for new sign-ups -------------------------
    pending = sb("bill_followers?confirm_sent=eq.false&unsubscribed=eq.false"
                 "&select=id,email,bill_number,token") or []
    sent_c = 0
    for f in pending:
        if send_email(f["email"], f"Confirm alerts for {f['bill_number']} — The Q Collective",
                      confirm_email(f["bill_number"], f["token"])):
            sb(f"bill_followers?id=eq.{f['id']}", "PATCH", {"confirm_sent": True}, "return=minimal")
            sent_c += 1
            time.sleep(0.6)
    if pending:
        log(f"confirmation emails sent: {sent_c}/{len(pending)}")

    # ---- 2) alerts for status changes ------------------------------------
    sent_a = 0
    if first_run:
        log("first run — recording a baseline, sending no change alerts.")
    else:
        changed = [n for n, v in now.items() if n in prev and prev[n] != v["status"]]
        log(f"bills with a new status: {len(changed)}")
        for n in changed:
            rows = sb("bill_followers?bill_number=eq." + urllib.parse.quote(n) +
                      "&confirmed=eq.true&unsubscribed=eq.false&select=email,token") or []
            for f in rows:
                if send_email(f["email"], f"{n} just moved — The Q Collective",
                              change_email(n, now[n]["title"], prev.get(n), now[n]["status"],
                                           f["token"], now[n]["state"])):
                    sent_a += 1
                    time.sleep(0.6)
        log(f"change alerts sent: {sent_a}")

    # ---- 3) save the new baseline ----------------------------------------
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({n: v["status"] for n, v in now.items()}, fh, indent=1, sort_keys=True)
    log(f"state saved for {len(now)} bills.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # never break the score run
        log("unexpected error, exiting cleanly: %s" % e)
        sys.exit(0)

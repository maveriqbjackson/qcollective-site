#!/usr/bin/env python3
"""
THE Q COLLECTIVE — SUNDAY UPDATE SENDER
Runs in GitHub Actions (.github/workflows/sunday-update.yml).

Three modes (set by the workflow):
  confirm  Every 6 hours. Sends a confirmation email to anyone who signed up
           and hasn't been sent one yet. Also keeps Supabase awake so the free
           plan doesn't pause it.
  recap    Sunday evening. Sends confirmations, then the weekly Sunday Update
           to every confirmed subscriber. Saves what it reported so next week
           can say what moved.
  test     Manual only. Builds this week's recap and sends it to TEST_TO
           (team@theqcollective.org) and nobody else. Changes nothing.

Safety:
  • Missing secrets -> prints a note and exits 0. Never fails a run.
  • The recap can only go out once every 5 days, even if the workflow is
    re-run by hand (set FORCE=1 to override on purpose).
  • First ever recap records a baseline, so nobody gets a fake list of
    "changes."

Secrets: SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY
"""

import datetime as dt
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SERVICE_KEY  = os.environ.get("SUPABASE_SERVICE_KEY") or ""
RESEND_KEY   = os.environ.get("RESEND_API_KEY") or ""
MODE         = (os.environ.get("MODE") or "confirm").strip().lower()
FORCE        = (os.environ.get("FORCE") or "").strip() in ("1", "true", "yes")
TEST_TO      = os.environ.get("TEST_TO") or "team@theqcollective.org"
SEND_FROM    = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
REPLY_TO     = os.environ.get("REPLY_TO") or "team@theqcollective.org"
SITE         = (os.environ.get("SITE_URL") or "https://theqcollective.org").rstrip("/")
STATE        = (os.environ.get("STATE") or "CO").strip()

# CAN-SPAM requires a real postal address in every recap.
POSTAL = ["The Q Collective LLC", "222 Wright St, Unit 102", "Lakewood, CO 80228"]

# Dates shown under "Dates to know". Only upcoming ones inside the next
# 75 days appear, so old dates fall off on their own. Add new ones here.
DATES = [
    ("2026-10-12", "Colorado mail ballots start going out"),
    ("2026-11-03", "Election Day in Colorado"),
    ("2027-01-13", "The 2027 legislative session opens"),
]

TZ = ZoneInfo("America/Denver")
STATE_FILE = os.path.join("data", "sunday_state.json")
CHAMPION = 80


def log(m):
    print("[sunday] " + m, flush=True)


def err(m):
    # Shows up as a red note on the run's page in GitHub Actions.
    print("::error title=Sunday Update::" + m.replace("\n", " "), flush=True)


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _req(url, method="GET", headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(headers or {})
    # Resend's firewall rejects Python's default User-Agent (Cloudflare 1010).
    headers.setdefault("User-Agent", "TheQCollective/1.0 (+https://theqcollective.org)")
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=40) as resp:
            raw = resp.read().decode() or "null"
            try:
                return json.loads(raw)
            except Exception:
                return raw
    except urllib.error.HTTPError as e:
        err("HTTP %s on %s :: %s" % (e.code, url.split("?")[0], e.read().decode()[:300]))
        return None
    except Exception as e:
        err("request failed: %s" % e)
        return None


def sb(path, method="GET", body=None, prefer=None):
    h = {"apikey": SERVICE_KEY, "Authorization": "Bearer " + SERVICE_KEY,
         "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return _req(SUPABASE_URL + "/rest/v1/" + path, method, h, body)


def send_email(to, subject, html_body, text_body, token=None):
    headers = {}
    if token:
        unsub = f"{SITE}/sunday.html?do=unsubscribe&token={urllib.parse.quote(token)}"
        headers["List-Unsubscribe"] = f"<{unsub}>, <mailto:{REPLY_TO}?subject=unsubscribe>"
    payload = {"from": SEND_FROM, "to": [to], "reply_to": REPLY_TO,
               "subject": subject, "html": html_body, "text": text_body}
    if headers:
        payload["headers"] = headers
    res = _req("https://api.resend.com/emails", "POST",
               {"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json"},
               payload)
    return bool(res)


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------
def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def snapshot():
    """Everything the recap reports on, pulled from this week's engine output."""
    co = load_json(os.path.join("data", f"{STATE}.json"), {}) or {}
    bills_doc = load_json(os.path.join("data", f"{STATE}_bills.json"), {}) or {}
    health = load_json(os.path.join("data", "health.json"), {}) or {}

    people = {}
    for l in co.get("legislators", []):
        people[str(l.get("id"))] = {
            "name": l.get("name", ""),
            "senate": "Senate" in (l.get("chamber") or ""),
            "party": l.get("party") or "",
            "district": str(l.get("district") or ""),
            "score": int(l.get("score") or 0),
        }

    bills = bills_doc.get("bills", bills_doc) if isinstance(bills_doc, dict) else bills_doc
    if isinstance(bills, dict):
        bills = list(bills.values())
    bill_map = {}
    for b in bills or []:
        n = str(b.get("number") or "").strip()
        if n:
            bill_map[n] = {"status": (b.get("status") or "").strip(),
                           "title": (b.get("title") or "").strip()}

    return {"people": people, "bills": bill_map,
            "last_run": health.get("last_run") or co.get("updated") or "",
            "run_ok": bool(health.get("ok", True))}


def title_for(p):
    pre = "Sen." if p["senate"] else "Rep."
    dist = ("SD " if p["senate"] else "HD ") + p["district"]
    return f"{pre} {p['name']}", dist


def avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else 0.0


PARTY_NAMES = {"D": "Democrats", "R": "Republicans", "I": "Independents",
               "U": "Unaffiliated", "L": "Libertarians", "G": "Greens"}


def build_recap(now, prev, today):
    """Returns (subject, sections) where sections is a list of (heading, [lines]).
    Lines are plain text; the HTML renderer escapes them."""
    P = now["people"]
    scores = [p["score"] for p in P.values()]
    house = [p for p in P.values() if not p["senate"]]
    senate = [p for p in P.values() if p["senate"]]

    sections = []

    # ---- freshness -------------------------------------------------------
    fresh = today.strftime("%B %-d, %Y") in (now["last_run"] or "")
    # ---- what moved ------------------------------------------------------
    moved, new_champs, lost_champs, bill_moves = [], [], [], []
    if prev:
        ps = prev.get("scores", {})
        for pid, p in P.items():
            if pid in ps and ps[pid] != p["score"]:
                moved.append((p, ps[pid], p["score"]))
                if p["score"] >= CHAMPION > ps[pid]:
                    new_champs.append(p)
                if ps[pid] >= CHAMPION > p["score"]:
                    lost_champs.append(p)
        pb = prev.get("bills", {})
        for n, b in now["bills"].items():
            if n in pb and pb[n] != b["status"]:
                bill_moves.append((n, b["title"], pb[n], b["status"]))
            elif n not in pb:
                bill_moves.append((n, b["title"], "", b["status"] or "Introduced"))

    head = []
    if not fresh:
        head.append(f"Heads up: this week's refresh hadn't finished when this went out. "
                    f"The numbers below are from the last completed run ({now['last_run']}).")
    if moved or bill_moves:
        head.append(f"{len(moved)} score change{'s' if len(moved) != 1 else ''} and "
                    f"{len(bill_moves)} bill update{'s' if len(bill_moves) != 1 else ''} this week.")
    else:
        head.append(f"Our engine checked all {len(P)} members of the Colorado General Assembly "
                    f"and found no changes this week.")
        if today.month >= 6:
            head.append("That's expected. The legislature is out of session, so the record "
                        "holds steady until the next session opens in January.")
    sections.append(("THE HEADLINE", head))

    if moved:
        lines = []
        for p, old, new in sorted(moved, key=lambda x: -abs(x[2] - x[1]))[:10]:
            t, d = title_for(p)
            arrow = "up" if new > old else "down"
            lines.append(f"{t}, {d}: {old} to {new} ({arrow} {abs(new - old)})")
        if len(moved) > 10:
            lines.append(f"...plus {len(moved) - 10} more on the Hub.")
        sections.append(("WHAT MOVED", lines))

    if new_champs or lost_champs:
        lines = []
        for p in new_champs:
            t, d = title_for(p)
            lines.append(f"New Champion: {t}, {d}, now at {p['score']}")
        for p in lost_champs:
            t, d = title_for(p)
            lines.append(f"Dropped below 80: {t}, {d}, now at {p['score']}")
        sections.append(("CHAMPION WATCH", lines))

    if bill_moves:
        lines = []
        for n, title, old, new in bill_moves[:8]:
            label = f"{n}" + (f" ({title})" if title else "")
            lines.append(f"{label}: {old + ' to ' if old else ''}{new}")
        if len(bill_moves) > 8:
            lines.append(f"...plus {len(bill_moves) - 8} more on the Hub.")
        sections.append(("BILLS ON THE MOVE", lines))

    # ---- scoreboard ------------------------------------------------------
    board = [f"Statewide average: {avg(scores)} out of 100", "",
             "By chamber:",
             f"- Senate ({len(senate)} members): {avg([p['score'] for p in senate])}",
             f"- House ({len(house)} members): {avg([p['score'] for p in house])}", "",
             "By party:"]
    parties = {}
    for p in P.values():
        parties.setdefault(p["party"] or "?", []).append(p["score"])
    for code, xs in sorted(parties.items(), key=lambda kv: -len(kv[1])):
        board.append(f"- {PARTY_NAMES.get(code, code)} ({len(xs)} members): {avg(xs)}")

    # majority note, computed so it stays true after any election
    def majority(group):
        c = {}
        for p in group:
            c[p["party"]] = c.get(p["party"], 0) + 1
        top = max(c.items(), key=lambda kv: kv[1]) if c else ("", 0)
        return top[0] if top[1] * 2 > len(group) else ""
    mh, ms = majority(house), majority(senate)
    if mh and mh == ms and len(parties) > 1:
        board += ["", f"A note on the party gap: {PARTY_NAMES.get(mh, mh)} hold the majority in "
                      f"both chambers, and majority members sponsor and pass more bills. That lifts "
                      f"the sponsorship and impact parts of the score. The rubric is the same for all "
                      f"{len(P)} members. It measures results on the seven pillars that keep a life "
                      f"stable, not party labels."]
    sections.append(("THE SCOREBOARD", board))

    # ---- champions -------------------------------------------------------
    champs = sorted([p for p in P.values() if p["score"] >= CHAMPION], key=lambda p: -p["score"])
    lines = [f"{len(champs)} legislator{'s' if len(champs) != 1 else ''} at 80 or higher:"]
    for i, p in enumerate(champs, 1):
        t, d = title_for(p)
        lines.append(f"{i}. {t}, {d}: {p['score']}")
    close = sorted([p for p in P.values() if 75 <= p["score"] < CHAMPION], key=lambda p: -p["score"])
    if close:
        t, d = title_for(close[0])
        lines.append(f"Closest to the line: {t}, {d}, at {close[0]['score']}.")
    sections.append(("THE ACCOUNTABILITY CHAMPIONS", lines))

    # ---- session numbers -------------------------------------------------
    st = {}
    for b in now["bills"].values():
        st[b["status"]] = st.get(b["status"], 0) + 1
    total = len(now["bills"])
    if total:
        law = st.get("Passed/Enacted", 0)
        failed = st.get("Failed", 0)
        vetoed = st.get("Vetoed", 0)
        other = total - law - failed - vetoed
        lines = [f"{total} bills tracked:",
                 f"- {law} became law ({round(100 * law / total)}%)",
                 f"- {failed} failed",
                 f"- {vetoed} vetoed"]
        if other:
            lines.append(f"- {other} {'died when the session ended' if today.month >= 6 else 'still in play'}")
        sections.append(("THE SESSION BY THE NUMBERS", lines))

    # ---- dates -----------------------------------------------------------
    upcoming = []
    for ds, what in DATES:
        d = dt.date.fromisoformat(ds)
        if today <= d <= today + dt.timedelta(days=75):
            upcoming.append(f"{d.strftime('%A, %B %-d')}: {what}")
    if upcoming:
        sections.append(("DATES TO KNOW", upcoming))

    sections.append(("YOUR MOVE", ["Look up your own House and Senate members: what they scored, "
                                   "what lifted them, and what held them back.", SITE]))

    subject = f"The Sunday Update: {today.strftime('%B %-d')}"
    if new_champs:
        subject += f" | {len(new_champs)} new Champion{'s' if len(new_champs) != 1 else ''}"
    elif moved:
        subject += f" | {len(moved)} score change{'s' if len(moved) != 1 else ''}"
    return subject, sections


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_text(today, sections, token):
    unsub = f"{SITE}/sunday.html?do=unsubscribe&token={token}"
    out = ["THE SUNDAY UPDATE", f"Week of {today.strftime('%B %-d, %Y')}", ""]
    for h, lines in sections:
        out += [h] + lines + [""]
    out += ["Thanks for being here. The record was always public. Now you can actually read it.", "",
            "The Q Collective Team", REPLY_TO, "", "---"] + POSTAL + [
            "", "You're getting this because you signed up for the Sunday Update at theqcollective.org.",
            f"Unsubscribe: {unsub}"]
    return "\n".join(out)


def render_html(today, sections, token):
    unsub = f"{SITE}/sunday.html?do=unsubscribe&token={urllib.parse.quote(token)}"
    body = ""
    for h, lines in sections:
        body += (f'<tr><td style="padding:22px 30px 0;"><div style="font-family:Helvetica,Arial,sans-serif;'
                 f'font-size:11px;letter-spacing:2px;color:#B8962E;font-weight:bold;">{html.escape(h)}</div>')
        for ln in lines:
            if not ln:
                body += '<div style="height:8px;"></div>'
                continue
            txt = html.escape(ln)
            if ln.startswith("http"):
                txt = f'<a href="{html.escape(ln)}" style="color:#122848;font-weight:bold;">{txt.replace("https://", "")}</a>'
            body += (f'<div style="font-family:Georgia,serif;font-size:15px;line-height:1.6;'
                     f'color:#2a3242;margin-top:4px;">{txt}</div>')
        body += "</td></tr>"
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe8;padding:28px 0;"><tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border:1px solid #e4e0d6;border-radius:14px;overflow:hidden;">
<tr><td style="background:#122848;padding:22px 30px;"><span style="font-family:Georgia,serif;font-size:22px;font-weight:bold;color:#ffffff;">The Sunday Update</span><span style="float:right;font-family:Georgia,serif;font-size:26px;font-weight:bold;color:#B8962E;">Q</span><div style="font-family:Helvetica,Arial,sans-serif;font-size:10px;letter-spacing:2px;color:#B8962E;text-transform:uppercase;margin-top:4px;">Week of {today.strftime('%B %-d, %Y')}</div></td></tr>
{body}
<tr><td style="padding:26px 30px 24px;"><div style="font-family:Georgia,serif;font-size:15px;line-height:1.6;color:#2a3242;">Thanks for being here. The record was always public. Now you can actually read it.<br><br><b>The Q Collective Team</b><br><a href="mailto:{REPLY_TO}" style="color:#122848;">{REPLY_TO}</a></div></td></tr>
<tr><td style="border-top:1px solid #e4e0d6;padding:18px 30px;"><p style="font-family:Helvetica,Arial,sans-serif;font-size:11px;line-height:1.6;color:#9aa0ae;margin:0;">Nonpartisan. Citizen-powered. One standard for everyone.<br>{"<br>".join(POSTAL)}<br><br>You're getting this because you signed up for the Sunday Update at theqcollective.org.<br><a href="{unsub}" style="color:#9aa0ae;">Unsubscribe</a></p></td></tr>
</table></td></tr></table>"""


def confirm_email(token):
    url = f"{SITE}/sunday.html?do=confirm&token={urllib.parse.quote(token)}"
    html_body = f"""<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe8;padding:28px 0;font-family:Helvetica,Arial,sans-serif;"><tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#ffffff;border:1px solid #e4e0d6;border-radius:14px;overflow:hidden;">
<tr><td style="background:#122848;padding:22px 30px;"><span style="font-family:Georgia,serif;font-size:22px;font-weight:bold;color:#ffffff;">The Q Collective</span><span style="float:right;font-family:Georgia,serif;font-size:26px;font-weight:bold;color:#B8962E;">Q</span></td></tr>
<tr><td style="padding:32px 30px 10px;">
<h1 style="font-family:Georgia,serif;font-size:21px;color:#122848;margin:0 0 12px;">One click and you're in</h1>
<p style="font-size:15px;line-height:1.6;color:#2a3242;margin:0 0 22px;">You signed up for the Sunday Update: every Sunday evening, what moved in the Colorado legislature that week, whose record changed, and the dates that matter. Confirm below and it'll start landing in your inbox.</p>
<table cellpadding="0" cellspacing="0"><tr><td style="background:#B8962E;border-radius:8px;"><a href="{url}" style="display:inline-block;padding:13px 30px;font-size:14px;font-weight:bold;color:#122848;text-decoration:none;">Confirm my subscription &rarr;</a></td></tr></table>
<p style="font-size:13px;line-height:1.6;color:#7a808f;margin:22px 0 22px;">Didn't sign up? Ignore this email and nothing else will be sent.</p>
</td></tr>
<tr><td style="border-top:1px solid #e4e0d6;padding:18px 30px;"><p style="font-size:11px;line-height:1.6;color:#9aa0ae;margin:0;">{"<br>".join(POSTAL)}</p></td></tr>
</table></td></tr></table>"""
    text = ("One click and you're in.\n\nYou signed up for the Sunday Update from The Q Collective. "
            f"Confirm here: {url}\n\nDidn't sign up? Ignore this email and nothing else will be sent.\n\n"
            + "\n".join(POSTAL))
    return html_body, text


# --------------------------------------------------------------------------
def send_confirmations():
    pending = sb("sunday_subscribers?confirm_sent=eq.false&unsubscribed=eq.false"
                 "&select=id,email,token") or []
    if not isinstance(pending, list):
        log("couldn't read the subscriber list (is Supabase paused?)")
        return
    sent = 0
    for s in pending:
        h, t = confirm_email(s["token"])
        if send_email(s["email"], "Confirm your Sunday Update", h, t):
            sb(f"sunday_subscribers?id=eq.{s['id']}", "PATCH", {"confirm_sent": True}, "return=minimal")
            sent += 1
            time.sleep(0.6)
    log(f"confirmations sent: {sent}/{len(pending)}")


def save_state(now, today):
    os.makedirs("data", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump({"last_sent": today.isoformat(),
                   "scores": {k: v["score"] for k, v in now["people"].items()},
                   "bills": {k: v["status"] for k, v in now["bills"].items()}},
                  fh, indent=1, sort_keys=True)


def run_recap(test=False):
    today = dt.datetime.now(TZ).date()
    now = snapshot()
    if not now["people"]:
        log("no score data found, nothing to send.")
        return False
    prev = load_json(STATE_FILE)

    if not test and prev and not FORCE:
        last = dt.date.fromisoformat(prev.get("last_sent", "2000-01-01"))
        if (today - last).days < 5:
            log(f"recap already went out on {last}; skipping (set FORCE=1 to override).")
            return True

    # First ever recap: compare against itself, so nobody gets fake "changes".
    subject, sections = build_recap(now, prev or {"scores": {k: v["score"] for k, v in now["people"].items()},
                                                   "bills": {k: v["status"] for k, v in now["bills"].items()}},
                                    today)

    if test:
        subject = "[TEST] " + subject
        ok = send_email(TEST_TO, subject, render_html(today, sections, "test-preview"),
                        render_text(today, sections, "test-preview"))
        log(f"test recap to {TEST_TO}: {'sent' if ok else 'FAILED'}")
        return ok

    subs = sb("sunday_subscribers?confirmed=eq.true&unsubscribed=eq.false&select=email,token") or []
    if not isinstance(subs, list):
        log("couldn't read the subscriber list; recap NOT sent, state NOT saved.")
        return False
    sent = 0
    for s in subs:
        if send_email(s["email"], subject, render_html(today, sections, s["token"]),
                      render_text(today, sections, s["token"]), token=s["token"]):
            sent += 1
            time.sleep(0.6)
    log(f"recap sent: {sent}/{len(subs)}")
    if subs and sent == 0:
        log("every send failed; state NOT saved so next run can retry.")
        return False
    save_state(now, today)
    return True


def main():
    if not (SUPABASE_URL and SERVICE_KEY and RESEND_KEY):
        log("secrets not set (SUPABASE_URL / SUPABASE_SERVICE_KEY / RESEND_API_KEY); skipping.")
        return 0
    log(f"mode: {MODE}")
    if MODE == "test":
        return 0 if run_recap(test=True) else 1
    send_confirmations()
    if MODE == "recap":
        # A failed recap turns the run red so GitHub emails you about it.
        return 0 if run_recap() else 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        err("unexpected error: %s" % e)
        # confirm runs stay quiet; a broken recap or test should be loud
        sys.exit(1 if MODE in ("recap", "test") else 0)

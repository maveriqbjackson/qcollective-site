#!/usr/bin/env python3
"""
THE Q COLLECTIVE — SCORE-CHANGE EMAILS TO LAWMAKERS
Runs in GitHub Actions right after the weekly Q Score engine (q-scores.yml).

Who gets one:
  - any lawmaker whose Q Score moved 5 or more points, or
  - any lawmaker who crossed the 80-point Accountability Champion line, up or down.
  Never more than one per lawmaker per run (the engine runs once a week).
  Changes are measured against the score in the LAST email we sent them (or
  the starting point), so a slow 2-2-2 drift is still reported once it adds up to 5.

What it says: old score to new score, which parts of the score moved, a link
to their profile, and an invitation to respond on the record ("In Their Words").

PREVIEW MODE (the default, and how it launches):
  Nothing goes to any lawmaker. Each email that WOULD go out comes to the team
  inbox instead, labeled with who it was for, plus a one-email summary.
  To go live, change PREVIEW from "1" to "0" in .github/workflows/q-scores.yml.

Safety:
  - The first run only records a starting point. Nobody is emailed about the past.
  - If the scoring rubric itself changed (a new scoring version), NOBODY is
    emailed: their score moved because we changed the yardstick, not because of
    anything they did. The new scores become the new starting point and the team
    gets a note.
  - Resigned members, missing addresses and opt-outs are skipped.
  - Addresses come only from data/<STATE>_contacts.json (the official roster).
  - Missing RESEND_API_KEY: prints what it would have sent and exits 0.

Opt-outs: a lawmaker who replies "stop" is added by id to data/official_optouts.json.

Modes (MODE env):
  weekly   (default) the real run described above
  sample   sends the team two clearly labeled made-up examples. Changes nothing.
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

RESEND_KEY = os.environ.get("RESEND_API_KEY") or ""
PREVIEW    = (os.environ.get("PREVIEW") or "1").strip() not in ("0", "false", "no")
MODE       = (os.environ.get("MODE") or "weekly").strip().lower()
STATE      = (os.environ.get("STATE") or "CO").strip()
TEAM_TO    = os.environ.get("TEAM_TO") or "team@theqcollective.org"
SEND_FROM  = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
REPLY_TO   = os.environ.get("REPLY_TO") or "team@theqcollective.org"
SITE       = (os.environ.get("SITE_URL") or "https://theqcollective.org").rstrip("/")

MOVE_POINTS = 5
CHAMPION = 80
PREVIEW_INDIVIDUAL_MAX = 10      # in preview, show up to this many full emails; the summary lists all

PARTS = (("pillar", "Pillar alignment"), ("impact", "Citizen impact"),
         ("attendance", "Attendance"), ("sponsorship", "Sponsorship"))

POSTAL = ["The Q Collective LLC", "222 Wright St, Unit 102", "Lakewood, CO 80228"]
TZ = ZoneInfo("America/Denver")

DATA = "data"
STATE_FILE = os.path.join(DATA, "official_alert_state.json")
OPTOUT_FILE = os.path.join(DATA, "official_optouts.json")


def log(m):
    print("[official-alerts] " + m, flush=True)


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)


def send(to, subject, html_body, text_body):
    if not RESEND_KEY:
        log(f"(no RESEND_API_KEY) would send to {to}: {subject}")
        return True
    payload = {"from": SEND_FROM, "to": [to], "reply_to": REPLY_TO,
               "subject": subject, "html": html_body, "text": text_body}
    req = urllib.request.Request(
        "https://api.resend.com/emails", method="POST", data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json",
                 "User-Agent": "TheQCollective/1.0 (+https://theqcollective.org)"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        print("::warning title=Lawmaker email::HTTP %s sending '%s': %s"
              % (e.code, subject, e.read().decode("utf-8", "ignore")[:200]), flush=True)
    except Exception as e:
        print("::warning title=Lawmaker email::could not send '%s': %s" % (subject, e), flush=True)
    return False


# ---------------------------------------------------------------- the email
def title(l):
    senate = "Senate" in (l.get("chamber") or "")
    return ("Senator" if senate else "Representative"), ("SD" if senate else "HD")


def build(l, old, kind):
    """kind: 'up80' | 'down80' | 'move'. old = dict with score and parts from the last email."""
    honor, dist = title(l)
    last = (l.get("name") or "").split()[-1] if l.get("name") else ""
    new = int(l.get("score") or 0)
    was = int(old.get("score") or 0)
    profile = f"{SITE}/legislator.html?state={STATE}&id={urllib.parse.quote(str(l.get('id')))}"
    reply = f"{SITE}/account.html"
    stop = (f"mailto:{REPLY_TO}?subject=" +
            urllib.parse.quote(f"Stop Q Score emails for {honor} {l.get('name', '')}"))

    if kind == "up80":
        subject = f"You're now an Accountability Champion: Q Score {new}"
        lead = (f"Congratulations. Your Q Score rose from {was} to {new}, which puts you at or above 80, "
                f"the line for Accountability Champion on The Q Collective's public scorecard.")
    elif kind == "down80":
        subject = f"Your Q Score moved below the Champion line: {was} to {new}"
        lead = (f"Your Q Score moved from {was} to {new}. That's below 80, the line for "
                f"Accountability Champion on The Q Collective's public scorecard, so the designation "
                f"no longer shows on your profile.")
    else:
        direction = "rose" if new > was else "fell"
        subject = f"Your Q Score {direction} {abs(new - was)} points: {was} to {new}"
        lead = f"Your Q Score {direction} from {was} to {new} in this week's update."

    parts = []
    for key, label in PARTS:
        a, b = old.get(key), l.get(key)
        if a is not None and b is not None and int(a) != int(b):
            parts.append(f"{label}: {int(a)} to {int(b)}")

    lines = [f"Dear {honor} {last},", "", lead, ""]
    if parts:
        lines += ["What moved:"] + [f"  - {p}" for p in parts] + [""]
    lines += [
        "Every Colorado legislator is scored on the same public rubric, built from official bill text "
        "and roll-call votes. Your full breakdown, including what lifted the score and what held it back, "
        "is on your profile:", profile, "",
        "We'd welcome your perspective. You or your office can respond on the record, and we publish "
        "responses unedited in the \"In Their Words\" section of your profile. Responses add context; "
        "they don't change the score. Verify your account here:", reply, "",
        f"Questions, or think we got something wrong? Just reply to this email and it reaches our team.", "",
        "Respectfully,", "The Q Collective", REPLY_TO, "",
    ]
    text = "\n".join(lines + ["---"] + POSTAL +
                     ["", f"You're receiving this because you serve in the Colorado General Assembly and are "
                          f"scored on The Q Collective's public Accountability Hub. To stop these emails: {stop}"])

    def p(t):
        return (f'<p style="font-family:Georgia,serif;font-size:15.5px;line-height:1.6;color:#2a3242;margin:0 0 14px;">'
                f'{t}</p>')
    body = p(html.escape(f"Dear {honor} {last},")) + p(html.escape(lead))
    if parts:
        body += ('<div style="background:#FBF6E6;border:1px solid #E0D5BE;border-left:4px solid #B8962E;border-radius:8px;'
                 'padding:12px 16px;margin:0 0 16px;font-family:Helvetica,Arial,sans-serif;font-size:14.5px;color:#122848;">'
                 '<b>What moved</b><br>' + "<br>".join(html.escape(x) for x in parts) + '</div>')
    body += p("Every Colorado legislator is scored on the same public rubric, built from official bill text and "
              "roll-call votes. Your full breakdown, including what lifted the score and what held it back, is on "
              f'your profile: <a href="{profile}" style="color:#122848;font-weight:bold;">see your profile</a>.')
    body += p("We&rsquo;d welcome your perspective. You or your office can respond on the record, and we publish "
              "responses unedited in the &ldquo;In Their Words&rdquo; section of your profile. Responses add "
              f'context; they don&rsquo;t change the score. <a href="{reply}" style="color:#122848;font-weight:bold;">'
              "Verify your account to respond</a>.")
    body += p("Questions, or think we got something wrong? Just reply to this email and it reaches our team.")
    body += p(f"Respectfully,<br><b>The Q Collective</b><br>"
              f'<a href="mailto:{REPLY_TO}" style="color:#122848;">{REPLY_TO}</a>')
    html_body = (
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe8;padding:26px 0;"><tr><td align="center">'
        '<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#fff;'
        'border:1px solid #e4e0d6;border-radius:12px;overflow:hidden;">'
        '<tr><td style="background:#122848;padding:18px 28px;"><span style="font-family:Georgia,serif;font-size:19px;'
        'font-weight:bold;color:#fff;">The Q Collective</span><span style="float:right;font-family:Georgia,serif;'
        f'font-size:22px;font-weight:bold;color:#B8962E;">Q</span></td></tr><tr><td style="padding:26px 28px 8px;">{body}</td></tr>'
        '<tr><td style="border-top:1px solid #e4e0d6;padding:16px 28px;"><p style="font-family:Helvetica,Arial,sans-serif;'
        'font-size:11px;line-height:1.6;color:#9aa0ae;margin:0;">' + "<br>".join(POSTAL) +
        "<br><br>You're receiving this because you serve in the Colorado General Assembly and are scored on The Q "
        f'Collective&rsquo;s public Accountability Hub. <a href="{stop}" style="color:#9aa0ae;">Stop these emails</a>.'
        '</p></td></tr></table></td></tr></table>')
    return subject, html_body, text


def snapshot_of(l):
    d = {"score": int(l.get("score") or 0)}
    for key, _ in PARTS:
        if l.get(key) is not None:
            d[key] = int(l[key])
    return d


def classify(old, new_score):
    was = int(old.get("score") or 0)
    if was < CHAMPION <= new_score:
        return "up80"
    if was >= CHAMPION > new_score:
        return "down80"
    if abs(new_score - was) >= MOVE_POINTS:
        return "move"
    return None


# ---------------------------------------------------------------- runs
def team_summary(rows, note=""):
    stamp = dt.datetime.now(TZ).strftime("%B %-d, %Y")
    mode = "PREVIEW (nothing went to lawmakers)" if PREVIEW else "LIVE"
    lines = [f"Score-change emails, {stamp}. Mode: {mode}.", ""]
    if note:
        lines += [note, ""]
    if rows:
        lines += [f"{len(rows)} lawmaker{'s' if len(rows) != 1 else ''} qualified "
                  f"(moved {MOVE_POINTS}+ points or crossed {CHAMPION}):", ""]
        lines += [f"- {r}" for r in rows]
    else:
        lines += [f"Nobody moved {MOVE_POINTS}+ points or crossed {CHAMPION} this week, so no emails."]
    if PREVIEW:
        lines += ["", "To go live, change PREVIEW from \"1\" to \"0\" in .github/workflows/q-scores.yml."]
    text = "\n".join(lines)
    h = "".join(f'<div style="font-family:Georgia,serif;font-size:15px;line-height:1.6;color:#2a3242;">'
                f'{html.escape(x) if x else "&nbsp;"}</div>' for x in lines)
    # "[TEST ...]" labels reach the team inbox reliably (Oct 2026).
    send(TEAM_TO, f"[TEST SUMMARY] Lawmaker score-change emails: {len(rows)} this week", h, text)


def run_weekly():
    co = load(os.path.join(DATA, f"{STATE}.json"), {}) or {}
    L = co.get("legislators", [])
    if not L:
        log("no score data; nothing to do.")
        return 0
    contacts = (load(os.path.join(DATA, f"{STATE}_contacts.json"), {}) or {}).get("contacts", {})
    optouts = set(str(x) for x in (load(OPTOUT_FILE, []) or []))
    state = load(STATE_FILE, None)
    version = co.get("scoring_version") or ""

    if not state or not state.get("baseline"):
        save(STATE_FILE, {"scoring_version": version, "baseline": {str(l["id"]): snapshot_of(l) for l in L}})
        log("first run: recorded a starting point for every lawmaker. Nobody emailed.")
        return 0

    base = state["baseline"]
    if state.get("scoring_version") and version and state["scoring_version"] != version:
        save(STATE_FILE, {"scoring_version": version, "baseline": {str(l["id"]): snapshot_of(l) for l in L}})
        team_summary([], note=(f"The scoring rubric changed ({state['scoring_version']} to {version}). Scores that "
                               f"moved because of the rubric are not something lawmakers did, so nobody was emailed. "
                               f"The new scores are the new starting point."))
        log("scoring version changed: re-based, nobody emailed.")
        return 0

    rows, shown = [], 0
    for l in L:
        lid = str(l.get("id"))
        if lid not in base:
            base[lid] = snapshot_of(l)          # new member: start tracking, no email
            continue
        kind = classify(base[lid], int(l.get("score") or 0))
        if not kind:
            continue
        c = contacts.get(lid) or {}
        honor, dist = title(l)
        who = f"{honor} {l.get('name')} ({dist} {l.get('district')})"
        moved = f"{base[lid].get('score')} to {l.get('score')}"
        if c.get("resigned"):
            rows.append(f"{who}: {moved}. Skipped, resigned.")
        elif not c.get("email"):
            rows.append(f"{who}: {moved}. Skipped, no address on file.")
        elif lid in optouts:
            rows.append(f"{who}: {moved}. Skipped, asked not to get these.")
        else:
            subject, h, t = build(l, base[lid], kind)
            if PREVIEW:
                ok = True
                if shown < PREVIEW_INDIVIDUAL_MAX:
                    ok = send(TEAM_TO, f"[TEST PREVIEW for {c['email']}] {subject}", h, t)
                    shown += 1
                    time.sleep(1.0)
                rows.append(f"{who}: {moved}. Would email {c['email']}.")
            else:
                ok = send(c["email"], subject, h, t)
                time.sleep(1.0)
                rows.append(f"{who}: {moved}. {'Emailed' if ok else 'SEND FAILED to'} {c['email']}.")
                if not ok:
                    continue                    # keep the old starting point so it retries next week
        base[lid] = snapshot_of(l)              # measure the next change from here
    state["baseline"], state["scoring_version"] = base, version or state.get("scoring_version", "")
    save(STATE_FILE, state)
    team_summary(rows)
    log(f"{len(rows)} qualified; preview={PREVIEW}")
    return 0


def run_sample():
    co = load(os.path.join(DATA, f"{STATE}.json"), {}) or {}
    L = sorted(co.get("legislators", []), key=lambda l: -(l.get("score") or 0))
    if len(L) < 2:
        log("no data for samples")
        return 1
    champ = dict(L[0])
    old_c = snapshot_of(champ); old_c["score"] = CHAMPION - 3
    if "pillar" in old_c: old_c["pillar"] = max(0, old_c["pillar"] - 7)
    mover = dict(L[len(L) // 2])
    old_m = snapshot_of(mover); old_m["score"] = old_m["score"] - 6
    if "impact" in old_m: old_m["impact"] = max(0, old_m["impact"] - 9)
    for l, old, kind in ((champ, old_c, "up80"), (mover, old_m, "move")):
        subject, h, t = build(l, old, kind)
        banner = ('<div style="background:#b3261e;color:#fff;font-family:Helvetica,Arial,sans-serif;font-size:13px;'
                  'padding:10px 14px;text-align:center;">SAMPLE ONLY. The numbers are made up to show the format. '
                  'Nothing was sent to any lawmaker.</div>')
        send(TEAM_TO, f"[TEST SAMPLE] {subject}", banner + h,
             "SAMPLE ONLY. The numbers are made up to show the format. Nothing was sent to any lawmaker.\n\n" + t)
        time.sleep(1.0)
    log("samples sent to the team")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run_sample() if MODE == "sample" else run_weekly())
    except Exception as e:
        print("::error title=Lawmaker emails::unexpected error: %s" % e, flush=True)
        sys.exit(1)

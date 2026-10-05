#!/usr/bin/env python3
"""
THE Q COLLECTIVE — FAILURE ALERT
Runs in GitHub Actions only when a step before it has failed.
Sends one plain email to the team so nobody has to find out from the website.

Needs: RESEND_API_KEY (already a repository secret; the bill alerts and the
Sunday Update use the same one).

Environment:
  WHAT       what broke, in a few words ("The Q Score engine")
  RUN_URL    link to the failed run on GitHub
  ALERT_TO   who gets the email (default team@theqcollective.org)
  Q_ERROR_FILE / RUNNER_TEMP/q_error.txt   private technical detail, if the
             failing script left any

Never fails the run on its own: if the email can't go out it says so in the
log and exits 0, so the real failure stays the headline.
"""

import html
import json
import os
import sys
import urllib.error
import urllib.request

RESEND_KEY = os.environ.get("RESEND_API_KEY") or ""
ALERT_TO   = os.environ.get("ALERT_TO") or "team@theqcollective.org"
SEND_FROM  = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
WHAT       = os.environ.get("WHAT") or "A scheduled job"
RUN_URL    = os.environ.get("RUN_URL") or ""
SITE       = (os.environ.get("SITE_URL") or "https://theqcollective.org").rstrip("/")


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def detail():
    path = os.environ.get("Q_ERROR_FILE") or os.path.join(os.environ.get("RUNNER_TEMP") or ".", "q_error.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()[:1500]
    except Exception:
        return ""


def main():
    health = load(os.path.join("data", "health.json"))
    last_good = (health.get("last_success") or "").strip()
    reason = "; ".join(health.get("errors") or []) if health.get("ok") is False else ""
    tech = detail()

    lines = [f"{WHAT} failed.", ""]
    if reason:
        lines += ["What happened: " + reason, ""]
    if last_good:
        lines += [f"The site is still showing the last good scores, from {last_good}.",
                  "Visitors see a short notice that we hit a mild glitch and are on it. "
                  "It clears by itself after the next good run.", ""]
    lines += ["What to do: open the run, read the red step, then press Re-run. "
              "If it fails twice, forward this email to whoever is helping you fix it.", ""]
    if RUN_URL:
        lines += ["The run: " + RUN_URL, ""]
    if tech:
        lines += ["Technical detail:", tech, ""]
    lines += ["Sent automatically by the site. Nobody else received this."]
    text = "\n".join(lines)

    body = "".join(
        '<div style="height:10px;"></div>' if not ln else
        f'<div style="font-family:Georgia,serif;font-size:15px;line-height:1.6;color:#2a3242;">'
        f'{html.escape(ln)}</div>' for ln in lines)
    html_body = (f'<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2efe8;padding:24px 0;">'
                 f'<tr><td align="center"><table width="560" cellpadding="0" cellspacing="0" '
                 f'style="max-width:560px;width:100%;background:#fff;border:1px solid #e4e0d6;border-left:5px solid #B8962E;'
                 f'border-radius:10px;"><tr><td style="padding:24px 28px;">{body}</td></tr></table></td></tr></table>')

    if not RESEND_KEY:
        print("[alert] RESEND_API_KEY is not set, so no email went out. Message was:\n" + text, flush=True)
        return 0

    req = urllib.request.Request(
        "https://api.resend.com/emails", method="POST",
        data=json.dumps({"from": SEND_FROM, "to": [ALERT_TO], "subject": f"Needs you: {WHAT} failed",
                         "html": html_body, "text": text}).encode(),
        headers={"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json",
                 # Resend's firewall rejects Python's default User-Agent.
                 "User-Agent": "TheQCollective/1.0 (+https://theqcollective.org)"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            r.read()
        print(f"[alert] failure email sent to {ALERT_TO}", flush=True)
    except urllib.error.HTTPError as e:
        print("::warning title=Failure alert::could not send the alert email: HTTP %s %s"
              % (e.code, e.read().decode("utf-8", "ignore")[:200]), flush=True)
    except Exception as e:
        print("::warning title=Failure alert::could not send the alert email: %s" % e, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

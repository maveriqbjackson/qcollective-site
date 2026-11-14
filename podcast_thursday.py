"""Power Back Weekly, Thursday episodes: Mav in his own voice.

Runs Thursday at 6 AM Mountain (GitHub Actions, "Power Back Weekly: Thursday episode").
Mav writes and records each episode in Ash HQ → The Q Collective → Podcast. Ash HQ only hands the episode
over once it's recorded, it's that Thursday (or later), and it isn't marked "skip". This script levels the
audio, adds it to the podcast feed (Apple Podcasts, Spotify and YouTube pick it up within hours), writes its
Q Notes post, and emails team@ and Mav that it's live. If it isn't ready, it does nothing.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import urllib.request
from zoneinfo import ZoneInfo

import podcast_lib as P

HQ = (os.environ.get("HQ_ORIGIN") or "https://aetherandash.digital").rstrip("/")
RESEND_KEY = os.environ.get("RESEND_API_KEY") or ""
SEND_FROM = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
TO = ["team@theqcollective.org", "maveriqbjackson@proton.me"]


def log(s):
    print("[thursday]", s, flush=True)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "QCollective-podcast/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def main():
    date = (os.environ.get("EP_DATE") or "").strip() or dt.datetime.now(ZoneInfo("America/Denver")).date().isoformat()
    eid = f"thu-{date}"
    d = P.load()
    if any(e["id"] == eid for e in d["episodes"]) and os.environ.get("FORCE") != "1":
        log(f"{eid} is already published; nothing to do.")
        return
    code, body = get(f"{HQ}/api/podcast/thursday?date={date}")
    if code != 200:
        log(f"{date}: not ready in Ash HQ (not recorded, skipped, or no script). Nothing posted.")
        return
    ep = json.loads(body)
    code, audio = get(f"{HQ}/api/podcast/thursday?date={date}&audio=1")
    if code != 200 or len(audio) < 20000:
        log(f"{date}: the recording couldn't be downloaded ({code}). Nothing posted.")
        return
    os.makedirs(os.path.join(P.DIR, "episodes"), exist_ok=True)
    out = os.path.join(P.DIR, "episodes", f"{eid}.mp3")
    with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as f:
        f.write(audio)
        raw = f.name
    P.level(raw, out)
    os.remove(raw)
    P.add_episode(d, eid=eid, kind="thursday", title=ep["title"], date=date, summary=ep.get("summary") or "", audio_path=out, script=ep.get("script") or "")
    P.save(d)
    secs = P.seconds(out)
    log(f"published {eid}: {ep['title']} ({secs // 60}:{secs % 60:02d})")
    if RESEND_KEY:
        html = (f"<p><b>{ep['title']}</b> is live on Power Back Weekly ({secs // 60} min).</p>"
                f"<p><a href='{P.SITE}/podcast.html#{eid}'>Podcast page</a> · <a href='{P.SITE}/notes/pbw-{eid}.html'>Q Notes post</a></p>"
                "<p>Apple Podcasts, Spotify and YouTube pick it up from the feed within a few hours.</p>")
        req = urllib.request.Request("https://api.resend.com/emails", method="POST",
                                     data=json.dumps({"from": SEND_FROM, "to": TO, "reply_to": "team@theqcollective.org",
                                                      "subject": f"Live: {ep['title']}", "html": html}).encode(),
                                     headers={"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json", "User-Agent": "QCollective-podcast/1.0"})
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            log(f"email didn't go out: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"failed: {e}")
        sys.exit(1)

"""Power Back Weekly bonus episodes.

Run from GitHub → Actions → "Power Back Weekly: bonus episode" → Run workflow.

  mode = draft     Writes a short episode from ONE source on our own site (a bill number like HB26-1001,
                   or a page like cesa-explained.html), reads it with the AI voice after Mav's opening,
                   and saves it to podcast/drafts/. Emails team@ a link to listen plus the full script.
                   Nothing goes in the podcast feed.
  mode = publish   Puts that draft in the feed (Apple Podcasts, Spotify and YouTube pick it up within hours).
  mode = trailer   Makes the show trailer (fixed script) as a draft.

The script is written only from the source text we hand it. It never takes sides on candidates or parties.
"""
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import tempfile
import urllib.request

import podcast_lib

SITE = podcast_lib.SITE
CF_AI_TOKEN = os.environ.get("CF_AI_TOKEN") or ""
CF_ACCOUNT = os.environ.get("CF_ACCOUNT_ID") or ""
RESEND_KEY = os.environ.get("RESEND_API_KEY") or ""
MODE = (os.environ.get("MODE") or "draft").strip()
SOURCE = (os.environ.get("SOURCE") or "").strip()
TITLE = (os.environ.get("TITLE") or "").strip()
NOTE = (os.environ.get("NOTE") or "").strip()[:600]
DRAFT = (os.environ.get("DRAFT") or "").strip()
# Drafts go to team@ and Mav's own inbox; sent from the same verified address as the Sunday Update.
TEAM = ["team@theqcollective.org", "maveriqbjackson@proton.me"]
SEND_FROM = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
DRAFTS = os.path.join(podcast_lib.DIR, "drafts")
EPDIR = os.path.join(podcast_lib.DIR, "episodes")

TRAILER = (
    "Power Back Weekly is the Colorado record, read out loud. "
    "Every Sunday we walk through what your lawmakers actually did that week: the bills that moved, the votes that counted, "
    "and whose Q Score went up or down, and why. No spin and no sides. Just the public record, in plain English, in about ten minutes. "
    "When something big moves in between, like a bill heading to the governor or a change in the law that touches your paycheck, "
    "your rent or your rights, you'll get a short bonus episode. "
    "Every fact in every episode links back to the record at the q collective dot org, so you never have to take our word for it. "
    "Hit follow, and we'll see you Sunday. This is Power Back Weekly, from The Q Collective."
)


def log(m):
    print(f"[bonus] {m}", flush=True)


def cf(model, payload, raw=False):
    r = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{model}",
                               data=json.dumps(payload).encode(), method="POST",
                               headers={"Authorization": "Bearer " + CF_AI_TOKEN, "Content-Type": "application/json",
                                        "User-Agent": "QCollective-podcast/1.0"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        body, ct = resp.read(), resp.headers.get("content-type", "")
    if raw and "json" not in ct:
        return body
    j = json.loads(body.decode() or "{}")
    return j.get("result")


def source_text(src):
    """Returns (label, text, link) for a bill number or a page on our site. Only our own published material."""
    m = re.fullmatch(r"(HB|SB|HJR|SJR|HR|SR|HCR|SCR)\s*-?\s*(?:\d\d-)?(\d{3,4})", src.upper())
    if m:
        num = m.group(1) + m.group(2)
        bills = json.load(open("data/CO_bills.json"))["bills"]
        b = bills.get(num)
        if not b:
            sys.exit(f"No bill {num} in data/CO_bills.json.")
        hist = "\n".join(f"{h['date']}: {h['action']}" for h in b.get("history", [])[-12:])
        spons = ", ".join(s.get("name", "") if isinstance(s, dict) else str(s) for s in b.get("sponsors", [])[:8])
        text = (f"Bill {num}: {b.get('title')}\nWhat it says it does: {b.get('description')}\n"
                f"Status: {b.get('status')} as of {b.get('status_date')}\nSponsors: {spons}\nRecent history:\n{hist}")
        return f"{num}: {b.get('title')}", text, f"{SITE}/bill.html?number={num}&state=CO"
    page = os.path.basename(src)
    if not page.endswith(".html") or not os.path.exists(page):
        sys.exit(f"SOURCE must be a bill number (like HB26-1001) or a page on the site (like cesa-explained.html). Got: {src!r}")
    raw = open(page, encoding="utf-8").read()
    raw = re.sub(r"(?is)<(script|style|nav|footer|head)\b.*?</\1>", " ", raw)
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    t = re.sub(r"\s+", " ", t).strip()[:14000]
    title = re.search(r"(?is)<title>(.*?)</title>", open(page, encoding="utf-8").read())
    return (html.unescape(title.group(1)).split("|")[0].strip() if title else page), t, f"{SITE}/{page}"


def write_script(label, text):
    system = ("You write scripts for Power Back Weekly, a nonpartisan podcast from The Q Collective about what "
              "Colorado lawmakers do. The script is read aloud by a voice right after the host's opening, which ends "
              "with 'Here's what moved this week.' Rules: use ONLY facts in the SOURCE. Never add numbers, names, "
              "dates or claims that are not in it. Never say whether anyone should vote for or against a candidate or party. "
              "Plain spoken English, short sentences, no lists, no headings, no URLs, no stage directions. "
              "Say bill numbers the way people say them (House Bill twenty-six dash ten-oh-one). "
              "450 to 650 words. End with: 'Every detail is at the q collective dot org. This has been a Power Back Weekly bonus. See you Sunday.'")
    user = f"Episode subject: {label}\n" + (f"Producer note: {NOTE}\n" if NOTE else "") + f"SOURCE:\n{text}"
    res = cf("@cf/meta/llama-3.3-70b-instruct-fp8-fast",
             {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
              "max_tokens": 1400, "temperature": 0.3})
    s = (res or {}).get("response") if isinstance(res, dict) else None
    if not s or len(s.split()) < 120:
        sys.exit("The writer model didn't return a usable script. Try again.")
    return s.strip()


def speak(script, out):
    chunks, rest = [], script
    while rest:
        cut = len(rest) if len(rest) <= 1800 else max(rest.rfind(". ", 0, 1800) + 1, 900)
        chunks.append(rest[:cut].strip()); rest = rest[cut:].strip()
    audio = b""
    for c in chunks:
        body = cf("@cf/deepgram/aura-1", {"text": c, "speaker": "asteria", "encoding": "mp3"}, raw=True)
        if isinstance(body, str):
            body = base64.b64decode(body)
        elif isinstance(body, dict):
            body = base64.b64decode(body.get("audio", ""))
        audio += body
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio); tmp = f.name
    podcast_lib.stitch(tmp, out)
    os.remove(tmp)


def email(subject, html_body):
    if not RESEND_KEY:
        log("no RESEND_API_KEY; skipping the email.")
        return
    r = urllib.request.Request("https://api.resend.com/emails", method="POST",
                               data=json.dumps({"from": SEND_FROM, "to": TEAM, "reply_to": "team@theqcollective.org",
                                                "subject": subject, "html": html_body}).encode(),
                               headers={"Authorization": "Bearer " + RESEND_KEY, "Content-Type": "application/json",
                                        "User-Agent": "QCollective-podcast/1.0"})
    try:
        urllib.request.urlopen(r, timeout=30).read()
        log(f"emailed {', '.join(TEAM)}")
    except Exception as e:
        log(f"email failed: {e}")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "episode"


def draft(trailer=False):
    if not (CF_AI_TOKEN and CF_ACCOUNT):
        sys.exit("CF_AI_TOKEN / CF_ACCOUNT_ID are missing, so there's no voice to read it.")
    today = dt.datetime.now(podcast_lib.TZ).date()
    if trailer:
        label, script, link = "Trailer: this is Power Back Weekly", TRAILER, podcast_lib.SHOW["page"]
        eid = "trailer"
    else:
        if not SOURCE:
            sys.exit("Give a SOURCE: a bill number or a page on the site.")
        label, text, link = source_text(SOURCE)
        script = write_script(label, text)
        eid = f"bonus-{today.isoformat()}-{slug(label)}"
    os.makedirs(DRAFTS, exist_ok=True)
    mp3 = os.path.join(DRAFTS, eid + ".mp3")
    speak(script, mp3)
    meta = {"id": eid, "type": "trailer" if trailer else "bonus", "title": TITLE or label, "date": today.isoformat(),
            "summary": (("The trailer. " if trailer else "Bonus episode: ") + (TITLE or label) +
                        ". From the public record, with every detail at " + link),
            "script": script, "source": link}
    json.dump(meta, open(os.path.join(DRAFTS, eid + ".json"), "w"), indent=1, ensure_ascii=False)
    mins = max(1, round(podcast_lib.seconds(mp3) / 60))
    log(f"draft saved: {mp3} (about {mins} min)")
    listen = f"{SITE}/{mp3}"
    email(f"[DRAFT] Power Back Weekly: {meta['title']}",
          f"<p>A {'trailer' if trailer else 'bonus episode'} is ready for your ear (about {mins} min). It is <b>not</b> in the podcast feed yet.</p>"
          f"<p><a href=\"{html.escape(listen)}\">&#9654; Listen to the draft</a></p>"
          f"<p>To publish it: GitHub → Actions → <b>Power Back Weekly: bonus episode</b> → Run workflow → mode <b>publish</b>, "
          f"draft <code>{html.escape(eid)}</code>. Or tell Claude <i>go live on {html.escape(eid)}</i>.</p>"
          f"<p>Source: <a href=\"{html.escape(link)}\">{html.escape(link)}</a></p><hr><p style=\"white-space:pre-wrap\">{html.escape(script)}</p>")
    print(f"::notice title=Draft ready::{listen}", flush=True)


def publish():
    if not DRAFT:
        sys.exit("Give the DRAFT id from the draft email.")
    meta_p = os.path.join(DRAFTS, DRAFT + ".json")
    mp3 = os.path.join(DRAFTS, DRAFT + ".mp3")
    if not (os.path.exists(meta_p) and os.path.exists(mp3)):
        sys.exit(f"No draft called {DRAFT}.")
    meta = json.load(open(meta_p))
    os.makedirs(EPDIR, exist_ok=True)
    final = os.path.join(EPDIR, DRAFT + ".mp3")
    os.replace(mp3, final)
    os.remove(meta_p)
    pod = podcast_lib.load()
    podcast_lib.add_episode(pod, eid=meta["id"], kind=meta["type"], title=meta["title"], date=meta["date"],
                            summary=meta["summary"], audio_path=final, script=meta.get("script", ""))
    podcast_lib.save(pod)
    log(f"published {meta['id']} to the feed")
    print(f"::notice title=Published::{meta['title']} is in the Power Back Weekly feed.", flush=True)


if __name__ == "__main__":
    {"draft": lambda: draft(False), "trailer": lambda: draft(True), "publish": publish}.get(MODE, lambda: sys.exit(f"Unknown mode {MODE}"))()

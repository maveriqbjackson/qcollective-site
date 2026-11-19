"""Power Back Weekly, The Q Collective's podcast.

Shared by the Sunday Update (weekly episodes) and podcast_bonus.py (bonus episodes).

  podcast/episodes.json   every published episode, newest first, plus the Apple / Spotify links
  podcast/feed.xml        the podcast feed that Apple Podcasts and Spotify read
  podcast/intro.mp3       Mav's own opening, recorded in Ash HQ and fetched fresh before every episode
                          (aetherandash.digital/api/podcast/intro); silence at both ends is trimmed
  podcast/episodes/       the episode audio files
  podcast/drafts/         bonus episodes waiting for Mav's OK (never in the feed)
  notes/pbw-<id>.html     the auto blog: every published episode becomes a written Q Notes post
                          (summary, player and the full transcript), and a card on notes.html

Everything is hosted on theqcollective.org itself: no podcast host, no ad network, no listener tracking.
"""
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import tempfile
from email.utils import format_datetime
from zoneinfo import ZoneInfo
import hq_outbox

SITE = (os.environ.get("SITE_URL") or "https://theqcollective.org").rstrip("/")
DIR = "podcast"
EPISODES = os.path.join(DIR, "episodes.json")
FEED = os.path.join(DIR, "feed.xml")
INTRO = os.path.join(DIR, "intro.mp3")
TZ = ZoneInfo("America/Denver")

SHOW = {
    "title": "Power Back Weekly",
    "author": "The Q Collective",
    "owner": "The Q Collective",
    "email": "team@theqcollective.org",
    "language": "en-us",
    "category": ("Government", None),
    "category2": ("News", "Politics"),
    "summary": ("The record, read out loud. Every Sunday, Power Back Weekly walks through what your "
                "lawmakers actually did that week: the votes, the bills that moved, and whose record changed, "
                "straight from the public record and in plain English. Every Thursday, founder maveriQ B Jackson, "
                "in his own voice, on what it means and what you can do about it. Special Session episodes drop when "
                "something big moves, and On the Record brings lawmakers and Coloradans on the show. "
                "From The Q Collective, a nonpartisan, citizen-powered accountability project. "
                "Sunday episodes open with Mav and are read by an AI voice from our published data; "
                "every fact links back to the record at theqcollective.org."),
    "page": f"{SITE}/podcast.html",
    "cover": f"{SITE}/podcast/cover.jpg",
}


def load():
    try:
        with open(EPISODES) as f:
            d = json.load(f)
    except (FileNotFoundError, ValueError):
        d = {}
    d.setdefault("links", {"apple": None, "spotify": None, "youtube": None})
    d.setdefault("episodes", [])
    return d


def save(d):
    os.makedirs(DIR, exist_ok=True)
    d["episodes"].sort(key=lambda e: (e["date"], e.get("published", "")), reverse=True)
    with open(EPISODES, "w") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
        f.write("\n")
    build_feed(d)
    build_posts(d)


def seconds(path):
    """Length of an mp3 in whole seconds (ffprobe), or a size-based guess."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return int(round(float(out)))
    except Exception:
        return int(os.path.getsize(path) / 16000)


def stitch(body_path, out_path):
    """Mav's opening (if recorded) + a short beat + the AI-read body, leveled to podcast loudness.
    Falls back to the body alone if ffmpeg or the intro isn't there."""
    have_intro = os.path.exists(INTRO)
    if not shutil.which("ffmpeg"):
        shutil.copyfile(body_path, out_path)
        return have_intro and False
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        if have_intro:
            parts += [INTRO, "SILENCE"]
        parts.append(body_path)
        inputs, filt, n = [], [], 0
        for p in parts:
            if p == "SILENCE":
                inputs += ["-f", "lavfi", "-t", "0.6", "-i", "anullsrc=r=44100:cl=mono"]
            else:
                inputs += ["-i", p]
            trim = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,") if p == INTRO else ""
            filt.append(f"[{n}:a]{trim}aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono[a{n}]")
            n += 1
        # Join first, then level the whole episode once (leveling a silent gap on its own breaks the encoder).
        filt.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[out]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
               "-map", "[out]", "-ac", "1", "-ar", "44100", "-b:a", "96k", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            print("[podcast] ffmpeg failed, using the body alone:", r.stderr[-400:], flush=True)
            shutil.copyfile(body_path, out_path)
            return False
    return have_intro


def level(in_path, out_path):
    """Mav's own recording (any format a phone or browser makes) -> a leveled podcast mp3, silence trimmed at both ends."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed")
    trim = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB,areverse,")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-af",
           trim + "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=mono,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100",
           "-ac", "1", "-ar", "44100", "-b:a", "96k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr[-400:])


def _vtt_time(t):
    t = max(0.0, float(t or 0)); h = int(t // 3600); m = int(t % 3600 // 60); s_ = t % 60
    return f"{h:02d}:{m:02d}:{s_:06.3f}"


def make_transcript(eid, audio_path, script=""):
    """Captions for podcast apps. First choice: a timed transcript (WebVTT) heard from the actual recording
    (Cloudflare Workers AI, Whisper). If that isn't available, a plain-text transcript from the saved script.
    Returns (relative path, MIME type) or (None, None)."""
    import base64
    import urllib.request
    os.makedirs(os.path.join(DIR, "transcripts"), exist_ok=True)
    tok, acct = os.environ.get("CF_AI_TOKEN") or "", os.environ.get("CF_ACCOUNT_ID") or ""
    if tok and acct:
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                small = f.name
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio_path, "-ac", "1", "-ar", "16000", "-b:a", "32k", small], check=True, timeout=600)
            body = json.dumps({"audio": base64.b64encode(open(small, "rb").read()).decode()}).encode()
            os.remove(small)
            req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/openai/whisper-large-v3-turbo", data=body, method="POST",
                                         headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json", "User-Agent": "QCollective-podcast/1.0"})
            with urllib.request.urlopen(req, timeout=300) as r:
                res = (json.loads(r.read()) or {}).get("result") or {}
            vtt = res.get("vtt") or ""
            if not vtt and res.get("segments"):
                vtt = "WEBVTT\n\n" + "\n".join(f"{_vtt_time(x.get('start'))} --> {_vtt_time(x.get('end'))}\n{str(x.get('text') or '').strip()}\n" for x in res["segments"] if str(x.get("text") or "").strip())
            if vtt.strip().startswith("WEBVTT"):
                rel = os.path.join(DIR, "transcripts", f"{eid}.vtt")
                open(rel, "w").write(vtt)
                print(f"[transcript] {eid}: timed captions from the recording", flush=True)
                return rel, "text/vtt"
        except Exception as ex:
            print(f"[transcript] {eid}: couldn't hear it ({ex}); using the script", flush=True)
    clean = "\n".join(ln for ln in str(script or "").splitlines() if not ln.strip().startswith("[")).replace("(pause)", "").strip()
    if len(clean) > 40:
        rel = os.path.join(DIR, "transcripts", f"{eid}.txt")
        open(rel, "w").write(clean + "\n")
        return rel, "text/plain"
    return None, None


def add_episode(d, *, eid, kind, title, date, summary, audio_path, script=""):
    """Adds (or replaces) one episode. audio_path is relative to the repo root."""
    d["episodes"] = [e for e in d["episodes"] if e["id"] != eid]
    tr, trt = (None, None)
    try:
        tr, trt = make_transcript(eid, audio_path, script)
    except Exception as ex:
        print(f"[transcript] skipped: {ex}", flush=True)
    d["episodes"].append({
        "id": eid, "type": kind, "title": title, "date": date, "summary": summary,
        "audio": audio_path, "bytes": os.path.getsize(audio_path), "seconds": seconds(audio_path),
        "published": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "script": script, "transcript": tr, "transcript_type": trt,
    })
    return d


def _x(s):
    return html.escape(str(s or ""), quote=True)


def build_feed(d):
    eps = [e for e in d["episodes"] if os.path.exists(e["audio"])]
    weekly = 0
    items = []
    for e in sorted(eps, key=lambda e: (e["date"], e.get("published", ""))):
        if e["type"] == "weekly":
            weekly += 1
        when = dt.datetime.fromisoformat(e.get("published") or (e["date"] + "T18:00:00-07:00"))
        dur = e.get("seconds") or 0
        items.append(f"""    <item>
      <title>{_x(e['title'])}</title>
      <description>{_x(e['summary'])}</description>
      <itunes:summary>{_x(e['summary'])}</itunes:summary>
      <link>{_x(SHOW['page'] + '#' + e['id'])}</link>
      <guid isPermaLink="false">theqcollective-powerback-{_x(e['id'])}</guid>
      <pubDate>{format_datetime(when)}</pubDate>
      <enclosure url="{_x(SITE + '/' + e['audio'])}" length="{e['bytes']}" type="audio/mpeg"/>
      <itunes:duration>{dur // 60}:{dur % 60:02d}</itunes:duration>
      <itunes:episodeType>{'trailer' if e['type'] == 'trailer' else 'bonus' if e['type'] == 'bonus' else 'full'}</itunes:episodeType>{chr(10) + '      <itunes:image href="' + _x(SITE + '/podcast/cover-thursday.jpg') + '"/>' if e['type'] in ('thursday', 'trailer') else ''}
      <itunes:explicit>false</itunes:explicit>{chr(10) + '      <podcast:transcript url="' + _x(SITE + '/' + e['transcript']) + '" type="' + _x(e.get('transcript_type') or 'text/plain') + '" language="en"' + (' rel="captions"' if e.get('transcript_type') == 'text/vtt' else '') + '/>' if e.get('transcript') else ''}
    </item>""")
    items.reverse()
    c1, c2 = SHOW["category"], SHOW["category2"]
    cat1 = f'<itunes:category text="{_x(c1[0])}"/>'
    cat2 = f'<itunes:category text="{_x(c2[0])}"><itunes:category text="{_x(c2[1])}"/></itunes:category>'
    now = format_datetime(dt.datetime.now(TZ))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>{_x(SHOW['title'])}</title>
    <link>{_x(SHOW['page'])}</link>
    <atom:link href="{_x(SITE + '/' + FEED)}" rel="self" type="application/rss+xml"/>
    <language>{SHOW['language']}</language>
    <copyright>© {dt.date.today().year} The Q Collective</copyright>
    <description>{_x(SHOW['summary'])}</description>
    <itunes:summary>{_x(SHOW['summary'])}</itunes:summary>
    <itunes:author>{_x(SHOW['author'])}</itunes:author>
    <itunes:owner><itunes:name>{_x(SHOW['owner'])}</itunes:name><itunes:email>{_x(SHOW['email'])}</itunes:email></itunes:owner>
    <itunes:image href="{_x(SHOW['cover'])}"/>
    <image><url>{_x(SHOW['cover'])}</url><title>{_x(SHOW['title'])}</title><link>{_x(SHOW['page'])}</link></image>
    {cat1}
    {cat2}
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    os.makedirs(DIR, exist_ok=True)
    with open(FEED, "w") as f:
        f.write(xml)
    return len(items)


# ---------- the auto blog: one Q Notes post per episode ----------
NOTES_DIR = "notes"
NOTES_INDEX = "notes.html"
START, END = "<!-- podcast-notes:start (written by podcast_lib.py, don't edit by hand) -->", "<!-- podcast-notes:end -->"
CHIP = '<button type="button" class="nf-chip" data-t="pod" aria-pressed="false">Power Back Weekly</button>'


def _when(e):
    d = dt.date.fromisoformat(e["date"])
    return d.strftime("%b ") + str(d.day), d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def _paras(script):
    out = []
    for block in str(script or "").replace("\r", "").split("\n\n"):
        block = " ".join(block.split())
        if block:
            out.append(f"<p>{_x(block)}</p>")
    return "\n".join(out)


def post_html(e):
    short, long = _when(e)
    url = f"{SITE}/{NOTES_DIR}/pbw-{e['id']}.html"
    kind = {"weekly": "Sunday recap", "thursday": "Thursday with Mav", "bonus": "Special Session", "guest": "On the Record", "trailer": "Trailer"}.get(e["type"], "Episode")
    mins = max(1, round((e.get("seconds") or 60) / 60))
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<base href="/">
<title>{_x(e['title'])} | Power Back Weekly | The Q Collective</title>
<meta name="description" content="{_x(e['summary'])}">
<meta property="og:type" content="article"><meta property="og:site_name" content="The Q Collective">
<meta property="og:title" content="{_x(e['title'])}"><meta property="og:description" content="{_x(e['summary'])}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE}/og/podcast.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
<link rel="alternate" type="application/rss+xml" title="Power Back Weekly" href="{SITE}/{FEED}">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="q-chrome.css">
<style>
  body{{margin:0;background:#F9F6F0;font-family:'DM Sans',sans-serif;color:#1a1a1a;line-height:1.75;-webkit-font-smoothing:antialiased}}
  a{{color:#1B3A6B}}
  /* site header (same as every other page) */
  .top-stripe {{ height: 5px; background: linear-gradient(90deg, #B8962E 0%, #D4AF50 50%, #B8962E 100%); }}
  .topbar {{ position: sticky; top: 0; z-index: 50; background: rgba(18,40,72,0.97); backdrop-filter: blur(6px); border-bottom: 1px solid rgba(184,150,46,0.25); }}
  .topbar-inner {{ max-width: 1100px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; padding: 14px 32px; gap: 16px; }}
  .brand {{ display: flex; align-items: baseline; gap: 10px; text-decoration: none; }}
  .brand-q {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 700; font-size: 26px; color: #D4AF50; line-height: 1; }}
  .brand-name {{ font-size: 14px; font-weight: 600; color: #fff; }}
  @media(max-width:640px){{.topbar-inner{{padding:12px 18px}}}}
  .ph{{background:#122848;color:#fff;padding:56px 22px 46px}}
  .in{{max-width:760px;margin:0 auto}}
  .eb{{font-family:'DM Mono',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#D4AF50}}
  h1{{font-family:'Playfair Display',serif;font-weight:900;font-size:clamp(30px,5vw,46px);line-height:1.1;margin:12px 0 12px}}
  .sum{{color:rgba(255,255,255,.8);font-size:18px;margin:0 0 22px}}
  audio{{width:100%}}
  .row{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}}
  .b{{font-family:'DM Mono',monospace;font-size:12px;letter-spacing:1.4px;text-transform:uppercase;text-decoration:none;padding:11px 16px;border-radius:6px;border:1px solid rgba(255,255,255,.3);color:#fff}}
  .b.g{{background:#B8962E;border-color:#B8962E;color:#122848}}
  main{{padding:40px 22px 70px}}
  main h2{{font-family:'Playfair Display',serif;font-size:26px;color:#122848;margin:0 0 6px}}
  .note{{font-size:14px;color:#5a5a5a;margin:0 0 20px}}
  main p{{margin:0 0 16px;font-size:17px}}
  .back{{margin-top:34px;padding-top:20px;border-top:1px solid #E0D5BE;font-size:15px}}
</style></head><body>
<div id="q-chrome-top"></div>
<header class="ph"><div class="in">
<div class="eb">Power Back Weekly &middot; {kind} &middot; {long} &middot; {mins} min</div>
<h1>{_x(e['title'])}</h1>
<p class="sum">{_x(e['summary'])}</p>
<audio controls preload="none" src="{_x(e['audio'])}"></audio>
<div class="row"><a class="b g" href="podcast.html">All episodes</a><a class="b" href="podcast.html#follow">Follow the show</a></div>
</div></header>
<main><div class="in">
<h2>Read the episode</h2>
<p class="note">{"The full script, read by founder maveriQ B Jackson in his own voice." if e["type"] == "thursday" else "The full transcript. The opening is founder maveriQ B Jackson in his own voice; the rest is read by an AI voice from our published data. Every fact is on the public record at theqcollective.org."}</p>
{_paras(e.get('script')) or '<p>The transcript for this episode is on its way.</p>'}
<p class="back"><a href="notes.html">&larr; All Q Notes</a> &middot; <a href="podcast.html">Power Back Weekly</a> &middot; <a href="hub.html">Look up your lawmakers</a></p>
</div></main>
<div id="q-chrome-footer"></div>
<script src="q-config.js"></script><script src="site-chrome.js"></script>
</body></html>
"""


def build_posts(d):
    """Writes a Q Notes post for every published episode and refreshes the podcast cards on notes.html."""
    eps = [e for e in d["episodes"] if os.path.exists(e["audio"])]
    os.makedirs(NOTES_DIR, exist_ok=True)
    for e in eps:
        with open(os.path.join(NOTES_DIR, f"pbw-{e['id']}.html"), "w") as f:
            f.write(post_html(e))
    try:
        with open(NOTES_INDEX) as f:
            idx = f.read()
    except FileNotFoundError:
        return 0
    cards = "\n".join(
        f'<li data-t="pod"><a class="nc" href="{NOTES_DIR}/pbw-{_x(e["id"])}.html"><span class="nc-meta">Power Back Weekly &middot; {_when(e)[0]}</span>'
        f'<span class="nc-title">{_x(e["title"])}</span><span class="nc-sum">{_x(e["summary"])}</span></a></li>'
        for e in sorted(eps, key=lambda e: (e["date"], e.get("published", "")), reverse=True))
    block = START + ("\n" + cards if cards else "") + "\n" + END
    if START in idx and END in idx:
        idx = idx[:idx.index(START)] + block + idx[idx.index(END) + len(END):]
    else:
        idx = idx.replace('<ul class="ng">', '<ul class="ng">\n' + block, 1)
    if 'data-t="pod"' not in idx.split('<ul class="ng">')[0]:
        idx = idx.replace('<button type="button" class="nf-chip" data-t="bills"', CHIP + '<button type="button" class="nf-chip" data-t="bills"', 1)
    idx = idx.replace("data-t must be one of: bills, q, ai, ahead, about", "data-t must be one of: bills, q, ai, ahead, about (pod is written automatically)")
    with open(NOTES_INDEX, "w") as f:
        f.write(idx)
    return len(eps)


if __name__ == "__main__":
    n = build_feed(load())
    print(f"feed rebuilt: {n} episodes")


# --------------------------------------------------------------------------
# New-episode emails. People who signed up on the podcast page ("email me every new episode")
# get a short note each time one goes out. Needs SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY.
# only_episode_only=True (Sunday episodes): skip people who already get the Sunday Update, which
# has the same episode's Listen button in it.
# --------------------------------------------------------------------------
def email_new_episode(e, only_episode_only=False):
    import urllib.parse
    import urllib.request
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or ""
    rk = os.environ.get("RESEND_API_KEY") or ""
    if not (url and key and rk):
        print("[episode-email] not set up (Supabase or Resend secret missing); skipped", flush=True)
        return 0
    q = "sunday_subscribers?confirmed=eq.true&unsubscribed=eq.false&episodes=eq.true&select=email,token"
    if only_episode_only:
        q += "&sunday=eq.false"
    req = urllib.request.Request(url + "/rest/v1/" + q, headers={"apikey": key, "Authorization": "Bearer " + key, "User-Agent": "QCollective-podcast/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            subs = json.loads(r.read())
    except Exception as ex:
        print(f"[episode-email] couldn't read the list: {ex}", flush=True)
        return 0
    if not subs:
        return 0
    kind = {"weekly": "Sunday recap", "thursday": "Thursday with Mav", "bonus": "Special Session", "guest": "On the Record", "trailer": "Trailer"}.get(e.get("type") or e.get("kind"), "New episode")
    link = f"{SITE}/podcast.html#{e['id']}"
    mins = max(1, round((e.get("seconds") or 0) / 60))
    sender = os.environ.get("SEND_FROM") or "The Q Collective <noreply@auth.theqcollective.org>"
    def one(s):
        off = f"{SITE}/podcast.html?do=episodes-off&token={urllib.parse.quote(s['token'])}"
        h = (f"<div style=\"background:#f4f1ea;padding:24px 12px;font-family:Georgia,serif\"><div style=\"max-width:560px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e6dfcf\">"
             f"<div style=\"background:#0b1a31;padding:22px 26px;color:#fff\"><div style=\"font:600 12px/1 monospace;letter-spacing:.18em;color:#D4AF50\">POWER BACK WEEKLY &middot; {html.escape(kind.upper())}</div>"
             f"<div style=\"font:700 26px/1.25 Georgia,serif;margin-top:10px\">{html.escape(e['title'])}</div></div>"
             f"<div style=\"padding:22px 26px;color:#222;font-size:16px;line-height:1.6\"><p style=\"margin:0 0 16px\">{html.escape(e.get('summary') or '')}</p>"
             f"<p style=\"margin:0 0 18px\"><a href=\"{link}\" style=\"display:inline-block;background:#D4AF50;color:#0b1a31;text-decoration:none;font:700 16px Arial,sans-serif;padding:12px 20px;border-radius:8px\">&#9654; Listen ({mins} min)</a></p>"
             f"<p style=\"margin:0;font-size:13px;color:#777;font-family:Arial,sans-serif\">You asked for an email every time Power Back Weekly has a new episode. <a href=\"{off}\" style=\"color:#777\">Stop these emails</a>.</p></div></div></div>")
        t = f"{kind}: {e['title']}\n\n{e.get('summary') or ''}\n\nListen ({mins} min): {link}\n\nStop these emails: {off}\n"
        return {"from": sender, "to": [s["email"]], "reply_to": "team@theqcollective.org", "subject": f"New on Power Back Weekly: {e['title']}", "html": h, "text": t,
                "headers": {"List-Unsubscribe": f"<{off}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}}
    sent = 0
    for i in range(0, len(subs), 100):
        batch = [one(s) for s in subs[i:i + 100]]
        r = urllib.request.Request("https://api.resend.com/emails/batch", method="POST", data=json.dumps(batch).encode(),
                                   headers={"Authorization": "Bearer " + rk, "Content-Type": "application/json", "User-Agent": "QCollective-podcast/1.0"})
        via = "The Q Collective (GitHub: new-episode email)"
        try:
            urllib.request.urlopen(r, timeout=60).read(); sent += len(batch)
            for m in batch:
                hq_outbox.record(m["to"], m["subject"], m["html"], m["from"], via=via)
        except Exception as ex:
            for m in batch:
                hq_outbox.record(m["to"], m["subject"], m["html"], m["from"], ok=False, error=str(ex), via=via)
            print(f"[episode-email] batch failed: {ex}", flush=True)
    print(f"[episode-email] {sent} sent for {e['id']}", flush=True)
    return sent

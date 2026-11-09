"""
Share pages and link-preview cards for every lawmaker, so a shared profile shows that
person's name, seat and current Q Score in texts, email and social posts.

Runs after the Q Score engine every Sunday (.github/workflows/q-scores.yml), so the cards
always match the scores on the site. Can also be run by hand: python make_profile_cards.py

Writes, for each legislator in data/CO.json:
  p/<id>.html      a tiny page with that person's preview tags. People who open it are sent
                   straight to legislator.html?state=CO&id=<id>. Link-preview robots don't run
                   scripts, so they read the tags and stop there.
  og/p/<id>.png    the 1200 x 630 preview card.

Every card uses the same template for every lawmaker, whatever their party.
"""
import html
import json
import os
from PIL import Image, ImageDraw, ImageFont

SITE = "https://theqcollective.org"
HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, "scripts", "fonts")
NAVY, GOLD, GOLD2, WHITE, SOFT = (18, 40, 72), (201, 164, 63), (212, 175, 80), (255, 255, 255), (211, 218, 229)
PARTY = {"D": "Democrat", "R": "Republican", "I": "Independent", "L": "Libertarian", "G": "Green"}


def font(name, size):
    return ImageFont.truetype(os.path.join(F, name), size)


def seat(l):
    ch = "House" if "House" in (l.get("chamber") or "") else "Senate" if "Senate" in (l.get("chamber") or "") else ""
    role = "State Representative" if ch == "House" else "State Senator" if ch == "Senate" else (l.get("role") or "Legislator")
    dist = f"{ch} District {l['district']}" if l.get("district") else ""
    return role, dist


def fit(draw, text, name, start, max_w, min_size):
    size = start
    while size > min_size and draw.textlength(text, font=font(name, size)) > max_w:
        size -= 2
    return font(name, size)


def card(l, path):
    im = Image.new("RGBA", (1200, 630), NAVY + (255,))
    ghost = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(ghost).text((1230, 650), "Q", font=font("DejaVuSerif-Bold.ttf", 820), fill=(255, 255, 255, 14), anchor="rd")
    box = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle((850, 150, 1120, 470), radius=22, fill=(255, 255, 255, 18), outline=(201, 164, 63, 150), width=3)
    im = Image.alpha_composite(Image.alpha_composite(im, ghost), box)
    d = ImageDraw.Draw(im)
    d.rectangle((80, 90, 180, 96), fill=GOLD)
    d.text((80, 122), "THE Q COLLECTIVE", font=font("DejaVuSans.ttf", 30), fill=GOLD2)
    role, dist = seat(l)
    nf = fit(d, l["name"], "DejaVuSerif-Bold.ttf", 76, 700, 40)
    d.text((80, 186), l["name"], font=nf, fill=WHITE)
    line2 = " · ".join(x for x in [role, dist] if x)
    d.text((80, 300), line2, font=fit(d, line2, "DejaVuSans.ttf", 32, 700, 22), fill=SOFT)
    if l.get("party"):
        d.text((80, 346), PARTY.get(l["party"], l["party"]), font=font("DejaVuSans.ttf", 30), fill=SOFT)
    d.text((80, 540), "theqcollective.org", font=font("DejaVuSans.ttf", 30), fill=GOLD2)

    # score block
    d.text((985, 196), "Q SCORE", font=font("DejaVuSans-Bold.ttf", 26), fill=GOLD2, anchor="mm")
    sc = l.get("score")
    if sc is None:
        d.text((985, 320), "Coming", font=font("DejaVuSerif-Bold.ttf", 54), fill=WHITE, anchor="mm")
    else:
        d.text((985, 320), str(sc), font=font("DejaVuSerif-Bold.ttf", 150), fill=WHITE, anchor="mm")
        d.text((985, 420), "out of 100", font=font("DejaVuSans.ttf", 24), fill=SOFT, anchor="mm")
    if l.get("label"):
        lab = l["label"]
        d.text((985, 510), lab, font=fit(d, lab, "DejaVuSans-Bold.ttf", 24, 300, 16), fill=GOLD2, anchor="mm")
    im.convert("RGB").save(path, optimize=True)


def page(l, state):
    role, dist = seat(l)
    sc = l.get("score")
    target = f"../legislator.html?state={state}&id={l['id']}"
    title = f"{l['name']}" + (f" · Q Score {sc}" if sc is not None else "") + " · The Q Collective"
    desc = f"{l['name']}, {role}" + (f" for {dist}" if dist else "") + ". " + (
        f"Q Score {sc} out of 100. See the bills, votes and record behind it." if sc is not None else "See their record on the Accountability Hub.")
    e = lambda t: html.escape(str(t), quote=True)
    img = f"{SITE}/og/p/{l['id']}.png"
    url = f"{SITE}/p/{l['id']}.html"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta property="og:type" content="profile">
<meta property="og:site_name" content="The Q Collective">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{img}">
<meta name="description" content="{e(desc)}">
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{SITE}/legislator.html?state={state}&amp;id={e(l['id'])}">
<script>location.replace({json.dumps(target)});</script>
<style>body{{font:18px/1.5 Georgia,serif;background:#F9F6F0;color:#122848;display:grid;place-items:center;min-height:90vh;margin:0;padding:16px}}a{{color:#122848}}</style>
</head><body><p>Opening <a href="{e(target)}">{e(l['name'])}’s profile</a>…</p></body></html>
"""


def main():
    state = "CO"
    data = json.load(open(os.path.join(HERE, "data", f"{state}.json")))
    os.makedirs(os.path.join(HERE, "p"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "og", "p"), exist_ok=True)
    keep = set()
    for l in data.get("legislators", []):
        if not l.get("id") or not l.get("name"):
            continue
        sid = str(l["id"])
        keep.add(sid)
        card(l, os.path.join(HERE, "og", "p", sid + ".png"))
        open(os.path.join(HERE, "p", sid + ".html"), "w").write(page(l, state))
    # lawmakers who left the roster lose their share page
    for f in os.listdir(os.path.join(HERE, "p")):
        if f.endswith(".html") and f[:-5] not in keep:
            os.remove(os.path.join(HERE, "p", f))
            png = os.path.join(HERE, "og", "p", f[:-5] + ".png")
            if os.path.exists(png):
                os.remove(png)
    print(f"Made {len(keep)} lawmaker share pages and preview cards.")


if __name__ == "__main__":
    main()

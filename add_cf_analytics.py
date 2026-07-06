#!/usr/bin/env python3
# add_cf_analytics.py — inject the Cloudflare Web Analytics beacon into every HTML page.
# Safe to run more than once: it skips any file that already has the beacon.
import os, sys

TOKEN = "6aff6948b0f84ed0b1530a42458bbb3b"
SNIPPET = (
    "<!-- Cloudflare Web Analytics -->"
    "<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
    "data-cf-beacon='{\"token\": \"" + TOKEN + "\"}'></script>"
    "<!-- End Cloudflare Web Analytics -->"
)

root = sys.argv[1] if len(sys.argv) > 1 else "."
changed, skipped = [], []

for dirpath, dirnames, filenames in os.walk(root):
    if ".git" in dirpath.split(os.sep):
        continue
    for name in filenames:
        if not name.lower().endswith(".html"):
            continue
        path = os.path.join(dirpath, name)
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        if "cloudflareinsights.com/beacon" in html:
            skipped.append(path)
            continue
        # insert right before the LAST </body>; if none, append to end
        idx = html.rfind("</body>")
        if idx == -1:
            new = html + "\n" + SNIPPET + "\n"
        else:
            new = html[:idx] + SNIPPET + "\n" + html[idx:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        changed.append(path)

print(f"Injected into {len(changed)} file(s); skipped {len(skipped)} already-tagged.")
for p in changed:
    print("  + " + p)

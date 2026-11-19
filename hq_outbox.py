"""
Log every email these jobs send into Ash HQ -> Outbox, so the Outbox shows everything, not only what HQ sends.

Each sender calls record(...) right after it talks to Resend (sent or failed). The list goes to Ash HQ once,
when the script ends (in groups of 100). It never stops or fails a job: if HQ can't be reached, the run log
says so and the emails have still gone out.

The call is signed (HMAC-SHA256 of "<time>.<body>"), so the key itself never leaves GitHub. The key is
HQ_OUTBOX_KEY if that secret is set, otherwise SUPABASE_SERVICE_KEY, which Ash HQ also holds.
"""
import atexit
import hashlib
import hmac
import json
import os
import time
import urllib.request
import datetime as dt

HQ = (os.environ.get("HQ_ORIGIN") or "https://aetherandash.digital").rstrip("/")
VIA = "The Q Collective (GitHub: " + (os.environ.get("GITHUB_WORKFLOW") or "daily job") + ")"
_queue = []


def record(to, subject, body="", frm="", ok=True, error=None, ref=None, via=None):
    """Remember one sent (or failed) email. `to` can be a string or a list."""
    if isinstance(to, (list, tuple)):
        to = ", ".join(str(x) for x in to)
    _queue.append({
        "channel": "email", "to": str(to or "")[:500], "from": str(frm or "")[:200], "subject": str(subject or "")[:300],
        "body": str(body or "")[:150000], "ok": bool(ok), "error": (str(error)[:500] if error else None),
        "ref": ref or None, "via": (via or VIA)[:80], "at": dt.datetime.now(dt.timezone.utc).isoformat(),
    })


def _post(items):
    key = os.environ.get("HQ_OUTBOX_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or ""
    if not key:
        print("[outbox] no key, so these emails were not logged in Ash HQ.", flush=True)
        return
    raw = json.dumps({"items": items}).encode()
    t = str(int(time.time()))
    sig = hmac.new(key.encode(), t.encode() + b"." + raw, hashlib.sha256).hexdigest()
    r = urllib.request.Request(HQ + "/api/team/outbox", data=raw, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": "QCollective-outbox/1.0", "x-hq-sig": f"t={t},v1={sig}"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            out = json.loads(resp.read().decode() or "{}")
            print(f"[outbox] logged {out.get('added', 0)} in Ash HQ ({out.get('skipped', 0)} already there).", flush=True)
    except Exception as e:  # never fail the job over the log
        code = getattr(e, "code", "")
        print(f"[outbox] Ash HQ didn't take the log ({code or e}).", "Set the HQ_OUTBOX_KEY secret in both places." if code == 404 else "", flush=True)


def flush():
    global _queue
    items, _queue = _queue, []
    for i in range(0, len(items), 100):
        _post(items[i:i + 100])


atexit.register(flush)

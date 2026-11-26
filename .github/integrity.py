"""Builds the list of public files and their SHA-256, so the deployed site can be checked against the code.
Run by .github/workflows/integrity.yml on every push. Ash HQ's heartbeat compares the live files to this list.
Usage: python .github/integrity.py OUT EXTS EXCLUDE_DIRS [--sovran]"""
import hashlib, json, os, sys, datetime, subprocess
out, exts, skip = sys.argv[1], set(sys.argv[2].split(',')), [d.strip('/') + '/' for d in sys.argv[3].split(',') if d]
sov = '--sovran' in sys.argv
files = {}
for root, dirs, names in os.walk('.'):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
    for n in names:
        p = os.path.join(root, n)[2:].replace(os.sep, '/')
        if p == out or n == 'robots.txt' or n.startswith('_') or n.startswith('.') or any(p.startswith(s) for s in skip): continue
        if p.rsplit('.', 1)[-1].lower() not in exts: continue
        b = open(p, 'rb').read()
        files['/' + p] = {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}
commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
doc = {'generated': now, 'commit': commit, 'note': 'SHA-256 of every public file, rebuilt on every commit.', 'files': dict(sorted(files.items()))}
if sov: doc['note'] = 'SHA-256 of every deployed file. robots.txt is excluded: Cloudflare rewrites it with managed bot rules.'
old = None
try: old = json.load(open(out))
except Exception: pass
if old and old.get('files') == doc['files']: print('no change'); sys.exit(0)
json.dump(doc, open(out, 'w'), indent=1); open(out, 'a').write('\n')
print(len(files), 'files')

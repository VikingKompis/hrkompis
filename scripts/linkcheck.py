"""Daily quality audit.

1. Dead-link check: EURES ads more than 21 days old are looked up in the EURES API (oldest first,
   up to LINKCHECK_MAX a day, each re-checked weekly). A "not found" answer marks the ad dead and
   process.py drops it. Adzuna links are deliberately not checked: Adzuna pays per click, so automated
   hits would count as fake clicks. Adzuna freshness is handled by its 14-day window instead.
2. Writes AUDIT.md: what came in, what was removed and why, and source health.
"""
import json, os, sys, datetime, urllib.request, urllib.error, collections
from concurrent.futures import ThreadPoolExecutor

RAW = os.environ.get('RAW_DIR', 'raw')
TODAY = datetime.date.today()
MAX = int(os.environ.get('LINKCHECK_MAX') or 500)
path = os.path.join(RAW, 'linkcheck.json')
state = json.load(open(path)) if os.path.exists(path) else {}
data = json.load(open('data/jobs.json', encoding='utf-8'))
jobs = data['jobs']
ids = {j['i'] for j in jobs}
state = {k: v for k, v in state.items() if k in ids or v.get('ok') is False and v.get('t', '') >= (TODAY - datetime.timedelta(days=30)).isoformat()}

def age(j):
    try: return (TODAY - datetime.date.fromisoformat(j['p'])).days
    except Exception: return 0
due = [j for j in jobs if j['o'] == 'eures' and age(j) > 21
       and (state.get(j['i'], {}).get('t', '') < (TODAY - datetime.timedelta(days=7)).isoformat())]
due.sort(key=lambda j: j.get('p') or '')
due = due[:MAX]
REPORT_ONLY = '--report-only' in sys.argv
if REPORT_ONLY: due = []

def check(j):
    url = f"https://europa.eu/eures/api/jv-searchengine/public/jv/id/{j['i']}?requestLang=en"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'HRKompis link check (hrkompis.com)', 'Accept': 'application/json'}), timeout=20) as r:
            return j['i'], True
    except urllib.error.HTTPError as e:
        return j['i'], (False if e.code in (404, 410) else None)
    except Exception:
        return j['i'], None

res = collections.Counter()
with ThreadPoolExecutor(6) as ex:
    for i, ok in ex.map(check, due):
        if ok is None: res['error'] += 1; continue
        state[i] = {'t': TODAY.isoformat(), 'ok': ok}; res['live' if ok else 'dead'] += 1
tpath = os.path.join(RAW, 'linkcheck_today.json')
if REPORT_ONLY:
    t = json.load(open(tpath)) if os.path.exists(tpath) else {}
    res.update(t.get('res', {})); n_checked = t.get('checked', 0)
else:
    json.dump(state, open(path, 'w'), separators=(',', ':'))
    n_checked = len(due)
    json.dump({'checked': n_checked, 'res': dict(res)}, open(tpath, 'w'))
    print(f'linkcheck: checked {n_checked} EURES ads: {dict(res)}')

# ---------------- AUDIT.md ----------------
st = data['stats']; au = st.get('audit', {})
status = json.load(open(os.path.join(RAW, 'status.json'))) if os.path.exists(os.path.join(RAW, 'status.json')) else {}
dead_total = sum(1 for v in state.values() if v.get('ok') is False)
by_src = collections.Counter(j['o'] for j in jobs)
ages = collections.Counter(min(age(j) // 7, 4) for j in jobs if j.get('p'))
L = [f"# HRKompis daily audit", f"", f"Run: {data['asof']} (UTC). Updated automatically after every daily refresh.", "",
     "## Today's list", "",
     f"- **{au.get('after_qc', st['total']):,} jobs published** (from {au.get('before_qc', 0):,} HR ads collected)",
     f"- {au.get('duplicates_merged', 0):,} duplicate rows merged: {au.get('multi_location_listings', 0):,} listings now show \"+N other locations\"; {au.get('cross_source_groups', 0):,} jobs were found via more than one source (best source kept)",
     f"- {au.get('dead_links_removed', 0):,} EURES ads removed because EURES says they no longer exist",
     f"- Adzuna ads are kept for 14 days at most; every other source is a fresh snapshot each morning", "",
     "## Freshness", "",
     f"- Posted in the last 7 days: {ages[0]:,}", f"- 8 to 14 days: {ages[1]:,}", f"- 15 to 28 days: {ages[2] + ages[3]:,}", f"- Over 28 days: {ages[4]:,} (of which over 45 days: {au.get('older_than_45_days', 0):,})",
     f"- No posting date given by the source: {au.get('no_date', 0):,}", "",
     "## Dead-link check (EURES)", "",
     f"- Checked today: {n_checked:,} ({res['live']:,} live, {res['dead']:,} gone, {res['error']:,} could not be checked)",
     f"- Known dead and excluded: {dead_total:,}", "",
     "## Jobs by source", "", "| Source | Jobs |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in by_src.most_common()] + ["",
     "## Source health", "",
     (f"- Problems: " + "; ".join(status['problems'])) if status.get('problems') else "- All sources ran without problems", ""]
open('AUDIT.md', 'w', encoding='utf-8').write('\n'.join(L))

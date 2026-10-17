"""Find which recruitment system each employer's careers site runs on.

Reads companies/<cc>.json ([{name, url}]), crawls the careers page and up to
two levels of "jobs/careers" links, and records any recognised applicant
tracking system (ATS) with the identifiers needed to read its public job feed.
Writes companies/<cc>.discovered.json.
"""
import json, re, sys, os, urllib.request, urllib.parse, http.cookiejar
from concurrent.futures import ThreadPoolExecutor

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
HDR = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9,sv;q=0.8'}

SIGS = [
    ('workday', re.compile(r'https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)', re.I)),
    ('workday', re.compile(r'https?://([a-z0-9-]+)\.(wd\d+)\.myworkdaysite\.com/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/[a-z0-9-]+/([A-Za-z0-9_-]+)', re.I)),
    ('teamtailor', re.compile(r'https?://([a-z0-9-]+)\.teamtailor\.com', re.I)),
    ('oracle', re.compile(r'https?://([a-z0-9-]+\.fa\.[a-z0-9-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z-]+/sites/([A-Za-z0-9_]+)', re.I)),
    ('smartrecruiters', re.compile(r'(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)', re.I)),
    ('greenhouse', re.compile(r'(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)', re.I)),
    ('lever', re.compile(r'jobs\.(?:eu\.)?lever\.co/([a-z0-9_-]+)', re.I)),
    ('varbi', re.compile(r'https?://([a-z0-9-]+)\.varbi\.com', re.I)),
    ('eightfold', re.compile(r'https?://([a-z0-9-]+)\.eightfold\.ai', re.I)),
    ('icims', re.compile(r'https?://([a-z0-9-]+)\.icims\.com', re.I)),
    ('workable', re.compile(r'apply\.workable\.com/([a-z0-9_-]+)', re.I)),
    ('recruitee', re.compile(r'https?://([a-z0-9-]+)\.recruitee\.com', re.I)),
    ('pinpoint', re.compile(r'https?://([a-z0-9-]+)\.pinpointhq\.com', re.I)),
    ('successfactors', re.compile(r'https?://(career\d*\.(?:sapsf|successfactors)\.(?:com|eu))/(?:career|sfcareer)[^"\'\s]*?company=([A-Za-z0-9_]+)', re.I)),
    ('taleo', re.compile(r'https?://([a-z0-9-]+)\.taleo\.net', re.I)),
    ('avature', re.compile(r'https?://([a-z0-9.-]+\.avature\.net)', re.I)),
    ('reachmee', re.compile(r'(site\d*\.reachmee\.com/[^"\'\s]*)', re.I)),
    ('jobylon', re.compile(r'(?:emp|cdn)\.jobylon\.com/(?:[a-z/]*?)(\d{3,})', re.I)),
]
# Platforms recognised from page markup rather than a URL with an id in it
MARKERS = [
    ('sf_rmk', re.compile(r'rmkcdn\.successfactors|/services/rss/job|data-careersite|j2w\.|jobs2web', re.I)),
    ('phenom', re.compile(r'phenompeople|cdn\.phenompeople|phApp\.', re.I)),
    ('radancy', re.compile(r'tmpwebeng|radancy|tmp\.com', re.I)),
    ('teamtailor_custom', re.compile(r'teamtailor-cdn|teamtailor\.com/assets', re.I)),
]
LINK = re.compile(r'href="([^"#]+)"[^>]*>(.*?)</a>', re.I | re.S)
JOBWORD = re.compile(r'(lediga|jobb|job|career|karri|vacanc|opening|position|search|sök|opportunit|roles|join)', re.I)


def fetch(url, op):
    req = urllib.request.Request(url, headers=HDR)
    with op.open(req, timeout=25) as r:
        return r.geturl(), r.read(1_500_000).decode('utf-8', 'replace')


def scan(text):
    hits = []
    for name, rx in SIGS:
        for m in rx.finditer(text):
            hits.append({'ats': name, 'ids': list(m.groups())})
    marks = [n for n, rx in MARKERS if rx.search(text)]
    return hits, marks


def discover(c):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    seen, queue, found, marks, pages = set(), [(c['url'], 0)], [], set(), []
    while queue and len(seen) < 8:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            final, html = fetch(url, op)
        except Exception as e:
            pages.append({'url': url, 'error': str(e)[:120]})
            continue
        pages.append({'url': url, 'final': final})
        hits, mk = scan(final + '\n' + html)
        found += hits
        marks |= set(mk)
        if found or depth >= 2:
            continue
        cand = []
        for href, txt in LINK.findall(html):
            t = re.sub(r'<[^>]+>', ' ', txt)
            if JOBWORD.search(href) or JOBWORD.search(t):
                u = urllib.parse.urljoin(final, href.strip())
                if u.startswith('http') and u not in seen:
                    cand.append(u)
        for u in list(dict.fromkeys(cand))[:6]:
            queue.append((u, depth + 1))
    uniq = []
    for h in found:
        if h not in uniq:
            uniq.append(h)
    return {**c, 'ats': uniq[:6], 'markers': sorted(marks), 'final': pages[-1].get('final') if pages else None, 'pages': pages}


if __name__ == '__main__':
    for cc in sys.argv[1:]:
        comps = json.load(open(f'companies/{cc}.json', encoding='utf-8'))
        with ThreadPoolExecutor(10) as ex:
            res = list(ex.map(discover, comps))
        json.dump(res, open(f'companies/{cc}.discovered.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        n = sum(1 for r in res if r['ats'])
        print(f'{cc}: {n}/{len(res)} with a recognised ATS')
        for r in res:
            print(' ', r['name'], '|', ', '.join(h['ats'] + ':' + '/'.join(x or '' for x in h['ids']) for h in r['ats'][:2]) or ('markers: ' + ','.join(r['markers']) if r['markers'] else '-'))

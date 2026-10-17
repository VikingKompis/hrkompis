"""Daily HRKompis harvest: pulls HR job ads from public sources into raw/*.json.

Each source is fetched independently. If a source fails or returns nothing,
the previous day's raw file is kept so the site never loses a whole country,
and the run is flagged as failed at the end so GitHub sends an alert email.
"""
import json, os, re, sys, time, html, http.cookiejar, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

RAW = os.environ.get('RAW_DIR', 'raw')
os.makedirs(RAW, exist_ok=True)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
problems = []


def opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(url, op=None, headers=None, data=None, timeout=40, tries=3):
    h = {'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'en-GB,en;q=0.9'}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h['Content-Type'] = 'application/json'
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h, method='POST' if body else 'GET')
            with (op or urllib.request.build_opener()).open(req, timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 + 3 * i)


def getj(*a, **k):
    return json.loads(get(*a, **k))


def save(name, payload, count, minimum):
    path = os.path.join(RAW, name + '.json')
    if count < minimum:
        problems.append(f'{name}: only {count} records (expected at least {minimum}); kept previous data')
        print(f'!! {name}: {count} records, keeping previous file', flush=True)
        return
    json.dump(payload, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'ok {name}: {count}', flush=True)


def run(name, fn, minimum):
    try:
        payload, count = fn()
        save(name, payload, count, minimum)
    except Exception as e:
        problems.append(f'{name}: {type(e).__name__}: {e}')
        print(f'!! {name} failed: {e}', flush=True)


def strip(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).strip()


# ---------------- Sweden: Arbetsförmedlingen JobTech ----------------
def jobtech():
    groups = ['bjqk_F3A_5Hk', 'mNoS_AN5_drn', 'L7eh_ihX_vM5', 'Qo7p_wjf_gtv']
    out = []
    for g in groups:
        off, tot = 0, 1
        while off < tot and off < 2000:
            j = getj(f'https://jobsearch.api.jobtechdev.se/search?occupation-group={g}&limit=100&offset={off}', headers={'accept': 'application/json'})
            tot = j['total']['value']
            for h in j['hits']:
                desc = ((h.get('description') or {}).get('text') or '')
                wa = h.get('workplace_address') or {}
                out.append({'id': h['id'], 't': h.get('headline'), 'e': (h.get('employer') or {}).get('name'),
                            'm': wa.get('municipality'), 'r': wa.get('region'),
                            'p': (h.get('publication_date') or '')[:10], 'd': (h.get('application_deadline') or '')[:10],
                            'o': (h.get('occupation') or {}).get('label'), 'g': g,
                            'wh': (h.get('working_hours_type') or {}).get('label'),
                            'lang': 'en' if re.search(r'\b(the|and|we are|you will)\b', desc[:400], re.I) else 'sv'})
            off += 100
    return {'src': 'jobtech', 'data': out}, len(out)


# ---------------- EURES (Germany, Netherlands, Ireland) ----------------
EURES_TERMS = {
    'de': ['HR', 'Personal', 'Recruiter', 'Recruiting', 'Payroll', 'Entgeltabrechnung', 'Lohnbuchhalter', 'Talent', 'People', 'Human Resources'],
    'nl': ['HR', 'HRM', 'recruiter', 'recruitment', 'payroll', 'salaris', 'P&O', 'personeel', 'talent', 'people', 'learning', 'Human Resources'],
    'ie': ['HR', 'human resources', 'payroll', 'recruitment', 'people', 'talent', 'learning'],
}


def eures():
    op = opener()
    try:
        get('https://europa.eu/eures/portal/jv-se/search?lang=en', op)
    except Exception:
        pass
    url = 'https://europa.eu/eures/api/jv-searchengine/public/jv-search/search'
    hdr = {'Accept': 'application/json', 'Origin': 'https://europa.eu', 'Referer': 'https://europa.eu/eures/portal/jv-se/search?lang=en'}
    seen = {}

    def one(loc, kw):
        p, tot = 1, 1
        got = []
        while (p - 1) * 50 < tot and p <= 40:
            body = {'resultsPerPage': 50, 'page': p, 'sortSearch': 'MOST_RECENT',
                    'keywords': [{'keyword': kw, 'specificSearchCode': 'TITLE'}], 'publicationPeriod': None,
                    'occupationUris': [], 'skillUris': [], 'requiredExperienceCodes': [], 'positionScheduleCodes': [],
                    'sectorCodes': [], 'educationAndQualificationLevelCodes': [], 'positionOfferingCodes': [],
                    'locationCodes': [loc], 'euresFlagCodes': [], 'otherBenefitsCodes': [], 'requiredLanguages': [],
                    'minNumberPost': None, 'sessionId': 'hrkompis'}
            j = json.loads(get(url, op, hdr, body))
            tot = j.get('numberRecords') or 0
            jvs = j.get('jvs') or []
            if not jvs:
                break
            for v in jvs:
                lm = v.get('locationMap') or {}
                k = next(iter(lm), '')
                got.append((v['id'], {'c': loc, 't': v.get('title'), 'e': (v.get('employer') or {}).get('name'),
                                      'n': (lm.get(k) or [k])[0] if k else '', 'd': v.get('creationDate'),
                                      's': ','.join(v.get('positionScheduleCodes') or []),
                                      'l': ','.join(v.get('availableLanguages') or []), 'o': v.get('positionOfferingCode')}))
            p += 1
        return got

    jobs = [(loc, kw) for loc, kws in EURES_TERMS.items() for kw in kws]
    with ThreadPoolExecutor(4) as ex:
        for got in ex.map(lambda a: one(*a), jobs):
            for i, v in got:
                seen.setdefault(i, v)
    data = [{'id': i, **v} for i, v in seen.items()]
    return {'src': 'eures', 'data': data}, len(data)


# ---------------- Denmark: Jobnet ----------------
def jobnet():
    op = opener()
    get('https://jobnet.dk/find-job', op)
    hdr = {'accept': 'application/json', 'x-csrf': '1', 'Referer': 'https://jobnet.dk/find-job'}
    out = {}
    for q in ['HR', 'rekruttering', 'recruiter', 'talent acquisition', 'lønbogholder', 'lønadministration', 'payroll',
              'personalechef', 'people', 'talent', 'learning', 'HR-partner', 'HR-konsulent', 'HR-chef', 'human resources',
              'arbejdsmiljø', 'løn og personale']:
        p, t = 1, 1
        while (p - 1) * 100 < t and p <= 10:
            u = ('https://jobnet.dk/bff/FindJob/Search?resultsPerPage=100&pageNumber=%d&orderType=PublicationDate&kmRadius=50&searchString=%s'
                 % (p, urllib.parse.quote(q)))
            j = getj(u, op, hdr)
            t = j.get('totalJobAdCount') or 0
            ads = j.get('jobAds') or []
            for a in ads:
                out[a['jobAdId']] = {'c': 'dk', 't': a.get('title'), 'e': a.get('hiringOrgName'), 'n': a.get('postalDistrictName'),
                                     'z': a.get('postalCode'), 'd': (a.get('publicationDate') or '')[:10],
                                     'dl': (a.get('applicationDeadline') or '')[:10], 'u': a.get('jobAdUrl'),
                                     'o': a.get('occupation'), 'pt': a.get('workHourPartTime')}
            if not ads:
                break
            p += 1
    data = [{'id': i, **v} for i, v in out.items()]
    return {'src': 'jobnet', 'data': data}, len(data)


# ---------------- UK: NHS Jobs ----------------
def nhs():
    out = {}
    tag = lambda x, n: html.unescape((re.search(rf'<{n}>(.*?)</{n}>', x, re.S) or [None, ''])[1])
    for q in ['HR', 'human resources', 'recruitment', 'payroll', 'people', 'organisational development', 'learning and development',
              'employee relations', 'workforce', 'ESR', 'resourcing', 'talent', 'temporary staffing', 'medical staffing', 'occupational health']:
        for p in range(1, 41):
            x = get(f'https://www.jobs.nhs.uk/api/v1/search_xml?keyword={urllib.parse.quote(q)}&page={p}')
            items = re.findall(r'<vacancyDetails>(.*?)</vacancyDetails>', x, re.S)
            if not items:
                break
            for v in items:
                out[tag(v, 'id')] = {'t': tag(v, 'title'), 'e': tag(v, 'employer'), 'ty': tag(v, 'type'), 's': tag(v, 'salary'),
                                     'dl': tag(v, 'closeDate'), 'd': tag(v, 'postDate')[:10], 'u': tag(v, 'url'),
                                     'l': '; '.join(html.unescape(l) for l in re.findall(r'<location>(.*?)</location>', v, re.S))}
    data = [{'id': i, **v} for i, v in out.items()]
    return {'src': 'nhs', 'data': data}, len(data)


# ---------------- UK: government Work Hub ----------------
def workhub():
    out = {}
    op = opener()
    hdr = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Sec-Fetch-Dest': 'document',
           'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin', 'Upgrade-Insecure-Requests': '1',
           'Referer': 'https://www.jobs.service.gov.uk/jobs'}
    try:
        get('https://www.jobs.service.gov.uk/', op, hdr)
    except Exception:
        pass
    for q in ['HR business partner', 'HR advisor', 'HR manager', 'HR director', 'head of HR', 'people partner', 'HR officer',
              'HR administrator', 'HR coordinator', 'HR generalist', 'people director', 'talent acquisition', 'in-house recruiter',
              'recruitment partner', 'recruitment coordinator', 'payroll', 'reward', 'learning and development', 'employee relations',
              'organisational development', 'HR assistant', 'people operations', 'HRIS']:
        for p in range(1, 26):
            t = get(f'https://www.jobs.service.gov.uk/jobs/search?keywords={urllib.parse.quote(q)}&pageNumber={p}', op, hdr)
            parts = t.split('data-testid="searchResultCard-')[1:]
            if not parts:
                break
            for c in parts:
                i = c.split('"', 1)[0]
                if i in out:
                    continue
                title = strip((re.search(r'<h2[^>]*>(.*?)</h2>', c, re.S) or [None, ''])[1])
                emp = strip((re.search(r'data-testid="searchResultCardEmployer"[^>]*>(.*?)</p>', c, re.S) or [None, ''])[1])
                ps = re.findall(r'<p class="([^"]*)"[^>]*?(data-testid="[^"]*")?[^>]*>(.*?)</p>', c, re.S)
                sal = ''
                for cls, tid, txt in ps[1:3]:
                    if 'font-weight-bold' in cls and not tid:
                        sal = strip(txt)
                        break
                tags = ','.join(strip(x) for x in re.findall(r'class="govuk-tag[^"]*"[^>]*>(.*?)</span>', c, re.S))
                out[i] = {'t': title, 'e': emp, 's': sal, 'tags': tags}
    data = [{'id': i, **v} for i, v in out.items()]
    return {'src': 'workhub', 'data': data}, len(data)


# ---------------- Ireland: publicjobs.ie ----------------
def publicjobs():
    base = 'https://publicjobs.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/candidate/jobboard/vacancy/3/adv/'
    out = {}
    for s in range(0, 1000, 50):
        t = get(f'{base}?start={s}')
        links = list(re.finditer(r'<a[^>]+href="([^"]*/opp/[^"]+)"[^>]*>(.*?)</a>', t, re.S))
        if not links:
            break
        for k, m in enumerate(links):
            u = html.unescape(m.group(1))
            if u in out:
                continue
            end = links[k + 1].start() if k + 1 < len(links) else len(t)
            seg = t[m.end():end]
            f = {lab.strip(): html.unescape(val).strip() for lab, val in re.findall(r'candidate-opp-field-label">([^<]+):</span>\s*([^<]*)<', seg)}
            out[u] = {'t': re.sub(r'\s+', ' ', strip(m.group(2))), 'u': u if u.startswith('http') else 'https://publicjobs.tal.net' + u,
                      'org': f.get('Department/Organisation', ''), 'loc': f.get('Location', ''),
                      'ad': f.get('Advertising Date', ''), 'cd': f.get('Closing Date', '')}
        if len(links) < 10:
            break
    data = list(out.values())
    return {'src': 'publicjobs', 'data': data}, len(data)


# ---------------- Employer career sites ----------------
GREENHOUSE = ('adyen airbnb airtable asana canonical catawiki celonis cleo cloudflare cognism coinbase contentful databricks datadog '
              'deliveroo dropbox elastic figma flipdish flix getyourguide gitlab gocardless grafanalabs hellofresh intercom kaluza '
              'mongodb monzo n26 okta oura pinterest realtimeboardglobal reddit robinhood samsara squarespace stripe sumup tines '
              'toast traderepublicbank truecaller truelayer trustpilot twilio wise workato hubspot zendesk docusign personio').split()
LEVER = 'aircall binance contentsquare jumpcloud kpler matchgroup outreach palantir pigment qonto spotify swile veeva zoox'.split()
SMARTR = 'AbbVie Accor BoschGroup Boskalis Continental DeliveryHero Experian KPN Primark Sodexo Ubisoft2 Wise'.split()
GEO = re.compile(r'united kingdom|\buk\b|england|scotland|wales|london|manchester|edinburgh|glasgow|bristol|birmingham|leeds|cambridge|oxford|belfast|cardiff|reading|ireland|dublin|cork|galway|limerick|\bie\b|denmark|copenhagen|københavn|aarhus|odense|germany|deutschland|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|leipzig|netherlands|amsterdam|rotterdam|utrecht|eindhoven|the hague|den haag|emea|europe', re.I)
HRX = re.compile(r'\b(hr|hris|people|talent|recruit\w*|human resources|payroll|reward\w*|compensation|benefits|learning|l&d|employee relations|hrbp|sourcer|organi[sz]ational development|workplace|culture)\b', re.I)


def greenhouse():
    def one(t):
        try:
            j = getj(f'https://boards-api.greenhouse.io/v1/boards/{t}/jobs', tries=1)
        except Exception:
            return []
        res = []
        for x in j.get('jobs', []):
            loc = (x.get('location') or {}).get('name') or ''
            if HRX.search(x['title']) and GEO.search(loc):
                res.append({'co': t, 't': x['title'], 'loc': loc, 'u': x.get('absolute_url'), 'd': (x.get('updated_at') or '')[:10], 'id': x['id']})
        return res
    with ThreadPoolExecutor(8) as ex:
        data = [r for rs in ex.map(one, GREENHOUSE) for r in rs]
    return {'src': 'greenhouse', 'data': data}, len(data)


def lever():
    def one(t):
        try:
            j = getj(f'https://api.lever.co/v0/postings/{t}?mode=json', tries=1)
        except Exception:
            return []
        res = []
        for x in j:
            c = x.get('categories') or {}
            r = {'src': 'lever', 'co': t, 't': x.get('text'), 'loc': c.get('location') or '', 'all': '; '.join(c.get('allLocations') or []),
                 'team': c.get('team') or '', 'dept': c.get('department') or '', 'u': x.get('hostedUrl'), 'd': x.get('createdAt'), 'ct': x.get('country') or ''}
            if HRX.search(r['t'] or '') or re.search(r'people|talent|human resources|\bhr\b', r['team'] + ' ' + r['dept'], re.I):
                res.append(r)
        return res
    with ThreadPoolExecutor(8) as ex:
        data = [r for rs in ex.map(one, LEVER) for r in rs]
    return data, len(data)


def smartrecruiters():
    terms = ['HR', 'People', 'Personal', 'Recruit', 'Talent', 'Payroll', 'Human Resources', 'Reward', 'Learning', 'Entgelt', 'Personeel']
    out = {}

    def one(arg):
        c, cc, q = arg
        res, off, tot = [], 0, 1
        while off < tot and off < 500:
            try:
                j = getj(f'https://api.smartrecruiters.com/v1/companies/{c}/postings?country={cc}&q={urllib.parse.quote(q)}&limit=100&offset={off}', tries=1)
            except Exception:
                break
            tot = j.get('totalFound') or 0
            for p in j.get('content') or []:
                loc = p.get('location') or {}
                res.append((p['id'], {'co': (p.get('company') or {}).get('name'), 't': p.get('name'), 'cc': cc, 'city': loc.get('city'),
                                      'reg': loc.get('region'), 'd': (p.get('releasedDate') or '')[:10],
                                      'u': f'https://jobs.smartrecruiters.com/{c}/{p["id"]}',
                                      'lvl': (p.get('experienceLevel') or {}).get('label'), 'fn': (p.get('function') or {}).get('label'),
                                      'tt': (p.get('typeOfEmployment') or {}).get('label')}))
            if not j.get('content'):
                break
            off += 100
        return res
    args = [(c, cc, q) for c in SMARTR for cc in ['gb', 'ie', 'dk', 'de', 'nl'] for q in terms]
    with ThreadPoolExecutor(8) as ex:
        for rs in ex.map(one, args):
            for i, v in rs:
                out[i] = v
    data = [{'id': i, **v} for i, v in out.items()]
    return {'src': 'smartrecruiters', 'data': data}, len(data)


if __name__ == '__main__':
    t0 = time.time()
    sources = [('jobtech', jobtech, 100), ('eures', eures, 1000), ('jobnet', jobnet, 50), ('nhs', nhs, 200),
               ('workhub', workhub, 200), ('publicjobs', publicjobs, 50), ('greenhouse', greenhouse, 10),
               ('lever', lever, 5), ('smartrecruiters', smartrecruiters, 20)]
    with ThreadPoolExecutor(len(sources)) as ex:
        list(ex.map(lambda s: run(*s), sources))
    print(f'done in {time.time() - t0:.0f}s')
    status = {'run_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'seconds': round(time.time() - t0), 'problems': problems}
    json.dump(status, open(os.path.join(RAW, 'status.json'), 'w'), indent=1)
    if problems:
        open(os.path.join(RAW, 'problems.txt'), 'w').write('\n'.join(problems))
        print('PROBLEMS:\n' + '\n'.join(problems))

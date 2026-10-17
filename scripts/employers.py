"""Read HR jobs straight from top employers' own careers sites.

Each employer in companies/targets.json names its recruitment system and the
identifiers its public job feed needs. One reader per system type. Results go
to raw/employers.json; per-employer counts go to raw/employers_status.json so
broken feeds are easy to spot.
"""
import datetime, json, re, html, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
COUNTRY = {'se': 'Sweden', 'gb': 'United Kingdom', 'ie': 'Ireland'}
GEO = {
    'ie': re.compile(r'\b((?<!northern )ireland|éire|eire|dublin|cork|galway|limerick|waterford|kilkenny|athlone|sligo|letterkenny|drogheda|dundalk|swords|blanchardstown|sandyford|leopardstown|cherrywood|carlow|shannon|ennis|tralee|naas|maynooth|wexford|clonmel|castlebar|mullingar|carrigtwohill|ringaskiddy|little island|grange castle|leixlip|clonee)\b', re.I),
    'se': re.compile(r'\b(sweden|sverige|swe|stockholm|göteborg|gothenburg|malmö|malmo|uppsala|linköping|linkoping|västerås|vasteras|örebro|orebro|södertälje|sodertalje|sandviken|lund|umeå|umea|luleå|lulea|jönköping|jonkoping|gävle|gavle|karlskoga|kiruna|skellefteå|skelleftea|borås|boras|eskilstuna|helsingborg|norrköping|norrkoping|sundsvall|solna|sundbyberg|kista|huskvarna|mölndal|molndal|halmstad|växjö|vaxjo|trollhättan|ludvika|gällivare|boden|östersund|karlstad|falun|kalmar)\b', re.I),
    'gb': re.compile(r'\b(united kingdom|uk|u\.k\.|great britain|gb|england|scotland|wales|northern ireland|london|manchester|birmingham|leeds|glasgow|edinburgh|bristol|cardiff|belfast|liverpool|sheffield|newcastle|nottingham|leicester|reading|cambridge|oxford|coventry|derby|milton keynes|southampton|brentford|stevenage|uxbridge|hatfield|leatherhead|slough|watford|crawley|chester|warwick|gaydon|solihull|halewood|whitley|bracknell|basingstoke|swindon|york|hull|aberdeen|dundee|preston|bolton|stockport|croydon|hounslow|isleworth|chiswick|osterley|heathrow|wythenshawe|knutsford|staines|guildford|woking|maidenhead|northampton|peterborough|ipswich|norwich|exeter|plymouth|portsmouth|bradford|wakefield|doncaster|sunderland|middlesbrough)\b', re.I),
}
TERMS = {'se': ['HR', 'Human Resources', 'People', 'Talent', 'Recruit', 'Payroll', 'Rekryt', 'Lön', 'Personal', 'Reward', 'Learning'],
         'gb': ['HR', 'Human Resources', 'People', 'Talent', 'Recruit', 'Payroll', 'Reward', 'Learning', 'Employee Relations', 'Resourcing'],
         'ie': ['HR', 'Human Resources', 'People', 'Talent', 'Recruit', 'Payroll', 'Reward', 'Learning', 'Employee Relations', 'Resourcing']}


import threading, urllib.error
WD_GATE = threading.Semaphore(4)


def req(url, data=None, headers=None, timeout=30, method=None):
    h = {'User-Agent': UA, 'Accept': 'application/json, text/html;q=0.9, */*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=body, headers=h, method=method or ('POST' if body else 'GET'))
    gate = WD_GATE if 'myworkday' in url else None
    for i in range(5):
        try:
            if gate: gate.acquire()
            try:
                with urllib.request.urlopen(r, timeout=timeout) as resp:
                    return resp.read().decode('utf-8', 'replace')
            finally:
                if gate: time.sleep(0.4); gate.release()
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and i < 4:
                time.sleep(6 * (i + 1)); continue
            raise


def strip(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def in_country(cc, *texts):
    return bool(GEO[cc].search(' '.join(t or '' for t in texts)))


# ---------------- Workday ----------------
def workday(c, cc):
    base = f"https://{c['tenant']}.{c['wd']}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    first = json.loads(req(api, {'appliedFacets': {}, 'limit': 20, 'offset': 0, 'searchText': ''}))
    facets = {}
    for f in first.get('facets') or []:
        stack = [f]
        while stack:
            g = stack.pop()
            p = g.get('facetParameter') or ''
            for v in g.get('values') or []:
                if 'values' in v and 'facetParameter' in v:
                    stack.append(v)
                elif re.search(r'country', p, re.I) and (v.get('descriptor') or '').strip().lower() == COUNTRY[cc].lower():
                    facets = {p: [v['id']]}
    out = {}
    for term in TERMS[cc]:
        off = 0
        while off < 200:
            j = json.loads(req(api, {'appliedFacets': facets, 'limit': 20, 'offset': off, 'searchText': term}))
            posts = j.get('jobPostings') or []
            for p in posts:
                loc = p.get('locationsText') or ''
                if not facets and not (c.get('local') or in_country(cc, loc, p.get('title'))):
                    continue
                url = f"{base}/en-US/{c['site']}{p.get('externalPath', '')}"
                out[url] = {'t': p.get('title'), 'loc': loc, 'u': url, 'd': p.get('postedOn') or ''}
            off += 20
            if len(posts) < 20 or off >= (j.get('total') or 0):
                break
    return list(out.values())


# ---------------- Oracle Recruiting Cloud ----------------
def oracle(c, cc):
    out = {}
    for term in TERMS[cc]:
        url = (f"https://{c['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
               f"&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={c['site']},"
               f"limit=100,keyword=%22{urllib.parse.quote(term)}%22,sortBy=POSTING_DATES_DESC")
        j = json.loads(req(url))
        for it in j.get('items') or []:
            for r in it.get('requisitionList') or []:
                loc = r.get('PrimaryLocation') or ''
                if not (c.get('local') or in_country(cc, loc)):
                    continue
                u = f"https://{c['host']}/hcmUI/CandidateExperience/en/sites/{c['site']}/job/{r['Id']}"
                out[u] = {'t': r.get('Title'), 'loc': loc, 'u': u, 'd': (r.get('PostedDate') or '')[:10]}
    return list(out.values())


# ---------------- SuccessFactors career sites (RMK), via their RSS feed ----------------
def rmk(c, cc):
    out = {}
    for term in TERMS[cc]:
        for loc_q in ([''] if c.get('local') else [COUNTRY[cc], '']):
            q = {'locale': 'en_US', 'keywords': f'({term})', 'sortColumn': 'referencedate', 'sortDirection': 'desc'}
            if loc_q:
                q['location'] = loc_q
            try:
                x = req(f"https://{c['host']}/services/rss/job/?" + urllib.parse.urlencode(q), headers={'Accept': 'application/rss+xml, text/xml, */*'})
            except Exception:
                continue
            for it in re.findall(r'<item>(.*?)</item>', x, re.S):
                g = lambda n: html.unescape((re.search(rf'<{n}[^>]*>(.*?)</{n}>', it, re.S) or [None, ''])[1]).replace('<![CDATA[', '').replace(']]>', '').strip()
                title, link, desc = g('title'), g('link'), strip(g('description'))
                m = re.match(r'^(.*?)\s*\(([^()]*)\)\s*$', title)
                t, loc = (m.group(1), m.group(2)) if m else (title, '')
                if not (c.get('local') or in_country(cc, loc, title, desc[:300])):
                    continue
                d = g('pubDate')
                try:
                    d = time.strftime('%Y-%m-%d', time.strptime(d[:16], '%a, %d %b %Y'))
                except Exception:
                    d = ''
                out[link] = {'t': t, 'loc': loc, 'u': link, 'd': d}
            if out and loc_q:
                break
    return list(out.values())


# ---------------- Teamtailor ----------------
def teamtailor(c, cc):
    out = {}
    try:
        x = req(f"https://{c['host']}/jobs.rss", headers={'Accept': 'application/rss+xml, text/xml, */*'})
        for it in re.findall(r'<item>(.*?)</item>', x, re.S):
            g = lambda n: html.unescape((re.search(rf'<{n}[^>]*>(.*?)</{n}>', it, re.S) or [None, ''])[1]).replace('<![CDATA[', '').replace(']]>', '').strip()
            d = g('pubDate')
            try:
                d = time.strftime('%Y-%m-%d', time.strptime(d[:16], '%a, %d %b %Y'))
            except Exception:
                d = ''
            out[g('link')] = {'t': g('title'), 'loc': strip(g('tt:location') or g('location')), 'u': g('link'), 'd': d}
    except Exception:
        pass
    if not out:
        x = req(f"https://{c['host']}/jobs", headers={'Accept': 'text/html'})
        for href, inner in re.findall(r'<a[^>]+href="((?:https?://[^"]+)?/jobs/\d+[^"]*)"[^>]*>(.*?)</a>', x, re.S):
            u = href if href.startswith('http') else f"https://{c['host']}{href}"
            t = strip(inner)
            if t:
                out[u] = {'t': t, 'loc': '', 'u': u, 'd': ''}
    return list(out.values())


# ---------------- Eightfold ----------------
def eightfold(c, cc):
    out = {}
    for term in TERMS[cc][:6]:
        start = 0
        while start < 200:
            j = json.loads(req(f"https://{c['host']}/api/apply/v2/jobs?domain={c['domain']}&query={urllib.parse.quote(term)}"
                               f"&location={urllib.parse.quote(COUNTRY[cc])}&start={start}&num=50&sort_by=timestamp"))
            ps = j.get('positions') or []
            for p in ps:
                loc = p.get('location') or ', '.join(p.get('locations') or [])
                if not in_country(cc, loc):
                    continue
                u = p.get('canonicalPositionUrl') or f"https://{c['host']}/careers?pid={p.get('id')}"
                ts = p.get('t_create')
                out[u] = {'t': p.get('name'), 'loc': loc, 'u': u, 'd': time.strftime('%Y-%m-%d', time.gmtime(ts)) if ts else ''}
            start += 50
            if len(ps) < 50:
                break
    return list(out.values())


# ---------------- SmartRecruiters / Greenhouse ----------------
def smartrecruiters(c, cc):
    out = {}
    off = 0
    while off < 1000:
        j = json.loads(req(f"https://api.smartrecruiters.com/v1/companies/{c['id']}/postings?country={cc}&limit=100&offset={off}"))
        for p in j.get('content') or []:
            loc = p.get('location') or {}
            u = f"https://jobs.smartrecruiters.com/{c['id']}/{p['id']}"
            out[u] = {'t': p.get('name'), 'loc': ', '.join(x for x in [loc.get('city'), loc.get('region')] if x), 'u': u, 'd': (p.get('releasedDate') or '')[:10]}
        off += 100
        if off >= (j.get('totalFound') or 0):
            break
    return list(out.values())


def greenhouse(c, cc):
    j = json.loads(req(f"https://boards-api.greenhouse.io/v1/boards/{c['id']}/jobs"))
    out = []
    for p in j.get('jobs') or []:
        loc = (p.get('location') or {}).get('name') or ''
        if in_country(cc, loc):
            out.append({'t': p.get('title'), 'loc': loc, 'u': p.get('absolute_url'), 'd': (p.get('updated_at') or '')[:10]})
    return out


# ---------------- Radancy (TalentBrew) ----------------
def radancy(c, cc):
    out = {}
    for term in TERMS[cc][:6]:
        q = {'ActiveFacetID': 0, 'CurrentPage': 1, 'RecordsPerPage': 100, 'Distance': 50, 'RadiusUnitType': 0, 'Keywords': term,
             'Location': COUNTRY[cc], 'ShowRadius': 'False', 'IsPagination': 'False', 'FacetType': 0,
             'SearchResultsModuleName': 'Search Results', 'SearchFiltersModuleName': 'Search Filters', 'SortCriteria': 0, 'SortDirection': 0, 'SearchType': 5}
        x = req(f"https://{c['host']}/{c.get('lang', 'en')}/search-jobs/results?" + urllib.parse.urlencode(q), headers={'X-Requested-With': 'XMLHttpRequest'})
        try:
            body = json.loads(x).get('results') or ''
        except Exception:
            body = x
        for li in re.findall(r'<li[^>]*>(.*?)</li>', body, re.S):
            m = re.search(r'<a[^>]+href="([^"]*/job/[^"]+)"[^>]*>(.*?)</a>', li, re.S)
            if not m:
                continue
            title = strip((re.search(r'<h2[^>]*>(.*?)</h2>', m.group(2), re.S) or [None, m.group(2)])[1])
            loc = strip((re.search(r'class="[^"]*job-location[^"]*"[^>]*>(.*?)</span>', li, re.S) or [None, ''])[1])
            d = strip((re.search(r'class="[^"]*job-date-posted[^"]*"[^>]*>(.*?)</span>', li, re.S) or [None, ''])[1])
            if not in_country(cc, loc, title):
                continue
            u = urllib.parse.urljoin(f"https://{c['host']}/", m.group(1))
            out[u] = {'t': title, 'loc': loc, 'u': u, 'd': ''}
    return list(out.values())


# ---------------- Phenom ----------------
def phenom(c, cc):
    out = {}
    for term in TERMS[cc][:6]:
        body = {'lang': c['locale'], 'deviceType': 'desktop', 'country': c['country'], 'pageName': 'search-results', 'ddoKey': 'refineSearch',
                'sortBy': 'Most recent', 'subsearch': '', 'from': 0, 'jobs': True, 'counts': True, 'all_fields': ['country', 'city', 'category'],
                'size': 100, 'clearAll': False, 'jdsource': 'facets', 'isSliderEnable': False, 'pageId': 'page20', 'siteType': 'external',
                'keywords': term, 'global': True, 'selected_fields': {}}
        if not c.get('local'):
            body['selected_fields'] = {'country': [COUNTRY[cc]]}
        j = json.loads(req(f"https://{c['host']}/widgets", body, headers={'Origin': f"https://{c['host']}", 'Referer': f"https://{c['host']}/"}))
        jobs = ((j.get('refineSearch') or {}).get('data') or {}).get('jobs') or []
        for p in jobs:
            loc = p.get('location') or ', '.join(x for x in [p.get('city'), p.get('country')] if x)
            if not (c.get('local') or in_country(cc, loc, p.get('country'))):
                continue
            u = p.get('applyUrl') or f"https://{c['host']}/{c['locale'].replace('_', '/')}/job/{p.get('jobId')}"
            out[u] = {'t': p.get('title'), 'loc': loc, 'u': u, 'd': (p.get('postedDate') or '')[:10]}
    return list(out.values())



# ---------------- Amazon (amazon.jobs public search feed) ----------------
ISO3 = {'se': 'SWE', 'gb': 'GBR', 'ie': 'IRL'}
def amazon(c, cc):
    out = {}
    for term in ['HR', 'Human Resources', 'People', 'Recruit', 'Talent', 'Payroll', 'Learning']:
        for off in range(0, 500, 100):
            q = urllib.parse.urlencode({'base_query': term, 'normalized_country_code[]': ISO3[cc], 'result_limit': 100, 'offset': off, 'sort': 'recent'})
            j = json.loads(req('https://www.amazon.jobs/en/search.json?' + q))
            jobs = j.get('jobs') or []
            for p in jobs:
                d = ''
                try: d = datetime.datetime.strptime(p.get('posted_date') or '', '%B %d, %Y').date().isoformat()
                except Exception: pass
                out[p.get('id_icims') or p.get('job_path')] = {'t': p.get('title'), 'loc': p.get('normalized_location') or p.get('location') or '',
                                                              'u': 'https://www.amazon.jobs' + (p.get('job_path') or ''), 'd': d}
            if len(jobs) < 100: break
    return list(out.values())


# ---------------- Lever ----------------
def lever(c, cc):
    j = json.loads(req(f"https://api.{'eu.' if c.get('eu') else ''}lever.co/v0/postings/{c['id']}?mode=json"))
    out = []
    for p in j:
        cat = p.get('categories') or {}
        loc = ' '.join([cat.get('location') or ''] + (cat.get('allLocations') or []) + [p.get('country') or ''])
        if in_country(cc, loc) or (p.get('country') or '').lower() == cc:
            d = datetime.datetime.fromtimestamp((p.get('createdAt') or 0) / 1000).date().isoformat() if p.get('createdAt') else ''
            out.append({'t': p.get('text'), 'loc': cat.get('location') or '', 'u': p.get('hostedUrl'), 'd': d})
    return out


READERS = {'amazon': amazon, 'lever': lever, 'workday': workday, 'oracle': oracle, 'rmk': rmk, 'teamtailor': teamtailor, 'eightfold': eightfold,
           'smartrecruiters': smartrecruiters, 'greenhouse': greenhouse, 'radancy': radancy, 'phenom': phenom}


def run_all(path='companies/targets.json'):
    targets = json.load(open(path, encoding='utf-8'))
    jobs = [(cc, c) for cc, lst in targets.items() for c in lst]
    status, data = [], []

    def one(arg):
        cc, c = arg
        t0 = time.time()
        try:
            rows = READERS[c['type']](c, cc)
            return cc, c, rows, None, time.time() - t0
        except Exception as e:
            return cc, c, [], f'{type(e).__name__}: {str(e)[:150]}', time.time() - t0

    with ThreadPoolExecutor(16) as ex:
        for cc, c, rows, err, secs in ex.map(one, jobs):
            for r in rows:
                data.append({'c': cc, 'co': c['name'], **r})
            status.append({'c': cc, 'name': c['name'], 'type': c['type'], 'jobs': len(rows), 'error': err, 'secs': round(secs)})
    return data, status


if __name__ == '__main__':
    data, status = run_all()
    for s in status:
        print(s)
    print(len(data))

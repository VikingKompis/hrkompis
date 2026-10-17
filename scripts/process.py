import json, re, datetime, collections, os, sys

RAW = os.environ.get('RAW_DIR', 'raw')
OUT = os.environ.get('OUT_FILE', 'data/jobs.json')
TODAY = datetime.date.today()
def D(n):
    p = os.path.join(RAW, n + '.json')
    if not os.path.exists(p): return {'data': []} if n != 'lever' else []
    return json.load(open(p, encoding='utf-8'))

def ms2d(v):
    try: return datetime.datetime.fromtimestamp(int(v) / 1000, datetime.timezone.utc).date().isoformat()
    except Exception: return ''

def clean(s): return re.sub(r'\s+', ' ', (s or '')).strip()

# ---------------- HR relevance ----------------
NEG = re.compile(r'machine learning|deep learning|learning engineer|software|developer|engineer(?!ing manager.*people)|scientist|data science|top talent program|account executive|sales (manager|executive|representative|agent)|nurse|doctor|physician|therap|teacher(?! of hr)|driver|chauffeur|cleaner|cleaning|operative|warehouse|lager|kraftfahrer|monteur|postbote|zusteller|kassierer|verkäufer|koch\b|kok\b|schoonmak|verpleeg|leerling (?!hr)|tømrer|produktionsmedarbejder|store manager|filialleiter|callcenter|call-center', re.I)
POS = re.compile(r'''\bhr\b|\bhr[-/ ]|hrbp|\bhris\b|\bhrm\b|human resource|people (partner|operations|ops|director|lead|manager|team|experience|business|advisor|adviser|specialist|coordinator|analytics|programs?|systems|consultant|generalist|officer|administrator|services|support)|people (&|and) (culture|organi[sz]ation|od|capability|change)|chief people|head of people|vp,? people|people & culture|people and culture|talent (acquisition|partner|manager|lead|sourc|attraction|management|development|director|specialist|strategy|programme|program)|recruit|sourcer|headhunt|executive search|resourcing|payroll|reward|compensation|\bc&b\b|benefits (manager|specialist|analyst|lead|partner|advisor|administrator)|learning (and|&) development|\bl&d\b|learning (partner|specialist|manager|consultant|designer|lead|director|business partner|experience|technolog)|leadership development|organi[sz]ation(al)? development|\bod\b|employee relations|employee experience|organi[sz]ation(al)? effectiveness|people data|workforce (planning|analyst|manager|lead|information)|culture (lead|manager)|employer brand|onboarding|mobility (manager|specialist|partner|advisor)|personal(?!dienstleistung)(referent|sachbearbeit|leit|leiter|entwickl|manager|berater|wesen|abteilung|planung|marketing|chef|verantwort|administ|controll|assist|business|fachkraft|bereich|services|service|recruit|gewinnung|beschaffung|betreuer|koordinat|kaufleute)|personalabteilung|entgelt|lohn(buch|abrechn|\s*und\s*gehalt|-\s*und\s*gehalt)|gehaltsabrechn|recruiting|ausbildungsleit|weiterbildung|p&o|personeel|salaris|werving|opleidingsadviseur|loopbaan|arbeidsrecht|verzuim|rekrutt|rekryt|lønbogholder|lønadministr|lønkonsulent|lønmedarbejder|lønspecialist|lønansvarlig|personale(chef|konsulent|administr|afdeling|sektion|ansvarlig|leder|partner|jura|udvikl)|kompetenceudvikling|arbejdsmiljø|personalchef|personalhandläggare|personaladministr|lön(e|ead|espec|ekons|ehand|ansv)|arbetsrätt|arbetsmiljö|kompetens|ledarskap|förhandl''', re.I)

OCC_OK = re.compile(r'personalsachbearbeiter|personalreferent|personalleiter|leiter/in - personal|personalentwickler|personalberater|lohn- und gehaltsbuchhalter|recruiter|hr business partner|hr-konsulent|hr-partner|lønbogholder|personalekonsulent|personalechef|human resources|hr-specialist|rekryterare|lönespecialist|personalchef|löneadministratör|personaladministratör|hr-generalist|hr-strateg', re.I)
JUNK = re.compile(r'talent (pool|community|network)|join our talent|expression of interest|general application|open application|spontaneous application|initiativbewerbung|open sollicitatie', re.I)
def is_hr(title, extra=''):
    t = re.sub(r'(salaris|salary|gehalt|løn)\s*(tot|vanaf|van|up to|bis|op til|max)\b.*$', '', title, flags=re.I)
    t = re.sub(r'\|\s*(salaris|salary).*$', '', t, flags=re.I)
    t = re.sub(r'\d\s*/\s*(hr|hour)\b|per (hr|hour)', '', t, flags=re.I)
    if JUNK.search(t): return False
    if extra and not OCC_OK.search(extra): extra = ''
    if NEG.search(t) and not re.search(r'\bhr\b|people partner|talent acquisition|recruit|payroll|personal(?!dienstleistung)(referent|leiter|sachbearb)', t, re.I):
        return False
    return bool(POS.search(t)) or bool(extra and POS.search(extra) and not NEG.search(t))

# ---------------- classification ----------------
def family(t):
    t = t.lower()
    if re.search(r'chief people|chro|\bcpo\b|head of (hr|people|human)|(hr|people|personal)[- ]?(direkt|director|chef|leiter|leitung)|personalchef|personalechef|hr[- ]?(manager|chef|lead\b|leader)|people (director|lead\b)|vp,? (hr|people)|director,? (hr|people|human)|leiter/?in -? personal|leitung personal|hr-ansvarig|personalansvarig|hr ansvarlig|manager (p&o|hr)|hoofd (p&o|hr)|interim\w* ?hr-?chef|hr director|people & culture (director|manager|lead)|people and culture (director|manager|lead)|enhetschef hr', t):
        return 'lead'
    if re.search(r'recruit|rekryt|rekrutt|talent acquisition|ta[- ]specialist|ta partner|sourc|headhunt|executive search|resourcing|werving|talangattrakt|personalgewinnung|personalbeschaffung|employer brand|staffing|bemanning|onboarding|disponent', t):
        return 'ta'
    if re.search(r'payroll|reward|compensation|c&b|benefit|salaris|lön|løn|lohn|entgelt|gehalt|mobility', t):
        return 'rew'
    if re.search(r'learning|l&d|leadership dev|ledarskap|lärande|kompetens|talent|organi[sz]ation(al)? dev|organisationsutv|\bod\b|weiterbildung|personalentwickl|ausbildungsleit|opleiding|loopbaan|training|culture|engagement|people consulting|people m&a|change', t):
        return 'tal'
    if re.search(r'employee relations|arbeitsrecht|arbeidsrecht|arbetsrätt|arbetsmiljö|arbejdsmiljø|verzuim|förhandl|industrial relations|labou?r relations|wellbeing|health and safety|occupational', t):
        return 'er'
    if re.search(r'admin|assist|handläggare|sachbearbeit|operations|\bops\b|hris|system|koordinat|coordinator|backoffice|back office|data|analyt|shared service|services|officer|medewerker|medarbejder|fachkraft|kaufmann|kauffrau|schemaspecialist', t):
        return 'ops'
    return 'bp'

def level(t):
    t = t.lower()
    if re.search(r'chief|\bchro\b|\bcpo\b|\bvp\b|vice president|head of|director|direktör|direktor|\bsvp\b|\bevp\b|global head|group hr|hrvp|leitung personal|personaldirekt', t): return 'exec'
    if re.search(r'manager|chef|leiter|leitung|lead\b|leader|ansvarig|ansvarlig|hoofd|teamleider|teamlead|gruppansvar|interim', t): return 'mgr'
    if re.search(r'student|studerande|werkstudent|working student|praktik|intern\b|internship|stage\b|stagiair|trainee|graduate|apprentice|ausbildung zum|ausbildung zur|azubi|extrajobb|junior|\bjr\b|assistent|assistant|kickstarta|studentmedhjælp|elev\b', t): return 'entry'
    if re.search(r'senior|\bsr\.?\b|erfaren|experienced|strateg|expert|principal|specialist på arbetsrätt|arbetsrättsspecialist|business partner|lead\b|referent', t): return 'senior'
    return 'pro'

AGENCY = re.compile(r'recruit|rekryt|rekrutt|bemann|staffing|personnel|personal(dienst|vermittl|partner|service|leasing)|zeitarbeit|arbeitnehmerüberlassung|uitzend|detacher|vikar|randstad|adecco|manpower|hays|michael page|page personnel|robert half|experis|academic work|poolia|jurek|sway sourcing|selecta|novare|clockwork|tng group|zoey|letsgig|oio väst|onepartner|resultat i sverige|quattro|hirely|jobbusters|unik resurs|paragera|framtiden|valora|get skills|lundin & boström|bemannica|nexer|nearyou|bravura|solum search|your talent|gigstep|tranpenad|andara|wise group|sjr in sweden|future people|ps partner|avanzera|quest consulting|tikk takk|emploid|perido|enrival|axö|tacting|studentconsulting|talangbron|we seeq|nxt interim|devotum|made for sales|techrytera|auxante|four potentials|procruitment|sallyq|rubino|jtc linked|boxflow|bolt\.works|westaff|dc talents|barona|nordic talent|jobs by nordics|ekonza|intensogruppen|camai|elitakademin|culpeo|vindex|qtym|ikett|worknordic|snabb jobb|renoa|eiss|teknikakademin|nordic investin|jobandtalent|dfds professionals|recruitive|telin|roi rekrytering|flodin|power people|search|talent ab|talents|headhunt|executive|resourcing|\bjobs\b|careers ltd|appointments|employment (ltd|agency|services)|hux ley|amadeus fire|orizon|piening|dis ag|tempton|persona service|gi group|synergie|start people|tempo-team|yacht|unique|olympia|brunel|hudson|harvey nash|reed\b|path recruitment|cma recruitment|remarkable jobs|essential employment|hamilton|sellick', re.I)
PUBLIC = re.compile(r'kommun|region|regionen|universit|högskola|hogskola|försvarsmakten|kriminalvården|statens|myndighet|regeringskansliet|riksarkivet|sametinget|länsstyrelsen|kungliga|institutionsstyrelse|\bstift\b|ambassad|totalförsvarets|skolforskning|kommunalförbund|karolinska|nhs|trust\b|council|borough|police|government|ministry|department for|hse\b|tusla|county council|city council|department of|office of|an garda|oberstown|civil service|gemeente|provincie|rijksoverheid|ministerie|politie|ziekenhuis|umc\b|hogeschool|universiteit|stadt |landkreis|bundes|landes|land berlin|landeshauptstadt|kreisverwaltung|bezirksamt|klinikum|universitätsklinik|kommune\b|region (hovedstaden|sjælland|syddanmark|midtjylland|nordjylland)|styrelsen|ministeriet|forsvaret|politi', re.I)

def eng_title(t):
    return bool(re.search(r'\b(manager|partner|specialist|advisor|adviser|lead|head|recruiter|payroll|business|people|talent|coordinator|administrator|director|officer|generalist|consultant|associate|analyst)\b', t, re.I)) and not re.search(r'[åäöæøü]|\(m/w/d\)|\(w/m/d\)|søges|sökes|gezocht|medewerker|medarbejder|till |för |hos |für |zur |zum ', t, re.I)

# ---------------- region maps ----------------
DE_NUTS = {'DE1':'Baden-Württemberg','DE2':'Bayern','DE3':'Berlin','DE4':'Brandenburg','DE5':'Bremen','DE6':'Hamburg','DE7':'Hessen','DE8':'Mecklenburg-Vorpommern','DE9':'Niedersachsen','DEA':'Nordrhein-Westfalen','DEB':'Rheinland-Pfalz','DEC':'Saarland','DED':'Sachsen','DEE':'Sachsen-Anhalt','DEF':'Schleswig-Holstein','DEG':'Thüringen'}
NL_NUTS = {'NL11':'Groningen','NL12':'Friesland','NL13':'Drenthe','NL21':'Overijssel','NL22':'Gelderland','NL23':'Flevoland','NL31':'Utrecht','NL35':'Utrecht','NL32':'Noord-Holland','NL36':'Noord-Holland','NL33':'Zuid-Holland','NL34':'Zeeland','NL41':'Noord-Brabant','NL42':'Limburg'}
IE_NUTS = {'IE061':'Dublin','IE062':'Mid-East','IE063':'Midlands','IE051':'Mid-West','IE052':'South-East','IE053':'South-West','IE041':'Border','IE042':'West'}

def dk_region(z):
    try: z = int(z)
    except Exception: return ''
    if z < 3700: return 'Hovedstaden'
    if z < 3800: return 'Hovedstaden'
    if z < 5000: return 'Sjælland'
    if z < 6800: return 'Syddanmark'
    if z < 7000: return 'Midtjylland'
    if z < 7300: return 'Syddanmark'
    if z < 9000: return 'Midtjylland'
    return 'Nordjylland'

def uk_region(loc):
    l = (loc or '').lower()
    if not l: return ''
    if 'london' in l or re.search(r'\b(e|ec|n|nw|se|sw|w|wc)\d', l): return 'London'
    if re.search(r'scotland|edinburgh|glasgow|aberdeen|dundee|inverness|stirling|\b(eh|g|ab|dd|iv|fk|ky|pa|ka|ml)\d', l): return 'Scotland'
    if re.search(r'wales|cardiff|swansea|newport|wrexham|bangor|\b(cf|sa|np|ll|ld|sy)\d', l): return 'Wales'
    if re.search(r'northern ireland|belfast|derry|\bbt\d', l): return 'Northern Ireland'
    if re.search(r'manchester|liverpool|lancashire|cheshire|preston|bolton|wigan|st helens|warrington|chester|blackpool|\b(m|l|pr|bl|wn|wa|ch|ck|bb|ol|sk|fy|la|ca)\d', l): return 'North West'
    if re.search(r'leeds|sheffield|bradford|york|hull|huddersfield|wakefield|doncaster|\b(ls|s|bd|yo|hu|hd|wf|dn|hg|hx)\d', l): return 'Yorkshire'
    if re.search(r'newcastle|sunderland|durham|middlesbrough|teesside|\b(ne|sr|dh|ts|dl)\d', l): return 'North East'
    if re.search(r'birmingham|coventry|wolverhampton|stoke|worcester|hereford|shrewsbury|telford|\b(b|cv|wv|st|wr|hr|ws|dy|tf)\d', l): return 'West Midlands'
    if re.search(r'nottingham|leicester|derby|lincoln|northampton|\b(ng|le|de|ln|nn)\d', l): return 'East Midlands'
    if re.search(r'bristol|bath|exeter|plymouth|gloucester|swindon|cornwall|devon|somerset|dorset|bournemouth|\b(bs|ba|ex|pl|gl|sn|tr|ta|dt|bh|tq)\d', l): return 'South West'
    if re.search(r'cambridge|norwich|ipswich|essex|chelmsford|colchester|luton|bedford|peterborough|hertford|st albans|\b(cb|nr|ip|cm|co|lu|mk|pe|al|sg|ss|hp|en|wd)\d', l): return 'East of England'
    return 'South East'

# ---------------- build ----------------
out = []
def add(**r):
    t = clean(r['t'])
    if not t: return
    r['t'] = t
    r['e'] = clean(r.get('e')) or 'Employer not named'
    r.setdefault('f', family(t)); r.setdefault('v', level(t))
    r['a'] = 1 if r.get('a') or AGENCY.search(r['e']) else 0
    r['g'] = 1 if PUBLIC.search(r['e']) else 0
    r['m'] = 1 if r.get('m') or re.search(r'interim|vikariat|vikarie|fixed[- ]term|maternity|parental|temp\b|temporary|befristet|elternzeit|tijdelijk|barselsvikar', t, re.I) else 0
    out.append(r)

# Sweden (JobTech)
for a in D('jobtech')['data']:
    if not is_hr(a['t'], a.get('o') or ''): continue
    add(o='af', c='se', i=a['id'], t=a['t'], e=a.get('e'), l=a.get('m') or '', r=re.sub(r's? län$', '', a.get('r') or ''),
        p=(a.get('p') or '')[:10], x=(a.get('d') or '')[:10], u=f"https://arbetsformedlingen.se/platsbanken/annonser/{a['id']}",
        h=1 if (a.get('wh') or '').startswith('Del') else 0, n=1 if a.get('lang') == 'en' else 0)

# EURES (DE, NL, IE)
for a in D('eures')['data']:
    full = a['t'] or ''
    m = re.match(r'^(.*?)\s*\(([^()]*)\)\s*$', full)
    title, occ = (m.group(1), m.group(2)) if (m and a['c'] == 'de') else (full, '')
    if occ and re.search(r'personaldisponent', occ, re.I) and not POS.search(re.sub(r'personaldisponent', '', title, flags=re.I)):
        continue
    if not is_hr(title, occ): continue
    code = a.get('n') or ''
    if a['c'] == 'de': reg = DE_NUTS.get(code[:3], '')
    elif a['c'] == 'nl': reg = NL_NUTS.get(code[:4], '')
    else: reg = IE_NUTS.get(code[:5], '')
    add(o='eures', c=a['c'], i=a['id'], t=title, e=a.get('e'), l=reg, r=reg, p=ms2d(a.get('d')), x='',
        u=f"https://europa.eu/eures/portal/jv-se/jv-details/{a['id']}?lang=en",
        h=1 if (a.get('s') == 'parttime') else 0, n=1 if 'en' in (a.get('l') or '') else 0,
        m=1 if a.get('o') in ('temporary',) else 0, hint=(a.get('l') or ''))

# Denmark (Jobnet)
for a in D('jobnet')['data']:
    if not is_hr(a['t'], a.get('o') or ''): continue
    add(o='jobnet', c='dk', i=a['id'], t=a['t'], e=a.get('e'), l=a.get('n') or '', r=dk_region(a.get('z')),
        p=a.get('d') or '', x=a.get('dl') or '', u=a.get('u') or f"https://jobnet.dk/find-job/{a['id']}", h=1 if a.get('pt') else 0, n=1 if eng_title(a['t']) else 0)

# UK: NHS
for a in D('nhs')['data']:
    if not is_hr(a['t']): continue
    loc = a.get('l') or ''
    town = loc.split(',')[0].strip() if loc else ''
    add(o='nhs', c='gb', i='nhs' + a['id'], t=a['t'], e=a.get('e'), l=town, r=uk_region(loc), p=a.get('d') or '', x=a.get('dl') or '',
        u=a.get('u'), s=(a.get('s') or '').replace('.00', ''), n=1, m=1 if re.search(r'fixed|secondment|bank|temporary', a.get('ty') or '', re.I) else 0,
        g=1)

# UK: Work Hub (DWP)
for a in D('workhub')['data']:
    if not is_hr(a['t']): continue
    emp, loc = a.get('e') or '', ''
    if ' - ' in emp: emp, loc = emp.split(' - ', 1)
    tags = a.get('tags') or ''
    add(o='workhub', c='gb', i='wh' + a['id'], t=a['t'], e=emp, l=loc, r=uk_region(loc), p='', x='',
        u=f"https://www.jobs.service.gov.uk/jobs/{a['id']}", s=a.get('s') or '', n=1,
        h=1 if 'Part time' in tags else 0, m=1 if re.search(r'Temporary|Contract', tags) else 0)


# Ireland: publicjobs.ie
import calendar
MON={m[:3].lower():i for i,m in enumerate(calendar.month_name) if m}
def pjdate(s):
    m=re.match(r'(\d+)\s+(\w+)\s+(\d{4})', s or '')
    if not m: return ''
    try: return datetime.date(int(m.group(3)), MON[m.group(2)[:3].lower()], int(m.group(1))).isoformat()
    except Exception: return ''
for a in D('publicjobs')['data']:
    t = re.sub(r'\s*-\s*' + re.escape(a.get('org') or '~~') + r'$', '', a['t'])
    if not is_hr(t) or re.search(r'learning disab|appeals committee|rolling recruitment', t, re.I): continue
    add(o='publicjobs', c='ie', i='pj' + a['u'].split('/opp/')[1].split('-')[0], t=t, e=a.get('org'), l=a.get('loc') or '', r='', p=pjdate(a.get('ad')), x=pjdate(a.get('cd')), u=a['u'], n=1)

# Employer career sites
CC = [('gb', r'united kingdom|\buk\b|england|scotland|wales|london|manchester|edinburgh|glasgow|bristol|birmingham|leeds|cambridge|oxford|belfast|cardiff|reading|nottingham|\bgb\b'),
      ('ie', r'ireland|dublin|cork|galway|limerick|\bie\b'),
      ('dk', r'denmark|copenhagen|københavn|aarhus|odense|\bdk\b'),
      ('de', r'germany|deutschland|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|düsseldorf|stuttgart|leipzig|\bde\b'),
      ('nl', r'netherlands|amsterdam|rotterdam|utrecht|eindhoven|the hague|den haag|\bnl\b')]
def countries(loc):
    return [c for c, rx in CC if re.search(rx, loc or '', re.I)]
NICE = {'adyen':'Adyen','airbnb':'Airbnb','canonical':'Canonical','cloudflare':'Cloudflare','coinbase':'Coinbase','databricks':'Databricks','datadog':'Datadog','deliveroo':'Deliveroo','elastic':'Elastic','figma':'Figma','gitlab':'GitLab','hellofresh':'HelloFresh','intercom':'Intercom','mongodb':'MongoDB','monzo':'Monzo','okta':'Okta','pinterest':'Pinterest','reddit':'Reddit','robinhood':'Robinhood','stripe':'Stripe','sumup':'SumUp','toast':'Toast','trustpilot':'Trustpilot','twilio':'Twilio','wise':'Wise','celonis':'Celonis','flix':'Flix','getyourguide':'GetYourGuide','n26':'N26','traderepublicbank':'Trade Republic','samsara':'Samsara','asana':'Asana','catawiki':'Catawiki','contentful':'Contentful','gocardless':'GoCardless','grafanalabs':'Grafana Labs','kaluza':'Kaluza','squarespace':'Squarespace','tines':'Tines','truecaller':'Truecaller','workato':'Workato','flipdish':'Flipdish','cognism':'Cognism','oura':'Oura','dropbox':'Dropbox','realtimeboardglobal':'Miro','personio':'Personio','hubspot':'HubSpot','zendesk':'Zendesk','docusign':'DocuSign','aircall':'Aircall','contentsquare':'Contentsquare','jumpcloud':'JumpCloud','kpler':'Kpler','matchgroup':'Match Group','outreach':'Outreach','palantir':'Palantir','pigment':'Pigment','qonto':'Qonto','spotify':'Spotify','swile':'Swile','veeva':'Veeva','zoox':'Zoox','binance':'Binance'}
def co(x): return NICE.get(x, x[:1].upper() + x[1:])
for a in D('greenhouse')['data']:
    if not is_hr(a['t']) or re.search(r'machine learning', a['t'], re.I): continue
    for c in countries(a['loc'])[:1] or []:
        add(o='career', c=c, i=f"gh{a['id']}", t=a['t'], e=co(a['co']), l=a['loc'], r=a['loc'].split(',')[0], p=a.get('d') or '', x='', u=a['u'], n=1)
for a in D('lever'):
    if not is_hr(a['t']) or re.search(r'machine learning|top talent program', a['t'], re.I): continue
    cs = countries(a.get('loc', '') + ' ' + a.get('all', '') + ' ' + ({'GB':'uk','IE':'ireland','DK':'denmark','DE':'germany','NL':'netherlands'}.get(a.get('ct'), '')))
    for c in cs[:1]:
        add(o='career', c=c, i='lv' + a['u'].rsplit('/', 1)[-1], t=a['t'], e=co(a['co']), l=a.get('loc', ''), r=(a.get('loc') or '').split(',')[0], p=ms2d(a.get('d')), x='', u=a['u'], n=1)
for a in D('smartrecruiters')['data']:
    if not is_hr(a['t'], 'human resources' if (a.get('fn') or '')=='Human Resources' else ''): continue
    c = a['cc']
    add(o='career', c=c, i='sr' + a['id'], t=a['t'], e=a.get('co'), l=a.get('city') or '', r=a.get('city') or '', p=a.get('d') or '', x='', u=a['u'],
        n=1 if c in ('gb', 'ie') or eng_title(a['t']) else 0, h=1 if 'part' in (a.get('tt') or '').lower() else 0)


# Top employers' own careers sites (companies/targets.json)
SE_CITY = [(r'stockholm|solna|kista|sundbyberg|södertälje|sodertalje|nacka|danderyd|täby|lidingö', 'Stockholm'), (r'göteborg|gothenburg|mölndal|molndal|trollhättan|borås|boras|skövde|lidköping', 'Västra Götaland'),
           (r'malmö|malmo|lund|helsingborg|landskrona|kristianstad', 'Skåne'), (r'uppsala|enköping', 'Uppsala'), (r'linköping|linkoping|norrköping|norrkoping|motala', 'Östergötland'),
           (r'västerås|vasteras', 'Västmanland'), (r'örebro|orebro|karlskoga', 'Örebro'), (r'sandviken|gävle|gavle', 'Gävleborg'), (r'umeå|umea|skellefteå|skelleftea', 'Västerbotten'),
           (r'luleå|lulea|kiruna|gällivare|boden', 'Norrbotten'), (r'jönköping|jonkoping|huskvarna|värnamo', 'Jönköping'), (r'eskilstuna|nyköping|strängnäs', 'Södermanland'),
           (r'sundsvall|örnsköldsvik|härnösand', 'Västernorrland'), (r'karlstad', 'Värmland'), (r'falun|ludvika|borlänge|avesta', 'Dalarna'), (r'halmstad|varberg', 'Halland'),
           (r'växjö|vaxjo|älmhult', 'Kronoberg'), (r'kalmar|västervik|oskarshamn', 'Kalmar'), (r'östersund', 'Jämtland'), (r'karlskrona|ronneby', 'Blekinge'), (r'visby|gotland', 'Gotland')]
def se_region(loc):
    for rx, reg in SE_CITY:
        if re.search(rx, loc or '', re.I): return reg
    return ''
def wd_date(s):
    s = (s or '').lower()
    if re.match(r'\d{4}-\d{2}-\d{2}', s): return s[:10]
    n = 0
    if 'today' in s: n = 0
    elif 'yesterday' in s: n = 1
    else:
        m = re.search(r'(\d+)\+?\s*day', s)
        if not m: return ''
        n = int(m.group(1))
    return (TODAY - datetime.timedelta(days=n)).isoformat()
import hashlib
for a in D('employers')['data']:
    t = a.get('t') or ''
    if not is_hr(t): continue
    loc = a.get('loc') or ''
    c = a['c']
    add(o='career', c=c, i='em' + hashlib.md5(a['u'].encode()).hexdigest()[:12], t=t, e=a['co'], l=loc,
        r=se_region(loc) if c == 'se' else uk_region(loc) if c == 'gb' else '', p=wd_date(a.get('d')), x='', u=a['u'],
        n=1 if c == 'gb' or eng_title(t) else 0)

# fix region for Germany career-site rows etc.: keep city as region where no region known
# ---------------- ad language ----------------
DE_M = re.compile(r'\b[mwfd]\s*[/|]\s*[wmf]\s*[/|]\s*(d|x|div)|\(all genders?\)|[äöüß]|\b(und|für|mit|zur|zum|im|bei|sachbearbeit|referent|leiter|leitung|personal|mitarbeiter|kauf(mann|frau)|abrechnung|entgelt|lohn|gehalt|stellvertret|teilzeit|vollzeit|befristet|werkstudent|gn\b|standort|bereich|schwerpunkt|vertrieb|technik|berlin|münchen|hamburg|köln|frankfurt|stuttgart|düsseldorf|leipzig|dresden|hannover|nürnberg|bremen|essen|dortmund|bonn|mannheim|karlsruhe)', re.I)
NL_M = re.compile(r'\b(medewerker|adviseur|salaris|personeel|werving|en|voor|bij|van|de|het|stagiair|stage|uur|regio|ervaren|zelfstandig|functioneel|beheerder|administratief|hoofdkantoor|opleidingen|leidinggevende|teamleider|onderwijs|zorg|gemeente|bouw|techniek|technisch|logistiek|overheid|sociaal|domein|horeca|energie|installatie|industrie|metaal|transport|uitzend|detachering|afstudeer|werkstudent|parttime|fulltime|binnendienst|buitendienst|zuid|noord|oost|west|amsterdam|rotterdam|utrecht|eindhoven|groningen|brabant|holland|limburg|gelderland|zeeland|twente|vacature|ondersteun|beleid|arbo|verzuim|loopbaan|ontwikkeling)\b|ij\w|\bp&o\b', re.I)
SV_M = re.compile(r'[åäö]|\b(till|för|och|med|söker|sökes|rekryterare|lön|personal|chef|handläggare|vikariat|kommun|region)\b', re.I)
EN_M = re.compile(r'\b(manager|partner|specialist|advisor|adviser|lead|head|recruiter|payroll|business|people|talent|coordinator|administrator|director|officer|generalist|consultant|associate|analyst|assistant|human resources|acquisition|operations|reward|learning|development|senior|junior)\b', re.I)
def lang_of(r, hint=''):
    c, t = r['c'], r['t']
    if c in ('gb', 'ie'): return 'en'
    if c == 'se': return 'en' if r.get('n') else 'sv'
    langs = [x for x in (hint or '').split(',') if x]
    if r['o'] == 'eures' and langs == ['en']: return 'en'
    if c == 'de' and DE_M.search(t): return 'de'
    if c == 'nl' and NL_M.search(t): return 'nl'
    if c == 'dk' and re.search(r'[æøå]|\b(og|til|med|søges|søger|medarbejder|konsulent|løn|vi|du|af|for)\b', t, re.I): return 'other'
    if EN_M.search(t): return 'en'
    return {'de': 'de', 'nl': 'nl'}.get(c, 'other')

# ---------------- dedupe ----------------
seen, final = set(), []
for r in out:
    k = (r['c'], re.sub(r'\W+', '', r['t'].lower())[:60], re.sub(r'\W+', '', r['e'].lower())[:30], (r.get('l') or '').lower()[:20])
    if k in seen: continue
    seen.add(k); final.append(r)

# drop stale (published > 120 days ago)
def fresh(r):
    if not r.get('p'): return True
    try: return (TODAY - datetime.date.fromisoformat(r['p'])).days <= 120
    except Exception: return True
final = [r for r in final if fresh(r)]

for r in final:
    r['lg'] = lang_of(r, r.pop('hint', ''))
    r['n'] = 1 if r['lg'] == 'en' else 0
    for k in ('s', 'x', 'p', 'l', 'r'): r.setdefault(k, '')
    for k in ('h', 'n'): r.setdefault(k, 0)

stats = {'total': len(final), 'by_country': dict(collections.Counter(r['c'] for r in final)), 'by_source': dict(collections.Counter(r['o'] for r in final))}
print(json.dumps(stats, indent=1))
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
asof = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
json.dump({'asof': asof, 'stats': stats, 'jobs': final}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

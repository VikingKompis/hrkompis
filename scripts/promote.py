"""Turn crawler findings (companies/<list>.discovered.json) into live feeds in companies/targets.json.

Usage: python scripts/promote.py mnc se gb ie
Adds each company with a readable recruitment system to every listed country, skipping names already there.
"""
import json, re, sys, urllib.parse

def entry(r):
    for h in r['ats']:
        a, ids = h['ats'], h['ids']
        if a == 'workday' and ids[2] not in ('wday', 'en-US'):
            return {'type': 'workday', 'tenant': ids[0].lower(), 'wd': ids[1].lower(), 'site': ids[2]}
        if a == 'oracle': return {'type': 'oracle', 'host': ids[0], 'site': ids[1]}
        if a == 'greenhouse' and ids[0] not in ('embed', 'v1'): return {'type': 'greenhouse', 'id': ids[0]}
        if a == 'lever': return {'type': 'lever', 'id': ids[0]}
        if a == 'smartrecruiters' and ids[0].lower() not in ('company', 'oneclick-ui', 'widget'): return {'type': 'smartrecruiters', 'id': ids[0]}
        if a == 'eightfold': return {'type': 'eightfold', 'host': ids[0] + '.eightfold.ai', 'domain': ids[0] + '.com'}
    host = urllib.parse.urlparse(r.get('final') or r['url']).netloc
    if 'sf_rmk' in r['markers']: return {'type': 'rmk', 'host': host}
    if 'radancy' in r['markers']: return {'type': 'radancy', 'host': host, 'lang': 'en'}
    return None

lst, countries = sys.argv[1], sys.argv[2:]
found = json.load(open(f'companies/{lst}.discovered.json', encoding='utf-8'))
T = json.load(open('companies/targets.json', encoding='utf-8'))
added, missing = 0, []
for r in found:
    e = entry(r) if r['name'] != 'Amazon' else {'type': 'amazon'}
    if not e:
        missing.append(r['name']); continue
    for cc in countries:
        T.setdefault(cc, [])
        if any(x['name'] == r['name'] for x in T[cc]): continue
        T[cc].append({'name': r['name'], **e}); added += 1
json.dump(T, open('companies/targets.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'added {added} feeds; no readable system found for {len(missing)}: ' + ', '.join(missing))

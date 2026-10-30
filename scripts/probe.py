"""Fetch a list of URLs (probe/urls.txt) from GitHub's network and save each response to probe/out/ for inspection."""
import os, re, json, urllib.request, http.cookiejar
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
os.makedirs('probe/out', exist_ok=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
idx = []
for n, url in enumerate(l.strip() for l in open('probe/urls.txt') if l.strip() and not l.startswith('#')):
    rec = {'n': n, 'url': url}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'})
        with op.open(req, timeout=30) as r:
            body = r.read(600_000).decode('utf-8', 'replace')
            rec.update(status=r.status, final=r.geturl(), type=r.headers.get('Content-Type'), size=len(body))
    except urllib.error.HTTPError as e:
        body = e.read(50_000).decode('utf-8', 'replace'); rec.update(status=e.code)
    except Exception as e:
        body = ''; rec.update(error=str(e)[:200])
    open(f'probe/out/{n:02d}.txt', 'w', encoding='utf-8').write(body)
    idx.append(rec); print(rec)
json.dump(idx, open('probe/out/index.json', 'w'), indent=1)

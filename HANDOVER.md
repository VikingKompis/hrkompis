# Handover: HRKompis

Read this first in any new session; rewrite it at the end. The README has the technical summary; AUDIT.md is rewritten automatically every morning.

_Last updated: 13 Nov 2026_

## What's live
- https://hrkompis.com (Cloudflare Pages, built from `site/` + `data/jobs.json` on every push). "Only HR jobs": search by country, sector, ad language, HR job family.
- Daily refresh at 05:00 Stockholm via GitHub Actions (`daily-refresh.yml`); an email alert fires if a source fails, and yesterday's data for that source is kept.
- About 9,900 HR jobs after de-duplication (8 Nov audit): UK, Ireland, Netherlands, Germany, Denmark, Sweden.
- Sources: JobTech (Arbetsförmedlingen), EURES, Jobnet, NHS Jobs, UK Work Hub, publicjobs.ie, Adzuna (kept max 14 days), and employer career sites on Greenhouse, Lever and SmartRecruiters (`companies/`).

## Who depends on it
- **JobKompis** ranks this feed in the browser (`raw.githubusercontent.com/VikingKompis/hrkompis/main/data/jobs.json`). Erik's paused "Senior HR role watch" reads it too. Don't change field names (t, e, c, l, v, f, fs, u …) without updating JobKompis.

## Decisions (Erik)
- Aim: representative enough that anything reaching LinkedIn is probably already here; go upstream to company career sites, prioritising multinationals with English as company language. Focus Sweden, UK, Ireland.
- Include the top ~50 companies' career sites per country, starting with Sweden and the UK.

## Known gap
- Senior Swedish roles are thin: in the 30 days to 6 Nov only 19 director-level HR ads in Sweden (10 in Stockholm, mostly interim, agency or public sector). The UK had 158. Most senior roles go through headhunters or company sites not yet covered.

## Next big step: the company index for all functions (Erik, 13 Nov)
Decision: once a company is connected, take ALL its jobs (HR, IT, finance, sales…), not just HR, and build country by country over time. This feeds JobKompis for every field; hrkompis.com keeps showing HR only.
- **Already in place:** `scripts/employers.py` reads 11 hiring systems (Workday, Oracle, SuccessFactors/rmk, Teamtailor, Eightfold, SmartRecruiters, Greenhouse, Radancy, Phenom, Amazon, Lever) for ~260 companies in `companies/*.json`. It only fetches HR jobs because each reader loops over HR search `TERMS`.
- **Change:** a per-company switch `"all": true` (start with Swedish and UK companies) that searches with an empty term and pages through everything; tag each job with a function family (HR, IT, finance, sales, marketing, operations, engineering, other) using title rules (no AI).
- **Output:** keep `data/jobs.json` HR-only for hrkompis.com; add `data/all/<cc>-<family>.json` (one small file per country and function) so JobKompis loads only what a person's search needs. Watch GitHub Actions run time (6 h limit) and repo size; drop jobs older than 45 days.
- **Add readers:** Varbi and ReachMee (Swedish employers, public sector), then Workday tenants for the big Swedish employers not yet listed.
- **Then in JobKompis:** use these files for non-HR fields alongside Platsbanken (today non-HR uses only Platsbanken).

## Next steps
1. Add career sites of large Swedish employers on Workday, Teamtailor, Varbi and ReachMee (the platforms not yet covered).
2. Check JobTech coverage against the feed for HR-direktör / HR Director / Head of HR.
3. Keep LinkedIn off-limits.

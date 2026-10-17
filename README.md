# HRKompis data

Open HR roles across the UK, Ireland, Denmark, Germany, the Netherlands and Sweden,
refreshed every day at 05:00 Stockholm time by GitHub Actions.

- `scripts/fetch.py` pulls ads from Arbetsförmedlingen JobTech, EURES, Jobnet, NHS Jobs,
  the UK Work Hub, publicjobs.ie and employer career sites (Greenhouse, Lever, SmartRecruiters).
- `scripts/process.py` keeps HR roles only and tags each with country, sector, ad language,
  HR job family and level, then writes `data/jobs.json`.
- `site/` is the hrkompis.com front end. It reads `data/jobs.json` from this repository.

If a source fails, yesterday's data for that source is kept and the run is marked failed,
which sends an email alert. Run it by hand from the Actions tab with "Run workflow".

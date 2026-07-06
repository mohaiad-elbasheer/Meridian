# Going live: exact requirements checklist

Everything in the codebase is ready for live ingestion. What live data needs is an
**environment, not more code** — specifically:

| # | Requirement | Status / where to get it |
|---|---|---|
| 1 | A machine with open internet to the providers (`services9.arcgis.com`, `data.gdeltproject.org`, `earthquake.usgs.gov`, `gdacs.org`, `comtradeapi.un.org`) | Your GitHub Codespace or any laptop/server qualifies. The Claude development sandbox does **not** (egress policy) — which is why live data never appears there. |
| 2 | The database running | `docker compose up -d db` |
| 3 | `.env` prepared | `cp .env.example .env` (in Codespaces also: `sed -i 's/@db:5432/@localhost:5432/' .env`). PortWatch URLs are already pinned; **no API key needed** for PortWatch, GDELT, USGS, GDACS. |
| 4 | (Once) verify the pinned PortWatch endpoints | `python -m meridian_ingest.verify_endpoints` — prints the live field schema; paste warnings into the dev session if any appear |
| 5 | First fill | `python -m meridian_ingest.run_all` — runs every ingestor once, continues past individual failures |
| 6 | Keep it fresh | `python -m meridian_ingest.scheduler` (or `docker compose --profile ingest up -d`) — PortWatch daily, GDELT every 15 min, hazards every 30 min, each also fired immediately on startup |
| 7 | Optional: UN Comtrade (annual trade matrix) | Free key from comtradeapi.un.org → `COMTRADE_API_KEY` in `.env`; ingested by `run_all`/scheduler automatically once set |
| 8 | Restart the API afterwards | Header chip flips to **PORTWATCH BASELINES**; Monitoring view gains historical series + CSV downloads; live signals populate |

One-terminal version (Codespace):

```bash
cp .env.example .env && sed -i 's/@db:5432/@localhost:5432/' .env
docker compose up -d db
pip install -e ./ingestion
python -m meridian_ingest.verify_endpoints && python -m meridian_ingest.run_all
python -m meridian_ingest.scheduler   # leave running (or: docker compose --profile ingest up -d)
```

The GitHub Pages demo can never show live data — it is a static site with the engine
running in the browser, permanently labeled STATIC DEMO. Live data appears wherever
the full stack (DB + API + web) runs: Codespaces now, OCI in P4.

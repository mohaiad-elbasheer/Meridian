# Meridian — Supply Chain Resilience Cockpit

Meridian is a geo-economic **monitoring and stress-testing cockpit** for international
supply chain resilience, built for analysts, researchers, and decision makers.

It watches the arteries of world trade — the maritime chokepoints and top ports
monitored daily by IMF PortWatch — and lets you ask *what-if* questions with answers
in real units: **"If the Suez Canal
loses 80% of its capacity for two weeks, how many tons reroute, how many are delayed,
how many days does transit grow, and whose imports are exposed?"**

Meridian is deliberately **not** marketed as a "digital twin", and it does not claim
real-time high-resolution visibility. The honest framing — and the engineering
contract — is **near-real-time signals, daily-resolution flows**. Where data is
modeled, estimated, synthetic, or provisional, the platform says so, in the UI, on
every result.

## Why

Maritime chokepoints concentrate a remarkable share of global trade into a handful of
narrow passages. Disruptions — conflict, drought in the Panama Canal watershed, Red Sea
attacks, groundings — propagate into rerouting, freight-rate spikes, insurance
premiums, and country-level import exposure. The signals to see this coming exist and
are largely **free and public**; what's missing is a tool that fuses them into a
coherent, quantitative, *auditable* picture. Commercial platforms are expensive black
boxes; academic models are rarely runnable day-to-day. Meridian aims at the gap.

## The core idea: a two-layer analysis engine

Purely qualitative models aren't credible to serious analysts; purely quantitative
models lose the intuitive scenario composition an expert wants. Meridian couples both:

1. **Quantitative trade network (Layer 1).** A directed graph of chokepoints, ports,
   and countries built from IMF PortWatch baselines and (later) UN Comtrade structure.
   Disruptions propagate as capacity reductions, rerouting with distance/time
   penalties, and country import-exposure shocks. Outputs are real units: transit
   calls, metric tons, added transit days, % of imports at risk.

2. **Fuzzy Cognitive Map (Layer 2).** Sitting on top, an FCM captures the soft factors
   the network cannot: geopolitical escalation, war-risk insurance premiums, sanction
   risk, freight-rate sentiment. Concept activations translate into explicit,
   inspectable **multipliers** on network parameters.

Every FCM edge weight carries a **provenance record** (citation, confidence,
provisional flag). Weights without a literature citation stay marked *provisional* and
every scenario result reports how many provisional weights it relied on. Runs are
deterministic and reproducible — the engine doubles as a publishable research artifact.

## Goals (v0) and ambitions

**v0 — macro lens.** Target: all 28 PortWatch chokepoints + top ~50 ports +
country-level trade dependencies. Daily-resolution ingestion, scenario stress tests
through the two-layer engine, a map-first cockpit. No sector detail yet.
*Current curated simulation topology covers 13 chokepoints + 16 ports* (ingestion
pulls every chokepoint/port PortWatch publishes; the curated alt-route/import-share
topology is being extended toward the full target).

**Where it's headed.**
- **Sector lenses** (textiles first): which industries feel a chokepoint closure, and when.
- **Data-informed FCM weights**: learning weight posteriors from event→flow
  correlations while keeping the literature-derived priors and full provenance.
- **Alerting**: push notifications when live signals cross scenario-informed thresholds.
- **Multi-user deployments** with saved scenario libraries.

## Current status — capability matrix

What works **today**, and on what data. "Synthetic seed" means the bundled, clearly
flagged development dataset; results on it are *illustrative, not decision-grade*.
Every graph carries a provenance label (`synthetic` / `mixed` / `observed`) shown in
the UI and on exported reports.

| Capability | Works on synthetic seed | Works on live data | Notes |
|---|---|---|---|
| Scenario simulation (two-layer engine) | ✔ tested | ✔ once PortWatch rows are ingested | Deterministic; warnings list provisional inputs |
| Monitoring view (baselines, cargo mix, rankings) | ✔ | ✔ (DB-backed trailing averages) | Static demo shows labeled *illustrative* series |
| Historical time series + CSV download | demo: illustrative only | ✔ from `chokepoint_daily` | |
| Live hazard/conflict signals → suggested inputs | — | ✔ (GDELT, USGS, GDACS) | Advisory only |
| Trade dependencies (UN Comtrade) | — | ✔ (requires free API key) | Annual structure |
| Scenario save/load | ✔ (demo: browser storage) | ✔ (Postgres) | No auth yet — single-analyst use |
| Advisor narratives + HTML reports | ✔ | ✔ | Rule-based; provenance line included |
| FRED / EIA cost proxies | — | — | Planned, not implemented |
| Sector lenses, learned FCM weights, alerting | — | — | Future phases (feature-frozen until stabilization completes) |

Phases P0–P3 are code-complete and unit-tested; the first *live* ingestion run
against PortWatch endpoints is still pending verification, and P4 (OCI deploy) has
Compose + CI in place but no public instance yet.

---

## Technical details

### Architecture

```
                 ┌────────────────────────────────────────────────┐
   free public   │  ingestion/  (Python: httpx, tenacity,         │
   data sources ─▶  APScheduler) PortWatch · GDELT · USGS · GDACS │
                 └──────────────────┬─────────────────────────────┘
                                    ▼ raw JSONB + parsed rows, idempotent upserts
                 ┌────────────────────────────────────────────────┐
                 │  Postgres 16 + TimescaleDB (hypertables)       │
                 └──────────────────┬─────────────────────────────┘
                                    ▼ trailing-average baselines
   ┌──────────────────┐   ┌────────────────────────────────────┐
   │  engine/  (pure  │◀──│  api/  (FastAPI)                   │
   │  numpy/networkx/ │   │  /network/baseline /scenario/…     │
   │  Pydantic v2)    │   │  /sources/status /fcm/…            │
   └──────────────────┘   └──────────────┬─────────────────────┘
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │  web/  React + Vite + TS, MapLibre GL +        │
                 │  deck.gl cockpit, scenario builder             │
                 └────────────────────────────────────────────────┘
```

- **`engine/`** — the research-grade core: FCM inference (modified-Kosko with clamping
  and convergence detection), the trade-network propagation model, and the scenario
  orchestrator. Pure and side-effect-free: zero DB or network dependencies, fully
  unit-tested, deterministic.
- **`ingestion/`** — standalone CLI workers (`python -m meridian_ingest.<source>`) plus
  an APScheduler entrypoint. Parsers are drift-tolerant (candidate field names) and
  every row keeps the full raw payload for reprocessing without re-fetching.
- **`api/`** — thin FastAPI layer. Baselines are trailing 28-day averages from
  ingested PortWatch rows overlaid on curated topology; with no data yet, a bundled,
  clearly-flagged synthetic seed keeps the full loop runnable.
- **`web/`** — dark, map-first cockpit: MapLibre GL + deck.gl over bundled world
  geometry (no external tile servers), IBM Plex, a single accent color, density over
  decoration. Strict TypeScript.

### Data sources (all free)

| Source | Content | Cadence |
|---|---|---|
| IMF PortWatch (ArcGIS) | Daily chokepoint transit calls + trade estimates (28 chokepoints); daily port activity (2,065 ports) | Daily data, weekly refresh (Tue 9 AM ET) |
| GDELT 2.0 | Geopolitical events, aggregated near chokepoints | 15 min |
| USGS / GDACS | Earthquakes / multi-hazard alerts | Real-time |
| UN Comtrade | Annual trade matrix (network structure) | Annual |
| FRED / EIA | Freight & energy cost proxies — **planned, not yet ingested** | Daily/weekly |

Data-quality caveats are surfaced, not hidden: AIS jamming/spoofing near conflict
zones, PortWatch tonnages being model estimates, GDELT noise. See
`docs/DATA_SOURCES.md`.

### Quickstarts

> Every command below assumes your Python environment has the project packages
> installed. If you work inside a virtualenv (recommended), install into **that**
> venv after activating it — a package installed into system Python is not visible
> from a venv, which surfaces as `ModuleNotFoundError: No module named 'meridian_…'`.

**One-time setup (local machine or GitHub Codespace):**
```bash
cd /workspaces/Meridian                      # or your clone path
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ./engine[dev] -e ./api[dev] -e ./ingestion[dev]
cd web && npm install && cd ..
cp .env.example .env
# Codespaces/local docker only — the DB runs on localhost, not on the 'db' hostname:
sed -i 's/@db:5432/@localhost:5432/' .env
```

**Run the platform — one long-running terminal each** (a terminal running a server
cannot accept other commands; open new terminals with the `+` button):

Terminal 1 — database (leave running, or use `-d` as shown and reuse the terminal):
```bash
docker compose up -d db
```
Terminal 1 — API (leave running; Ctrl+C, ↑, Enter to restart):
```bash
source .venv/bin/activate
uvicorn meridian_api.main:app --port 8000
```
Terminal 2 — web (leave running; open http://localhost:5173 or the forwarded port):
```bash
cd web && npm run dev
```

**Go live — fill the database (run in a free third terminal):**
```bash
source .venv/bin/activate
python -m meridian_ingest.verify_endpoints   # required once: checks the pinned PortWatch URLs
python -m meridian_ingest.run_all            # fills every source once (Comtrade only with COMTRADE_API_KEY)
curl -s localhost:8000/sources/status        # expect "reachable": true + row counts
python -m meridian_ingest.scheduler          # optional: keep data refreshing (leave running)
```
As soon as PortWatch rows exist, the API switches from the synthetic seed to
DB-backed baselines automatically — restart the API once and the cockpit header
flips to PORTWATCH BASELINES. Full checklist: `docs/LIVE_DATA.md`.

**Tests:**
```bash
pytest engine/tests api/tests ingestion/tests -q
# live-DB integration tests: TEST_DATABASE_URL=postgresql://… pytest api/tests
```

### Conventions

Python ≥ 3.11, Pydantic v2, `ruff` + `pytest`, type hints throughout the engine.
TypeScript strict mode. Conventional commits, one branch per phase, CI on every PR
(engine, ingestion, api, web). Architecture decisions are recorded ADR-style in
`docs/ARCHITECTURE.md`; the project contract lives in `CLAUDE.md`.

# MERIDIAN — Supply Chain Resilience Cockpit

> Working name "Meridian" (rename freely). This file is the master context for Claude Code.
> Read it fully before any task. It encodes decisions already made with the project owner —
> do not re-litigate them without asking.

## 1. What this is (and is not)

Meridian is a **geo-economic monitoring and stress-testing cockpit** for international
supply chain resilience, aimed at analysts, researchers, and decision makers.

Positioning rules (owner decision — strict):
- **Do NOT market it as a "digital twin"** or claim "real-time high-resolution" visibility.
  Honest framing: **"near-real-time signals, daily-resolution flows."** The owner has a
  strong, consistent preference for factual accuracy over embellishment. This applies to
  README copy, UI text, and any generated marketing/docs.
- It is primarily a **product seed** with research as a byproduct. Engine design choices
  should therefore also be publishable (provenance-tracked FCM weights, reproducible runs).
- Scope of v0 is **macro-first**: 28 maritime chokepoints + top ~50 ports + country-level
  trade dependencies. No sector-specific lens in v0 (sector filters are a later phase).

## 2. Core design: two-layer analysis engine

Serious analysts will reject a purely qualitative model, and a purely quantitative model
loses the intuitive scenario-composition the owner wants. Therefore:

**Layer 1 — Quantitative trade network (`engine/meridian_engine/network.py`)**
Directed graph (NetworkX) of chokepoints, ports, and countries built from IMF PortWatch
baselines + UN Comtrade structure. Disruptions propagate as capacity reductions,
rerouting distance/time penalties, and country import-exposure shocks. Outputs are in
real units: transit calls, estimated trade volume (metric tons), added transit days.

**Layer 2 — Fuzzy Cognitive Map (`engine/meridian_engine/fcm.py`)**
Sits ON TOP of the network layer. Captures soft factors the network cannot: geopolitical
escalation, insurance/war-risk premiums, sanction risk, freight-rate sentiment. FCM concept
activations map to **network parameter multipliers** via explicit `couplings` (see
`engine/meridian_engine/maps/macro_v0.json`). The FCM inference core is already implemented
and tested — extend, do not rewrite, unless tests are preserved.

**FCM weights (owner decision):** v0 weights are **literature-defined** (as in the owner's
prior IMAACA 2026 FCM work). Every edge MUST carry a `provenance` object (citation,
confidence, `provisional` flag). Weights without a filled citation stay `provisional: true`.
Never invent citations — leave the field empty and flag it. A later phase may learn weights
from data; do not build that now.

## 3. Data sources (all free; verified July 2026)

| Source | What | Cadence | Access |
|---|---|---|---|
| IMF PortWatch | Daily port activity + trade estimates, 2,065 ports; daily chokepoint transit calls + volumes, 28 chokepoints | Daily data, refreshed weekly (Tue 9 AM ET) | ArcGIS Feature Services. Resolve the "Access API" GeoService URLs from https://portwatch.imf.org/pages/data-and-methodology and pin them in `.env` (see `ingestion/`) |
| GDELT 2.0 | Global geopolitical events | 15 min | `http://data.gdeltproject.org/gdeltv2/lastupdate.txt` → CSV zips |
| USGS | Earthquakes | Real-time | GeoJSON feeds, `earthquake.usgs.gov` |
| GDACS | Multi-hazard disaster alerts | Real-time | RSS/XML, `gdacs.org` |
| UN Comtrade | Trade network structure (annual) | Annual | `comtradeapi.un.org` — requires free API key |
| FRED / EIA | Freight & energy cost proxies | Daily/weekly | Free API keys |

Rules:
- PortWatch is the **anchor dataset**. Ingest chokepoints first, then ports.
- Always store raw payloads (a `raw` JSONB column) alongside parsed rows — reprocessing
  must be possible without re-fetching.
- Respect AIS caveats (GPS jamming/spoofing near conflict zones, e.g. Hormuz). Surface a
  data-quality flag in the UI rather than hiding it.
- Never hardcode API keys; use `.env` + `pydantic-settings`.

## 4. Architecture & stack

- **DB:** Postgres 16 + TimescaleDB (hypertables for time series)
- **Ingestion:** Python workers in `ingestion/` (httpx, tenacity, APScheduler). The owner
  also self-hosts n8n (Cloud Run) and may mirror schedules there later; keep workers
  runnable standalone via CLI (`python -m meridian_ingest.portwatch`).
- **Engine:** `engine/` — numpy, networkx, Pydantic v2 models. Pure, side-effect-free,
  fully unit-tested. This is the research-grade core.
- **API:** FastAPI in `api/`, thin layer over engine + DB. OpenAPI kept clean.
- **Web:** React + Vite + TypeScript in `web/`. Map-centric: **MapLibre GL + deck.gl**
  (ArcLayer for flows, ScatterplotLayer for ports/chokepoints). Scenario builder = an
  editable causal-map canvas (React Flow) over the FCM spec.
- **Deploy:** Docker Compose on OCI Always-Free Ampere A1 (aarch64 — ensure ARM-compatible
  images). CI via GitHub Actions. Infra changes are delivered as `oci` CLI commands
  (owner preference: CLI, never console click-throughs). See `infra/oci/DEPLOY.md`.

## 5. Frontend design mandate

The owner explicitly wants the UI to NOT look AI-generated. Concretely:
- One deliberate design system: dark map-first cockpit, a single restrained accent color,
  real typographic hierarchy (e.g., Inter/IBM Plex — no default Tailwind look).
- No purple gradients, no glassmorphism, no emoji in UI, no generic hero sections.
- Density over decoration: analysts want numbers, sparklines, and the map.
- Every scenario result shows units and provenance (which edges/weights drove it).

## 6. Phased plan and definition of done

- **P0 Ingestion + DB** — PortWatch chokepoints & ports flowing into TimescaleDB on a
  schedule; GDELT + USGS + GDACS minimal ingestors; `docker compose up db ingestion` works.
  DoD: 7 days of chokepoint data queryable; idempotent re-runs; tests for parsers.
- **P1 Engine** — network layer over ingested baselines; FCM↔network couplings live;
  scenario API in pure Python. DoD: "Suez −80% capacity for 14 days" returns rerouted
  volumes + added days + FCM-modulated cost indices; deterministic given a seed; tests.
- **P2 API** — endpoints: sources status, time series, scenario CRUD, simulate. DoD:
  OpenAPI docs, integration tests against a seeded DB.
- **P3 Web** — map cockpit + scenario canvas + results panel. DoD: full loop in browser.
- **P4 Deploy** — OCI instance, Compose, GitHub Actions build/push/deploy. DoD: public
  URL, TLS (Caddy), data refreshing on schedule.

Work phase by phase. One branch per phase (`p0-ingestion`, ...), conventional commits,
PR into `main` with a short summary. Do not start a phase before the previous DoD passes.

## 7. Conventions

- Python ≥ 3.11, Pydantic v2, `ruff` + `pytest`; type hints everywhere in `engine/`.
- TypeScript strict mode in `web/`.
- Keep `engine/` importable with zero DB/network dependencies.
- Update `docs/` when architecture decisions change (short ADR style in `docs/ARCHITECTURE.md`).
- Ask the owner before: adding paid services, changing the two-layer engine design,
  renaming public API routes after P2, or any claim-of-capability wording in user-facing text.

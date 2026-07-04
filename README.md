# Meridian — Supply Chain Resilience Cockpit

Monitoring and stress-testing platform for international supply chain resilience:
near-real-time signals, daily-resolution maritime flows (IMF PortWatch anchor dataset),
and a two-layer scenario engine (quantitative trade network + fuzzy cognitive map).

Not a digital twin — and honest about it. See `CLAUDE.md` for the full project contract,
`docs/` for architecture and data sources.

## Quickstart (engine only)
```bash
pip install -e ./engine[dev]
pytest engine/tests -q
uvicorn meridian_api.main:app --reload   # after: pip install -e ./api
```

## Prototype (full loop, no external data needed)
Runs on a clearly-labeled synthetic baseline seed until PortWatch data is ingested.
```bash
pip install -e ./engine[dev] -e ./api[dev]
uvicorn meridian_api.main:app --port 8000 &
cd web && npm install && npm run dev        # open http://localhost:5173
```
Pick a chokepoint, set a capacity reduction and duration, run — the panel shows
rerouted/delayed volume (metric tons), added transit days, country import exposure,
and the FCM-modulated indices with provenance warnings.

## Ingestion (P0)
```bash
cp .env.example .env                              # then verify the pinned PortWatch URLs:
pip install -e ./ingestion[dev]
python -m meridian_ingest.verify_endpoints        # required before first ingest
docker compose up -d db
python -m meridian_ingest.portwatch chokepoints   # anchor dataset first
python -m meridian_ingest.portwatch ports
python -m meridian_ingest.gdelt
python -m meridian_ingest.hazards
python -m meridian_ingest.scheduler               # or: docker compose --profile ingest up ingestion
```


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
"# Meridian" 

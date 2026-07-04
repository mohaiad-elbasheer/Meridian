# PortWatch data fields and how Meridian can use them

> Source: IMF PortWatch data dictionary / methodology (portwatch.imf.org). This list
> was written from the documented schema because the development sandbox cannot reach
> *.arcgis.com; treat it as the expected schema and confirm against the live services
> with `python -m meridian_ingest.verify_endpoints`, which prints every field the
> layer actually serves. Parsers already tolerate drift (candidate names + raw JSONB).

## 1. Daily chokepoint transit calls & trade volume estimates
(pinned as `PORTWATCH_CHOKEPOINTS_URL`; one row = one chokepoint × one day)

| Field | Meaning |
|---|---|
| `objectid` | ArcGIS row id (not stable across refreshes — do not key on it) |
| `portid` | Chokepoint id, `chokepoint1` … `chokepoint28` |
| `portname` | Human name, e.g. "Suez Canal" (Meridian matches baselines on this) |
| `date`, `year`, `month`, `day` | Observation day (date arrives as epoch ms) |
| `n_container` | Transit calls by container ships |
| `n_dry_bulk` | Transit calls by dry-bulk carriers |
| `n_general_cargo` | Transit calls by general-cargo ships |
| `n_roro` | Transit calls by ro-ro vessels |
| `n_tanker` | Transit calls by tankers |
| `n_cargo` | All cargo classes combined |
| `n_total` | All transit calls (cargo + tanker) → our `transit_calls` |
| `capacity` | Estimated trade volume through the chokepoint, metric tons (model estimate from vessel capacity & payload assumptions — not customs data) → our `trade_tons` |

## 2. Daily port activity & trade estimates
(pinned as `PORTWATCH_PORTS_URL`; one row = one port × one day; 2,065 ports)

| Field | Meaning |
|---|---|
| `objectid` | ArcGIS row id |
| `portid`, `portname` | Port id and name |
| `country`, `ISO3` | Country name and ISO-3 code |
| `date`, `year`, `month`, `day` | Observation day |
| `portcalls_container` / `_dry_bulk` / `_general_cargo` / `_roro` / `_tanker` | Port calls by vessel class |
| `portcalls_cargo`, `portcalls` | Cargo-class total; grand total → our `portcalls` |
| `import_container` / `_dry_bulk` / `_general_cargo` / `_roro` / `_tanker` | Import volume estimates by class, metric tons |
| `import_cargo`, `import` | Cargo-class subtotal; total imports → our `import_tons` |
| `export_*` (same shape) | Export volume estimates → our `export_tons` |

## 3. Static master databases (not yet ingested — high-value follow-up)

- **Chokepoints database**: `portid`, `portname`, `lat`, `lon` (+ descriptive
  attributes). Gives authoritative chokepoint geometry — replaces both the curated
  coordinates in the engine seed and `chokepoints_seed.json` used by the GDELT
  ingestor.
- **Ports database**: `portid`, `portname`, `country`, `ISO3`, `lat`, `lon`, plus
  country-share fields (share of a country's maritime imports/exports moving through
  the port) and annual vessel-count statistics. The share fields are the data-driven
  replacement for our *curated* country import-dependency edges — the single biggest
  honesty upgrade available.

Field names in section 3 are less certain than 1–2; resolve the two master-database
layer URLs from the PortWatch data page alongside the daily ones and check with the
verify CLI pattern before parsing.

## Already captured today

The P0 parsers keep every attribute in the `raw` JSONB column, and the
`vessel_breakdown` JSONB on `chokepoint_daily` explicitly collects all
`n_*` / `portcalls_*` / `import_*` / `export_*` fields. **Nothing below requires
re-fetching data** — it's all reprocessable from stored rows.

## Augmentation plan (viz + analytics, additive — nothing existing is removed)

1. **Vessel-class breakdown in the cockpit.** Per-chokepoint class split
   (container / dry bulk / general cargo / ro-ro / tanker) as a segmented bar in the
   results panel; scenario targeting by class (e.g. "tankers avoid Hormuz, cargo
   continues") via per-class capacity multipliers in the engine — an *extension* of
   `apply_scenario`, not a rewrite.
2. **Time series + anomaly signal.** `/timeseries/{chokepoint}` endpoint over the
   hypertable; sparklines in the panel; z-score of latest week vs trailing baseline
   as a "signal" dot on the map. This is the "monitoring" half of the cockpit coming
   alive.
3. **Data-driven import shares.** Ingest the ports master database; aggregate
   port-level country shares through chokepoint associations to replace curated
   `import_dependencies`. Removes the "topology is curated v0" warning for shares.
4. **Directional port flows.** Import vs export tons per port → small trade-balance
   glyphs; ArcLayer flows between top port pairs once Comtrade structure lands.
5. **Seasonal baselines.** PortWatch publishes year/month/day — switch trailing-28d
   averages to month-matched climatology once ≥ 1 year of history is stored, so a
   January scenario compares against January norms.
6. **Chokepoint↔hazard join.** geo_events (GDELT counts, USGS, GDACS) within N km of
   chokepoint geometry → auto-suggest FCM clamp values from live signals (analyst
   confirms; never auto-applied).

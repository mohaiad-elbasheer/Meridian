# Data Sources (all free)

| Source | Content | Cadence | Access | Key |
|---|---|---|---|---|
| IMF PortWatch | 2,065 ports daily activity + trade estimates; 28 chokepoints daily transit calls + volumes | daily data, weekly refresh (Tue 9AM ET) | ArcGIS FeatureServer — pinned query URLs in `.env.example` (org `weJ1QsnbMYJlCHdG` on services9.arcgis.com; from portwatch.imf.org/pages/data-and-methodology). Verify with `python -m meridian_ingest.verify_endpoints` before first ingest | none |
| GDELT 2.0 | geopolitical events | 15 min | data.gdeltproject.org/gdeltv2/lastupdate.txt | none |
| USGS | earthquakes | real-time | GeoJSON feeds | none |
| GDACS | multi-hazard alerts | real-time | RSS | none |
| UN Comtrade | annual trade matrix (network structure) | annual | comtradeapi.un.org | free key |
| FRED / EIA | freight & energy proxies | daily/weekly | REST | free key |

Caveats to surface in UI: AIS jamming/spoofing near conflict zones (e.g., Hormuz);
PortWatch trade tons are model estimates, not customs data; GDELT is noisy — use as
signal intensity, never as ground truth for individual events.

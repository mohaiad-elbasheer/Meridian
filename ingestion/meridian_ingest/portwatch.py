"""IMF PortWatch ingestor (anchor dataset). Chokepoints first, then ports.

PortWatch data is exposed as ArcGIS Feature Services (GeoServices REST). We query with
f=json, resultOffset pagination, and a WHERE clause on date for incremental pulls.
Data cadence: daily observations, refreshed weekly (Tuesdays 9 AM ET).

Field names in the services can drift between PortWatch releases, so parsers resolve
each column through a list of candidate names and always keep the full attribute dict
in the `raw` JSONB column — reprocessing never requires a re-fetch. Run
`python -m meridian_ingest.verify_endpoints` to print the live schema and spot drift.

CLI:  python -m meridian_ingest.portwatch [chokepoints|ports|all] [--full]
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from typing import Any, Iterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import db
from .settings import Settings

PAGE_SIZE = 2000


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def fetch_page(client: httpx.Client, url: str, offset: int, where: str = "1=1") -> dict:
    params = {
        "f": "json",
        "where": where,
        "outFields": "*",
        "resultOffset": offset,
        "resultRecordCount": PAGE_SIZE,
        "orderByFields": "date ASC",
    }
    r = client.get(url, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    if "error" in payload:  # ArcGIS reports errors with HTTP 200
        raise RuntimeError(f"ArcGIS error from {url}: {payload['error']}")
    return payload


def iter_features(client: httpx.Client, url: str, where: str = "1=1") -> Iterator[dict]:
    offset = 0
    while True:
        payload = fetch_page(client, url, offset, where)
        features = payload.get("features", [])
        if not features:
            break
        yield from features
        offset += len(features)
        if not payload.get("exceededTransferLimit"):
            break


def _first(attrs: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in attrs and attrs[name] is not None:
            return attrs[name]
    return None


def parse_arcgis_date(value: Any) -> date | None:
    """ArcGIS serves dates as epoch milliseconds; tolerate ISO strings too."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
    return date.fromisoformat(str(value)[:10])


def _breakdown(attrs: dict[str, Any]) -> dict[str, Any]:
    prefixes = ("n_", "portcalls_", "capacity_", "import_", "export_")
    return {k: v for k, v in attrs.items() if k.startswith(prefixes) and v is not None}


def parse_chokepoint(feature: dict) -> dict[str, Any] | None:
    attrs = feature.get("attributes") or {}
    cid = _first(attrs, "portid", "chokepoint_id", "id")
    day = parse_arcgis_date(_first(attrs, "date"))
    if cid is None or day is None:
        return None
    return {
        "chokepoint_id": str(cid),
        "date": day,
        "transit_calls": _first(attrs, "n_total", "transit_calls"),
        # PortWatch "capacity" = estimated trade volume in metric tons (model estimate).
        "trade_tons": _first(attrs, "capacity", "trade_tons"),
        "vessel_breakdown": _breakdown(attrs) or None,
        "raw": attrs,
    }


def parse_port(feature: dict) -> dict[str, Any] | None:
    attrs = feature.get("attributes") or {}
    pid = _first(attrs, "portid", "port_id", "id")
    day = parse_arcgis_date(_first(attrs, "date"))
    if pid is None or day is None:
        return None
    return {
        "port_id": str(pid),
        "date": day,
        "portcalls": _first(attrs, "portcalls", "n_total"),
        "import_tons": _first(attrs, "import", "import_tons"),
        "export_tons": _first(attrs, "export", "export_tons"),
        "raw": attrs,
    }


def incremental_where(since: date | None) -> str:
    if since is None:
        return "1=1"
    return f"date > TIMESTAMP '{since:%Y-%m-%d} 23:59:59'"


def ingest(target: str, full: bool = False) -> None:
    settings = Settings()
    jobs = {
        "chokepoints": (settings.portwatch_chokepoints_url, "chokepoint_daily",
                        parse_chokepoint, db.UPSERT_CHOKEPOINT),
        "ports": (settings.portwatch_ports_url, "port_daily", parse_port, db.UPSERT_PORT),
    }
    with db.connect(settings.database_url) as conn, httpx.Client() as client:
        for name, (url, table, parse, sql) in jobs.items():
            if target not in (name, "all"):
                continue
            if not url:
                raise SystemExit(f"Set PORTWATCH_{name.upper()}_URL in .env (see .env.example)")
            since = None if full else db.max_date(conn, table)
            rows = (r for f in iter_features(client, url, incremental_where(since))
                    if (r := parse(f)) is not None)
            n = db.upsert_many(conn, sql, rows)
            print(f"portwatch/{name}: upserted {n} rows (since={since or 'beginning'})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", default="all", choices=["chokepoints", "ports", "all"])
    ap.add_argument("--full", action="store_true", help="ignore DB high-water mark, refetch all")
    args = ap.parse_args()
    ingest(args.target, full=args.full)


if __name__ == "__main__":
    main()

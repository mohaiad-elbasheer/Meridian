"""Verify the pinned PortWatch ArcGIS endpoints: layer reachable, expected fields present,
latest observation date. Run this after editing .env and before the first ingest —
the URLs were pinned from the PortWatch ArcGIS org but the pinning environment could
not reach *.arcgis.com, so first-run verification is mandatory.

Usage:  python -m meridian_ingest.verify_endpoints
Exit code 0 = both endpoints OK.
"""

from __future__ import annotations

import sys

import httpx

from .portwatch import parse_arcgis_date
from .settings import Settings

EXPECTED = {
    "chokepoints": {"portid", "date"},   # minimum for parse_chokepoint
    "ports": {"portid", "date"},         # minimum for parse_port
}


def check(client: httpx.Client, name: str, query_url: str) -> bool:
    if not query_url:
        print(f"[FAIL] {name}: URL not set in .env")
        return False
    layer_url = query_url.rsplit("/query", 1)[0]
    try:
        meta = client.get(layer_url, params={"f": "json"}, timeout=30).json()
        latest = client.get(query_url, params={
            "f": "json", "where": "1=1", "outFields": "*",
            "resultRecordCount": 1, "orderByFields": "date DESC",
        }, timeout=30).json()
    except Exception as exc:  # noqa: BLE001 — report, don't crash the other check
        print(f"[FAIL] {name}: {exc}")
        return False
    if "error" in meta or "error" in latest:
        print(f"[FAIL] {name}: ArcGIS error: {meta.get('error') or latest.get('error')}")
        return False
    fields = {f["name"] for f in meta.get("fields", [])}
    missing = EXPECTED[name] - fields
    feats = latest.get("features", [])
    latest_date = parse_arcgis_date(feats[0]["attributes"].get("date")) if feats else None
    print(f"[ OK ] {name}: layer '{meta.get('name')}', {len(fields)} fields, "
          f"latest date {latest_date}")
    print(f"       fields: {', '.join(sorted(fields))}")
    if missing:
        print(f"[WARN] {name}: expected fields missing: {missing} — "
              f"update the candidate names in portwatch.py parsers")
    return True


def main() -> None:
    settings = Settings()
    with httpx.Client() as client:
        ok = all([
            check(client, "chokepoints", settings.portwatch_chokepoints_url),
            check(client, "ports", settings.portwatch_ports_url),
        ])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

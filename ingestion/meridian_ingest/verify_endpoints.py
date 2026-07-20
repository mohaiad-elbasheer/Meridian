"""Verify the pinned PortWatch ArcGIS endpoints: layer reachable, expected fields present,
latest observation date. Run this after editing .env and before the first ingest —
the URLs were pinned from the PortWatch ArcGIS org but the pinning environment could
not reach *.arcgis.com, so first-run verification is mandatory.

Usage:  python -m meridian_ingest.verify_endpoints             # check pinned URLs
        python -m meridian_ingest.verify_endpoints --discover  # list the PortWatch
            org's public feature services (title + query URL) to find/repin a layer
Exit code 0 = both endpoints OK.
"""

from __future__ import annotations

import argparse
import sys

import httpx

from .portwatch import parse_arcgis_date
from .settings import Settings

PORTWATCH_ORG_ID = "weJ1QsnbMYJlCHdG"  # from portwatch.imf.org "Access API" links
ARCGIS_SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"

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


def discover(client: httpx.Client) -> None:
    """List the PortWatch org's public Feature Services so a wrong/renamed layer can
    be re-pinned in .env without guessing item ids."""
    start, found = 1, 0
    while start > 0:
        page = client.get(ARCGIS_SEARCH_URL, params={
            "q": f'orgid:{PORTWATCH_ORG_ID} type:"Feature Service"',
            "num": 50, "start": start, "f": "json",
        }, timeout=30).json()
        for item in page.get("results", []):
            found += 1
            url = item.get("url") or ""
            print(f"- {item.get('title')}\n    {url}/0/query")
        start = page.get("nextStart", -1)
    if not found:
        print("no public feature services returned — check connectivity or org id")
    else:
        print(f"\n{found} service(s). Pin the matching one in .env as "
              "PORTWATCH_PORTS_URL / PORTWATCH_CHOKEPOINTS_URL (keep the /0/query "
              "suffix), then re-run without --discover.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--discover", action="store_true",
                    help="list the PortWatch org's public feature services and exit")
    args = ap.parse_args()
    with httpx.Client() as client:
        if args.discover:
            discover(client)
            return
        settings = Settings()
        ok = all([
            check(client, "chokepoints", settings.portwatch_chokepoints_url),
            check(client, "ports", settings.portwatch_ports_url),
        ])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

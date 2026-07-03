"""IMF PortWatch ingestor (anchor dataset). Chokepoints first, then ports.

PortWatch data is exposed as ArcGIS Feature Services (GeoServices REST). Query with
f=json, resultOffset pagination, and a WHERE clause on date for incremental pulls.
Data cadence: daily observations, refreshed weekly (Tuesdays 9 AM ET).

P0 TODO (Claude Code):
- Resolve and pin FeatureServer URLs in .env (see settings.py).
- Incremental fetch: MAX(date) in DB -> where=date > '...'.
- Upsert into TimescaleDB hypertables (see infra: db/init.sql), store raw JSON.
- Idempotent: re-running must not duplicate rows (ON CONFLICT DO NOTHING on natural key).
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

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
    return r.json()


def run() -> None:
    settings = Settings()
    if not settings.portwatch_chokepoints_url:
        raise SystemExit("Set PORTWATCH_CHOKEPOINTS_URL in .env (see settings.py docstring)")
    with httpx.Client() as client:
        offset = 0
        while True:
            payload = fetch_page(client, settings.portwatch_chokepoints_url, offset)
            features = payload.get("features", [])
            if not features:
                break
            # TODO(P0): parse attributes, upsert to DB with raw payload
            offset += len(features)
            if not payload.get("exceededTransferLimit"):
                break


if __name__ == "__main__":
    run()

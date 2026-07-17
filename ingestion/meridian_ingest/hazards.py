"""Natural hazard ingestors: USGS earthquakes (GeoJSON feed) + GDACS alerts (RSS).

P0 scope: store individual events with geometry in geo_events; spatial joins to
ports/chokepoints happen later in the engine layer.

CLI:  python -m meridian_ingest.hazards [usgs|gdacs|all]
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx
from defusedxml import ElementTree as SafeET  # GDACS feed is remote input (QC P0-07)
from tenacity import retry, stop_after_attempt, wait_exponential

from . import db
from .settings import Settings

GDACS_NS = {
    "gdacs": "http://www.gdacs.org",
    "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
}
GDACS_ALERT_SEVERITY = {"green": 1.0, "orange": 2.0, "red": 3.0}


def parse_usgs(feed: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for feat in feed.get("features", []):
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
        if feat.get("id") is None or props.get("time") is None:
            continue
        rows.append({
            "id": f"usgs:{feat['id']}",
            "source": "usgs",
            "event_time": datetime.fromtimestamp(props["time"] / 1000, tz=timezone.utc),
            "category": "earthquake",
            "severity": props.get("mag"),
            "lon": coords[0],
            "lat": coords[1],
            "raw": feat,
        })
    return rows


def _text(item: ET.Element, path: str) -> str | None:
    el = item.find(path, GDACS_NS)
    return el.text.strip() if el is not None and el.text else None


def parse_gdacs(xml_text: str) -> list[dict[str, Any]]:
    rows = []
    for item in SafeET.fromstring(xml_text).iter("item"):
        guid = _text(item, "guid")
        pub = _text(item, "pubDate")
        if not guid or not pub:
            continue
        try:
            event_time = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(
                tzinfo=timezone.utc)
        except ValueError:
            event_time = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z")
        alert = (_text(item, "gdacs:alertlevel") or "").lower()
        lat, lon = _text(item, "geo:Point/geo:lat"), _text(item, "geo:Point/geo:long")
        raw = {c.tag: c.text for c in item}
        rows.append({
            "id": f"gdacs:{guid}",
            "source": "gdacs",
            "category": _text(item, "gdacs:eventtype"),
            "event_time": event_time,
            "severity": GDACS_ALERT_SEVERITY.get(alert),
            "lon": float(lon) if lon else None,
            "lat": float(lat) if lat else None,
            "raw": raw,
        })
    return rows


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str) -> httpx.Response:
    r = client.get(url, timeout=60)
    r.raise_for_status()
    return r


def run(target: str = "all") -> None:
    settings = Settings()
    with db.connect(settings.database_url) as conn, httpx.Client(follow_redirects=True) as client:
        if target in ("usgs", "all"):
            rows = parse_usgs(_get(client, settings.usgs_feed_url).json())
            print(f"usgs: upserted {db.upsert_many(conn, db.UPSERT_GEO_EVENT, rows)} events")
        if target in ("gdacs", "all"):
            rows = parse_gdacs(_get(client, settings.gdacs_rss_url).text)
            print(f"gdacs: upserted {db.upsert_many(conn, db.UPSERT_GEO_EVENT, rows)} alerts")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="?", default="all", choices=["usgs", "gdacs", "all"])
    run(ap.parse_args().target)


if __name__ == "__main__":
    main()

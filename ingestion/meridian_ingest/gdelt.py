"""GDELT 2.0 events ingestor (15-minute cadence geopolitical signal).

Polls lastupdate.txt for the newest export CSV zip, filters events to conflict-relevant
CAMEO root codes located near maritime chokepoints, and stores ONE AGGREGATE ROW per
(chokepoint, 15-min window) in geo_events — counts and tone only, never person-level
data. GDELT is noisy: treat severity as signal intensity, not ground truth.

Chokepoint coordinates come from chokepoints_seed.json (provisional) until the
PortWatch chokepoint master list is ingested.

CLI:  python -m meridian_ingest.gdelt
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from datetime import datetime, timezone
from importlib import resources
from typing import Any, Iterator, NamedTuple

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from . import db
from .settings import Settings

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# CAMEO root codes: 14 protest, 17 coerce, 18 assault, 19 fight, 20 mass violence.
CONFLICT_ROOT_CODES = {"14", "17", "18", "19", "20"}
MAX_KM = 300.0  # events farther than this from every chokepoint are dropped

# Column indices in the 61-column GDELT 2.0 event table.
COL_EVENT_ROOT_CODE = 28
COL_GOLDSTEIN = 30
COL_NUM_ARTICLES = 33
COL_ACTIONGEO_LAT = 56
COL_ACTIONGEO_LON = 57
COL_DATEADDED = 59


class Event(NamedTuple):
    root_code: str
    goldstein: float | None
    num_articles: int
    lat: float
    lon: float


def parse_lastupdate(text: str) -> str | None:
    """lastupdate.txt lines: '<size> <md5> <url>'; we want the .export.CSV.zip url."""
    for line in text.splitlines():
        parts = line.split()
        if parts and parts[-1].endswith(".export.CSV.zip"):
            return parts[-1]
    return None


def window_from_url(url: str) -> datetime:
    stamp = url.rsplit("/", 1)[-1].split(".")[0]  # YYYYMMDDHHMMSS
    return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def parse_events(csv_bytes: bytes) -> Iterator[Event]:
    text = csv_bytes.decode("utf-8", errors="replace")
    for row in csv.reader(io.StringIO(text), delimiter="\t"):
        if len(row) < 61 or row[COL_EVENT_ROOT_CODE] not in CONFLICT_ROOT_CODES:
            continue
        try:
            lat, lon = float(row[COL_ACTIONGEO_LAT]), float(row[COL_ACTIONGEO_LON])
        except ValueError:
            continue  # no usable geolocation
        try:
            goldstein: float | None = float(row[COL_GOLDSTEIN])
        except ValueError:
            goldstein = None
        try:
            n_articles = int(row[COL_NUM_ARTICLES])
        except ValueError:
            n_articles = 1
        yield Event(row[COL_EVENT_ROOT_CODE], goldstein, n_articles, lat, lon)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def load_chokepoints() -> list[dict[str, Any]]:
    ref = resources.files("meridian_ingest").joinpath("chokepoints_seed.json")
    return json.loads(ref.read_text())["chokepoints"]


def nearest_chokepoint(lat: float, lon: float, chokepoints: list[dict],
                       max_km: float = MAX_KM) -> str | None:
    best_id, best_km = None, max_km
    for cp in chokepoints:
        d = haversine_km(lat, lon, cp["lat"], cp["lon"])
        if d <= best_km:
            best_id, best_km = cp["id"], d
    return best_id


def aggregate(events: Iterator[Event], window: datetime,
              chokepoints: list[dict]) -> list[dict[str, Any]]:
    """One geo_events row per chokepoint per window; severity = conflict event count."""
    buckets: dict[str, dict[str, Any]] = {}
    for ev in events:
        cid = nearest_chokepoint(ev.lat, ev.lon, chokepoints)
        if cid is None:
            continue
        b = buckets.setdefault(cid, {"count": 0, "articles": 0, "goldstein_sum": 0.0,
                                     "goldstein_n": 0, "by_root_code": {}})
        b["count"] += 1
        b["articles"] += ev.num_articles
        b["by_root_code"][ev.root_code] = b["by_root_code"].get(ev.root_code, 0) + 1
        if ev.goldstein is not None:
            b["goldstein_sum"] += ev.goldstein
            b["goldstein_n"] += 1
    cp_by_id = {c["id"]: c for c in chokepoints}
    rows = []
    for cid, b in sorted(buckets.items()):
        avg_goldstein = b["goldstein_sum"] / b["goldstein_n"] if b["goldstein_n"] else None
        rows.append({
            "id": f"gdelt:{window:%Y%m%d%H%M%S}:{cid}",
            "source": "gdelt",
            "event_time": window,
            "category": "conflict_events_nearby",
            "severity": float(b["count"]),
            "lon": cp_by_id[cid]["lon"],
            "lat": cp_by_id[cid]["lat"],
            "raw": {"chokepoint_id": cid, "window": f"{window:%Y-%m-%dT%H:%M:%SZ}",
                    "count": b["count"], "articles": b["articles"],
                    "avg_goldstein": avg_goldstein, "by_root_code": b["by_root_code"],
                    "chokepoint_source": "seed_provisional"},
        })
    return rows


def _retryable(exc: BaseException) -> bool:
    # Retrying a 4xx is pointless: a 404 means the advertised window isn't on the
    # server (yet, or anymore) and won't appear within our backoff horizon.
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


@retry(retry=retry_if_exception(_retryable),
       stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30),
       reraise=True)
def _get(client: httpx.Client, url: str) -> httpx.Response:
    r = client.get(url, timeout=120)
    r.raise_for_status()
    return r


def run() -> None:
    settings = Settings()
    with httpx.Client(follow_redirects=True) as client:
        export_url = parse_lastupdate(_get(client, settings.gdelt_lastupdate_url).text)
        if not export_url:
            raise SystemExit("gdelt: no export url in lastupdate.txt")
        window = window_from_url(export_url)
        try:
            payload = _get(client, export_url).content
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # lastupdate.txt occasionally advertises a window before the zip is
                # uploaded; the next 15-min run will catch it. Not an error.
                print(f"gdelt: advertised window {window:%Y-%m-%d %H:%M}Z not available "
                      "upstream yet (404) — skipping this run")
                return
            raise
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            csv_bytes = zf.read(zf.namelist()[0])
    rows = aggregate(parse_events(csv_bytes), window, load_chokepoints())
    with db.connect(settings.database_url) as conn:
        n = db.upsert_many(conn, db.UPSERT_GEO_EVENT, rows)
    print(f"gdelt: window {window:%Y-%m-%d %H:%M}Z, upserted {n} chokepoint aggregates")


if __name__ == "__main__":
    run()

"""Live signals: recent geo_events near chokepoints -> suggested soft-factor clamps.

Suggestions are ADVISORY: the mapping below is provisional and documented in the
response; the analyst applies a suggestion explicitly in the UI — nothing is
auto-applied to scenarios. Degrades to {"available": false} without a database.
"""

from __future__ import annotations

import math
from typing import Any

import psycopg
from fastapi import APIRouter

from .settings import Settings

router = APIRouter(prefix="/signals", tags=["signals"])

MAX_KM = 300.0
WINDOW_DAYS = 7

EVENTS_SQL = """
SELECT source, category, severity, lon, lat, raw
FROM geo_events
WHERE event_time > now() - make_interval(days => %(days)s)
"""


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def _suggestions(bucket: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    if bucket["conflict_events"] >= 5:
        out["armed_conflict"] = round(min(1.0, bucket["conflict_events"] / 40.0), 2)
    if bucket["max_quake_mag"] >= 5.5:
        out["natural_hazard"] = round(min(1.0, (bucket["max_quake_mag"] - 5.0) / 3.0), 2)
    if bucket["gdacs_max_level"] >= 2.0:  # orange/red alert
        out["natural_hazard"] = max(out.get("natural_hazard", 0.0),
                                    0.5 if bucket["gdacs_max_level"] < 3 else 0.8)
    return out


def collect(chokepoints: list[dict[str, Any]], events: list[tuple]) -> list[dict[str, Any]]:
    buckets = {
        cp["id"]: {"chokepoint_id": cp["id"], "label": cp.get("label", cp["id"]),
                   "conflict_events": 0, "max_quake_mag": 0.0, "gdacs_max_level": 0.0,
                   "events": 0}
        for cp in chokepoints
    }
    for source, category, severity, lon, lat, raw in events:
        cid = None
        if source == "gdelt" and isinstance(raw, dict):
            cid = raw.get("chokepoint_id")
        if cid is None and lat is not None and lon is not None:
            best = MAX_KM
            for cp in chokepoints:
                d = _haversine_km(lat, lon, cp["lat"], cp["lon"])
                if d <= best:
                    cid, best = cp["id"], d
        b = buckets.get(cid) if cid else None
        if b is None:
            continue
        b["events"] += 1
        if source == "gdelt":
            b["conflict_events"] += int(severity or 0)
        elif source == "usgs":
            b["max_quake_mag"] = max(b["max_quake_mag"], float(severity or 0.0))
        elif source == "gdacs":
            b["gdacs_max_level"] = max(b["gdacs_max_level"], float(severity or 0.0))
    out = []
    for b in buckets.values():
        if b["events"] == 0:
            continue
        b["suggested_clamps"] = _suggestions(b)
        out.append(b)
    out.sort(key=lambda b: b["events"], reverse=True)
    return out


@router.get("/chokepoints")
def chokepoint_signals() -> dict[str, Any]:
    from .main import _graph  # late import to reuse the cached graph

    try:
        with psycopg.connect(Settings().database_url, connect_timeout=3) as conn, \
                conn.cursor() as cur:
            cur.execute(EVENTS_SQL, {"days": WINDOW_DAYS})
            events = cur.fetchall()
    except psycopg.Error:
        return {"available": False, "window_days": WINDOW_DAYS, "chokepoints": []}

    g = _graph()
    chokepoints = [{"id": n, **d} for n, d in g.nodes(data=True)
                   if d.get("type") == "chokepoint" and d.get("lat") is not None]
    return {
        "available": True,
        "window_days": WINDOW_DAYS,
        "note": "suggested_clamps use a provisional mapping (conflict events/40; "
                "quake (mag-5)/3; GDACS orange 0.5, red 0.8) — advisory only",
        "chokepoints": collect(chokepoints, events),
    }

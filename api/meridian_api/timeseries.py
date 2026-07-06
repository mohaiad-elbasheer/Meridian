"""Historical series and trade dependencies for the Monitoring view.

Chokepoint series come from ingested `chokepoint_daily` rows, matched to the graph's
chokepoints by PortWatch portname (same normalization as baselines.py). Trade
dependencies come from ingested UN Comtrade rows (`country_trade`). Both degrade to
{"available": false} without a database — the UI hides the affected widgets.
"""

from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, Query

from .baselines import _normalize
from .settings import Settings

router = APIRouter(tags=["monitoring"])

SERIES_SQL = """
SELECT date::text, transit_calls, trade_tons
FROM chokepoint_daily
WHERE {match} = %(name)s AND date > (SELECT max(date) FROM chokepoint_daily) - %(days)s::int
ORDER BY date
""".format(match="lower(regexp_replace(raw->>'portname', '[^a-zA-Z0-9]', '', 'g'))")

DEPENDENCIES_SQL = """
SELECT reporter, partner, year, import_usd
FROM country_trade
WHERE year = (SELECT max(year) FROM country_trade) AND import_usd IS NOT NULL
"""


def _connect() -> psycopg.Connection:
    return psycopg.connect(Settings().database_url, connect_timeout=3)


@router.get("/timeseries/chokepoints/{chokepoint_id}")
def chokepoint_series(chokepoint_id: str, days: int = Query(90, ge=7, le=730)) -> dict[str, Any]:
    from .main import _graph  # late import to reuse the cached graph

    node = _graph().nodes.get(chokepoint_id)
    if node is None or node.get("type") != "chokepoint":
        return {"available": False, "reason": "unknown chokepoint", "points": []}
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(SERIES_SQL, {"name": _normalize(node.get("label", chokepoint_id)),
                                     "days": days})
            rows = cur.fetchall()
    except psycopg.Error:
        return {"available": False, "reason": "database unreachable", "points": []}
    return {
        "available": len(rows) > 0,
        "chokepoint_id": chokepoint_id,
        "label": node.get("label", chokepoint_id),
        "days": days,
        "points": [{"date": r[0], "transit_calls": r[1], "trade_tons": r[2]} for r in rows],
    }


@router.get("/trade/dependencies")
def trade_dependencies(top: int = Query(8, ge=1, le=50)) -> dict[str, Any]:
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(DEPENDENCIES_SQL)
            rows = cur.fetchall()
    except psycopg.Error:
        return {"available": False, "reporters": {}}
    if not rows:
        return {"available": False, "reporters": {}}

    year = rows[0][2]
    totals: dict[str, float] = {}
    partners: dict[str, list[tuple[str, float]]] = {}
    for reporter, partner, _year, usd in rows:
        if partner == "WLD" or partner == "W00":
            totals[reporter] = max(totals.get(reporter, 0.0), float(usd))
        else:
            partners.setdefault(reporter, []).append((partner, float(usd)))
    reporters: dict[str, Any] = {}
    for reporter, plist in partners.items():
        total = totals.get(reporter) or sum(v for _, v in plist)
        if total <= 0:
            continue
        plist.sort(key=lambda pv: pv[1], reverse=True)
        reporters[reporter] = {
            "total_import_usd": total,
            "partners": [{"partner": p, "import_usd": v, "share": v / total}
                         for p, v in plist[:top]],
        }
    return {"available": True, "year": year, "source": "UN Comtrade (annual)",
            "reporters": reporters}

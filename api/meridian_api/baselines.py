"""Baseline graph provider: PortWatch averages from TimescaleDB when available,
bundled synthetic seed otherwise.

Merge strategy (honest by construction):
- Topology (chokepoint coordinates, alt routes, country import shares) is CURATED —
  PortWatch daily data carries none of it. It stays curated until UN Comtrade
  ingestion; a warning says so whenever DB baselines are in use.
- Volumes (baseline_daily_tons / baseline_daily_calls) come from trailing-N-day
  averages of ingested `chokepoint_daily` / `port_daily` rows, matched to curated
  entries by the PortWatch `portname` kept in the raw payload — no invented ID maps.
- Chokepoints without a DB match keep synthetic volumes and are listed in a warning.
- Empty/unreachable DB -> full synthetic seed, flagged as before.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import networkx as nx
import psycopg

from meridian_engine import build_graph_from_baselines, load_synthetic_seed

log = logging.getLogger(__name__)

BASELINE_SQL = """
SELECT max(raw->>'portname') AS portname,
       avg({calls_col})::float AS calls,
       avg({tons_col})::float AS tons,
       count(*) AS n_days,
       max(date) AS latest
FROM {table}
WHERE date > (SELECT max(date) FROM {table}) - %(days)s::int
GROUP BY {id_col}
"""


@dataclass
class DbBaseline:
    portname: str
    calls: float | None
    tons: float | None
    n_days: int
    latest: date


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def fetch_db_baselines(conn: psycopg.Connection, table: str, trailing_days: int,
                       ) -> list[DbBaseline]:
    cols = {
        "chokepoint_daily": ("chokepoint_id", "transit_calls", "trade_tons"),
        "port_daily": ("port_id", "portcalls", "import_tons + export_tons"),
    }
    id_col, calls_col, tons_col = cols[table]
    sql = BASELINE_SQL.format(table=table, id_col=id_col, calls_col=calls_col,
                              tons_col=tons_col)
    with conn.cursor() as cur:
        cur.execute(sql, {"days": trailing_days})
        rows = cur.fetchall()
    return [DbBaseline(*r) for r in rows if r[0]]


def merge_baselines(template: list[dict[str, Any]], db_rows: list[DbBaseline],
                    ) -> tuple[list[dict[str, Any]], list[str], int]:
    """Overlay DB volume averages onto curated entries, matched by normalized name.
    Returns (merged entries, unmatched curated labels, matched count)."""
    by_name = {_normalize(r.portname): r for r in db_rows}
    merged, unmatched, matched = [], [], 0
    for entry in template:
        row = by_name.get(_normalize(entry.get("label", entry["id"])))
        entry = dict(entry)
        if row is not None and row.tons:
            entry["baseline_daily_tons"] = row.tons
            if row.calls:
                entry["baseline_daily_calls"] = row.calls
            entry["baseline_source"] = "portwatch_daily"
            matched += 1
        else:
            entry["baseline_source"] = "synthetic_seed"
            unmatched.append(entry.get("label", entry["id"]))
        merged.append(entry)
    return merged, unmatched, matched


def build_graph(database_url: str, trailing_days: int) -> nx.DiGraph:
    """DB-backed graph if PortWatch rows exist; synthetic seed fallback otherwise."""
    seed = load_synthetic_seed()
    try:
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            cp_rows = fetch_db_baselines(conn, "chokepoint_daily", trailing_days)
            port_rows = fetch_db_baselines(conn, "port_daily", trailing_days)
    except psycopg.Error as exc:
        log.warning("database unavailable (%s); serving synthetic seed", exc)
        cp_rows, port_rows = [], []

    if not cp_rows:
        g = build_graph_from_baselines(seed["chokepoints"], seed["ports"])
        g.graph.update(
            source=seed["name"], synthetic=True, provenance="synthetic",
            coverage={"chokepoints_observed": 0,
                      "chokepoints_total": len(seed["chokepoints"]),
                      "ports_observed": 0, "ports_total": len(seed["ports"])},
        )
        return g

    chokepoints, cp_unmatched, cp_matched = merge_baselines(seed["chokepoints"], cp_rows)
    ports, _, port_matched = merge_baselines(seed["ports"], port_rows)
    g = build_graph_from_baselines(chokepoints, ports)
    latest = max(r.latest for r in cp_rows)
    # Provenance contract (QC REL-02): a single matched row must not present the
    # whole graph as observed. "observed" requires every chokepoint matched.
    provenance = "observed" if cp_matched == len(chokepoints) else "mixed"
    g.graph.update(
        source=f"portwatch_daily (trailing {trailing_days}d avg to {latest})",
        synthetic=False,
        provenance=provenance,
        coverage={"chokepoints_observed": cp_matched, "chokepoints_total": len(chokepoints),
                  "ports_observed": port_matched, "ports_total": len(ports)},
        data_warnings=[
            "topology (alt routes, import shares, coordinates) is curated v0 — "
            "not derived from data until Comtrade ingestion",
        ],
    )
    if provenance == "mixed":
        g.graph["data_warnings"].insert(0,
            f"MIXED baselines: {cp_matched}/{len(chokepoints)} chokepoints observed from "
            "PortWatch; the rest retain synthetic seed volumes")
    if cp_unmatched:
        g.graph["data_warnings"].append(
            f"no PortWatch match for {len(cp_unmatched)} chokepoint(s) "
            f"({', '.join(sorted(cp_unmatched)[:4])}…) — synthetic volumes retained"
            if len(cp_unmatched) > 4 else
            f"no PortWatch match for: {', '.join(sorted(cp_unmatched))} — "
            "synthetic volumes retained")
    log.info("baselines: %d chokepoints + %d ports from DB (%s)",
             cp_matched, port_matched, provenance)
    return g


def sources_status(database_url: str) -> dict[str, Any]:
    status: dict[str, Any] = {"database": {"reachable": False}, "tables": {}}
    try:
        with psycopg.connect(database_url, connect_timeout=3) as conn, conn.cursor() as cur:
            status["database"]["reachable"] = True
            queries = {
                "chokepoint_daily": "SELECT count(*), max(date::text), "
                                    "count(DISTINCT chokepoint_id) FROM chokepoint_daily",
                "port_daily": "SELECT count(*), max(date::text), "
                              "count(DISTINCT port_id) FROM port_daily",
                "geo_events": "SELECT count(*), max(event_time::date::text), "
                              "count(DISTINCT source) FROM geo_events",
            }
            for table, sql in queries.items():
                cur.execute(sql)
                rows, latest, distinct = cur.fetchone()  # type: ignore[misc]
                status["tables"][table] = {"rows": rows, "latest": latest,
                                           "distinct": distinct}
    except psycopg.Error as exc:
        status["database"]["error"] = str(exc).strip()
    return status

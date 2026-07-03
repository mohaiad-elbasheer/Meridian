"""Thin psycopg layer. All writes are idempotent: ON CONFLICT DO NOTHING on natural keys,
raw payloads stored as JSONB so rows can be reprocessed without re-fetching.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import psycopg
from psycopg.types.json import Jsonb

# Allowlist for identifiers interpolated into SQL.
_TABLES = {"chokepoint_daily", "port_daily", "geo_events"}

UPSERT_CHOKEPOINT = """
INSERT INTO chokepoint_daily (chokepoint_id, date, transit_calls, trade_tons, vessel_breakdown, raw)
VALUES (%(chokepoint_id)s, %(date)s, %(transit_calls)s, %(trade_tons)s, %(vessel_breakdown)s, %(raw)s)
ON CONFLICT (chokepoint_id, date) DO NOTHING
"""

UPSERT_PORT = """
INSERT INTO port_daily (port_id, date, portcalls, import_tons, export_tons, raw)
VALUES (%(port_id)s, %(date)s, %(portcalls)s, %(import_tons)s, %(export_tons)s, %(raw)s)
ON CONFLICT (port_id, date) DO NOTHING
"""

UPSERT_GEO_EVENT = """
INSERT INTO geo_events (id, source, event_time, category, severity, lon, lat, raw)
VALUES (%(id)s, %(source)s, %(event_time)s, %(category)s, %(severity)s, %(lon)s, %(lat)s, %(raw)s)
ON CONFLICT (id) DO NOTHING
"""


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


def max_date(conn: psycopg.Connection, table: str) -> date | None:
    if table not in _TABLES:
        raise ValueError(f"unknown table: {table}")
    with conn.cursor() as cur:
        cur.execute(f"SELECT max(date) FROM {table}")  # noqa: S608 — table allowlisted above
        row = cur.fetchone()
    return row[0] if row else None


def _wrap_json(row: dict[str, Any]) -> dict[str, Any]:
    return {k: Jsonb(v) if k in ("raw", "vessel_breakdown") and v is not None else v
            for k, v in row.items()}


def upsert_many(conn: psycopg.Connection, sql: str, rows: Iterable[dict[str, Any]]) -> int:
    """Insert rows idempotently; returns how many were attempted."""
    n = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, _wrap_json(row))
            n += 1
    conn.commit()
    return n

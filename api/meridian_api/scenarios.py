"""Scenario persistence (P2 CRUD). Specs are validated against the engine's
ScenarioSpec before touching the DB; a missing DB degrades to 503, never a crash."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from meridian_engine import ScenarioSpec

from .settings import Settings

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class SavedScenarioIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    spec: ScenarioSpec


def _connect() -> psycopg.Connection:
    try:
        return psycopg.connect(Settings().database_url, connect_timeout=3)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="scenario storage unavailable (database unreachable)") from exc


def _row(r: tuple) -> dict[str, Any]:
    return {"id": str(r[0]), "name": r[1], "spec": r[2],
            "created_at": r[3].isoformat(), "updated_at": r[4].isoformat()}


COLS = "id, name, spec, created_at, updated_at"


@router.get("")
def list_scenarios() -> list[dict]:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {COLS} FROM scenarios ORDER BY updated_at DESC")
        return [_row(r) for r in cur.fetchall()]


@router.post("", status_code=201)
def create_scenario(body: SavedScenarioIn) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO scenarios (name, spec) VALUES (%s, %s) RETURNING {COLS}",
            (body.name, Jsonb(body.spec.model_dump())))
        row = cur.fetchone()
        conn.commit()
    return _row(row)  # type: ignore[arg-type]


@router.get("/{scenario_id}")
def get_scenario(scenario_id: UUID) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {COLS} FROM scenarios WHERE id = %s", (scenario_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return _row(row)


@router.put("/{scenario_id}")
def update_scenario(scenario_id: UUID, body: SavedScenarioIn) -> dict:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE scenarios SET name = %s, spec = %s, updated_at = now() "
            f"WHERE id = %s RETURNING {COLS}",
            (body.name, Jsonb(body.spec.model_dump()), scenario_id))
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return _row(row)


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: UUID) -> None:
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM scenarios WHERE id = %s RETURNING id", (scenario_id,))
        row = cur.fetchone()
        conn.commit()
    if row is None:
        raise HTTPException(status_code=404, detail="scenario not found")

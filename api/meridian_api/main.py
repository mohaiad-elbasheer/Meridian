"""Meridian API — thin layer over engine + DB.

Baselines come from ingested PortWatch rows in TimescaleDB when present (trailing
average, curated topology overlay — see baselines.py); otherwise the bundled,
clearly-flagged synthetic seed. Routes may be renamed freely until P2 is declared done.
"""

import json
import time
from functools import lru_cache
from importlib.resources import files

import networkx as nx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from meridian_engine import FCMSpec, ScenarioSpec, SimulationRequest, run_scenario, simulate

from . import baselines
from .settings import Settings

app = FastAPI(title="Meridian API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def _macro_spec() -> FCMSpec:
    raw = files("meridian_engine").joinpath("maps/macro_v0.json").read_text()
    return FCMSpec.model_validate(json.loads(raw))


_graph_cache: tuple[float, nx.DiGraph] | None = None


def _graph(force_refresh: bool = False) -> nx.DiGraph:
    global _graph_cache
    s = _settings()
    now = time.monotonic()
    if force_refresh or _graph_cache is None or now - _graph_cache[0] > s.baseline_cache_seconds:
        _graph_cache = (now, baselines.build_graph(s.database_url, s.baseline_trailing_days))
    return _graph_cache[1]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sources/status")
def get_sources_status() -> dict:
    return baselines.sources_status(_settings().database_url)


@app.get("/network/baseline")
def network_baseline(refresh: bool = False) -> dict:
    g = _graph(force_refresh=refresh)
    return {
        "source": g.graph.get("source"),
        "synthetic": bool(g.graph.get("synthetic", False)),
        "data_warnings": g.graph.get("data_warnings", []),
        "nodes": [{"id": n, **d} for n, d in g.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in g.edges(data=True)],
    }


@app.get("/fcm/map")
def fcm_map() -> dict:
    return _macro_spec().model_dump()


@app.post("/fcm/simulate")
def fcm_simulate(request: SimulationRequest) -> dict:
    try:
        return simulate(_macro_spec(), request).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/scenario/simulate")
def scenario_simulate(scenario: ScenarioSpec) -> dict:
    try:
        return run_scenario(_macro_spec(), _graph(), scenario).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

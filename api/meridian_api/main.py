"""Meridian API — thin layer over engine + DB.

Prototype scope: serves the bundled synthetic baseline graph (clearly flagged) so the
full loop runs with no DB; once PortWatch data is ingested the graph source switches to
TimescaleDB baselines. Routes may be renamed freely until P2 is declared done.
"""

import json
from functools import lru_cache
from importlib.resources import files

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from meridian_engine import (
    FCMSpec, ScenarioSpec, SimulationRequest, build_synthetic_graph, run_scenario, simulate,
)

app = FastAPI(title="Meridian API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _macro_spec() -> FCMSpec:
    raw = files("meridian_engine").joinpath("maps/macro_v0.json").read_text()
    return FCMSpec.model_validate(json.loads(raw))


@lru_cache(maxsize=1)
def _graph():
    return build_synthetic_graph()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/network/baseline")
def network_baseline() -> dict:
    g = _graph()
    return {
        "source": g.graph.get("source"),
        "synthetic": bool(g.graph.get("synthetic", False)),
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

"""Meridian API — thin layer over engine + DB. Expanded in Phase P2."""

import json
from importlib.resources import files

from fastapi import FastAPI

from meridian_engine import FCMSpec, SimulationRequest, simulate

app = FastAPI(title="Meridian API", version="0.1.0")


def _macro_spec() -> FCMSpec:
    raw = files("meridian_engine").joinpath("maps/macro_v0.json").read_text()
    return FCMSpec.model_validate(json.loads(raw))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/fcm/simulate")
def fcm_simulate(request: SimulationRequest) -> dict:
    result = simulate(_macro_spec(), request)
    return result.model_dump()

import json
from pathlib import Path

from meridian_engine import Clamp, FCMSpec, SimulationRequest, simulate

MAP = Path(__file__).resolve().parents[1] / "meridian_engine" / "maps" / "macro_v0.json"


def load_spec() -> FCMSpec:
    return FCMSpec.model_validate(json.loads(MAP.read_text()))


def test_macro_map_validates():
    spec = load_spec()
    assert len(spec.concepts) == 12
    assert all(e.provenance.provisional for e in spec.edges)  # weights not yet literature-assigned


def test_simulation_converges_deterministically():
    spec = load_spec()
    req = SimulationRequest(clamps=[Clamp(concept_id="armed_conflict", value=1.0)])
    r1 = simulate(spec, req)
    r2 = simulate(spec, req)
    assert r1.converged and r1.steps <= 100
    assert r1.final_activations == r2.final_activations


def test_conflict_scenario_raises_costs_and_disruption():
    spec = load_spec()
    base = simulate(spec, SimulationRequest())
    shock = simulate(spec, SimulationRequest(clamps=[Clamp(concept_id="armed_conflict", value=1.0)]))
    assert shock.final_activations["chokepoint_disruption"] > base.final_activations["chokepoint_disruption"]
    assert shock.final_activations["landed_cost"] > base.final_activations["landed_cost"]
    assert "reroute_cost_factor" in shock.network_multipliers
    assert shock.network_multipliers["reroute_cost_factor"] >= 1.0


def test_clamp_window():
    spec = load_spec()
    req = SimulationRequest(clamps=[Clamp(concept_id="natural_hazard", value=1.0, from_step=0, to_step=3)])
    res = simulate(spec, req)
    assert res.trajectories["natural_hazard"][3] == 1.0
    assert res.trajectories["natural_hazard"][-1] != 1.0  # released after window

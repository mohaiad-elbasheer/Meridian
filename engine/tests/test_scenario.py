import json
from pathlib import Path

import pytest

from meridian_engine import (
    Clamp, FCMSpec, ScenarioSpec, build_synthetic_graph, run_scenario,
)

MAP = Path(__file__).resolve().parents[1] / "meridian_engine" / "maps" / "macro_v0.json"


def spec() -> FCMSpec:
    return FCMSpec.model_validate(json.loads(MAP.read_text()))


def suez_scenario(**overrides) -> ScenarioSpec:
    base = dict(name="Suez -80% for 14 days", target_chokepoint_id="suez_canal",
                capacity_reduction=0.8, duration_days=14)
    return ScenarioSpec(**{**base, **overrides})


def test_p1_dod_suez_scenario():
    """P1 DoD: 'Suez -80% capacity for 14 days' returns rerouted volumes + added days
    + FCM-modulated cost indices; deterministic."""
    g = build_synthetic_graph()
    r1 = run_scenario(spec(), g, suez_scenario())
    r2 = run_scenario(spec(), build_synthetic_graph(), suez_scenario())

    assert r1.model_dump() == r2.model_dump()  # deterministic
    assert r1.fcm.converged

    # network outputs in real units
    blocked_daily = g.nodes["suez_canal"]["baseline_daily_tons"] * 0.8
    assert r1.impact.rerouted_tons + r1.impact.delayed_tons == pytest.approx(blocked_daily * 14)
    assert r1.impact.rerouted_tons > 0
    assert r1.impact.avg_added_days >= 9.5  # Cape reroute penalty (+ any dwell)
    assert r1.impact.country_exposure["EGY"] == pytest.approx(0.45 * 0.8 * 100)

    # FCM-modulated cost indices present and sensible
    assert r1.network_multipliers["reroute_cost_factor"] >= 1.0
    assert r1.network_multipliers["port_dwell_factor"] >= 1.0


def test_escalation_clamp_raises_cost_indices():
    g = build_synthetic_graph()
    calm = run_scenario(spec(), g, suez_scenario())
    hot = run_scenario(spec(), g, suez_scenario(
        fcm_clamps=[Clamp(concept_id="armed_conflict", value=1.0)]))
    assert hot.network_multipliers["reroute_cost_factor"] > \
        calm.network_multipliers["reroute_cost_factor"]
    assert hot.fcm.final_activations["landed_cost"] > calm.fcm.final_activations["landed_cost"]


def test_provenance_and_synthetic_warnings_surface():
    r = run_scenario(spec(), build_synthetic_graph(), suez_scenario())
    assert r.provisional_edges == r.total_edges == 14
    assert any("provisional" in w for w in r.warnings)
    assert any("synthetic" in w for w in r.warnings)


def test_unknown_chokepoint_rejected():
    with pytest.raises(ValueError, match="Unknown chokepoint"):
        run_scenario(spec(), build_synthetic_graph(),
                     suez_scenario(target_chokepoint_id="atlantis"))


def test_hormuz_has_no_alternative():
    r = run_scenario(spec(), build_synthetic_graph(), suez_scenario(
        name="Hormuz -50%", target_chokepoint_id="strait_of_hormuz", capacity_reduction=0.5))
    assert r.impact.rerouted_tons == 0.0  # no alt route exists
    assert r.impact.delayed_tons > 0
    assert r.impact.country_exposure["JPN"] > 30

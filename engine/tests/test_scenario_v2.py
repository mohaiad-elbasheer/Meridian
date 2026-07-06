import json
from pathlib import Path

import pytest

from meridian_engine import Clamp, FCMSpec, ScenarioSpec, build_synthetic_graph, run_scenario
from meridian_engine.scenario import DEFAULT_VALUE_PER_TON_USD, VESSEL_CLASSES

MAP = Path(__file__).resolve().parents[1] / "meridian_engine" / "maps" / "macro_v0.json"


def spec() -> FCMSpec:
    return FCMSpec.model_validate(json.loads(MAP.read_text()))


def run(**kw):
    base = dict(target_chokepoint_id="strait_of_hormuz", capacity_reduction=0.0,
                duration_days=30)
    return run_scenario(spec(), build_synthetic_graph(), ScenarioSpec(**{**base, **kw}))


def test_tanker_only_disruption_hits_tanker_class():
    r = run(class_reductions={"tanker": 0.9})
    # Hormuz: 75% tanker share, 5.5M t/d baseline -> effective reduction 0.675
    assert r.kpis.per_class["tanker"].reduction == 0.9
    assert r.kpis.per_class["container"].reduction == 0.0
    assert r.kpis.per_class["container"].blocked_tons == 0.0
    expected_blocked = 5_500_000 * 0.75 * 0.9 * 30
    assert r.kpis.blocked_tons == pytest.approx(expected_blocked)
    assert r.network_multipliers["chokepoint_capacity_multiplier:strait_of_hormuz"] == \
        pytest.approx(1 - 0.675)
    # no alt route at Hormuz -> everything delayed
    assert r.kpis.delayed_tons == pytest.approx(expected_blocked)
    assert r.kpis.value_delayed_usd == pytest.approx(
        expected_blocked * DEFAULT_VALUE_PER_TON_USD["tanker"])


def test_cause_derives_soft_factor_clamps_dynamically():
    calm = run(capacity_reduction=0.5, cause="unspecified")
    hot = run(capacity_reduction=0.5, cause="conflict")
    assert "armed_conflict" not in calm.auto_clamps
    assert hot.auto_clamps["armed_conflict"] == pytest.approx(0.3 + 0.7 * 0.5)
    assert hot.kpis.reroute_cost_factor > calm.kpis.reroute_cost_factor
    # scenario change alters the FCM outcome, not just network numbers
    assert hot.fcm.final_activations["war_risk_premium"] > \
        calm.fcm.final_activations["war_risk_premium"]


def test_expert_clamp_overrides_auto():
    r = run(capacity_reduction=0.5, cause="conflict",
            fcm_clamps=[Clamp(concept_id="armed_conflict", value=0.1)])
    assert r.fcm.final_activations["armed_conflict"] == pytest.approx(0.1)
    assert r.auto_clamps["armed_conflict"] > 0.1  # derived value reported for transparency


def test_kpis_are_consistent():
    r = run(target_chokepoint_id="suez_canal", capacity_reduction=0.8, duration_days=14)
    k = r.kpis
    assert k.blocked_tons == pytest.approx(k.rerouted_tons + k.delayed_tons)
    assert k.baseline_window_tons == pytest.approx(4_500_000 * 14)
    assert 0 <= k.delayed_share_of_window <= 1
    assert sum(c.blocked_tons for c in k.per_class.values()) == pytest.approx(k.blocked_tons)
    assert set(k.per_class) == set(VESSEL_CLASSES)
    assert k.top_exposed_countries  # non-empty for Suez


def test_assumptions_reported_and_overridable():
    r = run(capacity_reduction=0.5, value_per_ton_usd={"tanker": 700.0})
    assert r.assumptions["value_per_ton_usd"]["tanker"] == 700.0
    assert r.assumptions["value_per_ton_provisional"] is True
    assert r.assumptions["class_shares_source"] == "curated_seed"
    assert any("USD/ton" in w for w in r.warnings)


def test_unknown_class_rejected():
    with pytest.raises(ValueError, match="Unknown vessel class"):
        run(class_reductions={"submarine": 0.5})

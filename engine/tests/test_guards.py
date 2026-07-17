import json
from pathlib import Path

import pytest

from meridian_engine import FCMSpec, ScenarioSpec, build_synthetic_graph, run_scenario

MAP = Path(__file__).resolve().parents[1] / "meridian_engine" / "maps" / "macro_v0.json"


def spec() -> FCMSpec:
    return FCMSpec.model_validate(json.loads(MAP.read_text()))


def test_negative_value_per_ton_rejected():
    with pytest.raises(ValueError, match="finite value >= 0"):
        ScenarioSpec(target_chokepoint_id="suez_canal", capacity_reduction=0.5,
                     duration_days=7, value_per_ton_usd={"tanker": -100.0})


def test_nan_and_inf_value_per_ton_rejected():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite value >= 0"):
            ScenarioSpec(target_chokepoint_id="suez_canal", capacity_reduction=0.5,
                         duration_days=7, value_per_ton_usd={"tanker": bad})


def test_non_convergence_produces_prominent_warning():
    r = run_scenario(spec(), build_synthetic_graph(), ScenarioSpec(
        target_chokepoint_id="suez_canal", capacity_reduction=0.8, duration_days=14,
        max_steps=1))  # force non-convergence
    assert r.fcm.converged is False
    assert r.warnings[0].startswith("FCM did NOT converge")


def test_converged_run_has_no_convergence_warning():
    r = run_scenario(spec(), build_synthetic_graph(), ScenarioSpec(
        target_chokepoint_id="suez_canal", capacity_reduction=0.8, duration_days=14))
    assert r.fcm.converged is True
    assert not any(w.startswith("FCM did NOT") for w in r.warnings)

"""Generate the static-demo dataset for the GitHub Pages build.

Writes into web/src/demo/data/:
- baseline.json      — the synthetic-seed graph exactly as /network/baseline serves it
- fcm.json           — the macro_v0 FCM spec exactly as /fcm/map serves it
- parity_cases.json  — scenario inputs + full expected results computed by the REAL
                       Python engine; the TypeScript port must reproduce them
                       (web parity test, run in CI). This is the guard against the
                       demo drifting from the research engine.
- series.json        — ILLUSTRATIVE 90-day series per chokepoint (deterministic,
                       seeded; mild seasonality + noise around the synthetic
                       baseline). Flagged illustrative and labeled as such in the
                       demo UI — never presented as observed history.

Run from repo root:  python tools/gen_demo_data.py
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from meridian_engine import (
    Clamp, FCMSpec, ScenarioSpec, build_synthetic_graph, run_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "demo" / "data"

CASES = [
    {"target_chokepoint_id": "suez_canal", "capacity_reduction": 0.8, "duration_days": 14,
     "fcm_clamps": []},
    {"target_chokepoint_id": "suez_canal", "capacity_reduction": 0.8, "duration_days": 14,
     "fcm_clamps": [{"concept_id": "armed_conflict", "value": 1.0}]},
    {"target_chokepoint_id": "strait_of_hormuz", "capacity_reduction": 0.5, "duration_days": 30,
     "fcm_clamps": [{"concept_id": "war_risk_premium", "value": 0.75}]},
    {"target_chokepoint_id": "strait_of_malacca", "capacity_reduction": 1.0, "duration_days": 7,
     "fcm_clamps": [{"concept_id": "natural_hazard", "value": 0.6}]},
    {"target_chokepoint_id": "panama_canal", "capacity_reduction": 0.35, "duration_days": 90,
     "fcm_clamps": [{"concept_id": "sanction_risk", "value": -0.4}]},
    {"target_chokepoint_id": "bab_el_mandeb", "capacity_reduction": 0.65, "duration_days": 21,
     "fcm_clamps": [{"concept_id": "armed_conflict", "value": 0.9},
                    {"concept_id": "energy_prices", "value": 0.5}]},
    # v2: vessel-class targeting + cause-derived soft factors
    {"target_chokepoint_id": "strait_of_hormuz", "capacity_reduction": 0.0, "duration_days": 30,
     "class_reductions": {"tanker": 0.9}, "cause": "conflict", "fcm_clamps": []},
    {"target_chokepoint_id": "suez_canal", "capacity_reduction": 0.6, "duration_days": 21,
     "class_reductions": {"container": 0.9, "tanker": 0.2}, "cause": "natural_hazard",
     "fcm_clamps": []},
    {"target_chokepoint_id": "bosporus_strait", "capacity_reduction": 0.7, "duration_days": 45,
     "cause": "policy", "value_per_ton_usd": {"dry_bulk": 300.0},
     "fcm_clamps": [{"concept_id": "sanction_risk", "value": 0.95}]},
]


def main() -> None:
    fcm_spec = FCMSpec.model_validate(json.loads(
        (ROOT / "engine/meridian_engine/maps/macro_v0.json").read_text()))
    g = build_synthetic_graph()

    baseline = {
        "source": g.graph.get("source"),
        "synthetic": bool(g.graph.get("synthetic", False)),
        "data_warnings": g.graph.get("data_warnings", []),
        "nodes": [{"id": n, **d} for n, d in g.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in g.edges(data=True)],
    }

    cases = []
    for case in CASES:
        spec = ScenarioSpec(
            **{**case, "fcm_clamps": [Clamp(**c) for c in case["fcm_clamps"]]})
        cases.append({"input": case, "expected": run_scenario(fcm_spec, g, spec).model_dump()})

    seed = json.loads((ROOT / "engine/meridian_engine/data/synthetic_seed_v0.json").read_text())
    start = date(2026, 4, 8)  # fixed window keeps output deterministic
    series = {}
    for cp in seed["chokepoints"]:
        rng = random.Random(cp["id"])
        pts = []
        for i in range(90):
            level = 1 + 0.06 * math.sin(i / 90 * 2 * math.pi) + rng.uniform(-0.05, 0.05)
            pts.append({
                "date": str(start + timedelta(days=i)),
                "transit_calls": round(cp["baseline_daily_calls"] * level),
                "trade_tons": round(cp["baseline_daily_tons"] * level),
            })
        series[cp["id"]] = pts

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "baseline.json").write_text(json.dumps(baseline, indent=1))
    (OUT / "fcm.json").write_text(json.dumps(fcm_spec.model_dump(), indent=1))
    (OUT / "parity_cases.json").write_text(json.dumps(cases, indent=1))
    (OUT / "series.json").write_text(json.dumps({"illustrative": True, "series": series}))
    print(f"wrote {OUT}/baseline.json, fcm.json, parity_cases.json ({len(cases)} cases), "
          f"series.json ({len(series)} chokepoints)")


if __name__ == "__main__":
    main()

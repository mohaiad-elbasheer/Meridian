"""Scenario orchestrator: composes the FCM layer (soft factors) with the network layer.

v2 additions (all backward compatible):
- Vessel-class targeting: reductions can differ per class (container / dry bulk /
  general cargo / ro-ro / tanker), mirroring PortWatch's per-class observations.
  The network layer still propagates total tons; class outputs are derived from the
  per-class blocked volumes.
- Dynamic soft factors: the scenario's `cause` + severity derive FCM clamps
  automatically (documented mapping below, provisional). Expert-provided clamps for
  the same concept always win. `auto_clamps` in the result shows what was derived.
- KPI layer: headline figures with explicit, per-scenario-overridable valuation
  assumptions (USD/ton per vessel class). Assumptions are always reported back.

Flow for e.g. "Suez -80% capacity for 14 days":
1. Derive clamps (disruption level, cause concepts), merge expert clamps, run FCM
   to convergence -> concept activations -> coupling multipliers.
2. The user-specified reductions are authoritative for the TARGET chokepoint; the
   FCM's own untargeted capacity multiplier is surfaced but not applied on top
   (double-counting). `port_dwell_factor` modulates rerouted flows;
   `reroute_cost_factor` is a cost index.
3. Deterministic given the same inputs (both layers are pure; no randomness).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Literal

import networkx as nx
from pydantic import BaseModel, Field, model_validator

from .fcm import simulate
from .models import Clamp, FCMSpec, SimulationRequest, SimulationResult
from .network import CAPACITY_KEY, NetworkImpact, apply_scenario

DISRUPTION_CONCEPT = "chokepoint_disruption"

VESSEL_CLASSES = ("container", "dry_bulk", "general_cargo", "roro", "tanker")

# PROVISIONAL analyst assumptions (typical cargo value density, USD per metric ton).
# Overridable per scenario; always echoed back in ScenarioResult.assumptions.
DEFAULT_VALUE_PER_TON_USD = {
    "container": 4000.0,
    "dry_bulk": 120.0,
    "general_cargo": 900.0,
    "roro": 3000.0,
    "tanker": 550.0,
}

# Fallback class mix when a chokepoint has no curated/observed class shares.
# PROVISIONAL and flagged in assumptions whenever used.
DEFAULT_CLASS_SHARES = {
    "container": 0.30, "dry_bulk": 0.25, "general_cargo": 0.15,
    "roro": 0.05, "tanker": 0.25,
}

Cause = Literal["unspecified", "conflict", "natural_hazard", "accident", "policy"]

# cause -> (concept, base, gain): clamp value = clip(base + gain * severity, 0, 1)
# where severity is the effective capacity reduction. PROVISIONAL mapping — the
# concepts and shape are documented so experts can override via fcm_clamps.
CAUSE_CLAMP_RULES: dict[str, list[tuple[str, float, float]]] = {
    "conflict": [("armed_conflict", 0.3, 0.7)],
    "natural_hazard": [("natural_hazard", 0.3, 0.7)],
    "policy": [("sanction_risk", 0.3, 0.7)],
    "accident": [],       # pure logistics event, no geopolitical concept activated
    "unspecified": [],
}


class ScenarioSpec(BaseModel):
    name: str = ""
    target_chokepoint_id: str
    capacity_reduction: float = Field(..., ge=0.0, le=1.0, description="0.8 = -80% capacity")
    duration_days: int = Field(..., ge=1, le=365)
    # v2: per-vessel-class reductions; a class listed here overrides capacity_reduction
    class_reductions: dict[str, float] = {}
    cause: Cause = "unspecified"
    fcm_clamps: list[Clamp] = []
    value_per_ton_usd: dict[str, float] = {}
    max_steps: int = Field(100, ge=1, le=10_000)
    epsilon: float = Field(1e-4, gt=0)

    @model_validator(mode="after")
    def _validate_classes(self) -> "ScenarioSpec":
        for cls, red in self.class_reductions.items():
            if cls not in VESSEL_CLASSES:
                raise ValueError(f"Unknown vessel class: {cls}")
            if not 0.0 <= red <= 1.0:
                raise ValueError(f"class_reductions[{cls}] out of [0,1]: {red}")
        for cls, value in self.value_per_ton_usd.items():
            if cls not in VESSEL_CLASSES:
                raise ValueError(f"Unknown vessel class in value_per_ton_usd: {cls}")
            if not (value >= 0.0) or value != value or value == float("inf"):
                raise ValueError(f"value_per_ton_usd[{cls}] must be a finite value >= 0: {value}")
        return self


class ClassImpact(BaseModel):
    share: float                # of the target chokepoint's baseline tons
    reduction: float            # applied capacity reduction for this class
    blocked_tons: float
    rerouted_tons: float
    delayed_tons: float
    value_delayed_usd: float


class Kpis(BaseModel):
    baseline_window_tons: float       # target baseline over the scenario window
    blocked_tons: float
    rerouted_tons: float
    delayed_tons: float
    delayed_share_of_window: float    # delayed / baseline window
    avg_added_days: float
    value_delayed_usd: float
    value_rerouted_usd: float
    per_class: dict[str, ClassImpact]
    reroute_cost_factor: float
    port_dwell_factor: float
    landed_cost_activation: float     # FCM outcome concept, dimensionless (-1..1)
    supply_availability_activation: float
    top_exposed_countries: dict[str, float]  # ISO3 -> % imports at risk


class NetworkImpactModel(BaseModel):
    rerouted_tons: float
    delayed_tons: float
    avg_added_days: float
    country_exposure: dict[str, float]
    chokepoints: list[dict]


class ScenarioResult(BaseModel):
    scenario: ScenarioSpec
    fcm: SimulationResult
    auto_clamps: dict[str, float]     # clamps derived from the scenario definition
    network_multipliers: dict[str, float]  # as applied to the network layer
    impact: NetworkImpactModel
    kpis: Kpis
    assumptions: dict[str, Any]
    provisional_edges: int
    total_edges: int
    warnings: list[str]


def derive_auto_clamps(spec: ScenarioSpec, effective_reduction: float) -> dict[str, float]:
    clamps = {DISRUPTION_CONCEPT: round(effective_reduction, 6)}
    for concept, base, gain in CAUSE_CLAMP_RULES[spec.cause]:
        clamps[concept] = round(min(1.0, base + gain * effective_reduction), 6)
    return clamps


def run_scenario(fcm_spec: FCMSpec, graph: nx.DiGraph, scenario: ScenarioSpec) -> ScenarioResult:
    node = graph.nodes.get(scenario.target_chokepoint_id)
    if node is None or node.get("type") != "chokepoint":
        raise ValueError(f"Unknown chokepoint: {scenario.target_chokepoint_id}")

    baseline_daily = float(node["baseline_daily_tons"])
    shares = node.get("class_shares")
    shares_provisional = shares is None
    if shares is None:
        shares = DEFAULT_CLASS_SHARES

    reductions = {c: scenario.class_reductions.get(c, scenario.capacity_reduction)
                  for c in VESSEL_CLASSES}
    blocked_daily_by_class = {c: baseline_daily * shares.get(c, 0.0) * reductions[c]
                              for c in VESSEL_CLASSES}
    blocked_daily = sum(blocked_daily_by_class.values())
    effective_reduction = blocked_daily / baseline_daily if baseline_daily > 0 else 0.0

    # Dynamic soft factors: scenario definition drives the FCM; expert clamps win.
    auto = derive_auto_clamps(scenario, effective_reduction)
    expert_concepts = {c.concept_id for c in scenario.fcm_clamps}
    clamps = list(scenario.fcm_clamps) + [
        Clamp(concept_id=k, value=v) for k, v in auto.items() if k not in expert_concepts
    ]
    fcm_result = simulate(fcm_spec, SimulationRequest(
        clamps=clamps, max_steps=scenario.max_steps, epsilon=scenario.epsilon))

    applied = {
        f"{CAPACITY_KEY}:{scenario.target_chokepoint_id}": 1.0 - effective_reduction,
    }
    for key in ("port_dwell_factor", "reroute_cost_factor"):
        if key in fcm_result.network_multipliers:
            applied[key] = fcm_result.network_multipliers[key]

    impact: NetworkImpact = apply_scenario(graph, applied, scenario.duration_days)

    # Per-class split of the network outcome, proportional to blocked volume.
    values = {**DEFAULT_VALUE_PER_TON_USD, **scenario.value_per_ton_usd}
    per_class: dict[str, ClassImpact] = {}
    value_delayed = value_rerouted = 0.0
    for c in VESSEL_CLASSES:
        frac = blocked_daily_by_class[c] / blocked_daily if blocked_daily > 0 else 0.0
        blocked_c = blocked_daily_by_class[c] * scenario.duration_days
        rerouted_c = impact.rerouted_tons * frac
        delayed_c = impact.delayed_tons * frac
        v_delayed = delayed_c * values[c]
        value_delayed += v_delayed
        value_rerouted += rerouted_c * values[c]
        per_class[c] = ClassImpact(
            share=shares.get(c, 0.0), reduction=reductions[c], blocked_tons=blocked_c,
            rerouted_tons=rerouted_c, delayed_tons=delayed_c, value_delayed_usd=v_delayed,
        )

    window_tons = baseline_daily * scenario.duration_days
    kpis = Kpis(
        baseline_window_tons=window_tons,
        blocked_tons=blocked_daily * scenario.duration_days,
        rerouted_tons=impact.rerouted_tons,
        delayed_tons=impact.delayed_tons,
        delayed_share_of_window=impact.delayed_tons / window_tons if window_tons > 0 else 0.0,
        avg_added_days=impact.avg_added_days,
        value_delayed_usd=value_delayed,
        value_rerouted_usd=value_rerouted,
        per_class=per_class,
        reroute_cost_factor=applied.get("reroute_cost_factor", 1.0),
        port_dwell_factor=applied.get("port_dwell_factor", 1.0),
        landed_cost_activation=fcm_result.final_activations.get("landed_cost", 0.0),
        supply_availability_activation=fcm_result.final_activations.get(
            "supply_availability", 0.0),
        top_exposed_countries=dict(list(impact.country_exposure.items())[:8]),
    )

    assumptions: dict[str, Any] = {
        "value_per_ton_usd": values,
        "value_per_ton_provisional": True,
        "class_shares": shares,
        "class_shares_source": "default_provisional" if shares_provisional else "curated_seed",
        "cause_clamp_rules": {
            c: {"base": b, "gain": g} for c, b, g in CAUSE_CLAMP_RULES[scenario.cause]
        },
    }

    warnings = []
    if not fcm_result.converged:
        warnings.append(
            f"FCM did NOT converge within {scenario.max_steps} steps — soft-factor "
            "indices are unreliable for this run; do not base decisions on them "
            "(increase max_steps or review clamps)")
    if fcm_spec.provisional_edges():
        warnings.append(
            f"{len(fcm_spec.provisional_edges())}/{len(fcm_spec.edges)} FCM edge weights are "
            "provisional (citation unassigned) — treat soft-factor outputs as indicative")
    if graph.graph.get("synthetic"):
        warnings.append(
            f"baselines: {graph.graph.get('source', 'unknown')} — synthetic development seed, "
            "not PortWatch data")
    if graph.graph.get("provenance") == "mixed" and \
            node.get("baseline_source") == "synthetic_seed":
        warnings.append(
            f"the TARGET chokepoint ({scenario.target_chokepoint_id}) has a synthetic "
            "baseline in this mixed dataset — its volumes are not observed")
    warnings.extend(graph.graph.get("data_warnings", []))
    warnings.append(
        "monetary figures use provisional USD/ton assumptions (see assumptions) — "
        "adjust them to your book of business")

    return ScenarioResult(
        scenario=scenario,
        fcm=fcm_result,
        auto_clamps=auto,
        network_multipliers=applied,
        impact=NetworkImpactModel.model_validate(asdict(impact)),
        kpis=kpis,
        assumptions=assumptions,
        provisional_edges=len(fcm_spec.provisional_edges()),
        total_edges=len(fcm_spec.edges),
        warnings=warnings,
    )

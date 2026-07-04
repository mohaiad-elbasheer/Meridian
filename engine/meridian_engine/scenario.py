"""Scenario orchestrator: composes the FCM layer (soft factors) with the network layer.

Flow for e.g. "Suez -80% capacity for 14 days":
1. Clamp `chokepoint_disruption` to the capacity reduction (unless the caller clamps it
   explicitly) plus any extra scenario clamps (e.g. armed_conflict), run FCM to
   convergence -> concept activations -> coupling multipliers.
2. The user-specified capacity reduction is authoritative for the TARGET chokepoint:
   the network layer receives `chokepoint_capacity_multiplier:<target> = 1 - reduction`.
   The FCM's own (untargeted) `chokepoint_capacity_multiplier` is surfaced for
   comparison but not applied on top — applying both would double-count the same
   disruption concept. `port_dwell_factor` does modulate rerouted flows;
   `reroute_cost_factor` is a cost index (no time/volume effect in the network layer).
3. Deterministic given the same inputs (both layers are pure; no randomness in v0).

Every result carries provenance: how many FCM edge weights are provisional and whether
the baseline graph is synthetic seed data.
"""

from __future__ import annotations

from dataclasses import asdict

import networkx as nx
from pydantic import BaseModel, Field

from .fcm import simulate
from .models import Clamp, FCMSpec, SimulationRequest, SimulationResult
from .network import CAPACITY_KEY, NetworkImpact, apply_scenario

DISRUPTION_CONCEPT = "chokepoint_disruption"


class ScenarioSpec(BaseModel):
    name: str = ""
    target_chokepoint_id: str
    capacity_reduction: float = Field(..., ge=0.0, le=1.0, description="0.8 = -80% capacity")
    duration_days: int = Field(..., ge=1, le=365)
    fcm_clamps: list[Clamp] = []
    max_steps: int = Field(100, ge=1, le=10_000)
    epsilon: float = Field(1e-4, gt=0)


class NetworkImpactModel(BaseModel):
    rerouted_tons: float
    delayed_tons: float
    avg_added_days: float
    country_exposure: dict[str, float]
    chokepoints: list[dict]


class ScenarioResult(BaseModel):
    scenario: ScenarioSpec
    fcm: SimulationResult
    network_multipliers: dict[str, float]  # as applied to the network layer
    impact: NetworkImpactModel
    provisional_edges: int
    total_edges: int
    warnings: list[str]


def run_scenario(fcm_spec: FCMSpec, graph: nx.DiGraph, scenario: ScenarioSpec) -> ScenarioResult:
    node = graph.nodes.get(scenario.target_chokepoint_id)
    if node is None or node.get("type") != "chokepoint":
        raise ValueError(f"Unknown chokepoint: {scenario.target_chokepoint_id}")

    clamps = list(scenario.fcm_clamps)
    if not any(c.concept_id == DISRUPTION_CONCEPT for c in clamps):
        clamps.append(Clamp(concept_id=DISRUPTION_CONCEPT, value=scenario.capacity_reduction))
    fcm_result = simulate(fcm_spec, SimulationRequest(
        clamps=clamps, max_steps=scenario.max_steps, epsilon=scenario.epsilon))

    applied = {
        f"{CAPACITY_KEY}:{scenario.target_chokepoint_id}": 1.0 - scenario.capacity_reduction,
    }
    for key in ("port_dwell_factor", "reroute_cost_factor"):
        if key in fcm_result.network_multipliers:
            applied[key] = fcm_result.network_multipliers[key]

    impact: NetworkImpact = apply_scenario(graph, applied, scenario.duration_days)

    warnings = []
    if fcm_spec.provisional_edges():
        warnings.append(
            f"{len(fcm_spec.provisional_edges())}/{len(fcm_spec.edges)} FCM edge weights are "
            "provisional (citation unassigned) — treat soft-factor outputs as indicative")
    if graph.graph.get("synthetic"):
        warnings.append(
            f"baselines: {graph.graph.get('source', 'unknown')} — synthetic development seed, "
            "not PortWatch data")

    return ScenarioResult(
        scenario=scenario,
        fcm=fcm_result,
        network_multipliers=applied,
        impact=NetworkImpactModel.model_validate(asdict(impact)),
        provisional_edges=len(fcm_spec.provisional_edges()),
        total_edges=len(fcm_spec.edges),
        warnings=warnings,
    )

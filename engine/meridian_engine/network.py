"""Quantitative trade network layer (Layer 1). SKELETON — implement in Phase P1.

Contract (do not change without owner approval, see CLAUDE.md §2):

- Directed graph (networkx.DiGraph):
    nodes: {"type": "chokepoint" | "port" | "country", ...attrs}
    chokepoint attrs: baseline_daily_calls, baseline_daily_tons (from PortWatch history)
    edges: flow dependencies with attrs: share (fraction of target's imports via source),
           alt_route (optional alternative path id), added_days (rerouting penalty)

- apply_scenario(graph, multipliers, duration_days) -> NetworkImpact
    `multipliers` comes from FCM SimulationResult.network_multipliers, e.g.
    {"chokepoint_capacity_reduction": 0.72, "reroute_cost_factor": 2.1, ...}
    Propagation: reduce chokepoint capacity -> divert flow to alt routes up to their
    slack -> residual becomes delayed/lost volume -> country exposure via import shares.

- Outputs must be in real units (calls/day, metric tons, days added, % import exposure).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx


@dataclass
class NetworkImpact:
    rerouted_tons: float = 0.0
    delayed_tons: float = 0.0
    avg_added_days: float = 0.0
    country_exposure: dict[str, float] = field(default_factory=dict)  # ISO3 -> % imports at risk


def build_graph_from_baselines(chokepoints: list[dict], ports: list[dict]) -> nx.DiGraph:
    raise NotImplementedError("P1: build from PortWatch baselines in TimescaleDB")


def apply_scenario(graph: nx.DiGraph, multipliers: dict[str, float], duration_days: int) -> NetworkImpact:
    raise NotImplementedError("P1: capacity-reduction propagation with rerouting")

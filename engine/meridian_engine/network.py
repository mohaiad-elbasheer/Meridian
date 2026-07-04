"""Quantitative trade network layer (Layer 1).

Contract (do not change without owner approval, see CLAUDE.md §2):

- Directed graph (networkx.DiGraph):
    nodes: {"type": "chokepoint" | "port" | "country", ...attrs}
    chokepoint attrs: baseline_daily_calls, baseline_daily_tons (from PortWatch history),
                      capacity_daily_tons (baseline * (1 + headroom))
    edges: kind="import_share" (share = fraction of target country's seaborne imports
           transiting the source chokepoint) or kind="alt_route" (added_days = rerouting
           distance/time penalty toward the alternative chokepoint)

- apply_scenario(graph, multipliers, duration_days) -> NetworkImpact
    Capacity multipliers are per-chokepoint: "chokepoint_capacity_multiplier:<node_id>".
    A bare (untargeted) "chokepoint_capacity_multiplier" from the FCM couplings is NOT
    applied here — resolving *which* chokepoint it targets is the scenario
    orchestrator's job (see scenario.py); applying it globally would double-count.
    "port_dwell_factor" (>1) adds congestion dwell on top of rerouting added_days.
    Propagation: reduce chokepoint capacity -> divert flow to alt routes up to their
    slack (cheapest added_days first) -> residual becomes delayed volume -> country
    exposure via import shares.

- Outputs are in real units (metric tons, days added, % of imports at risk).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

# Baseline port dwell in days; the FCM port_dwell_factor scales this on rerouted flows.
# Provisional modeling constant — revisit when PortWatch dwell statistics are ingested.
BASELINE_PORT_DWELL_DAYS = 1.5

CAPACITY_KEY = "chokepoint_capacity_multiplier"


@dataclass
class NetworkImpact:
    rerouted_tons: float = 0.0
    delayed_tons: float = 0.0
    avg_added_days: float = 0.0
    country_exposure: dict[str, float] = field(default_factory=dict)  # ISO3 -> % imports at risk
    chokepoints: list[dict[str, Any]] = field(default_factory=list)   # per-chokepoint detail


def build_graph_from_baselines(chokepoints: list[dict], ports: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    for cp in chokepoints:
        baseline_tons = float(cp["baseline_daily_tons"])
        headroom = float(cp.get("headroom", 0.25))
        g.add_node(
            cp["id"], type="chokepoint", label=cp.get("label", cp["id"]),
            lat=cp.get("lat"), lon=cp.get("lon"),
            baseline_daily_calls=float(cp["baseline_daily_calls"]),
            baseline_daily_tons=baseline_tons,
            capacity_daily_tons=baseline_tons * (1.0 + headroom),
        )
    for cp in chokepoints:
        for alt in cp.get("alt_routes", []):
            if alt["via"] not in g:
                raise ValueError(f"{cp['id']}: alt route via unknown chokepoint {alt['via']}")
            g.add_edge(cp["id"], alt["via"], kind="alt_route",
                       added_days=float(alt["added_days"]))
        for dep in cp.get("import_dependencies", []):
            iso3 = dep["country"]
            if iso3 not in g:
                g.add_node(iso3, type="country", label=dep.get("label", iso3))
            g.add_edge(cp["id"], iso3, kind="import_share", share=float(dep["share"]))
    for p in ports:
        g.add_node(
            p["id"], type="port", label=p.get("label", p["id"]),
            lat=p.get("lat"), lon=p.get("lon"),
            baseline_daily_calls=float(p["baseline_daily_calls"]),
            baseline_daily_tons=float(p.get("baseline_daily_tons", 0.0)),
        )
    return g


def _capacity_multiplier(multipliers: dict[str, float], node_id: str) -> float:
    m = float(multipliers.get(f"{CAPACITY_KEY}:{node_id}", 1.0))
    if not 0.0 <= m <= 1.0:
        raise ValueError(f"capacity multiplier for {node_id} out of [0,1]: {m}")
    return m


def apply_scenario(graph: nx.DiGraph, multipliers: dict[str, float],
                   duration_days: int) -> NetworkImpact:
    if duration_days < 1:
        raise ValueError("duration_days must be >= 1")
    dwell_factor = float(multipliers.get("port_dwell_factor", 1.0))
    dwell_added = max(0.0, dwell_factor - 1.0) * BASELINE_PORT_DWELL_DAYS

    impact = NetworkImpact()
    rerouted_day_tons = 0.0  # ton-days numerator for avg_added_days
    for node, data in graph.nodes(data=True):
        if data.get("type") != "chokepoint":
            continue
        m = _capacity_multiplier(multipliers, node)
        if m >= 1.0:
            continue
        blocked_daily = data["baseline_daily_tons"] * (1.0 - m)
        remaining = blocked_daily
        reroutes: list[dict[str, Any]] = []
        alts = sorted(
            ((v, e) for _, v, e in graph.out_edges(node, data=True)
             if e.get("kind") == "alt_route"),
            key=lambda ve: ve[1]["added_days"],
        )
        for alt_id, edge in alts:
            if remaining <= 0:
                break
            alt = graph.nodes[alt_id]
            alt_available = alt["capacity_daily_tons"] * _capacity_multiplier(multipliers, alt_id)
            slack_daily = max(0.0, alt_available - alt["baseline_daily_tons"])
            take = min(remaining, slack_daily)
            if take > 0:
                added = edge["added_days"] + dwell_added
                rerouted_day_tons += take * duration_days * added
                reroutes.append({"via": alt_id, "daily_tons": take, "added_days": added})
                remaining -= take
        rerouted_daily = blocked_daily - remaining
        for _, country, edge in graph.out_edges(node, data=True):
            if edge.get("kind") != "import_share":
                continue
            exposure = edge["share"] * (1.0 - m) * 100.0
            impact.country_exposure[country] = min(
                100.0, impact.country_exposure.get(country, 0.0) + exposure
            )
        impact.rerouted_tons += rerouted_daily * duration_days
        impact.delayed_tons += remaining * duration_days
        impact.chokepoints.append({
            "chokepoint_id": node,
            "capacity_multiplier": m,
            "baseline_daily_tons": data["baseline_daily_tons"],
            "blocked_tons": blocked_daily * duration_days,
            "rerouted_tons": rerouted_daily * duration_days,
            "delayed_tons": remaining * duration_days,
            "reroutes": reroutes,
        })
    if impact.rerouted_tons > 0:
        impact.avg_added_days = rerouted_day_tons / impact.rerouted_tons
    impact.country_exposure = dict(sorted(
        impact.country_exposure.items(), key=lambda kv: kv[1], reverse=True
    ))
    return impact

"""Loader for the bundled SYNTHETIC baseline seed (demo/tests only — not PortWatch data).

The graph it builds carries graph attrs `source` and `synthetic` so every consumer can
(and must) surface the data-quality flag. Real baselines come from PortWatch history in
TimescaleDB once P0 ingestion is running; the seed exists so the engine and prototype UI
work with zero DB/network dependencies (CLAUDE.md §7).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import networkx as nx

from .network import build_graph_from_baselines


def load_synthetic_seed() -> dict[str, Any]:
    raw = resources.files("meridian_engine").joinpath("data/synthetic_seed_v0.json").read_text()
    return json.loads(raw)


def build_synthetic_graph() -> nx.DiGraph:
    seed = load_synthetic_seed()
    g = build_graph_from_baselines(seed["chokepoints"], seed["ports"])
    g.graph["source"] = seed["name"]
    g.graph["synthetic"] = seed["synthetic"]
    return g

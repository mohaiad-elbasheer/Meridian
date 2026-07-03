"""Pydantic v2 models for the Meridian two-layer analysis engine.

Design contract (see CLAUDE.md §2):
- FCM layer: qualitative concepts with literature-provenanced weighted edges.
- Coupling layer: maps FCM concept activations to quantitative network multipliers.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Provenance(BaseModel):
    """Every FCM edge weight must be traceable. Empty citation => provisional."""

    citation: str = ""  # e.g. "Doe & Smith (2023), Transp. Res. E, Table 4"
    source_type: Literal["literature", "expert", "learned", "unassigned"] = "unassigned"
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    provisional: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def _flag_provisional(self) -> "Provenance":
        if not self.citation:
            object.__setattr__(self, "provisional", True)
        return self


class ConceptLayer(str, Enum):
    HAZARD = "hazard"          # e.g. armed conflict intensity, extreme weather
    LOGISTICS = "logistics"    # e.g. chokepoint disruption, port congestion
    ECONOMIC = "economic"      # e.g. freight rates, insurance premium
    OUTCOME = "outcome"        # e.g. lead time, supply availability


class Concept(BaseModel):
    id: str
    label: str
    description: str = ""
    layer: ConceptLayer
    initial_activation: float = Field(0.0, ge=-1.0, le=1.0)


class Edge(BaseModel):
    source: str
    target: str
    weight: float = Field(..., ge=-1.0, le=1.0)
    provenance: Provenance = Field(default_factory=Provenance)


class Coupling(BaseModel):
    """Maps an FCM concept's activation to a network-layer parameter multiplier.

    multiplier = 1 + gain * activation, clamped to [min_multiplier, max_multiplier].
    Example: concept 'war_risk_premium' -> parameter 'reroute_cost_factor'.
    """

    concept_id: str
    network_parameter: str
    gain: float = 1.0
    min_multiplier: float = Field(0.0, ge=0.0)
    max_multiplier: float = 5.0


class Squashing(str, Enum):
    SIGMOID = "sigmoid"   # 1/(1+exp(-lambda*x)), range (0,1)
    TANH = "tanh"         # tanh(lambda*x), range (-1,1)


class FCMSpec(BaseModel):
    name: str
    version: str = "0.1.0"
    concepts: list[Concept]
    edges: list[Edge]
    couplings: list[Coupling] = []
    squashing: Squashing = Squashing.SIGMOID
    lam: float = Field(1.0, gt=0, description="Steepness lambda of squashing function")

    @model_validator(mode="after")
    def _validate_refs(self) -> "FCMSpec":
        ids = {c.id for c in self.concepts}
        if len(ids) != len(self.concepts):
            raise ValueError("Duplicate concept ids")
        for e in self.edges:
            if e.source not in ids or e.target not in ids:
                raise ValueError(f"Edge references unknown concept: {e.source}->{e.target}")
            if e.source == e.target:
                raise ValueError(f"Self-loop not allowed: {e.source}")
        for c in self.couplings:
            if c.concept_id not in ids:
                raise ValueError(f"Coupling references unknown concept: {c.concept_id}")
        return self

    def provisional_edges(self) -> list[Edge]:
        return [e for e in self.edges if e.provenance.provisional]


class Clamp(BaseModel):
    """Scenario intervention: hold a concept at a value during simulation."""

    concept_id: str
    value: float = Field(..., ge=-1.0, le=1.0)
    from_step: int = 0
    to_step: int | None = None  # None = held until the end


class SimulationRequest(BaseModel):
    clamps: list[Clamp] = []
    max_steps: int = Field(100, ge=1, le=10_000)
    epsilon: float = Field(1e-4, gt=0, description="Convergence threshold (L-inf)")


class SimulationResult(BaseModel):
    converged: bool
    steps: int
    final_activations: dict[str, float]
    trajectories: dict[str, list[float]]
    network_multipliers: dict[str, float]
    provisional_edges_used: int

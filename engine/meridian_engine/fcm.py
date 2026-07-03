"""FCM inference core.

Implements modified-Kosko iterative activation with clamping (scenario interventions),
convergence detection, and FCM->network coupling evaluation.

    A(t+1) = f( A(t) + A(t) @ W )

where W[i, j] is the weight of edge concept_i -> concept_j and f is the squashing
function. Pure, deterministic, no I/O. Extend rather than rewrite (tests depend on it).
"""

from __future__ import annotations

import numpy as np

from .models import Clamp, FCMSpec, SimulationRequest, SimulationResult, Squashing


def build_weight_matrix(spec: FCMSpec) -> tuple[np.ndarray, list[str]]:
    ids = [c.id for c in spec.concepts]
    index = {cid: i for i, cid in enumerate(ids)}
    w = np.zeros((len(ids), len(ids)), dtype=float)
    for e in spec.edges:
        w[index[e.source], index[e.target]] = e.weight
    return w, ids


def _squash(x: np.ndarray, kind: Squashing, lam: float) -> np.ndarray:
    if kind is Squashing.SIGMOID:
        return 1.0 / (1.0 + np.exp(-lam * x))
    return np.tanh(lam * x)


def _apply_clamps(a: np.ndarray, clamps: list[Clamp], index: dict[str, int], step: int) -> None:
    for c in clamps:
        active = step >= c.from_step and (c.to_step is None or step <= c.to_step)
        if active:
            a[index[c.concept_id]] = c.value


def simulate(spec: FCMSpec, request: SimulationRequest) -> SimulationResult:
    w, ids = build_weight_matrix(spec)
    index = {cid: i for i, cid in enumerate(ids)}

    for c in request.clamps:
        if c.concept_id not in index:
            raise ValueError(f"Clamp references unknown concept: {c.concept_id}")

    a = np.array([c.initial_activation for c in spec.concepts], dtype=float)
    _apply_clamps(a, request.clamps, index, step=0)
    trajectories: list[np.ndarray] = [a.copy()]

    converged = False
    step = 0
    for step in range(1, request.max_steps + 1):
        a_next = _squash(a + a @ w, spec.squashing, spec.lam)
        _apply_clamps(a_next, request.clamps, index, step)
        trajectories.append(a_next.copy())
        if np.max(np.abs(a_next - a)) < request.epsilon:
            converged = True
            a = a_next
            break
        a = a_next

    traj = np.stack(trajectories)
    final = {cid: float(a[i]) for cid, i in index.items()}

    multipliers: dict[str, float] = {}
    for cpl in spec.couplings:
        m = 1.0 + cpl.gain * final[cpl.concept_id]
        multipliers[cpl.network_parameter] = float(
            np.clip(m, cpl.min_multiplier, cpl.max_multiplier)
        )

    return SimulationResult(
        converged=converged,
        steps=step,
        final_activations=final,
        trajectories={cid: traj[:, i].tolist() for cid, i in index.items()},
        network_multipliers=multipliers,
        provisional_edges_used=len(spec.provisional_edges()),
    )

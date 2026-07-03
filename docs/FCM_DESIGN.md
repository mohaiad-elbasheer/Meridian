# FCM Layer Design

- Spec: `engine/meridian_engine/maps/macro_v0.json` (12 concepts, 4 layers:
  hazard -> logistics -> economic -> outcome).
- Inference: modified Kosko, A(t+1)=f(A(t)+A(t)W), sigmoid default, clamp-based
  interventions with time windows. Implemented + tested in `engine/`.
- Weights: v0 = literature-elicited by the owner (IMAACA-style protocol). All current
  weights are placeholders flagged `provisional: true`. The UI must visibly badge results
  computed with provisional edges (`SimulationResult.provisional_edges_used`).
- Couplings: FCM activation -> network multiplier (1 + gain*a, clamped). Current:
  chokepoint_capacity_reduction, reroute_cost_factor, port_dwell_factor.
- Research byproduct: provenance-complete weight table exports directly to a paper table.

## Squashing decision (verified 2026-07)
`macro_v0` uses **tanh**, not sigmoid. Empirical check during scaffolding: sigmoid
modified-Kosko drifts to a saturated fixed point (baseline ~0.8) that dampens shock
deltas to near zero downstream; tanh gives a zero-neutral baseline and strong,
sign-correct propagation (conflict clamp -> supply_availability ~ -0.9). Report scenario
results as deltas vs. the model's own baseline run, never as raw activations only.
Capacity-type couplings use a negative gain on a capacity *multiplier*
(e.g., chokepoint_capacity_multiplier = 1 - 0.9*a, clipped to [0.05, 1]).

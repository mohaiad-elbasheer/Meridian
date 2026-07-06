# Architecture Decisions (ADR-style, newest first)

## ADR-006: Scenario engine v2 — vessel classes, cause-driven soft factors, KPI layer (2026-07)
Vessel classes (container/dry-bulk/general-cargo/ro-ro/tanker — PortWatch's own
disaggregation) become first-class: per-class reductions, curated class mixes in the
seed, per-class KPI outputs. The scenario's `cause` (conflict/hazard/accident/policy)
derives FCM clamps automatically via a documented provisional mapping
(clamp = base + gain × effective reduction); expert clamps override per concept and
the derivation is always reported (`auto_clamps`). KPI layer adds cargo-value-at-delay
under explicit, overridable USD/ton assumptions — assumptions are echoed in every
result, never silent. Network propagation is unchanged (totals); class outputs are
proportional splits of blocked volume. UI de-jargonizes FCM as "Soft factors /
market & risk conditions"; the causal map stays as the expert view. Live signals
(geo_events near chokepoints) suggest clamps but are never auto-applied.

## ADR-005: First running prototype on a labeled synthetic seed (2026-07)
To close the full loop (engine -> API -> map cockpit) before live PortWatch data is
verified, the engine bundles `data/synthetic_seed_v0.json`: plausible-magnitude,
explicitly `synthetic: true` baselines for 13 chokepoints + 16 ports. Every layer
propagates the flag — graph attrs, API `/network/baseline.synthetic`, scenario-result
warnings, and a persistent "SYNTHETIC SEED" chip in the UI header (honesty rule,
ADR-001). Swapping to real baselines = replacing the graph builder input with
PortWatch aggregates from TimescaleDB; no interface changes.
Network propagation model (v0): per-chokepoint capacity multiplier -> blocked daily
tons -> divert to alt routes by cheapest added_days up to slack
(capacity = baseline * (1 + headroom)) -> residual is delayed volume -> country
exposure = import share x capacity cut. The FCM's untargeted capacity multiplier is
deliberately NOT stacked on the user's explicit reduction (double-counting);
`port_dwell_factor` adds dwell days on rerouted flows, `reroute_cost_factor` is a
cost index only. Web map renders bundled world-atlas geometry inline (no external
tile/glyph servers), MapLibre + deck.gl overlay, IBM Plex, one accent.


## ADR-004: P0 ingestion — tolerant parsers, idempotent upserts, provisional GDELT geo-tagging (2026-07)
PortWatch ArcGIS field names can drift between releases, so parsers resolve columns via
candidate-name lists and always store the full attribute dict in `raw` JSONB — schema
drift degrades to NULL columns (reprocessable) instead of failed runs.
`python -m meridian_ingest.verify_endpoints` prints the live layer schema to catch drift.
All writes are `ON CONFLICT DO NOTHING` on natural keys (chokepoint_id/port_id + date;
event id), making every ingestor safe to re-run. GDELT events are aggregated to one row
per (chokepoint, 15-min window) — counts and tone only, no person-level data — using a
*provisional* seed list of chokepoint coordinates (`chokepoints_seed.json`) until the
PortWatch chokepoint master list with authoritative geometry is ingested.
Note: the pinned FeatureServer URLs in `.env.example` could not be live-verified in the
development sandbox (egress policy blocked *.arcgis.com); verification is a required
first-run step, not optional.

## ADR-003: OCI Always-Free Ampere A1 + Docker Compose (2026-07)
Single-VM Compose over Kubernetes for the prototype. aarch64 => all images must be arm64.

## ADR-002: Two-layer engine — trade network (quantitative) + FCM (qualitative) (2026-07)
FCM alone is not credible to analysts (dimensionless outputs); network alone loses
intuitive scenario composition. FCM modulates network parameters via explicit couplings.
FCM weights are literature-defined with mandatory provenance (research byproduct).

## ADR-001: Honest positioning (2026-07)
Not a "digital twin"; a monitoring & stress-testing cockpit. "Near-real-time signals,
daily-resolution flows." Anchor dataset: IMF PortWatch (daily data, weekly refresh).

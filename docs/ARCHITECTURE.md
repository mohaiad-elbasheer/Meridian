# Architecture Decisions (ADR-style, newest first)

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

# Architecture Decisions (ADR-style, newest first)

## ADR-003: OCI Always-Free Ampere A1 + Docker Compose (2026-07)
Single-VM Compose over Kubernetes for the prototype. aarch64 => all images must be arm64.

## ADR-002: Two-layer engine — trade network (quantitative) + FCM (qualitative) (2026-07)
FCM alone is not credible to analysts (dimensionless outputs); network alone loses
intuitive scenario composition. FCM modulates network parameters via explicit couplings.
FCM weights are literature-defined with mandatory provenance (research byproduct).

## ADR-001: Honest positioning (2026-07)
Not a "digital twin"; a monitoring & stress-testing cockpit. "Near-real-time signals,
daily-resolution flows." Anchor dataset: IMF PortWatch (daily data, weekly refresh).

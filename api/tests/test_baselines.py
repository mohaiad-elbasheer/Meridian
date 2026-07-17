import os
from datetime import date

import pytest

from meridian_api.baselines import (
    DbBaseline, _normalize, build_graph, fetch_db_baselines, merge_baselines, sources_status,
)

TEMPLATE = [
    {"id": "suez_canal", "label": "Suez Canal", "baseline_daily_calls": 50,
     "baseline_daily_tons": 4_500_000, "alt_routes": [], "import_dependencies": []},
    {"id": "strait_of_hormuz", "label": "Strait of Hormuz", "baseline_daily_calls": 80,
     "baseline_daily_tons": 5_500_000, "alt_routes": [], "import_dependencies": []},
]


def test_normalize_matches_name_variants():
    assert _normalize("Suez Canal") == _normalize("suez canal") == _normalize("SUEZ-CANAL")


def test_merge_overlays_db_volumes_and_reports_unmatched():
    rows = [DbBaseline("Suez Canal", calls=48.5, tons=4_812_345.5, n_days=28,
                       latest=date(2026, 7, 1))]
    merged, unmatched, matched = merge_baselines(TEMPLATE, rows)
    assert matched == 1
    suez = next(m for m in merged if m["id"] == "suez_canal")
    assert suez["baseline_daily_tons"] == pytest.approx(4_812_345.5)
    assert suez["baseline_daily_calls"] == pytest.approx(48.5)
    assert suez["baseline_source"] == "portwatch_daily"
    hormuz = next(m for m in merged if m["id"] == "strait_of_hormuz")
    assert hormuz["baseline_daily_tons"] == 5_500_000  # curated value retained
    assert hormuz["baseline_source"] == "synthetic_seed"
    assert unmatched == ["Strait of Hormuz"]
    assert TEMPLATE[0]["baseline_daily_tons"] == 4_500_000  # template not mutated


def test_merge_ignores_rows_without_tons():
    rows = [DbBaseline("Suez Canal", calls=48.5, tons=None, n_days=3, latest=date(2026, 7, 1))]
    _, unmatched, matched = merge_baselines(TEMPLATE, rows)
    assert matched == 0 and "Suez Canal" in unmatched


def test_build_graph_falls_back_to_seed_when_db_unreachable():
    g = build_graph("postgresql://x:x@127.0.0.1:9/x?connect_timeout=1", 28)
    assert g.graph["synthetic"] is True
    assert g.graph["source"] == "synthetic_seed_v0"
    assert g.graph["provenance"] == "synthetic"
    assert g.graph["coverage"]["chokepoints_observed"] == 0


# ---- integration tests against a live DB (skipped unless TEST_DATABASE_URL is set) ----

DSN = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


@needs_db
def test_fetch_db_baselines_live():
    import psycopg

    with psycopg.connect(DSN) as conn:
        rows = fetch_db_baselines(conn, "chokepoint_daily", trailing_days=3650)
    names = {r.portname for r in rows}
    assert "Suez Canal" in names  # fixture rows ingested by the P0 pipeline tests


@needs_db
def test_build_graph_live_uses_portwatch_source():
    g = build_graph(DSN, trailing_days=3650)
    assert g.graph["synthetic"] is False
    assert g.graph["source"].startswith("portwatch_daily")
    assert any("curated" in w for w in g.graph["data_warnings"])
    # fixture DB covers a subset of curated chokepoints -> mixed, never "observed"
    cov = g.graph["coverage"]
    assert 0 < cov["chokepoints_observed"] <= cov["chokepoints_total"]
    if cov["chokepoints_observed"] < cov["chokepoints_total"]:
        assert g.graph["provenance"] == "mixed"
        assert any(w.startswith("MIXED baselines") for w in g.graph["data_warnings"])
    else:
        assert g.graph["provenance"] == "observed"


@needs_db
def test_sources_status_live():
    body = sources_status(DSN)
    assert body["database"]["reachable"] is True
    assert body["tables"]["chokepoint_daily"]["rows"] >= 3

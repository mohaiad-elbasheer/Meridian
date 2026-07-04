import pytest

from meridian_engine import apply_scenario, build_graph_from_baselines, build_synthetic_graph
from meridian_engine.network import CAPACITY_KEY, BASELINE_PORT_DWELL_DAYS

CHOKEPOINTS = [
    {"id": "main_strait", "baseline_daily_calls": 50, "baseline_daily_tons": 1_000_000,
     "headroom": 0.1,
     "alt_routes": [{"via": "alt_near", "added_days": 2.0}, {"via": "alt_far", "added_days": 10.0}],
     "import_dependencies": [{"country": "AAA", "share": 0.5}, {"country": "BBB", "share": 0.2}]},
    {"id": "alt_near", "baseline_daily_calls": 20, "baseline_daily_tons": 400_000,
     "headroom": 0.5, "alt_routes": [], "import_dependencies": []},
    {"id": "alt_far", "baseline_daily_calls": 10, "baseline_daily_tons": 100_000,
     "headroom": 1.0, "alt_routes": [], "import_dependencies": []},
]


def graph():
    return build_graph_from_baselines(CHOKEPOINTS, ports=[])


def test_build_graph_nodes_and_edges():
    g = graph()
    assert g.nodes["main_strait"]["type"] == "chokepoint"
    assert g.nodes["main_strait"]["capacity_daily_tons"] == pytest.approx(1_100_000)
    assert g.nodes["AAA"]["type"] == "country"
    assert g.edges["main_strait", "alt_near"]["kind"] == "alt_route"
    assert g.edges["main_strait", "AAA"]["share"] == 0.5


def test_build_graph_rejects_unknown_alt():
    bad = [dict(CHOKEPOINTS[0], alt_routes=[{"via": "nowhere", "added_days": 1}])]
    with pytest.raises(ValueError, match="unknown chokepoint"):
        build_graph_from_baselines(bad, ports=[])


def test_full_block_conserves_volume_and_fills_cheapest_alt_first():
    # -100% on main: blocked 1,000,000/day. alt_near slack = 600,000-400,000... no:
    # capacity 400,000*1.5=600,000, slack 200,000. alt_far slack = 200,000-100,000=100,000.
    impact = apply_scenario(graph(), {f"{CAPACITY_KEY}:main_strait": 0.0}, duration_days=10)
    assert impact.rerouted_tons == pytest.approx(300_000 * 10)
    assert impact.delayed_tons == pytest.approx(700_000 * 10)
    cp = impact.chokepoints[0]
    assert cp["blocked_tons"] == pytest.approx(cp["rerouted_tons"] + cp["delayed_tons"])
    assert cp["reroutes"][0]["via"] == "alt_near"  # cheapest added_days first
    # weighted added days: (200k*2 + 100k*10) / 300k = 4.6667
    assert impact.avg_added_days == pytest.approx((200_000 * 2 + 100_000 * 10) / 300_000)


def test_partial_reduction_and_country_exposure():
    impact = apply_scenario(graph(), {f"{CAPACITY_KEY}:main_strait": 0.6}, duration_days=14)
    # blocked 400,000/day, fits entirely in alt_near slack (200k) + alt_far (100k)? No: 300k
    assert impact.rerouted_tons == pytest.approx(300_000 * 14)
    assert impact.delayed_tons == pytest.approx(100_000 * 14)
    assert impact.country_exposure["AAA"] == pytest.approx(0.5 * 0.4 * 100)
    assert impact.country_exposure["BBB"] == pytest.approx(0.2 * 0.4 * 100)


def test_dwell_factor_adds_days():
    base = apply_scenario(graph(), {f"{CAPACITY_KEY}:main_strait": 0.6}, 14)
    congested = apply_scenario(
        graph(), {f"{CAPACITY_KEY}:main_strait": 0.6, "port_dwell_factor": 2.0}, 14)
    assert congested.avg_added_days == pytest.approx(
        base.avg_added_days + BASELINE_PORT_DWELL_DAYS)


def test_disrupted_alt_route_reduces_slack():
    mults = {f"{CAPACITY_KEY}:main_strait": 0.0, f"{CAPACITY_KEY}:alt_near": 0.5}
    impact = apply_scenario(graph(), mults, 1)
    # alt_near available = 600,000*0.5 = 300,000 < its own baseline -> zero slack,
    # and alt_near itself is disrupted too (its baseline 400k at 0.5 => 200k blocked, no alts)
    main = next(c for c in impact.chokepoints if c["chokepoint_id"] == "main_strait")
    assert main["reroutes"][0]["via"] == "alt_far"
    assert main["rerouted_tons"] == pytest.approx(100_000)


def test_untargeted_capacity_multiplier_is_not_applied():
    impact = apply_scenario(graph(), {CAPACITY_KEY: 0.2}, 7)  # bare key: orchestrator's job
    assert impact.rerouted_tons == 0 and impact.delayed_tons == 0 and not impact.chokepoints


def test_synthetic_graph_builds_and_is_flagged():
    g = build_synthetic_graph()
    assert g.graph["synthetic"] is True
    types = {d["type"] for _, d in g.nodes(data=True)}
    assert types == {"chokepoint", "port", "country"}
    assert g.nodes["suez_canal"]["baseline_daily_tons"] > 0

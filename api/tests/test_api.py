import pytest
from fastapi.testclient import TestClient

from meridian_api import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def synthetic_fallback(monkeypatch):
    """Point the API at a dead DB so tests exercise the deterministic synthetic path."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:9/x?connect_timeout=1")
    main._settings.cache_clear()
    main._graph_cache = None
    yield
    main._settings.cache_clear()
    main._graph_cache = None


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_network_baseline_flags_synthetic():
    body = client.get("/network/baseline?refresh=true").json()
    assert body["synthetic"] is True
    assert body["provenance"] == "synthetic"
    assert body["coverage"]["chokepoints_observed"] == 0
    assert body["coverage"]["chokepoints_total"] > 0
    assert all(n["baseline_source"] == "synthetic_seed"
               for n in body["nodes"] if n["type"] == "chokepoint")
    ids = {n["id"] for n in body["nodes"]}
    assert "suez_canal" in ids and "port_rotterdam" in ids
    kinds = {e["kind"] for e in body["edges"]}
    assert kinds == {"alt_route", "import_share"}


def test_scenario_simulate_suez():
    client.get("/network/baseline?refresh=true")
    r = client.post("/scenario/simulate", json={
        "target_chokepoint_id": "suez_canal",
        "capacity_reduction": 0.8,
        "duration_days": 14,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["impact"]["rerouted_tons"] > 0
    assert body["impact"]["avg_added_days"] >= 9.5
    assert any("synthetic" in w for w in body["warnings"])


def test_scenario_simulate_unknown_chokepoint_is_422():
    client.get("/network/baseline?refresh=true")
    r = client.post("/scenario/simulate", json={
        "target_chokepoint_id": "atlantis",
        "capacity_reduction": 0.5,
        "duration_days": 7,
    })
    assert r.status_code == 422


def test_fcm_map_served():
    body = client.get("/fcm/map").json()
    assert body["name"] == "macro_v0"
    assert len(body["concepts"]) == 12


def test_sources_status_degrades_gracefully():
    body = client.get("/sources/status").json()
    assert body["database"]["reachable"] is False
    assert "error" in body["database"]

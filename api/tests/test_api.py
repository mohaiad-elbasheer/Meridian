from fastapi.testclient import TestClient

from meridian_api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_network_baseline_flags_synthetic():
    body = client.get("/network/baseline").json()
    assert body["synthetic"] is True
    ids = {n["id"] for n in body["nodes"]}
    assert "suez_canal" in ids and "port_rotterdam" in ids
    kinds = {e["kind"] for e in body["edges"]}
    assert kinds == {"alt_route", "import_share"}


def test_scenario_simulate_suez():
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

import os

import pytest
from fastapi.testclient import TestClient

from meridian_api import main

client = TestClient(main.app)

SPEC = {"target_chokepoint_id": "suez_canal", "capacity_reduction": 0.8,
        "duration_days": 14, "fcm_clamps": []}

DSN = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


def test_degrades_to_503_without_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:9/x?connect_timeout=1")
    assert client.get("/scenarios").status_code == 503


def test_invalid_spec_rejected_422(monkeypatch):
    if DSN:
        monkeypatch.setenv("DATABASE_URL", DSN)
    r = client.post("/scenarios", json={"name": "bad", "spec": {"capacity_reduction": 2.0}})
    assert r.status_code == 422


@needs_db
def test_crud_roundtrip(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)

    created = client.post("/scenarios", json={"name": "Suez -80% / 14d", "spec": SPEC})
    assert created.status_code == 201
    sid = created.json()["id"]
    assert created.json()["spec"]["target_chokepoint_id"] == "suez_canal"

    assert any(s["id"] == sid for s in client.get("/scenarios").json())
    assert client.get(f"/scenarios/{sid}").json()["name"] == "Suez -80% / 14d"

    updated = client.put(f"/scenarios/{sid}", json={
        "name": "Suez -60% / 7d", "spec": {**SPEC, "capacity_reduction": 0.6,
                                           "duration_days": 7}})
    assert updated.status_code == 200
    assert updated.json()["spec"]["duration_days"] == 7

    assert client.delete(f"/scenarios/{sid}").status_code == 204
    assert client.get(f"/scenarios/{sid}").status_code == 404
    assert client.delete(f"/scenarios/{sid}").status_code == 404

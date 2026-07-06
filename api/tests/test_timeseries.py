import os

import pytest
from fastapi.testclient import TestClient

from meridian_api import main

client = TestClient(main.app)

DSN = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not DSN, reason="TEST_DATABASE_URL not set")


def test_series_degrades_without_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:9/x?connect_timeout=1")
    main._settings.cache_clear()
    main._graph_cache = None
    body = client.get("/timeseries/chokepoints/suez_canal").json()
    assert body["available"] is False and body["points"] == []
    dep = client.get("/trade/dependencies").json()
    assert dep["available"] is False
    main._settings.cache_clear()
    main._graph_cache = None


def test_series_unknown_chokepoint():
    body = client.get("/timeseries/chokepoints/atlantis").json()
    assert body["available"] is False and body["reason"] == "unknown chokepoint"


@needs_db
def test_series_live_matches_by_portname(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    main._settings.cache_clear()
    main._graph_cache = None
    body = client.get("/timeseries/chokepoints/suez_canal?days=730").json()
    assert body["available"] is True
    assert body["label"] == "Suez Canal"
    assert len(body["points"]) >= 2                       # fixture rows
    assert body["points"][0]["date"] < body["points"][-1]["date"]
    assert body["points"][0]["trade_tons"] == pytest.approx(4812345.5)
    main._settings.cache_clear()
    main._graph_cache = None


@needs_db
def test_trade_dependencies_live(monkeypatch):
    import psycopg

    monkeypatch.setenv("DATABASE_URL", DSN)
    main._settings.cache_clear()
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO country_trade (reporter, partner, year, import_usd, raw) VALUES
            ('ITA', 'WLD', 2025, 700e9, '{}'), ('ITA', 'CHN', 2025, 58e9, '{}'),
            ('ITA', 'DEU', 2025, 90e9, '{}')
            ON CONFLICT (reporter, partner, year) DO NOTHING""")
        conn.commit()
    body = client.get("/trade/dependencies").json()
    assert body["available"] is True and body["year"] == 2025
    ita = body["reporters"]["ITA"]
    assert ita["partners"][0]["partner"] == "DEU"          # sorted by value
    assert ita["partners"][0]["share"] == pytest.approx(90e9 / 700e9)
    main._settings.cache_clear()

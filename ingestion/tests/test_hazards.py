from datetime import datetime, timezone

from meridian_ingest import hazards


def test_parse_usgs(usgs_feed):
    rows = hazards.parse_usgs(usgs_feed)
    assert len(rows) == 2
    r = rows[0]
    assert r["id"] == "usgs:us7000abcd"
    assert r["source"] == "usgs"
    assert r["category"] == "earthquake"
    assert r["severity"] == 6.4
    assert (r["lon"], r["lat"]) == (178.1, -24.7)
    assert r["event_time"] == datetime.fromtimestamp(1751500000, tz=timezone.utc)
    assert r["raw"]["properties"]["place"] == "south of the Fiji Islands"


def test_parse_gdacs(gdacs_rss):
    rows = hazards.parse_gdacs(gdacs_rss)
    assert len(rows) == 2
    tc, eq = rows
    assert tc["id"] == "gdacs:TC1001234"
    assert tc["category"] == "TC"
    assert tc["severity"] == 2.0  # orange
    assert (tc["lat"], tc["lon"]) == (13.2, 124.5)
    assert tc["event_time"] == datetime(2026, 7, 2, 6, 0, tzinfo=timezone.utc)
    assert eq["severity"] == 1.0  # green

from datetime import date

import httpx
import pytest
import respx

from meridian_ingest import db, portwatch

CHOKEPOINTS_URL = "https://example.com/arcgis/rest/services/chokepoints/FeatureServer/0/query"


def test_parse_chokepoint(chokepoints_page):
    rows = [portwatch.parse_chokepoint(f) for f in chokepoints_page["features"]]
    assert rows[0] == {
        "chokepoint_id": "chokepoint1",
        "date": date(2025, 6, 26),
        "transit_calls": 52,
        "trade_tons": 4812345.5,
        "vessel_breakdown": {"n_total": 52, "n_cargo": 30, "n_tanker": 22},
        "raw": chokepoints_page["features"][0]["attributes"],
    }
    # nulls stay None; row is still kept (raw preserved for reprocessing)
    assert rows[2]["transit_calls"] is None
    assert rows[2]["trade_tons"] is None
    assert rows[2]["vessel_breakdown"] is None


def test_parse_port(ports_page):
    rows = [portwatch.parse_port(f) for f in ports_page["features"]]
    assert rows[0]["port_id"] == "port1114"
    assert rows[0]["portcalls"] == 61
    assert rows[0]["import_tons"] == 812345.2
    assert rows[0]["export_tons"] == 501234.9
    assert rows[0]["raw"]["ISO3"] == "NLD"
    # feature without an id is dropped, not half-ingested
    assert rows[2] is None


def test_parse_arcgis_date_variants():
    assert portwatch.parse_arcgis_date(1750896000000) == date(2025, 6, 26)
    assert portwatch.parse_arcgis_date("2026-07-01") == date(2026, 7, 1)
    assert portwatch.parse_arcgis_date(None) is None


def test_incremental_where():
    assert portwatch.incremental_where(None) == "1=1"
    assert portwatch.incremental_where(date(2026, 6, 30)) == (
        "date > TIMESTAMP '2026-06-30 23:59:59'"
    )


@respx.mock
def test_iter_features_paginates(chokepoints_page):
    page2 = {"features": [chokepoints_page["features"][2]], "exceededTransferLimit": False}
    route = respx.get(CHOKEPOINTS_URL.rsplit("/query", 1)[0] + "/query")
    route.side_effect = [
        httpx.Response(200, json=chokepoints_page),
        httpx.Response(200, json=page2),
    ]
    with httpx.Client() as client:
        feats = list(portwatch.iter_features(client, CHOKEPOINTS_URL))
    assert len(feats) == 4
    assert route.calls[1].request.url.params["resultOffset"] == "3"


@respx.mock
def test_fetch_page_raises_on_arcgis_error():
    respx.get(CHOKEPOINTS_URL).mock(
        return_value=httpx.Response(200, json={"error": {"code": 400, "message": "bad"}})
    )
    with httpx.Client() as client, pytest.raises(RuntimeError, match="ArcGIS error"):
        # __wrapped__ bypasses tenacity so the test doesn't sit through retries
        portwatch.fetch_page.__wrapped__(client, CHOKEPOINTS_URL, 0)


def test_upsert_sql_is_idempotent():
    for sql in (db.UPSERT_CHOKEPOINT, db.UPSERT_PORT, db.UPSERT_GEO_EVENT):
        assert "ON CONFLICT" in sql and "DO NOTHING" in sql

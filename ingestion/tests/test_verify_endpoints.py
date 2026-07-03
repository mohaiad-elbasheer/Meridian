import httpx
import respx

from meridian_ingest import verify_endpoints

QUERY_URL = "https://example.com/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
LAYER_URL = QUERY_URL.rsplit("/query", 1)[0]

LAYER_META = {
    "name": "Daily_Chokepoints_Data",
    "fields": [{"name": "objectid"}, {"name": "portid"}, {"name": "date"},
               {"name": "n_total"}, {"name": "capacity"}],
}
LATEST = {"features": [{"attributes": {"portid": "chokepoint1", "date": 1750896000000}}]}


@respx.mock
def test_check_ok(capsys):
    respx.get(LAYER_URL).mock(return_value=httpx.Response(200, json=LAYER_META))
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=LATEST))
    with httpx.Client() as client:
        assert verify_endpoints.check(client, "chokepoints", QUERY_URL) is True
    out = capsys.readouterr().out
    assert "[ OK ] chokepoints" in out and "2025-06-26" in out


@respx.mock
def test_check_warns_on_schema_drift(capsys):
    drifted = {"name": "x", "fields": [{"name": "chokepoint_ref"}, {"name": "obs_date"}]}
    respx.get(LAYER_URL).mock(return_value=httpx.Response(200, json=drifted))
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json={"features": []}))
    with httpx.Client() as client:
        assert verify_endpoints.check(client, "chokepoints", QUERY_URL) is True
    assert "[WARN] chokepoints: expected fields missing" in capsys.readouterr().out


@respx.mock
def test_check_fails_on_arcgis_error(capsys):
    err = {"error": {"code": 403, "message": "denied"}}
    respx.get(LAYER_URL).mock(return_value=httpx.Response(200, json=err))
    respx.get(QUERY_URL).mock(return_value=httpx.Response(200, json=err))
    with httpx.Client() as client:
        assert verify_endpoints.check(client, "chokepoints", QUERY_URL) is False
    assert "[FAIL]" in capsys.readouterr().out


def test_check_fails_on_missing_url(capsys):
    with httpx.Client() as client:
        assert verify_endpoints.check(client, "ports", "") is False
    assert "URL not set" in capsys.readouterr().out

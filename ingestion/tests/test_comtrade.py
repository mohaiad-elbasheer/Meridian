from meridian_ingest import db
from meridian_ingest.comtrade import parse_comtrade

PAYLOAD = {
    "count": 3,
    "data": [
        {"reporterISO": "ITA", "partnerISO": "CHN", "refYear": 2025,
         "flowCode": "M", "cmdCode": "TOTAL", "primaryValue": 58123456789.0},
        {"reporterISO": "ITA", "partnerISO": "WLD", "refYear": 2025,
         "flowCode": "M", "cmdCode": "TOTAL", "primaryValue": 712345678901.0},
        {"reporterISO": "ITA", "partnerISO": None, "refYear": 2025},  # dropped: no partner
    ],
}


def test_parse_comtrade_rows():
    rows = parse_comtrade(PAYLOAD)
    assert len(rows) == 2
    assert rows[0] == {
        "reporter": "ITA", "partner": "CHN", "year": 2025,
        "import_usd": 58123456789.0, "raw": PAYLOAD["data"][0],
    }
    assert rows[1]["partner"] == "WLD"


def test_upsert_sql_idempotent():
    assert "ON CONFLICT" in db.UPSERT_COUNTRY_TRADE and "DO NOTHING" in db.UPSERT_COUNTRY_TRADE

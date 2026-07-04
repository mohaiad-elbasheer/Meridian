from datetime import datetime, timezone

from meridian_ingest import gdelt

LASTUPDATE = """\
123456 abcdef0123456789 http://data.gdeltproject.org/gdeltv2/20260703121500.export.CSV.zip
234567 fedcba9876543210 http://data.gdeltproject.org/gdeltv2/20260703121500.mentions.CSV.zip
345678 0123456789abcdef http://data.gdeltproject.org/gdeltv2/20260703121500.gkg.csv.zip
"""


def make_row(root_code="19", goldstein="-8.0", n_articles="4", lat="26.6", lon="56.5"):
    row = [""] * 61
    row[0] = "1234567890"
    row[gdelt.COL_EVENT_ROOT_CODE] = root_code
    row[gdelt.COL_GOLDSTEIN] = goldstein
    row[gdelt.COL_NUM_ARTICLES] = n_articles
    row[gdelt.COL_ACTIONGEO_LAT] = lat
    row[gdelt.COL_ACTIONGEO_LON] = lon
    row[gdelt.COL_DATEADDED] = "20260703121500"
    return "\t".join(row)


def test_parse_lastupdate_picks_export_zip():
    url = gdelt.parse_lastupdate(LASTUPDATE)
    assert url == "http://data.gdeltproject.org/gdeltv2/20260703121500.export.CSV.zip"
    assert gdelt.parse_lastupdate("garbage\n") is None


def test_window_from_url():
    url = "http://data.gdeltproject.org/gdeltv2/20260703121500.export.CSV.zip"
    assert gdelt.window_from_url(url) == datetime(2026, 7, 3, 12, 15, tzinfo=timezone.utc)


def test_parse_events_filters():
    csv_bytes = "\n".join([
        make_row(),                                  # kept: fight near Hormuz
        make_row(root_code="04"),                    # dropped: consult, not conflict
        make_row(lat="", lon=""),                    # dropped: no geolocation
        make_row(root_code="14", goldstein="oops"),  # kept: bad goldstein -> None
    ]).encode()
    events = list(gdelt.parse_events(csv_bytes))
    assert len(events) == 2
    assert events[0].root_code == "19" and events[0].goldstein == -8.0
    assert events[1].goldstein is None


def test_nearest_chokepoint():
    cps = gdelt.load_chokepoints()
    assert gdelt.nearest_chokepoint(26.9, 56.2, cps) == "strait_of_hormuz"
    assert gdelt.nearest_chokepoint(0.0, -160.0, cps) is None  # mid-Pacific


def test_aggregate_one_row_per_chokepoint_window():
    window = datetime(2026, 7, 3, 12, 15, tzinfo=timezone.utc)
    events = [
        gdelt.Event("19", -8.0, 4, 26.6, 56.5),   # Hormuz
        gdelt.Event("14", -2.0, 1, 26.7, 56.4),   # Hormuz
        gdelt.Event("18", -9.0, 2, 30.5, 32.3),   # Suez
    ]
    rows = gdelt.aggregate(iter(events), window, gdelt.load_chokepoints())
    assert [r["raw"]["chokepoint_id"] for r in rows] == ["strait_of_hormuz", "suez_canal"]
    hormuz = rows[0]
    assert hormuz["id"] == "gdelt:20260703121500:strait_of_hormuz"
    assert hormuz["severity"] == 2.0
    assert hormuz["raw"]["by_root_code"] == {"19": 1, "14": 1}
    assert hormuz["raw"]["avg_goldstein"] == -5.0
    assert hormuz["raw"]["chokepoint_source"] == "seed_provisional"

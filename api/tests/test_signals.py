from meridian_api.signals import collect

CHOKEPOINTS = [
    {"id": "strait_of_hormuz", "label": "Strait of Hormuz", "lat": 26.6, "lon": 56.5},
    {"id": "suez_canal", "label": "Suez Canal", "lat": 30.45, "lon": 32.35},
]


def test_collect_buckets_and_suggests():
    events = [
        # gdelt aggregate carries its chokepoint in raw
        ("gdelt", "conflict_events_nearby", 24.0, 56.5, 26.6,
         {"chokepoint_id": "strait_of_hormuz"}),
        # quake near Hormuz matched spatially
        ("usgs", "earthquake", 6.1, 56.2, 26.9, {}),
        # far-away quake: dropped
        ("usgs", "earthquake", 7.0, -170.0, -20.0, {}),
        # gdacs orange near Suez
        ("gdacs", "TC", 2.0, 32.3, 30.5, {}),
    ]
    out = collect(CHOKEPOINTS, events)
    by_id = {b["chokepoint_id"]: b for b in out}
    hormuz = by_id["strait_of_hormuz"]
    assert hormuz["events"] == 2
    assert hormuz["conflict_events"] == 24
    assert hormuz["max_quake_mag"] == 6.1
    assert hormuz["suggested_clamps"]["armed_conflict"] == 0.6   # 24/40
    assert hormuz["suggested_clamps"]["natural_hazard"] == 0.37  # (6.1-5)/3
    suez = by_id["suez_canal"]
    assert suez["gdacs_max_level"] == 2.0
    assert suez["suggested_clamps"]["natural_hazard"] == 0.5     # orange alert
    # sorted by activity
    assert out[0]["chokepoint_id"] == "strait_of_hormuz"


def test_collect_quiet_chokepoints_omitted():
    assert collect(CHOKEPOINTS, []) == []

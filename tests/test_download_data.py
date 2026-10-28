import json

import download_data
from download_data import HEILBRONN_BBOX, UNSTABLE_PAGING, HourlyBackground, _danger_zone_row, _pm_row, clean_pm_rows, download_single_request, overtaking_risk


def raw_row(distance=100, manoeuvre=1, lon=9.2, lat=49.14, tags='["bike", "atrai", "heilbronn"]'):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "index": 7, "boxId": "abc", "boxName": "bike 1", "groupTags": tags, "createdAt": "2026-01-01T12:00:00", "longitude": lon, "latitude": lat,
            "Overtaking Manoeuvre": manoeuvre, "Overtaking Distance": distance, "Speed": 4.0, "Finedust PM2.5": 3.0,
        },
    }


def test_overtaking_risk_matches_the_docs_formula():
    assert overtaking_risk(1, 0) == 1
    assert overtaking_risk(1, 400) == 0.3
    assert overtaking_risk(1, 1000) == 0.3  # distances are capped at 400 cm
    assert overtaking_risk(0.5, 200) == 0.15 + 0.35


def test_danger_zone_row_keeps_device_and_exact_distance():
    row = _danger_zone_row(raw_row(distance=68))
    assert row["geometry"] == {"type": "Point", "coordinates": [9.2, 49.14]}
    assert row["properties"] == {
        "index": 7, "boxId": "abc", "boxName": "bike 1", "createdAt": "2026-01-01T12:00:00", "Overtaking Manoeuvre": 1,
        "Overtaking Distance": 68, "Risk Index Overtaking": overtaking_risk(1, 68), "Speed": 4.0,
    }


def test_danger_zone_row_skips_rows_without_an_overtaking_or_outside_heilbronn():
    assert _danger_zone_row(raw_row(manoeuvre=0)) is None
    assert _danger_zone_row(raw_row(manoeuvre=0.05)) is None
    assert _danger_zone_row(raw_row(lon=8.40, lat=49.01)) is None  # Karlsruhe
    west, south, east, north = HEILBRONN_BBOX
    assert _danger_zone_row(raw_row(lon=east + 0.01, lat=north)) is None


def test_danger_zone_row_skips_devices_not_tagged_heilbronn():
    # a test box of another project rode through the city; danger_zones does not contain it
    assert _danger_zone_row(raw_row(tags='["bike", "lauds_26"]')) is None


def test_danger_zone_row_gives_no_risk_without_a_distance():
    # 0 is how the raw table stores "no reading", so it must not become maximum risk
    assert _danger_zone_row(raw_row(distance=0))["properties"]["Risk Index Overtaking"] is None
    assert _danger_zone_row(raw_row(distance=None))["properties"]["Risk Index Overtaking"] is None


def pm_raw_row(humidity=60.0, pm25=3.0, lon=9.2, lat=49.14, tags='["bike", "atrai", "heilbronn"]'):
    row = raw_row(lon=lon, lat=lat, tags=tags)
    row["properties"].update({"Rel. Humidity": humidity, "Finedust PM1": 2.0, "Finedust PM2.5": pm25,
                              "Finedust PM4": 4.0, "Finedust PM10": 5.0})
    return row


def test_pm_row_keeps_device_and_pm_readings():
    row = _pm_row(pm_raw_row())
    assert row["geometry"] == {"type": "Point", "coordinates": [9.2, 49.14]}
    assert row["properties"] == {
        "index": 7, "boxId": "abc", "boxName": "bike 1", "createdAt": "2026-01-01T12:00:00",
        "Finedust PM1": 2.0, "Finedust PM2.5": 3.0, "Finedust PM4": 4.0, "Finedust PM10": 5.0,
    }


def test_pm_row_skips_humid_incomplete_and_other_devices():
    assert _pm_row(pm_raw_row(humidity=75)) is not None
    assert _pm_row(pm_raw_row(humidity=75.5)) is None
    assert _pm_row(pm_raw_row(humidity=None)) is None
    assert _pm_row(pm_raw_row(pm25=None)) is None
    assert _pm_row(pm_raw_row(tags='["bike", "lauds_26"]')) is None


def test_pm_row_keeps_rides_outside_heilbronn():
    # needed for the per-device outlier removal in routing; they don't snap to any Heilbronn street
    assert _pm_row(pm_raw_row(lon=8.40, lat=49.01)) is not None


def pm_point(box, pm1, pm10=None, lon=9.2, lat=49.14):
    return {"geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"boxId": box, "Finedust PM1": pm1, "Finedust PM2.5": pm1, "Finedust PM4": pm1, "Finedust PM10": pm10 or pm1}}


def test_clean_pm_rows_drops_spikes_against_each_devices_own_quartiles():
    quiet = [pm_point("quiet", v) for v in (2, 3, 3, 4, 3, 2, 4, 3, 3, 40)]
    dirty = [pm_point("dirty", v) for v in (38, 40, 42, 39, 41, 40, 38, 42, 40, 39)]  # high everywhere, but no spikes
    kept = clean_pm_rows(quiet + dirty)
    assert [f["properties"]["Finedust PM1"] for f in kept] == [2, 3, 3, 4, 3, 2, 4, 3, 3, 38, 40, 42, 39, 41, 40, 38, 42, 40, 39]


def test_clean_pm_rows_drops_a_row_when_any_pm_value_is_a_spike():
    assert len(clean_pm_rows([pm_point("a", 3) for _ in range(9)] + [pm_point("a", 3, pm10=90)])) == 9


def test_clean_pm_rows_drops_devices_with_fewer_than_10_rows():
    assert clean_pm_rows([pm_point("few", 3) for _ in range(9)]) == []


def test_clean_pm_rows_uses_rides_outside_heilbronn_for_the_quartiles_but_drops_them():
    # Inside the city this device reads 10, elsewhere mostly 3: 10 is a spike for this device.
    rows = [pm_point("a", 3, lon=8.40, lat=49.01) for _ in range(12)] + [pm_point("a", 10)]
    assert clean_pm_rows(rows) == []
    assert len(clean_pm_rows([pm_point("a", 3, lon=8.40, lat=49.01) for _ in range(9)] + [pm_point("a", 3)])) == 1


class FakeResponse:
    """A streamed response that hands out its body in tiny chunks, to cut features and characters in half."""

    def __init__(self, body, chunk=7):
        self.body, self.chunk = body.encode("utf-8"), chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _size):
        for i in range(0, len(self.body), self.chunk):
            yield self.body[i:i + self.chunk]


class FakeSession:
    def __init__(self, body):
        self.body, self.params = body, None

    def get(self, url, params=None, **_):
        self.params = params
        return FakeResponse(self.body)


def test_download_single_request_streams_every_feature_once(tmp_path):
    rows = [raw_row(distance=d) for d in (10, 60, 120)]
    rows[1]["properties"]["boxName"] = "Bäume, ] { }"  # brackets and a multi-byte character inside a string
    body = json.dumps({"type": "FeatureCollection", "numberMatched": 3, "features": rows, "numberReturned": 3})
    out = tmp_path / "rows.geojson"
    written, seen = download_single_request(FakeSession(body), "osem_bike_data", out, keep=lambda f: f["properties"]["Overtaking Distance"] > 50)
    assert (written, seen) == (2, 3)
    kept = json.loads(out.read_text(encoding="utf-8"))["features"]
    assert [f["properties"]["Overtaking Distance"] for f in kept] == [60, 120]
    assert kept[0]["properties"]["boxName"] == "Bäume, ] { }"


def test_osem_bike_data_is_never_paged():
    # Its pages come back in a different order on every request, which duplicates and skips rows.
    assert "osem_bike_data" in UNSTABLE_PAGING


def home_row(box, hour, pm1, pm10=None):
    return {"properties": {"boxId": box, "createdAt": f"2026-07-01T{hour}:00:10.000", "Finedust PM1": pm1,
                           "Finedust PM2.5": pm1, "Finedust PM4": pm1, "Finedust PM10": pm1 if pm10 is None else pm10}}


def test_hourly_background_is_the_median_of_each_stations_hourly_mean(monkeypatch):
    monkeypatch.setattr(download_data, "MIN_HOME_HOURS", 2)
    bg = HourlyBackground()
    rows = [home_row("a", "08", 2), home_row("a", "08", 4), home_row("b", "08", 9), home_row("c", "08", 5),
            home_row("a", "09", 1), home_row("b", "09", 6), home_row("c", "09", 4),
            home_row("a", "09", None), home_row("d", "08", 100)]  # a gap, and a station with a single hour
    assert all(bg(r) is None for r in rows)  # keeps no row itself
    out = bg.features()
    assert [f["properties"]["hour"] for f in out] == ["2026-07-01T08", "2026-07-01T09"]
    assert out[0]["properties"]["Finedust PM1"] == 5  # median of a 3, b 9, c 5; d has too few hours
    assert out[0]["properties"]["stations"] == 3
    assert out[1]["properties"]["Finedust PM10"] == 4

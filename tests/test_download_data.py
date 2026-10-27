import json

from download_data import HEILBRONN_BBOX, UNSTABLE_PAGING, _danger_zone_row, download_single_request, overtaking_risk


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

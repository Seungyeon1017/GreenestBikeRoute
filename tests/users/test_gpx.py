"""Reading recorded rides from GPX files (backend/users/gpx.py). No database needed."""
import pytest

from backend.users import gpx
from tests.users.gpx_files import NEAR_NECKAR, gpx as make_gpx, line


def code(data):
    with pytest.raises(gpx.GpxError) as error:
        gpx.read_track(data)
    return error.value.code


def test_a_recorded_ride_is_read_without_its_first_and_last_200_m():
    points = line(metres=3000)

    track = gpx.read_track(make_gpx(points))

    assert track.length_m == pytest.approx(3000 - 2 * gpx.PRIVACY_TRIM_M, abs=5)
    assert gpx._metres(points[0], track.coordinates[0]) == pytest.approx(gpx.PRIVACY_TRIM_M, abs=2)
    assert gpx._metres(points[-1], track.coordinates[-1]) == pytest.approx(gpx.PRIVACY_TRIM_M, abs=2)
    assert track.moving_s == (len(points) - 1) * 10
    assert str(track.recorded_on) == "2026-09-06"
    assert track.creator == "TestApp"


def test_a_straight_ride_is_simplified_to_its_ends():
    track = gpx.read_track(make_gpx(line(metres=3000)))

    assert len(track.coordinates) == 2


def test_long_wiggly_rides_are_cut_to_max_points(monkeypatch):
    monkeypatch.setattr(gpx, "MAX_POINTS", 10)
    zigzag = [[lon + (0.001 if i % 2 else 0), lat] for i, (lon, lat) in enumerate(line(metres=5000))]

    track = gpx.read_track(make_gpx(zigzag, step_s=20))

    assert len(track.coordinates) <= 10


def test_gpx_1_0_files_are_read():
    assert gpx.read_track(make_gpx(line(), version="1.0")).length_m > 2000


def test_a_planned_route_without_times_is_refused():
    assert code(make_gpx(line(), times=False)) == "no_times"
    assert code(make_gpx(line(), times=False, kind="rte")) == "no_times"


def test_a_ride_too_fast_for_a_bike_is_refused():
    assert code(make_gpx(line(), step_s=2)) == "too_fast"  # 50 m in 2 s = 90 km/h


def test_standing_still_doesnt_count_as_moving():
    points = line(metres=3000)
    waiting = [points[30]] * 30  # half an hour at a traffic light, at most
    track = gpx.read_track(make_gpx(points[:30] + waiting + points[30:], step_s=60))

    assert track.moving_s == (len(points) - 1) * 60


def test_rides_outside_heilbronn_are_refused():
    stuttgart = (9.18, 48.78)
    assert code(make_gpx(line(start=stuttgart))) == "outside"
    # Starts in Heilbronn, but goes 60 km north.
    assert code(make_gpx(line(metres=60_000), step_s=10)) == "outside"
    # Near Heilbronn (Neckarsulm) without touching the city.
    assert code(make_gpx(line(start=(9.25, 49.23)))) == "outside"


def test_too_short_and_too_long_rides_are_refused(monkeypatch):
    assert code(make_gpx(line(metres=600))) == "too_short"
    monkeypatch.setattr(gpx, "MAX_LENGTH_M", 2000)
    assert code(make_gpx(line(metres=3000))) == "too_long"


@pytest.mark.parametrize("data", [b"not xml", b"<kml></kml>", b'<!DOCTYPE gpx [<!ENTITY a "aaa">]><gpx>&a;</gpx>'])
def test_files_that_arent_gpx_are_refused(data):
    assert code(data) == "invalid"


def test_a_gpx_without_points_is_refused():
    assert code(b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg/></trk></gpx>') == "no_track"


def test_big_files_are_refused(monkeypatch):
    monkeypatch.setattr(gpx, "MAX_FILE_BYTES", 100)
    assert code(make_gpx(line())) == "too_big"


def test_loops_are_recognised():
    out_and_back = line(metres=2000) + line(start=line(metres=2000)[-1], metres=2000, bearing_deg=180)[1:]

    assert gpx.is_loop(gpx.read_track(make_gpx(out_and_back)).coordinates)
    assert not gpx.is_loop(gpx.read_track(make_gpx(line(metres=3000))).coordinates)


def test_preview_line_keeps_ends_and_count():
    coords = [[i, 0] for i in range(100)]

    preview = gpx.preview_line(coords, 10)

    assert len(preview) == 10 and preview[0] == [0, 0] and preview[-1] == [99, 0]
    assert gpx.preview_line(coords[:5], 10) == coords[:5]

import json
import math

from backend.tracks import MAX_END_GAP_M, Tracks, build_tracks
from backend.transit import Transit, is_train
from tests.test_transit import csv_text, feed_zip

# One train A -> B -> C along a bent track, and a bus whose shape is not kept.
FEED = {
    "routes.txt": csv_text("route_id,route_short_name,route_type", ("s4", "S4", "0"), ("bus", "11", "3")),
    "trips.txt": csv_text("route_id,service_id,trip_id,shape_id",
                          ("s4", "daily", "t1", "track"), ("s4", "daily", "t2", "track"), ("bus", "daily", "b1", "road")),
    "stops.txt": csv_text("stop_id,stop_name,stop_lat,stop_lon",
                          ("de:1:1:0:1", "A", "49.10", "9.10"), ("de:1:2:0:1", "B", "49.12", "9.12"),
                          ("de:1:3:0:1", "C", "49.14", "9.10")),
    "stop_times.txt": csv_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,shape_dist_traveled",
        ("t1", "08:00:00", "08:00:00", "de:1:1:0:1", "1", "0"), ("t1", "08:05:00", "08:05:00", "de:1:2:0:1", "2", "3000"),
        ("t1", "08:10:00", "08:10:00", "de:1:3:0:1", "3", "6000"),
        ("b1", "08:00:00", "08:00:00", "de:1:1:0:1", "1", "0"), ("b1", "08:05:00", "08:05:00", "de:1:3:0:1", "2", "900")),
    "shapes.txt": csv_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled",
        ("track", "49.10", "9.10", "1", "0"), ("track", "49.11", "9.12", "2", "1500"), ("track", "49.12", "9.12", "3", "3000"),
        ("track", "49.13", "9.12", "4", "4500"), ("track", "49.14", "9.10", "5", "6000"),
        ("road", "49.10", "9.10", "1", "0"), ("road", "49.14", "9.10", "2", "900")),
}
A, B, C = "de:1:1", "de:1:2", "de:1:3"


def fetch(to_path):
    with open(to_path, "wb") as f:
        f.write(feed_zip(FEED))


def transit_with(tmp_path, tracks):
    return Transit(path=tmp_path / "gtfs.zip", fetch=lambda: None, tracks=tracks)


def written(tmp_path, tracks):
    """A Tracks over a tracks file holding `tracks` ({"a|b": line})."""
    path = tmp_path / "tracks.json"
    path.write_text(json.dumps({"tracks": tracks}), encoding="utf-8")
    return Tracks(path=path, fetch=fetch, is_train=is_train, background=False)


def call(place, lon, lat):
    return {"stop_id": place, "stop_place": place, "lon": lon, "lat": lat}


def metres_between(p, q):
    return math.hypot((p[0] - q[0]) * 111_320 * math.cos(math.radians(p[1])), (p[1] - q[1]) * 111_320)


def test_the_track_is_cut_between_each_two_stations_in_a_row(tmp_path):
    zip_path = tmp_path / "feed.zip"
    fetch(zip_path)
    assert build_tracks(zip_path, is_train) == {  # not the bus from A to C
        f"{A}|{B}": [[9.10, 49.10], [9.12, 49.11], [9.12, 49.12]],
        f"{B}|{C}": [[9.12, 49.12], [9.12, 49.13], [9.10, 49.14]]}


def test_tracks_are_built_once_and_kept(tmp_path):
    calls = []

    def counted(to_path):
        calls.append(to_path)
        fetch(to_path)

    tracks = Tracks(path=tmp_path / "tracks.json", fetch=counted, is_train=is_train, background=False)
    assert set(tracks.tracks()) == {(A, B), (B, C)} and set(tracks.tracks()) == {(A, B), (B, C)}
    assert len(calls) == 1 and json.loads((tmp_path / "tracks.json").read_text())["tracks"]


def test_a_trains_line_follows_the_tracks(tmp_path):
    tracks = Tracks(path=tmp_path / "tracks.json", fetch=fetch, is_train=is_train, background=False)
    stops = [call(A, 9.10, 49.10), call(B, 9.12, 49.12), call(C, 9.10, 49.14)]
    assert transit_with(tmp_path, tracks).train_line(stops) == [
        [9.10, 49.10], [9.12, 49.11], [9.12, 49.12], [9.12, 49.13], [9.10, 49.14]]


def test_without_the_feed_trains_are_drawn_straight(tmp_path):
    def down(to_path):
        raise OSError("no network")

    tracks = Tracks(path=tmp_path / "tracks.json", fetch=down, is_train=is_train, background=False)
    assert tracks.tracks() == {}
    stops = [call(A, 9.10, 49.10), call(C, 9.10, 49.14)]
    assert transit_with(tmp_path, tracks).train_line(stops) == [[9.10, 49.10], [9.10, 49.14]]


# A station X with two stops 80 m apart (X1 north of X2), between A in the west and B in the east.
X1, X2 = "de:1:10", "de:1:11"
AT = {A: (9.100, 49.1000), X1: (9.110, 49.1004), X2: (9.110, 49.0997), B: (9.120, 49.1000)}
TO_X1 = [[9.100, 49.1000], [9.105, 49.1004], [9.110, 49.1004]]
FROM_X2 = [[9.110, 49.0997], [9.115, 49.0995], [9.120, 49.1000]]
FROM_X1 = [[9.110, 49.1004], [9.115, 49.1006], [9.120, 49.1000]]


def stops_of(*places):
    return [{"stop_id": "de:1:10" if p in (X1, X2) else p, "stop_place": p, "lon": AT[p][0], "lat": AT[p][1]}
            for p in places]


def test_a_train_uses_the_track_of_the_stop_it_calls_at(tmp_path):
    # X2's track to B comes first in the file: the train through X1 must not take it.
    tracks = written(tmp_path, {f"{A}|{X1}": TO_X1, f"{X2}|{B}": FROM_X2, f"{X1}|{B}": FROM_X1})
    transit = transit_with(tmp_path, tracks)
    assert transit.train_line(stops_of(A, X1, B)) == TO_X1 + FROM_X1[1:]
    # Stop X2 has a track on to B but none from A: straight to it, never X1's track, then its own.
    line = transit.train_line(stops_of(A, X2, B))
    assert line == [[9.100, 49.1000], *FROM_X2]
    assert [9.115, 49.1006] not in line and [9.105, 49.1004] not in line


def test_a_track_ending_short_of_its_stop_is_joined_to_it(tmp_path):
    short = [[9.100, 49.1000], [9.105, 49.1004], [9.1093, 49.1004]]  # ends 50 m before X1
    transit = transit_with(tmp_path, written(tmp_path, {f"{A}|{X1}": short}))
    line = transit.train_line(stops_of(A, X1))
    assert line == [*short, [9.110, 49.1004]]


def test_a_track_running_past_its_stop_ends_at_the_stop(tmp_path):
    past = [[9.0986, 49.1000], [9.100, 49.1000], [9.105, 49.1004], [9.1114, 49.1004]]  # 100 m more at both ends
    transit = transit_with(tmp_path, written(tmp_path, {f"{A}|{X1}": past}))
    line = transit.train_line(stops_of(A, X1))
    assert line == [[9.100, 49.1000], [9.105, 49.1004], [9.110, 49.1004]]
    assert all(9.100 <= lon <= 9.110 for lon, _ in line)


def test_a_track_far_from_its_stop_is_not_trusted(tmp_path):
    far = [[9.114, 49.1090], [9.105, 49.1004], [9.110, 49.1004]]  # starts 1 km from A
    assert metres_between(far[0], AT[A]) > 1000
    transit = transit_with(tmp_path, written(tmp_path, {f"{A}|{X1}": far, f"{X1}|{B}": FROM_X1}))
    line = transit.train_line(stops_of(A, X1, B))
    assert line == [[9.100, 49.1000], *FROM_X1]  # A to X1 straight, then the track
    # Within MAX_END_GAP_M the track is kept, and joined to the stop.
    near = [[9.100, 49.1020], [9.105, 49.1040], [9.110, 49.1004]]  # starts 220 m north of A, leading away
    assert metres_between(near[0], AT[A]) < MAX_END_GAP_M
    transit = transit_with(tmp_path, written(tmp_path, {f"{A}|{X1}": near}))
    assert transit.train_line(stops_of(A, X1)) == [[9.100, 49.1000], *near]


def test_two_tracks_in_a_row_meet_at_the_stop_between_them(tmp_path):
    # The first ends 30 m short of X1, the second starts 40 m past it: both are tied to X1's mark.
    first = [[9.100, 49.1000], [9.105, 49.1004], [9.1096, 49.1004]]
    second = [[9.1094, 49.1004], [9.115, 49.1006], [9.120, 49.1000]]
    transit = transit_with(tmp_path, written(tmp_path, {f"{A}|{X1}": first, f"{X1}|{B}": second}))
    a_x = transit.train_line(stops_of(A, X1))
    x_b = transit.train_line(stops_of(X1, B))
    assert a_x[-1] == x_b[0] == [9.110, 49.1004]
    whole = transit.train_line(stops_of(A, X1, B))
    assert whole == a_x + x_b[1:] and whole.count([9.110, 49.1004]) == 1
    assert (whole[0], whole[-1]) == ([9.100, 49.1000], [9.120, 49.1000])

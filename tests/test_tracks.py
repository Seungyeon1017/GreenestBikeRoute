import json

from backend.tracks import Tracks, build_tracks
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


class Stations:
    """As much of a Timetable as Transit.train_line reads."""

    def __init__(self, alias):
        self.alias = alias


def transit_with(tmp_path, tracks, alias):
    transit = Transit(path=tmp_path / "gtfs.zip", fetch=lambda: None, tracks=tracks)
    transit.timetable = lambda: Stations(alias)
    return transit


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
    # Stops the timetable made one station: B is part of A, so only A -> C is left.
    assert set(tracks.between({A: A, B: A, C: C})) == {(A, C)}


def test_a_trains_line_follows_the_tracks(tmp_path):
    tracks = Tracks(path=tmp_path / "tracks.json", fetch=fetch, is_train=is_train, background=False)
    transit = transit_with(tmp_path, tracks, {A: A, B: B, C: C})
    stops = [{"stop_id": sid, "lon": 0, "lat": 0} for sid in (A, B, C)]
    assert transit.train_line(stops) == [[9.10, 49.10], [9.12, 49.11], [9.12, 49.12], [9.12, 49.13], [9.10, 49.14]]


def test_without_the_feed_trains_are_drawn_straight(tmp_path):
    def down(to_path):
        raise OSError("no network")

    tracks = Tracks(path=tmp_path / "tracks.json", fetch=down, is_train=is_train, background=False)
    assert tracks.tracks() == {}
    transit = transit_with(tmp_path, tracks, {A: A, C: C})
    stops = [{"stop_id": A, "lon": 9.10, "lat": 49.10}, {"stop_id": C, "lon": 9.10, "lat": 49.14}]
    assert transit.train_line(stops) == [[9.10, 49.10], [9.10, 49.14]]

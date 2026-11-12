from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import TrainTrip
from backend.sharing import SharingUnavailable
from backend.transit import LOCAL_TZ, Timetable, Transit
from routing.costs import SHORTEST
from routing.route import RouteError
from routing.train_trip import ALIGHT_BUFFER_S, BOARD_BUFFER_S, plan_train_trip
from tests.conftest import COORDS, A, B, C
from tests.test_transit import csv_text, feed_zip

SA, SB, SC, FAR = "de:08121:1", "de:08121:2", "de:08121:3", "de:08225:8209"


def stop(sid, name, node=None, lat=None, lon=None):
    lat, lon = COORDS[node] if node else (lat, lon)
    return (f"{sid}:0:1", name, str(lat), str(lon), "0", "", "1")


def calls(trip, *stops):
    return [(trip, f"{t}:00", f"{t}:00", f"{sid}:0:1", str(i), "0", "0") for i, (sid, t) in enumerate(stops, 1)]


# Stations at the toy graph's three corners and one far away. Trains on working days:
#   B 08:10 -> Far 09:00 and B 09:10 -> Far 10:00 (fast), C 08:15 -> Far 09:30 (slow),
#   Far 09:00 -> A 10:00 -> C 10:01, Far 09:30 -> C 10:20.
FEED = {
    "feed_info.txt": csv_text("feed_publisher_name,feed_start_date,feed_end_date", ("NVBW", "20260712", "20261212")),
    "routes.txt": csv_text("route_id,agency_id,route_short_name,route_long_name,route_type",
                           ("s41", "kvv", "S41", "", "0"), ("re8", "db", "RE 8", "", "2")),
    "stops.txt": csv_text(
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,platform_code",
        stop(SA, "Heilbronn A", A), stop(SB, "Heilbronn B", B), stop(SC, "Heilbronn C", C),
        stop(FAR, "Mosbach, Bahnhof", lat=49.353, lon=9.144)),
    "calendar.txt": csv_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date",
        ("weekdays", "1", "1", "1", "1", "1", "0", "0", "20260712", "20261212")),
    "trips.txt": csv_text(
        "route_id,service_id,trip_id,trip_headsign",
        ("re8", "weekdays", "fast1", "Mosbach"), ("re8", "weekdays", "fast2", "Mosbach"),
        ("s41", "weekdays", "slow", "Mosbach"), ("s41", "weekdays", "back1", "Heilbronn"),
        ("s41", "weekdays", "back2", "Heilbronn")),
    "stop_times.txt": csv_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type",
        *calls("fast1", (SB, "08:10"), (FAR, "09:00")), *calls("fast2", (SB, "09:10"), (FAR, "10:00")),
        *calls("slow", (SC, "08:15"), (FAR, "09:30")),
        *calls("back1", (FAR, "09:00"), (SA, "10:00"), (SC, "10:01")), *calls("back2", (FAR, "09:30"), (SC, "10:20"))),
}


@pytest.fixture
def timetable():
    return Timetable(feed_zip(FEED), same_station_m=0)  # the toy graph's corners are 100 m apart: keep them three stations


def at(hour, minute, second=0):
    return datetime(2026, 11, 4, hour, minute, second, tzinfo=LOCAL_TZ)  # a Wednesday


def minute(when):
    return when.isoformat(timespec="minutes")


def test_ride_to_the_station_whose_train_arrives_first(toy_graph, timetable):
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), origin=COORDS[A], to_stop=FAR)
    assert trip["direction"] == "to_train"
    assert (trip["board"]["properties"]["stop_id"], trip["alight"]["properties"]["stop_id"]) == (SB, FAR)
    ride = trip["ride"]
    assert ride["properties"]["mode"] == "bike" and ride["properties"]["length_m"] == 100.0
    assert ride["geometry"]["coordinates"][-1] == [COORDS[B][1], COORDS[B][0]]
    first, second = trip["options"][:2]  # then the next day's
    assert (first["line"], first["departure"], first["arrival"]) == ("RE 8", minute(at(8, 10)), minute(at(9, 0)))
    # Start riding early enough to be at the station BOARD_BUFFER_S before the train leaves.
    leave = at(8, 10) - timedelta(seconds=BOARD_BUFFER_S + ride["properties"]["duration_s"])
    assert (first["leave_at"], first["arrive_at"], first["wait_s"]) == (minute(leave), minute(at(9, 0)), BOARD_BUFFER_S)
    assert first["duration_s"] == 50 * 60 + BOARD_BUFFER_S + ride["properties"]["duration_s"]
    assert first["bike_ticket_needed"] and not second["bike_ticket_needed"]  # 08:10 on a working day, then 09:10
    assert [s["stop_id"] for s in first["stops"]] == [SB, FAR]
    assert (first["stops"][0]["lat"], first["stops"][0]["lon"]) == COORDS[B]
    assert second["departure"] == minute(at(9, 10))


def test_a_missed_train_sends_the_rider_to_another_station(toy_graph, timetable):
    # At 08:09 the 08:10 from B can't be caught any more: the slow train from C (09:30) beats B's next one (10:00).
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 9), origin=COORDS[A], to_stop=FAR)
    assert trip["board"]["properties"]["stop_id"] == SC
    assert [(o["departure"], o["arrive_at"]) for o in trip["options"][:1]] == [(minute(at(8, 15)), minute(at(9, 30)))]
    assert trip["options"][0]["leave_at"] >= minute(at(8, 9))


def test_get_off_where_the_ride_ends_first(toy_graph, timetable):
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 30), from_stop=FAR, destination=COORDS[B])
    assert trip["direction"] == "from_train"
    # Getting off at A (10:00) and riding 100 m beats staying on to C (10:01) for a 70 m ride.
    assert (trip["board"]["properties"]["stop_id"], trip["alight"]["properties"]["stop_id"]) == (FAR, SA)
    ride = trip["ride"]
    assert ride["geometry"]["coordinates"][0] == [COORDS[A][1], COORDS[A][0]]
    option = trip["options"][0]
    arrive = at(10, 0) + timedelta(seconds=ALIGHT_BUFFER_S + ride["properties"]["duration_s"])
    assert (option["leave_at"], option["arrival"], option["arrive_at"]) == (
        minute(at(9, 0)), minute(at(10, 0)), minute(arrive))
    assert option["wait_s"] == 0 and [s["stop_id"] for s in option["stops"]] == [FAR, SA]


def test_get_off_at_the_only_station_a_later_train_calls_at(toy_graph, timetable):
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(9, 10), from_stop=FAR, destination=COORDS[B])
    assert trip["alight"]["properties"]["stop_id"] == SC
    assert trip["options"][0]["departure"] == minute(at(9, 30))


def test_no_direct_train_or_unknown_station(toy_graph, timetable):
    with pytest.raises(RouteError, match="no direct train to Heilbronn A"):
        plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), origin=COORDS[A], to_stop=SA)
    with pytest.raises(RouteError, match="no direct train from Mosbach"):  # the timetable ends on 12 December
        plan_train_trip(toy_graph, timetable, SHORTEST, datetime(2026, 12, 20, 8, 0, tzinfo=LOCAL_TZ),
                        from_stop=FAR, destination=COORDS[B])
    with pytest.raises(KeyError):
        plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), origin=COORDS[A], to_stop="de:00000:1")


def test_a_station_without_a_way_to_the_end_is_skipped(toy_graph, timetable):
    # Nothing leads from B back to A: no station's ride gets there.
    with pytest.raises(RouteError, match="no rideable route"):
        plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 30), from_stop=FAR, destination=(49.13995, 9.2099))


class Bikes:
    """A sharing feed with one free bike at corner A and one scooter; `down` makes it unreadable."""
    down = False

    def snapshot(self):
        if self.down:
            raise SharingUnavailable("feed down")
        lat, lon = COORDS[A]
        return {"vehicles": [
            {"geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"vehicle": "bike"}},
            {"geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {"vehicle": "scooter"}},
            {"geometry": {"type": "Point", "coordinates": [lon + 0.01, lat]}, "properties": {"vehicle": "bike"}}]}


@pytest.fixture
def bikes():
    return Bikes()


@pytest.fixture
def client(toy_graph, tmp_path, bikes):
    transit = Transit(path=tmp_path / "gtfs.zip", fetch=lambda: feed_zip(FEED), same_station_m=0)
    with TestClient(create_app(graph=toy_graph, transit=transit, sharing=bikes)) as c:
        yield c


def test_api_bike_then_train(client):
    lat, lon = COORDS[A]
    r = client.get("/route/train", params={"from_lat": lat, "from_lon": lon, "to_stop": FAR,
                                           "depart_time": "2026-11-04T08:00"})
    assert r.status_code == 200
    trip = TrainTrip.model_validate(r.json())
    assert (trip.direction, trip.board.properties.name, trip.alight.properties.name) == (
        "to_train", "Heilbronn B", "Mosbach, Bahnhof")
    assert trip.options[0].departure == "2026-11-04T08:10+01:00" and trip.shared_bikes_near is None
    assert trip.valid_until == "2026-12-12"


def test_api_train_then_bike_counts_the_shared_bikes_at_the_station(client, bikes):
    lat, lon = COORDS[B]
    params = {"from_stop": FAR, "to_lat": lat, "to_lon": lon, "depart_time": "2026-11-04T08:30"}
    trip = TrainTrip.model_validate(client.get("/route/train", params=params).json())
    assert (trip.direction, trip.alight.properties.name, trip.shared_bikes_near) == ("from_train", "Heilbronn A", 1)
    bikes.down = True
    assert client.get("/route/train", params=params).json()["shared_bikes_near"] is None


def test_api_errors(client):
    lat, lon = COORDS[A]
    point = {"from_lat": lat, "from_lon": lon}
    assert client.get("/route/train", params=point).status_code == 422  # no station
    assert client.get("/route/train", params={**point, "to_stop": FAR, "from_stop": FAR}).status_code == 422
    r = client.get("/route/train", params={**point, "to_stop": "de:00000:1"})
    assert r.status_code == 404 and "/transit/stops" in r.json()["detail"]
    r = client.get("/route/train", params={**point, "to_stop": SA, "depart_time": "2026-11-04T08:00"})
    assert r.status_code == 400 and "no direct train" in r.json()["detail"]
    assert client.get("/route/train", params={**point, "to_stop": FAR}).status_code in (200, 400)  # from now


def test_between_two_stations_it_is_the_train_only(toy_graph, timetable):
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), from_stop=SB, to_stop=FAR)
    assert (trip["direction"], trip["ride"], trip["direct"]) == ("train", None, None)  # Mosbach: no riding there
    assert (trip["board"]["properties"]["stop_id"], trip["alight"]["properties"]["stop_id"]) == (SB, FAR)
    first = trip["options"][0]
    assert (first["leave_at"], first["arrive_at"], first["wait_s"], first["duration_s"]) == (
        minute(at(8, 10)), minute(at(9, 0)), 0, 50 * 60)
    with pytest.raises(RouteError, match="no direct train from Heilbronn A to Mosbach"):
        plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), from_stop=SA, to_stop=FAR)
    with pytest.raises(RouteError, match="same station"):
        plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), from_stop=SB, to_stop=SB)


def test_a_trip_inside_heilbronn_says_how_long_riding_all_the_way_takes(toy_graph, timetable):
    # From station A the only train goes on to C at 10:00, for a 70 m ride back to B: riding the 100 m is there first.
    trip = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), from_stop=SA, destination=COORDS[B])
    direct = trip["direct"]
    assert trip["alight"]["properties"]["stop_id"] == SC
    assert direct["length_m"] == 100.0 and direct["arrive_at"] < trip["options"][0]["arrive_at"]
    assert direct["arrive_at"] == minute(at(8, 0) + timedelta(seconds=direct["duration_s"]))
    # Between two stations in Heilbronn too; to a station outside there is no riding all the way.
    between = plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), from_stop=SA, to_stop=SC)
    assert between["direct"]["length_m"] == 70.0
    assert plan_train_trip(toy_graph, timetable, SHORTEST, at(8, 0), origin=COORDS[A], to_stop=FAR)["direct"] is None


def test_api_train_only_and_the_way_of_the_train(client):
    r = client.get("/route/train", params={"from_stop": SB, "to_stop": FAR, "depart_time": "2026-11-04T08:00"})
    assert r.status_code == 200
    trip = TrainTrip.model_validate(r.json())
    assert (trip.direction, trip.ride, trip.direct) == ("train", None, None)
    # No tracks in tests: straight from station to station.
    assert trip.options[0].path == [[COORDS[B][1], COORDS[B][0]], [9.144, 49.353]]
    r = client.get("/route/train", params={"from_stop": SA, "to_stop": FAR, "depart_time": "2026-11-04T08:00"})
    assert r.status_code == 400 and "no direct train from Heilbronn A to Mosbach" in r.json()["detail"]

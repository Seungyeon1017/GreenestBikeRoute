import csv
import io
import os
import zipfile
from datetime import date, datetime, timezone

import pytest
import requests
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.schemas import TransitDepartures, TransitStopCollection
from backend.transit import REFRESH_DAYS, Transit, TransitUnavailable, bike_ticket_needed, easter, is_public_holiday

HBF, MOSBACH, SUELMERTOR = "de:08121:1114", "de:08225:8209", "de:08121:75"


def csv_text(header, *rows):
    buf = io.StringIO()
    csv.writer(buf).writerows([header.split(","), *rows])
    return buf.getvalue()


FEED = {
    "feed_info.txt": csv_text("feed_publisher_name,feed_start_date,feed_end_date", ("NVBW", "20260712", "20261212")),
    "routes.txt": csv_text(
        "route_id,agency_id,route_short_name,route_long_name,route_type",
        ("s41", "kvv", "S41", "Heilbronn - Mosbach (Baden)", "0"),
        ("re8", "db", "RE 8", "", "2"),
        ("sev", "db", "SEV", "", "2"),                           # rail replacement bus typed as a train
        ("unnamed", "db", "", "Hauptbahnhof - Hauptbahnhof", "2"),  # another one, without a line name
        ("bus11", "hnv", "11", "", "3")),
    "stops.txt": csv_text(
        "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,platform_code",
        ("de:08121:1114_Parent", "Heilbronn Hbf/Willy-Brandt-Pl.", "49.1427624", "9.2084503", "1", "", ""),
        ("de:08121:1114:3:1", "Heilbronn Hbf/Willy-Brandt-Pl. Gleis 1", "49.1426", "9.2083", "0", "de:08121:1114_Parent", "1"),
        ("de:08121:1114:3:2", "Heilbronn Hbf/Willy-Brandt-Pl. Gleis 2", "49.1425", "9.2084", "0", "de:08121:1114_Parent", "2"),
        ("de:08121:75:1:1", "Heilbronn Sülmertor Gleis 1", "49.1512", "9.2203", "0", "", "1"),  # no parent station
        ("de:08225:8209:3:2", "Mosbach, Bahnhof", "49.3530", "9.1440", "0", "", ""),
        ("de:08225:8209:3:3", "Mosbach, Bahnhof", "49.3531", "9.1441", "0", "", ""),
        ("de:08121:999:0:1", "Heilbronn Bus Stop", "49.14", "9.21", "0", "", "")),
    "calendar.txt": csv_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date",
        ("weekdays", "1", "1", "1", "1", "1", "0", "0", "20260712", "20261212"),
        ("weekend", "0", "0", "0", "0", "0", "1", "1", "20260712", "20261212")),
    "calendar_dates.txt": csv_text("service_id,date,exception_type", ("weekdays", "20261105", "2")),  # not on Thu 5 Nov
    "trips.txt": csv_text(
        "route_id,service_id,trip_id,trip_headsign",
        ("s41", "weekdays", "morning", "Mosbach, Bahnhof"),
        ("s41", "weekdays", "late", "Mosbach, Bahnhof"),
        ("s41", "weekend", "saturday", "Mosbach, Bahnhof"),
        ("re8", "weekdays", "re", ""),
        ("sev", "weekdays", "sev", "Mosbach"),
        ("unnamed", "weekdays", "unnamed", ""),
        ("bus11", "weekdays", "bus", "Bus")),
    "stop_times.txt": csv_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type",
        ("morning", "08:18:00", "08:18:00", "de:08121:1114:3:2", "1", "0", "0"),
        ("morning", "08:25:00", "08:25:00", "de:08121:75:1:1", "2", "0", "0"),
        ("morning", "09:16:00", "09:16:00", "de:08225:8209:3:2", "3", "0", "0"),
        ("late", "23:50:00", "23:50:00", "de:08121:1114:3:1", "1", "0", "0"),
        ("late", "24:48:00", "24:48:00", "de:08225:8209:3:3", "2", "0", "0"),
        ("saturday", "08:18:00", "08:18:00", "de:08121:1114:3:2", "1", "0", "0"),
        ("saturday", "09:16:00", "09:16:00", "de:08225:8209:3:2", "2", "0", "0"),
        ("re", "10:00:00", "10:00:00", "de:08121:1114:3:1", "1", "0", "0"),
        ("re", "10:07:00", "10:07:00", "de:08121:75:1:1", "2", "0", "0"),
        ("sev", "07:00:00", "07:00:00", "de:08121:1114:3:1", "1", "0", "0"),
        ("sev", "08:00:00", "08:00:00", "de:08225:8209:3:2", "2", "0", "0"),
        ("unnamed", "07:10:00", "07:10:00", "de:08121:1114:3:1", "1", "0", "0"),
        ("unnamed", "07:20:00", "07:20:00", "de:08121:999:0:1", "2", "0", "0"),
        ("bus", "07:00:00", "07:00:00", "de:08121:999:0:1", "1", "0", "0"),
        ("bus", "07:05:00", "07:05:00", "de:08121:1114:3:1", "2", "0", "0")),
}


def feed_zip(files=FEED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


class FakeDownload:
    """Returns the test feed and counts calls; `down` makes it fail like a timeout."""

    def __init__(self):
        self.calls, self.down = 0, False

    def __call__(self):
        self.calls += 1
        if self.down:
            raise requests.ConnectionError("nvbw down")
        return feed_zip()


@pytest.fixture
def download():
    return FakeDownload()


@pytest.fixture
def transit(tmp_path, download):
    return Transit(path=tmp_path / "gtfs.zip", fetch=download)


@pytest.fixture
def client(toy_graph, transit):
    with TestClient(create_app(graph=toy_graph, transit=transit)) as c:
        yield c


def names(collection):
    return [f["properties"]["name"] for f in collection["features"]]


def test_only_train_stations_are_listed_one_per_station(transit):
    stops = transit.stops()
    # Platforms are grouped by station (also without a parent station), "Gleis 1" is dropped from the name;
    # the bus stop, served by a bus and an unnamed "train" (rail replacement), is left out.
    assert names(stops) == ["Heilbronn Hbf/Willy-Brandt-Pl.", "Heilbronn Sülmertor", "Mosbach, Bahnhof"]
    hbf = stops["features"][0]
    assert hbf["properties"] == {"stop_id": HBF, "name": "Heilbronn Hbf/Willy-Brandt-Pl.", "lines": ["RE 8", "S41"]}
    assert hbf["geometry"]["coordinates"] == [9.2084503, 49.1427624]  # the parent station's position
    assert stops["valid_until"] == "2026-12-12"


def test_stops_are_found_by_name_without_caring_for_case_or_umlauts(transit):
    assert names(transit.stops(q="MOSBACH")) == ["Mosbach, Bahnhof"]
    assert names(transit.stops(q="sulmertor")) == ["Heilbronn Sülmertor"]
    assert names(transit.stops(q="Stuttgart")) == []


def test_stops_near_a_point_come_closest_first(transit):
    stops = transit.stops(near=(49.1512, 9.2203), limit=2)
    assert names(stops) == ["Heilbronn Sülmertor", "Heilbronn Hbf/Willy-Brandt-Pl."]
    assert stops["features"][0]["properties"]["distance_m"] == 0


def test_departures_to_a_station_come_with_their_arrival(transit):
    out = transit.departures(HBF, datetime(2026, 11, 4, 7, 30), to=MOSBACH)  # a Wednesday
    assert out["stop"] == {"stop_id": HBF, "name": "Heilbronn Hbf/Willy-Brandt-Pl."}
    assert out["to"] == {"stop_id": MOSBACH, "name": "Mosbach, Bahnhof"}
    # The RE 8 doesn't go to Mosbach; the SEV bus is no train. The late one arrives after midnight.
    assert out["departures"] == [
        {"line": "S41", "headsign": "Mosbach, Bahnhof", "departure": "2026-11-04T08:18+01:00", "platform": "2",
         "bike_ticket_needed": True, "arrival": "2026-11-04T09:16+01:00", "arrival_platform": None, "duration_min": 58},
        {"line": "S41", "headsign": "Mosbach, Bahnhof", "departure": "2026-11-04T23:50+01:00", "platform": "1",
         "bike_ticket_needed": False, "arrival": "2026-11-05T00:48+01:00", "arrival_platform": None, "duration_min": 58}]


def test_departures_without_a_destination_list_every_train(transit):
    out = transit.departures(HBF, datetime(2026, 11, 4, 8, 0), limit=2)
    assert [(d["line"], d["departure"], d["headsign"]) for d in out["departures"]] == [
        ("S41", "2026-11-04T08:18+01:00", "Mosbach, Bahnhof"),
        ("RE 8", "2026-11-04T10:00+01:00", "Heilbronn Sülmertor")]  # no headsign in the feed: its last stop
    assert out["to"] is None and "arrival" not in out["departures"][0]


def test_no_departures_from_the_last_stop_or_the_wrong_way(transit):
    assert transit.departures(MOSBACH, datetime(2026, 11, 4, 7, 0))["departures"] == []
    assert transit.departures(SUELMERTOR, datetime(2026, 11, 4, 7, 0), to=HBF)["departures"] == []


def test_departures_follow_the_calendar_and_its_exceptions(transit):
    # Thursday 5 November has no weekday trains: the next one is on Friday.
    first = transit.departures(HBF, datetime(2026, 11, 5, 5, 0), to=MOSBACH)["departures"][0]
    assert first["departure"] == "2026-11-06T08:18+01:00"
    # Saturday: the weekend train, and bikes ride free.
    first = transit.departures(HBF, datetime(2026, 11, 7, 5, 0), to=MOSBACH)["departures"][0]
    assert (first["departure"], first["bike_ticket_needed"]) == ("2026-11-07T08:18+01:00", False)
    # After the timetable ends, nothing.
    assert transit.departures(HBF, datetime(2026, 12, 20, 5, 0))["departures"] == []


def test_a_time_with_a_time_zone_is_read_as_heilbronn_time(transit):
    first = transit.departures(HBF, datetime(2026, 11, 4, 7, 0, tzinfo=timezone.utc), to=MOSBACH)["departures"][0]
    assert first["departure"] == "2026-11-04T08:18+01:00"  # 07:00 UTC is 08:00 in Heilbronn
    first = transit.departures(HBF, datetime(2026, 11, 4, 7, 30, tzinfo=timezone.utc), to=MOSBACH)["departures"][0]
    assert first["departure"] == "2026-11-04T23:50+01:00"


def test_unknown_stations_raise_key_error(transit):
    with pytest.raises(KeyError):
        transit.departures("de:00000:1", datetime(2026, 11, 4, 8, 0))
    with pytest.raises(KeyError):
        transit.departures(HBF, datetime(2026, 11, 4, 8, 0), to="de:00000:1")


def test_easter_and_the_holidays_around_it():
    assert [easter(y) for y in (2024, 2025, 2026, 2027)] == [
        date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5), date(2027, 3, 28)]
    holidays = [date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 14), date(2026, 5, 25), date(2026, 6, 4),
                date(2026, 1, 6), date(2026, 11, 1), date(2026, 12, 26)]
    assert all(is_public_holiday(d) for d in holidays)
    assert not is_public_holiday(date(2026, 4, 5 + 2)) and not is_public_holiday(date(2026, 10, 31))


def test_a_bike_needs_a_ticket_only_on_working_day_mornings():
    assert bike_ticket_needed(datetime(2026, 11, 4, 6, 0))
    assert bike_ticket_needed(datetime(2026, 11, 4, 8, 59))
    assert not bike_ticket_needed(datetime(2026, 11, 4, 5, 59))
    assert not bike_ticket_needed(datetime(2026, 11, 4, 9, 0))
    assert not bike_ticket_needed(datetime(2026, 11, 7, 8, 0))   # Saturday
    assert not bike_ticket_needed(datetime(2026, 12, 25, 8, 0))  # Christmas, a Friday


def test_the_timetable_is_downloaded_once_and_kept(transit, download):
    transit.stops()
    transit.departures(HBF, datetime(2026, 11, 4, 8, 0))
    assert download.calls == 1 and transit.path.exists()
    assert Transit(path=transit.path, fetch=download).stops()["features"]  # a new server reads the copy
    assert download.calls == 1


def test_an_old_copy_is_used_when_the_download_fails(tmp_path, download):
    path = tmp_path / "gtfs.zip"
    path.write_bytes(feed_zip())
    old = path.stat().st_mtime - (REFRESH_DAYS + 1) * 86400
    os.utime(path, (old, old))
    download.down = True
    transit = Transit(path=path, fetch=download)
    assert names(transit.stops())
    transit.stops()
    assert download.calls == 1  # not tried again right away


def test_a_stale_copy_is_replaced(tmp_path, download):
    path = tmp_path / "gtfs.zip"
    files = {**FEED, "feed_info.txt": csv_text("feed_publisher_name,feed_start_date,feed_end_date",
                                               ("NVBW", "20260101", "20260711"))}
    path.write_bytes(feed_zip(files))
    old = path.stat().st_mtime - (REFRESH_DAYS + 1) * 86400
    os.utime(path, (old, old))
    assert Transit(path=path, fetch=download).stops()["valid_until"] == "2026-12-12"


def test_no_timetable_at_all_is_unavailable(transit, download):
    download.down = True
    with pytest.raises(TransitUnavailable):
        transit.stops()


def test_api_stops(client):
    r = client.get("/transit/stops", params={"q": "mosbach"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/geo+json"
    assert names(TransitStopCollection.model_validate(r.json()).model_dump()) == ["Mosbach, Bahnhof"]
    r = client.get("/transit/stops", params={"near_lat": 49.15, "near_lon": 9.22, "limit": 1})
    assert [f["properties"]["stop_id"] for f in r.json()["features"]] == [SUELMERTOR]
    assert client.get("/transit/stops", params={"near_lat": 49.15}).status_code == 422


def test_api_departures(client):
    r = client.get("/transit/departures", params={"stop_id": HBF, "to": MOSBACH, "after": "2026-11-04T07:30"})
    assert r.status_code == 200
    body = TransitDepartures.model_validate(r.json())
    assert [(d.departure, d.duration_min) for d in body.departures] == [
        ("2026-11-04T08:18+01:00", 58), ("2026-11-04T23:50+01:00", 58)]
    assert client.get("/transit/departures", params={"stop_id": HBF}).status_code == 200  # from now
    r = client.get("/transit/departures", params={"stop_id": "de:00000:1"})
    assert r.status_code == 404 and "/transit/stops" in r.json()["detail"]


def test_api_without_a_timetable_is_503(client, download):
    download.down = True
    r = client.get("/transit/stops")
    assert r.status_code == 503 and "timetable unavailable" in r.json()["detail"]

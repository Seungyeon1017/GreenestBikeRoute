"""Train and Stadtbahn timetable of the Heilbronn region, for bike + train trips: ride to a station and take the
train, or get off and ride the rest.

Every station that a rail line of the HNV timetable calls at is listed: the Stadtbahn (S4, S41, S42) and the
regional trains (RE, RB, MEX), including where they run outside Heilbronn (Mosbach, Öhringen, Stuttgart, ...).
Buses are left out: HNV buses generally don't take bikes.

Bikes on HNV trains (https://www.mein-hnv.de/service-und-kontakt/hilfe-faq/mitnahme/): free, except Monday to Friday
06:00-09:00, when a Fahrradkarte is needed as well; free all day on weekends and public holidays. One bike per person,
pedelecs too, as long as there is room (wheelchairs and prams go first). Other networks a train runs into may have
other rules.

Data: NVBW / MobiData BW, "Soll-Fahrplandaten Verkehrsverbünde BW (einzeln) ohne Linienverlauf", HNV
(https://mobidata-bw.de/dataset/soll-fahrplandaten-verkehrsverbunde-bw-einzeln-ohne-linienverlauf), GTFS, ODbL.
Updated weekly upstream; the copy in cache/ is downloaded again when it is older than REFRESH_DAYS.
"""
import csv
import io
import re
import threading
import time
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from backend.sharing import distance_m

GTFS_URL = "https://www.nvbw.de/fileadmin/user_upload/service/open_data/fahrplandaten_ohne_liniennetz/hnv.zip"
CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "gtfs_hnv.zip"
REFRESH_DAYS = 7
RETRY_S = 3600              # after a failed download, keep the old copy this long before trying again
ATTRIBUTION = "NVBW / MobiData BW (ODbL), timetable of the Heilbronner Hohenloher Haller Nahverkehr (HNV)"
LOCAL_TZ = ZoneInfo("Europe/Berlin")
BIKE_TICKET_HOURS = (6, 9)  # Monday to Friday from 06:00 to before 09:00 a bike needs a Fahrradkarte
SEARCH_DAYS = 2             # look this many service days ahead for departures
PLATFORM = re.compile(r" (Gleis|Bstg) \S+$")  # "Heilbronn Hauptbahnhof Gleis 1" -> "Heilbronn Hauptbahnhof"


def is_train(route):
    """Whether a GTFS route is a Stadtbahn or train line: a tram, metro or rail route type, basic (0-2) or extended
    (100-199 rail, 400-499 urban rail, 900-999 tram), with a line name. Rail replacement buses (SEV) are left out:
    the feed types some as trains, with "SEV" or no line name."""
    t, line = int(route["route_type"]), route["route_short_name"].strip()
    rail = t in (0, 1, 2) or 100 <= t < 200 or 400 <= t < 500 or 900 <= t < 1000
    return rail and line != "" and not line.startswith("SEV")


def easter(year):
    """Easter Sunday (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def is_public_holiday(day):
    """Public holidays in Baden-Württemberg."""
    if (day.month, day.day) in {(1, 1), (1, 6), (5, 1), (10, 3), (11, 1), (12, 25), (12, 26)}:
        return True
    return (day - easter(day.year)).days in (-2, 1, 39, 50, 60)  # Good Friday, Easter Monday, Ascension, Whit Monday, Corpus Christi


def bike_ticket_needed(when):
    """Whether a bike needs a Fahrradkarte on an HNV train leaving at `when` (local time)."""
    start, end = BIKE_TICKET_HOURS
    return when.weekday() < 5 and not is_public_holiday(when.date()) and start <= when.hour < end


def local(when):
    """`when` in Heilbronn time; a time without a time zone already is."""
    return when.replace(tzinfo=LOCAL_TZ) if when.tzinfo is None else when.astimezone(LOCAL_TZ)


def folded(text):
    """For name search: case, accents and umlauts don't matter (Sülmertor = sulmertor)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def _seconds(hms):
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s


def _gtfs_date(text):
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))


class TransitUnavailable(RuntimeError):
    """There is no timetable: it can't be downloaded and no copy is cached."""


class Timetable:
    """The rail part of a GTFS feed (zip bytes): stations, the lines calling there and every trip's stops."""

    def __init__(self, zip_bytes):
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            def rows(name):
                if name not in z.namelist():
                    return iter(())
                return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))

            lines = {r["route_id"]: r["route_short_name"].strip() for r in rows("routes.txt") if is_train(r)}
            trips = {t["trip_id"]: (lines[t["route_id"]], t["service_id"], t.get("trip_headsign") or "")
                     for t in rows("trips.txt") if t["route_id"] in lines}
            stops = {s["stop_id"]: s for s in rows("stops.txt")}
            stop_times = {}
            for st in rows("stop_times.txt"):
                if st["trip_id"] in trips:
                    stop_times.setdefault(st["trip_id"], []).append(st)
            self._read_calendar(rows("calendar.txt"), rows("calendar_dates.txt"))
            info = next(rows("feed_info.txt"), {})

        self.valid_from = _gtfs_date(info["feed_start_date"]) if info.get("feed_start_date") else None
        self.valid_until = _gtfs_date(info["feed_end_date"]) if info.get("feed_end_date") else None
        self.stations = {}      # station id -> {"name", "lat", "lon", "lines"}
        self.trips = []         # (line, service_id, headsign, [(station id, platform, arrival s, departure s, board, alight)])
        self.calls = {}         # station id -> [(trip index, stop index)]
        for trip_id, (line, service, headsign) in trips.items():
            calls = []
            for st in sorted(stop_times.get(trip_id, ()), key=lambda st: int(st["stop_sequence"])):
                stop = stops[st["stop_id"]]
                station = self._station(stops, stop)
                self.stations[station]["lines"].add(line)
                arrival, departure = st["arrival_time"] or st["departure_time"], st["departure_time"] or st["arrival_time"]
                calls.append((station, stop.get("platform_code") or None, _seconds(arrival), _seconds(departure),
                              st.get("pickup_type") != "1", st.get("drop_off_type") != "1"))
            for i, call in enumerate(calls):
                self.calls.setdefault(call[0], []).append((len(self.trips), i))
            self.trips.append((line, service, headsign, calls))

    def _station(self, stops, stop):
        """The id of the station `stop` (a platform) belongs to: its stop place in the stop id (de:08121:26 for
        de:08121:26:1:1, the parent's id without "_Parent"), as not every platform has a parent station."""
        parent = stops.get(stop.get("parent_station") or "")
        place = parent or stop
        sid = ":".join(place["stop_id"].removesuffix("_Parent").split(":")[:3])
        if sid not in self.stations:
            name = PLATFORM.sub("", " ".join(place["stop_name"].split()))
            self.stations[sid] = {"name": name, "lat": float(place["stop_lat"]), "lon": float(place["stop_lon"]),
                                  "lines": set()}
        return sid

    def _read_calendar(self, calendar, calendar_dates):
        days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        self._weekly = {c["service_id"]: (_gtfs_date(c["start_date"]), _gtfs_date(c["end_date"]),
                                          [c[d] == "1" for d in days]) for c in calendar}
        self._exceptions = {}
        for c in calendar_dates:
            self._exceptions[(c["service_id"], _gtfs_date(c["date"]))] = c["exception_type"] == "1"

    def runs(self, service, day):
        """Whether trips of `service` run on service day `day`."""
        if (service, day) in self._exceptions:
            return self._exceptions[(service, day)]
        weekly = self._weekly.get(service)
        return weekly is not None and weekly[0] <= day <= weekly[1] and weekly[2][day.weekday()]

    def departures(self, station, after, to=None, limit=10):
        """The next `limit` trains leaving `station` at or after `after` (aware datetime), soonest first, within
        SEARCH_DAYS; with `to`, only trains that go on to station `to`, with their arrival there."""
        out = []
        first = after.date() - timedelta(days=1)  # GTFS times run past 24:00 for trips that began the day before
        for trip_index, i in self.calls.get(station, ()):
            line, service, headsign, calls = self.trips[trip_index]
            _, platform, _, dep_s, board, _ = calls[i]
            if not board or i == len(calls) - 1:
                continue
            end = None
            if to is not None:
                end = next((c for c in calls[i + 1:] if c[0] == to and c[5]), None)
                if end is None:
                    continue
            for offset in range(SEARCH_DAYS + 1):
                day = first + timedelta(days=offset)
                leaves = self._at(day, dep_s)
                if leaves < after or leaves > after + timedelta(days=SEARCH_DAYS) or not self.runs(service, day):
                    continue
                departure = {"line": line, "headsign": headsign or self.stations[calls[-1][0]]["name"],
                             "departure": leaves.isoformat(timespec="minutes"), "platform": platform,
                             "bike_ticket_needed": bike_ticket_needed(leaves)}
                if end is not None:
                    arrives = self._at(day, end[2])
                    departure.update(arrival=arrives.isoformat(timespec="minutes"), arrival_platform=end[1],
                                     duration_min=round((arrives - leaves).total_seconds() / 60))
                out.append((leaves, departure))
        return [d for _, d in sorted(out, key=lambda x: x[0])[:limit]]

    @staticmethod
    def _at(day, seconds):
        """The local time `seconds` after the start of service day `day` (GTFS counts from noon minus 12 h, which
        differs from midnight only on the two nights the clocks change)."""
        return (datetime(day.year, day.month, day.day, 12, tzinfo=LOCAL_TZ) - timedelta(hours=12)
                + timedelta(seconds=seconds))


class Transit:
    """The timetable, read on first use from the GTFS zip at `path` and downloaded again when that is older than
    REFRESH_DAYS. `fetch()` returns the zip's bytes (tests pass a fake)."""

    def __init__(self, path=CACHE_PATH, fetch=None, clock=time.time):
        self.path, self.clock = Path(path), clock
        self.fetch = fetch or self._download
        self._timetable, self._tried, self._lock = None, None, threading.Lock()

    @staticmethod
    def _download():
        r = requests.get(GTFS_URL, timeout=120)
        r.raise_for_status()
        return r.content

    def _stale(self):
        return not self.path.exists() or self.clock() - self.path.stat().st_mtime > REFRESH_DAYS * 86400

    def timetable(self):
        """The Timetable; the first call reads it (~10 s, plus the download if there is no recent copy)."""
        with self._lock:
            if self._stale() and (self._tried is None or self.clock() - self._tried > RETRY_S):
                self._tried = self.clock()
                try:
                    data = self.fetch()
                    zipfile.ZipFile(io.BytesIO(data)).testzip()
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    self.path.write_bytes(data)
                    self._timetable = None
                except (requests.RequestException, zipfile.BadZipFile, OSError) as e:
                    if not self.path.exists():  # else keep using the old copy
                        raise TransitUnavailable(f"timetable unavailable ({type(e).__name__}), try again later") from e
            if self._timetable is None:
                self._timetable = Timetable(self.path.read_bytes())
            return self._timetable

    def stops(self, q=None, near=None, limit=None):
        """A FeatureCollection of the stations, with name containing `q` if given; with near=(lat, lon), closest
        first, each with `distance_m`."""
        tt = self.timetable()
        features = []
        for sid, s in tt.stations.items():
            if q and folded(q) not in folded(s["name"]):
                continue
            properties = {"stop_id": sid, "name": s["name"], "lines": sorted(s["lines"])}
            if near is not None:
                properties["distance_m"] = round(distance_m(*near, s["lat"], s["lon"]))
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                             "properties": properties})
        features.sort(key=lambda f: (f["properties"].get("distance_m", 0), f["properties"]["name"]))
        return {"type": "FeatureCollection", "features": features[:limit] if limit else features,
                **self._about(tt)}

    def departures(self, stop_id, after, to=None, limit=10):
        """The next departures from `stop_id` (see Timetable.departures); KeyError for an unknown stop."""
        tt = self.timetable()
        for sid in (stop_id, to):
            if sid is not None and sid not in tt.stations:
                raise KeyError(sid)
        named = lambda sid: {"stop_id": sid, "name": tt.stations[sid]["name"]}
        return {"stop": named(stop_id), "to": named(to) if to else None,
                "departures": tt.departures(stop_id, local(after), to, limit), **self._about(tt)}

    @staticmethod
    def _about(tt):
        return {"valid_until": tt.valid_until.isoformat() if tt.valid_until else None, "attribution": ATTRIBUTION}

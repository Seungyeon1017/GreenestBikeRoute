"""A trip by bike and train: ride to a station and take the train, or get off the train and ride the rest.

The rider names the far station (any station of the timetable, also outside Heilbronn, e.g. Mosbach); which station
to ride to, or to get off at, is chosen here: the one that gets the rider there soonest, and of those the one
with the shortest ride. Every station counts the same. Only stations the bike graph reaches (Heilbronn) are ridden
to or from, and only trains without a change.

From one station to another there is nothing to ride: the trip is the direct trains between the two.

When both ends are in Heilbronn the trip also says how long riding all the way takes (`direct`), so nobody is sent
to a train that is slower than their bike.

Which station: for each one with a train to (or from) the far station, the ride is first guessed from the straight
line; the CANDIDATES best are then routed for real, with the request's penalties, as /route.

A station can have several stops (the timetable merges stops within 200 m into one station, e.g. the train platforms
of the Hauptbahnhof and the Stadtbahn stop in front of it). The bike leg goes to the stop the train uses: the trains
of all stops of the station are listed, each timed with the ride to its own stop.

Group: features on top.
"""
import weakref
from datetime import datetime, timedelta

from routing.costs import MEDIAN_SPEED_KMH
from routing.edges import RouteError
from routing.route import find_route
from routing.sharing_trip import DETOUR, _metres
from routing.snap import nearest_street

STATION_SNAP_M = 150   # a station further than this from every street of the bike graph is not ridden to
BOARD_BUFFER_S = 180   # from arriving at the station by bike to the train leaving: find the platform, lift the bike in
ALIGHT_BUFFER_S = 120  # from the train arriving to riding off
CANDIDATES = 4         # stations routed for real
OPTIONS = 4            # trains offered


def _time(text):
    return datetime.fromisoformat(text)


def _iso(when):
    return when.isoformat(timespec="minutes")


_REACHABLE = weakref.WeakKeyDictionary()  # timetable -> (its graph, rideable_stops): neither changes while the API runs


def rideable_stops(G, timetable):
    """The stops the bike graph reaches (in Heilbronn), by station: {station id: {stop place id: (lat, lon)}}.
    A merged station has a stop per part; a part too far from every street is left out."""
    if timetable not in _REACHABLE or _REACHABLE[timetable][0]() is not G:
        near = {}
        for sid, parts in timetable.parts_of.items():
            stops = {part: (p["lat"], p["lon"]) for part, p in ((part, timetable.parts[part]) for part in parts)
                     if nearest_street(G, p["lat"], p["lon"])[3] <= STATION_SNAP_M}
            if stops:
                near[sid] = stops
        _REACHABLE[timetable] = (weakref.ref(G), near)
    return _REACHABLE[timetable][1]


def rideable_stations(G, timetable):
    """The stations the bike graph reaches, those with a stop it reaches: [(id, (lat, lon) of its main part)]."""
    return [(sid, (timetable.stations[sid]["lat"], timetable.stations[sid]["lon"]))
            for sid in rideable_stops(G, timetable)]


def _straight_s(a, b):
    """Guessed riding seconds between two (lat, lon)."""
    return DETOUR * float(_metres(a[0], a[1], b[0], b[1])) / (MEDIAN_SPEED_KMH / 3.6)


def _ride(G, a, b, penalties, depart, rider):
    """The bike leg from a to b as a route Feature (as /route), or None if there is no route."""
    try:
        feature = find_route(G, a, b, *penalties._replace(depart_time=depart), **rider)["features"][0]
    except RouteError:
        return None
    feature["properties"]["mode"] = "bike"
    return feature


def _option(train, stop_place, leave, arrive, wait_s):
    """A train with the times of the whole trip; `stop_place` is the stop the bike leg goes to or starts at."""
    return {**train, "stop_place": stop_place, "leave_at": _iso(leave), "arrive_at": _iso(arrive), "wait_s": round(wait_s),
            "duration_s": round((arrive - leave).total_seconds())}


def _direct(G, a, b, penalties, after, rider):
    """Riding all the way from a to b, leaving at `after`: {"length_m", "duration_s", "arrive_at"}, or None."""
    ride = _ride(G, a, b, penalties, after, rider)
    if ride is None:
        return None
    p = ride["properties"]
    return {"length_m": p["length_m"], "duration_s": p["duration_s"],
            "arrive_at": _iso(after + timedelta(seconds=p["duration_s"]))}


def _train_only(G, timetable, penalties, after, a, b, rider):
    """The direct trains from station a to station b, as plan_train_trip's answer without a ride."""
    def name(sid):
        return timetable.stations[sid]["name"]

    if a == b:
        raise RouteError(f"no direct train from {name(a)} to itself: start and end are the same station")
    found = sorted(timetable.departures(a, after, to=b, limit=OPTIONS, with_stops=True),
                   key=lambda t: (t["arrival"], t["departure"]))
    if not found:
        raise RouteError(f"no direct train from {name(a)} to {name(b)} in the next two days")
    near = dict(rideable_stations(G, timetable))
    direct = _direct(G, near[a], near[b], penalties, after, rider) if a in near and b in near else None
    return {"direction": "train", "board": timetable.stop_feature(a), "alight": timetable.stop_feature(b),
            "ride": None, "rides": [], "direct": direct,
            "options": [_option(t, None, _time(t["departure"]), _time(t["arrival"]), 0) for t in found]}


def plan_train_trip(G, timetable, penalties, after, origin=None, to_stop=None, from_stop=None, destination=None,
                    **rider):
    """The trip that arrives soonest, starting at or after `after` (aware datetime).

    Bike then train: `origin` (lat, lon) and `to_stop` (a station id). Train then bike: `from_stop` and `destination`.
    Train only: `from_stop` and `to_stop`; then `ride` is None and `direction` "train".
    `timetable` is a backend.transit.Timetable, `penalties` the routing Penalties of /route (depart_time is set here:
    the bike leg starts at `after`, or when the train arrives), `rider` weight_kg / e_bike for kcal.

    Returns {"direction", "board", "alight" (station Features), "ride", "rides", "options"}: the trains to take
    between `board` and `alight`, the one arriving first first, each as Timetable.departures with `stops`, plus
    `stop_place` (the stop of the station in Heilbronn this train uses: a merged station has several, up to 175 m
    apart), `leave_at` (start riding, or the train leaves), `arrive_at` (the train arrives, or the ride ends), `wait_s` at the
    station before the train leaves (to_train) and `duration_s` for the whole trip, all with the ride to its own
    stop. `rides`: [{"stop_place", "ride" (route Feature)}], the bike leg for each stop a listed train uses; `ride`
    is the one of options[0]. `direct`: riding all the way
    instead ({"length_m", "duration_s", "arrive_at"}), None when the far station is outside the bike graph.
    Raises KeyError for an unknown station and RouteError when no station in reach has a direct train.
    """
    if from_stop is not None and to_stop is not None:
        return _train_only(G, timetable, penalties, after, timetable.station_id(from_stop),
                           timetable.station_id(to_stop), rider)
    to_train = origin is not None
    far = timetable.station_id(to_stop if to_train else from_stop)
    point = origin if to_train else destination
    far_name = timetable.stations[far]["name"]

    def trip(station, ride_s):
        """The options through `station`, the soonest there first, or [] without a train: the trains of each of its
        stops in `ride_s` ({stop place id: riding seconds}), each timed with the ride to (or from) its own stop."""
        limit = OPTIONS * (len(timetable.parts_of[station]) + 1)  # room for the trains of stops that are left out
        found = []
        if to_train:
            ready = after + timedelta(seconds=min(ride_s.values()) + BOARD_BUFFER_S)
            for t in timetable.departures(station, ready, to=far, limit=limit, with_stops=True):
                part = t["stops"][0]["stop_place"]
                lead = timedelta(seconds=ride_s.get(part, 0) + BOARD_BUFFER_S)
                if part in ride_s and _time(t["departure"]) >= after + lead:
                    found.append((_time(t["arrival"]), t["departure"],
                                  _option(t, part, _time(t["departure"]) - lead, _time(t["arrival"]), BOARD_BUFFER_S)))
        else:
            for t in timetable.departures(far, after, to=station, limit=limit, with_stops=True):
                part = t["stops"][-1]["stop_place"]
                if part in ride_s:
                    arrive = _time(t["arrival"]) + timedelta(seconds=ALIGHT_BUFFER_S + ride_s[part])
                    found.append((arrive, t["departure"], _option(t, part, _time(t["departure"]), arrive, 0)))
        return [option for _, _, option in sorted(found, key=lambda f: f[:2])[:OPTIONS]]

    def rank(options, ride_s):
        """Soonest there first; then the shortest ride (the same train stops at several stations in a row)."""
        return options[0]["arrive_at"], ride_s[options[0]["stop_place"]]

    def routed(station, stops, guessed):
        """The real rides for `station`: ({stop place id: route Feature}, options). A stop is routed once a listed
        train uses it; until then its ride is the guess, so the list is worked out again after each new route.
        A stop without a route is left out with its trains."""
        ride_s, rides, options = dict(guessed), {}, trip(station, guessed)
        while options:
            new = next((o for o in options if o["stop_place"] not in rides), None)
            if new is None:
                break
            part = new["stop_place"]
            if to_train:
                ride = _ride(G, origin, stops[part], penalties, after, rider)
            else:
                ride = _ride(G, stops[part], destination, penalties, _time(new["arrival"]), rider)
            if ride is None:
                del ride_s[part]
            else:
                rides[part], ride_s[part] = ride, ride["properties"]["duration_s"]
            options = trip(station, ride_s) if ride_s else []
        return rides, options, ride_s

    guesses = []
    near = rideable_stops(G, timetable)
    for sid, stops in near.items():
        if sid == far:
            continue
        ride_s = {part: _straight_s(point, at) for part, at in stops.items()}
        options = trip(sid, ride_s)
        if options:
            guesses.append((rank(options, ride_s), sid, ride_s))
    if not guesses:
        way = f"to {far_name}" if to_train else f"from {far_name}"
        raise RouteError(f"no direct train {way} at a station in Heilbronn in the next two days")

    best = None
    for _, sid, guessed in sorted(guesses, key=lambda g: g[:2])[:CANDIDATES]:
        rides, options, ride_s = routed(sid, near[sid], guessed)
        if options and (best is None or rank(options, ride_s) < best[0]):
            best = (rank(options, ride_s), sid, rides, options)
    if best is None:
        raise RouteError("no rideable route between the point and a station with a direct train")

    _, sid, rides, options = best
    used = list(dict.fromkeys(o["stop_place"] for o in options))
    here, there = timetable.stop_feature(sid), timetable.stop_feature(far)
    far_at = dict(rideable_stations(G, timetable)).get(far)
    direct = None
    if far_at is not None:
        direct = _direct(G, *((origin, far_at) if to_train else (far_at, destination)), penalties, after, rider)
    return {"direction": "to_train" if to_train else "from_train",
            "board": here if to_train else there, "alight": there if to_train else here,
            "ride": rides[used[0]], "rides": [{"stop_place": part, "ride": rides[part]} for part in used],
            "direct": direct, "options": options}

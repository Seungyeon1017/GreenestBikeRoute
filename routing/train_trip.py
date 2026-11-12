"""A trip by bike and train: ride to a station and take the train, or get off the train and ride the rest.

The rider names the far station (any station of the timetable, also outside Heilbronn, e.g. Mosbach); which station
to ride to, or to get off at, is chosen here: the one that gets the rider there soonest, and of those the one
with the shortest ride. Every station counts the same. Only stations the bike graph reaches (Heilbronn) are ridden
to or from, and only trains without a change.

Which station: for each one with a train to (or from) the far station, the ride is first guessed from the straight
line; the CANDIDATES best are then routed for real, with the request's penalties, as /route.

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


_REACHABLE = weakref.WeakKeyDictionary()  # timetable -> (its graph, _reachable): neither changes while the API runs


def _reachable(G, timetable):
    """The stations the bike graph reaches: [(id, (lat, lon))]."""
    if timetable not in _REACHABLE or _REACHABLE[timetable][0]() is not G:
        near = [(sid, (s["lat"], s["lon"])) for sid, s in timetable.stations.items()
                if nearest_street(G, s["lat"], s["lon"])[3] <= STATION_SNAP_M]
        _REACHABLE[timetable] = (weakref.ref(G), near)
    return _REACHABLE[timetable][1]


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


def _option(train, leave, arrive, wait_s):
    return {**train, "leave_at": _iso(leave), "arrive_at": _iso(arrive), "wait_s": round(wait_s),
            "duration_s": round((arrive - leave).total_seconds())}


def plan_train_trip(G, timetable, penalties, after, origin=None, to_stop=None, from_stop=None, destination=None,
                    **rider):
    """The trip that arrives soonest, starting at or after `after` (aware datetime).

    Bike then train: `origin` (lat, lon) and `to_stop` (a station id). Train then bike: `from_stop` and `destination`.
    `timetable` is a backend.transit.Timetable, `penalties` the routing Penalties of /route (depart_time is set here:
    the bike leg starts at `after`, or when the train arrives), `rider` weight_kg / e_bike for kcal.

    Returns {"direction", "board", "alight" (station Features), "ride" (route Feature), "options"}: the trains to take
    between `board` and `alight`, the one arriving first first, each as Timetable.departures with `stops`, plus
    `leave_at` (start riding, or the train leaves), `arrive_at` (the train arrives, or the ride ends), `wait_s` at the
    station before the train leaves (to_train) and `duration_s` for the whole trip.
    Raises KeyError for an unknown station and RouteError when no station in reach has a direct train.
    """
    to_train = origin is not None
    far = to_stop if to_train else from_stop
    if far not in timetable.stations:
        raise KeyError(far)
    point = origin if to_train else destination
    far_name = timetable.stations[far]["name"]

    def trains(station, ready):
        """Direct trains for a rider who is at `station` at `ready` (to_train), or leaving `far` from `ready` on."""
        if to_train:
            found = timetable.departures(station, ready, to=far, limit=OPTIONS, with_stops=True)
        else:
            found = timetable.departures(far, ready, to=station, limit=OPTIONS, with_stops=True)
        return sorted(found, key=lambda t: (t["arrival"], t["departure"]))

    def trip(station, ride_s):
        """The options through `station` for a ride of ride_s seconds, the soonest first, or [] without a train."""
        if to_train:
            found = trains(station, after + timedelta(seconds=ride_s + BOARD_BUFFER_S))
            return [_option(t, _time(t["departure"]) - timedelta(seconds=ride_s + BOARD_BUFFER_S), _time(t["arrival"]),
                            BOARD_BUFFER_S) for t in found]
        return [_option(t, _time(t["departure"]), _time(t["arrival"]) + timedelta(seconds=ALIGHT_BUFFER_S + ride_s), 0)
                for t in trains(station, after)]

    def rank(options, ride_s):
        """Soonest there first; then the shortest ride (the same train stops at several stations in a row)."""
        return options[0]["arrive_at"], ride_s

    guesses = []
    for sid, at in _reachable(G, timetable):
        if sid == far:
            continue
        ride_s = _straight_s(point, at)
        options = trip(sid, ride_s)
        if options:
            guesses.append((rank(options, ride_s), sid, at, options))
    if not guesses:
        way = f"to {far_name}" if to_train else f"from {far_name}"
        raise RouteError(f"no direct train {way} at a station in Heilbronn in the next two days")

    best = None
    for _, sid, at, guessed in sorted(guesses, key=lambda g: g[0])[:CANDIDATES]:
        if to_train:
            ride = _ride(G, origin, at, penalties, after, rider)
        else:
            ride = _ride(G, at, destination, penalties, _time(guessed[0]["arrival"]), rider)
        if ride is None:
            continue
        options = trip(sid, ride["properties"]["duration_s"])
        if options and (best is None or rank(options, ride["properties"]["duration_s"]) < best[0]):
            best = (rank(options, ride["properties"]["duration_s"]), sid, ride, options)
    if best is None:
        raise RouteError("no rideable route between the point and a station with a direct train")

    _, sid, ride, options = best
    here, there = timetable.stop_feature(sid), timetable.stop_feature(far)
    return {"direction": "to_train" if to_train else "from_train",
            "board": here if to_train else there, "alight": there if to_train else here,
            "ride": ride, "options": options}

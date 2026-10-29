"""Reading a recorded ride from a GPX file, for riders' leisure routes (community_routes.py).

Riders don't draw their routes: they upload a ride they recorded with another app, as GPX (Komoot, Strava, Garmin
Connect, OsmAnd and most bike computers can export it). A track is taken only if it

- is a recording: its points have times (a route planned in an app has none);
- is a bike ride: at most MAX_SPEED_KMH on average while moving, and MIN_LENGTH_M to MAX_LENGTH_M long;
- belongs to Heilbronn: it passes through HEILBRONN_BBOX and never leaves AREA_BBOX (the city and around it).

Before it is stored, PRIVACY_TRIM_M is cut off both ends (a ride often starts at home) and the line is simplified to
SIMPLIFY_M, at most MAX_POINTS points. Times are only used for these checks: what is kept is the day and how long the
ride took while moving, never when the rider was where.
"""
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from download_data import HEILBRONN_BBOX

MAX_FILE_BYTES = 5 * 1024 * 1024
MIN_LENGTH_M = 1000
MAX_LENGTH_M = 200_000
MAX_SPEED_KMH = 40         # faster on average while moving is not a bike ride
MOVING_KMH = 3             # slower than this between two points counts as standing
MIN_TIMED_SHARE = 0.9      # share of points that must have a time
PRIVACY_TRIM_M = 200
LOOP_M = 600               # a ride whose published ends are this close is a loop (each end lost PRIVACY_TRIM_M)
SIMPLIFY_M = 5
MAX_POINTS = 2000
# Heilbronn with about 20 km around it: rides along the Neckar to Lauffen or Bad Wimpfen are fine.
AREA_BBOX = (HEILBRONN_BBOX[0] - 0.28, HEILBRONN_BBOX[1] - 0.18, HEILBRONN_BBOX[2] + 0.28, HEILBRONN_BBOX[3] + 0.18)
LOCAL_TZ = ZoneInfo("Europe/Berlin")
EARTH_RADIUS_M = 6_371_008.8


class GpxError(ValueError):
    """The file can't be taken. `code` says why, for the app's own message (e.g. "no_times")."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class Track:
    coordinates: list[list[float]]  # [lon, lat], trimmed and simplified
    length_m: float                 # of the trimmed track
    moving_s: int                   # of the whole recording
    recorded_on: date               # Heilbronn day the ride started
    creator: str | None             # the app that wrote the file (GPX `creator`), e.g. "StravaGPX"


def _metres(a, b):
    """Great-circle distance between two [lon, lat] points."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _length(coords):
    return sum(_metres(a, b) for a, b in zip(coords, coords[1:]))


def _local_name(tag):
    """"{http://www.topografix.com/GPX/1/1}trkpt" -> "trkpt": GPX 1.0 and 1.1 use different namespaces."""
    return tag.rsplit("}", 1)[-1]


def _time(text):
    if not text:
        return None
    try:
        t = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=LOCAL_TZ)


def _points(root):
    """[(lon, lat, time or None)] of all track points in file order; route points (rtept) if there is no track."""
    for kind in ("trkpt", "rtept"):
        points = []
        for el in root.iter():
            if _local_name(el.tag) != kind:
                continue
            try:
                lon, lat = float(el.get("lon")), float(el.get("lat"))
            except (TypeError, ValueError):
                raise GpxError("invalid", "a track point has no valid lat/lon") from None
            t = next((_time(c.text) for c in el if _local_name(c.tag) == "time"), None)
            points.append((lon, lat, t))
        if points:
            return points
    raise GpxError("no_track", "the file has no track")


def _trim(coords, metres):
    """`coords` without the first and last `metres` of its length."""
    def cut(points):
        walked = 0.0
        for i in range(1, len(points)):
            step = _metres(points[i - 1], points[i])
            if walked + step >= metres:
                f = (metres - walked) / step if step else 0
                a, b = points[i - 1], points[i]
                return [[a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])]] + points[i:]
            walked += step
        return points[-1:]
    return cut(cut(coords)[::-1])[::-1]


def _simplify(coords, tolerance_m):
    """Douglas-Peucker in a local plane (metres), keeping the first and last point."""
    lat0 = math.radians(coords[0][1])
    k = math.pi / 180 * EARTH_RADIUS_M
    xy = [(lon * k * math.cos(lat0), lat * k) for lon, lat in coords]
    keep = [False] * len(coords)
    keep[0] = keep[-1] = True
    stack = [(0, len(coords) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        far, far_d = None, tolerance_m
        for m in range(i + 1, j):
            x, y = xy[m]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > far_d:
                far, far_d = m, d
        if far is not None:
            keep[far] = True
            stack += [(i, far), (far, j)]
    return [c for c, k in zip(coords, keep) if k]


def _inside(bbox, lon, lat):
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def read_track(data: bytes) -> Track:
    """The recorded ride in GPX file `data`, checked, trimmed and simplified. Raises GpxError."""
    if len(data) > MAX_FILE_BYTES:
        raise GpxError("too_big", f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    # GPX needs no DOCTYPE; refusing it keeps entity tricks out of the XML parser.
    if b"<!DOCTYPE" in data[:4096].upper() or b"<!ENTITY" in data.upper():
        raise GpxError("invalid", "the file is not a GPX file")
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise GpxError("invalid", "the file is not a GPX file") from None
    if _local_name(root.tag) != "gpx":
        raise GpxError("invalid", "the file is not a GPX file")

    points = _points(root)
    if len(points) < 2:
        raise GpxError("too_short", "the track has fewer than 2 points")
    timed = [p for p in points if p[2] is not None]
    if len(timed) < MIN_TIMED_SHARE * len(points):
        raise GpxError("no_times", "the track has no times: upload a recorded ride, not a planned route")

    coords = [[lon, lat] for lon, lat, _ in points]
    if any(not _inside(AREA_BBOX, lon, lat) for lon, lat in coords):
        raise GpxError("outside", "the track leaves the Heilbronn area")
    if not any(_inside(HEILBRONN_BBOX, lon, lat) for lon, lat in coords):
        raise GpxError("outside", "the track doesn't pass through Heilbronn")

    length = _length(coords)
    if length < MIN_LENGTH_M:
        raise GpxError("too_short", f"the track is shorter than {MIN_LENGTH_M / 1000:g} km")
    if length > MAX_LENGTH_M:
        raise GpxError("too_long", f"the track is longer than {MAX_LENGTH_M / 1000:g} km")

    moving_s, moving_m = 0.0, 0.0
    for (lon1, lat1, t1), (lon2, lat2, t2) in zip(timed, timed[1:]):
        dt = (t2 - t1).total_seconds()
        if dt <= 0:
            continue
        d = _metres((lon1, lat1), (lon2, lat2))
        if d / dt * 3.6 >= MOVING_KMH:
            moving_s, moving_m = moving_s + dt, moving_m + d
    if moving_s <= 0:
        raise GpxError("no_times", "the track's times don't move forward")
    if moving_m / moving_s * 3.6 > MAX_SPEED_KMH:
        raise GpxError("too_fast", f"the track averages more than {MAX_SPEED_KMH} km/h: not a bike ride")

    line = _trim(coords, PRIVACY_TRIM_M)
    tolerance = SIMPLIFY_M
    simple = _simplify(line, tolerance)
    while len(simple) > MAX_POINTS:
        tolerance *= 2
        simple = _simplify(line, tolerance)
    creator = (root.get("creator") or "").strip()[:100] or None
    return Track(coordinates=[[round(lon, 6), round(lat, 6)] for lon, lat in simple], length_m=round(_length(line), 1),
                 moving_s=round(moving_s), recorded_on=timed[0][2].astimezone(LOCAL_TZ).date(), creator=creator)


def is_loop(coords):
    """The ride ends near where it started."""
    return _metres(coords[0], coords[-1]) <= LOOP_M


def preview_line(coords, points=40):
    """At most `points` of `coords`, evenly spaced along the list, for a small drawing of the route's shape."""
    if len(coords) <= points:
        return coords
    step = (len(coords) - 1) / (points - 1)
    return [coords[round(i * step)] for i in range(points)]

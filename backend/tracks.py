"""Where the trains run: the track between each two stations a train calls at in a row, to draw a train trip on the map
along its rails instead of straight from station to station.

The timetable used for departures (backend.transit) comes without line geometry. NVBW publishes the same timetable
with it ("mit Linienverlauf": shapes.txt, a point every ~40 m along the track), but that feed is 70 MB zipped
(400 MB of shapes, mostly buses), so it is not read on every start: once, in the background, the rail tracks are cut out
of it into cache/gtfs_hnv_tracks.json (a few MB) and the download is thrown away. Tracks rarely move: the file is built
again when it is older than REFRESH_DAYS. Until it is there, and between stops it doesn't know, trips are drawn
straight.

The file has a track for each two stop places, also for each part of a station the timetable merges (the platforms of
the Hauptbahnhof and the Stadtbahn stop in front of it have their own). The cuts are not exact: some tracks end short
of their stop, some run on past it. `fitted` trims a track to its two stops and ties it to their marks.

Data: NVBW / MobiData BW, "Soll-Fahrplandaten Verkehrsverbünde BW (einzeln) mit Linienverlauf", HNV
(https://mobidata-bw.de/dataset/soll-fahrplandaten-verkehrsverbunde-bw-einzeln-mit-linienverlauf), GTFS, ODbL.
"""
import csv
import io
import json
import os
import tempfile
import threading
import time
import zipfile
import math
from bisect import bisect_left, bisect_right
from pathlib import Path

import requests
from shapely.geometry import LineString, Point
from shapely.ops import substring

GTFS_URL = "https://www.nvbw.de/fileadmin/user_upload/service/open_data/fahrplandaten_mit_liniennetz/hnv.zip"
TRACKS_PATH = Path(__file__).resolve().parent.parent / "cache" / "gtfs_hnv_tracks.json"
REFRESH_DAYS = 90
RETRY_S = 3600          # after a failed build, wait this long before trying again
SIMPLIFY_DEG = 0.00001  # ~1 m: drops the points of straight track
MAX_END_GAP_M = 250     # a track that comes no nearer than this to one of its stops is not that pair's: drawn straight
SNAP_M = 10             # a trimmed track's end this near its stop's mark is moved onto it; further away, joined to it
M_PER_DEG = 111_320


def fitted(track, a, b):
    """`track` ([[lon, lat], ...], from stop a to stop b) from a's mark to b's and no further: [[lon, lat], ...] that
    starts at `a` and ends at `b` (each (lon, lat)), so that two tracks in a row meet at the mark between them.
    Of the track only the part between the point nearest to a (looked for in its first half) and the point nearest to
    b (in its second half) is kept. None when the track stays more than MAX_END_GAP_M away from a or b."""
    kx = M_PER_DEG * math.cos(math.radians(a[1]))  # metres around a: the pair is a few km at most

    def metres(p):
        return (p[0] - a[0]) * kx, (p[1] - a[1]) * M_PER_DEG

    line = LineString([metres(p) for p in track])
    half = line.length / 2
    if half == 0:
        return None
    pa, pb = Point(metres(a)), Point(metres(b))
    start = substring(line, 0, half).project(pa)
    end = half + substring(line, half, line.length).project(pb)
    first, last = line.interpolate(start), line.interpolate(end)
    if first.distance(pa) > MAX_END_GAP_M or last.distance(pb) > MAX_END_GAP_M:
        return None
    cut = list(substring(line, start, end).coords) if end > start else []
    if cut and first.distance(pa) <= SNAP_M:
        cut = cut[1:]
    if cut and last.distance(pb) <= SNAP_M:
        cut = cut[:-1]
    inner = [[round(a[0] + x / kx, 6), round(a[1] + y / M_PER_DEG, 6)] for x, y in cut]
    return [[a[0], a[1]], *inner, [b[0], b[1]]]


def station_of(stop_id):
    """The stop place a platform's stop_id belongs to (de:08121:26 for de:08121:26:1:1), as backend.transit."""
    return ":".join(stop_id.removesuffix("_Parent").split(":")[:3])


def build_tracks(zip_file, is_train):
    """{"a|b": [[lon, lat], ...]}: the track from stop place a to b, for each two a train of the GTFS feed `zip_file`
    (a path or file) calls at in a row. `is_train(route row)` says which routes are trains."""
    with zipfile.ZipFile(zip_file) as z:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))

        routes = {r["route_id"] for r in rows("routes.txt") if is_train(r)}
        shape_of = {t["trip_id"]: t["shape_id"] for t in rows("trips.txt") if t["route_id"] in routes and t.get("shape_id")}
        calls = {}  # trip -> [(sequence, station, metres along its shape)]
        for st in rows("stop_times.txt"):
            if st["trip_id"] in shape_of and st.get("shape_dist_traveled"):
                calls.setdefault(st["trip_id"], []).append(
                    (int(st["stop_sequence"]), station_of(st["stop_id"]), float(st["shape_dist_traveled"])))
        cuts = {}  # (a, b) -> (shape, from metres, to metres); the first trip that runs a pair gives its track
        for trip, stops in calls.items():
            stops.sort()
            for (_, a, da), (_, b, db) in zip(stops, stops[1:]):
                if a != b and db > da:
                    cuts.setdefault((a, b), (shape_of[trip], da, db))
        wanted = {shape for shape, _, _ in cuts.values()}
        shapes = {}  # shape -> [(metres, sequence, lon, lat)]
        with z.open("shapes.txt") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig")
            header = next(csv.reader([next(text)]))
            col = {name: header.index(name) for name in
                   ("shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence", "shape_dist_traveled")}
            for line in text:  # 6 million lines, mostly buses: look at the id before parsing the line
                if line.split(",", 1)[0].strip('"') not in wanted:
                    continue
                p = next(csv.reader([line]))
                shapes.setdefault(p[col["shape_id"]], []).append(
                    (float(p[col["shape_dist_traveled"]]), int(p[col["shape_pt_sequence"]]),
                     float(p[col["shape_pt_lon"]]), float(p[col["shape_pt_lat"]])))
    for points in shapes.values():
        points.sort()
    tracks = {}
    for (a, b), (shape, da, db) in cuts.items():
        points = shapes.get(shape, [])
        metres = [p[0] for p in points]
        part = [(p[2], p[3]) for p in points[bisect_left(metres, da):bisect_right(metres, db)]]
        if len(part) >= 2:
            line = LineString(part).simplify(SIMPLIFY_DEG)
            tracks[f"{a}|{b}"] = [[round(x, 6), round(y, 6)] for x, y in line.coords]
    return tracks


class Tracks:
    """The tracks file at `path`, built in the background when missing or older than REFRESH_DAYS.
    `fetch(to_path)` downloads the feed with shapes there (tests pass a fake)."""

    def __init__(self, path=TRACKS_PATH, fetch=None, is_train=None, clock=time.time, background=True):
        self.path, self.clock, self.background = Path(path), clock, background
        self.fetch, self.is_train = fetch or self._download, is_train
        self._tracks, self._read_at, self._tried, self._lock = None, None, None, threading.Lock()
        self._fitted = (None, {})  # (the tracks they were made from, {(a, b): fitted track or None})

    @staticmethod
    def _download(to_path):
        with requests.get(GTFS_URL, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(to_path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)

    def _stale(self):
        return not self.path.exists() or self.clock() - self.path.stat().st_mtime > REFRESH_DAYS * 86400

    def _build(self):
        fd, tmp = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        try:
            self.fetch(tmp)
            tracks = build_tracks(tmp, self.is_train)
            if not tracks:
                return  # a feed without shapes: keep what there is
            self.path.parent.mkdir(parents=True, exist_ok=True)
            part = self.path.with_suffix(".part")
            part.write_text(json.dumps({"tracks": tracks}, separators=(",", ":")), encoding="utf-8")
            os.replace(part, self.path)
        except (requests.RequestException, zipfile.BadZipFile, OSError, KeyError, ValueError):
            pass  # trips are drawn straight meanwhile; tried again after RETRY_S
        finally:
            Path(tmp).unlink(missing_ok=True)

    def tracks(self):
        """{(a, b): [[lon, lat], ...]} by stop place, as far as known ({} while the first build runs)."""
        with self._lock:
            if self._stale() and (self._tried is None or self.clock() - self._tried > RETRY_S):
                self._tried = self.clock()
                if self.background:
                    threading.Thread(target=self._build, daemon=True, name="rail-tracks").start()
                else:
                    self._build()
            if self.path.exists() and self._read_at != self.path.stat().st_mtime:
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))["tracks"]
                    self._tracks = {tuple(key.split("|")): line for key, line in raw.items()}
                    self._read_at = self.path.stat().st_mtime
                except (OSError, ValueError, KeyError):
                    pass
            return self._tracks or {}

    def line(self, a, b, at_a, at_b):
        """The way of a train from stop place a to b, whose marks are at_a and at_b ((lon, lat)): its track from
        mark to mark (see fitted), or straight when the pair has no track of its own or the track isn't near both.
        Never another stop's track: the next stop of the same station can be 100 m away."""
        tracks = self.tracks()
        if self._fitted[0] is not tracks:
            self._fitted = (tracks, {})
        cache = self._fitted[1]
        key = (a, b, at_a, at_b)
        if key not in cache:
            track = tracks.get((a, b))
            cache[key] = fitted(track, at_a, at_b) if track and len(track) >= 2 else None
        return cache[key] or [list(at_a), list(at_b)]

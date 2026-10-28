"""Time-dependent shade from 3D buildings (LGL LoD2) and street trees (Baumkataster).

    python -X utf8 -m routing.shadow --download      # fetch all LoD2 tiles of Heilbronn (~300 MB) into cache/lod2/, then compute
    python -X utf8 -m routing.shadow                 # compute from the tiles already there -> data/custom/shadow_heilbronn.json
    python -X utf8 -m routing.shadow --date 2026-10-28 --hours 10 13 16

For every street of routing.shade.road_features() that lies inside the
downloaded LoD2 tiles, sample a point every STEP_M metres (on the centre line and
LANE_OFFSETS_M to both sides) and look from it towards the sun:

- Building: the point is in shadow if the ray towards the sun passes through a building
  footprint before it has climbed above the building's height, i.e. the segment from the
  point, length height / tan(sun altitude), towards the sun crosses the footprint.
- Tree: the crown is a sphere (radius = KRONE_DM / 2, height estimated from crown size,
  the cadastre has no tree heights); the point is in shade if the ray hits a sphere.

shade = shaded samples / all samples, 0 (full sun) .. 1 (fully shaded), per OSM way and time slot.
Streets outside the LoD2 tiles are left out: use routing.shade (static tree canopy) there.

Default slots match HeiGIT's shaded routing (21 July, 09/12/15/18 CEST) so the two can be compared.
No dependencies beyond the standard library.

Data: LGL Baden-Württemberg, 3D-Gebäudemodell LoD2 (opengeodata.lgl-bw.de), dl-de/by-2-0;
Stadt Heilbronn, Baumkataster 01.01.2026, dl-de/by-2-0.
"""
import argparse
import json
import math
import re
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from routing.shade import DATA_DIR, load_trees, osm_way_ids, road_features, to_xy, utm32_to_lonlat

OUT = DATA_DIR / "custom" / "shadow_heilbronn.json"
LOD2_DIR = DATA_DIR.parent / "cache" / "lod2"  # cache/ is git-ignored
LOD2_URL = "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_{e}_{n}_2_bw.zip"
COVER_CELL_M = 100.0            # resolution of the "do we have building data here" grid
CEST = timezone(timedelta(hours=2))

DEFAULT_DATE = "2026-07-21"
DEFAULT_HOURS = (9, 12, 15, 18)

STEP_M = 5.0                    # sampling distance along a street
LANE_OFFSETS_M = (-2.5, 0.0, 2.5)  # where a bike can be: both sides of the centre line
EYE_M = 1.2                     # height of the rider's head/torso that we want in shade
MIN_SUN_ALT = 3.0               # below this the sun is behind terrain/haze anyway: all shade
MAX_SHADOW_M = 250.0            # longest shadow we trace
CELL_M = 40.0                   # spatial grid for buildings and trees
MIN_COVERAGE = 0.5              # keep a way when at least this share of its samples has building data

LAT0 = 49.14                    # Heilbronn, for the sun position
LON0 = 9.22


# ------------------------------------------------------------- sun -----

def sun_position(when, lat=LAT0, lon=LON0):
    """(azimuth from north clockwise, altitude) in degrees. NOAA solar equations, ~0.1 deg."""
    t = when.astimezone(timezone.utc)
    jd = t.timestamp() / 86400 + 2440587.5
    jc = (jd - 2451545) / 36525
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * jc) + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    eps = math.radians(eps0 + 0.00256 * math.cos(math.radians(omega)))
    decl = math.asin(math.sin(eps) * math.sin(math.radians(app_long)))
    y = math.tan(eps / 2) ** 2
    l0r = math.radians(l0)
    eq_time = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(mr)
                               + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
                               - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    minutes = t.hour * 60 + t.minute + t.second / 60
    hour_angle = math.radians((minutes + eq_time + 4 * lon) / 4 - 180)
    latr = math.radians(lat)
    cos_zen = math.sin(latr) * math.sin(decl) + math.cos(latr) * math.cos(decl) * math.cos(hour_angle)
    zen = math.acos(max(-1.0, min(1.0, cos_zen)))
    az = math.degrees(math.atan2(math.sin(hour_angle),
                                 math.cos(hour_angle) * math.sin(latr) - math.tan(decl) * math.cos(latr))) + 180
    return az % 360, 90 - math.degrees(zen)


def toward_sun(azimuth):
    """Unit vector (east, north) pointing at the sun on the ground."""
    a = math.radians(azimuth)
    return math.sin(a), math.cos(a)


# ------------------------------------------------------------- buildings --

_SPLIT = re.compile(r"<bldg:(?:Building|BuildingPart)[ >]")
_HEIGHT = re.compile(r"<bldg:measuredHeight[^>]*>([\d.]+)<")
_GROUND = re.compile(r"<bldg:GroundSurface.*?</bldg:GroundSurface>", re.S)
_POSLIST = re.compile(r"<gml:posList[^>]*>([^<]+)<")
_TILE = re.compile(r"LoD2_32_(\d+)_(\d+)_(\d)_", re.I)


def _utm_to_xy(e, n):
    return to_xy(*utm32_to_lonlat(e, n))


def lonlat_to_utm32(lon, lat):
    """(lon, lat) -> ETRS89 / UTM zone 32N (easting, northing) in metres, standard series (~mm)."""
    a, f, k0 = 6378137.0, 1 / 298.257222101, 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    phi, lam = math.radians(lat), math.radians(lon - 9)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t, c = math.tan(phi) ** 2, ep2 * math.cos(phi) ** 2
    aa = math.cos(phi) * lam
    m = a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
             + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
             - (35 * e2**3 / 3072) * math.sin(6 * phi))
    east = 500_000 + k0 * n * (aa + (1 - t + c) * aa**3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * ep2) * aa**5 / 120)
    north = k0 * (m + n * math.tan(phi) * (aa * aa / 2 + (5 - t + 9 * c + 4 * c * c) * aa**4 / 24
                                           + (61 - 58 * t + t * t + 600 * c - 330 * ep2) * aa**6 / 720))
    return east, north


def tiles_for_roads(roads):
    """The 2 km LoD2 download tiles (east km, north km) that the streets run through.

    LGL names a 2 km tile by its south-west corner: odd east km, even north km (e.g. 515_5442)."""
    tiles = set()
    for f in roads:
        for lon, lat in f["geometry"]["coordinates"]:
            east, north = lonlat_to_utm32(lon, lat)
            e, n = int(east // 1000), int(north // 1000)
            tiles.add((e if e % 2 else e - 1, n if n % 2 == 0 else n - 1))
    return sorted(tiles)


def download_tiles(tiles, dest=LOD2_DIR, have=()):
    """Download the LoD2 zips for `tiles` into `dest`; skips tiles already on disk and tiles LGL doesn't serve."""
    dest.mkdir(parents=True, exist_ok=True)
    have = {p.name.lower() for p in have}
    session = requests.Session()
    for i, (e, n) in enumerate(tiles, 1):
        url = LOD2_URL.format(e=e, n=n)
        path = dest / url.rsplit("/", 1)[1]
        if path.exists() or path.name.lower() in have:
            continue
        for attempt in range(3):
            try:
                r = session.get(url, timeout=120)
                break
            except requests.RequestException as err:
                if attempt == 2:
                    print(f"  [{i}/{len(tiles)}] {path.name}: failed ({err}), skipped")
                    r = None
                time.sleep(2)
        if r is None:
            continue
        if r.status_code == 404:
            print(f"  [{i}/{len(tiles)}] {path.name}: not available, skipped")
            continue
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        print(f"  [{i}/{len(tiles)}] {path.name}: {len(r.content) / 1e6:.1f} MB")


def parse_gml(text):
    """Footprints of one CityGML file: list of (polygon [(x, y), ...] in local metres, height m)."""
    out = []
    for chunk in _SPLIT.split(text)[1:]:
        h = _HEIGHT.search(chunk)
        if not h:
            continue
        height = float(h.group(1))
        if height < 2:  # walls, bridges, shelters
            continue
        for ground in _GROUND.findall(chunk):
            for pl in _POSLIST.findall(ground):
                v = [float(x) for x in pl.split()]
                ring = [_utm_to_xy(v[i], v[i + 1]) for i in range(0, len(v) - 2, 3)]
                if len(ring) >= 4:
                    out.append((ring, height))
    return out


def load_buildings(zips):
    """(buildings, tiles) from LoD2 zips. tiles = list of covered rectangles (x0, y0, x1, y1) in local metres."""
    buildings, tiles = [], []
    for path in zips:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.lower().endswith(".gml"):
                    continue
                buildings += parse_gml(z.read(name).decode("utf-8"))
                m = _TILE.search(Path(name).name)
                if m:  # file tiles are 1 km x 1 km: LoD2_32_<E km>_<N km>_1_BW.gml
                    e, n, size = (int(g) for g in m.groups())
                    corners = [_utm_to_xy(e * 1000 + dx, n * 1000 + dy)
                               for dx in (0, size * 1000) for dy in (0, size * 1000)]
                    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
                    tiles.append((min(xs), min(ys), max(xs), max(ys)))
    return buildings, tiles


class BuildingIndex:
    def __init__(self, buildings):
        self.items = []
        self.grid = defaultdict(list)
        for ring, h in buildings:
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            i = len(self.items)
            self.items.append((ring, h, bbox))
            for cx in range(int(bbox[0] // CELL_M), int(bbox[2] // CELL_M) + 1):
                for cy in range(int(bbox[1] // CELL_M), int(bbox[3] // CELL_M) + 1):
                    self.grid[(cx, cy)].append(i)
        self.max_h = max((h for _, h in buildings), default=0)

    def candidates(self, x, y, ux, uy, length):
        seen = set()
        n = int(length / (CELL_M / 4)) + 1
        for k in range(n + 1):
            t = min(length, k * CELL_M / 4)
            cell = (int((x + ux * t) // CELL_M), int((y + uy * t) // CELL_M))
            for i in self.grid.get(cell, ()):
                if i not in seen:
                    seen.add(i)
                    yield self.items[i]

    def shades(self, x, y, ux, uy, tan_alt):
        reach = min(MAX_SHADOW_M, self.max_h / tan_alt)
        qx, qy = x + ux * reach, y + uy * reach
        for ring, h, (bx0, by0, bx1, by1) in self.candidates(x, y, ux, uy, reach):
            length = min(MAX_SHADOW_M, h / tan_alt)
            ex, ey = x + ux * length, y + uy * length
            if max(x, ex) < bx0 or min(x, ex) > bx1 or max(y, ey) < by0 or min(y, ey) > by1:
                continue
            if _point_in_ring(x, y, ring) or _segment_hits_ring(x, y, ex, ey, ring):
                return True
        return False


def _point_in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segment_hits_ring(x1, y1, x2, y2, ring):
    def orient(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        d1 = orient(ax, ay, bx, by, x1, y1)
        d2 = orient(ax, ay, bx, by, x2, y2)
        d3 = orient(x1, y1, x2, y2, ax, ay)
        d4 = orient(x1, y1, x2, y2, bx, by)
        if (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0):
            return True
    return False


# ------------------------------------------------------------- trees ------

def tree_height(crown_radius):
    """The cadastre has no heights: a rough street-tree rule, crown diameter 5 m -> ~9.5 m, 10 m -> ~17 m."""
    return max(4.0, min(25.0, 3.0 * crown_radius + 2.0))


class TreeIndex:
    def __init__(self, trees):
        self.grid = defaultdict(list)
        self.max_top = 0.0
        self.max_r = 0.0
        for x, y, r in trees:
            h = tree_height(r)
            zc = h - r
            self.grid[(int(x // CELL_M), int(y // CELL_M))].append((x, y, zc, r))
            self.max_top, self.max_r = max(self.max_top, h), max(self.max_r, r)

    def shades(self, x, y, vx, vy, vz, tan_alt):
        reach = min(MAX_SHADOW_M, (self.max_top - EYE_M) / tan_alt) + self.max_r
        ux, uy = toward_sun_unit(vx, vy)
        seen = set()
        n = int(reach / (CELL_M / 2)) + 1
        for k in range(n + 1):
            t = min(reach, k * CELL_M / 2)
            cx, cy = int((x + ux * t) // CELL_M), int((y + uy * t) // CELL_M)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cell = (cx + dx, cy + dy)
                    if cell in seen:
                        continue
                    seen.add(cell)
                    for tx, ty, tz, r in self.grid.get(cell, ()):
                        wx, wy, wz = tx - x, ty - y, tz - EYE_M
                        along = wx * vx + wy * vy + wz * vz
                        if along <= 0:
                            continue
                        if wx * wx + wy * wy + wz * wz - along * along <= r * r:
                            return True
        return False


def toward_sun_unit(vx, vy):
    n = math.hypot(vx, vy) or 1.0
    return vx / n, vy / n


# ------------------------------------------------------------- streets ----

def sample_points(coords, step=STEP_M, offsets=LANE_OFFSETS_M):
    """Points every `step` m along a [lon, lat] LineString, shifted sideways by each offset."""
    xy = [to_xy(lon, lat) for lon, lat in coords]
    pts = []
    carry = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        if seg == 0:
            continue
        nx, ny = -(y2 - y1) / seg, (x2 - x1) / seg
        d = carry
        while d <= seg:
            px, py = x1 + (x2 - x1) * d / seg, y1 + (y2 - y1) * d / seg
            pts.extend((px + nx * o, py + ny * o) for o in offsets)
            d += step
        carry = d - seg
    if not pts and xy:
        pts = [xy[len(xy) // 2]]
    return pts


def coverage_grid(tiles):
    """Set of COVER_CELL_M cells whose centre lies inside one of the tile rectangles."""
    cells = set()
    for x0, y0, x1, y1 in tiles:
        for cx in range(int(x0 // COVER_CELL_M), int(x1 // COVER_CELL_M) + 1):
            for cy in range(int(y0 // COVER_CELL_M), int(y1 // COVER_CELL_M) + 1):
                mx, my = (cx + 0.5) * COVER_CELL_M, (cy + 0.5) * COVER_CELL_M
                if x0 <= mx <= x1 and y0 <= my <= y1:
                    cells.add((cx, cy))
    return cells


def _covered(x, y, cells):
    return (int(x // COVER_CELL_M), int(y // COVER_CELL_M)) in cells


def shade_slots(roads, buildings, trees, tiles, times):
    """{way_id: [shade per time]} for ways inside the tiles."""
    cells = coverage_grid(tiles)
    suns = []
    for when in times:
        az, alt = sun_position(when)
        ux, uy = toward_sun(az)
        tan_alt = math.tan(math.radians(max(alt, 0.01)))
        ca, sa = math.cos(math.radians(alt)), math.sin(math.radians(alt))
        suns.append((alt, ux, uy, tan_alt, (ux * ca, uy * ca, sa)))

    acc = defaultdict(lambda: [0, 0, [0] * len(times)])  # way -> [samples, covered, shaded per slot]
    start = time.time()
    for k, f in enumerate(roads, 1):
        if k % 5000 == 0:
            print(f"  {k:,}/{len(roads):,} streets, {time.time() - start:.0f} s")
        pts = sample_points(f["geometry"]["coordinates"])
        covered = [p for p in pts if _covered(p[0], p[1], cells)]
        if len(covered) < MIN_COVERAGE * len(pts):
            continue
        shaded = [0] * len(times)
        for x, y in covered:
            for s, (alt, ux, uy, tan_alt, v) in enumerate(suns):
                if (alt < MIN_SUN_ALT or buildings.shades(x, y, ux, uy, tan_alt)
                        or trees.shades(x, y, *v, tan_alt)):
                    shaded[s] += 1
        for way in osm_way_ids(f["properties"]["osmid"]):
            a = acc[way]
            a[0] += len(pts)
            a[1] += len(covered)
            for s in range(len(times)):
                a[2][s] += shaded[s]
    return {w: [round(c / cov, 3) for c in sh] for w, (n, cov, sh) in acc.items() if cov}


# ------------------------------------------------------------- lookup -----

def load_shadow(path=OUT):
    """(slots, {way_id: [shade per slot]}) as written by main()."""
    d = json.loads(Path(path).read_text())
    return d["slots"], {int(k): v for k, v in d["ways"].items()}


def slot_index(slots, hour):
    """Index of the slot closest to `hour` (0-23), e.g. for the departure time."""
    hours = [int(s.split("T")[1][:2]) for s in slots]
    return min(range(len(hours)), key=lambda i: abs(hours[i] - hour))


def edge_shadow(osmid, ways, slot, default=None):
    """Mean shade (0-1) of the OSM ways of a graph edge at slot index `slot`, or `default`
    when none of them lies inside the LoD2 tiles (then fall back to routing.shade)."""
    ids = osmid if isinstance(osmid, list) else [osmid]
    known = [ways[i][slot] for i in ids if i in ways]
    return sum(known) / len(known) if known else default


# ------------------------------------------------------------- main -------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zips", nargs="*", type=Path, help="LoD2 zips (default: cache/lod2/*.zip and data/LoD2_*.zip)")
    ap.add_argument("--download", action="store_true",
                    help=f"first download every LoD2 tile Heilbronn's streets run through into {LOD2_DIR}")
    ap.add_argument("--trees", type=Path, help="Baumkataster zip (default: download / cached)")
    ap.add_argument("--date", default=DEFAULT_DATE)
    ap.add_argument("--hours", type=int, nargs="+", default=list(DEFAULT_HOURS), help="local time (CEST)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    roads = road_features()

    def found():
        return sorted(LOD2_DIR.glob("LoD2_*.zip")) + sorted(DATA_DIR.glob("LoD2_*.zip"))

    if args.download:
        tiles = tiles_for_roads(roads)
        print(f"Downloading {len(tiles)} LoD2 tiles into {LOD2_DIR} (skips the ones already there)")
        download_tiles(tiles, have=found())
    zips = args.zips or found()
    if not zips:
        raise SystemExit("No LoD2 tiles found: run with --download, or put e.g. "
                         "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_515_5442_2_bw.zip into data/")
    day = datetime.fromisoformat(args.date)
    times = [day.replace(hour=h, tzinfo=CEST) for h in args.hours]

    print(f"Reading {len(zips)} LoD2 zip(s) ...")
    blds, tiles = load_buildings(zips)
    print(f"{len(blds):,} building footprints")
    trees = load_trees(args.trees)
    print(f"{len(trees):,} trees")
    print("Tracing shadows ...")
    ways = shade_slots(roads, BuildingIndex(blds), TreeIndex(trees), tiles, times)

    slots = [t.isoformat(timespec="minutes") for t in times]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "slots": slots,
        "sun": [dict(zip(("azimuth", "altitude"), (round(v, 1) for v in sun_position(t)))) for t in times],
        "source": "LGL BW LoD2 (dl-de/by-2-0), Stadt Heilbronn Baumkataster 2026 (dl-de/by-2-0)",
        "ways": {str(k): v for k, v in ways.items()},
    }))
    print(f"{len(ways):,} OSM ways -> {args.out}")
    for i, s in enumerate(slots):
        vals = sorted(v[i] for v in ways.values())
        print(f"  {s}: median shade {vals[len(vals) // 2]:.2f}")


if __name__ == "__main__":
    main()

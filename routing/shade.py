"""Street-tree shade per OSM way, from the Heilbronn Baumkataster (tree cadastre).

    python -X utf8 -m routing.shade          # downloads the cadastre, writes data/custom/shade_heilbronn.json

Idea: walk along every street of road_features() in 5 m steps
and count a step as shaded when a tree crown reaches the street corridor, i.e. the
tree stands within (crown radius + SIDE_M) of the street centre line.
shade = shaded steps / all steps, from 0 (full sun) to 1 (fully under trees).

No extra dependencies: the shapefile is read with the standard library, and
coordinates use a local flat projection (error well under 1 % at city scale).

Data: Stadt Heilbronn, Baumkataster, Stand 01.01.2026, dl-de/by-2-0
https://opendata.heilbronn.de/dataset/baumkataster
Caveat: trees not maintained by the city often only have a default 2 m crown,
so shade is underestimated there.
"""
import ast
import json
import math
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

import requests


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TREES_URL = (
    "https://opendata.heilbronn.de/sites/default/files/"
    "SHAPE_BKA_HN20260101_EPSG4326.zip"
)
TREES_ZIP = DATA_DIR.parent / "cache" / "baumkataster_heilbronn_2026.zip"  # cache/ is git-ignored
ROADS = DATA_DIR / "ready-made" / "road_network_heilbronn.geojson"
OUT = DATA_DIR / "custom" / "shade_heilbronn.json"

STEP_M = 5.0        # sampling distance along a street
SIDE_M = 4.0        # tree may stand this far beside the corridor and still shade it
MIN_CROWN_M = 2.0   # crown diameter used when the cadastre has none
CELL_M = 30.0       # spatial grid cell size

# Local flat projection around Heilbronn (lon/lat degrees -> metres).
LON0, LAT0 = 9.22, 49.14
M_PER_DEG_LAT = 111_132.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


def osm_way_ids(osmid):
    """`osmid` is a string: either "83738619" or a merged list "[439572396, 401802699]" (same as routing.costs)."""
    s = str(osmid)
    return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]


def to_xy(lon, lat):
    return (lon - LON0) * M_PER_DEG_LON, (lat - LAT0) * M_PER_DEG_LAT


def utm32_to_lonlat(e, n):
    """ETRS89 / UTM zone 32N (EPSG:25832) -> (lon, lat), standard series inverse (~mm accuracy)."""
    a, f, k0, lon0 = 6378137.0, 1 / 298.257222101, 0.9996, math.radians(9)
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x, y = e - 500_000.0, n
    m = y / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
            + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
            + (151 * e1**3 / 96) * math.sin(6 * mu))
    s, c, t = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * s * s)
    t1, c1 = t * t, ep2 * c * c
    r1 = a * (1 - e2) / (1 - e2 * s * s) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * t / r1) * (d * d / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * ep2) * d**4 / 24
                                 + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * ep2 - 3 * c1 * c1) * d**6 / 720)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d**3 / 6
                  + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * ep2 + 24 * t1 * t1) * d**5 / 120) / c
    return math.degrees(lon), math.degrees(lat)


# ---------------------------------------------------------------- trees ----

def download_trees(path=TREES_ZIP):
    if not path.exists():
        print(f"Downloading Baumkataster -> {path.name}")
        r = requests.get(TREES_URL, timeout=120)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    return path


def _read_dbf(raw):
    """Minimal dBASE reader -> list of dicts (strings)."""
    n_rec, h_len, r_len = struct.unpack("<IHH", raw[4:12])
    fields, off = [], 32
    while raw[off] != 0x0D:
        name = raw[off:off + 11].split(b"\0")[0].decode("ascii")
        fields.append((name, raw[off + 16]))
        off += 32
    rows = []
    for i in range(n_rec):
        pos = h_len + i * r_len + 1  # skip deletion flag
        row = {}
        for name, length in fields:
            row[name] = raw[pos:pos + length].decode("utf-8", "replace").strip()
            pos += length
        rows.append(row)
    return rows


def _read_point_shp(raw):
    """Minimal reader for a POINT shapefile -> list of (lon, lat)."""
    pts, pos = [], 100
    while pos < len(raw):
        _, content_words = struct.unpack(">ii", raw[pos:pos + 8])
        shape_type = struct.unpack("<i", raw[pos + 8:pos + 12])[0]
        if shape_type == 1:
            pts.append(struct.unpack("<dd", raw[pos + 12:pos + 28]))
        else:  # null shape
            pts.append(None)
        pos += 8 + content_words * 2
    return pts


def load_trees(path=None):
    """List of (x, y, crown_radius_m) in local metres.

    Accepts either cadastre zip: WGS84 (EPSG:4326) or UTM32N (EPSG:25832).
    """
    path = path or download_trees()
    with zipfile.ZipFile(path) as z:
        shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
        dbf = shp[:-4] + ".dbf"
        prj = shp[:-4] + ".prj"
        is_utm = prj in z.namelist() and b"UTM" in z.read(prj).upper()
        pts = _read_point_shp(z.read(shp))
        rows = _read_dbf(z.read(dbf))
    trees = []
    for pt, row in zip(pts, rows):
        if pt is None:
            continue
        if is_utm:
            pt = utm32_to_lonlat(*pt)
        try:
            crown = float(row.get("KRONE_DM") or 0)
        except ValueError:
            crown = 0.0
        x, y = to_xy(*pt)
        trees.append((x, y, max(crown, MIN_CROWN_M) / 2))
    return trees


def build_grid(trees):
    grid = defaultdict(list)
    for t in trees:
        grid[(int(t[0] // CELL_M), int(t[1] // CELL_M))].append(t)
    return grid


def is_shaded(x, y, grid):
    cx, cy = int(x // CELL_M), int(y // CELL_M)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for tx, ty, r in grid.get((cx + dx, cy + dy), ()):
                reach = r + SIDE_M
                if (tx - x) ** 2 + (ty - y) ** 2 <= reach * reach:
                    return True
    return False


# ---------------------------------------------------------------- roads ----

def road_features(G=None):
    """Streets to compute shade for, as GeoJSON-like features with an "osmid" property.

    The ATRAI road network (data/ready-made), plus the bike graph's edges on OSM ways it doesn't have,
    such as the rideable footways routing.graph adds; without them ~12 % of the graph's ways get no shade.
    """
    roads = json.loads(ROADS.read_text(encoding="utf-8"))["features"]
    if G is None:
        from routing.graph import load_graph  # osmnx, only needed here
        G = load_graph()
    have = {w for f in roads for w in osm_way_ids(f["properties"]["osmid"])}
    seen = set()
    for u, v, d in G.edges(data=True):
        ids = d["osmid"] if isinstance(d["osmid"], list) else [d["osmid"]]
        street = (min(u, v), max(u, v), str(ids))
        if street in seen or all(int(i) in have for i in ids):
            continue  # each street once, not once per direction
        seen.add(street)
        coords = (list(d["geometry"].coords) if "geometry" in d
                  else [(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])
        missing = [int(i) for i in ids if int(i) not in have]
        osmid = str(missing[0]) if len(missing) == 1 else str(missing)
        roads.append({"geometry": {"coordinates": coords}, "properties": {"osmid": osmid}})
    return roads


def line_shade(coords, grid):
    """(shade ratio 0-1, length in m) of one LineString given as [lon, lat] pairs."""
    xy = [to_xy(lon, lat) for lon, lat in coords]
    shaded = total = 0
    length = 0.0
    carry = 0.0  # distance into the current segment where the next sample sits
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        d = carry
        while d <= seg:
            t = d / seg if seg else 0
            total += 1
            shaded += is_shaded(x1 + t * (x2 - x1), y1 + t * (y2 - y1), grid)
            d += STEP_M
        carry = d - seg
        length += seg
    if total == 0:  # very short street: test its midpoint
        mx, my = xy[len(xy) // 2]
        return float(is_shaded(mx, my, grid)), length
    return shaded / total, length


def way_shade(road_features, grid):
    """Length-weighted shade ratio per OSM way id."""
    acc = defaultdict(lambda: [0.0, 0.0])  # way -> [shade*length, length]
    for f in road_features:
        ratio, length = line_shade(f["geometry"]["coordinates"], grid)
        for way in osm_way_ids(f["properties"]["osmid"]):
            acc[way][0] += ratio * length
            acc[way][1] += length
    return {w: (s / L if L else 0.0) for w, (s, L) in acc.items()}


def edge_shade(osmid, way_sh, default=0.0):
    """Mean shade of the OSM ways a graph edge is made of (same convention as costs.edge_roughness)."""
    ids = osmid if isinstance(osmid, list) else [osmid]
    known = [way_sh[i] for i in ids if i in way_sh]
    return sum(known) / len(known) if known else default


def load_way_shade(path=OUT):
    """{way_id: shade} as written by main(); JSON keys are strings, so convert back to int."""
    return {int(k): v for k, v in json.loads(Path(path).read_text()).items()}


def main():
    import sys
    # Optional: python -m routing.shade path\to\SHAPE_BKA_...zip  (either projection)
    trees = load_trees(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(f"{len(trees):,} trees loaded")
    grid = build_grid(trees)
    roads = road_features()
    shade = way_shade(roads, grid)
    OUT.write_text(json.dumps({str(k): round(v, 3) for k, v in shade.items()}))
    vals = sorted(shade.values())
    print(f"{len(shade):,} OSM ways -> {OUT.name}")
    print(f"median shade {vals[len(vals) // 2]:.2f}, "
          f"ways with any shade {sum(v > 0 for v in vals) / len(vals):.0%}")


if __name__ == "__main__":
    main()

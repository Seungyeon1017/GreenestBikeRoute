"""Street-tree shade per OSM way, from the Heilbronn Baumkataster (tree cadastre).

    python -X utf8 -m routing.shade          # downloads the cadastre, writes data/shade_heilbronn.json

Idea: walk along every street of data/road_network_heilbronn.geojson in 5 m steps
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
import io
import json
import math
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

import requests

from routing.costs import osm_way_ids

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TREES_URL = (
    "https://opendata.heilbronn.de/sites/default/files/"
    "SHAPE_BKA_HN20260101_EPSG4326.zip"
)
TREES_ZIP = DATA_DIR / "baumkataster_heilbronn_2026.zip"
ROADS = DATA_DIR / "road_network_heilbronn.geojson"
OUT = DATA_DIR / "shade_heilbronn.json"

STEP_M = 5.0        # sampling distance along a street
SIDE_M = 4.0        # tree may stand this far beside the corridor and still shade it
MIN_CROWN_M = 2.0   # crown diameter used when the cadastre has none
CELL_M = 30.0       # spatial grid cell size

# Local flat projection around Heilbronn (lon/lat degrees -> metres).
LON0, LAT0 = 9.22, 49.14
M_PER_DEG_LAT = 111_132.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


def to_xy(lon, lat):
    return (lon - LON0) * M_PER_DEG_LON, (lat - LAT0) * M_PER_DEG_LAT


# ---------------------------------------------------------------- trees ----

def download_trees(path=TREES_ZIP):
    if not path.exists():
        print(f"Downloading Baumkataster -> {path.name}")
        r = requests.get(TREES_URL, timeout=120)
        r.raise_for_status()
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
    """List of (x, y, crown_radius_m) in local metres."""
    path = path or download_trees()
    with zipfile.ZipFile(path) as z:
        shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
        dbf = shp[:-4] + ".dbf"
        pts = _read_point_shp(z.read(shp))
        rows = _read_dbf(z.read(dbf))
    trees = []
    for pt, row in zip(pts, rows):
        if pt is None:
            continue
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
    trees = load_trees()
    print(f"{len(trees):,} trees loaded")
    grid = build_grid(trees)
    roads = json.loads(ROADS.read_text(encoding="utf-8"))["features"]
    shade = way_shade(roads, grid)
    OUT.write_text(json.dumps({str(k): round(v, 3) for k, v in shade.items()}))
    vals = sorted(shade.values())
    print(f"{len(shade):,} OSM ways -> {OUT.name}")
    print(f"median shade {vals[len(vals) // 2]:.2f}, "
          f"ways with any shade {sum(v > 0 for v in vals) / len(vals):.0%}")


if __name__ == "__main__":
    main()

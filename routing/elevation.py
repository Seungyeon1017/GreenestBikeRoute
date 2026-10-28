"""Ground height of every bike-graph node from the LGL DGM1 terrain model, to show grade along a route.

    python -X utf8 -m routing.elevation --download   # fetch the DGM1 tiles the graph touches (~516 MB) into cache/dgm1/, then compute
    python -X utf8 -m routing.elevation              # compute from the tiles already there -> data/custom/elevation_heilbronn.json

Display only: grade does not enter the route cost (see routing/README.md, "Grade").

DGM1: one height per 1 m x 1 m cell (cell centre), ETRS89 / UTM32 (EPSG:25832), heights NHN (DHHN2016),
+/- 15 cm. A 2 km download tile holds four 1 km .xyz files, `east north height` per line,
north-descending then east-ascending. Each node gets the height of the cell it lies in.

The terrain model is bare ground: a node on a bridge would get the river or railway below it,
a node in a tunnel the hill above it. Nodes that only touch bridge/tunnel edges are therefore
interpolated along the structure between its ends (the nodes that also touch normal streets),
weighted by distance.

Data: LGL Baden-Württemberg, Digitales Geländemodell DGM1 (opengeodata.lgl-bw.de),
"Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0".
"""
import argparse
import io
import json
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import networkx as nx
import pandas as pd
import requests

from routing.shade import DATA_DIR
from routing.shadow import lonlat_to_utm32

OUT = DATA_DIR / "custom" / "elevation_heilbronn.json"
DGM1_DIR = DATA_DIR.parent / "cache" / "dgm1"  # cache/ is git-ignored
DGM1_URL = "https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_{e}_{n}_2_bw.zip"
CELLS = 1000  # an .xyz file is 1 km x 1 km of 1 m cells
SOURCE = "LGL BW DGM1 (Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0)"


def utm(G, n):
    return lonlat_to_utm32(G.nodes[n]["x"], G.nodes[n]["y"])


def tile_2km(east, north):
    """The 2 km download tile (east km, north km) holding a point: named by its south-west corner,
    odd east km and even north km (e.g. 515_5442), like the LoD2 tiles in routing.shadow."""
    e, n = int(east // 1000), int(north // 1000)
    return e if e % 2 else e - 1, n if n % 2 == 0 else n - 1


def graph_tiles(G):
    return sorted({tile_2km(*utm(G, n)) for n in G.nodes})


def download_tiles(tiles, dest=DGM1_DIR, workers=6):
    """Download the DGM1 zips for `tiles` into `dest`, a few at a time; skips the ones already there."""
    dest.mkdir(parents=True, exist_ok=True)

    def fetch(tile):
        url = DGM1_URL.format(e=tile[0], n=tile[1])
        path = dest / url.rsplit("/", 1)[1]
        if path.exists():
            return f"{path.name}: already there"
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=300)
                break
            except requests.RequestException as err:
                if attempt == 2:
                    return f"{path.name}: failed ({err}), skipped"
        if r.status_code == 404:
            return f"{path.name}: not available, skipped"
        r.raise_for_status()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        return f"{path.name}: {len(r.content) / 1e6:.1f} MB"

    with ThreadPoolExecutor(workers) as pool:
        for i, msg in enumerate(pool.map(fetch, tiles), 1):
            print(f"  [{i}/{len(tiles)}] {msg}")


def read_xyz(f):
    """(west, north, heights) of one 1 km .xyz file: heights[row, col] is the cell whose centre is
    (west + col + 0.5, north - row - 0.5)."""
    xyz = pd.read_csv(f, sep=r"\s+", header=None, names=["e", "n", "h"], dtype=float).to_numpy()
    if len(xyz) != CELLS * CELLS:
        raise ValueError(f"expected {CELLS * CELLS:,} cells, got {len(xyz):,}")
    west, north = xyz[0, 0] - 0.5, xyz[0, 1] + 0.5
    return west, north, xyz[:, 2].reshape(CELLS, CELLS)


def ground_heights(G, zips):
    """{node: terrain height in m} for every node inside the tiles; reads each 1 km file once."""
    by_km = defaultdict(list)
    for n in G.nodes:
        east, north = utm(G, n)
        by_km[(int(east // 1000), int(north // 1000))].append((n, east, north))
    heights = {}
    for path in zips:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.lower().endswith(".xyz"):
                    continue
                parts = Path(name).name.split("_")  # dgm1_32_<E km>_<N km>_1_bw_<year>.xyz
                nodes = by_km.get((int(parts[2]), int(parts[3])))
                if not nodes:
                    continue
                west, north, h = read_xyz(io.BytesIO(z.read(name)))
                for n, e, no in nodes:
                    col = min(CELLS - 1, int(e - west))
                    row = min(CELLS - 1, int(north - no))
                    heights[n] = float(h[row, col])
    return heights


def is_structure(d):
    """A bridge or tunnel edge: the terrain model doesn't describe its height."""
    return any(d.get(tag) not in (None, "no") for tag in ("bridge", "tunnel"))


def structure_nodes(G):
    """Nodes whose every edge is a bridge or tunnel: the terrain under/over them is not the street."""
    on, off = set(), set()
    for u, v, d in G.edges(data=True):
        (on if is_structure(d) else off).update((u, v))
    return on - off


def fix_structures(G, heights):
    """Replace the terrain height of bridge/tunnel interior nodes by the distance-weighted mean of
    the two closest structure ends (nodes on the structure that also touch normal streets).
    On a simple bridge this is the straight line between its two abutments. Returns the fixed nodes."""
    inner = structure_nodes(G)
    S = nx.Graph()
    for u, v, d in G.edges(data=True):
        length = float(d["length"])
        if is_structure(d) and (not S.has_edge(u, v) or length < S.edges[u, v]["length"]):
            S.add_edge(u, v, length=length)
    fixed = {}
    for comp in nx.connected_components(S):
        ends = [n for n in comp if n not in inner and n in heights]
        dist = defaultdict(list)  # node -> [(distance, end height)]
        for end in ends:
            for n, d in nx.single_source_dijkstra_path_length(S, end, weight="length").items():
                if n in inner:
                    dist[n].append((d, heights[end]))
        for n, pairs in dist.items():
            nearest = sorted(pairs)[:2]
            if nearest[0][0] == 0 or len(nearest) == 1:
                fixed[n] = nearest[0][1]
            else:
                w = [1 / d for d, _ in nearest]
                fixed[n] = sum(wi * h for wi, (_, h) in zip(w, nearest)) / sum(w)
    heights.update(fixed)
    return fixed


def load_elevation(path=OUT):
    """{node id: height in m} as written by main(), or {} if the file is missing."""
    path = Path(path)
    if not path.exists():
        return {}
    return {int(k): v for k, v in json.loads(path.read_text())["nodes"].items()}


def attach_elevation(G, heights):
    """Set node attribute `elevation` (m above sea level, or None outside the tiles), keeping values already set."""
    for n, d in G.nodes(data=True):
        if d.get("elevation") is None:
            d["elevation"] = heights.get(int(n))


def main(argv=None):
    from routing.graph import load_graph  # needs the cached graph; keep the module importable without it

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--download", action="store_true",
                    help=f"first download every DGM1 tile the bike graph touches into {DGM1_DIR}")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    G = load_graph()
    tiles = graph_tiles(G)
    if args.download:
        print(f"Downloading {len(tiles)} DGM1 tiles into {DGM1_DIR} (skips the ones already there)")
        download_tiles(tiles)
    zips = sorted(DGM1_DIR.glob("dgm1_*.zip"))
    if not zips:
        raise SystemExit("No DGM1 tiles found: run with --download")

    print(f"Reading {len(zips)} DGM1 zip(s) for {G.number_of_nodes():,} nodes ...")
    heights = ground_heights(G, zips)
    missing = G.number_of_nodes() - len(heights)
    terrain = dict(heights)
    fixed = fix_structures(G, heights)
    print(f"{len(heights):,} nodes, {missing} outside the tiles, {len(fixed)} bridge/tunnel nodes interpolated "
          f"(moved by up to {max((abs(h - terrain[n]) for n, h in fixed.items()), default=0):.1f} m)")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": SOURCE,
        "unit": "m above sea level (NHN, DHHN2016)",
        "nodes": {str(n): round(h, 2) for n, h in sorted(heights.items())},
    }, separators=(",", ":")))
    print(f"-> {args.out} ({args.out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()

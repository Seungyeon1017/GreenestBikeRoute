"""Ground height of every bike-graph node from the LGL DGM1 terrain model, to show grade along a route.

    python -X utf8 -m routing.elevation --download   # fetch the DGM1 tiles the graph touches (~516 MB) into cache/dgm1/, then compute
    python -X utf8 -m routing.elevation              # compute from the tiles already there -> data/custom/elevation_heilbronn.json

Display only: grade does not enter the route cost (see routing/README.md, "Grade").

DGM1: one height per 1 m x 1 m cell (cell centre), ETRS89 / UTM32 (EPSG:25832), heights NHN (DHHN2016),
+/- 15 cm. A 2 km download tile holds four 1 km .xyz files, `east north height` per line,
north-descending then east-ascending. Each node gets the height of the cell it lies in.

The terrain model is bare ground: a node on a bridge would get the river or railway below it,
a node in a tunnel the hill above it. Nodes on a bridge or tunnel (inside one of its OSM ways) are therefore
interpolated along the structure between its ends (the nodes that also touch normal streets),
weighted by distance. A straight line between the abutments flattens a humped bridge, so for the few
bridges in data/custom/bridge_decks.json, hand-checked heights on the deck (routing.bridge_profile) are
used as well: listed nodes keep them, the rest are interpolated through them, and a crest in the middle of
an edge is saved with the heights so routing.grade can show that edge as up, then down.

Data: LGL Baden-Württemberg, Digitales Geländemodell DGM1 (opengeodata.lgl-bw.de),
"Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0".
"""
import argparse
import heapq
import io
import itertools
import json
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import networkx as nx
import pandas as pd
import requests
from shapely.geometry import LineString, Point

from routing.shade import DATA_DIR
from routing.shadow import lonlat_to_utm32

OUT = DATA_DIR / "custom" / "elevation_heilbronn.json"
BRIDGE_DECKS = DATA_DIR / "custom" / "bridge_decks.json"
CREST_MAX_M = 10  # a crest must lie this close to a bridge edge
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


def download_tiles(tiles, dest=DGM1_DIR, workers=6, url_pattern=DGM1_URL):
    """Download the zips for `tiles` (DGM1 unless `url_pattern` says otherwise) into `dest`, a few at a time;
    skips the ones already there."""
    dest.mkdir(parents=True, exist_ok=True)

    def fetch(tile):
        url = url_pattern.format(e=tile[0], n=tile[1])
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


def utm_line(G, u, v, d):
    """The edge as a LineString in UTM32 metres, from u to v."""
    pts = list(d["geometry"].coords) if "geometry" in d else [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in (u, v)]
    return LineString([lonlat_to_utm32(x, y) for x, y in pts])


def overpass_features(tags):
    """OSM features in Heilbronn with `tags` (osmnx, cached in cache/), retrying while Overpass is at capacity."""
    import time

    import osmnx as ox
    from routing.graph import CACHE_DIR, PLACE

    ox.settings.cache_folder = CACHE_DIR
    for wait in (10, 30, 90, None):
        try:
            return ox.features_from_place(PLACE, tags=tags)
        except Exception as err:
            if wait is None:
                raise
            print(f"Overpass: {str(err).splitlines()[0]} - retrying in {wait} s")
            time.sleep(wait)


def structure_lines():
    """[(lon, lat), ...] of every OSM bridge or tunnel way in Heilbronn."""
    ways = overpass_features({"bridge": True, "tunnel": True})
    lines = []
    for _, row in ways.iterrows():
        tagged = any(str(row.get(tag)) not in ("nan", "None", "no") for tag in ("bridge", "tunnel"))
        if tagged and row.geometry.geom_type == "LineString":
            lines.append(list(row.geometry.coords))
    return lines


def structure_nodes_from_ways(G, lines):
    """Nodes on a bridge or tunnel: an inner point of one of its OSM ways (`lines`), or the point where two
    of them meet. After simplification an edge is tagged bridge when any of the ways it merges is one (in
    Heilbronn 24.6 km of tagged edges hold 8.7 km of bridge), so the ways themselves say better where
    the terrain is not the street."""
    def key(x, y):
        return round(x, 7), round(y, 7)

    inner, ends = set(), defaultdict(int)
    for pts in lines:
        keys = [key(x, y) for x, y in pts]
        inner.update(keys[1:-1])
        for k in {keys[0], keys[-1]}:
            ends[k] += 1
    on = inner | {k for k, count in ends.items() if count >= 2}
    return {n for n, d in G.nodes(data=True) if key(d["x"], d["y"]) in on}


def is_structure(d):
    """A bridge or tunnel edge: the terrain model doesn't describe its height."""
    return any(d.get(tag) not in (None, "no") for tag in ("bridge", "tunnel"))


def structure_nodes(G):
    """Nodes whose every edge is a bridge or tunnel: the terrain under/over them is not the street."""
    on, off = set(), set()
    for u, v, d in G.edges(data=True):
        (on if is_structure(d) else off).update((u, v))
    return on - off


def load_bridge_decks(path=BRIDGE_DECKS):
    """({node: height}, [(lon, lat, height), ...]) of the hand-checked deck heights, or ({}, []) without the file."""
    path = Path(path)
    if not path.exists():
        return {}, []
    nodes, crests = {}, []
    for bridge in json.loads(path.read_text(encoding="utf-8"))["bridges"].values():
        nodes.update({int(n): h for n, h in bridge.get("nodes", {}).items()})
        crests.extend((c["lon"], c["lat"], c["height_m"]) for c in bridge.get("crests", []))
    return nodes, crests


def place_crests(G, crests, max_m=CREST_MAX_M):
    """Each crest (lon, lat, height) on the nearest bridge/tunnel edge: {"u", "v", "frac" (share of the edge
    from u), "height", "length"}, in the direction the edge u -> v runs (routing.grade turns it for v -> u)."""
    lines = [(u, v, d, utm_line(G, u, v, d)) for u, v, d in G.edges(data=True) if is_structure(d)]
    placed = []
    for lon, lat, height in crests:
        p = Point(lonlat_to_utm32(lon, lat))
        dist, u, v, d, line = min(((line.distance(p), u, v, d, line) for u, v, d, line in lines), key=lambda t: t[0])
        if dist > max_m:
            raise ValueError(f"crest at {lat}, {lon} is {dist:.0f} m from the nearest bridge edge")
        placed.append({"u": u, "v": v, "frac": round(line.project(p) / line.length, 4), "height": height,
                       "length": round(float(d["length"]), 1)})
    return placed


def fix_structures(G, heights, inner=None, deck=None, crests=()):
    """Replace the terrain height of bridge/tunnel interior nodes (`inner`, by default structure_nodes) by the
    distance-weighted mean of the two closest known heights on the structure: its ends (nodes that also touch
    normal streets) and the hand-checked deck heights, `deck` nodes and `crests` (from place_crests).
    On a simple bridge without them this is the straight line between its two abutments. Returns the fixed nodes."""
    deck = {n: h for n, h in (deck or {}).items() if n in G}
    inner = set(structure_nodes(G) if inner is None else inner) - set(deck)
    heights.update(deck)
    S = nx.Graph()
    for u, v, d in G.edges(data=True):
        length = float(d["length"])
        if is_structure(d) and (not S.has_edge(u, v) or length < S.edges[u, v]["length"]):
            S.add_edge(u, v, length=length)
    for i, c in enumerate(crests):  # a crest splits its edge: a known height in the middle
        u, v, crest = c["u"], c["v"], ("crest", i)
        length = S.edges[u, v]["length"] if S.has_edge(u, v) else c["length"]
        if S.has_edge(u, v):
            S.remove_edge(u, v)
        S.add_edge(u, crest, length=c["frac"] * length)
        S.add_edge(crest, v, length=(1 - c["frac"]) * length)
        heights[crest] = c["height"]
    fixed = dict(deck)
    for n in inner & set(S):
        nearest = sorted(_known_around(S, n, inner, heights))[:2]
        if nearest:
            if nearest[0][0] == 0 or len(nearest) == 1:
                fixed[n] = nearest[0][1]
            else:
                w = [1 / d for d, _ in nearest]
                fixed[n] = sum(wi * h for wi, (_, h) in zip(w, nearest)) / sum(w)
    for i in range(len(crests)):
        del heights[("crest", i)]
    heights.update(fixed)
    return fixed


def _known_around(S, n, inner, heights):
    """[(distance, height)] of the known heights met first going out from n along the structure S in every
    direction (abutments, deck heights, crests): a known point hides the ones behind it, so a node between a
    crest and an abutment is interpolated between those two."""
    tie = itertools.count()
    dist, heap, found = {n: 0.0}, [(0.0, next(tie), n)], []
    while heap:
        d, _, x = heapq.heappop(heap)
        if d > dist[x]:
            continue
        if x != n and x not in inner and x in heights:
            found.append((d, heights[x]))
            continue
        for y, data in S[x].items():
            if d + data["length"] < dist.get(y, float("inf")):
                dist[y] = d + data["length"]
                heapq.heappush(heap, (dist[y], next(tie), y))
    return found


def load_elevation(path=OUT):
    """{node id: height in m} as written by main(), or {} if the file is missing."""
    path = Path(path)
    if not path.exists():
        return {}
    return {int(k): v for k, v in json.loads(path.read_text())["nodes"].items()}


def load_crests(path=OUT):
    """The bridge crests in the middle of an edge as written by main() (see place_crests), or []."""
    path = Path(path)
    return json.loads(path.read_text()).get("crests", []) if path.exists() else []


def attach_elevation(G, heights, crests=()):
    """Set node attribute `elevation` (m above sea level, or None outside the tiles), keeping values already set,
    and edge attribute `crest` = (share of the edge before the crest, crest height) on both directions of the
    edges in `crests`."""
    for n, d in G.nodes(data=True):
        if d.get("elevation") is None:
            d["elevation"] = heights.get(int(n))
    by_id = {str(n): n for n in G.nodes}  # node ids are ints when loaded from GraphML, strings in some tests
    for c in crests:
        u, v = by_id.get(str(c["u"])), by_id.get(str(c["v"]))
        for a, b, frac in ((u, v, c["frac"]), (v, u, 1 - c["frac"])):
            for d in (G[a][b].values() if a is not None and b is not None and G.has_edge(a, b) else []):
                if abs(float(d["length"]) - c["length"]) < 1:
                    d["crest"] = (frac, c["height"])


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
    inner = structure_nodes_from_ways(G, structure_lines())
    deck, crests = load_bridge_decks()
    placed = place_crests(G, crests)
    fixed = fix_structures(G, heights, inner, deck, placed)
    print(f"{len(heights):,} nodes, {missing} outside the tiles, {len(inner)} on bridges/tunnels, {len(fixed)} of them "
          f"given a structure height (moved by up to {max((abs(h - terrain[n]) for n, h in fixed.items()), default=0):.1f} m), "
          f"{len(deck)} deck heights and {len(placed)} crests from {BRIDGE_DECKS.name}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": SOURCE,
        "unit": "m above sea level (NHN, DHHN2016)",
        "nodes": {str(n): round(h, 2) for n, h in sorted(heights.items())},
        "crests": placed,
    }, separators=(",", ":")))
    print(f"-> {args.out} ({args.out.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()

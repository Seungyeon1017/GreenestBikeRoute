"""Deck profile of a bridge from the LGL DOM1 surface model, to hand-check its heights for routing.elevation.

    uv run --group estimation python -X utf8 -m routing.bridge_profile "Erwin-Fuchs-Brücke"

Why: the DGM1 terrain model is bare ground, so routing.elevation draws a bridge as a straight line between its
abutments, which flattens a humped bridge. The DOM1 surface model keeps the deck, but also what is above it
(arches, lamp posts, trees, vehicles), so it is only used for the few bridges in data/custom/bridge_decks.json,
each checked by eye on the plot this script writes.

It takes the bridge-tagged bike-graph edges inside the bridge's OSM man_made=bridge outline (so not the paths
passing underneath) and joins them into runs from abutment to abutment. Along each run it samples the DOM1 every
metre (median of the 3 x 3 cells around the point) and smooths with a 15 m running median. A height on the deck
is today's straight line between the abutments plus how far the DOM1 deck rises above the line between its own
ends there, so an offset between DOM1 and DGM1 at the abutments drops out. It prints these heights for the run's
inner nodes and for its highest point (the crest), ready to paste into bridge_decks.json, and plots each run
(cache/bridge_profiles/<name>.png).

When the highest point is not the deck (an arch, a sign, a stretch where DOM1 is older than DGM1), read the
deck off the plot and print that spot instead: --at 1=100 gives run 1's position and heights 100 m from its first
abutment.

DOM1: one height per 1 m x 1 m cell, GeoTIFF per 1 km in 2 km zips (same grid as DGM1). Around Heilbronn it was
captured on 2017-02-15, while DGM1 was updated in 2024: check the bridge has not been rebuilt since. The script
prints how far DOM1 and today's heights differ at the abutments.

Data: LGL Baden-Württemberg, Digitales Oberflächenmodell DOM1 (opengeodata.lgl-bw.de),
"Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0".
"""
import argparse
import io
import json
import re
import zipfile
from functools import lru_cache

import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from routing.elevation import DGM1_DIR, download_tiles, load_elevation, overpass_features, tile_2km, utm_line
from routing.shade import utm32_to_lonlat

DOM1_DIR = DGM1_DIR.parent / "dom1"  # cache/ is git-ignored
DOM1_URL = "https://opengeodata.lgl-bw.de/data/dom1/dom1_32_{e}_{n}_2_bw.zip"
PLOT_DIR = DGM1_DIR.parent / "bridge_profiles"
STEP_M = 1.0
SMOOTH_M = 15  # running median: removes lamp posts and single vehicles, keeps the deck's shape
ON_BRIDGE = 0.5  # an edge counts as on the bridge when this share of it lies inside the outline ...
ON_BRIDGE_M = 15  # ... or at least this many metres of it


@lru_cache(maxsize=None)
def _dom_km(east_km, north_km):
    """(west, north, heights) of the 1 km DOM1 GeoTIFF with south-west corner (east_km, north_km)."""
    from PIL import Image  # comes with matplotlib (estimation group); the API never imports this module

    e2, n2 = tile_2km(east_km * 1000 + 0.5, north_km * 1000 + 0.5)
    path = DOM1_DIR / f"dom1_32_{e2}_{n2}_2_bw.zip"
    if not path.exists():
        download_tiles([(e2, n2)], dest=DOM1_DIR, url_pattern=DOM1_URL)
    with zipfile.ZipFile(path) as z:
        name = next(m for m in z.namelist() if re.search(rf"dom1_32_{east_km}_{north_km}_1_.*\.tif$", m))
        heights = np.array(Image.open(io.BytesIO(z.read(name))), dtype=float)
        x_centre, y_centre = (float(v) for v in z.read(name[:-4] + ".tfw").split()[4:6])  # top-left cell centre
    return x_centre - 0.5, y_centre + 0.5, heights


def dom_height(east, north):
    """DOM1 height at a UTM32 point: median of the 3 x 3 cells around it."""
    west, top, h = _dom_km(int(east // 1000), int(north // 1000))
    row, col = int(top - north), int(east - west)
    return float(np.median(h[max(row - 1, 0):row + 2, max(col - 1, 0):col + 2]))


def bridge_edges(G, outline):
    """Undirected graph of the bridge-tagged edges with at least ON_BRIDGE of their length, or ON_BRIDGE_M,
    inside `outline` (a UTM32 polygon); each edge keeps its UTM `line` from the smaller node id to the larger."""
    area = outline.buffer(3)
    B = nx.Graph()
    for u, v, d in G.edges(data=True):
        if d.get("bridge") in (None, "no") or B.has_edge(u, v):  # untagged: e.g. a path passing underneath
            continue
        line = utm_line(G, u, v, d)
        inside = line.intersection(area).length
        if inside >= ON_BRIDGE * line.length or inside >= ON_BRIDGE_M:
            B.add_edge(u, v, line=line if u < v else LineString(line.coords[::-1]), label=d.get("name") or d.get("highway"))
    return B


def runs(B):
    """Each connected piece of the bridge as (nodes from one end to the other, joined UTM line, distance of each
    node along it), when it is a simple run; branching pieces are skipped."""
    out = []
    for comp in nx.connected_components(B):
        sub = B.subgraph(comp)
        ends = [n for n in sub if sub.degree(n) == 1]
        if len(ends) != 2 or any(deg > 2 for _, deg in sub.degree()):
            continue
        nodes = nx.shortest_path(sub, *sorted(ends))
        coords, along = [], [0.0]
        for a, b in zip(nodes, nodes[1:]):
            line = sub.edges[a, b]["line"]
            pts = list(line.coords) if a < b else list(line.coords)[::-1]  # stored from smaller id to larger
            coords.extend(pts if not coords else pts[1:])
            along.append(along[-1] + line.length)
        out.append((nodes, LineString(coords), along))
    return out


def smooth_profile(heights, window=SMOOTH_M):
    """Running median over `window` samples, so single spikes (lamp posts, vehicles) drop out."""
    return pd.Series(heights).rolling(window, center=True, min_periods=1).median().to_numpy()


def deck_profile(line, height=dom_height, step=STEP_M):
    """(distances along the line in m, smoothed surface heights) every `step` metres."""
    s = np.append(np.arange(0, line.length, step), line.length)
    return s, smooth_profile([height(*line.interpolate(x).coords[0]) for x in s])


def deck_height(s, h, at, start, end):
    """Deck height at distance `at`: the straight line between today's abutment heights `start` and `end`, plus
    how far the surface profile rises there above the straight line between its own ends."""
    frac = at / s[-1]
    rise = np.interp(at, s, h) - (h[0] + frac * (h[-1] - h[0]))
    return float(start + frac * (end - start) + rise)


def bridge_outline(name):
    """The OSM man_made=bridge outline called `name`, as a UTM32 polygon."""
    from routing.graph import PLACE

    outlines = overpass_features({"man_made": "bridge"})
    match = outlines[outlines.get("name", pd.Series(dtype=str)).fillna("") == name]
    if match.empty:
        raise SystemExit(f"No man_made=bridge outline called {name!r} in OSM for {PLACE}")
    return match.to_crs(25832).geometry.iloc[0]


def main(argv=None):
    import matplotlib
    import osmnx as ox
    from routing.graph import GRAPH_PATH

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name", help='bridge name as in OSM, e.g. "Erwin-Fuchs-Brücke"')
    ap.add_argument("--at", action="append", default=[], metavar="RUN=METRES",
                    help="also print run RUN's position and heights this far from its first abutment")
    args = ap.parse_args(argv)
    spots = {int(r): float(m) for r, m in (a.split("=") for a in args.at)}

    G = ox.load_graphml(GRAPH_PATH)
    heights = load_elevation()
    bridge = bridge_edges(G, bridge_outline(args.name))
    pieces = runs(bridge)
    if not pieces:
        raise SystemExit(f"No run of bike-graph edges across {args.name}")

    fig, axes = plt.subplots(len(pieces), 1, figsize=(10, 3.4 * len(pieces)), squeeze=False)
    print(f"{args.name}: {len(pieces)} run(s) of bike-graph edges across the bridge")
    for run, (ax, (nodes, line, along)) in enumerate(zip(axes[:, 0], pieces), 1):
        s, h = deck_profile(line)
        start, end = heights[int(nodes[0])], heights[int(nodes[-1])]
        at = float(s[int(np.nanargmax(h))])
        crest = deck_height(s, h, at, start, end)
        lon, lat = utm32_to_lonlat(*line.interpolate(at).coords[0])
        inner = {str(n): round(deck_height(s, h, x, start, end), 1) for n, x in zip(nodes[1:-1], along[1:-1])}
        labels = sorted({str(B_edge["label"]) for B_edge in (bridge.edges[a, b] for a, b in zip(nodes, nodes[1:]))})
        print(f"\n  run {run}, {', '.join(labels)}: {' -> '.join(map(str, nodes))}, {line.length:.0f} m")
        print(f"    today:   {' -> '.join(f'{heights[int(n)]:.1f}' for n in nodes)} m")
        print(f"    surface: abutments {h[0]:.1f} / {h[-1]:.1f} m (vs today {h[0] - start:+.1f} / {h[-1] - end:+.1f} m),"
              f" highest {h.max():.1f} m at {at:.0f} m")
        print(f"    crest {crest:.1f} m at {at:.0f} m: {start:.1f} -> {crest:.1f} ({(crest - start) / at * 100 if at else 0:+.1f}%)"
              f" -> {end:.1f} m ({(end - crest) / (line.length - at) * 100 if line.length > at else 0:+.1f}%)")
        print("    paste: " + json.dumps({"nodes": inner, "crest": {"lon": round(lon, 6), "lat": round(lat, 6),
                                                                 "height_m": round(crest, 1)}}))
        if run in spots:
            x = spots[run]
            lon_x, lat_x = utm32_to_lonlat(*line.interpolate(x).coords[0])
            print(f"    at {x:.0f} m: lon {lon_x:.6f}, lat {lat_x:.6f}, surface {np.interp(x, s, h):.1f} m,"
                  f" today's line {start + x / line.length * (end - start):.1f} m, deck estimate {deck_height(s, h, x, start, end):.1f} m")
        ax.plot(s, h, color="#1f6feb", label="DOM1 surface, 15 m running median")
        ax.plot(along, [heights[int(n)] for n in nodes], "--o", color="#2e7d32", ms=3, label="today's node heights")
        fixed = sorted([(0.0, start), (at, crest), (line.length, end)]
                       + [(x, inner[str(n)]) for n, x in zip(nodes[1:-1], along[1:-1])])
        ax.plot(*zip(*fixed), ":", color="#d63b3b", label=f"with the deck heights (crest {crest:.1f} m)")
        ax.set_title(f"{args.name}: {', '.join(labels)}")
        ax.set_xlabel("metres from the first abutment")
        ax.set_ylabel("m above sea level")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    out = PLOT_DIR / f"{re.sub(r'[^A-Za-z0-9]+', '_', args.name)}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"\nPlot: {out}")


if __name__ == "__main__":
    main()

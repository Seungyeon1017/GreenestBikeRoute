"""Road surface per OSM way: how unpaved it is, 0 (paved) to 1 (soil, grass).

    python -X utf8 -m routing.surface          # -> data/custom/surface_heilbronn.json

The ATRAI roughness can't tell these apart: on the few unpaved ways bikes measured, roughness reads like asphalt
(median 10.0 on grass and grade4/5 tracks, 11.2 on asphalt), likely as riders slow down there. So the surface comes
from OSM: `surface` where mapped, else `tracktype` (on 99% of tracks), else a track counts as gravel. Ways with
neither (mostly town streets and footways, which are paved) are left out and count as paved.

Value per way: 0 paved (asphalt, concrete, paving stones, sett; tracktype grade1), 0.25 firm and fairly smooth
(compacted, fine gravel: most park paths; grade2), 0.5 loose or bumpy (gravel, cobblestones; grade3), 1 soft (soil,
grass, sand; grade4-5): slow, and mud after rain.

Input: the OSM ways and tags OSMnx cached in cache/*.json when routing.graph built the graph (run the API once
first).

Group: building the graph (data -> edge attributes).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from routing.lighting import CACHE_DIR, load_osm_ways
from routing.shade import DATA_DIR

OUT = DATA_DIR / "custom" / "surface_heilbronn.json"

PAVED = {"asphalt", "concrete", "concrete:plates", "concrete:lanes", "paving_stones", "paving_stones:lanes", "paved",
         "chipseal", "sett", "bricks", "brick", "metal", "wood", "rubber", "tartan", "acrylic"}
FIRM = {"compacted", "fine_gravel", "grass_paver"}
LOOSE = {"gravel", "pebblestone", "cobblestone", "unhewn_cobblestone", "rock", "stone", "unpaved"}
SOFT = {"ground", "dirt", "earth", "soil", "grass", "mud", "sand", "woodchips"}
TRACKTYPE = {"grade1": 0.0, "grade2": 0.25, "grade3": 0.5, "grade4": 1.0, "grade5": 1.0}
# A track with neither tag: about the mean of the tagged track length.
UNTAGGED_TRACK = 0.5


def unpaved(tags):
    """How unpaved a way with these OSM tags is (0, 0.25, 0.5 or 1), or None when nothing says."""
    surface = tags.get("surface", "").split(";")[0]
    if surface in PAVED:
        return 0.0
    if surface in FIRM:
        return 0.25
    if surface in LOOSE:
        return 0.5
    if surface in SOFT:
        return 1.0
    if tags.get("tracktype") in TRACKTYPE:
        return TRACKTYPE[tags["tracktype"]]
    return UNTAGGED_TRACK if tags.get("highway") == "track" else None


def load_surface(path=OUT):
    """{way_id: unpaved 0-1} from data/custom/surface_heilbronn.json, or {} if the file is missing."""
    path = Path(path)
    return {int(w): v for w, v in json.loads(path.read_text())["ways"].items()} if path.exists() else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=CACHE_DIR, help="folder with OSMnx's cached Overpass responses")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    osm_ways = load_osm_ways(args.cache)
    if not osm_ways:
        raise SystemExit(f"No OSM ways in {args.cache}: start the API once (routing.graph caches OSM there)")
    ways = {w: v for w, (tags, _) in osm_ways.items() if (v := unpaved(tags))}  # paved and unknown count as paved
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "about": "how unpaved each OSM way is: 0 paved, 0.25 compacted/fine gravel (tracktype grade2), 0.5 gravel/"
                 "cobblestones (grade3), 1 soil/grass (grade4-5); from surface, else tracktype, else 0.5 for a track. "
                 "Others count as paved",
        "source": "OpenStreetMap contributors (ODbL)",
        "ways": {str(w): v for w, v in sorted(ways.items())},
    }))
    print(f"{len(osm_ways):,} OSM ways, {len(ways):,} unpaved -> {args.out}")
    print("  " + ", ".join(f"{v}: {n:,}" for v, n in sorted(Counter(ways.values()).items())))


if __name__ == "__main__":
    main()

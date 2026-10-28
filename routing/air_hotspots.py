"""Air hotspots: the car roads Heilbronn's clean-air plan names as over the NO2 limit, as lines.

    python -X utf8 -m routing.air_hotspots          # -> data/custom/air_hotspots_heilbronn.json

Source: Luftreinhalteplan für den Regierungsbezirk Stuttgart, Teilplan Heilbronn, 2. Fortschreibung (August 2020),
Tabelle 3 / Abbildung 14: the sections of measure M9 (diesel ban below Euro 6), those forecast "deutlich über
40 µg/m³" NO2 in 2020 plus the sections traffic would shift to. The plan lists streets by name only, so each is
matched to OSM car roads of that name inside the city centre (HOTSPOT_BBOX, where Abbildung 14 shows them), a
little longer than some listed sections ("Kreuzung Allee bis Adenauerplatz" and the like).

routing.graph.attach_danger then starts bike streets that run along these roads (side paths and pavements
included, cross streets not) a little above typical air (routing.costs.AIR_HOTSPOT_OFFSET).

Needs the OSM car network: downloaded on the first run into cache/ (~1 min).
"""
import argparse
import json

import osmnx as ox

from routing.graph import AIR_HOTSPOTS_PATH as OUT, CACHE_DIR, PLACE

DRIVE_PATH = CACHE_DIR / "heilbronn_drive.graphml"

HOTSPOT_STREETS = [
    "Neckarsulmer Straße", "Burenstraße", "Orthstraße", "Schaeuffelenstraße", "Paulinenstraße", "Mannheimer Straße",
    "Weinsberger Straße", "Paul-Göbel-Straße", "Oststraße", "Allee", "Karlstraße", "Wollhausstraße", "Am Wollhaus",
    "Südstraße", "Urbanstraße", "Happelstraße", "Wilhelmstraße", "Bahnhofstraße", "Karlsruher Straße",
]
HOTSPOT_BBOX = (9.195, 49.125, 9.245, 49.165)  # (min lon, min lat, max lon, max lat): Abbildung 14's map


def hotspot_roads(drive):
    """[(lon, lat), ...] lines of the car roads named in HOTSPOT_STREETS whose middle lies in HOTSPOT_BBOX."""
    west, south, east, north = HOTSPOT_BBOX
    out = []
    for u, v, d in drive.edges(data=True):
        coords = list(d["geometry"].coords) if "geometry" in d else [(drive.nodes[n]["x"], drive.nodes[n]["y"]) for n in (u, v)]
        names = d.get("name") or []
        lon, lat = coords[len(coords) // 2]
        if west <= lon <= east and south <= lat <= north and set(names if isinstance(names, list) else [names]) & set(HOTSPOT_STREETS):
            out.append([(round(x, 7), round(y, 7)) for x, y in coords])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=type(OUT), default=OUT)
    args = ap.parse_args(argv)
    if DRIVE_PATH.exists():
        drive = ox.load_graphml(DRIVE_PATH)
    else:
        ox.settings.cache_folder = CACHE_DIR
        drive = ox.graph_from_place(PLACE, network_type="drive")
        ox.save_graphml(drive, DRIVE_PATH)
    roads = hotspot_roads(drive)
    args.out.write_text(json.dumps({
        "about": "car roads ([lon, lat] lines) of the Heilbronn clean-air plan's NO2 hotspot sections (measure M9)",
        "source": "Luftreinhalteplan Regierungsbezirk Stuttgart, Teilplan Heilbronn, 2. Fortschreibung (2020), "
                  "Tabelle 3; OpenStreetMap contributors (ODbL)",
        "streets": HOTSPOT_STREETS,
        "roads": roads,
    }, ensure_ascii=False))
    print(f"{len(roads)} car-road pieces on {len(HOTSPOT_STREETS)} named streets -> {args.out}")


if __name__ == "__main__":
    main()

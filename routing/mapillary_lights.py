"""Street lights detected in Mapillary street-view photos, for Heilbronn.

    $env:MAPILLARY_TOKEN = "MLY|..."                      # PowerShell, this window only
    python -X utf8 -m routing.mapillary_lights --check    # one small request at Marktplatz
    python -X utf8 -m routing.mapillary_lights            # all of Heilbronn -> data/custom/street_lights_mapillary.geojson

Mapillary's map features are objects placed on the map by triangulating AI detections
across several photos. This downloads the street lights (default object value
`object--street-light`) in small bounding boxes over Heilbronn and saves them as GeoJSON
points. The token is read from the MAPILLARY_TOKEN environment variable and is never written
to disk.

Data: Mapillary map features, CC BY-SA 4.0 (https://www.mapillary.com/developer).
Caveats: a light the AI missed (hidden by trees, bad photo) is not in the data, and photos can
be several years old.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from routing.shade import DATA_DIR

API = "https://graph.mapillary.com/map_features"
OUT = DATA_DIR / "custom" / "street_lights_mapillary.geojson"
OBJECT_VALUE = "object--street-light"
BBOX = (9.04, 49.09, 9.31, 49.215)  # Heilbronn road network, with a margin
STEP = 0.01                          # degrees per request box (~0.7 x 1.1 km)
LIMIT = 2000                         # max features per request; boxes that hit it are split
MARKTPLATZ = (9.214, 49.140, 9.224, 49.146)


def _token():
    token = os.environ.get("MAPILLARY_TOKEN", "").strip()
    if not token:
        sys.exit('Set the token first, e.g. in PowerShell:  $env:MAPILLARY_TOKEN = "MLY|..."')
    return token


def fetch_box(session, token, box, object_value=OBJECT_VALUE):
    """Map features in one (min_lon, min_lat, max_lon, max_lat) box; splits the box when it is full."""
    params = {
        "access_token": token,
        "fields": "id,object_value,geometry,first_seen_at,last_seen_at",
        "bbox": ",".join(f"{v:.6f}" for v in box),
        "object_values": object_value,
        "limit": LIMIT,
    }
    for attempt in range(4):
        r = session.get(API, params=params, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (400, 401, 403):
            # Don't print the URL: it contains the token.
            sys.exit(f"Mapillary refused the request (HTTP {r.status_code}): {r.text[:300]}")
        r.raise_for_status()
        data = r.json().get("data", [])
        break
    else:
        print(f"  box {box}: gave up after retries, skipped")
        return []
    if len(data) >= LIMIT:
        x0, y0, x1, y1 = box
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        for sub in ((x0, y0, mx, my), (mx, y0, x1, my), (x0, my, mx, y1), (mx, my, x1, y1)):
            out += fetch_box(session, token, sub, object_value)
        return out
    return data


def boxes(bbox=BBOX, step=STEP):
    x0, y0, x1, y1 = bbox
    x = x0
    while x < x1:
        y = y0
        while y < y1:
            yield (x, y, min(x + step, x1), min(y + step, y1))
            y += step
        x += step


def to_geojson(features):
    seen, out = set(), []
    for f in features:
        if f["id"] in seen or "geometry" not in f:
            continue
        seen.add(f["id"])
        out.append({"type": "Feature", "geometry": f["geometry"], "properties": {
            "id": f["id"], "object_value": f.get("object_value"),
            "first_seen_at": f.get("first_seen_at"), "last_seen_at": f.get("last_seen_at")}})
    return {"type": "FeatureCollection",
            "source": "Mapillary map features, CC BY-SA 4.0", "features": out}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="one small request around Marktplatz, saves nothing")
    ap.add_argument("--object-value", default=OBJECT_VALUE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    token, session = _token(), requests.Session()
    if args.check:
        found = fetch_box(session, token, MARKTPLATZ, args.object_value)
        print(f"{len(found)} {args.object_value} around Marktplatz (~700 x 650 m)")
        for f in found[:3]:
            print("  e.g.", f.get("geometry", {}).get("coordinates"), "last seen", f.get("last_seen_at"))
        return

    all_boxes = list(boxes())
    found = []
    for i, box in enumerate(all_boxes, 1):
        found += fetch_box(session, token, box, args.object_value)
        if i % 25 == 0 or i == len(all_boxes):
            print(f"  {i}/{len(all_boxes)} boxes, {len(found):,} lights so far")
    gj = to_geojson(found)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(gj))
    print(f"{len(gj['features']):,} street lights -> {args.out}")


if __name__ == "__main__":
    main()

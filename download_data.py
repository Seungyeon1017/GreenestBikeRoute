"""Download the ready-made ATRAI datasets for Heilbronn into ./data as GeoJSON.

    python -X utf8 download_data.py                  # all Heilbronn datasets (~85 MB)
    python -X utf8 download_data.py --only bumpy_roads road_network
    python -X utf8 download_data.py --large          # also the raw 1M+ row collections
    python -X utf8 download_data.py --force          # re-download even if cached

Every file is a standard GeoJSON FeatureCollection (open in QGIS / geopandas /
json.load(...)["features"]). Files that already exist are skipped, so teammates
can re-run the script safely. See data/manifest.json for what was fetched.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://api.atrai.bike"
CITY = "heilbronn"
DATA_DIR = Path(__file__).parent / "data"

# One collection per city: "<prefix>_<city>".
CITY_PREFIXES = [
    "bumpy_roads",
    "danger_zones",
    "danger_zones_PM",
    "overtaking_distance",
    "speed_map",
    "traffic_flow",
    "road_network",
    "bike_road_network",
]


def _has_city_tag(feature):
    # groupTags is a JSON-encoded string, e.g. '["bike", "atrai", "heilbronn"]'
    return CITY in json.loads(feature["properties"]["groupTags"])


# Collections that cover all cities: (collection, output name, row filter).
FILTERED = [
    ("tracks", f"tracks_{CITY}", _has_city_tag),
    ("statistics", f"statistics_{CITY}", lambda f: f["properties"]["tag"] == CITY),
]

# Raw sensor collections with over a million rows (GBs of JSON). Opt-in only.
# The first two contain every city; osem_home_data_heilbronn is Heilbronn only.
LARGE = [
    ("track_points", "track_points", None),
    ("osem_bike_data", "osem_bike_data", None),
    ("osem_home_data_heilbronn", "osem_home_data_heilbronn", None),
]


def all_datasets(include_large):
    items = [(f"{p}_{CITY}", f"{p}_{CITY}", None) for p in CITY_PREFIXES] + FILTERED
    return items + (LARGE if include_large else [])


def make_session():
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def download(session, collection, out_path, page=2000, keep=None):
    """Page through /collections/{collection}/items and stream it into out_path.

    Features are written as they arrive, so memory use stays flat even for the
    million-row collections. Returns (features_written, features_seen).
    """
    tmp = out_path.with_suffix(".part")
    url = f"{BASE}/collections/{collection}/items"
    offset = written = matched = 0
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write('{"type":"FeatureCollection","features":[')
        while True:
            r = session.get(url, params={"limit": page, "offset": offset}, timeout=300)
            r.raise_for_status()
            body = r.json()
            matched = body["numberMatched"]
            feats = body["features"]
            for f in feats:
                if keep is None or keep(f):
                    fh.write(("," if written else "") + json.dumps(f, ensure_ascii=False))
                    written += 1
            offset += len(feats)
            print(f"\r  {collection}: {offset}/{matched}", end="", flush=True)
            if not feats or offset >= matched:
                break
        fh.write("]}")
    print()
    if offset != matched:
        print(f"  WARNING: expected {matched} rows, got {offset}", file=sys.stderr)
    os.replace(tmp, out_path)
    return written, offset


def update_manifest(entry):
    path = DATA_DIR / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    manifest[entry.pop("file")] = entry
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch(collection, name, keep=None, force=False, session=None, page=2000):
    """Download one dataset to data/<name>.geojson unless it is already there."""
    DATA_DIR.mkdir(exist_ok=True)
    out = DATA_DIR / f"{name}.geojson"
    if out.exists() and not force:
        print(f"{name}: cached ({out.stat().st_size / 1e6:.1f} MB)")
        return out
    print(f"{name}: downloading")
    t0 = time.time()
    written, seen = download(session or make_session(), collection, out, page, keep)
    update_manifest({
        "file": out.name,
        "collection": collection,
        "features": written,
        "rows_in_collection": seen,
        "megabytes": round(out.stat().st_size / 1e6, 1),
        "seconds": round(time.time() - t0),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return out


def load_features(name):
    """Return the features of data/<name>.geojson, downloading it first if needed."""
    for collection, out_name, keep in all_datasets(include_large=True):
        if out_name == name:
            path = fetch(collection, out_name, keep)
            return json.loads(path.read_text(encoding="utf-8"))["features"]
    raise KeyError(f"unknown dataset {name!r}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", nargs="+", metavar="NAME",
                    help="dataset prefixes or file names, e.g. bumpy_roads tracks")
    ap.add_argument("--large", action="store_true", help="include the 1M+ row raw collections")
    ap.add_argument("--force", action="store_true", help="re-download cached files")
    ap.add_argument("--page-size", type=int, default=2000)
    args = ap.parse_args()

    datasets = all_datasets(args.large)
    if args.only:
        wanted = {w.removesuffix(f"_{CITY}") for w in args.only}
        datasets = [d for d in datasets if d[1].removesuffix(f"_{CITY}") in wanted]
        if not datasets:
            sys.exit(f"nothing matches --only {args.only}")

    session = make_session()
    for collection, name, keep in datasets:
        fetch(collection, name, keep, args.force, session, args.page_size)
    print(f"Done. Files are in {DATA_DIR}")


if __name__ == "__main__":
    main()

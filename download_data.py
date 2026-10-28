"""Download the ATRAI datasets for Heilbronn into ./data as GeoJSON: data/ready-made/ as ATRAI serves them,
data/custom/ built by us from raw sensor rows.

    python -X utf8 download_data.py                  # all Heilbronn datasets (~87 MB)
    python -X utf8 download_data.py --only bumpy_roads road_network
    python -X utf8 download_data.py --large          # also the raw 1M+ row collections
    python -X utf8 download_data.py --force          # re-download even if cached

Every file is a standard GeoJSON FeatureCollection (open in QGIS / geopandas /
json.load(...)["features"]). Files that already exist are skipped, so teammates
can re-run the script safely. See data/manifest.json for what was fetched.

load_features downloads any missing file on first use.
The backend can also start without data/
(first start ~1-2 min, mostly streaming osem_bike_data)
"""
import argparse
import codecs
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://api.atrai.bike"
CITY = "heilbronn"
DATA_DIR = Path(__file__).resolve().parent / "data"

# Raw tables whose pages come back in a different order on every request: paging them
# duplicates and skips rows, so they are fetched in a single request instead.
UNSTABLE_PAGING = {"osem_bike_data", "osem_home_data_heilbronn"}
ALL_ROWS = 5_000_000  # a `limit` above any collection's size

# Heilbronn road network extent plus ~1 km: (min lon, min lat, max lon, max lat).
# The *_heilbronn danger_zones points also include rides in Karlsruhe, Heidelberg, Munich, ...
HEILBRONN_BBOX = (9.038, 49.083, 9.312, 49.220)

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


def overtaking_risk(manoeuvre, distance_cm):
    """Risk Index Overtaking as the ATRAI docs define it (manoeuvre 0-1, distance in cm)."""
    return 0.3 * manoeuvre + 0.7 * (1 - min(max(distance_cm / 400, 0), 1))


def _danger_zone_row(feature):
    """A raw osem_bike_data row as a danger_zones point with its device and exact distance, or None.

    Keeps rows flagged as an overtaking (manoeuvre > 0.05) that were recorded inside HEILBRONN_BBOX
    by a device tagged "heilbronn". Without the tag, a test box of another project (`66.11 Test`,
    tagged lauds_26) that rode through the city would slip in; danger_zones leaves it out too.
    A distance of 0 is the table's "no reading" value, so such rows get no risk.
    """
    p = feature["properties"]
    manoeuvre, distance = p.get("Overtaking Manoeuvre"), p.get("Overtaking Distance")
    lon, lat = p["longitude"], p["latitude"]
    west, south, east, north = HEILBRONN_BBOX
    if manoeuvre is None or manoeuvre <= 0.05 or not (west <= lon <= east and south <= lat <= north):
        return None
    if not _has_city_tag(feature):
        return None
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "index": p["index"],
            "boxId": p["boxId"],
            "boxName": p["boxName"],
            "createdAt": p["createdAt"],
            "Overtaking Manoeuvre": manoeuvre,
            "Overtaking Distance": distance,
            "Risk Index Overtaking": overtaking_risk(manoeuvre, distance) if distance else None,
            "Speed": p.get("Speed"),
        },
    }


PM_FIELDS = ["Finedust PM1", "Finedust PM2.5", "Finedust PM4", "Finedust PM10"]

# danger_zones_PM leaves out air readings above this relative humidity (%), where the sensors over-read.
MAX_HUMIDITY = 75


# Outlier removal as in danger_zones_PM: per device with at least MIN_DEVICE_ROWS rows, a row is
# dropped when any PM value lies more than IQR_FACTOR interquartile ranges outside the quartiles.
MIN_DEVICE_ROWS = 10
IQR_FACTOR = 1.5


def _pm_row(feature):
    """A raw osem_bike_data row as an air quality point with its device and PM readings, or None.

    Keeps rows from devices tagged "heilbronn" with all four PM values and a humidity of at most
    MAX_HUMIDITY, the rows danger_zones_PM starts from. Rows outside HEILBRONN_BBOX are kept for
    now: clean_pm_rows needs each device's full set of rides.
    """
    p = feature["properties"]
    humidity = p.get("Rel. Humidity")
    if any(p.get(k) is None for k in PM_FIELDS) or humidity is None or humidity > MAX_HUMIDITY:
        return None
    if not _has_city_tag(feature):
        return None
    return {
        "type": "Feature",
        "geometry": feature["geometry"],
        "properties": {
            "index": p["index"],
            "boxId": p["boxId"],
            "boxName": p["boxName"],
            "createdAt": p["createdAt"],
            **{k: p[k] for k in PM_FIELDS},
        },
    }


def clean_pm_rows(features):
    """The _pm_row rows without PM spikes, inside HEILBRONN_BBOX: the danger_zones_PM rows in Heilbronn.

    Each device is checked against its own quartiles over all its rides, so a sensor that reads
    high everywhere keeps its rows and only its spikes are dropped. Only then is the city cut out:
    cutting first would change the quartiles and keep about 20,000 rows danger_zones_PM drops.
    """
    by_device = {}
    for i, f in enumerate(features):
        by_device.setdefault(f["properties"]["boxId"], []).append(i)
    keep = []
    for rows in by_device.values():
        if len(rows) < MIN_DEVICE_ROWS:
            continue
        pm = np.array([[features[i]["properties"][k] for k in PM_FIELDS] for i in rows], dtype=float)
        q1, q3 = np.percentile(pm, [25, 75], axis=0)
        spread = IQR_FACTOR * (q3 - q1)
        inside = ((pm >= q1 - spread) & (pm <= q3 + spread)).all(axis=1)
        keep += [i for i, ok in zip(rows, inside) if ok]
    west, south, east, north = HEILBRONN_BBOX
    return [f for f in (features[i] for i in sorted(keep))
            if west <= f["geometry"]["coordinates"][0] <= east and south <= f["geometry"]["coordinates"][1] <= north]


# senseBox:home stations that measured fine dust for fewer hours than this are left out of the background:
# a few logged only on their first day. The 7 left are in and around Heilbronn (Innenstadt to Beilstein).
MIN_HOME_HOURS = 1000


class HourlyBackground:
    """Row filter for osem_home_data_heilbronn (2M rows from ~15 senseBox:home stations, one every ~10 s) that keeps
    no row but sums each station's PM readings per hour. features() then gives one feature per hour: the median
    over stations of their hourly mean, per PM value, the fine-dust level of the region at that hour.

    Hours are the first 13 characters of createdAt (UTC, as in osem_bike_data), e.g. "2026-07-13T15".
    """

    def __init__(self):
        self.sums = {}  # (box, hour) -> [sum per PM_FIELDS..., count]

    def __call__(self, feature):
        p = feature["properties"]
        if all(p.get(k) is not None for k in PM_FIELDS):
            s = self.sums.setdefault((p["boxId"], p["createdAt"][:13]), [0.0] * len(PM_FIELDS) + [0])
            for i, k in enumerate(PM_FIELDS):
                s[i] += p[k]
            s[-1] += 1
        return None

    def features(self):
        hours_per_box = {}
        for box, _ in self.sums:
            hours_per_box[box] = hours_per_box.get(box, 0) + 1
        by_hour = {}
        for (box, hour), s in self.sums.items():
            if hours_per_box[box] >= MIN_HOME_HOURS:
                by_hour.setdefault(hour, []).append([v / s[-1] for v in s[:-1]])
        return [{"type": "Feature", "geometry": None,
                 "properties": {"hour": hour, "stations": len(means),
                                **{k: round(float(v), 3) for k, v in zip(PM_FIELDS, np.median(means, axis=0))}}}
                for hour, means in sorted(by_hour.items())]


# Collections that cover all cities: (collection, output name, row filter).
# A row filter returns True to keep the feature, a replacement feature to keep that instead, or a falsy value to skip it.
FILTERED = [
    ("tracks", f"tracks_{CITY}", _has_city_tag),
    ("statistics", f"statistics_{CITY}", lambda f: f["properties"]["tag"] == CITY),
    # Each streams all 1.4M raw rows (about 1 GB over the wire), but keeps only a few to tens of MB.
    ("osem_bike_data", f"danger_zones_raw_{CITY}", _danger_zone_row),
    ("osem_bike_data", f"air_quality_{CITY}", _pm_row),
    # Streams ~3 GB (about a minute), keeps one row per hour. A class is a fresh row filter per download
    # that builds the features itself (see HourlyBackground).
    ("osem_home_data_heilbronn", f"air_background_{CITY}", HourlyBackground),
]

# Steps that need all kept rows at once, run on the downloaded file: output name -> features -> features.
FINISH = {f"air_quality_{CITY}": clean_pm_rows}

# Datasets we build from raw sensor rows; they go to data/custom/, everything else to data/ready-made/.
CUSTOM = {f"danger_zones_raw_{CITY}", f"air_quality_{CITY}", f"air_background_{CITY}"}

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


def download_single_request(session, collection, out_path, keep=None):
    """Fetch the whole collection in ONE request and stream it into out_path.

    osem_bike_data comes back in a different order on every request, so offset paging
    returns some rows twice and skips others (we measured ~40% duplicates). One request is
    one consistent scan. Returns (features_written, features_seen).
    """
    tmp = out_path.with_suffix(".part")
    url = f"{BASE}/collections/{collection}/items"
    decoder, text = json.JSONDecoder(), codecs.getincrementaldecoder("utf-8")()
    written = seen = 0
    matched = None
    buf, done = "", False
    with session.get(url, params={"limit": ALL_ROWS}, stream=True, timeout=(30, 900)) as r, \
            tmp.open("w", encoding="utf-8") as fh:
        r.raise_for_status()
        fh.write('{"type":"FeatureCollection","features":[')
        for chunk in r.iter_content(1 << 20):
            if done:
                continue
            buf += text.decode(chunk)
            if matched is None:
                opening = re.search(r'"features"\s*:\s*\[', buf)
                if opening is None:
                    continue
                matched = int(re.search(r'"numberMatched"\s*:\s*(\d+)', buf[:opening.start()]).group(1))
                buf = buf[opening.end():]
            pos = 0
            while True:
                while pos < len(buf) and buf[pos] in ", \n\r\t":
                    pos += 1
                if pos < len(buf) and buf[pos] == "]":
                    done = True
                    break
                try:
                    f, pos = decoder.raw_decode(buf, pos)
                except json.JSONDecodeError:
                    break  # the feature is cut off by the end of this chunk
                seen += 1
                out = keep(f) if keep else f
                if out:
                    fh.write(("," if written else "") + json.dumps(f if out is True else out, ensure_ascii=False))
                    written += 1
            buf = buf[pos:]
            print(f"\r  {collection}: {seen}/{matched}", end="", flush=True)
        fh.write("]}")
    print()
    if not done or seen != matched:
        print(f"  WARNING: expected {matched} rows, got {seen}", file=sys.stderr)
    os.replace(tmp, out_path)
    return written, seen


def download(session, collection, out_path, page=2000, keep=None):
    """Page through /collections/{collection}/items and stream it into out_path.

    Features are written as they arrive, so memory use stays flat even for the
    million-row collections. Returns (features_written, features_seen).
    """
    if collection in UNSTABLE_PAGING:
        return download_single_request(session, collection, out_path, keep)
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
                out = f if keep is None else keep(f)
                if out:
                    fh.write(("," if written else "") + json.dumps(f if out is True else out, ensure_ascii=False))
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


def dataset_path(name):
    return DATA_DIR / ("custom" if name in CUSTOM else "ready-made") / f"{name}.geojson"


def fetch(collection, name, keep=None, force=False, session=None, page=2000):
    """Download one dataset to data/<folder>/<name>.geojson unless it is already there."""
    out = dataset_path(name)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not force:
        print(f"{name}: cached ({out.stat().st_size / 1e6:.1f} MB)")
        return out
    print(f"{name}: downloading")
    t0 = time.time()
    if isinstance(keep, type):
        keep = keep()
    written, seen = download(session or make_session(), collection, out, page, keep)
    if name in FINISH or hasattr(keep, "features"):
        features = keep.features() if hasattr(keep, "features") else FINISH[name](json.loads(out.read_text(encoding="utf-8"))["features"])
        # compact, so the file stays under GitHub's 50 MB warning
        out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        written = len(features)
    update_manifest({
        "file": out.relative_to(DATA_DIR).as_posix(),
        "collection": collection,
        "features": written,
        "rows_in_collection": seen,
        "megabytes": round(out.stat().st_size / 1e6, 1),
        "seconds": round(time.time() - t0),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    return out


def load_features(name):
    """Return the features of dataset `name`, downloading it first if needed."""
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

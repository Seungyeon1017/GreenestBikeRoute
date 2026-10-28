"""Estimate roughness for unmeasured Heilbronn streets from nearby measured ones.

    uv run --group ml python ml/estimate_roughness.py

For each unmeasured road segment: the inverse-distance-weighted mean of the measured segments within
250 m, pulled towards the city median the further away the nearest measurement is, and left unknown
beyond 150 m (the router then uses the median). ml/README.md has the formulas and why this beats a
Random Forest on the same data.

Outputs:
  data/custom/roughness_estimates_heilbronn.json  {OSM way id: roughness} for unmeasured ways, read by routing/graph.py
  ml/metrics.json                                 cross-validation and coverage
  ml/roughness_performance.png                    measured vs estimated on held-out streets
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.neighbors import BallTree

from download_data import load_features
from routing.graph import ESTIMATED_ROUGHNESS_PATH

ML_DIR = ROOT / "ml"

EARTH_RADIUS_M = 6_371_000
RADIUS_M = 250  # measured segments further away are ignored
K_NEIGHBOURS = 25  # at most this many of the nearest measured segments are averaged
IDW_OFFSET_M = 25  # weight = 1 / (distance + 25 m), so a neighbour right next to the segment can't take over
CV_FOLDS = 5

# Weight of the neighbour mean against the city median. The same street measured within
# SAME_STREET_RADIUS_M gets full weight; otherwise it depends on how far the nearest measurement is,
# and beyond the last limit the estimate is no better than the median, so the street stays unknown.
# Tuned on held-out streets and checked on a second half of the streets (ml/README.md).
SAME_STREET_RADIUS_M = 100
SHRINK_BY_NEAREST_M = ((50, 0.7), (150, 0.5))


def parse_osm_ids(osmid):
    s = str(osmid).strip()
    try:
        return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]
    except (ValueError, SyntaxError):
        return []


def segment_table(road_features):
    """One row per road segment: street name ("osm:<id>" when unnamed), OSM way ids and position
    (the average of its line's coordinates)."""
    rows = []
    for f in road_features:
        p = f["properties"]
        coords = f["geometry"]["coordinates"] if f.get("geometry") else []
        name = p.get("name")
        rows.append({
            "street": str(name) if name else f"osm:{p.get('osmid')}",
            "ways": parse_osm_ids(p.get("osmid")),
            "lat": np.mean([c[1] for c in coords]) if coords else np.nan,
            "lon": np.mean([c[0] for c in coords]) if coords else np.nan,
        })
    return pd.DataFrame(rows)


def measured_values(features, index_key, value_key, road_osmids):
    """{road segment index: value}, keeping only rows whose osmid matches that road segment."""
    out = {}
    for f in features:
        p = f["properties"]
        i, v = p.get(index_key), p.get(value_key)
        if v is None or i is None or not 0 <= i < len(road_osmids) or road_osmids[i] != str(p.get("osmid")):
            continue
        out[i] = float(v)
    return out


def neighbour_estimates(table, src_idx, query_idx, values, fallback):
    """Estimate per query segment from the measured `src_idx` segments, NaN where none is close enough.

    Also returns the weight given to the neighbour mean (1.0 same street, else from SHRINK_BY_NEAREST_M).
    """
    lat, lon, street = table.lat.values, table.lon.values, table.street.values
    tree = BallTree(np.radians(np.c_[lat[src_idx], lon[src_idx]]), metric="haversine")
    q_xy = np.radians(np.c_[lat[query_idx], lon[query_idx]])
    dist, ind = tree.query(q_xy, k=min(K_NEIGHBOURS, len(src_idx)))
    dist = dist * EARTH_RADIUS_M
    close = tree.query_radius(q_xy, r=SAME_STREET_RADIUS_M / EARTH_RADIUS_M)
    est = np.full(len(query_idx), np.nan)
    weight = np.full(len(query_idx), np.nan)
    for r, q in enumerate(query_idx):
        keep = dist[r] <= RADIUS_M
        if not keep.any():
            continue
        d, v = dist[r][keep], values[src_idx[ind[r][keep]]]
        idw = np.sum(v / (d + IDW_OFFSET_M)) / np.sum(1 / (d + IDW_OFFSET_M))
        if np.any(street[src_idx[close[r]]] == street[q]):
            w = 1.0
        else:
            w = next((s for limit, s in SHRINK_BY_NEAREST_M if d.min() < limit), np.nan)
        est[r], weight[r] = fallback + w * (idw - fallback), w
    return est, weight


def cross_validate(table, values, measured_idx, splits):
    """Hide each fold, estimate it from the rest; a segment without an estimate gets the median."""
    parts = []
    for tr, te in splits:
        tr_idx, te_idx = measured_idx[tr], measured_idx[te]
        median = float(np.median(values[tr_idx]))
        est, _ = neighbour_estimates(table, tr_idx, te_idx, values, median)
        parts.append(pd.DataFrame({"y": values[te_idx], "median": median,
                                   "estimate": np.where(np.isnan(est), median, est)}))
    return pd.concat(parts, ignore_index=True)


def scores(cv):
    out = {m: {"mae": round(float(mean_absolute_error(cv.y, cv[m])), 4), "r2": round(float(r2_score(cv.y, cv[m])), 4)}
           for m in ("median", "estimate")}
    out["estimate"]["spearman"] = round(float(spearmanr(cv.y, cv["estimate"]).statistic), 4)
    return out


def spatial_blocks(table, idx, size_m=1000):
    lat0 = np.radians(table.lat.mean())
    gx = np.floor(table.lon.values[idx] * 111_320 * np.cos(lat0) / size_m).astype(int)
    gy = np.floor(table.lat.values[idx] * 110_540 / size_m).astype(int)
    return gx * 100_000 + gy


def way_estimates(table, segment_idx, estimates, measured_ways):
    """Mean estimate per OSM way, skipping ways with any measured segment (the router uses those)."""
    acc = {}
    for i, e in zip(segment_idx, estimates):
        for way in table.ways.values[i]:
            if way not in measured_ways:
                acc.setdefault(way, []).append(float(e))
    return {way: sum(v) / len(v) for way, v in acc.items()}


def plot_performance(cv, metrics, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    lim = [0, max(cv.y.max(), cv.estimate.max()) * 1.05]
    axes[0].scatter(cv.y, cv.estimate, s=8, alpha=0.25, color="#16a085", edgecolors="none")
    axes[0].plot(lim, lim, "--", color="#e74c3c", label="perfect 1:1")
    axes[0].set(xlim=lim, ylim=lim, xlabel="measured roughness", ylabel="estimated roughness")
    axes[0].set_title(f"Held-out streets (Spearman {metrics['estimate']['spearman']:.3f}, "
                      f"MAE {metrics['estimate']['mae']:.2f})", fontweight="bold")
    axes[0].legend()

    for m, color in (("estimate", "#2980b9"), ("median", "#95a5a6")):
        axes[1].hist(cv.y - cv[m], bins=50, alpha=0.6, color=color, label=f"{m}: MAE {metrics[m]['mae']:.3g}")
    axes[1].axvline(0, ls="--", color="#e74c3c")
    axes[1].set(xlabel="error (measured - estimated)", ylabel="segments")
    axes[1].set_title("Errors vs always guessing the median", fontweight="bold")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    roads = load_features("road_network_heilbronn")
    table = segment_table(roads)
    road_osmids = [str(f["properties"].get("osmid")) for f in roads]
    measured = measured_values(load_features("bumpy_roads_heilbronn"), "id", "Normalized Roughness", road_osmids)
    values = np.full(len(table), np.nan)
    values[list(measured)] = list(measured.values())
    measured_idx = np.array(sorted(measured))
    unmeasured_idx = np.array([i for i in range(len(table)) if i not in measured])
    print(f"{len(measured_idx)} measured / {len(table)} road segments")

    splits = {
        "cv_unseen_streets": GroupKFold(CV_FOLDS).split(measured_idx, groups=table.street.values[measured_idx]),
        "cv_unseen_1km_areas": GroupKFold(CV_FOLDS).split(measured_idx, groups=spatial_blocks(table, measured_idx)),
        # Unmeasured parts of measured streets: the same-street rule only shows up here.
        "cv_random_segments": KFold(CV_FOLDS, shuffle=True, random_state=0).split(measured_idx),
    }
    cv = {name: cross_validate(table, values, measured_idx, list(sp)) for name, sp in splits.items()}
    cv_scores = {name: scores(c) for name, c in cv.items()}
    for name, sc in cv_scores.items():
        print(f"  {name:20} median MAE {sc['median']['mae']:.3f} | estimate MAE {sc['estimate']['mae']:.3f} "
              f"R2 {sc['estimate']['r2']:.3f} Spearman {sc['estimate']['spearman']:.3f}")

    median = float(np.median(values[measured_idx]))
    est, weight = neighbour_estimates(table, measured_idx, unmeasured_idx, values, median)
    known = ~np.isnan(est)
    measured_ways = {w for i in measured_idx for w in table.ways.values[i]}
    ways = way_estimates(table, unmeasured_idx[known], np.clip(est[known], 0.0, 100.0), measured_ways)
    ESTIMATED_ROUGHNESS_PATH.write_text(json.dumps({str(k): round(v, 4) for k, v in sorted(ways.items())}, indent=0))
    plot_performance(cv["cv_unseen_streets"], cv_scores["cv_unseen_streets"], ML_DIR / "roughness_performance.png")

    coverage = {
        "segments_measured": len(measured_idx),
        "segments_estimated": int(known.sum()),
        "segments_unknown": int((~known).sum()),
        "segments_estimated_by_weight": {str(w): int((weight == w).sum())
                                         for w in (1.0, *(s for _, s in SHRINK_BY_NEAREST_M))},
        "ways_estimated": len(ways),
    }
    metrics = {"median": median, **{n: {"n": len(c), **cv_scores[n]} for n, c in cv.items()}, "coverage": coverage}
    (ML_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"  {coverage['segments_estimated']} segments estimated, {coverage['segments_unknown']} unknown; "
          f"wrote {len(ways)} way estimates to {ESTIMATED_ROUGHNESS_PATH.relative_to(ROOT)}")
    return metrics


if __name__ == "__main__":
    main()

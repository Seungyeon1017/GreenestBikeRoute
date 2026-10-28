"""Fill in roughness and traffic flow for unmeasured Heilbronn streets.

    python ml/train_imputer.py

Roughness: inverse-distance-weighted mean of the measured segments within 250 m. Used as is when the
same street was measured within 100 m; otherwise pulled towards the city median, the more the further
away the nearest measurement is, and left unknown beyond 150 m. On held-out streets this beats a
Random Forest on the same data, and OSM highway/surface tags carry no roughness signal (ml/README.md).

Traffic flow: Random Forest on OSM highway & surface tags (data/osm_tags_cache.json), geometry and
spatial neighbours.

Both are evaluated with GroupKFold on unseen streets and unseen 1 km blocks.

Outputs:
  data/ml_predicted_roughness.json, data/ml_predicted_traffic_flow.json
  ml/metrics.json
  ml/<target>_performance.png, ml/traffic_flow_feature_importance.png
"""
import ast
import json
import math
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.neighbors import BallTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ML_DIR = PROJECT_ROOT / "ml"

EARTH_RADIUS_M = 6_371_000
RADIUS_M = 250
K_NEIGHBOURS = 25
IDW_OFFSET_M = 25
CV_FOLDS = 5

# Roughness: weight of the neighbour mean against the city median. The same street measured within
# SAME_STREET_RADIUS_M gets full weight; otherwise it depends on how far the nearest measurement is,
# and beyond the last limit the estimate is no better than the median, so the street stays unknown.
# Tuned on held-out streets and checked on a second half of the streets (ml/README.md).
SAME_STREET_RADIUS_M = 100
SHRINK_BY_NEAREST_M = ((50, 0.7), (150, 0.5))

TARGETS = {
    "roughness": {"source": "bumpy_roads_heilbronn", "index_key": "id", "value_key": "Normalized Roughness",
                  "method": "neighbours"},
    "traffic_flow": {"source": "traffic_flow_heilbronn", "index_key": "road_segment", "value_key": "avg_traffic_flow",
                     "method": "random_forest"},
}

HIGHWAY_TO_SURFACE = {
    "motorway": "asphalt", "motorway_link": "asphalt",
    "trunk": "asphalt", "trunk_link": "asphalt",
    "primary": "asphalt", "primary_link": "asphalt",
    "secondary": "asphalt", "secondary_link": "asphalt",
    "tertiary": "asphalt", "tertiary_link": "asphalt",
    "unclassified": "asphalt",
    "residential": "asphalt",
    "living_street": "paving_stones",
    "service": "asphalt",
    "cycleway": "asphalt",
    "pedestrian": "paving_stones",
    "track": "gravel",
    "path": "ground",
    "footway": "paving_stones",
    "steps": "concrete",
}

SURFACES = ["asphalt", "paving_stones", "sett", "cobblestone", "concrete", "gravel", "fine_gravel",
            "compacted", "ground", "dirt", "grass", "unknown"]

HIGHWAYS = ["residential", "service", "track", "path", "primary", "secondary", "tertiary",
            "living_street", "pedestrian", "cycleway", "other"]

NEIGHBOUR_FEATURES = ["nb_idw_mean", "nb_median", "nb_count", "nb_nearest_m"]
STATIC_FEATURES = (
    ["log_length", "sinuosity", "oneway", "has_cycleway", "has_name", "is_weg", "is_gasse", "is_platz", "is_brucke"]
    + [f"surface_{s}" for s in SURFACES]
    + [f"highway_{h}" for h in HIGHWAYS]
)
FEATURES = NEIGHBOUR_FEATURES + STATIC_FEATURES


def parse_osm_ids(osmid_val):
    s = str(osmid_val).strip()
    try:
        return [int(x) for x in ast.literal_eval(s)] if s.startswith("[") else [int(s)]
    except (ValueError, SyntaxError):
        return []


def clean_surface_tag(raw_surface):
    if not raw_surface:
        return "unknown"
    s = str(raw_surface).strip()
    if s.startswith("["):
        try:
            s = ast.literal_eval(s)[0]
        except (ValueError, SyntaxError, IndexError):
            return "unknown"
    s = str(s).strip().lower()
    return s if s in SURFACES else ("unknown" if s in ("", "none") else s)


def line_geometry(coordinates):
    if not coordinates:
        return 0.0, math.nan, math.nan, 1.0
    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]

    def dist(a, b):
        mid = math.radians((a[1] + b[1]) / 2)
        return math.hypot((b[0] - a[0]) * 111_320 * math.cos(mid), (b[1] - a[1]) * 110_540)

    length = sum(dist(a, b) for a, b in zip(coordinates, coordinates[1:]))
    sinuosity = length / max(dist(coordinates[0], coordinates[-1]), 1.0)
    return length, sum(lats) / len(lats), sum(lons) / len(lons), sinuosity


def load_cached_osm_tags():
    cache_path = DATA_DIR / "osm_tags_cache.json"
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def segment_table(road_features):
    osm_tags = load_cached_osm_tags()
    rows = []
    for f in road_features:
        p = f["properties"]
        length, lat, lon, sinuosity = line_geometry(f["geometry"]["coordinates"] if f.get("geometry") else [])
        name = p.get("name")
        lname = str(name or "").lower()
        ways = parse_osm_ids(p.get("osmid"))

        # Determine highway and surface from OSM cache
        hw = "other"
        surf = clean_surface_tag(p.get("surface"))
        for w in ways:
            t = osm_tags.get(str(w), {})
            cand_hw = str(t.get("highway") or "").lower()
            if cand_hw:
                hw = cand_hw if cand_hw in HIGHWAYS else "other"
                if surf == "unknown" and t.get("surface"):
                    surf = clean_surface_tag(t["surface"])
                break

        # Apply highway -> surface criteria fillna
        if surf == "unknown":
            surf = HIGHWAY_TO_SURFACE.get(hw, "unknown")
            if surf not in SURFACES:
                surf = "unknown"

        row = {
            "street": str(name) if name else f"osm:{p.get('osmid')}",
            "ways": ways,
            "lat": lat,
            "lon": lon,
            "log_length": math.log1p(length),
            "sinuosity": sinuosity,
            "oneway": int(bool(p.get("oneway"))),
            "has_cycleway": int(p.get("cycleway") not in (None, "", "no", "none")),
            "has_name": int(bool(name)),
            "is_weg": int("weg" in lname or "pfad" in lname),
            "is_gasse": int("gasse" in lname),
            "is_platz": int("platz" in lname),
            "is_brucke": int("brücke" in lname or "steg" in lname),
            "highway": hw,
            "surface": surf,
        }
        row.update({f"surface_{s}": int(surf == s) for s in SURFACES})
        row.update({f"highway_{h}": int(hw == h) for h in HIGHWAYS})
        rows.append(row)
    return pd.DataFrame(rows)


def measured_values(features, index_key, value_key, road_osmids):
    out = {}
    for f in features:
        p = f["properties"]
        i, v = p.get(index_key), p.get(value_key)
        if v is None or i is None or not 0 <= i < len(road_osmids) or road_osmids[i] != str(p.get("osmid")):
            continue
        out[i] = float(v)
    return out


def neighbour_features(src_lat, src_lon, src_values, src_street, q_lat, q_lon, q_street,
                       radius_m=RADIUS_M, k=K_NEIGHBOURS):
    src_xy = np.radians(np.c_[src_lat, src_lon])
    k = min(k, len(src_xy))
    dist, ind = BallTree(src_xy, metric="haversine").query(np.radians(np.c_[q_lat, q_lon]), k=k)
    dist = dist * EARTH_RADIUS_M
    out = np.full((len(q_lat), 4), np.nan)
    out[:, 2] = 0
    for r in range(len(q_lat)):
        keep = (dist[r] <= radius_m) & (src_street[ind[r]] != q_street[r])
        if not keep.any():
            continue
        d, v = dist[r][keep], src_values[ind[r][keep]]
        w = 1 / (d + IDW_OFFSET_M)
        out[r] = (np.sum(w * v) / w.sum(), np.median(v), keep.sum(), d.min())
    return out


def add_neighbour_features(table, src_idx, query_idx, values):
    nb = neighbour_features(
        table.lat.values[src_idx], table.lon.values[src_idx], values[src_idx], table.street.values[src_idx],
        table.lat.values[query_idx], table.lon.values[query_idx], table.street.values[query_idx],
    )
    X = table.iloc[query_idx][STATIC_FEATURES].copy()
    # Fill any NaN in neighbour features with median/zero
    for j, name in enumerate(NEIGHBOUR_FEATURES):
        col_vals = nb[:, j]
        if name in ("nb_idw_mean", "nb_median"):
            default_val = float(np.nanmedian(values[src_idx]))
            col_vals = np.where(np.isnan(col_vals), default_val, col_vals)
        elif name == "nb_nearest_m":
            col_vals = np.where(np.isnan(col_vals), 999.0, col_vals)
        X.insert(j, name, col_vals)
    return X


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


def new_model():
    return RandomForestRegressor(
        n_estimators=150,
        max_depth=14,
        min_samples_leaf=4,
        max_features=0.6,
        n_jobs=-1,
        random_state=42,
    )


def cross_validate(table, values, measured_idx, splits, method):
    parts = []
    for tr, te in splits:
        tr_idx, te_idx = measured_idx[tr], measured_idx[te]
        default = float(np.median(values[tr_idx]))
        if method == "neighbours":
            est, _ = neighbour_estimates(table, tr_idx, te_idx, values, default)
            preds = np.where(np.isnan(est), default, est)
        else:
            X_tr = add_neighbour_features(table, tr_idx, tr_idx, values)
            X_te = add_neighbour_features(table, tr_idx, te_idx, values)
            preds = new_model().fit(X_tr[FEATURES], values[tr_idx]).predict(X_te[FEATURES])
        parts.append(pd.DataFrame({"y": values[te_idx], "default": default, method: preds}))
    return pd.concat(parts, ignore_index=True)


def scores(cv, method):
    out = {m: {"mae": round(float(mean_absolute_error(cv.y, cv[m])), 4), "r2": round(float(r2_score(cv.y, cv[m])), 4)}
           for m in ("default", method)}
    out[method]["spearman"] = round(float(spearmanr(cv.y, cv[method]).statistic), 4)
    return out


def spatial_blocks(table, idx, size_m=1000):
    lat0 = math.radians(table.lat.mean())
    gx = np.floor(table.lon.values[idx] * 111_320 * math.cos(lat0) / size_m).astype(int)
    gy = np.floor(table.lat.values[idx] * 110_540 / size_m).astype(int)
    return gx * 100_000 + gy


def way_estimates(table, segment_idx, predictions, measured_ways):
    acc = {}
    for i, p in zip(segment_idx, predictions):
        for way in table.ways.values[i]:
            if way not in measured_ways:
                acc.setdefault(way, []).append(float(p))
    return {way: sum(v) / len(v) for way, v in acc.items()}


def plot_performance(cv, target, metrics, path, method):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    lim = [0, max(cv.y.max(), cv[method].max()) * 1.05]
    axes[0].scatter(cv.y, cv[method], s=8, alpha=0.25, color="#16a085", edgecolors="none")
    axes[0].plot(lim, lim, "--", color="#e74c3c", label="perfect 1:1")
    axes[0].set(xlim=lim, ylim=lim, xlabel=f"measured {target}", ylabel=f"estimated {target} ({method})")
    axes[0].set_title(f"Held-out Streets (R2: {metrics[method]['r2']:.3f}, MAE: {metrics[method]['mae']:.2f})", fontweight="bold")
    axes[0].legend()

    for m, color in ((method, "#2980b9"), ("default", "#95a5a6")):
        axes[1].hist(cv.y - cv[m], bins=50, alpha=0.6, color=color, label=f"{m}: MAE {metrics[m]['mae']:.3g}")
    axes[1].axvline(0, ls="--", color="#e74c3c")
    axes[1].set(xlabel="error (measured - estimated)", ylabel="segments")
    axes[1].set_title("Error Residuals vs Default", fontweight="bold")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_feature_importance(model, target, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values().tail(15)
    fig = plt.figure(figsize=(10, 6), dpi=150)
    colors = [
        "#e67e22" if f.startswith("highway_") else ("#2ecc71" if f.startswith("surface_") else "#3498db")
        for f in imp.index
    ]
    plt.barh(imp.index, imp.values, color=colors)
    plt.title(f"{target}: Feature Importance (Orange=Highway, Green=Surface, Blue=Geo)", fontweight="bold")
    plt.xlabel("Random Forest Relative Importance")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def impute_target(target, table, road_osmids, load):
    cfg = TARGETS[target]
    method = cfg["method"]
    measured = measured_values(load(cfg["source"]), cfg["index_key"], cfg["value_key"], road_osmids)
    values = np.full(len(table), np.nan)
    values[list(measured)] = list(measured.values())
    measured_idx = np.array(sorted(measured))
    unmeasured_idx = np.array([i for i in range(len(table)) if i not in measured])
    print(f"\n[{target}] {len(measured_idx)} measured / {len(table)} segments, method: {method}")

    splits = {
        "cv_unseen_streets": GroupKFold(CV_FOLDS).split(measured_idx, groups=table.street.values[measured_idx]),
        "cv_unseen_1km_areas": GroupKFold(CV_FOLDS).split(measured_idx, groups=spatial_blocks(table, measured_idx)),
    }
    if method == "neighbours":
        # Unmeasured parts of measured streets: the same-street rule only shows up here.
        splits["cv_random_segments"] = KFold(CV_FOLDS, shuffle=True, random_state=0).split(measured_idx)
    cv = {name: cross_validate(table, values, measured_idx, list(sp), method) for name, sp in splits.items()}
    cv_scores = {name: scores(c, method) for name, c in cv.items()}
    for name, sc in cv_scores.items():
        print(f"  {name:20} default MAE {sc['default']['mae']:.3f} | {method} MAE {sc[method]['mae']:.3f} "
              f"R2 {sc[method]['r2']:.3f} Spearman {sc[method]['spearman']:.3f}")

    default = float(np.median(values[measured_idx]))
    if method == "neighbours":
        est, weight = neighbour_estimates(table, measured_idx, unmeasured_idx, values, default)
        known = ~np.isnan(est)
        est_idx, preds = unmeasured_idx[known], np.clip(est[known], 0.0, 100.0)
    else:
        X_fit = add_neighbour_features(table, measured_idx, measured_idx, values)
        model = new_model().fit(X_fit[FEATURES], values[measured_idx])
        X_unmeasured = add_neighbour_features(table, measured_idx, unmeasured_idx, values)
        preds = np.clip(model.predict(X_unmeasured[FEATURES]), 0.0, 100.0 if target == "roughness" else 1.0)
        est_idx = unmeasured_idx
        plot_feature_importance(model, target, ML_DIR / f"{target}_feature_importance.png")

    measured_ways = {w for i in measured_idx for w in table.ways.values[i]}
    ways = way_estimates(table, est_idx, preds, measured_ways)

    out_path = DATA_DIR / f"ml_predicted_{target}.json"
    out_path.write_text(json.dumps({str(k): round(v, 4) for k, v in sorted(ways.items())}, indent=0))
    plot_performance(cv["cv_unseen_streets"], target, cv_scores["cv_unseen_streets"],
                     ML_DIR / f"{target}_performance.png", method)

    print(f"  Exported {len(ways)} way estimates to {out_path.name}")
    print(f"  Estimates: min={preds.min():.2f}, p50={np.median(preds):.2f}, max={preds.max():.2f}")

    coverage = {
        "segments_measured": len(measured_idx),
        "segments_estimated": len(est_idx),
        "segments_unknown": len(unmeasured_idx) - len(est_idx),
        "ways_estimated": len(ways),
    }
    if method == "neighbours":
        coverage["segments_estimated_by_weight"] = {
            str(w): int((weight == w).sum()) for w in (1.0, *(s for _, s in SHRINK_BY_NEAREST_M))
        }
    return {"method": method, "default_value": round(default, 4), **{n: {"n": len(c), **cv_scores[n]} for n, c in cv.items()},
            "coverage": coverage}


def main():
    from download_data import load_features

    roads = load_features("road_network_heilbronn")
    table = segment_table(roads)
    road_osmids = [str(f["properties"].get("osmid")) for f in roads]
    
    summary = {
        "settings": {"features_count": len(FEATURES), "cv_folds": CV_FOLDS},
        **{t: impute_target(t, table, road_osmids, load_features) for t in TARGETS},
    }
    (ML_DIR / "metrics.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {ML_DIR / 'metrics.json'}")
    return summary


if __name__ == "__main__":
    main()

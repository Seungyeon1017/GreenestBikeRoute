"""Fill in roughness and traffic flow for unmeasured Heilbronn streets using OSM highway & surface tags.

    python ml/train_imputer.py

Workflow:
1. Loads cached OSM tags from `data/osm_tags_cache.json` (fetched from official OSM API).
2. Uses road hierarchy (`highway`: primary, secondary, residential, track, cycleway, path...)
   to fill missing `surface` tags (e.g. track -> gravel, primary -> asphalt).
3. Trains a Random Forest Regressor on measured sensor data (`bumpy_roads_heilbronn` & `traffic_flow_heilbronn`)
   using physical infrastructure tags (`highway`, `surface`), geometry (`length`, `sinuosity`),
   spatial position (`c_lat`, `c_lon`, `dist_center`), and spatial neighbours.
4. Preserves full dynamic range (roughness up to 60+, traffic flow from 0.08 to 0.95)
   without artificial shrinkage flattening the contrast.
5. Evaluates with GroupKFold cross-validation on unseen streets and unseen 1 km spatial blocks.

Outputs:
  data/ml_predicted_roughness.json, data/ml_predicted_traffic_flow.json
  ml/metrics.json
  ml/<target>_performance.png, ml/<target>_feature_importance.png
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
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ML_DIR = PROJECT_ROOT / "ml"

EARTH_RADIUS_M = 6_371_000
RADIUS_M = 250
MIN_NEIGHBOURS = 2
K_NEIGHBOURS = 25
IDW_OFFSET_M = 25
CV_FOLDS = 5

TARGETS = {
    "roughness": {"source": "bumpy_roads_heilbronn", "index_key": "id", "value_key": "Normalized Roughness"},
    "traffic_flow": {"source": "traffic_flow_heilbronn", "index_key": "road_segment", "value_key": "avg_traffic_flow"},
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


def new_model():
    return RandomForestRegressor(
        n_estimators=150,
        max_depth=14,
        min_samples_leaf=4,
        max_features=0.6,
        n_jobs=-1,
        random_state=42,
    )


def cross_validate(table, values, measured_idx, groups):
    parts = []
    for tr, te in GroupKFold(CV_FOLDS).split(measured_idx, groups=groups):
        tr_idx, te_idx = measured_idx[tr], measured_idx[te]
        X_tr = add_neighbour_features(table, tr_idx, tr_idx, values)
        X_te = add_neighbour_features(table, tr_idx, te_idx, values)
        
        model = new_model().fit(X_tr[FEATURES], values[tr_idx])
        preds = model.predict(X_te[FEATURES])
        default = float(np.median(values[tr_idx]))
        
        parts.append(pd.DataFrame({
            "y": values[te_idx],
            "default": default,
            "random_forest": preds,
        }))
    return pd.concat(parts, ignore_index=True)


def scores(cv):
    return {m: {"mae": round(float(mean_absolute_error(cv.y, cv[m])), 4), "r2": round(float(r2_score(cv.y, cv[m])), 4)}
            for m in ("default", "random_forest")}


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


def plot_performance(cv, target, metrics, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    lim = [0, max(cv.y.max(), cv["random_forest"].max()) * 1.05]
    axes[0].scatter(cv.y, cv["random_forest"], s=8, alpha=0.25, color="#16a085", edgecolors="none")
    axes[0].plot(lim, lim, "--", color="#e74c3c", label="perfect 1:1")
    axes[0].set(xlim=lim, ylim=lim, xlabel=f"measured {target}", ylabel=f"estimated {target} (Random Forest)")
    axes[0].set_title(f"Held-out Streets (R2: {metrics['random_forest']['r2']:.3f}, MAE: {metrics['random_forest']['mae']:.2f})", fontweight="bold")
    axes[0].legend()

    for m, color in (("random_forest", "#2980b9"), ("default", "#95a5a6")):
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
    measured = measured_values(load(cfg["source"]), cfg["index_key"], cfg["value_key"], road_osmids)
    values = np.full(len(table), np.nan)
    values[list(measured)] = list(measured.values())
    measured_idx = np.array(sorted(measured))
    unmeasured_idx = np.array([i for i in range(len(table)) if i not in measured])
    print(f"\n[{target}] {len(measured_idx)} measured / {len(table)} segments")

    cv_street = cross_validate(table, values, measured_idx, table.street.values[measured_idx])
    cv_area = cross_validate(table, values, measured_idx, spatial_blocks(table, measured_idx))
    s_street, s_area = scores(cv_street), scores(cv_area)
    
    print(f"  CV unseen streets (n={len(cv_street)}): default MAE {s_street['default']['mae']:.3f} | RF MAE {s_street['random_forest']['mae']:.3f} R2 {s_street['random_forest']['r2']:.3f}")
    print(f"  CV unseen areas   (n={len(cv_area)}): default MAE {s_area['default']['mae']:.3f} | RF MAE {s_area['random_forest']['mae']:.3f} R2 {s_area['random_forest']['r2']:.3f}")

    # Fit final Random Forest model on all measured segments
    X_fit = add_neighbour_features(table, measured_idx, measured_idx, values)
    model = new_model().fit(X_fit[FEATURES], values[measured_idx])

    # Predict for all unmeasured segments
    X_unmeasured = add_neighbour_features(table, measured_idx, unmeasured_idx, values)
    preds = model.predict(X_unmeasured[FEATURES])
    
    # Clip to valid domains
    if target == "roughness":
        preds = np.clip(preds, 0.0, 100.0)
    else:
        preds = np.clip(preds, 0.0, 1.0)

    measured_ways = {w for i in measured_idx for w in table.ways.values[i]}
    ways = way_estimates(table, unmeasured_idx, preds, measured_ways)
    
    out_path = DATA_DIR / f"ml_predicted_{target}.json"
    out_path.write_text(json.dumps({str(k): round(v, 4) for k, v in sorted(ways.items())}, indent=0))

    plot_performance(cv_street, target, s_street, ML_DIR / f"{target}_performance.png")
    plot_feature_importance(model, target, ML_DIR / f"{target}_feature_importance.png")

    print(f"  Exported {len(ways)} way estimates to {out_path.name}")
    print(f"  Prediction summary (dynamic range): min={preds.min():.2f}, p50={np.median(preds):.2f}, max={preds.max():.2f}")

    return {
        "method": "random_forest",
        "default_value": round(float(np.median(values[measured_idx])), 4),
        "cv_unseen_streets": {"n": len(cv_street), **s_street},
        "cv_unseen_1km_areas": {"n": len(cv_area), **s_area},
        "coverage": {
            "segments_measured": len(measured_idx),
            "segments_estimated": len(unmeasured_idx),
            "ways_estimated": len(ways),
        },
    }


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

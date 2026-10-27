"""Machine Learning Imputation for Road Roughness in Heilbronn.

This script trains a spatial regression model (Random Forest) on measured bike sensor data
from `data/bumpy_roads_heilbronn.geojson` (9,599 segments) and OpenStreetMap road attributes
to predict Normalized Roughness (0-100) for all 34,243 road segments in Heilbronn.

Outputs:
  - data/ml_predicted_roughness.json: Dictionary mapping OSM way id (int) to roughness (float)
  - ml/roughness_model.joblib: Trained scikit-learn model pipeline
  - ml/feature_importance.png: Presentation-ready chart of top predictive features
  - ml/model_performance.png: Actual vs Predicted evaluation plot
"""
import ast
import json
import math
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ML_DIR = PROJECT_ROOT / "ml"

HEILBRONN_CENTER_LAT = 49.1427
HEILBRONN_CENTER_LON = 9.2195


def parse_osm_ids(osmid_val):
    """Parse OSM way id which can be an int, string '123', or string '[123, 456]'."""
    s = str(osmid_val).strip()
    if s.startswith("[") and s.endswith("]"):
        try:
            return [int(x) for x in ast.literal_eval(s)]
        except Exception:
            return []
    try:
        return [int(s)]
    except ValueError:
        return []


def calculate_length_and_centroid(coordinates):
    """Calculate approximate length in meters, vertex count, and centroid of a LineString."""
    if not coordinates or len(coordinates) < 2:
        return 0.0, len(coordinates) if coordinates else 0, HEILBRONN_CENTER_LAT, HEILBRONN_CENTER_LON, 1.0, 0.0

    total_m = 0.0
    for i in range(len(coordinates) - 1):
        x1, y1 = coordinates[i]
        x2, y2 = coordinates[i + 1]
        mid_lat = math.radians((y1 + y2) / 2.0)
        dx = (x2 - x1) * 111320.0 * math.cos(mid_lat)
        dy = (y2 - y1) * 110540.0
        total_m += math.hypot(dx, dy)

    lons = [c[0] for c in coordinates]
    lats = [c[1] for c in coordinates]
    c_lon = sum(lons) / len(lons)
    c_lat = sum(lats) / len(lats)

    # Sinuosity (actual length / straight line distance)
    x1, y1 = coordinates[0]
    x2, y2 = coordinates[-1]
    mid_lat = math.radians((y1 + y2) / 2.0)
    end_dist = math.hypot((x2 - x1) * 111320.0 * math.cos(mid_lat), (y2 - y1) * 110540.0)
    sinuosity = total_m / max(end_dist, 1.0)

    # Distance to city center
    dx_c = (c_lon - HEILBRONN_CENTER_LON) * 111320.0 * math.cos(math.radians(HEILBRONN_CENTER_LAT))
    dy_c = (c_lat - HEILBRONN_CENTER_LAT) * 110540.0
    dist_center = math.hypot(dx_c, dy_c)

    return total_m, len(coordinates), c_lat, c_lon, sinuosity, dist_center


def clean_surface_tag(raw_surface):
    """Normalize surface string, handling lists like ['asphalt', 'paving_stones']."""
    if not raw_surface:
        return "unknown"
    if isinstance(raw_surface, list):
        raw_surface = raw_surface[0] if raw_surface else "unknown"
    surf = str(raw_surface).strip().lower()
    return surf if surf and surf != "none" else "unknown"


def extract_features(props, geom, rn_props=None, tf_lookup=None, sm_lookup=None):
    """Extract tabular features from GeoJSON properties and geometry."""
    rn_props = rn_props or {}
    coords = geom.get("coordinates", []) if geom else []
    length_m, num_pts, c_lat, c_lon, sinuosity, dist_center = calculate_length_and_centroid(coords)

    # Merge properties (road_network has richer OSM tags like surface)
    raw_surface = rn_props.get("surface") or props.get("surface")
    surface = clean_surface_tag(raw_surface)

    name = str(props.get("name") or rn_props.get("name") or "").lower()
    cycleway = str(props.get("cycleway") or rn_props.get("cycleway") or "none").lower()
    junction = str(props.get("junction") or rn_props.get("junction") or "none").lower()
    oneway = 1 if (props.get("oneway") or rn_props.get("oneway")) else 0

    # Traffic & speed enrichment if available
    osmid_str = str(props.get("osmid") or rn_props.get("osmid") or "")
    traffic_flow = 0.0
    has_traffic = 0
    if tf_lookup and osmid_str in tf_lookup:
        traffic_flow = float(tf_lookup[osmid_str])
        has_traffic = 1

    avg_speed = 0.0
    has_speed = 0
    if sm_lookup and osmid_str in sm_lookup:
        avg_speed = float(sm_lookup[osmid_str])
        has_speed = 1

    return {
        "surface": surface,
        "cycleway": cycleway,
        "junction": junction,
        "oneway": oneway,
        "length_m": length_m,
        "num_pts": num_pts,
        "c_lat": c_lat,
        "c_lon": c_lon,
        "sinuosity": sinuosity,
        "dist_center": dist_center,
        "is_weg": int("weg" in name or "pfad" in name),
        "is_strasse": int("str" in name),
        "is_gasse": int("gasse" in name),
        "is_platz": int("platz" in name),
        "is_brucke": int("brücke" in name or "steg" in name),
        "has_name": int(bool(name and name != "none")),
        "has_traffic": has_traffic,
        "avg_traffic_flow": traffic_flow,
        "has_speed": has_speed,
        "avg_speed": avg_speed,
    }


def load_dataset():
    """Load raw geojson datasets from data/."""
    bumpy_path = DATA_DIR / "bumpy_roads_heilbronn.geojson"
    road_net_path = DATA_DIR / "road_network_heilbronn.geojson"

    if not bumpy_path.exists() or not road_net_path.exists():
        raise FileNotFoundError(
            f"Missing required data files. Ensure {bumpy_path.name} and {road_net_path.name} exist."
        )

    with open(bumpy_path, "r", encoding="utf-8") as f:
        bumpy_data = json.load(f)
    with open(road_net_path, "r", encoding="utf-8") as f:
        road_net_data = json.load(f)

    # Optional traffic & speed datasets
    tf_lookup = {}
    tf_path = DATA_DIR / "traffic_flow_heilbronn.geojson"
    if tf_path.exists():
        with open(tf_path, "r", encoding="utf-8") as f:
            for feat in json.load(f).get("features", []):
                osmid = str(feat["properties"].get("osmid"))
                val = feat["properties"].get("avg_traffic_flow")
                if val is not None:
                    tf_lookup[osmid] = val

    sm_lookup = {}
    sm_path = DATA_DIR / "speed_map_heilbronn.geojson"
    if sm_path.exists():
        with open(sm_path, "r", encoding="utf-8") as f:
            for feat in json.load(f).get("features", []):
                osmid = str(feat["properties"].get("osmid"))
                val = feat["properties"].get("avg_speed[km/h]")
                if val is not None:
                    sm_lookup[osmid] = val

    return bumpy_data, road_net_data, tf_lookup, sm_lookup


def build_pipeline():
    """Construct Scikit-Learn preprocessing and Random Forest Regressor pipeline."""
    cat_cols = ["surface", "cycleway", "junction"]
    num_cols = [
        "oneway",
        "length_m",
        "num_pts",
        "c_lat",
        "c_lon",
        "sinuosity",
        "dist_center",
        "is_weg",
        "is_strasse",
        "is_gasse",
        "is_platz",
        "is_brucke",
        "has_name",
        "has_traffic",
        "avg_traffic_flow",
        "has_speed",
        "avg_speed",
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("num", "passthrough", num_cols),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=14,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", model),
    ])
    return pipeline, cat_cols, num_cols


def plot_feature_importance(pipeline, cat_cols, num_cols, output_path):
    """Plot the top 15 most important features for Pitch presentation."""
    encoder = pipeline.named_steps["preprocessor"].named_transformers_["cat"]
    cat_names = list(encoder.get_feature_names_out(cat_cols))
    all_feature_names = cat_names + num_cols

    importances = pipeline.named_steps["regressor"].feature_importances_
    feat_df = pd.DataFrame({"feature": all_feature_names, "importance": importances})
    feat_df = feat_df.sort_values(by="importance", ascending=True).tail(15)

    plt.figure(figsize=(10, 6), dpi=200)
    colors = ["#2ecc71" if "surface" in f or "weg" in f or "cycleway" in f else "#3498db" for f in feat_df["feature"]]
    bars = plt.barh(feat_df["feature"], feat_df["importance"], color=colors, edgecolor="none", height=0.65)
    plt.title("GreenestBikeRoute: Road Roughness Predictors (Feature Importance)", fontsize=13, fontweight="bold", pad=15)
    plt.xlabel("Random Forest Relative Importance", fontsize=11)
    plt.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f" Saved feature importance chart to: {output_path}")


def plot_performance(y_true, y_pred, output_path):
    """Plot actual vs predicted scatter and residual distribution."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=200)

    # Scatter
    axes[0].scatter(y_true, y_pred, alpha=0.25, color="#16a085", s=15, edgecolors="none")
    lims = [0, max(np.max(y_true), np.max(y_pred)) * 1.05]
    axes[0].plot(lims, lims, color="#e74c3c", linestyle="--", linewidth=1.5, label="Perfect 1:1 line")
    axes[0].set_xlim(lims)
    axes[0].set_ylim(lims)
    axes[0].set_title("Actual vs Predicted Roughness", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Measured Roughness (ATRAI Sensor)", fontsize=10)
    axes[0].set_ylabel("Predicted Roughness (ML Model)", fontsize=10)
    axes[0].grid(True, linestyle=":", alpha=0.6)
    axes[0].legend()

    # Residuals
    residuals = y_true - y_pred
    axes[1].hist(residuals, bins=40, color="#2980b9", edgecolor="white", alpha=0.85)
    axes[1].axvline(0, color="#e74c3c", linestyle="--", linewidth=1.5)
    axes[1].set_title("Error Distribution (Residuals)", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Residual (True - Predicted)", fontsize=10)
    axes[1].set_ylabel("Number of Road Segments", fontsize=10)
    axes[1].grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print(f" Saved model performance plot to: {output_path}")


def train_and_impute():
    """Main execution function."""
    print("=" * 60)
    print("GreenestBikeRoute: Training Road Roughness Imputer")
    print("=" * 60)

    # 1. Load data
    bumpy_data, road_net_data, tf_lookup, sm_lookup = load_dataset()
    print(f"Loaded {len(bumpy_data.get('features', []))} measured bumpy segments.")
    print(f"Loaded {len(road_net_data.get('features', []))} total road network segments.")

    # Index road_network by osmid for rapid property lookup
    rn_lookup = {}
    for feat in road_net_data.get("features", []):
        p = feat["properties"]
        for way in parse_osm_ids(p.get("osmid")):
            rn_lookup[str(way)] = p

    # 2. Build training dataset from bumpy_roads
    X_train_rows = []
    y_train = []
    measured_ways = {}

    for feat in bumpy_data.get("features", []):
        p = feat["properties"]
        roughness = p.get("Normalized Roughness")
        if roughness is None or np.isnan(roughness):
            continue

        osmids = parse_osm_ids(p.get("osmid"))
        primary_rn_props = rn_lookup.get(str(osmids[0])) if osmids else None

        f_dict = extract_features(
            props=p,
            geom=feat["geometry"],
            rn_props=primary_rn_props,
            tf_lookup=tf_lookup,
            sm_lookup=sm_lookup,
        )
        X_train_rows.append(f_dict)
        y_train.append(float(roughness))

        for way in osmids:
            measured_ways.setdefault(way, []).append(float(roughness))

    df_train = pd.DataFrame(X_train_rows)
    y_train = np.array(y_train)

    # Compute measured average per way
    way_ground_truth = {way: sum(v) / len(v) for way, v in measured_ways.items()}
    print(f"Unique OSM ways measured by bike sensors: {len(way_ground_truth)}")

    # 3. Cross-Validation
    pipeline, cat_cols, num_cols = build_pipeline()
    print("Running 5-Fold Cross Validation...")
    cv_scores = cross_validate(
        pipeline,
        df_train,
        y_train,
        cv=5,
        scoring=["r2", "neg_mean_absolute_error", "neg_root_mean_squared_error"],
        n_jobs=-1,
    )
    cv_r2 = float(cv_scores["test_r2"].mean())
    cv_mae = float(-cv_scores["test_neg_mean_absolute_error"].mean())
    cv_rmse = float(-cv_scores["test_neg_root_mean_squared_error"].mean())

    print(f" 5-Fold CV R^2:  {cv_r2:.4f}")
    print(f" 5-Fold CV MAE:  {cv_mae:.2f} (on 0-100 scale)")
    print(f" 5-Fold CV RMSE: {cv_rmse:.2f}")

    # 4. Fit on all training data
    print("Training final Random Forest model...")
    pipeline.fit(df_train, y_train)

    # Save model
    ML_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ML_DIR / "roughness_model.joblib"
    joblib.dump(pipeline, model_path)
    print(f" Saved model pipeline to: {model_path}")

    # Visualizations
    plot_feature_importance(pipeline, cat_cols, num_cols, ML_DIR / "feature_importance.png")
    train_preds = pipeline.predict(df_train)
    plot_performance(y_train, train_preds, ML_DIR / "model_performance.png")

    # 5. Predict for ALL road network segments (Spatial Imputation)
    print("Predicting roughness for all road network segments...")
    inference_rows = []
    rn_features = road_net_data.get("features", [])

    for feat in rn_features:
        p = feat["properties"]
        f_dict = extract_features(
            props=p,
            geom=feat["geometry"],
            rn_props=p,
            tf_lookup=tf_lookup,
            sm_lookup=sm_lookup,
        )
        inference_rows.append(f_dict)

    df_inf = pd.DataFrame(inference_rows)
    all_preds = pipeline.predict(df_inf)
    all_preds = np.clip(all_preds, 0.0, 100.0)

    # 6. Build combined way -> roughness dictionary
    # Priority:
    # 1. Physical sensor measurement (Ground Truth) if available
    # 2. ML Spatial Prediction if unmeasured
    final_way_roughness = {}
    ml_imputed_count = 0
    measured_count = 0

    # Aggregate predictions across segments by osmid
    predicted_way_acc = {}
    for feat, pred_val in zip(rn_features, all_preds):
        osmids = parse_osm_ids(feat["properties"].get("osmid"))
        for way in osmids:
            predicted_way_acc.setdefault(way, []).append(pred_val)

    # Merge: ground truth takes precedence
    all_ways = set(predicted_way_acc.keys()) | set(way_ground_truth.keys())
    for way in all_ways:
        if way in way_ground_truth:
            final_way_roughness[way] = round(way_ground_truth[way], 2)
            measured_count += 1
        elif way in predicted_way_acc:
            preds = predicted_way_acc[way]
            final_way_roughness[way] = round(float(sum(preds) / len(preds)), 2)
            ml_imputed_count += 1

    print(f"Total city ways populated: {len(final_way_roughness)}")
    print(f"   - Physically measured: {measured_count} ways ({measured_count/len(final_way_roughness)*100:.1f}%)")
    print(f"   - ML imputed:          {ml_imputed_count} ways ({ml_imputed_count/len(final_way_roughness)*100:.1f}%)")

    # 7. Export JSON
    out_json = DATA_DIR / "ml_predicted_roughness.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({str(k): v for k, v in final_way_roughness.items()}, f, indent=2)
    print(f" Exported way roughness to: {out_json}")

    # Summary metrics file for presentation
    summary = {
        "metrics": {
            "5_fold_cv_r2": round(cv_r2, 4),
            "5_fold_cv_mae": round(cv_mae, 2),
            "5_fold_cv_rmse": round(cv_rmse, 2),
        },
        "coverage": {
            "total_ways": len(final_way_roughness),
            "measured_ways": measured_count,
            "ml_imputed_ways": ml_imputed_count,
            "ml_coverage_ratio": round(ml_imputed_count / len(final_way_roughness), 3),
        },
    }
    with open(ML_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 60)
    print("ML Pipeline Complete!")
    print("=" * 60)
    return summary


if __name__ == "__main__":
    train_and_impute()

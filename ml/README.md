# GreenestBikeRoute: Spatial Machine Learning Imputation

## 🎯 The Hackathon Problem
Heilbronn has **34,243 road segments** across **11,011 unique OpenStreetMap ways**. However, IoT bike sensor coverage is inherently sparse:
* **Measured with Physical Sensors**: 3,873 ways (35.2% of city network).
* **Unmeasured (Missing Data)**: 7,138 ways (64.8% of city network).

Previously, any unmeasured street defaulted to a flat fallback of `10.0`, blinding the routing engine to unmeasured cobblestone streets, gravel paths, or smooth cycleways.

---

## 🤖 The ML Solution: Spatial Random Forest Imputer
We implemented a spatial regression pipeline using **Random Forest Regressor** trained on the 9,599 measured sensor segments from ATRAI (`data/bumpy_roads_heilbronn.geojson`) cross-referenced with OpenStreetMap road geometry and attributes (`data/road_network_heilbronn.geojson`).

### Extracted Features:
1. **Pavement & Infrastructure**:
   - `surface`: Asphalt, paving stones, sett, gravel, fine gravel, grass, concrete, cobblestone, etc.
   - `cycleway`: Dedicated bike lane, shared lane, none, etc.
   - `junction`: Roundabouts, standard junctions.
   - `oneway`: Directional constraints.
2. **Road Geometry & Sinuosity**:
   - `length_m`: Accurate geodesic road length.
   - `num_pts`: Vertex count / geometry complexity.
   - `sinuosity`: Curviness ratio (actual path length / straight line endpoint distance).
3. **Spatial Location**:
   - `c_lat`, `c_lon`: Geographic centroid.
   - `dist_center`: Distance to Heilbronn city center.
4. **German Street Semantics**:
   - `is_weg`: Flag for paths/trails ("Weg", "Pfad" - frequently gravel/unpaved).
   - `is_strasse`: Flag for urban streets ("Straße").
   - `is_gasse`: Flag for narrow historic alleys ("Gasse" - frequently historic paving).
   - `is_platz`: Public plazas / town squares.
   - `is_brucke`: Bridges and footbridges.
5. **Traffic & Dynamics (where available)**:
   - `avg_traffic_flow` & `avg_speed[km/h]` from ATRAI monitoring.

---

## 📊 Model Evaluation (5-Fold Cross Validation)
* **$R^2$ Score**: `0.3345` (explains 1/3 of sensor roughness variance purely from OSM attributes).
* **Mean Absolute Error (MAE)**: `5.04` (on a 0-100 scale, meaning predictions are on average within ±5 points of actual sensor readings).
* **Root Mean Squared Error (RMSE)**: `7.60`.

### Presentation Assets Generated:
* `ml/feature_importance.png`: Feature importance breakdown chart (ready for pitch slide).
* `ml/model_performance.png`: Scatter plot of actual vs. predicted roughness and error residuals.
* `ml/metrics.json`: Machine-readable summary for API or dashboards.
* `data/ml_predicted_roughness.json`: Precomputed roughness for all 11,011 city ways.

---

## 🤝 GitHub Collaboration & Compatibility
* **Zero Overhead for Teammates**: The precomputed results are stored in `data/ml_predicted_roughness.json` (229 KB). Teammates pulling from GitHub do **not** need to retrain or install heavy ML libraries if they are only working on frontend/backend.
* **Graceful Fallback**: `routing/graph.py` automatically loads ML predictions if available, falls back to physical measurements, and retains `DEFAULT_ROUGHNESS` as a safety net.
* **100% Passing Tests**: All existing unit tests pass without breakage.

---

## 🚀 How to Retrain (Optional)
```bash
python ml/train_imputer.py
```

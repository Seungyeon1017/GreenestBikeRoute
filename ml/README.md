# GreenestBikeRoute: Physical & Spatial Feature Imputation

## The Problem
Heilbronn's road network (`data/road_network_heilbronn.geojson`) has **34,243 segments** across **11,011 OSM ways**, while ATRAI bike sensor measurements only cover part of the city:
* **Road Roughness (`bumpy_roads_heilbronn`)**: 9,599 measured segments (28.0% of segments).
* **Traffic Flow (`traffic_flow_heilbronn`)**: 7,153 measured segments (20.9% of segments).

## Methodology: Highway-Aware Feature Engineering & Random Forest
Instead of collapsing predictions into an overly smoothed average, we use OpenStreetMap's physical road infrastructure hierarchy to anchor predictions:
1. **Official OSM Tags Retrieval** (`ml/fetch_osm_highways.py`):
   - Queries `api.openstreetmap.org/api/0.6/ways` for all 11,011 unique ways in the Heilbronn network.
   - Retrieves official `highway` (primary, secondary, residential, service, track, path...) and `surface` tags.
   - Saved locally to `data/osm_tags_cache.json`.
2. **Domain-Rule Surface Imputation (FillNA)**:
   - When `surface` is unspecified, it is imputed using international cycling routing criteria:
     `track` -> gravel, `path` -> ground, `primary/secondary/residential` -> asphalt, `living_street` -> paving stones.
   - Reduces unknown surfaces across the 34,243 segments from 26.5% down to under 2.0%.
3. **Random Forest Regression with Preserved Dynamic Range**:
   - Features: `highway` (one-hot), `surface` (one-hot), `length`, `sinuosity`, `oneway`, `has_cycleway`, `is_weg`, `is_gasse`, `c_lat`, `c_lon`, and spatial neighbour signals.
   - Restores the natural contrast needed for route planning:
     - **Roughness**: spans from **2.68** (smooth asphalt/cycleway) up to **61.50** (rough cobblestone/track).
     - **Traffic Flow**: spans from **0.08** (quiet paths/living streets) up to **0.96** (busy major arterial roads).

## Validation Results (5-Fold Group Cross-Validation on Unseen Streets)

| Target | Sample Size | Baseline Default MAE | Random Forest MAE | Held-Out $R^2$ | Dynamic Range (Min - Max) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Roughness** (0–100) | `n=9,599` | 6.13 | **5.91** | 0.148 | **2.68 – 61.50** |
| **Traffic Flow** (0–1) | `n=7,153` | 0.127 | **0.105** | **0.315** | **0.08 – 0.96** |

## Outputs
* `data/osm_tags_cache.json`: Cached OSM highway & surface tags for all 11,011 ways.
* `data/ml_predicted_roughness.json`: Roughness estimates for 7,138 unmeasured OSM ways.
* `data/ml_predicted_traffic_flow.json`: Traffic flow estimates for 6,784 unmeasured OSM ways.
* `data/road_network_enriched_heilbronn.geojson`: Complete 34,243-segment GeoJSON with `highway`, `surface`, `roughness`, `traffic_flow`, and provenance sources (`measured` / `estimated`).
* `ml/roughness_performance.png` & `ml/traffic_flow_performance.png`: Validation plots on unseen held-out streets.
* `ml/roughness_feature_importance.png` & `ml/traffic_flow_feature_importance.png`: Feature importance breakdown charts.

## Retraining & Re-exporting
```bash
.venv/bin/python ml/train_imputer.py
.venv/bin/python ml/export_enriched_geojson.py
```

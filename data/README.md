# data/

fetched by `download_data.py`, logged in `manifest.json`, Heilbronn only.

## `ready-made/`
ATRAI collections as served (`api.atrai.bike`); for details, see https://hackathon.greencity.hn/resources/bike-data
- `tracks` and `statistics` are filtered to Heilbronn

Routing uses `bumpy_roads`, `traffic_flow` and `speed_map` from here.

## `custom/`
Built by us from raw `osem_bike_data`, used by routing
- `danger_zones_raw_heilbronn`: overtakes with device + exact distance
- `air_quality_heilbronn`: fine dust (PM1–PM10), outliers removed
- `shade_heilbronn`: street-tree canopy per OSM way (`routing.shade`)
- `shadow_heilbronn`: building and tree shadow per OSM way and time slot (`routing.shadow`)
- `roughness_estimates_heilbronn.json`: roughness for unmeasured OSM ways near measured streets, from `bumpy_roads` by `estimation/estimate_roughness.py` (see [estimation/README.md](../estimation/README.md))

Details: [routing/README.md](../routing/README.md)

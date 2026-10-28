# data/

fetched by `download_data.py`, logged in `manifest.json`, Heilbronn only.

## `ready-made/`
ATRAI collections as served (`api.atrai.bike`); for details, see https://hackathon.greencity.hn/resources/bike-data
- `tracks` and `statistics` are filtered to Heilbronn

Routing uses `bumpy_roads` and `traffic_flow` from here.

## `custom/`
Built by us from raw `osem_bike_data`, used by routing
- `danger_zones_raw_heilbronn`: overtakes with device + exact distance
- `air_quality_heilbronn`: fine dust (PM1–PM10), outliers removed

Details: [routing/README.md](../routing/README.md)

# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Getting the data

We only use the **Heilbronn** campaign of the [ATRAI senseBox:bike data](https://hackathon.greencity.hn/resources/bike-data) (API: `https://api.atrai.bike`).

```bash
pip install requests
python -X utf8 download_data.py          # ~85 MB into ./data, skips files you already have
```

`-X utf8` is needed on Windows because street names contain non-ASCII characters.
Options: `--only bumpy_roads road_network` (subset), `--force` (re-download), `--large` (also the raw 1M+ row collections; untested, expect a very long download and GBs of disk).

| File in `data/` | One feature is | Rows |
|---|---|---|
| `bumpy_roads_heilbronn.geojson` | measured street segment, with roughness | 9,599 |
| `road_network_heilbronn.geojson` | OSM street segment (all bike-relevant streets, incl. unmeasured) | 34,243 |
| `bike_road_network_heilbronn.geojson` | same, without `surface` | 34,243 |
| `danger_zones_heilbronn.geojson` | overtaking point with risk index | 7,095 |
| `danger_zones_PM_heilbronn.geojson` | point with traffic + fine-dust risk index | 183,030 |
| `overtaking_distance_heilbronn.geojson` | street segment, avg. overtaking distance | 1,388 |
| `speed_map_heilbronn.geojson` | street segment, avg. speed | 7,384 |
| `traffic_flow_heilbronn.geojson` | street segment, flow 0-1 | 7,153 |
| `tracks_heilbronn.geojson` | one ride | 2,281 |
| `statistics_heilbronn.geojson` | city polygon + stats | 1 |

Gotchas:
- Join the datasets on `osmid`. It is a string that is sometimes a merged list like `"[123, 456]"`; see `osm_way_ids()` in `atrai_bumpy_roads.py`.
- Only about a third of OSM ways have bumpy-road measurements, so routing needs a default roughness for the rest.
- `Normalized Roughness` is 0-100 (the docs table says 0-1). A few segments score 0 or above 4, which looks like noise.
- `statistics` is a Python-syntax string containing `np.float64(...)`, so neither `json.loads` nor `ast.literal_eval` parses it directly.
- `atrai_bumpy_roads.py` shows how to load a dataset and turn roughness into a routing cost.

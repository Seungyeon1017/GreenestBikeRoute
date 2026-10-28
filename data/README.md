# data/

fetched by `download_data.py`, logged in `manifest.json`, Heilbronn only.

## `ready-made/`
ATRAI collections as served (`api.atrai.bike`); for details, see https://hackathon.greencity.hn/resources/bike-data
- `tracks` and `statistics` are filtered to Heilbronn

Routing uses `bumpy_roads`, `traffic_flow` and `speed_map` from here.

## `custom/`
Built by us from raw `osem_bike_data`, `osem_home_data_heilbronn` and other sources, used by routing
- `danger_zones_raw_heilbronn`: overtakes with device + exact distance
- `air_quality_heilbronn`: fine dust (PM1–PM10), outliers removed
- `air_hotspots_heilbronn`: car roads of the NO₂ hotspot sections in Heilbronn's Luftreinhalteplan (2020, Tabelle 3), from OSM, by `python -m routing.air_hotspots`
- `air_background_heilbronn`: fine dust per hour, the median of the senseBox:home stations, which the bike readings are compared against
- `shade_heilbronn`: street-tree canopy per OSM way (`routing.shade`)
- `shadow_heilbronn`: building and tree shadow per OSM way and time slot (`routing.shadow`)
- `roughness_estimates_heilbronn.json`: roughness for unmeasured OSM ways near measured streets, from `bumpy_roads` by `estimation/estimate_roughness.py` (see [estimation/README.md](../estimation/README.md))
- `elevation_heilbronn.json`: height of every bike-graph node (m above sea level) from the LGL DGM1 terrain model, bridges and tunnels interpolated, plus the crests of humped bridges; built by `python -m routing.elevation --download`, used only to show grade (`/route/grade`), not for routing. Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0
- `rideable_ways.json`: footways without a bicycle tag that cyclists may and do ride (OSM way id: why), hand-picked or approved from riders' reports (`python -m backend.reports approve`); see [routing/README.md](../routing/README.md#which-streets-are-in-the-graph)
- `bridge_decks.json`: hand-checked deck heights of humped bridges (Erwin-Fuchs-, Karl-Nägele-, Bleichinselbrücke) from the LGL DOM1 surface model, read with `python -m routing.bridge_profile`; see [routing/README.md](../routing/README.md#humped-bridges-datacustombridge_decksjson). Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0
- `dott_geofencing_heilbronn.json`: Dott's geofencing zones, where a shared e-bike or e-scooter may be left (`/sharing/geofencing`, `/route/sharing`); by `python -m backend.sharing`. MobiData BW, dl-de/by-2-0

## Licenses

| Source | License                                                         | Credit                                     | Used in |
|---|-----------------------------------------------------------------|--------------------------------------------|---|
| openSenseMap (raw `osem_*` bike and senseBox:home readings, via ATRAI) | [PDDL 1.0](https://opendatacommons.org/licenses/pddl/1-0/)      | --  | `danger_zones_raw`, `air_quality`, `air_background` |
| ATRAI ready-made collections (reedu GmbH & Co. KG, `api.atrai.bike`) | to-be-added                                                     | "ATRAI, reedu GmbH & Co. KG"               | `ready-made/*`, `roughness_estimates` |
| © OpenStreetMap contributors (graph, tags, Overpass, Nominatim) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/)      | "© OpenStreetMap contributors"             | every file keyed by OSM way or node; data derived from them stays ODbL |
| LGL Baden-Württemberg (DGM1, DOM1, LoD2) | [dl-de/by-2-0](https://www.govdata.de/dl-de/by-2-0)             | "Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0" | `elevation`, `bridge_decks`, `shadow`, `lighting` |
| Stadt Heilbronn, Baumkataster | [dl-de/by-2-0](https://www.govdata.de/dl-de/by-2-0)             | "Stadt Heilbronn, Baumkataster, dl-de/by-2-0" | `shade`, `shadow` |
| Mapillary map features | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | "Mapillary, CC BY-SA 4.0"                  | `street_lights_mapillary`, `lighting` |
| MobiData BW, bikesharing GBFS (live, not stored) | [dl-de/by-2-0](https://www.govdata.de/dl-de/by-2-0)             | "MobiData BW, dl-de/by-2-0"                | `/sharing` |
| Luftreinhalteplan Heilbronn 2020 (street names of the NO₂ hotspots only) | official document, facts only                                   | "Regierungspräsidium Stuttgart"            | `air_hotspots` |

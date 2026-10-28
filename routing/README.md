# How route planning works

The Heilbronn street map (OpenStreetMap, ~42k street pieces) is a graph. Every street piece gets a **cost**, and route planning picks the path with the lowest total cost. Bad streets "feel longer", so a detour wins when it's cheaper than riding through.

```
cost = length × (1 + bump_penalty × roughness / 100 + pm_penalty × pm_risk + stop_penalty × stop_go)
     + danger_penalty × danger
     + stop_penalty × 100 m × lifts
```

- Roughness, PM risk and stop-and-go describe the whole street, so they **scale with length**.
- Danger counts incidents at spots, so it's **a fixed amount per street**, whatever its length.
- A lift (`highway=elevator` node, e.g. onto the Campusbrücke) is a stop too: riding through one costs `stop_penalty` × 100 m (waiting plus getting in and out, about 25 s), a **fixed amount per lift**. At the default 0.5 that is 50 m of detour, at 5 it is 500 m. The route reports its `lifts`.
- All penalties at 0 give the shortest route.
- With `prefer_time`, `length` becomes riding time: `length × 15.7 km/h / speed`, i.e. metres ridden at the median cyclist speed (see [speed_map](#speed_map_heilbronn-cyclist-speed-per-street-for-prefer_time)). The other terms keep their meaning in metres.
- **Riders' closure reports** (`backend/reports.py`): a street reported closed by too few riders yet, or whose reports lapsed without confirmation, costs 4× as much (`REPORTED_CLOSED_FACTOR`), so routes take a detour up to 4× its length but still ride it when there is none. A closed street (3 live independent reports) isn't ridden at all, except the piece up to a start or end point on it. This applies to the shortest route in `/route/compare` too, but not to `/score`, which rates streets, not today's closures.

## Which streets are in the graph

OSMnx's bike network, with these changes:

- **Left out:** roads tagged `bicycle=use_sidepath` (~23 km, mostly the B 39 around Europaplatz). Those have a mandatory bike path beside them (StVO §2 Abs. 4, signs 237/240/241), so cycling on the road is illegal; the path itself is mapped as its own way and stays in. Roads with an optional bike path beside them stay in too: riding on the road is legal there, so smoothness or overtaking data may pick either. Ways tagged `bicycle=dismount` are left out as well.
- **Added:** footways and paths tagged `bicycle=yes|designated|permissive`, which OSMnx drops. Untagged footways stay out (no bikes in Germany), except `bridge=yes` ones and ones touching a lift (`highway=elevator` node): bikes reach the Campusbrücke and BUGA-Brücke by lift. Street crossings (`footway=crossing`) are in even when tagged `bicycle=no`: cyclists push their bike across the lights. Footways tagged `bicycle=no` or without a tag stay out, with two exceptions where cyclists push their bike a short way: a footway up to 30 m long that links two places the graph already reaches (a crossing to a bike path), and an untagged footway up to 150 m long that fills a gap between two `bicycle=yes` ways (path 694954948 next to the Hauptbahnhof). Steps stay out.
- **Hand-picked ways:** footways without a bicycle tag that cyclists use anyway are listed in `data/custom/rideable_ways.json` (way id: why) and count as `bicycle=yes` (e.g. the Allee footway 286359672, beside the bus and car lanes). Add one by hand, or approve a rider's report (`POST /reports/mapping`) with `python -m backend.reports approve ID`, which writes the same file.
- **Graph file:** `cache/heilbronn_bike_rideable.graphml`, built from OSM on first start (~2 min). It records the hand-picked ways it was built with and is built again by itself when the list changed. Delete it to pick up newer OSM edits.

## Datasets

### `bumpy_roads_heilbronn`: roughness per street

- Matched by OSM way id. Values are 0–100 (`Normalized Roughness`; the ATRAI docs call it `normalized_score`).
- A street without data but with measured streets close by gets an **estimate** from them (`data/custom/roughness_estimates_heilbronn.json`, see [estimation/README.md](../estimation/README.md)). Responses report it as `estimated_share`; `mean_roughness` stays over the measured part.
- Any other street gets **10**, the median. With 0, unknown streets would look perfectly smooth and attract every route.
- Graph edges: 38% measured, 28% estimated, 34% unknown. `bump_penalty` default: 10.

### `danger_zones_raw_heilbronn`: close overtakes, **summed** per street

- One row is one overtake, with its device, time and exact distance. A street's danger is the sum of its rows' Risk Index (0–1). A mean would rate one near-miss the same as fifty.
- A street without rows gets no penalty.
- `danger_penalty` default 25 = metres of detour you'd ride to avoid one full-risk spot.
- Only rows over 25 cm count, see [below](#which-overtaking-readings-count).
- **Source:** `download_data.py` builds it from the raw sensor table `osem_bike_data`: devices tagged `heilbronn`, inside Heilbronn (`HEILBRONN_BBOX`). 6,280 rows from 28 devices. Fields: `index`, `boxId`, `boxName`, `createdAt`, `Overtaking Distance` (cm), `Overtaking Manoeuvre`, `Risk Index Overtaking`, `Speed`.
- **Why not the ready-made `danger_zones_heilbronn`?** Same overtakes, but no device or time, 919 of its 7,095 points are rides in Karlsruhe, Heidelberg, Munich and elsewhere, and a distance of 0 ("no reading") is scored as maximum risk. After the 25 cm rule both give the same 4,052 points and the same routes.
- **Test devices:** `test`, `biketest` and `OpenSpace123` are included, as in `danger_zones`. Filter on `boxName` to drop them. The test box `66.11 Test` (tag `lauds_26`) is excluded.
- **Download:** the raw table returns its pages in a different order on every request, so paging duplicates and skips rows. `download_data.py` fetches it in one request (about 1 GB) and keeps 2 MB. The API downloads it on first start if it is missing.

### `air_quality_heilbronn`: air quality, **averaged** per street

- Fine dust samples about every 20 m of every ride, combined as `0.4 × PM1 + 0.3 × PM2.5 + 0.2 × PM4 + 0.1 × PM10` (the PM weights of `danger_zones_PM`, scaled to sum to 1).
- Weather and sensor offsets outweigh location, so each reading is scored relative to two references (`routing.costs.air_scores`):
  1. **The region's air at that hour**, from the fixed senseBox:home stations (`air_background_heilbronn`, below): a log ratio, so a smoggy afternoon or a smoggy half hour within a ride drops out.
  2. **The rest of its ride** (same device and day): the ride's median is subtracted, so a bike sensor that reads high everywhere drops out.
- The result is mapped linearly to 0-1: 0.5 = typical, 1 = about 1.35× the ride's usual (`AIR_SPREAD`), clipped.
- Streets agree only weakly. Split the bikes into two random halves and rank streets by each half's readings: the rankings correlate ~0.24 (Spearman, 30 splits, streets with 5+ readings in both halves; 0.18 with the old within-ride rank, which the new score beat in 28 of 30 splits). Split by day instead: ~0.39 (0.38 before).
- **Averaged per street by ride, not by reading.** One pass leaves several readings from the same sensor in the same minute, so they count as one: each ride's readings on a street are averaged first, then the rides, pulled towards the street's prior (0.5, or 0.525 on a hotspot, below) by 8 virtual rides (`AIR_PRIOR_RIDES`). A street one bike passed once barely moves from 0.5; a street 20 rides agree on keeps most of its value. A third of the measured streets have a single ride.
  - Why 8: street values from one half of the bikes (or days) predict the other half's per-ride street means. Plain reading means, as before, are 25-30% *worse* than giving every street 0.5, i.e. they mostly carried noise. 8 rides does best, slightly better than 0.5 everywhere (1% by bike, 3.5% by day); anything from 5 to 30 is within 1%.
  - Street values now span about 0.44-0.58 (5-95%; 0.23-0.86 before). Over 40 random trips of 1.5-5 km with only `pm_penalty` on, 0.5 changes 15 routes (26 before) for no extra length, and 2 changes 24 for 0.2%. Air now moves routes only where many rides agree.
- `pm_penalty` default 0.5. Unmeasured streets get 0.5.
- **Source:** built from `osem_bike_data` with the `danger_zones_PM` filters: devices tagged `heilbronn`, humidity ≤ 75%, per-device IQR outlier removal, then cut to `HEILBRONN_BBOX`. 166,429 rows; 164,789 are scored (rows before the stations started in March 2026, or in hours without a station reading, are dropped).
- **Map overlay:** `/air` serves these points with their 0-1 score (not an absolute PM value).
- **Why not `danger_zones_PM_heilbronn`?** Its `Risk Index` mixes in overtaking, which `danger_penalty` already counts. Our rows match its points inside Heilbronn exactly, plus 21,915 valid air readings from bikes without a distance sensor.

### `air_hotspots_heilbronn`: NO₂ hotspots from the clean-air plan, a prior for every street along them

- **Source:** Luftreinhalteplan Regierungsbezirk Stuttgart, Teilplan Heilbronn, 2. Fortschreibung (2020), Tabelle 3: the 19 street sections of measure M9 (diesel ban), forecast well over 40 µg/m³ NO₂ (Weinsberger, Paulinen-, Mannheimer, Süd-, Karlstraße, ...). Matched by name to OSM car roads in the centre by `python -m routing.air_hotspots`.
- **Use:** bike streets running along them (≥ 50% within 15 m: side paths and pavements, not cross streets) start at **0.525** instead of 0.5 (`AIR_HOTSPOT_OFFSET`), measured or not. ~2,400 graph edges.
- **Why:** the bikes agree. Within the same ride they read +0.06 higher there than on other main roads (181 rides, worse in 67%; ~5 standard errors). 0.025 is the difference of the ride-weighted means (0.557 vs 0.530). In the hold-out test (fit on half the bikes or days, predict the rest) this prior beats 0.5 in 26-28 of 30 splits, with 2-2.6% lower error on the hotspot streets.
- **Tried and dropped:** a ridge regression on road class, car traffic within 50/150 m (OSM `drive`, by class × lanes), distance to main roads, building cover and height within 30 m (LoD2), trees (Baumkataster) and distance to the centre. On streets the training half never measured, it did no better than 0.5 (−0.3% to +5%, unstable coefficients). PM2.5 is mostly regional, and the bikes see only weak street differences; the named NO₂ hotspots are the one street feature they confirm.

### `air_background_heilbronn`: the region's fine dust per hour (senseBox:home)

- Built by `download_data.py` from `osem_home_data_heilbronn`: 2M rows (every ~10 s) from 15 fixed senseBox:home stations. One feature per hour: the **median over stations** of each station's hourly mean, per PM value. 5,211 hours from March 2026, usually 3-5 stations.
- Only the 7 stations with at least 1,000 hours of fine dust count (`MIN_HOME_HOURS`): Innenstadt, Schulgarten, GreenCity OpenSpace, Eichbottschule Leingarten, Wolf-von-Gemmingen-Schule, PDG-NEO and HCG Beilstein. The others logged only on their first day, or have no PM sensor.
- **Why not route with the stations directly?** Only 3 of them are in Heilbronn proper, all in the centre within 1.5 km of each other: far too few to tell streets apart. What they show is time: the two centre stations correlate 0.90 hour by hour, and each bike ride's median correlates 0.86 with the stations' median at the same hour. Bike sensors do measure the real air; most of what they see is how the whole region's air changes, which this background takes out.
- **Download:** like `osem_bike_data`, its pages come in a different order on every request, so it is fetched in one request (about 3 GB, a minute) and only the hourly sums are kept.

### `traffic_flow_heilbronn`: stop-and-go per street

- `avg_traffic_flow` is 0-1 per segment: near 1 = bikes roll freely, near 0 = slow or stop-and-go (traffic lights, congestion). Routing uses `stop_go = 1 − flow`, so higher is worse like the other factors.
- Matched by OSM way id, like roughness. A way's value is the mean of its segments **weighted by `points_in_segment`**, pulled towards the median flow (0.37) by 5 extra points. Half the segments have 7 or fewer points and their values scatter more, so one slow reading doesn't brand a street.
- Unmeasured streets get **0.63** (1 − median). About 43% of graph edges (35% of the length) are measured.
- `stop_penalty` default 0.5. Streets differ little (way values ~0.5-0.85, 5-95%), and the shortest route is rarely the slow one: over 40 random trips of 1.5 km or more, a penalty of 1 changes 72% of routes but adds only 0.4% distance and lowers `mean_stop_go` by 0.02. Expect small detours.
- **Map overlay:** `/flow` serves the raw segments as `stop_go`.

### `speed_map_heilbronn`: cyclist speed per street, for `prefer_time`

- `avg_speed[km/h]` per segment is the speed bikes were measured at, waits at lights included. Not a penalty but a switch: with `prefer_time=true` each street costs its riding time instead of its length (in metres at the median speed, so `danger_penalty` and lifts keep their meaning). Off by default.
- Matched by OSM way id and aggregated like traffic_flow: points-weighted mean, pulled towards the median (15.7 km/h) by 5 extra points. Unmeasured streets get the median, so they cost their length. About 41% of graph edges (34% of the length) are measured.
- **Floor of 5 km/h** (walking pace). Some segments with hundreds of points average ~2 km/h (bikes pushed, or waiting), which would make them cost 3-8× their length. 3.7% of measured edges sit at the floor; edge values span 5.7-22 km/h (5-95%).
- Both directions of a street get the same speed: the dataset is per segment, not per direction, so uphill and downhill are not told apart.
- **Overlap with stop_go:** traffic_flow is itself built from normalized speed and standing time, so `prefer_time` and `stop_penalty` partly count the same thing. Time mode already lowers `mean_stop_go` on its own (0.67 → 0.59 on the example trip); keep `stop_penalty` low when using it.
- **Every route** reports `duration_s` (length / speed per street, plus ~23 s per lift) and `speed_measured_share`; `/route/compare` adds `extra_time_pct` next to `detour_pct`. The comparison's shortest route is always by distance.
- Over 40 random trips of 1.5 km or more: with only `prefer_time` (penalties 0), 95% of routes change, 5.1% longer on average (max 21%) and 8.7% faster (max 29%). With the default penalties, switching it on changes 90% of routes, 3.4% longer and 12.1% faster than the default route.
- **Map overlay:** `/speed` serves the raw segments as `speed_kmh` (higher = faster, unlike the other overlays).

### Shade and street lighting, chosen by `depart_time`

- Both apply only with a `depart_time`. The sun's altitude at that time and date (NOAA equations, `routing.shadow.sun_position`) decides which one: above the horizon (-0.833°, as for sunrise and sunset), sunny streets cost `shade_penalty × (1 − shade)` times their length; below it, unlit streets cost `dark_penalty × (1 − lit)` times their length.
- **Shade** (`data/custom/shadow_heilbronn.json`, building and tree shadow per OSM way) exists for 21 July at 09, 12, 15 and 18 h; a route uses the slot nearest its time of day, whatever the date. Ways without it fall back to the static tree canopy (`shade_heilbronn.json`), then 0.1 (most streets get little shade: median ~0.05 at noon). Over 30 random trips at 15:00, `shade_penalty` 0.5 changes 23 routes for a 0.5% mean detour (mean shade 0.18 → 0.21).
- **Lighting** (`data/custom/lighting_heilbronn.json`) is the chance a way is lit: OSM `lit=*`, else Mapillary street lights, else a road-type and buildings rule. Unknown ways get 0.5; about 11% of the graph's ways have no value yet. Over the same trips at 21:00, `dark_penalty` 1 changes 26 of 30 routes for a 3% mean detour, raising the chance of being lit from 0.80 to 0.91.
- Routes report `daylight`, `shade_slot`, `mean_shade` (by day only), `mean_lit` and the share of the route each is known for. **Map overlays:** `/shade` (all slots per street, plus `slots`) and `/lighting`.

## Which overtaking readings count

Each row in `danger_zones_raw_heilbronn` is one overtake, with the gap between car and bike as the sensor measured it. Route planning and `/danger` only count gaps of **more than 25 cm**:

| Rows                           | Count | Used                     |
|--------------------------------|-------|--------------------------|
| Gap over 25 cm                 | 4,052 | yes                      |
| Gap of 25 cm or less           | 2,025 | no, likely sensor errors |
| No gap recorded (0 or empty)   | 203   | no, nothing to score     |

Why gaps of 25 cm or less are treated as sensor errors:

- 82% of them come from three devices: `arcadia-wnck`, `catcat 42` and `Ganzjahresradler dsS`. Their median gap is 1, 12 and 42 cm; other devices measure about 90 cm. Hundreds of cars passing 1 cm away is not plausible.
- When those three devices measure more than 25 cm, their values look normal (median 89 cm). The devices work; their very short readings don't.
- The ready-made `overtaking_distance_heilbronn` dataset leaves out gaps of 25 cm or less too.

Note: This is a judgement from the data; the hardware owners haven't confirmed it. Some short gaps from other devices (about 12% of their readings) may be real close passes and are lost.

## Snapping points to streets

- Each overtaking and PM point is assigned to the nearest street within **25 m** (GPS noise). A point with no street that close is ignored. That is 13% of the overtaking points we use and 16% of the PM points.
- A two-way street gets the same values in both directions.
- The start and end you request are moved onto the nearest street, which is split there so the route can enter or leave it. If that street is more than 500 m away (for example outside Heilbronn), the API returns an error (HTTP 400).

## Example

From 49.14838, 9.22687 to 49.1262, 9.22439:

| Penalties (bump / danger / PM / stop) | Length  | Roughness | Overtaking spots | Stop-and-go |
|---------------------------------------|---------|-----------|------------------|-------------|
| 0 / 0 / 0 / 0 (shortest)              | 3.06 km | 24.7      | 10               | 0.67        |
| 10 / 25 / 0.5 / 0.5 (defaults)        | 3.09 km | 12.3      | 21               | 0.69        |
| 10 / 100 / 0.5 / 0.5                  | 3.23 km | 12.4      | 6                | 0.69        |
| 0 / 0 / 0 / 5                         | 3.07 km | 24.3      | 12               | 0.66        |
| 0 / 0 / 0 / 0, `prefer_time`          | 3.72 km | 19.6      | 9                | 0.59        |
| 10 / 25 / 0.5 / 0.5, `prefer_time`    | 4.15 km | 11.3      | 3                | 0.60        |

On this trip the defaults pick the smooth street, which has more overtaking spots than the shortest route, and 25 is too weak to change that. At 100 the route avoids both. The default `stop_penalty` doesn't change any of these routes, and even 5 only swaps a few short pieces. `prefer_time` takes faster streets: 822 s instead of 940 s for the shortest route (−13%), 21% further. With the default penalties it rides 918 s over 4.15 km: the time-scaled penalties now find a detour around nearly all overtaking spots that pays off.

## Grade (display only, not in the route cost)

`/route/grade` takes the same parameters as `/route` and returns **the same path**, split into pieces coloured by how steep they are, so a map can show where the climbs are. Grade never enters `edge_cost`: the route is chosen exactly as before (`tests/test_heilbronn.py` checks that the pieces join up to the `/route` line).

Why not route on it: Heilbronn is mostly flat in the valley, and the hills (Wartberg, east and south) have no flat way around. An uphill penalty of 10 m per metre climbed cut the total climb by only 9%, and valley trips climb about 13 m anyway. So grade is shown, not avoided.

- **Grade of an edge** = height gain in the travel direction / edge length, from the heights of its two end nodes. A two-way street is two edges, so it is uphill one way and downhill the other. Where the start or end splits a street (see [Snapping](#snapping-points-to-streets)), that point gets the height on the straight line between the street's two ends. Consecutive edges with the same class and direction (up/down) are merged into one piece; a piece's `grade_pct` is its total rise / length.
- **Classes** on the absolute grade: flat < 2%, gentle 2–4%, noticeable 4–6%, steep 6–10%, very_steep ≥ 10% (a bound belongs to the steeper class). Each piece carries a suggested `color`.
- **Totals** in `summary`: `climb_m`, `descent_m`, start and end height, the steepest uphill (`max_grade_pct`) and downhill piece, and metres per class.
- **Whole network** (by length, both directions): 57% flat, 21% gentle, 11% noticeable, 9% steep, 3% very steep. Heights range from 150 to 372 m. Example trip: 3.09 km, climbs 25 m (162.7 → 180.8 m), steepest 4.1% (a 10 m piece).

### Heights: `data/custom/elevation_heilbronn.json`

- One height per graph node (17,546), in metres above sea level (NHN, DHHN2016), from the **LGL DGM1** terrain model: 1 m × 1 m cells, ±15 cm. Each node gets the height of the cell it lies in.
- Built by `python -X utf8 -m routing.elevation --download`: downloads the 43 DGM1 tiles (2 km × 2 km, ~520 MB) the graph touches into `cache/dgm1/` (git-ignored, ~3.5 min), then reads only the 1 km files with nodes (~10 s). The API reads only the 340 kB JSON. Without it, `/route/grade` answers 503.
- **Bridges and tunnels:** the DGM is bare ground, so a node on a bridge gets the river or railway below it and a node in a tunnel the hill above it. A node is on a structure when it is an inner point of an OSM bridge/tunnel way, or where two such ways meet (`structure_nodes_from_ways`; the ways come from Overpass, cached in `cache/`). That is 39 nodes; 38 of them are interpolated along their structure between the nearest known height on each side, weighted by distance (a straight line between the abutments of a simple bridge), moving by up to 8.1 m. Example: Kaiserstraße over the Neckar, eastbound. With terrain heights its three bridge edges read −11.3%, −1.9% and +8.8% (the two middle nodes sat about 4 m below the deck); now all three are −0.4%.
- Why the OSM ways and not the edges' `bridge` tag: after `simplify_graph` an edge is tagged bridge when any of the ways it merges is one, so the 24.6 km of tagged edges hold only 8.7 km of bridge (an 805 m track over a 17 m culvert). Going by the tag, 88 nodes counted as on a structure and many ordinary nodes, mostly on such tracks, were interpolated from abutments far away, by up to 10.8 m. Switching changed 47 node heights; the number of edges steeper than 15% stayed at 139, and those steeper than 25% went from 13 to 11.

### Humped bridges: `data/custom/bridge_decks.json`

A straight line between the abutments flattens a bridge that rises over a river or railway. Erwin-Fuchs-Brücke (Böckingen, over the railway yard and the Neckar) was the worst: its deck read −1.1% and +1.8% eastbound, but it rises about 5 m above its abutments, which riders feel. For the bridges listed in this file, hand-checked heights on the deck are used as well: listed `nodes` keep their height, the rest of the bridge is interpolated through them, and a `crest` in the middle of an edge is stored with the heights (`crests` in `elevation_heilbronn.json`), so `/route/grade` shows that edge as two pieces, up to the crest and down from it. Routing is unchanged.

| Bridge | Edges | Before (one direction) | Now |
|---|---|---|---|
| Erwin-Fuchs-Brücke | Badstraße, 94 m + 165 m | −1.1%, +1.8% | +3.9%, then +3.0% up to the crest and −2.5% down; with the ramp the crossing climbs about 10 m |
| Karl-Nägele-Brücke | the two side paths (cars only on the deck), 204 m and 243 m | −0.2% each | about +2% up to 160.7 m, about −3% down |
| Bleichinselbrücke | road both ways, two side paths | 0% to −0.5% | gentle hump, 0.6–1.5 m |

The heights come from the **LGL DOM1** surface model (1 m, ±15 cm), which keeps bridge decks but also arches, lamp posts, trees and vehicles, so it is used only here and every value was checked on a plot. To check or add a bridge:

```bash
uv run --group estimation python -X utf8 -m routing.bridge_profile "Karl-Nägele-Brücke" --at 1=100
uv run python -X utf8 -m routing.elevation
```

`routing/bridge_profile.py` takes the bridge-tagged graph edges inside the bridge's OSM `man_made=bridge` outline (so not the paths passing underneath), joins them from abutment to abutment, samples the DOM1 every metre (median of 3 × 3 cells, then a 15 m running median), and prints the heights for the run's inner nodes and its highest point, ready to paste. A deck height is today's straight line between the abutments plus how far the DOM1 deck rises above the line between its own ends, so an offset between the two models at the abutments drops out. The plot goes to `cache/bridge_profiles/`. When the highest point is not the deck, read the deck off the plot and print that spot with `--at RUN=METRES`: on Karl-Nägele-Brücke the highest DOM1 points are a jump near one end and a stretch where the 2017 surface is lower than today's ground, so both crests are the deck plateau at 160.7 m; on Bleichinselbrücke one is a narrow spike (a sign or lamp). Each entry in the file says what was checked.

DOM1 around Heilbronn was captured on 2017-02-15 and not updated since, while DGM1 was updated in 2024. A bridge rebuilt since 2017 needs another source; the script prints how far the two models differ at the abutments (here within 0.7 m, and 0.9 m at the west end of Karl-Nägele's south path, where the plateau value was used). Industriebrücke and Salzhafenbrücke were checked too and need no entry: Industriebrücke climbs to the harbour terrace, which the DGM already has (+6.0% and +3.6% on the bike path), and only 42 m of Salzhafenbrücke is bridge.

Limits:
- Only nodes have heights (plus the hand-checked crests above). A long edge over a hump shows its average grade; half of the edges are under 35 m, but 10% are over 158 m. Humped bridges not in `bridge_decks.json` still read as a straight line between their abutments.
- Where a street is on a ramp or wall that OSM doesn't tag as a bridge, its nodes get the ground beside or below it. 9 of the 194 routable bridges/tunnels have an approach edge steeper than 15% within 50 m of their ends. Worst: a 7 m piece of Wilhelm-Leuschner-Straße next to the Neckartalstraße bridges at 54%.
- A node a few metres off the real street, next to an embankment or retaining wall, can make a short piece look steep. Treat very short red pieces with suspicion.
- **Data:** LGL Baden-Württemberg, Digitales Geländemodell DGM1, https://opengeodata.lgl-bw.de. Licence Datenlizenz Deutschland – Namensnennung – 2.0: the portal states it for every dataset not marked otherwise (DGM1 isn't), and every DGM1 zip ships `GOVDATA-Datenlizenz_Deutschland.pdf`. Required credit: "Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0".

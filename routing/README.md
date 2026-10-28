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

## Which streets are in the graph

OSMnx's bike network, with these changes:

- **Left out:** roads tagged `bicycle=use_sidepath` (~23 km, mostly the B 39 around Europaplatz). Those have a mandatory bike path beside them (StVO §2 Abs. 4, signs 237/240/241), so cycling on the road is illegal; the path itself is mapped as its own way and stays in. Roads with an optional bike path beside them stay in too: riding on the road is legal there, so smoothness or overtaking data may pick either. Ways tagged `bicycle=dismount` are left out as well.
- **Added:** footways and paths tagged `bicycle=yes|designated|permissive`, which OSMnx drops. Untagged footways stay out (no bikes in Germany), except `bridge=yes` ones and ones touching a lift (`highway=elevator` node): bikes reach the Campusbrücke and BUGA-Brücke by lift. Street crossings (`footway=crossing`) are in even when tagged `bicycle=no`: cyclists push their bike across the lights. Footways tagged `bicycle=no` or without a tag stay out, with two exceptions where cyclists push their bike a short way: a footway up to 30 m long that links two places the graph already reaches (a crossing to a bike path), and an untagged footway up to 150 m long that fills a gap between two `bicycle=yes` ways (path 694954948 next to the Hauptbahnhof). Steps stay out.
- **Hand-picked ways:** footways without a bicycle tag that cyclists use anyway are listed in [rideable_ways.py](rideable_ways.py) and count as `bicycle=yes` (e.g. the Allee footway 286359672, beside the bus and car lanes). Add a way id and a reason there, then delete the graph file. Planned: users report streets and, once checked, they are added to this list.
- **Graph file:** `cache/heilbronn_bike_rideable.graphml`, built from OSM on first start (~2 min). Delete it to pick up newer OSM edits.

## Datasets

### `bumpy_roads_heilbronn`: roughness per street

- Matched by OSM way id. Values are 0–100, even though the docs say 0–1.
- A street without data gets **10**, the median. With 0, unknown streets would look perfectly smooth and attract every route.
- About 31% of streets are measured. `bump_penalty` default: 10.

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

- Fine dust samples about every 20 m of every ride. A point's index is `0.4 × PM1 + 0.3 × PM2.5 + 0.2 × PM4 + 0.1 × PM10`, each divided by its maximum (the PM weights of `danger_zones_PM`, scaled to sum to 1).
- Weather and sensor offsets outweigh location, so routing uses each point's **rank within its ride** (same device and day; 0.5 = typical). Unmeasured streets get 0.5.
- `pm_penalty` default 0.5: streets agree only weakly between days (correlation ~0.17).
- **Source:** built from `osem_bike_data` with the `danger_zones_PM` filters: devices tagged `heilbronn`, humidity ≤ 75%, per-device IQR outlier removal, then cut to `HEILBRONN_BBOX`. 166,429 rows.
- **Map overlay:** `/air` serves these points scored 0-1 against the rest of the same bike trip (0.5 = usual; not an absolute PM value).
- **Why not `danger_zones_PM_heilbronn`?** Its `Risk Index` mixes in overtaking, which `danger_penalty` already counts. Our rows match its points inside Heilbronn exactly, plus 21,915 valid air readings from bikes without a distance sensor.

### `traffic_flow_heilbronn`: stop-and-go per street

- `avg_traffic_flow` is 0-1 per segment: near 1 = bikes roll freely, near 0 = slow or stop-and-go (traffic lights, congestion). Routing uses `stop_go = 1 − flow`, so higher is worse like the other factors.
- Matched by OSM way id, like roughness. A way's value is the mean of its segments **weighted by `points_in_segment`**, pulled towards the median flow (0.37) by 5 extra points. Half the segments have 7 or fewer points and their values scatter more, so one slow reading doesn't brand a street.
- Unmeasured streets get **0.63** (1 − median). About 43% of graph edges (35% of the length) are measured.
- `stop_penalty` default 0.5. Streets differ little (way values ~0.5-0.85, 5-95%), and the shortest route is rarely the slow one: over 40 random trips of 1.5 km or more, a penalty of 1 changes 72% of routes but adds only 0.4% distance and lowers `mean_stop_go` by 0.02. Expect small detours.
- **Map overlay:** `/flow` serves the raw segments as `stop_go`.

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
| 10 / 25 / 0.5 / 0.5 (defaults)        | 3.12 km | 12.2      | 21               | 0.69        |
| 10 / 100 / 0.5 / 0.5                  | 3.25 km | 12.3      | 6                | 0.69        |
| 0 / 0 / 0 / 5                         | 3.07 km | 24.3      | 12               | 0.66        |

On this trip the defaults pick the smooth street, which has more overtaking spots than the shortest route, and 25 is too weak to change that. At 100 the route avoids both. The default `stop_penalty` doesn't change any of these routes, and even 5 only swaps a few short pieces.

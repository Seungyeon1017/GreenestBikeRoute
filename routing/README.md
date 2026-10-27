# How route planning works

The Heilbronn street map (OpenStreetMap, ~34k street pieces) is a graph. Every street piece gets a **cost**, and route planning picks the path with the lowest total cost. Bad streets "feel longer", so a detour wins when it's cheaper than riding through.

```
cost = length × (1 + bump_penalty × roughness / 100 + pm_penalty × pm_risk)
     + danger_penalty × danger
```

- Roughness and PM risk describe the whole street, so they **scale with length**.
- Danger counts incidents at spots, so it's **a fixed amount per street**, whatever its length.
- All penalties at 0 give the shortest route.

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

### `danger_zones_PM_heilbronn`: traffic and air quality, **averaged** per street

- One point is a sample logged about every 20 m of every ride. Many points only mean many people ride there, so the mean says how bad the street is.
- A street without data gets **0.33**, the median, for the same reason as roughness.
- `pm_penalty` default 2. It's a weak lever, because street means only span 0.24–0.40.

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

- Each overtaking and PM point is assigned to the nearest street within **25 m** (GPS noise). A point with no street that close is ignored. That is 13% of the overtaking points we use and 33% of the PM points, mostly rides outside Heilbronn.
- A two-way street gets the same values in both directions.
- The start and end you request are moved to the nearest street corner. If that corner is more than 500 m away (for example outside Heilbronn), the API returns an error (HTTP 400).

## Example

From 49.14838, 9.22687 to 49.1262, 9.22439:

| Penalties (bump / danger / PM) | Length  | Roughness | Overtaking spots |
|--------------------------------|---------|-----------|------------------|
| 0 / 0 / 0 (shortest)           | 3.15 km | 24        | 10               |
| 10 / 25 / 2 (defaults)         | 3.25 km | 11.8      | 26               |
| 10 / 100 / 2                   | 3.33 km | 12.5      | 7                |

On this trip the defaults pick the smooth street, which has more overtaking spots than the shortest route, and 25 is too weak to change that. At 100 the route avoids both.

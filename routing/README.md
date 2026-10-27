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

### `bumpy_roads_heilbronn`: LineStrings, roughness per street

- **Matching:** by OSM way id. The values are 0–100, even though the docs say 0–1.
- **No data:** a street without data gets **10**, the median. With 0, unknown streets would look perfectly smooth and attract every route.
- **Coverage:** about 31% of streets are measured.
- **`bump_penalty`:** default 10.

### `danger_zones_heilbronn`: Points, **summed** per street

- **What a point is:** one close overtake. More points means cyclists get overtaken closely there more often.
- **Why sum:** a mean would rate one near-miss the same as fifty.
- **No data:** no points, no penalty.
- **`danger_penalty`:** default 25, in metres of detour per full-risk spot. It changes little above ~50.

### `danger_zones_PM_heilbronn`: Points, **averaged** per street

- **What a point is:** a sample of traffic and air quality, logged about every 20 m of every ride.
- **Why average:** many points only mean many people ride there. The mean tells you how bad the street is.
- **No data:** a street without data gets **0.33**, the median, for the same reason as roughness.
- **`pm_penalty`:** default 2. It's a weak lever, because street means only span 0.24–0.40.

## Snapping points to streets

- **Distance:** each point goes to the nearest street within **25 m** (GPS noise).
- **Dropped points:** points further away are almost all from rides outside Heilbronn, about 17% of overtaking points and 27% of PM points.
- **Both directions:** a two-way street gets the same values in both directions.
- **Start and end:** they must be within 500 m of a street, or the API returns 400.

## Example

From 49.14838, 9.22687 to 49.1262, 9.22439:

| Penalties (bump / danger / PM) | Length  | Roughness | Overtaking spots |
|--------------------------------|---------|-----------|------------------|
| 0 / 0 / 0 (shortest)           | 3.15 km | 24        | 42               |
| 10 / 25 / 2 (defaults)         | 3.33 km | 12.5      | 15               |

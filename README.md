# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Route Planning API
Serves bike routes that avoid bumpy streets, close-overtaking spots, streets with bad air and stop-and-go streets as GeoJSON. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds. See [Backend Setup and Usage](#backend-setup-and-usage) for how to start it.

Example request: `/route?from_lat=49.14838&from_lon=9.22687&to_lat=49.1262&to_lon=9.22439&bump_penalty=2`. Four penalties steer the route, and setting all of them to 0 gives the shortest route. All penalties but `danger_penalty` count in whole points, 0-10: each point makes a bad street 25% dearer. A street only costs extra where it is worse than a typical Heilbronn street, and the dislikes multiply, so raising one never drowns the others (see [routing/README.md](routing/README.md)):

- `bump_penalty` (default 2, 0-10): how much you hate bumps (`bumpy_roads`).
- `danger_penalty` (default 10, 0-100): metres of detour you'd ride to pass one fewer close-overtaking spot (`danger_zones_raw`, summed Risk Index Overtaking; readings of 25 cm or less ignored).
- `pm_penalty` (default 1, 0-10): how much you hate bad air (`air_quality`, bike fine dust compared with the senseBox:home stations at the same hour and with the rest of the ride, so weather and sensor offsets drop out, averaged per street by ride so a street needs several rides to count; streets along the NO₂ hotspots of Heilbronn's Luftreinhalteplan start slightly worse).
- `stop_penalty` (default 1, 0-10): how much you hate slowing down and stopping at traffic lights, in congestion (`traffic_flow`) or at a lift (each costs 25 m × this).

`depart_time` (e.g. `2026-07-21T15:00`, Heilbronn local time) brings in two more penalties, chosen by the sun at that time: while it is up, `shade_penalty` (default 2) avoids sunny streets (building and tree shade, `routing.shadow`); after sunset or before sunrise, `dark_penalty` (default 4) avoids streets that are probably unlit (`routing.lighting`). Without `depart_time` neither applies.

`prefer_time=true` plans by riding time instead of distance, using the speed bikes were measured at on each street (`speed_map`); the penalties still apply. Every route reports its expected `duration_s`.

`/route/compare` takes the same parameters and returns the route next to the shortest route (by distance, with `detour_pct` and `extra_time_pct`), to draw both and show what the penalties changed. See `/docs` for the response.

Every route also reports metres on bad streets, to compare routes in metres (the demo's "Why this route?" card): `bumpy_m`, `bad_air_m` and `stop_go_m` (each the worst tenth of measured street length for that factor), `sunny_m` by day, `unlit_m` after dark, and `bike_friendly_m` on bike paths and lanes.

`/route/day` takes the same parameters and returns `/route/compare` for every departure time of the day of `depart_time` (today without one), in periods with the same sky: night, each shade slot, night. The demo's "Slide through the day" slider stops only where the route changes.

`/route/sharing` takes the same parameters plus `vehicle` (`all`, `bike`, `scooter`) and `park_in_zone`, and plans walk → ride → walk with a shared Dott vehicle free right now: the walks on OSM's walking network (`cache/heilbronn_walk.graphml`, downloaded on first use, ~1.5 min; pavements, footways and pedestrian zones, no bike paths), the ride on the bike graph with the penalties, ending at the destination, as Dott is free-floating, unless that lies in one of Dott's no-parking zones (`/sharing/geofencing`, from its GBFS geofencing feed; some zones allow parking only at a parking zone): then at the nearest place where it may be left (`return_point`). `park_in_zone=true` always ends at a parking zone. The geofencing zones change rarely, so they are read from `data/custom/dott_geofencing_heilbronn.json` (`python -m backend.sharing` refreshes it). An e-scooter is pushed at walking pace on footways and in pedestrian zones it must not ride on (eKFV §10; `pushed_m`), shared paths signed for bikes (`bicycle=designated`) are ridden. The vehicle needs a free one within 1 km walk with enough range.

`/route/grade` takes the same parameters and returns the same route in pieces coloured by grade (flat < 2% … very steep ≥ 10%), plus climb, descent and the steepest piece. It is display only: grade doesn't change the route. Heights: LGL DGM1 (Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0), see [routing/README.md](routing/README.md#grade-display-only-not-in-the-route-cost).

Places: routes take coordinates only. `/geocode?q=Rathaus` finds a landmark, address or street in Heilbronn and returns up to 5 candidates (GeoJSON points with a `label`) for a "did you mean" list; route with the picked one's coordinates. It searches [Nominatim](https://nominatim.org/) (OpenStreetMap, ODbL), cached and at most one search a second, so search on Enter rather than while typing.

Map overlays: `/roughness` (streets), `/danger` (overtaking spots), `/air` (air-quality points, 0-1 worse than usual), `/flow` (streets, 0-1 stop-and-go), `/speed` (streets, measured cyclist km/h), `/shade` (streets, 0-1 in shade per time slot) `/lighting` (streets, 0-1 chance lit at night) and `/score` (every street, 0-100 overall score combining all factors for the same penalties as `/route`, higher = better) return GeoJSON.

Sharing: `/sharing` lists the shared e-bikes and e-scooters free to rent right now (Heilbronn: Dott, about 140 pedelecs and 350 e-scooters), with `vehicle` (bike/scooter), battery, range, price and a link that opens the vehicle in the provider's app; `vehicle=bike` or `vehicle=scooter` shows one kind, and `near_lat`/`near_lon` (e.g. the route start) sort them closest first. `/sharing/zones` lists the provider's parking zones with how many bikes and scooters stand there (the provider's own counts, so they can differ slightly from `/sharing`). Both are live from [MobiData BW](https://mobidata-bw.de/dataset/bikesh) (GBFS, dl-de/by-2-0), cached for a minute; if the feed is down the last snapshot is served for up to 30 minutes, then 503. `/route` plans for bikes; e-scooters must not ride on footways even where bikes may, which `/route/sharing` follows for a rented e-scooter.

Reports: riders report closed streets (`POST /reports/closures`) and footways bikes ride on that OSM doesn't mark for bikes (`POST /reports/mapping`). Closures steer routes right away and stay until riders say they are open again or stop confirming them; mapping reports wait for a maintainer (`python -m backend.reports list`, then `approve ID`), and approved ways go into `data/custom/rideable_ways.json` and are routed from the next server start. The rules are in `/docs`; reports are kept in `data/reports.sqlite3`.

Danger points come from `danger_zones_raw_heilbronn` (one row per overtake, with device id and exact distance) and are snapped to the nearest street within 25 m. [routing/README.md](routing/README.md) explains how route planning works and why readings of 25 cm or less are ignored.

For a clickable demo map, start the API, run `python -m http.server 5500 -d demo-prototype` and open http://127.0.0.1:5500. It also shows riders' reports and takes new ones (pick what a map click does). It is a throwaway prototype kept outside `frontend/`.

## Backend Setup and Usage

### 1. Run the Backend Locally with `uv`

Make sure you are in the project root directory, for example:

```powershell
cd D:\bike_project\GreenestBikeRoute
```

Install the project dependencies using the lockfile:

```powershell
uv sync
```

Start the FastAPI backend:

```powershell
uv run uvicorn backend.app:app --reload --port 8001
```

The backend will be available at:

- **API base URL:** http://127.0.0.1:8001
- **Interactive API documentation (Swagger UI):** http://127.0.0.1:8001/docs

The `--reload` option automatically restarts the development server when Python source files change.

### 2. Port Configuration

The backend is served on port `8001` (not `8000`, in case another local FastAPI project uses), both locally and with Docker Compose. In `compose.yml`, `"8001:8000"` maps host port `8001` to Uvicorn's port `8000` inside the container.

When running with Docker Compose, the port mapping in `compose.yml` is:

```yaml
ports:
  - "8001:8000"
```
### 3. Run the Backend with Docker Compose

Build the Docker image and start the backend in the background:

```powershell
docker compose up --build -d
```

View the running containers:

```powershell
docker compose ps
```

Follow the backend logs:

```powershell
docker compose logs -f backend
```

Stop following the logs with `Ctrl+C`. This does not stop the container.

Stop the backend:

```powershell
docker compose down
```

Rebuild and restart after changing the Dockerfile, dependencies, or application code:

```powershell
docker compose up --build -d
```

Open the API documentation:

http://127.0.0.1:8001/docs

### 4. Data and Cache Volumes

The backend service in `compose.yml` uses these volume mappings:

```yaml
volumes:
  - ./data:/app/data
  - ./cache:/app/cache
```

These mappings make the project's local `data` and `cache` directories available inside the container. If the application uses these paths, downloaded datasets and cached graph data can persist between container recreations.

### 5. Run Tests

Run the test suite from the project root:

```powershell
uv run pytest
```


## License
Code: [AGPL-3.0](LICENSE), the license of the Green City Dashboard that `frontend/` is forked from.

Data: each dataset keeps its source's license; see [data/README.md](data/README.md#licenses) for credits.

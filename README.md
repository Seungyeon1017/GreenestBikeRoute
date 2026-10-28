# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Route Planning API
Serves bike routes that avoid bumpy streets, close-overtaking spots, streets with bad air and stop-and-go streets as GeoJSON. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds. See [Backend Setup and Usage](#backend-setup-and-usage) for how to start it.

Example request: `/route?from_lat=49.14838&from_lon=9.22687&to_lat=49.1262&to_lon=9.22439&bump_penalty=10`. Four penalties steer the route, and setting all of them to 0 gives the shortest route:

- `bump_penalty` (default 10): how much you hate bumps (`bumpy_roads`).
- `danger_penalty` (default 25): metres of detour you'd ride to pass one fewer close-overtaking spot (`danger_zones_raw`, summed Risk Index Overtaking; readings of 25 cm or less ignored).
- `pm_penalty` (default 0.5): how much you hate bad air (`air_quality`, fine dust ranked within each ride so weather drops out, averaged per street).
- `stop_penalty` (default 0.5): how much you hate slowing down and stopping at traffic lights, in congestion (`traffic_flow`) or at a lift (each costs 100 m × this).

`prefer_time=true` plans by riding time instead of distance, using the speed bikes were measured at on each street (`speed_map`); the penalties still apply. Every route reports its expected `duration_s`.

`/route/compare` takes the same parameters and returns the route next to the shortest route (by distance, with `detour_pct` and `extra_time_pct`), to draw both and show what the penalties changed. See `/docs` for the response.

`/route/grade` takes the same parameters and returns the same route in pieces coloured by grade (flat < 2% … very steep ≥ 10%), plus climb, descent and the steepest piece. It is display only: grade doesn't change the route. Heights: LGL DGM1 (Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0), see [routing/README.md](routing/README.md#grade-display-only-not-in-the-route-cost).

Map overlays: `/roughness` (streets), `/danger` (overtaking spots), `/air` (air-quality points, 0-1 worse than usual for the same bike trip) , `/flow` (streets, 0-1 stop-and-go) and `/speed` (streets, measured cyclist km/h) return GeoJSON.

Danger points come from `danger_zones_raw_heilbronn` (one row per overtake, with device id and exact distance) and are snapped to the nearest street within 25 m. [routing/README.md](routing/README.md) explains how route planning works and why readings of 25 cm or less are ignored.

For a clickable demo map, start the API, run `python -m http.server 5500 -d demo-prototype` and open http://127.0.0.1:5500. It is a throwaway prototype kept outside `frontend/`.

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


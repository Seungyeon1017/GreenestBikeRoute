# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Getting the data
Downloads the Heilbronn datasets from the [ATRAI API](https://hackathon.greencity.hn/resources/bike-data) into `data/` (~85 MB):

```bash
pip install -r requirements.txt
python -X utf8 download_data.py
```

## Routing API
Serves bike routes that avoid bumpy streets, close-overtaking spots and streets with heavy traffic and bad air as GeoJSON. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds. See [Backend Setup and Usage](#backend-setup-and-usage) for how to start it.

Example request: `/route?from_lat=49.14838&from_lon=9.22687&to_lat=49.1262&to_lon=9.22439&bump_penalty=10`. Three penalties steer the route, and setting all of them to 0 gives the shortest route:

- `bump_penalty` (default 10): how much you hate bumps (`bumpy_roads`).
- `danger_penalty` (default 25): metres of detour you'd ride to pass one fewer close-overtaking spot (`danger_zones`, summed Risk Index Overtaking).
- `pm_penalty` (default 2): how much you hate traffic and bad air (`danger_zones_PM`, mean Risk Index per street).

Danger points are snapped to the nearest street within 25 m. [routing/README.md](routing/README.md) explains how route planning works and why.

For a clickable demo map, start the API, run `python -m http.server 5500 -d demo-prototype` and open http://127.0.0.1:5500. It is a throwaway prototype kept outside `frontend/`.

## Backend Setup and Usage

### 1. Run the Backend Locally with `uv`

Make sure you are in the project root directory:

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

This project uses **port `8001` on the host machine** because another local FastAPI project already uses port `8000`.

When running locally, Uvicorn listens directly on port `8001`.

When running with Docker Compose, the port mapping in `compose.yml` is:

```yaml
ports:
  - "8001:8000"
```

The mapping follows the format `HOST_PORT:CONTAINER_PORT`:

- **Host port `8001`:** The port accessed from your computer.
- **Container port `8000`:** The port on which Uvicorn listens inside the Docker container.

Therefore, the backend is accessed at http://127.0.0.1:8001 in both cases, even though Docker runs Uvicorn on port `8000` inside the container.

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


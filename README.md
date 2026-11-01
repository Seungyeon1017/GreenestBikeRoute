# GreenestBikeRoute

Greenest Routes for Bikes is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone. We would like to show a map and possibly plan routes using data mainly from senseBox:bike (air quality, bumpy roads, traffic situations) but also possibly shades or noise. Through this way, we could promote biking and cut emissions from mobility.

The backend (`backend/`, FastAPI) plans the routes and serves map data; the frontend (`frontend/`, Next.js) is the website. Once the backend is running, its endpoints, parameters and responses are documented on the interactive API docs page at http://127.0.0.1:8001/docs. How route planning works is explained in [routing/README.md](routing/README.md), and data sources and licenses in [data/README.md](data/README.md).

## Setup

### Backend

Run all commands from the project root.

Install the dependencies using the lockfile:

```powershell
uv sync
```

Start the FastAPI backend:

```powershell
uv run uvicorn backend.app:app --reload --port 8001
```

The API is then at http://127.0.0.1:8001 and the Swagger UI at http://127.0.0.1:8001/docs. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds. Port `8001` is used instead of `8000` in case another local FastAPI project uses it.

Run the tests:

```powershell
uv run pytest
```

#### Docker Compose

`compose.yml` starts the backend and the PostgreSQL database for user accounts. Once, create `.env` from the example and set your own password and secret:

```powershell
copy .env.users.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste after USERS_JWT_SECRET_KEY=
```

Build and start both in the background (the backend creates the users tables itself on start):

```powershell
docker compose up --build -d
```

Check the containers, follow the backend logs (stop with `Ctrl+C`, which does not stop the container), and stop everything:

```powershell
docker compose ps
docker compose logs -f backend
docker compose down
```

The backend is again at http://127.0.0.1:8001 (host port `8001` maps to Uvicorn's `8000` in the container). `./data` and `./cache` are mounted into the container. Users and saved routes stay in the `postgres-data` volume; `docker compose down -v` deletes them. Rebuild with `docker compose up --build -d` only after changing the Dockerfile or dependencies.

### Frontend

The website lives in `frontend/` (Next.js) with the tabs: Overview, Plan a Trip and Highlights.

For development, first time only (and again whenever `frontend/package.json` changes):

```bash
cd frontend
npx yarn@1.22.22 install
npx yarn@1.22.22 prisma generate
```

Every time:

```bash
cd frontend
npx yarn@1.22.22 dev
```

Then open http://localhost:3000. Saved component changes show up within a second.

To run the production build with Docker Compose instead (start the backend first):

```powershell
cd frontend
docker compose up --build -d
```

It serves on http://localhost:3000. There is no hot reload, so use `yarn dev` for frontend work and this build as a final check. 

The Overview map reads small files from `frontend/public/map-data/`. After downloading new data, rebuild them with:

```bash
node frontend/scripts/build-map-data.mjs
```

## License

Code: [AGPL-3.0](LICENSE), the license of the Green City Dashboard that `frontend/` is forked from.

Data: each dataset keeps its source's license; see [data/README.md](data/README.md#licenses) for credits.

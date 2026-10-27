# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Getting the data
Downloads the Heilbronn datasets from the [ATRAI API](https://hackathon.greencity.hn/resources/bike-data) into `data/` (~85 MB):

```bash
pip install -r requirements.txt
python -X utf8 download_data.py
```

## Routing API
Serves bike routes that avoid bumpy streets as GeoJSON. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds.

```bash
uvicorn backend.app:app
```

Try it at http://127.0.0.1:8000/docs, e.g. `/route?from_lat=49.14838&from_lon=9.22687&to_lat=49.1262&to_lon=9.22439&penalty=10`. `penalty` is how much you hate bumps: 0 gives the shortest route. Run the tests with `python -m pytest`.

For a clickable demo map, start the API, run `python -m http.server 5500 -d demo-prototype` and open http://127.0.0.1:5500. It is a throwaway prototype kept outside `frontend/`.

## Running the frontend
The website lives in `frontend/` (Next.js, based on the Green City Dashboard Heilbronn). It has three tabs: Overview, Plan a Trip and Highlights.

First time only (and again whenever `frontend/package.json` changes):

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

Then open http://localhost:3000 (`/overview`, `/plan-trip`, `/highlights`). Stop the server with `Ctrl+C`. Use yarn, not `npm install`: npm ignores `yarn.lock` and fails with a peer-dependency error.

Without a database (`DATABASE_URL`) the site still runs and falls back to German texts. For route search, also start the routing API above; the frontend calls `NEXT_PUBLIC_GREENEST_API_URL` (default `http://127.0.0.1:8000`).

The Overview map reads small files from `frontend/public/map-data/`. After downloading new data, rebuild them with `node frontend/scripts/build-map-data.mjs`.

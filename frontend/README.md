# GreenestBikeRoute – Frontend

Next.js app for GreenestBikeRoute Heilbronn, with three tabs:

- **Overview** (`/overview`): map of environmental layers per area, loaded from `public/map-data/`.
- **Plan trip** (`/plan-trip`): compare the fastest and the greenest bike route.
- **Highlights** (`/highlights`): green places and experiences around Heilbronn.

The UI lives in `app/(greenest)/` and `components/Greenest/`. All calls to the FastAPI backend go through `services/greenestApi.ts`.

## Run with Docker

```bash
docker compose up --build
```

Then open http://localhost:3000. The backend URL is set by `NEXT_PUBLIC_GREENEST_API_URL` in `compose.yml` (default `http://127.0.0.1:8000`).

## Run locally

```bash
yarn install
yarn dev
```

## Map data

`scripts/build-map-data.mjs` turns the datasets in `../data` (downloaded by `../download_data.py`) into the GeoJSON files in `public/map-data/`:

```bash
node scripts/build-map-data.mjs
```

## License

Based on the Green City Dashboard Heilbronn (Klimadashboard), licensed under [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.en.html). See `LICENSE`.

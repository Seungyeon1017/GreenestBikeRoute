# GreenestBikeRoute
*Greenest Bike Route* is a smart cycling navigation platform that recommends routes based on environmental quality and cycling comfort, rather than distance alone.

## Getting the data
Downloads the Heilbronn datasets from the [ATRAI API](https://hackathon.greencity.hn/resources/bike-data) into `data/` (~85 MB):

```bash
pip install -r requirements.txt
python -X utf8 download_data.py
```

## Routing API
Serves bike routes that avoid bumpy streets, close-overtaking spots and streets with heavy traffic and bad air as GeoJSON. The first start downloads the Heilbronn street graph from OpenStreetMap into `cache/` (about 2 minutes); later starts take a few seconds.

```bash
uvicorn backend.app:app --port 8001
```

Or with Docker: `docker compose up -d --build`, also on port 8001. Rebuild after every code change, since the code is baked into the image.

Try it at http://127.0.0.1:8001/docs, e.g. `/route?from_lat=49.14838&from_lon=9.22687&to_lat=49.1262&to_lon=9.22439&bump_penalty=10`. Three penalties steer the route, and setting all of them to 0 gives the shortest route:

- `bump_penalty` (default 10): how much you hate bumps (`bumpy_roads`).
- `danger_penalty` (default 25): metres of detour you'd ride to pass one fewer close-overtaking spot (`danger_zones`, summed Risk Index Overtaking).
- `pm_penalty` (default 2): how much you hate traffic and bad air (`danger_zones_PM`, mean Risk Index per street).

Danger points are snapped to the nearest street within 25 m. Run the tests with `python -m pytest`.

For a clickable demo map, start the API, run `python -m http.server 5500 -d demo-prototype` and open http://127.0.0.1:5500. It is a throwaway prototype kept outside `frontend/`.

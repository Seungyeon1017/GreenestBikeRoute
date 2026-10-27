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

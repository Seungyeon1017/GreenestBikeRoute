"""HTTP API for the bike router. From the repo root: uvicorn backend.app:app"""
from contextlib import asynccontextmanager
from datetime import datetime
from functools import cache
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.schemas import EXAMPLE_TRIP, AirCollection, DangerCollection, Error, FlowCollection, GradeCollection, \
    LightingCollection, RouteCollection, RouteComparison, RoughnessCollection, ShadeCollection, SpeedCollection
from download_data import load_features
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY, \
    DEFAULT_SHADE_PENALTY, DEFAULT_STOP_PENALTY, air_ranks, clean_overtaking
from routing.elevation import attach_elevation, load_elevation
from routing.grade import NoElevationError, route_grade
from routing.graph import load_graph
from routing.route import RouteError, compare_routes, edge_coords, find_route


class GeoJSONResponse(JSONResponse):
    media_type = "application/geo+json"


@cache
def roughness_collection():
    """The measured streets from bumpy_roads_heilbronn, trimmed to geometry + roughness (0-100)."""
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"roughness": f["properties"]["Normalized Roughness"]}}
        for f in load_features("bumpy_roads_heilbronn")
    ]
    return {"type": "FeatureCollection", "features": features}


@cache
def danger_collection():
    """The overtaking spots routing uses (over 25 cm), trimmed to geometry + risk (0-1)."""
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"risk": f["properties"]["Risk Index Overtaking"]}}
        for f in clean_overtaking(load_features("danger_zones_raw_heilbronn"))
    ]
    return {"type": "FeatureCollection", "features": features}


@cache
def air_collection():
    """The air_quality points routing uses, trimmed to geometry + air rank (0-1, within each ride)."""
    lonlat, ranks = air_ranks(load_features("air_quality_heilbronn"))
    features = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": list(p)}, "properties": {"air": r}}
        for p, r in zip(lonlat, ranks)
    ]
    return {"type": "FeatureCollection", "features": features}


@cache
def flow_collection():
    """The measured streets from traffic_flow_heilbronn, trimmed to geometry + stop_go (0-1, 1 - avg_traffic_flow)."""
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"stop_go": 1 - f["properties"]["avg_traffic_flow"]}}
        for f in load_features("traffic_flow_heilbronn") if f["properties"].get("avg_traffic_flow") is not None
    ]
    return {"type": "FeatureCollection", "features": features}


@cache
def speed_collection():
    """The measured streets from speed_map_heilbronn, trimmed to geometry + speed_kmh (mean cyclist speed)."""
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"speed_kmh": f["properties"]["avg_speed[km/h]"]}}
        for f in load_features("speed_map_heilbronn") if f["properties"].get("avg_speed[km/h]") is not None
    ]
    return {"type": "FeatureCollection", "features": features}


def street_collection(G, key):
    """The graph's streets with a value for edge attribute `key`, each street once (a two-way street is two edges),
    trimmed to geometry + that value."""
    features, seen = [], set()
    for u, v, d in G.edges(data=True):
        street = (min(u, v), max(u, v), str(d["osmid"]), round(float(d["length"]), 1))
        if d.get(key) is None or street in seen:
            continue
        seen.add(street)
        coords = [[round(x, 6), round(y, 6)] for x, y in edge_coords(G, u, v, d)]
        value = [round(x, 2) for x in d[key]] if isinstance(d[key], list) else round(d[key], 2)
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                         "properties": {key: value}})
    return {"type": "FeatureCollection", "features": features}


API_DESCRIPTION = """
Bike routes through **Heilbronn** that avoid bumpy streets, close-overtaking spots, bad air and stop-and-go,
based on ATRAI bike sensor data, optionally the fastest one by measured cyclist speed.

**Quick start:** call `/route/compare` with the example trip (pre-filled under *Try it out*) and draw
`route` and `shortest` on a map. `/route` returns just the route as GeoJSON.
`/route/grade` returns the same route split into pieces coloured by how steep they are (display only:
grade doesn't change which route is picked).

- **Coordinate order:** the query takes `lat` and `lon` separately, but every GeoJSON response is in
  **[lon, lat]** order (Leaflet's `L.geoJSON` handles this; raw `L.polyline` needs `[lat, lon]`).
- **Penalties:** 0 ignores a factor; all four at 0 give the shortest route. Higher values accept longer detours.
- **prefer_time:** weighs each street by its riding time at the speed bikes were measured at (`speed_map`) instead
  of its length. Every route reports its expected `duration_s` either way.
- **depart_time:** when the trip starts (local Heilbronn time unless it has a time zone). If the sun is up then,
  `shade_penalty` makes sunny streets cost more, using the shade slot nearest that time of day. If the sun has set
  (or not yet risen) on that date, `dark_penalty` makes streets that are probably unlit cost more instead.
  Without `depart_time`, neither applies. Shade is computed for a summer day (21 July, 09/12/15/18 h), so in other
  seasons it shows where buildings and trees shade a street, not the exact shadow of that day.
- **Errors:** 400 with a readable `detail` when a point is more than 500 m from a Heilbronn street or no
  route exists; 422 when a parameter is missing or out of range; 503 from `/route/grade` when the server
  has no elevation data (`python -m routing.elevation`).
- **Grade:** each piece has `grade_pct` (positive uphill in the travel direction), `severity` (flat < 2 %,
  gentle 2-4, noticeable 4-6, steep 6-10, very_steep 10 % and more) and a suggested `color`; `summary` has
  climb, descent and the steepest pieces. Very short steep pieces can be terrain-model noise.
- **Map overlays:** `/roughness`, `/danger`, `/air` and `/flow` are static GeoJSON layers. Each
  value is 0-1 (roughness 0-100), and higher is always worse. `/speed` gives km/h, where higher is faster.
  `/shade` (share in shade per time slot) and `/lighting` (chance a street is lit at night) are 0-1 where higher
  is better.

Heights for `/route/grade`: Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0 (DGM1).
Shade: LGL BW LoD2 (dl-de/by-2-0) and Stadt Heilbronn Baumkataster (dl-de/by-2-0).
Lighting: OpenStreetMap contributors (ODbL), Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0).
"""


def trip_example(name):
    """The example trip's value for query parameter `name`, so Swagger UI's "Try it out" is pre-filled."""
    return {"example_trip": {"summary": "Example trip (README)", "value": EXAMPLE_TRIP[name]}}


def route_query(
    from_lat: float = Query(..., ge=-90, le=90, description="Start latitude (must be in Heilbronn)",
                            openapi_examples=trip_example("from_lat")),
    from_lon: float = Query(..., ge=-180, le=180, description="Start longitude", openapi_examples=trip_example("from_lon")),
    to_lat: float = Query(..., ge=-90, le=90, description="End latitude (must be in Heilbronn)",
                          openapi_examples=trip_example("to_lat")),
    to_lon: float = Query(..., ge=-180, le=180, description="End longitude", openapi_examples=trip_example("to_lon")),
    bump_penalty: float = Query(DEFAULT_BUMP_PENALTY, ge=0, le=50, description=(
        "How much do you hate bumps. 0 = ignore; 10 accepts a few % detour for smoother streets; 50 = strongly avoid")),
    danger_penalty: float = Query(DEFAULT_DANGER_PENALTY, ge=0, le=100, description=(
        "How much do you hate close overtaking: metres of detour you'd ride to pass one fewer close-overtaking spot")),
    pm_penalty: float = Query(DEFAULT_PM_PENALTY, ge=0, le=5, description=(
        "How much do you hate bad air (fine dust). 0 = ignore, 5 = strongly avoid")),
    stop_penalty: float = Query(DEFAULT_STOP_PENALTY, ge=0, le=5, description=(
        "How much do you hate stop-and-go (traffic lights, congestion, waiting for a lift). 0 = ignore, "
        "5 = strongly avoid; detours stay small, as streets differ little. Each lift costs this x 100 m")),
    prefer_time: bool = Query(False, description=(
        "Time matters, not distance: weigh each street by its riding time at the measured cyclist speed "
        "(unmeasured streets at the median, 15.7 km/h) instead of its length. The penalties still apply")),
    shade_penalty: float = Query(DEFAULT_SHADE_PENALTY, ge=0, le=5, description=(
        "By day: how much do you hate riding in the sun. 0 = ignore, 5 = strongly prefer shaded streets. "
        "Only applies with a depart_time when the sun is up")),
    dark_penalty: float = Query(DEFAULT_DARK_PENALTY, ge=0, le=5, description=(
        "After dark: how much do you hate unlit streets. 0 = ignore, 5 = strongly prefer lit streets. "
        "Only applies with a depart_time between sunset and sunrise")),
    depart_time: Optional[datetime] = Query(None, description=(
        "When the trip starts, e.g. 2026-07-21T15:00 (Heilbronn local time) or with a time zone. Sun up: "
        "shade_penalty applies; sun down: dark_penalty applies. Leave out to ignore both"),
        openapi_examples={"afternoon": {"summary": "Summer afternoon (shade counts)", "value": "2026-07-21T15:00"},
                          "night": {"summary": "Autumn evening after sunset (lighting counts)", "value": "2026-10-28T19:30"}}),
):
    """The query parameters shared by /route, /route/compare and /route/grade."""
    return (from_lat, from_lon), (to_lat, to_lon), (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time,
                                                     shade_penalty, dark_penalty, depart_time)


ROUTE_ERRORS = {400: {"description": "Start or end is outside Heilbronn, or no route exists",
                      "content": {"application/json": {"schema": Error.model_json_schema(), "example": {
                          "detail": "start point is 812 m from the nearest Heilbronn street"}}}}}


ROUTING, OVERLAYS = "Routing", "Map overlays"
TAGS_METADATA = [
    {"name": ROUTING, "description": "Plan a bike route from A to B, compare it with the shortest one, "
                                       "or show its grade."},
    {"name": OVERLAYS, "description": "Static GeoJSON layers of the measured data, to draw on a map."},
]


def create_app(graph=None):
    """`graph` lets tests pass a small graph; by default the Heilbronn graph is loaded at startup."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.graph = graph if graph is not None else load_graph()
        attach_elevation(app.state.graph, load_elevation())  # node heights for /route/grade
        yield

    app = FastAPI(title="Greenest Bike Route", description=API_DESCRIPTION, lifespan=lifespan,
                  openapi_tags=TAGS_METADATA)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    def routed(route_fn, query):
        origin, destination, penalties = query
        try:
            return route_fn(app.state.graph, origin, destination, *penalties)
        except RouteError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/route", tags=[ROUTING], summary="Bike route from A to B as GeoJSON", response_class=GeoJSONResponse,
             response_model=RouteCollection, response_description="One LineString feature: the route",
             responses=ROUTE_ERRORS)
    def route(query=Depends(route_query)):
        return GeoJSONResponse(routed(find_route, query))

    @app.get("/route/compare", tags=[ROUTING], summary="Bike route from A to B next to the shortest route",
             response_model=RouteComparison, responses=ROUTE_ERRORS,
             response_description="The route, the shortest route, and how much they differ")
    def route_compare(query=Depends(route_query)):
        return JSONResponse(routed(compare_routes, query))

    @app.get("/route/grade", tags=[ROUTING], summary="The route from /route split into pieces coloured by grade (display only)",
             response_class=GeoJSONResponse, response_model=GradeCollection,
             responses={**ROUTE_ERRORS, 503: {"description": "No elevation data: run python -m routing.elevation",
                                              "model": Error}},
             response_description="LineStrings with `grade_pct`, `severity` and `color`, plus route totals in `summary`")
    def route_grade_pieces(query=Depends(route_query)):
        try:
            return GeoJSONResponse(routed(route_grade, query))
        except NoElevationError as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/roughness", tags=[OVERLAYS], summary="Measured street roughness as GeoJSON, e.g. for a map overlay",
             response_class=GeoJSONResponse, response_model=RoughnessCollection,
             response_description="LineStrings with `roughness` 0-100 (higher = bumpier); unmeasured streets are left out")
    def roughness():
        return GeoJSONResponse(roughness_collection())

    @app.get("/danger", tags=[OVERLAYS], summary="Spots where cars overtook bikes closely, as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=DangerCollection,
             response_description="Points with `risk` 0-1 (higher = closer, more certain overtake)")
    def danger():
        return GeoJSONResponse(danger_collection())

    @app.get("/air", tags=[OVERLAYS], summary="Air quality (worse than usual for its bike trip) as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=AirCollection,
             response_description="Points with `air` 0-1 (0.5 = usual for that bike trip, higher = worse). About 21 MB")
    def air():
        return GeoJSONResponse(air_collection())

    @app.get("/flow", tags=[OVERLAYS], summary="How often bikes have to slow down or stop per street, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=FlowCollection,
             response_description="LineStrings with `stop_go` 0-1 (higher = more slowing and stopping); unmeasured streets are left out")
    def flow():
        return GeoJSONResponse(flow_collection())

    @app.get("/speed", tags=[OVERLAYS], summary="How fast bikes ride per street, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=SpeedCollection,
             response_description="LineStrings with `speed_kmh` (mean measured cyclist speed, waits included; higher = faster); unmeasured streets are left out")
    def speed():
        return GeoJSONResponse(speed_collection())

    @app.get("/shade", tags=[OVERLAYS], summary="How much of each street lies in building or tree shade, per time of day, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=ShadeCollection,
             response_description="LineStrings with `shade`: one value 0-1 per entry of `slots` (higher = more shade)")
    def shade():
        if not hasattr(app.state, "shade"):
            app.state.shade = {**street_collection(app.state.graph, "shade"),
                               "slots": app.state.graph.graph.get("shade_slots", [])}
        return GeoJSONResponse(app.state.shade)

    @app.get("/lighting", tags=[OVERLAYS], summary="Chance each street is lit at night, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=LightingCollection,
             response_description="LineStrings with `lit` 0-1 (higher = more likely lit); streets without data are left out")
    def lighting():
        if not hasattr(app.state, "lighting"):
            app.state.lighting = street_collection(app.state.graph, "lit")
        return GeoJSONResponse(app.state.lighting)

    return app


app = create_app()

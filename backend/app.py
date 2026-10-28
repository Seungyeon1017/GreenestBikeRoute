"""HTTP API for the bike router. From the repo root: uvicorn backend.app:app"""
from contextlib import asynccontextmanager
from functools import cache

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.schemas import EXAMPLE_TRIP, AirCollection, DangerCollection, Error, FlowCollection, GradeCollection, \
    RouteCollection, RouteComparison, RoughnessCollection, SpeedCollection
from download_data import load_features
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_PM_PENALTY, DEFAULT_STOP_PENALTY, air_ranks, \
    clean_overtaking
from routing.elevation import attach_elevation, load_elevation
from routing.grade import NoElevationError, route_grade
from routing.graph import load_graph
from routing.route import RouteError, compare_routes, find_route


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
- **Errors:** 400 with a readable `detail` when a point is more than 500 m from a Heilbronn street or no
  route exists; 422 when a parameter is missing or out of range.
- **Map overlays:** `/roughness`, `/danger`, `/air` and `/flow` are static GeoJSON layers. Each
  value is 0-1 (roughness 0-100), and higher is always worse. `/speed` gives km/h, where higher is faster.
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
):
    """The query parameters shared by /route, /route/compare and /route/grade."""
    return (from_lat, from_lon), (to_lat, to_lon), (bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time)


ROUTE_ERRORS = {400: {"description": "Start or end is outside Heilbronn, or no route exists",
                      "content": {"application/json": {"schema": Error.model_json_schema(), "example": {
                          "detail": "start point is 812 m from the nearest Heilbronn street"}}}}}


def create_app(graph=None):
    """`graph` lets tests pass a small graph; by default the Heilbronn graph is loaded at startup."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.graph = graph if graph is not None else load_graph()
        attach_elevation(app.state.graph, load_elevation())  # node heights for /route/grade
        yield

    app = FastAPI(title="Greenest Bike Route", description=API_DESCRIPTION, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    def routed(route_fn, query):
        origin, destination, penalties = query
        try:
            return route_fn(app.state.graph, origin, destination, *penalties)
        except RouteError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/route", summary="Bike route from A to B as GeoJSON", response_class=GeoJSONResponse,
             response_model=RouteCollection, response_description="One LineString feature: the route",
             responses=ROUTE_ERRORS)
    def route(query=Depends(route_query)):
        return GeoJSONResponse(routed(find_route, query))

    @app.get("/route/compare", summary="Bike route from A to B next to the shortest route",
             response_model=RouteComparison, responses=ROUTE_ERRORS,
             response_description="The route, the shortest route, and how much they differ")
    def route_compare(query=Depends(route_query)):
        return JSONResponse(routed(compare_routes, query))

    @app.get("/route/grade", summary="The route from /route split into pieces coloured by grade (display only)",
             response_class=GeoJSONResponse, response_model=GradeCollection,
             responses={**ROUTE_ERRORS, 503: {"description": "No elevation data: run python -m routing.elevation",
                                              "model": Error}},
             response_description="LineStrings with `grade_pct`, `severity` and `color`, plus route totals in `summary`")
    def route_grade_pieces(query=Depends(route_query)):
        try:
            return GeoJSONResponse(routed(route_grade, query))
        except NoElevationError as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/roughness", summary="Measured street roughness as GeoJSON, e.g. for a map overlay",
             response_class=GeoJSONResponse, response_model=RoughnessCollection,
             response_description="LineStrings with `roughness` 0-100 (higher = bumpier); unmeasured streets are left out")
    def roughness():
        return GeoJSONResponse(roughness_collection())

    @app.get("/danger", summary="Spots where cars overtook bikes closely, as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=DangerCollection,
             response_description="Points with `risk` 0-1 (higher = closer, more certain overtake)")
    def danger():
        return GeoJSONResponse(danger_collection())

    @app.get("/air", summary="Air quality (worse than usual for its bike trip) as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=AirCollection,
             response_description="Points with `air` 0-1 (0.5 = usual for that bike trip, higher = worse). About 21 MB")
    def air():
        return GeoJSONResponse(air_collection())

    @app.get("/flow", summary="How often bikes have to slow down or stop per street, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=FlowCollection,
             response_description="LineStrings with `stop_go` 0-1 (higher = more slowing and stopping); unmeasured streets are left out")
    def flow():
        return GeoJSONResponse(flow_collection())

    @app.get("/speed", summary="How fast bikes ride per street, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=SpeedCollection,
             response_description="LineStrings with `speed_kmh` (mean measured cyclist speed, waits included; higher = faster); unmeasured streets are left out")
    def speed():
        return GeoJSONResponse(speed_collection())

    return app


app = create_app()

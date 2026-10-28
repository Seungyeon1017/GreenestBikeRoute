"""HTTP API for the bike router. From the repo root: uvicorn backend.app:app"""
from contextlib import asynccontextmanager
from functools import cache

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.schemas import AirCollection, DangerCollection, Error, FlowCollection, RouteCollection, RouteComparison, \
    RoughnessCollection
from download_data import load_features
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_PM_PENALTY, DEFAULT_STOP_PENALTY, air_ranks, \
    clean_overtaking
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


def route_query(
    from_lat: float = Query(..., ge=-90, le=90),
    from_lon: float = Query(..., ge=-180, le=180),
    to_lat: float = Query(..., ge=-90, le=90),
    to_lon: float = Query(..., ge=-180, le=180),
    bump_penalty: float = Query(DEFAULT_BUMP_PENALTY, ge=0, le=50, description="How much do you hate bumps"),
    danger_penalty: float = Query(DEFAULT_DANGER_PENALTY, ge=0, le=100,
                                  description="How much do you hate close overtaking (metres of detour per spot)"),
    pm_penalty: float = Query(DEFAULT_PM_PENALTY, ge=0, le=5, description="How much do you hate bad air (fine dust)"),
    stop_penalty: float = Query(DEFAULT_STOP_PENALTY, ge=0, le=5,
                                description="How much do you hate stop-and-go (traffic lights, congestion)"),
):
    """The query parameters shared by /route and /route/compare."""
    return (from_lat, from_lon), (to_lat, to_lon), (bump_penalty, danger_penalty, pm_penalty, stop_penalty)


ROUTE_ERRORS = {400: {"description": "Start or end is outside Heilbronn, or no route exists",
                      "content": {"application/json": {"schema": Error.model_json_schema(), "example": {
                          "detail": "start point is 812 m from the nearest Heilbronn street"}}}}}


def create_app(graph=None):
    """`graph` lets tests pass a small graph; by default the Heilbronn graph is loaded at startup."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.graph = graph if graph is not None else load_graph()
        yield

    app = FastAPI(title="Greenest Bike Route", lifespan=lifespan)
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
             response_model=RouteComparison, responses=ROUTE_ERRORS)
    def route_compare(query=Depends(route_query)):
        return JSONResponse(routed(compare_routes, query))

    @app.get("/roughness", summary="Measured street roughness as GeoJSON, e.g. for a map overlay",
             response_class=GeoJSONResponse, response_model=RoughnessCollection)
    def roughness():
        return GeoJSONResponse(roughness_collection())

    @app.get("/danger", summary="Spots where cars overtook bikes closely, as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=DangerCollection)
    def danger():
        return GeoJSONResponse(danger_collection())

    @app.get("/air", summary="Air quality (worse than usual for its bike trip) as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=AirCollection)
    def air():
        return GeoJSONResponse(air_collection())

    @app.get("/flow", summary="How often bikes have to slow down or stop per street, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=FlowCollection)
    def flow():
        return GeoJSONResponse(flow_collection())

    return app


app = create_app()

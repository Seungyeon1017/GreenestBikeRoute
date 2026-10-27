"""HTTP API for the bike router. From the repo root: uvicorn backend.app:app"""
from contextlib import asynccontextmanager
from functools import cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from download_data import load_features
from routing.costs import DEFAULT_DANGER_PENALTY, DEFAULT_PENALTY, DEFAULT_PM_PENALTY
from routing.graph import load_graph
from routing.route import RouteError, find_route


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
    """The overtaking spots from danger_zones_heilbronn, trimmed to geometry + risk (0-1)."""
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"risk": f["properties"]["Risk Index Overtaking"]}}
        for f in load_features("danger_zones_heilbronn")
    ]
    return {"type": "FeatureCollection", "features": features}


def create_app(graph=None):
    """`graph` lets tests pass a small graph; by default the Heilbronn graph is loaded at startup."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.graph = graph if graph is not None else load_graph()
        yield

    app = FastAPI(title="Greenest Bike Route", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

    @app.get("/route", summary="Bike route from A to B as GeoJSON")
    def route(
        from_lat: float = Query(..., ge=-90, le=90),
        from_lon: float = Query(..., ge=-180, le=180),
        to_lat: float = Query(..., ge=-90, le=90),
        to_lon: float = Query(..., ge=-180, le=180),
        penalty: float = Query(DEFAULT_PENALTY, ge=0, le=100, description="How much do you hate bumps"),
        danger_penalty: float = Query(DEFAULT_DANGER_PENALTY, ge=0, le=1000,
                                      description="How much do you hate close overtaking (metres of detour per spot)"),
        pm_penalty: float = Query(DEFAULT_PM_PENALTY, ge=0, le=100,
                                  description="How much do you hate traffic and bad air"),
    ):
        try:
            collection = find_route(app.state.graph, (from_lat, from_lon), (to_lat, to_lon),
                                    penalty, danger_penalty, pm_penalty)
        except RouteError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse(collection, media_type="application/geo+json")

    @app.get("/roughness", summary="Measured street roughness as GeoJSON, e.g. for a map overlay")
    def roughness():
        return JSONResponse(roughness_collection(), media_type="application/geo+json")

    @app.get("/danger", summary="Spots where cars overtook bikes closely, as GeoJSON points for a map overlay")
    def danger():
        return JSONResponse(danger_collection(), media_type="application/geo+json")

    return app


app = create_app()

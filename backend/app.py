"""HTTP API for the bike router. From the repo root: uvicorn backend.app:app"""
import json
from contextlib import asynccontextmanager
from datetime import datetime
from functools import cache
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.reports import SNAP_M, ReportError, Reports
from backend.schemas import EXAMPLE_TRIP, AirCollection, BikeFriendlyCollection, ClosureAnswer, ClosureCollection, ClosureFeature, ClosureReport,     DangerCollection, DayRoutes, Error, FlowCollection, GeofencingCollection, GradeCollection, LightingCollection, MappingCollection,     MappingFeature, MappingReport, PlaceCollection, RouteCollection, RouteComparison, RoughnessCollection, ScoreCollection,     ShadeCollection, SharingTrip, SpeedCollection, VehicleCollection, ZoneCollection
from backend.geocoding import Geocoder, GeocodingUnavailable, normalize
from backend.sharing import ATTRIBUTION, Sharing, SharingUnavailable
from backend.users.router import router as users_router
from download_data import DATA_DIR, load_features
from routing.calories import DEFAULT_WEIGHT_KG
from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY, \
    DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_PENALTY, MAX_POINTS, air_scores, clean_overtaking, \
    osm_way_ids
from routing.elevation import attach_elevation, load_crests, load_elevation
from routing.grade import NoElevationError, route_grade
from routing.graph import load_graph
from routing.route import RouteError, compare_routes, day_routes, edge_coords, find_route, nearest_street, set_closures,     sky, street_scores
from routing.sharing_trip import WalkNetwork, load_walk_graph, plan_sharing_trip


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
    """The air_quality points routing uses, trimmed to geometry + air score (0-1, 0.5 = typical, see air_scores)."""
    lonlat, scores, _ = air_scores(load_features("air_quality_heilbronn"), load_features("air_background_heilbronn"))
    features = [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": list(p)}, "properties": {"air": s}}
        for p, s in zip(lonlat, scores)
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



BIKE_FRIENDLY_PATH = DATA_DIR / "custom" / "bike_friendly_streets_heilbronn.geojson"


@cache
def bike_friendly_collection():
    """Bike paths, bike lanes and bike routes from OSM (Overpass query next to the file), trimmed to geometry + osm_id."""
    data = json.loads(BIKE_FRIENDLY_PATH.read_text(encoding="utf-8"))
    features = [
        {"type": "Feature", "geometry": f["geometry"], "properties": {"osm_id": int(f["id"].split("/")[1])}}
        for f in data["features"] if f["geometry"]["type"] == "LineString"
    ]
    return {"type": "FeatureCollection", "features": features}


def closure_feature(G, segment, state):
    """One segment of Reports.closure_states as a GeoJSON LineString, or None if the graph no longer has it."""
    u, v = segment
    a, b = (u, v) if G.has_edge(u, v) else (v, u)
    if not G.has_edge(a, b):
        return None
    d = next(iter(G[a][b].values()))
    return {"type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[round(x, 6), round(y, 6)] for x, y in edge_coords(G, a, b, d)]},
            "properties": {"segment": f"{u}-{v}", **state}}


def mapping_feature(report):
    """One report of Reports.mapping_reports as a GeoJSON Point."""
    properties = {k: v for k, v in report.items() if k not in ("lon", "lat")}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [report["lon"], report["lat"]]},
            "properties": properties}


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
- **Place names:** routes take coordinates only. For a landmark, address or street, search it with `/geocode`,
  let the rider pick one of the candidates ("did you mean …") and route with its coordinates. Search on Enter, not
  while typing: Nominatim allows 1 search a second for everyone, so results are cached and searches queue.
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
  is better. `/bike-friendly-streets` shows the bike paths, bike lanes and bike routes `prefer_bike_friendly` favours.
- **Closures:** riders report closed streets with `POST /reports/closures`, optionally with `until` (the last day,
  e.g. from the sign; else the report counts for 24 h, at most 30 days). Three live independent reports close the
  street segment for every route; with fewer, routes avoid it if the detour is at most 4x its length, and
  `reported_closures` counts the ones a route still rides. Since nobody reports a closure they already see, riders
  answer with one tap instead: `POST /reports/closures/{segment}/confirm` (still closed, or open again: two such
  answers lift it). When all reports lapse it stays `unconfirmed` for 3 days (routes still avoid it): ask riders
  whose trip starts or ends near it. `GET /reports/closures` shows them on a map.
- **Mapping mistakes:** `POST /reports/mapping` with `kind=rideable` reports a footway bikes ride on that routing
  leaves out (OSM lacks bicycle=yes). A maintainer checks it (`python -m backend.reports`); approved ways are routed
  from the next server start.
- **Overall score:** `/score` puts every street on one 0-100 scale (higher = better): its percentile, by length, among
  Heilbronn streets ranked by routing cost per metre. It takes the same penalties, `prefer_time`, `prefer_bike_friendly` and `depart_time` as
  `/route`, so it shows the streets the way that route request weighs them. Overtaking spots and air points count for
  the street they are snapped to.

Heights for `/route/grade`: Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0 (DGM1).
Shade: LGL BW LoD2 (dl-de/by-2-0) and Stadt Heilbronn Baumkataster (dl-de/by-2-0).
Lighting: OpenStreetMap contributors (ODbL), Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0).
Air: ATRAI bike sensors and senseBox:home stations (openSenseMap); streets along the NO₂ hotspots of the Luftreinhalteplan Heilbronn (Regierungspräsidium Stuttgart, 2020, Tabelle 3) start slightly worse.
"""


def trip_example(name):
    """The example trip's value for query parameter `name`, so Swagger UI's "Try it out" is pre-filled."""
    return {"example_trip": {"summary": "Example trip (README)", "value": EXAMPLE_TRIP[name]}}


def penalty_query(
    bump_penalty: float = Query(DEFAULT_BUMP_PENALTY, ge=0, le=MAX_POINTS, description=(
        "How much do you hate bumps, in points 0-10: each point makes a street among the bumpiest tenth cost 25% more "
        "than a typical one (2 = 1.5x, 10 = 3.5x), smoother than typical costs nothing extra. 0 = ignore")),
    danger_penalty: float = Query(DEFAULT_DANGER_PENALTY, ge=0, le=100, description=(
        "How much do you hate close overtaking: metres of detour you'd ride to pass one fewer close-overtaking spot")),
    pm_penalty: float = Query(DEFAULT_PM_PENALTY, ge=0, le=MAX_POINTS, description=(
        "How much do you hate bad air (fine dust), in points 0-10 as bump_penalty: each point makes a street among the "
        "worst tenth cost 25% more than a typical one. 0 = ignore")),
    stop_penalty: float = Query(DEFAULT_STOP_PENALTY, ge=0, le=MAX_POINTS, description=(
        "How much do you hate stop-and-go (traffic lights, congestion, waiting for a lift), in points 0-10 as "
        "bump_penalty. 0 = ignore. Each lift costs this x 25 m")),
    prefer_time: bool = Query(False, description=(
        "Time matters, not distance: weigh each street by its riding time at the measured cyclist speed "
        "(unmeasured streets at the median, 15.7 km/h) instead of its length. The penalties still apply")),
    shade_penalty: float = Query(DEFAULT_SHADE_PENALTY, ge=0, le=MAX_POINTS, description=(
        "By day: how much do you hate riding in the sun, in points 0-10: each point makes a fully sunny street cost 25% "
        "more. 0 = ignore. "
        "Only applies with a depart_time when the sun is up")),
    dark_penalty: float = Query(DEFAULT_DARK_PENALTY, ge=0, le=MAX_POINTS, description=(
        "After dark: how much do you hate unlit streets, in points 0-10: each point makes a surely unlit street cost "
        "25% more. 0 = ignore. "
        "Only applies with a depart_time between sunset and sunrise")),
    prefer_bike_friendly: float = Query(DEFAULT_PREFER_BIKE_FRIENDLY, ge=0, le=MAX_POINTS, description=(
        "How much do you prefer bike-friendly streets (bike paths, bike lanes, bike routes; see /bike-friendly-streets). "
        "In points 0-10: each point makes other streets cost 25% more (4 = they feel twice as long). 0 = ignore. Multiplies with the other dislikes, so it doesn't drown them")),
    depart_time: Optional[datetime] = Query(None, description=(
        "When the trip starts, e.g. 2026-07-21T15:00 (Heilbronn local time) or with a time zone. Sun up: "
        "shade_penalty applies; sun down: dark_penalty applies. Leave out to ignore both"),
        openapi_examples={"afternoon": {"summary": "Summer afternoon (shade counts)", "value": "2026-07-21T15:00"},
                          "night": {"summary": "Autumn evening after sunset (lighting counts)", "value": "2026-10-28T19:30"}}),
):
    """The penalties, prefer_time, prefer_bike_friendly and depart_time, shared by the routes and /score."""
    return bump_penalty, danger_penalty, pm_penalty, stop_penalty, prefer_time, shade_penalty, dark_penalty,         prefer_bike_friendly, depart_time


def route_query(
    from_lat: float = Query(..., ge=-90, le=90, description="Start latitude (must be in Heilbronn)",
                            openapi_examples=trip_example("from_lat")),
    from_lon: float = Query(..., ge=-180, le=180, description="Start longitude", openapi_examples=trip_example("from_lon")),
    to_lat: float = Query(..., ge=-90, le=90, description="End latitude (must be in Heilbronn)",
                          openapi_examples=trip_example("to_lat")),
    to_lon: float = Query(..., ge=-180, le=180, description="End longitude", openapi_examples=trip_example("to_lon")),
    penalties=Depends(penalty_query),
):
    """The query parameters shared by /route, /route/compare and /route/grade."""
    return (from_lat, from_lon), (to_lat, to_lon), penalties


def weight_query(weight_kg: float = Query(DEFAULT_WEIGHT_KG, gt=0, le=250, description=(
        "Rider weight in kg (with the bike's for climbs), for kcal. Does not change the route"))):
    return weight_kg


def rider_query(
    weight_kg=Depends(weight_query),
    e_bike: bool = Query(False, description=(
        "Pedelec: kcal is a rough estimate, see routing/calories.py. Does not change the route")),
):
    """The rider's weight and bike, for the kcal estimate of /route."""
    return {"weight_kg": weight_kg, "e_bike": e_bike}


# /score collections kept for the most recent penalty settings; each is ~4 MB.
SCORE_CACHE_SIZE = 8


ROUTE_ERRORS = {400: {"description": "Start or end is outside Heilbronn, or no route exists",
                      "content": {"application/json": {"schema": Error.model_json_schema(), "example": {
                          "detail": "start point is 812 m from the nearest Heilbronn street"}}}}}


ROUTING, PLACES, OVERLAYS, SHARING, REPORTS = "Routing", "Places", "Map overlays", "Sharing", "Reports"
TAGS_METADATA = [
    {"name": ROUTING, "description": "Plan a bike route from A to B, compare it with the shortest one, "
                                       "or show its grade."},
    {"name": PLACES, "description": "Find a landmark, address or street in Heilbronn, to route to its coordinates "
                                     "(OpenStreetMap via Nominatim)."},
    {"name": OVERLAYS, "description": "Static GeoJSON layers of the measured data, to draw on a map."},
    {"name": SHARING, "description": "Shared e-bikes and e-scooters free to rent right now and their parking zones, "
                                       "live from MobiData BW (Heilbronn: Dott). Each vehicle links to the provider's app."},
    {"name": REPORTS, "description": "Riders report closed streets (routing uses them right away) and mapping mistakes "
                                       "(checked by a maintainer first)."},
]


def near_query(
    near_lat: Optional[float] = Query(None, ge=-90, le=90, description="Latitude to sort by distance from, e.g. the route start"),
    near_lon: Optional[float] = Query(None, ge=-180, le=180, description="Longitude to sort by distance from"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Return at most this many (closest first if near_lat/near_lon is given)"),
):
    """The query parameters of /sharing and /sharing/zones."""
    if (near_lat is None) != (near_lon is None):
        raise HTTPException(status_code=422, detail="give both near_lat and near_lon, or neither")
    return (None if near_lat is None else (near_lat, near_lon)), limit


SHARING_ERRORS = {503: {"description": "The sharing feed can't be read right now", "model": Error}}
GEOCODE_ERRORS = {503: {"description": "The place search (Nominatim) can't be reached right now", "model": Error}}


def create_app(graph=None, sharing=None, reports=None, geocoder=None, walk_graph=None):
    """`graph`, `sharing`, `reports`, `geocoder` and `walk_graph` let tests pass small graphs, a fake feed, an in-memory
    report store and a fake place search; by default the Heilbronn bike graph is loaded at startup, the walking graph on
    the first /route/sharing, bike and scooter sharing is read live from MobiData BW, reports are kept in
    data/reports.sqlite3 and places are searched with Nominatim."""

    @asynccontextmanager
    async def lifespan(app):
        app.state.graph = graph if graph is not None else load_graph()
        attach_elevation(app.state.graph, load_elevation(), load_crests())  # node heights and bridge crests for /route/grade
        app.state.scores = {}
        yield

    app = FastAPI(title="Greenest Bike Route", description=API_DESCRIPTION, lifespan=lifespan,
                  openapi_tags=TAGS_METADATA)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Content-Type", "Authorization"])
    sharing = sharing if sharing is not None else Sharing()
    reports = reports if reports is not None else Reports()
    geocoder = geocoder if geocoder is not None else Geocoder()

    def shared(kind, query, vehicle="all"):
        near, limit = query
        try:
            return sharing.collection(kind, near, limit, vehicle)
        except SharingUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e))

    def routed(route_fn, query, **rider):
        origin, destination, penalties = query
        set_closures(app.state.graph, reports.closures())
        try:
            return route_fn(app.state.graph, origin, destination, *penalties, **rider)
        except RouteError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/route", tags=[ROUTING], summary="Bike route from A to B as GeoJSON", response_class=GeoJSONResponse,
             response_model=RouteCollection, response_description="One LineString feature: the route, with its kcal estimate",
             responses=ROUTE_ERRORS)
    def route(query=Depends(route_query), rider=Depends(rider_query)):
        return GeoJSONResponse(routed(find_route, query, **rider))

    @app.get("/route/compare", tags=[ROUTING], summary="Bike route from A to B next to the shortest route",
             response_model=RouteComparison, responses=ROUTE_ERRORS,
             response_description="The route, the shortest route, and how much they differ")
    def route_compare(query=Depends(route_query), rider=Depends(rider_query)):
        return JSONResponse(routed(compare_routes, query, **rider))

    @app.get("/route/day", tags=[ROUTING], summary="The route from A to B for every departure time of one day",
             response_model=DayRoutes, responses=ROUTE_ERRORS,
             response_description="Periods of the day with the same route, each as from /route/compare")
    def route_day(query=Depends(route_query), rider=Depends(rider_query)):
        """Like /route/compare, for the whole day of depart_time (today without one), e.g. for a departure time slider:
        by day the route follows the shade of the nearest shade slot, after dark the lit streets."""
        return JSONResponse(routed(day_routes, query, **rider))

    @app.get("/route/grade", tags=[ROUTING], summary="The route from /route split into pieces coloured by grade (display only)",
             response_class=GeoJSONResponse, response_model=GradeCollection,
             responses={**ROUTE_ERRORS, 503: {"description": "No elevation data: run python -m routing.elevation",
                                              "model": Error}},
             response_description="LineStrings with `grade_pct`, `severity` and `color`, plus route totals in `summary`")
    def route_grade_pieces(query=Depends(route_query), rider=Depends(rider_query)):
        try:
            return GeoJSONResponse(routed(route_grade, query, **rider))
        except NoElevationError as e:
            raise HTTPException(status_code=503, detail=str(e))

    @app.get("/route/sharing", tags=[ROUTING, SHARING], summary="Walk to a shared e-bike or e-scooter, ride it, walk to the end",
             response_model=SharingTrip, responses={**ROUTE_ERRORS, **SHARING_ERRORS},
             response_description="The vehicle to rent, the parking zone to leave it at, and the three legs")
    def route_sharing(query=Depends(route_query), vehicle: Literal["all", "bike", "scooter"] = Query(
            "all", description="Rent only an e-bike (bike), only an e-scooter (scooter), or whichever is quicker (all)"),
            park_in_zone: bool = Query(False, description=(
                "Always end the ride at a parking zone. Off: at the end itself, unless parking is not allowed there "
                "(see /sharing/geofencing); then wherever allowed that gets you to the end soonest")),
            weight_kg=Depends(weight_query)):
        """The quickest trip with a vehicle free to rent now within 1 km walk of the start, with enough battery.
        Dott is free-floating: the ride ends at the destination, or where its no-parking zones send you.
        400 when there is no vehicle or nowhere to leave it, 503 when the sharing feed can't be read."""
        origin, destination, penalties = query
        try:
            snap = sharing.snapshot()
        except SharingUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e))
        set_closures(app.state.graph, reports.closures())
        if not hasattr(app.state, "walk"):
            app.state.walk = WalkNetwork(walk_graph if walk_graph is not None else load_walk_graph())
        try:
            trip = plan_sharing_trip(app.state.graph, app.state.walk, snap["vehicles"], snap["zones"], origin, destination,
                                     penalties, vehicle, park_in_zone, snap["geofencing"], weight_kg)
        except RouteError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return JSONResponse({**trip, "updated": snap["updated"], "attribution": ATTRIBUTION})

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

    @app.get("/air", tags=[OVERLAYS], summary="Air quality (worse than usual for that hour and bike trip) as GeoJSON points for a map overlay",
             response_class=GeoJSONResponse, response_model=AirCollection,
             response_description="Points with `air` 0-1 (0.5 = usual, higher = worse). About 21 MB")
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

    @app.get("/bike-friendly-streets", tags=[OVERLAYS],
             summary="Streets that suit bikes (bike paths, bike lanes, bike routes), as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=BikeFriendlyCollection,
             response_description="LineStrings with `osm_id` (OpenStreetMap way id); every bike path, bike lane and bike route")
    def bike_friendly_streets():
        return GeoJSONResponse(bike_friendly_collection())

    @app.get("/score", tags=[OVERLAYS], summary="Overall score per street, all factors in one, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=ScoreCollection,
             response_description="LineStrings with `score` 0-100 (higher = better); every street of the bike graph")
    def score(penalties=Depends(penalty_query)):
        *weights, depart_time = penalties
        key = (*weights, *sky(app.state.graph, depart_time))  # departure times in the same shade slot score alike
        scores = app.state.scores
        if key not in scores:
            if len(scores) >= SCORE_CACHE_SIZE:
                del scores[next(iter(scores))]  # the oldest
            scores[key] = street_scores(app.state.graph, *penalties)
        return GeoJSONResponse(scores[key])

    @app.get("/sharing", tags=[SHARING], summary="Shared e-bikes and e-scooters free to rent right now, as GeoJSON points",
             response_class=GeoJSONResponse, response_model=VehicleCollection, responses=SHARING_ERRORS,
             response_description="Points with `vehicle` (bike/scooter), battery, range, price and a link to rent it in the provider's app")
    def sharing_vehicles(query=Depends(near_query), vehicle: Literal["all", "bike", "scooter"] = Query(
            "all", description="Only e-bikes (bike), only e-scooters (scooter), or both (all)")):
        return GeoJSONResponse(shared("vehicles", query, vehicle))

    @app.get("/sharing/zones", tags=[SHARING], summary="Sharing parking zones with how many bikes and scooters stand there",
             response_class=GeoJSONResponse, response_model=ZoneCollection, responses=SHARING_ERRORS,
             response_description="Points with the zone name, `bikes_available` and `scooters_available`")
    def sharing_zones(query=Depends(near_query)):
        return GeoJSONResponse(shared("zones", query))

    @app.get("/geocode", tags=[PLACES], summary="Places in Heilbronn matching a landmark, address or street, as GeoJSON points",
             response_class=GeoJSONResponse, response_model=PlaceCollection, responses=GEOCODE_ERRORS,
             response_description="Points with a `label` to show, best match first; empty if nothing matches")
    def geocode(q: str = Query(..., max_length=200, description=(
            "What the rider typed, e.g. Rathaus, Allee 40 or Kaiserstraße. Case and extra spaces don't matter"),
            openapi_examples={"landmark": {"summary": "Landmark", "value": "Rathaus"},
                              "address": {"summary": "Address", "value": "Allee 40"}}),
                limit: int = Query(5, ge=1, le=10, description="Return at most this many candidates")):
        if len(normalize(q)) < 3:
            raise HTTPException(status_code=422, detail="type at least 3 characters to search")
        try:
            return GeoJSONResponse(geocoder.collection(q, limit))
        except GeocodingUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e))

    def client(request):
        return request.client.host if request.client else ""

    @app.post("/reports/closures", tags=[REPORTS], summary="Report that a street is closed right now",
              status_code=201, response_model=ClosureFeature,
              responses={400: {"description": "No street within 50 m of the point, or `until` is in the past", "model": Error}},
              response_description="The street segment the report went to, with how many reports it has now")
    def report_closure(report: ClosureReport, request: Request):
        G = app.state.graph
        u, v, d, dist = nearest_street(G, report.lat, report.lon)
        if dist > SNAP_M:
            raise HTTPException(status_code=400, detail=f"no street within {SNAP_M} m: the nearest is {dist:.0f} m away")
        try:
            state = reports.report_closure(u, v, osm_way_ids(d["osmid"]), (report.lon, report.lat), report.reporter_id,
                                           client(request), report.note, report.until)
        except ReportError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return closure_feature(G, (min(u, v), max(u, v)), state)

    @app.post("/reports/closures/{segment}/confirm", tags=[REPORTS],
              summary="Answer whether a reported street is still closed (one tap)", response_model=ClosureFeature,
              responses={404: {"description": "No closure on this segment", "model": Error}},
              response_description="The segment with the answer counted; status `open` if the answers lifted it")
    def confirm_closure(segment: str, answer: ClosureAnswer, request: Request):
        G = app.state.graph
        try:
            key = tuple(map(int, segment.split("-")))
        except ValueError:
            key = None
        state = reports.closure_states().get(key)
        feature = state and closure_feature(G, key, state)
        if not feature:
            raise HTTPException(status_code=404, detail=f"no closure on segment {segment}")
        coords = feature["geometry"]["coordinates"]
        state = reports.report_closure(*key, state["osm_way_ids"], coords[len(coords) // 2], answer.reporter_id,
                                       client(request), still_closed=answer.still_closed)
        return closure_feature(G, key, state)

    @app.get("/reports/closures", tags=[REPORTS], summary="Streets riders reported closed, as GeoJSON for a map overlay",
             response_class=GeoJSONResponse, response_model=ClosureCollection,
             response_description="LineStrings with `status` (closed / reported / unconfirmed) and how many reports")
    def closures():
        features = [closure_feature(app.state.graph, segment, state) for segment, state in reports.closure_states().items()]
        return GeoJSONResponse({"type": "FeatureCollection", "features": [f for f in features if f]})

    @app.post("/reports/mapping", tags=[REPORTS], summary="Report a mapping mistake, e.g. a footway bikes ride on",
              status_code=201, response_model=MappingFeature, response_description="The stored report, pending")
    def report_mapping(report: MappingReport, request: Request):
        stored = reports.report_mapping(report.kind, (report.lon, report.lat), report.reporter_id, client(request),
                                        report.osm_way_id, report.note)
        return mapping_feature(stored)

    @app.get("/reports/mapping", tags=[REPORTS], summary="Riders' mapping reports, as GeoJSON points",
             response_class=GeoJSONResponse, response_model=MappingCollection)
    def mapping(status: Literal["pending", "approved", "rejected", "all"] = Query(
            "pending", description="Only reports with this status")):
        return GeoJSONResponse({"type": "FeatureCollection",
                                "features": [mapping_feature(r) for r in reports.mapping_reports(status)]})

    @app.get("/sharing/geofencing", tags=[SHARING], summary="Where shared vehicles may be left: the provider's geofencing zones",
             response_class=GeoJSONResponse, response_model=GeofencingCollection, responses=SHARING_ERRORS,
             response_description="Polygons in feed order (an earlier zone wins where zones overlap) with the end rule per vehicle kind")
    def sharing_geofencing():
        """Dott's no-parking zones (pedestrian zones, parks, ...), zones where vehicles may only be left at a parking
        zone, exceptions inside them, and last its whole Heilbronn area, where a ride may end anywhere."""
        return GeoJSONResponse(shared("geofencing", (None, None)))

    app.include_router(users_router)
    return app


app = create_app()

"""GeoJSON response shapes, so /docs shows what the endpoints return, and the request bodies of the reports."""
from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

LonLat = tuple[float, float]  # GeoJSON order: [longitude, latitude]

# The example trip from the README (query order: lat, lon). The examples below are what the API
# returns for it with the default penalties; tests/test_heilbronn.py checks they still match.
EXAMPLE_TRIP = {"from_lat": 49.14838, "from_lon": 9.22687, "to_lat": 49.1262, "to_lon": 9.22439}
ROUTE_EXAMPLE = {
    "type": "Feature",
    # Shortened: the real line has 160 points.
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2227619, 49.139049], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 2, "danger_penalty": 10.0, "pm_penalty": 1, "stop_penalty": 1, "prefer_time": False,
        "shade_penalty": 2, "dark_penalty": 4, "prefer_bike_friendly": 0, "depart_time": None, "daylight": None, "shade_slot": None,
        "length_m": 3257.1, "duration_s": 959, "climb_m": 26.2, "kcal": 147.6, "speed_measured_share": 0.89, "mean_roughness": 12.4, "measured_share": 0.88, "estimated_share": 0.0,
        "danger_points": 11, "danger_risk": 9.0, "mean_pm_risk": 0.506, "pm_measured_share": 0.63,
        "mean_stop_go": 0.68, "stop_measured_share": 0.89,
        "mean_shade": None, "shade_known_share": 0.95, "mean_lit": 0.986, "lit_known_share": 0.89, "lifts": 0,
        "reported_closures": 0,
        "bumpy_m": 202, "bad_air_m": 292, "stop_go_m": 379, "sunny_m": None, "unlit_m": None, "bike_friendly_m": 1160, "pushed_m": 0,
        # Shortened: the real route has 44 stretches.
        "segments": [
            {"from_index": 0, "to_index": 4, "start_m": 0.0, "length_m": 36.4, "name": "Kleiststraße", "way": None, "along": False, "flags": [], "roughness": 11.833, "danger_points": 0, "pm_risk": 0.494, "stop_go": 0.652, "speed_kmh": 14.495, "shade": None, "lit": 1.0, "bike_friendly": False, "pushed": False, "segments": ["1214835654-11925390607", "26890921-1214835654"]},
            {"from_index": 4, "to_index": 7, "start_m": 36.4, "length_m": 36.2, "name": "Sichererstraße", "way": None, "along": False, "flags": ["bike_friendly_m"], "roughness": 9.485, "danger_points": 0, "pm_risk": 0.507, "stop_go": 0.636, "speed_kmh": 13.248, "shade": None, "lit": 1.0, "bike_friendly": True, "pushed": False, "segments": ["26890921-1214745069", "1214745069-1216889477", "1028721133-1216889477"]},
        ],
    },
}
SHORTEST_EXAMPLE = {
    "type": "Feature",
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2294832, 49.1399564], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0, "prefer_time": False,
        "shade_penalty": 0, "dark_penalty": 0, "prefer_bike_friendly": 0, "depart_time": None, "daylight": None, "shade_slot": None,
        "length_m": 3061.2, "duration_s": 940, "climb_m": 30.7, "kcal": 148.8, "speed_measured_share": 0.97, "mean_roughness": 24.7, "measured_share": 0.97, "estimated_share": 0.02,
        "danger_points": 10, "danger_risk": 7.94, "mean_pm_risk": 0.524, "pm_measured_share": 0.75,
        "mean_stop_go": 0.665, "stop_measured_share": 0.97,
        "mean_shade": None, "shade_known_share": 1.0, "mean_lit": 0.93, "lit_known_share": 0.99, "lifts": 0,
        "reported_closures": 0,
        "bumpy_m": 1895, "bad_air_m": 733, "stop_go_m": 481, "sunny_m": None, "unlit_m": None, "bike_friendly_m": 874, "pushed_m": 0,
        # Shortened: the real route has 35 stretches.
        "segments": [
            {"from_index": 0, "to_index": 4, "start_m": 0.0, "length_m": 36.4, "name": "Kleiststraße", "way": None, "along": False, "flags": [], "roughness": 11.833, "danger_points": 0, "pm_risk": 0.494, "stop_go": 0.652, "speed_kmh": 14.495, "shade": None, "lit": 1.0, "bike_friendly": False, "pushed": False, "segments": ["1214835654-11925390607", "26890921-1214835654"]},
            {"from_index": 4, "to_index": 11, "start_m": 36.4, "length_m": 89.8, "name": "Sichererstraße", "way": None, "along": False, "flags": ["bike_friendly_m"], "roughness": 9.485, "danger_points": 0, "pm_risk": 0.491, "stop_go": 0.636, "speed_kmh": 13.248, "shade": None, "lit": 1.0, "bike_friendly": True, "pushed": False, "segments": ["26890921-1214835706", "1214835682-1214835706", "1214835682-1216735058", "1214835677-1216735058", "1214835597-1214835677", "1214835597-1214835623", "1214835623-1558436876"]},
        ],
    },
}

# /route/grade for the example trip, shortened to its first 2 of 14 pieces; tests/test_heilbronn.py checks them and the summary.
GRADE_EXAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
            [9.2268683, 49.148385], [9.2267631, 49.1482275], [9.2267132, 49.1481547], [9.2266937, 49.1481132],
            [9.2266865, 49.1480816], [9.2266622, 49.1480821], [9.2263651, 49.1480986], [9.2261904, 49.1481081],
            [9.2256731, 49.1481397]]},
         "properties": {"grade_pct": -0.5, "severity": "flat", "color": "#4caf50", "length_m": 110.4, "rise_m": -0.5,
                        "start_m": 0.0}},
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
            [9.2256731, 49.1481397], [9.2256235, 49.1478228], [9.225569, 49.147444], [9.2255341, 49.147208],
            [9.2255212, 49.1471208]]},
         "properties": {"grade_pct": 2.6, "severity": "gentle", "color": "#c0ca33", "length_m": 113.8, "rise_m": 3.0,
                        "start_m": 110.4}},
    ],
    "summary": {
        "length_m": 3257.1, "climb_m": 26.2, "descent_m": 8.0, "start_elevation_m": 162.7, "end_elevation_m": 180.8,
        "max_grade_pct": 4.1, "max_descent_grade_pct": -3.0,
        "length_by_severity_m": {"flat": 2851.5, "gentle": 396.0, "noticeable": 9.6, "steep": 0.0, "very_steep": 0.0},
        "kcal": 147.6,
    },
}


def collection_example(feature):
    return {"json_schema_extra": {"example": {"type": "FeatureCollection", "features": [feature]}}}


class LineString(BaseModel):
    type: Literal["LineString"]
    coordinates: list[LonLat] = Field(description="[lon, lat] pairs from start to end, following the streets")


class Point(BaseModel):
    type: Literal["Point"]
    coordinates: LonLat = Field(description="[lon, lat]")


class MultiLineString(BaseModel):
    type: Literal["MultiLineString"]
    coordinates: list[list[LonLat]] = Field(description="Lines of [lon, lat] pairs")


PLANNED_WITH = "The penalty this route was planned with, as requested (0 for the shortest route)"


Flag = Literal["bumpy_m", "danger_points", "bad_air_m", "stop_go_m", "sunny_m", "unlit_m", "bike_friendly_m"]


class RouteSegment(BaseModel):
    """A stretch of the route: consecutive streets with the same name and the same flags."""
    from_index: int = Field(description="Index in the route's coordinates where the stretch starts")
    to_index: int = Field(description="Index in the route's coordinates where it ends (inclusive)")
    start_m: float = Field(description="Distance from the start of the route to the start of the stretch, in metres")
    length_m: float = Field(description="Length of the stretch in metres")
    name: Optional[str] = Field(description=(
        "Street name from OpenStreetMap. A way without a name takes the name of the road it runs beside (along), e.g. "
        "a sidewalk or bike path, or for a crossing the road it crosses; null if there is none (a park path, a farm track)"))
    way: Optional[Literal["crossing", "sidewalk", "cycleway", "footway", "path", "track", "service", "pedestrian"]] = Field(
        description=("The kind of way, from highway=* and footway=* in OSM: service is an access road or car park; null "
                     "for an ordinary road, or for a stretch that is partly road and partly the sidewalk beside it"))
    along: bool = Field(description="True if `name` is that of the road the way runs beside or crosses, not its own")
    flags: list[Flag] = Field(description=(
        "What the stretch counts towards, named after the route totals: bumpy_m, bad_air_m and stop_go_m by the same "
        "thresholds, danger_points if it has a close-overtaking spot, sunny_m less than half in shade at shade_slot (by "
        "day), unlit_m probably unlit (lit < 0.5, after dark), bike_friendly_m on a bike path, lane or route"))
    roughness: Optional[float] = Field(description="Roughness, measured or estimated (length-weighted); null if unknown")
    danger_points: int = Field(description="Close-overtaking spots on the stretch")
    pm_risk: Optional[float] = Field(description="Air score 0-1, higher = more fine dust; null if not measured")
    stop_go: Optional[float] = Field(description="Stop-and-go 0-1, higher = more stopping; null if not measured")
    speed_kmh: Optional[float] = Field(description="Measured bike speed in km/h; null if not measured")
    shade: Optional[float] = Field(description="Share in shade at shade_slot, 0-1; null at night, without a departure or data")
    lit: Optional[float] = Field(description="Chance the street is lit at night, 0-1; null without lighting data")
    bike_friendly: bool = Field(description="On a bike path, bike lane or bike route")
    pushed: bool = Field(description="An e-scooter is pushed here (footway or pedestrian street); always false for bikes")
    segments: list[str] = Field(description=(
        "The street segments (\"u-v\", as in `/reports/closures`) the stretch rides, in riding order: the app reports "
        "them all when a rider says the stretch is closed"))


class RouteProperties(BaseModel):
    bump_penalty: float = Field(description=PLANNED_WITH)
    danger_penalty: float = Field(description=PLANNED_WITH)
    pm_penalty: float = Field(description=PLANNED_WITH)
    stop_penalty: float = Field(description=PLANNED_WITH)
    prefer_time: bool = Field(description="Whether the route was planned by riding time instead of length, as requested (false for the shortest route)")
    shade_penalty: float = Field(description=PLANNED_WITH)
    dark_penalty: float = Field(description=PLANNED_WITH)
    prefer_bike_friendly: float = Field(description="How much bike-friendly streets were preferred, as requested (0 for the shortest route)")
    depart_time: Optional[str] = Field(description="The requested depart_time in Heilbronn local time (ISO 8601), or null")
    daylight: Optional[bool] = Field(
        description="Whether the sun is up at depart_time (then shade_penalty applies, else dark_penalty); null without depart_time")
    shade_slot: Optional[str] = Field(description="The shade time slot used by day (nearest to the time of day of depart_time); null otherwise")
    length_m: float = Field(description="Route length in metres")
    duration_s: int = Field(
        description="Expected riding time in seconds from speed_map (measured cyclist speed, waits included; unmeasured streets at 15.7 km/h), lifts included")
    climb_m: Optional[float] = Field(
        description="Total height gained in metres, bridge humps included (same as `climb_m` of /route/grade); null without elevation data")
    kcal: float = Field(description=(
        "Rough energy use in kcal for riding this route (MET 6.8 for the riding time, plus the climbs), for the weight_kg "
        "rider; e_bike gives a rough pedelec estimate. When `climb_m` is null the climbs count as 0, so it is a lower bound. "
        "For an e-scooter ride (/route/sharing) only pushing it (pushed_m) counts, as walking: the motor does the riding. "
        "Show it rounded, e.g. \"about 120 kcal\". An estimate, not a measurement; see routing/calories.py"))
    speed_measured_share: float = Field(description="Share of the route length with speed_map measurements, 0-1")
    mean_roughness: Optional[float] = Field(
        description="Normalized Roughness 0-100, length-weighted over the measured part; null if none was measured")
    measured_share: float = Field(description="Share of the route length with bumpy_roads measurements, 0-1")
    estimated_share: float = Field(
        description="Share of the route length whose roughness is estimated from nearby measured streets (estimation/README.md), 0-1")
    danger_points: int = Field(description="Close-overtaking spots (danger_zones) on the route")
    danger_risk: float = Field(description="Summed Risk Index Overtaking of those spots")
    mean_pm_risk: Optional[float] = Field(
        description="Air score 0-1 from air_quality (0.5 = typical, see `/air`), length-weighted over the measured part; null if none was measured")
    pm_measured_share: float = Field(description="Share of the route length with air_quality measurements, 0-1")
    mean_stop_go: Optional[float] = Field(
        description="Stop-and-go 0-1 from traffic_flow (1 - avg_traffic_flow; higher = more slowing and stopping), length-weighted over the measured part; null if none was measured")
    stop_measured_share: float = Field(description="Share of the route length with traffic_flow measurements, 0-1")
    mean_shade: Optional[float] = Field(
        description="Share in building or tree shade at shade_slot, 0-1, length-weighted over the part with shade data; null unless by day")
    shade_known_share: float = Field(description="Share of the route length with shade data, 0-1")
    mean_lit: Optional[float] = Field(
        description="Chance the streets are lit at night, 0-1, length-weighted over the part with lighting data; null if none")
    lit_known_share: float = Field(description="Share of the route length with lighting data, 0-1")
    lifts: int = Field(description="Lifts (elevators) the route rides through, e.g. onto the Campusbrücke; each one costs stop_penalty x 25 m")
    reported_closures: int = Field(description=(
        "Streets on the route that riders reported closed, by too few to close them or without a recent report "
        "(status reported or unconfirmed in `/reports/closures`); the route still rides them, as there was no sensible "
        "way round. Worth a warning"))
    bumpy_m: int = Field(description="Metres on bumpy streets: roughness (measured or estimated) 20 or more, the worst tenth of measured street length")
    bad_air_m: int = Field(description="Metres on streets with bad air: measured air score 0.555 or more, the worst tenth of measured street length")
    stop_go_m: int = Field(description="Metres on stop-and-go streets: measured stop_go 0.77 or more, the worst tenth of measured street length")
    sunny_m: Optional[int] = Field(description="By day: metres in the sun at shade_slot (share not in shade, over the streets with shade data); null otherwise")
    unlit_m: Optional[int] = Field(description="After dark: metres on probably unlit streets (chance not lit, over the streets with lighting data); null otherwise")
    bike_friendly_m: int = Field(description="Metres on bike paths, bike lanes and bike routes (see /bike-friendly-streets)")
    pushed_m: int = Field(description="Metres an e-scooter is pushed at walking pace, on footways and pedestrian streets it must not ride on (eKFV); 0 for bikes")
    segments: list[RouteSegment] = Field(description=(
        "The route as stretches with what is measured on them, in riding order, e.g. for a tooltip when pointing at the "
        "line or to highlight where the bumpy or stop-and-go parts are"))


class RouteFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: RouteProperties


class RouteCollection(BaseModel):
    """A FeatureCollection with exactly one LineString feature: the route."""
    type: Literal["FeatureCollection"]
    features: list[RouteFeature] = Field(min_length=1, max_length=1)

    model_config = collection_example(ROUTE_EXAMPLE)


class RouteComparison(BaseModel):
    """The route next to the shortest route between the same points, e.g. to draw both and show what the penalties changed."""
    route: RouteFeature = Field(description="The route for the given penalties, as from /route")
    shortest: RouteFeature = Field(description="The shortest route: all penalties 0, prefer_time off, same depart_time")
    detour_pct: float = Field(description="How much longer the route is than the shortest route, in %")
    extra_time_pct: float = Field(description="How much longer the route takes than the shortest route (by duration_s), in %; negative if faster")
    same_path: bool = Field(description="True if the route follows the same streets as the shortest route")

    model_config = {"json_schema_extra": {"example": {
        "route": ROUTE_EXAMPLE, "shortest": SHORTEST_EXAMPLE, "detour_pct": 6.4, "extra_time_pct": 2.0, "same_path": False}}}


class DayPeriod(RouteComparison):
    """/route/compare for every departure time in [from, to)."""
    from_: str = Field(alias="from", description="First departure time of the period, HH:MM local time")
    to: str = Field(description="End of the period, HH:MM local time (23:59 for the last one)")

    model_config = {"populate_by_name": True}


class DayRoutes(BaseModel):
    """The routes of one day by departure time: by day the route can follow the shade of the time slot, after
    dark the lit streets. Consecutive periods differ in shade slot or in daylight."""
    date: str = Field(description="The day, ISO 8601 (that of depart_time, or today)")
    periods: list[DayPeriod] = Field(min_length=1, description="From 00:00 to 23:59, in order")


Severity = Literal["flat", "gentle", "noticeable", "steep", "very_steep"]


class GradeProperties(BaseModel):
    grade_pct: float = Field(description="Rise / length of this piece in %, in the travel direction: positive uphill, negative downhill")
    severity: Severity = Field(description="On the absolute grade: flat < 2 %, gentle 2-4 %, noticeable 4-6 %, steep 6-10 %, very_steep 10 % and more")
    color: str = Field(description="Suggested line colour for the severity (#rrggbb)")
    length_m: float = Field(description="Length of this piece in metres")
    rise_m: float = Field(description="Height gained over this piece in metres (negative = lost)")
    start_m: float = Field(description="Distance from the start of the route to the start of this piece, in metres")


class GradeFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: GradeProperties


class GradeSummary(BaseModel):
    length_m: float = Field(description="Route length in metres (same as /route)")
    climb_m: float = Field(description="Total height gained in metres")
    descent_m: float = Field(description="Total height lost in metres")
    start_elevation_m: float = Field(description="Height of the start above sea level (NHN) in metres")
    end_elevation_m: float = Field(description="Height of the end above sea level (NHN) in metres")
    max_grade_pct: float = Field(description="Steepest uphill street piece in % (0 if the route never climbs)")
    max_descent_grade_pct: float = Field(description="Steepest downhill street piece in %, negative (0 if it never descends)")
    length_by_severity_m: dict[Severity, float] = Field(description="Metres of the route in each severity")
    kcal: float = Field(description="Rough energy use in kcal for riding the route, for the weight_kg rider (same as `kcal` of /route)")


class GradeCollection(BaseModel):
    """The route from /route, in pieces of the same grade class. Only for display: grade is not part of the route cost,
    so this is exactly the path /route returns for the same parameters. Heights: LGL DGM1 (Datenquelle: LGL, www.lgl-bw.de, dl-de/by-2-0)."""
    type: Literal["FeatureCollection"]
    features: list[GradeFeature] = Field(min_length=1, description="Consecutive pieces from start to end; joined, they give the /route line")
    summary: GradeSummary

    model_config = {"json_schema_extra": {"example": GRADE_EXAMPLE}}


class RoughnessFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["roughness"], float] = Field(description="Normalized Roughness 0-100")


class RoughnessCollection(BaseModel):
    """Measured streets from bumpy_roads (~9,600 lines, ~2 MB)."""
    type: Literal["FeatureCollection"]
    features: list[RoughnessFeature]

    model_config = collection_example({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
        [9.2213487, 49.1495941], [9.2212358, 49.1495259]]}, "properties": {"roughness": 22.14}})


class DangerFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: dict[Literal["risk"], float] = Field(description="Risk Index Overtaking 0-1")


class DangerCollection(BaseModel):
    """Overtakes with a gap over 25 cm, the ones routing counts (~4,000 points, ~0.5 MB)."""
    type: Literal["FeatureCollection"]
    features: list[DangerFeature]

    model_config = collection_example(
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.2233647, 49.1505723]}, "properties": {"risk": 0.7235}})


class AirFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: dict[Literal["air"], float] = Field(
        description="How much worse than usual the air is, 0-1, where 0.5 is typical and higher is worse. Not an absolute PM value: "
                    "each bike reading is divided by the fine dust the senseBox:home stations measured in that hour "
                    "(so weather and the time of day drop out), then compared with the rest of the same bike trip "
                    "(so the bike sensor's own offset drops out). 1 = about 1.35x the trip's usual, 0 = as far below")


class AirCollection(BaseModel):
    """Air readings about every 20 m of every ride (~165,000 points, ~21 MB): load it only when the layer is shown."""
    type: Literal["FeatureCollection"]
    features: list[AirFeature]

    model_config = collection_example(
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.2294581, 49.1331402]}, "properties": {"air": 0.998}})


class FlowFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["stop_go"], float] = Field(
        description="1 - avg_traffic_flow, 0-1: near 0 = bikes roll freely, near 1 = slow or stop-and-go (traffic lights, congestion)")


class FlowCollection(BaseModel):
    """Measured street segments from traffic_flow (~7,000 lines, ~1.5 MB)."""
    type: Literal["FeatureCollection"]
    features: list[FlowFeature]

    model_config = collection_example({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
        [9.2213487, 49.1495941], [9.2212358, 49.1495259]]}, "properties": {"stop_go": 0.662}})


class SpeedFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["speed_kmh"], float] = Field(
        description="Mean speed bikes were measured at in km/h, waits at lights included; higher = faster")


class SpeedCollection(BaseModel):
    """Measured street segments from speed_map (~7,400 lines, ~1.6 MB)."""
    type: Literal["FeatureCollection"]
    features: list[SpeedFeature]

    model_config = collection_example({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
        [9.2213487, 49.1495941], [9.2212358, 49.1495259]]}, "properties": {"speed_kmh": 12.8}})


LINE_EXAMPLE = {"type": "LineString", "coordinates": [[9.2213487, 49.1495941], [9.2212358, 49.1495259]]}


class ShadeFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["shade"], list[float]] = Field(
        description="Share of the street in building or tree shade, 0-1, one value per entry of the collection's `slots`")


class ShadeCollection(BaseModel):
    """Bike graph streets with shade from LoD2 buildings and street trees, computed for a few hours of 21 July
    (routing.shadow). Sources: LGL BW LoD2 and Stadt Heilbronn Baumkataster, dl-de/by-2-0."""
    type: Literal["FeatureCollection"]
    slots: list[str] = Field(description="The time of each shade value, ISO 8601 local time, e.g. 2026-07-21T15:00+02:00")
    features: list[ShadeFeature]

    model_config = {"json_schema_extra": {"example": {
        "type": "FeatureCollection",
        "slots": ["2026-07-21T09:00+02:00", "2026-07-21T12:00+02:00", "2026-07-21T15:00+02:00", "2026-07-21T18:00+02:00"],
        "features": [{"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {"shade": [0.42, 0.1, 0.05, 0.31]}}]}}}


class LightingFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["lit"], float] = Field(
        description="Chance the street is lit at night, 0-1: 1/0 from OSM lit=*, else from Mapillary street lights or a road-type rule")


class LightingCollection(BaseModel):
    """Bike graph streets with street lighting (routing.lighting). Sources: OpenStreetMap contributors (ODbL),
    Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0)."""
    type: Literal["FeatureCollection"]
    features: list[LightingFeature]

    model_config = collection_example({"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {"lit": 0.96}})


class BikeFriendlyFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["osm_id"], int] = Field(description="OpenStreetMap way id")


class BikeFriendlyCollection(BaseModel):
    """Bike paths, bike lanes, bike roads and signed bike routes in Heilbronn (OSM via Overpass,
    data/custom/bike_friendly_streets_heilbronn.overpassql): the streets prefer_bike_friendly favours.
    Source: OpenStreetMap contributors (ODbL)."""
    type: Literal["FeatureCollection"]
    features: list[BikeFriendlyFeature]

    model_config = collection_example({"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {"osm_id": 4087087}})


class ScoreFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["score"], float] = Field(
        description="Overall score 0-100: the street's percentile, by length, among Heilbronn streets ranked by routing cost per "
                    "metre for the request's penalties (higher = better; 50 = median). Combines roughness, close-overtaking spots "
                    "and air-quality points snapped to the street, stop-and-go and lifts; with depart_time also sun "
                    "(by day) or no street lighting (after dark). Streets without data count at the routing defaults")


class ScoreCollection(BaseModel):
    """Every bike graph street once, with its overall score."""
    type: Literal["FeatureCollection"]
    features: list[ScoreFeature]

    model_config = collection_example({"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {"score": 72.4}})


class VehicleProperties(BaseModel):
    provider: str = Field(description="Sharing provider, e.g. Dott")
    vehicle: Literal["bike", "scooter"] = Field(description="bike (incl. cargo bikes) or scooter (e-scooter)")
    vehicle_id: str
    electric: bool = Field(description="True for e-scooters, pedelecs (pedal assist) and other electric bikes")
    battery_pct: Optional[int] = Field(description="Battery level 0-100, null if the provider doesn't say")
    range_m: Optional[float] = Field(description="Distance the battery still lasts, in metres, as the provider estimates")
    price: Optional[str] = Field(description="Price as the provider publishes it, e.g. \"€1.00 to unlock + €0.44/min\"")
    rent_url: Optional[str] = Field(description="Link that opens this vehicle in the provider's app (or its web page) to rent it")
    last_reported: Optional[str] = Field(description="When the provider last reported this vehicle (ISO 8601)")
    distance_m: Optional[int] = Field(None, description="Metres from the near_lat/near_lon point, when one was given")


class VehicleFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: VehicleProperties


SHARING_UPDATED = "When this snapshot was read from the feed (ISO 8601, UTC); it is at most a minute old unless the feed is down"
SHARING_ATTRIBUTION = "Data credit to show with the layer"


class VehicleCollection(BaseModel):
    """Shared e-bikes and e-scooters free to rent right now (live, not reserved or broken).
    Heilbronn: Dott, about 140 pedelecs and 350 e-scooters."""
    type: Literal["FeatureCollection"]
    features: list[VehicleFeature]
    updated: str = Field(description=SHARING_UPDATED)
    attribution: str = Field(description=SHARING_ATTRIBUTION)

    model_config = {"json_schema_extra": {"example": {
        "type": "FeatureCollection", "updated": "2026-10-28T15:51:58+00:00",
        "attribution": "MobiData BW (dl-de/by-2-0), sharing data by the providers",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.2131, 49.1478]}, "properties": {
            "provider": "Dott", "vehicle": "bike", "vehicle_id": "DOU:Vehicle:9909176a-3cf4-44a8-85c7-7cd6728e77dc", "electric": True,
            "battery_pct": 73, "range_m": 26800.0, "price": "€1.00 to unlock + €0.44/min",
            "rent_url": "https://go.ridedott.com/vehicles/9909176a-3cf4-44a8-85c7-7cd6728e77dc?platform=android",
            "last_reported": "2026-10-28T15:38:14.000+00:00", "distance_m": 614}}]}}}


class ZoneProperties(BaseModel):
    provider: str
    name: str
    bikes_available: int = Field(description="E-bikes parked in the zone right now, as the provider reports it (Dott "
                                             "reports every zone as full: this equals bike_capacity)")
    scooters_available: int = Field(description="E-scooters parked in the zone right now, as the provider reports it "
                                                "(Dott: equals scooter_capacity)")
    bike_capacity: Optional[int] = Field(description="How many bikes the zone is meant for, null if unknown")
    scooter_capacity: Optional[int] = Field(description="How many scooters the zone is meant for, null if unknown")
    distance_m: Optional[int] = Field(None, description="Metres from the near_lat/near_lon point, when one was given")


class ZoneFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: ZoneProperties


class ZoneCollection(BaseModel):
    """Parking zones where shared bikes and scooters are picked up and left (Dott: about 35 in Heilbronn), with live counts."""
    type: Literal["FeatureCollection"]
    features: list[ZoneFeature]
    updated: str = Field(description=SHARING_UPDATED)
    attribution: str = Field(description=SHARING_ATTRIBUTION)

    model_config = {"json_schema_extra": {"example": {
        "type": "FeatureCollection", "updated": "2026-10-28T15:51:58+00:00",
        "attribution": "MobiData BW (dl-de/by-2-0), sharing data by the providers",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.205396, 49.133834]}, "properties": {
            "provider": "Dott", "name": "Parkingzone Theresienstraße /Badstraße", "bikes_available": 5,
            "scooters_available": 5, "bike_capacity": 5, "scooter_capacity": 5}}]}}}


class PlaceProperties(BaseModel):
    label: str = Field(description="Full name with street and district, to show in a \"did you mean\" list")
    name: Optional[str] = Field(description="Short name of the place, e.g. \"Rathaus Heilbronn\"; null for a plain address")
    category: Optional[str] = Field(description="OSM category, e.g. amenity, highway, building")
    type: Optional[str] = Field(description="OSM type within the category, e.g. townhall, residential, yes")


class PlaceFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: PlaceProperties


class PlaceCollection(BaseModel):
    """Places matching the search, best first; empty if nothing in Heilbronn matches."""
    type: Literal["FeatureCollection"]
    features: list[PlaceFeature]
    attribution: str = Field(description="Data credit to show with the results")

    model_config = {"json_schema_extra": {"example": {
        "type": "FeatureCollection", "attribution": "© OpenStreetMap contributors (ODbL), search by Nominatim",
        "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.21839, 49.142788]}, "properties": {
            "label": "Rathaus Heilbronn, 7, Marktplatz, Kernstadt, Heilbronn, Baden-Württemberg, 74072, Deutschland",
            "name": "Rathaus Heilbronn", "category": "amenity", "type": "townhall"}}]}}}


class ClosureReport(BaseModel):
    """A rider's report that a street is closed right now (construction, event, ...): a `segment` the rider picked
    (from `/reports/segment` or a route stretch's `segments`), or a point, which goes to the nearest street."""
    segment: Optional[str] = Field(None, pattern=r"^\d+-\d+$", description=(
        "The street segment, \"u-v\" as in `/reports/segment`; give this or lat/lon"))
    lat: Optional[float] = Field(None, ge=-90, le=90, description=(
        "Where the street is closed, without `segment`; the report goes to the nearest street within 50 m"))
    lon: Optional[float] = Field(None, ge=-180, le=180)
    reporter_id: Optional[str] = Field(None, max_length=64, description=(
        "An anonymous random id the app keeps per device, so one rider's repeated reports count once"))
    note: Optional[str] = Field(None, max_length=500, description="What is closed, e.g. \"Baustelle, bis Freitag\"")
    until: Optional[date] = Field(None, description=(
        "The last day it is closed, if known (e.g. from the sign); the report then counts through that day "
        "(Heilbronn time), at most 30 days. Without it, the report counts for 24 h"))

    model_config = {"json_schema_extra": {"example": {"segment": "268245781-268245790", "reporter_id": "3f9c2a71",
                                                      "note": "Baustelle, Durchfahrt gesperrt", "until": "2026-11-15"}}}

    @model_validator(mode="after")
    def _where(self):
        if self.segment is None and (self.lat is None or self.lon is None):
            raise ValueError("give a segment, or lat and lon")
        return self


class ClosureAnswer(BaseModel):
    """A rider's one-tap answer on a known closure: still closed, or open again."""
    still_closed: bool = Field(description=(
        "true: still closed (counts as a new report, for 24 h); false: open again (2 independent answers lift it)"))
    reporter_id: Optional[str] = Field(None, max_length=64, description="An anonymous random id the app keeps per device")

    model_config = {"json_schema_extra": {"example": {"still_closed": True, "reporter_id": "3f9c2a71"}}}


class ClosureProperties(BaseModel):
    segment: str = Field(description="The street segment (between two junctions) as \"u-v\", its OSM node ids")
    osm_way_ids: list[int] = Field(description="The OpenStreetMap ways the segment is part of")
    status: Literal["closed", "reported", "unconfirmed", "open"] = Field(description=(
        "closed: 3 or more live independent reports, routes don't use it. reported: fewer, routes avoid it if the "
        "detour is at most 4x its length. unconfirmed: all reports have lapsed, less than 3 days ago; routes still "
        "avoid it, and the app should ask riders nearby whether it is still closed. open: only in the answer to "
        "`/confirm` or a report, when riders' answers just lifted it"))
    reports: int = Field(description=(
        "Live independent reports (different riders on different networks). A report counts through its `until` "
        "day, else 24 h; \"still closed\" answers count as reports"))
    open_reports: int = Field(description="Independent riders who said it is open again since the last report; 2 lift it")
    note: Optional[str] = Field(description="The latest reporter's note, e.g. \"Baustelle bis Freitag\"")
    last_report: str = Field(description="When the latest report or answer came in (ISO 8601, UTC)")
    expires: str = Field(description=(
        "When the last report lapses (ISO 8601, UTC); then it is unconfirmed for 3 days unless riders confirm it"))


class ClosureFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: ClosureProperties


CLOSURE_EXAMPLE = {"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {
    "segment": "268245781-268245790", "osm_way_ids": [24710470], "status": "reported", "reports": 1, "open_reports": 0,
    "note": "Baustelle, Durchfahrt gesperrt", "last_report": "2026-10-28T15:10:00+00:00",
    "expires": "2026-11-15T23:00:00+00:00"}}


class StreetSegmentProperties(BaseModel):
    segment: str = Field(description="\"u-v\", the OSM node ids at its two junctions: what `/reports/closures` takes")
    osm_way_ids: list[int] = Field(description="The OpenStreetMap ways the segment is part of")
    name: Optional[str] = Field(description=(
        "Street name; a sidewalk or bike path without one takes the name of the road beside it; null if none"))
    length_m: float
    status: Optional[Literal["closed", "reported", "unconfirmed"]] = Field(description=(
        "What riders already reported on it, as in `/reports/closures`; null if nothing"))


class StreetSegmentFeature(BaseModel):
    """The street segment (between two junctions) a click would report closed."""
    type: Literal["Feature"]
    geometry: LineString
    properties: StreetSegmentProperties

    model_config = {"json_schema_extra": {"example": {"type": "Feature", "geometry": LINE_EXAMPLE, "properties": {
        "segment": "268245781-268245790", "osm_way_ids": [24710470], "name": "Allee", "length_m": 84.2,
        "status": None}}}}


class FootwayProperties(BaseModel):
    osm_way_id: int = Field(description="The OpenStreetMap way: what a `rideable` mapping report should name")
    name: Optional[str] = Field(description="Its name in OSM, if it has one (most footways don't)")
    length_m: float


class FootwayFeature(BaseModel):
    """A footway or path routing leaves out because OSM doesn't say bikes may use it: the whole OSM way."""
    type: Literal["Feature"]
    geometry: MultiLineString
    properties: FootwayProperties

    model_config = {"json_schema_extra": {"example": {"type": "Feature", "geometry": {
        "type": "MultiLineString", "coordinates": [[[9.21998, 49.14425], [9.22051, 49.14398]]]},
        "properties": {"osm_way_id": 286359672, "name": None, "length_m": 46.3}}}}


class ClosureCollection(BaseModel):
    """Street segments riders say are closed: reported, closed, or unconfirmed (lapsed, waiting for an answer)."""
    type: Literal["FeatureCollection"]
    features: list[ClosureFeature]

    model_config = collection_example(CLOSURE_EXAMPLE)


class MappingReport(BaseModel):
    """A rider's report that the map is wrong here, e.g. a footway bikes ride on that routing leaves out."""
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    kind: Literal["rideable", "other"] = Field(description=(
        "rideable: bikes may and do ride here, but routing doesn't use it (a footway without bicycle=yes in OSM); "
        "once checked it is added to the list of rideable ways. other: any other mistake, described in note"))
    osm_way_id: Optional[int] = Field(None, gt=0, description="The OpenStreetMap way, if the app knows it")
    reporter_id: Optional[str] = Field(None, max_length=64, description="An anonymous random id the app keeps per device")
    note: Optional[str] = Field(None, max_length=500, description="What is wrong; why bikes may ride here")

    model_config = {"json_schema_extra": {"example": {
        "lat": 49.14425, "lon": 9.21998, "kind": "rideable", "osm_way_id": 286359672, "reporter_id": "3f9c2a71",
        "note": "Footway beside the tram lane, signed for bikes (Zeichen 240)"}}}


class MappingProperties(BaseModel):
    id: int
    kind: Literal["rideable", "other"]
    osm_way_id: Optional[int] = Field(description="The OpenStreetMap way, if given (or set by the maintainer who approved it)")
    note: Optional[str]
    status: Literal["pending", "approved", "rejected"] = Field(description=(
        "pending until a maintainer checks it; an approved rideable way is routed from the next server start"))
    created: str = Field(description="ISO 8601, UTC")
    resolved: Optional[str] = Field(description="When it was approved or rejected (ISO 8601, UTC)")


class MappingFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: MappingProperties


class MappingCollection(BaseModel):
    """Riders' reports of mapping mistakes."""
    type: Literal["FeatureCollection"]
    features: list[MappingFeature]

    model_config = collection_example({"type": "Feature", "geometry": {"type": "Point", "coordinates": [9.21998, 49.14425]},
                                       "properties": {"id": 7, "kind": "rideable", "osm_way_id": 286359672,
                                                      "note": "Footway beside the tram lane, signed for bikes",
                                                      "status": "pending", "created": "2026-10-28T15:10:00+00:00",
                                                      "resolved": None}})


EndRule = Literal["anywhere", "parking_zone", "no"]


class GeofencingProperties(BaseModel):
    provider: str
    name: Optional[str] = Field(description="The zone's name, if the provider gives one (Dott: only its whole area)")
    order: int = Field(description="Position in the provider's feed: where zones overlap, the lowest order decides")
    bike: Optional[EndRule] = Field(None, description="Where an e-bike ride may end in this zone: anywhere, only at a parking zone, or not at all; null if the zone has no rule for e-bikes")
    scooter: Optional[EndRule] = Field(None, description="The same for e-scooters")


class GeofencingFeature(BaseModel):
    type: Literal["Feature"]
    geometry: dict = Field(description="GeoJSON Polygon or MultiPolygon")
    properties: GeofencingProperties


class GeofencingCollection(BaseModel):
    """The provider's geofencing zones in feed order, from the saved copy (python -m backend.sharing): they change
    rarely. Outside every zone a ride may not end."""
    type: Literal["FeatureCollection"]
    features: list[GeofencingFeature]
    updated: str = Field(description=SHARING_UPDATED)
    attribution: str = Field(description=SHARING_ATTRIBUTION)


class ReturnPointProperties(BaseModel):
    rule: Literal["anywhere", "parking_zone"] = Field(description="Left where free parking is allowed, or at a parking zone")
    at_destination: bool = Field(description="True when the vehicle can be left at the destination itself")
    name: Optional[str] = Field(description="The parking zone's name, null elsewhere")


class ReturnPoint(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: ReturnPointProperties


class WalkProperties(BaseModel):
    mode: Literal["walk"]
    length_m: float = Field(description="Walking distance in metres")
    duration_s: int = Field(description="Walking time in seconds at 4.8 km/h")
    kcal: float = Field(description="Rough energy use in kcal for the walk (MET 3.5, climbs not counted), for the weight_kg rider")


class WalkFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: WalkProperties


class RideProperties(RouteProperties):
    mode: Literal["bike", "scooter"] = Field(description=(
        "Ridden on the rented e-bike or e-scooter. `kcal` is for a pedelec when the bike is electric; on an e-scooter "
        "it counts only pushing it, as walking"))


class RideFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: RideProperties


class SharingTrip(BaseModel):
    """Walk to a free shared vehicle, ride it to the end (or, where the end is a no-parking zone, to the nearest place
    it may be left), walk to the end. The walks follow OSM's
    walking network (pavements, footways, pedestrian zones; no bike paths), the ride the bike graph with the request's
    penalties, as /route; an e-scooter is pushed on footways and in pedestrian zones (pushed_m)."""
    vehicle: VehicleFeature = Field(description="The vehicle to rent, as from /sharing")
    zone: Optional[ZoneFeature] = Field(description="The parking zone the ride ends at; null when it ends elsewhere")
    return_point: ReturnPoint = Field(description="Where to leave the vehicle")
    legs: list[Union[WalkFeature, RideFeature]] = Field(min_length=3, max_length=3, description="Walk, ride, walk")
    duration_s: int = Field(description="Walking plus riding time in seconds (not counting unlocking)")
    walk_m: float = Field(description="Metres walked, both walks")
    ride_m: float = Field(description="Metres ridden")
    ride_s: int = Field(description="Riding time in seconds, what the per-minute price applies to")
    kcal: float = Field(description="Rough energy use in kcal for the whole trip: both walks and the ride, for the weight_kg rider")
    updated: str = Field(description=SHARING_UPDATED)
    attribution: str = Field(description=SHARING_ATTRIBUTION)


class Error(BaseModel):
    detail: str = Field(description="What went wrong, readable enough to show to the user")

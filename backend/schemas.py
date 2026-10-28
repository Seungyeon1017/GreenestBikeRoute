"""GeoJSON response shapes, so /docs shows what the endpoints return. Only used for the OpenAPI schema."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

LonLat = tuple[float, float]  # GeoJSON order: [longitude, latitude]

# The example trip from the README (query order: lat, lon). The examples below are what the API
# returns for it with the default penalties; tests/test_heilbronn.py checks they still match.
EXAMPLE_TRIP = {"from_lat": 49.14838, "from_lon": 9.22687, "to_lat": 49.1262, "to_lon": 9.22439}
ROUTE_EXAMPLE = {
    "type": "Feature",
    # Shortened: the real line has 157 points.
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2228294, 49.1386103], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 10.0, "danger_penalty": 25.0, "pm_penalty": 0.5, "stop_penalty": 0.5, "prefer_time": False,
        "shade_penalty": 0.5, "dark_penalty": 1.0, "depart_time": None, "daylight": None, "shade_slot": None,
        "length_m": 3088.2, "duration_s": 940, "speed_measured_share": 0.97, "mean_roughness": 12.3, "measured_share": 0.97, "estimated_share": 0.0,
        "danger_points": 21, "danger_risk": 17.12, "mean_pm_risk": 0.511, "pm_measured_share": 0.65,
        "mean_stop_go": 0.691, "stop_measured_share": 0.97,
        "mean_shade": None, "shade_known_share": 1.0, "mean_lit": 0.986, "lit_known_share": 0.97, "lifts": 0,
    },
}
SHORTEST_EXAMPLE = {
    "type": "Feature",
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2294832, 49.1399564], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0, "prefer_time": False,
        "shade_penalty": 0, "dark_penalty": 0, "depart_time": None, "daylight": None, "shade_slot": None,
        "length_m": 3061.2, "duration_s": 940, "speed_measured_share": 0.97, "mean_roughness": 24.7, "measured_share": 0.97, "estimated_share": 0.02,
        "danger_points": 10, "danger_risk": 7.94, "mean_pm_risk": 0.524, "pm_measured_share": 0.75,
        "mean_stop_go": 0.665, "stop_measured_share": 0.97,
        "mean_shade": None, "shade_known_share": 1.0, "mean_lit": 0.93, "lit_known_share": 0.99, "lifts": 0,
    },
}

# /route/grade for the example trip, shortened to its first 2 of 12 pieces; tests/test_heilbronn.py checks them and the summary.
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
        "length_m": 3088.2, "climb_m": 24.6, "descent_m": 6.4, "start_elevation_m": 162.7, "end_elevation_m": 180.8,
        "max_grade_pct": 4.1, "max_descent_grade_pct": -3.0,
        "length_by_severity_m": {"flat": 2735.3, "gentle": 343.3, "noticeable": 9.6, "steep": 0.0, "very_steep": 0.0},
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


PLANNED_WITH = "The penalty this route was planned with, as requested (0 for the shortest route)"


class RouteProperties(BaseModel):
    bump_penalty: float = Field(description=PLANNED_WITH)
    danger_penalty: float = Field(description=PLANNED_WITH)
    pm_penalty: float = Field(description=PLANNED_WITH)
    stop_penalty: float = Field(description=PLANNED_WITH)
    prefer_time: bool = Field(description="Whether the route was planned by riding time instead of length, as requested (false for the shortest route)")
    shade_penalty: float = Field(description=PLANNED_WITH)
    dark_penalty: float = Field(description=PLANNED_WITH)
    depart_time: Optional[str] = Field(description="The requested depart_time in Heilbronn local time (ISO 8601), or null")
    daylight: Optional[bool] = Field(
        description="Whether the sun is up at depart_time (then shade_penalty applies, else dark_penalty); null without depart_time")
    shade_slot: Optional[str] = Field(description="The shade time slot used by day (nearest to the time of day of depart_time); null otherwise")
    length_m: float = Field(description="Route length in metres")
    duration_s: int = Field(
        description="Expected riding time in seconds from speed_map (measured cyclist speed, waits included; unmeasured streets at 15.7 km/h), lifts included")
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
    lifts: int = Field(description="Lifts (elevators) the route rides through, e.g. onto the Campusbrücke; each one costs stop_penalty x 100 m")


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
        "route": ROUTE_EXAMPLE, "shortest": SHORTEST_EXAMPLE, "detour_pct": 0.9, "extra_time_pct": 0.0, "same_path": False}}}


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
    bikes_available: int = Field(description="E-bikes parked in the zone right now")
    scooters_available: int = Field(description="E-scooters parked in the zone right now")
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


class Error(BaseModel):
    detail: str = Field(description="What went wrong, readable enough to show to the user")

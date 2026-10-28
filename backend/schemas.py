"""GeoJSON response shapes, so /docs shows what the endpoints return. Only used for the OpenAPI schema."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

LonLat = tuple[float, float]  # GeoJSON order: [longitude, latitude]

# The example trip from the README (query order: lat, lon). The examples below are what the API
# returns for it with the default penalties; tests/test_heilbronn.py checks they still match.
EXAMPLE_TRIP = {"from_lat": 49.14838, "from_lon": 9.22687, "to_lat": 49.1262, "to_lon": 9.22439}
ROUTE_EXAMPLE = {
    "type": "Feature",
    # Shortened: the real line has 156 points.
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2228294, 49.1386103], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 10.0, "danger_penalty": 25.0, "pm_penalty": 0.5, "stop_penalty": 0.5,
        "length_m": 3117.2, "mean_roughness": 12.2, "measured_share": 0.91,
        "danger_points": 21, "danger_risk": 17.12, "mean_pm_risk": 0.533, "pm_measured_share": 0.66,
        "mean_stop_go": 0.693, "stop_measured_share": 0.92, "lifts": 0,
    },
}
SHORTEST_EXAMPLE = {
    "type": "Feature",
    "geometry": {"type": "LineString",
                 "coordinates": [[9.2268683, 49.148385], [9.2294832, 49.1399564], [9.2243909, 49.1262013]]},
    "properties": {
        "bump_penalty": 0, "danger_penalty": 0, "pm_penalty": 0, "stop_penalty": 0,
        "length_m": 3061.2, "mean_roughness": 24.7, "measured_share": 0.97,
        "danger_points": 10, "danger_risk": 7.94, "mean_pm_risk": 0.604, "pm_measured_share": 0.77,
        "mean_stop_go": 0.665, "stop_measured_share": 0.97, "lifts": 0,
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
    length_m: float = Field(description="Route length in metres")
    mean_roughness: Optional[float] = Field(
        description="Normalized Roughness 0-100, length-weighted over the measured part; null if none was measured")
    measured_share: float = Field(description="Share of the route length with bumpy_roads measurements, 0-1")
    danger_points: int = Field(description="Close-overtaking spots (danger_zones) on the route")
    danger_risk: float = Field(description="Summed Risk Index Overtaking of those spots")
    mean_pm_risk: Optional[float] = Field(
        description="Air rank 0-1 from air_quality (0.5 = typical for its ride), length-weighted over the measured part; null if none was measured")
    pm_measured_share: float = Field(description="Share of the route length with air_quality measurements, 0-1")
    mean_stop_go: Optional[float] = Field(
        description="Stop-and-go 0-1 from traffic_flow (1 - avg_traffic_flow; higher = more slowing and stopping), length-weighted over the measured part; null if none was measured")
    stop_measured_share: float = Field(description="Share of the route length with traffic_flow measurements, 0-1")
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
    shortest: RouteFeature = Field(description="The shortest route: all penalties 0")
    detour_pct: float = Field(description="How much longer the route is than the shortest route, in %")
    same_path: bool = Field(description="True if the route follows the same streets as the shortest route")

    model_config = {"json_schema_extra": {"example": {
        "route": ROUTE_EXAMPLE, "shortest": SHORTEST_EXAMPLE, "detour_pct": 1.8, "same_path": False}}}


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
        description="How much worse than usual the air is, 0-1: compared with the rest of the same bike trip, where 0.5 is typical and higher is worse. Not an absolute PM value")


class AirCollection(BaseModel):
    """Air readings about every 20 m of every ride (~166,000 points, ~21 MB): load it only when the layer is shown."""
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


class Error(BaseModel):
    detail: str = Field(description="What went wrong, readable enough to show to the user")

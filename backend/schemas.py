"""GeoJSON response shapes, so /docs shows what the endpoints return. Only used for the OpenAPI schema."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

LonLat = tuple[float, float]  # GeoJSON order: [longitude, latitude]


class LineString(BaseModel):
    type: Literal["LineString"]
    coordinates: list[LonLat] = Field(description="[lon, lat] pairs from start to end, following the streets")


class Point(BaseModel):
    type: Literal["Point"]
    coordinates: LonLat


class RouteProperties(BaseModel):
    bump_penalty: float
    danger_penalty: float
    pm_penalty: float
    stop_penalty: float
    length_m: float
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


class RouteFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: RouteProperties


class RouteCollection(BaseModel):
    """A FeatureCollection with exactly one LineString feature: the route."""
    type: Literal["FeatureCollection"]
    features: list[RouteFeature] = Field(min_length=1, max_length=1)

    model_config = {"json_schema_extra": {"example": {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[9.22687, 49.14838], [9.2259, 49.1371], [9.22439, 49.1262]]},
            "properties": {
                "bump_penalty": 10, "danger_penalty": 25, "pm_penalty": 0.5, "stop_penalty": 0.5,
                "length_m": 3331.9, "mean_roughness": 12.5, "measured_share": 0.96,
                "danger_points": 15, "danger_risk": 13.42, "mean_pm_risk": 0.492, "pm_measured_share": 0.7,
                "mean_stop_go": 0.62, "stop_measured_share": 0.81,
            },
        }],
    }}}


class RouteComparison(BaseModel):
    """The route next to the shortest route between the same points, e.g. to draw both and show what the penalties changed."""
    route: RouteFeature = Field(description="The route for the given penalties, as from /route")
    shortest: RouteFeature = Field(description="The shortest route: all penalties 0")
    detour_pct: float = Field(description="How much longer the route is than the shortest route, in %")
    same_path: bool = Field(description="True if the route follows the same streets as the shortest route")


class RoughnessFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["roughness"], float] = Field(description="Normalized Roughness 0-100")


class RoughnessCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[RoughnessFeature]


class DangerFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: dict[Literal["risk"], float] = Field(description="Risk Index Overtaking 0-1")


class DangerCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[DangerFeature]


class AirFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Point
    properties: dict[Literal["air"], float] = Field(
        description="How much worse than usual the air is, 0-1: compared with the rest of the same bike trip, where 0.5 is typical and higher is worse. Not an absolute PM value")


class AirCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[AirFeature]


class FlowFeature(BaseModel):
    type: Literal["Feature"]
    geometry: LineString
    properties: dict[Literal["stop_go"], float] = Field(
        description="1 - avg_traffic_flow, 0-1: near 0 = bikes roll freely, near 1 = slow or stop-and-go (traffic lights, congestion)")


class FlowCollection(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[FlowFeature]


class Error(BaseModel):
    detail: str

"""Request and response shapes (Pydantic) for the users endpoints. Separate from the database tables in models.py."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from routing.costs import DEFAULT_BUMP_PENALTY, DEFAULT_DANGER_PENALTY, DEFAULT_DARK_PENALTY, DEFAULT_PM_PENALTY,     DEFAULT_PREFER_BIKE_FRIENDLY, DEFAULT_SHADE_PENALTY, DEFAULT_STOP_PENALTY, MAX_POINTS


class UserCreate(BaseModel):
    """Body of POST /users (sign-up)."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description="At least 8 characters")
    display_name: str | None = Field(None, max_length=100)

    model_config = {"json_schema_extra": {"example": {
        "email": "anna@example.com", "password": "a-long-password", "display_name": "Anna"}}}


class UserOut(BaseModel):
    """A user as the API returns it: never with the password hash."""
    # Lets FastAPI build this from a SQLAlchemy User object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str | None
    created_at: datetime


class Token(BaseModel):
    """Response of POST /auth/login. Send it back as the header `Authorization: Bearer <access_token>`."""
    access_token: str
    token_type: Literal["bearer"] = "bearer"



class RouteOptions(BaseModel):
    """The settings a route was planned with. Same names, limits and defaults as the query
    parameters of /route/compare (penalty_query in backend/app.py), taken from routing/costs.py
    so they stay in step when the routing team changes them."""
    model_config = ConfigDict(extra="forbid")  # a misspelled option is an error, not silently dropped

    bump_penalty: float = Field(DEFAULT_BUMP_PENALTY, ge=0, le=MAX_POINTS)
    danger_penalty: float = Field(DEFAULT_DANGER_PENALTY, ge=0, le=100)
    pm_penalty: float = Field(DEFAULT_PM_PENALTY, ge=0, le=MAX_POINTS)
    stop_penalty: float = Field(DEFAULT_STOP_PENALTY, ge=0, le=MAX_POINTS)
    prefer_bike_friendly: float = Field(DEFAULT_PREFER_BIKE_FRIENDLY, ge=0, le=MAX_POINTS)
    prefer_time: bool = False
    shade_penalty: float = Field(DEFAULT_SHADE_PENALTY, ge=0, le=MAX_POINTS)
    dark_penalty: float = Field(DEFAULT_DARK_PENALTY, ge=0, le=MAX_POINTS)
    depart_time: str | None = Field(None, max_length=40, description="e.g. 2026-07-21T15:00, or null")


class SavedRouteCreate(BaseModel):
    """Body of POST /users/me/routes."""
    start_lon: float = Field(ge=-180, le=180)
    start_lat: float = Field(ge=-90, le=90)
    start_label: str | None = Field(None, max_length=200)
    end_lon: float = Field(ge=-180, le=180)
    end_lat: float = Field(ge=-90, le=90)
    end_label: str | None = Field(None, max_length=200)
    options: RouteOptions = Field(default_factory=RouteOptions)
    length_m: float | None = Field(None, ge=0)
    duration_s: int | None = Field(None, ge=0)

    model_config = {"json_schema_extra": {"example": {
        "start_lon": 9.21839, "start_lat": 49.14279, "start_label": "Rathaus Heilbronn",
        "end_lon": 9.2353, "end_lat": 49.1462, "end_label": "Pfühlpark",
        "options": {"bump_penalty": 2, "danger_penalty": 10, "prefer_time": False},
        "length_m": 1850.4, "duration_s": 520}}}


class SavedRouteOut(SavedRouteCreate):
    """A saved route as the API returns it."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime

# --- Riders' leisure routes (community_routes.py) -------------------------------------------------------------------

# The tags a rider can give a route; the app translates them.
RouteTag = Literal["family", "view", "quiet", "river", "nature", "gravel"]


class TrackPreview(BaseModel):
    """Response of POST /community-routes/preview: the ride as it would be published."""
    coordinates: list[list[float]] = Field(description="[lon, lat] points, without the first and last 200 m")
    length_m: float = Field(description="Length of the published line")
    moving_s: int = Field(description="How long the recorded ride took while moving")
    recorded_on: date = Field(description="The day of the ride (Heilbronn time)")
    creator: str | None = Field(description="The app that wrote the file, from GPX `creator`")
    is_loop: bool = Field(description="The ride ends near where it started")


class CommunityRouteSummary(BaseModel):
    """A route in the list: everything but the full line."""
    id: int
    name: str
    description: str
    tags: list[str]
    author: str | None = Field(description="The author's display name, or null")
    length_m: float
    moving_s: int
    recorded_on: date
    creator: str | None
    is_loop: bool
    start: list[float] = Field(description="[lon, lat] where the published line starts")
    preview: list[list[float]] = Field(description="At most 40 [lon, lat] points, to draw the route's shape small")
    hearts: int
    hearted: bool = Field(description="The logged-in rider hearted it (false when logged out)")
    saved: bool = Field(description="The logged-in rider saved it (false when logged out)")
    mine: bool = Field(description="The logged-in rider published it")
    status: Literal["published", "hidden", "removed"] = Field(
        description="Only the author sees routes that aren't published: hidden after riders flagged it, removed by a "
                    "maintainer")
    created_at: datetime


class CommunityRoute(CommunityRouteSummary):
    """GET /community-routes/{id}: a route with its whole line."""
    coordinates: list[list[float]] = Field(description="[lon, lat] points of the ride")


class CommunityRouteList(BaseModel):
    routes: list[CommunityRouteSummary]
    total: int = Field(description="How many routes match, for paging with offset")


class HeartState(BaseModel):
    hearts: int
    hearted: bool


class FlagBody(BaseModel):
    reason: str | None = Field(None, max_length=300, description="What is wrong with it, for the maintainer")

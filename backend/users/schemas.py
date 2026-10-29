"""Request and response shapes (Pydantic) for the users endpoints. Separate from the database tables in models.py."""
from datetime import datetime
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
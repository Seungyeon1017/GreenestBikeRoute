"""Request and response shapes (Pydantic) for the users endpoints. Separate from the database tables in models.py."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    """The settings a route was planned with. Same names and limits as the query parameters
    of /route/compare (backend/app.py), so the frontend can send them back unchanged."""
    model_config = ConfigDict(extra="forbid")  # a misspelled option is an error, not silently dropped

    bump_penalty: float = Field(10, ge=0, le=50)
    danger_penalty: float = Field(25, ge=0, le=100)
    pm_penalty: float = Field(0.5, ge=0, le=5)
    stop_penalty: float = Field(0.5, ge=0, le=5)
    prefer_bike_friendly: float = Field(0, ge=0, le=5)
    prefer_time: bool = False
    shade_penalty: float = Field(0.5, ge=0, le=5)
    dark_penalty: float = Field(1, ge=0, le=5)
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
        "options": {"bump_penalty": 10, "danger_penalty": 25, "prefer_time": False},
        "length_m": 1850.4, "duration_s": 520}}}


class SavedRouteOut(SavedRouteCreate):
    """A saved route as the API returns it."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
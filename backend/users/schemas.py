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
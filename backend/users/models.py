"""Database tables (SQLAlchemy). After changing one, create a migration (see migrations/README)."""
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.users.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    # Stored in lower case (see router.py), so "Anna@x.de" and "anna@x.de" are the same account.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Never the password itself: an Argon2 hash from security.hash_password().
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    # False blocks login without deleting the account.
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

        # The user's saved routes, newest first. Deleting a user deletes them too.
    saved_routes: Mapped[list["SavedRoute"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True,
        order_by="SavedRoute.id.desc()",
    )
    
    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r})"


class SavedRoute(Base):
    """A route a user saved on Plan a Trip. Only the last few are kept (see saved_routes.py).

    The route line itself isn't stored: the frontend asks /route/compare again with these
    points and options, so a reopened route always uses the current data.
    """
    __tablename__ = "saved_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # ondelete="CASCADE": the database itself removes a user's routes when the user is deleted.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    start_lon: Mapped[float]
    start_lat: Mapped[float]
    # What the search field showed, e.g. "Rathaus Heilbronn", or null for a map click.
    start_label: Mapped[str | None] = mapped_column(String(200))
    end_lon: Mapped[float]
    end_lat: Mapped[float]
    end_label: Mapped[str | None] = mapped_column(String(200))

    # The route options as sent to /route/compare (bump_penalty, prefer_time, ...).
    options: Mapped[dict[str, Any]] = mapped_column(JSON)
    # From the route when it was saved, to show in the list without asking the router again.
    length_m: Mapped[float | None]
    duration_s: Mapped[int | None]

    user: Mapped[User] = relationship(back_populates="saved_routes")

    def __repr__(self) -> str:
        return f"SavedRoute(id={self.id}, user_id={self.user_id})"


class CommunityRoute(Base):
    """A leisure route a rider recorded with another app and published for everyone (see community_routes.py).

    The line is the rider's own GPX track (gpx.py), trimmed at both ends and simplified; it is not routed again.
    """
    __tablename__ = "community_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # From community_routes.ROUTE_TAGS, e.g. ["family", "river"]. JSONB so the list can be filtered by tag.
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")

    # [[lon, lat], ...] of the track.
    coordinates: Mapped[list[list[float]]] = mapped_column(JSON)
    length_m: Mapped[float]
    # How long the recorded ride took while moving.
    moving_s: Mapped[int]
    recorded_on: Mapped[date]
    # The app that wrote the GPX file, e.g. "StravaGPX".
    creator: Mapped[str | None] = mapped_column(String(100))

    # "published" (everyone sees it), "hidden" (riders flagged it; waits for a maintainer) or "removed" (by a
    # maintainer). Only its author sees a route that isn't published.
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published", index=True)
    # How many riders hearted it, kept here so the list can be sorted by it.
    hearts: Mapped[int] = mapped_column(default=0, server_default="0")

    user: Mapped[User] = relationship()

    def __repr__(self) -> str:
        return f"CommunityRoute(id={self.id}, name={self.name!r})"


class RouteHeart(Base):
    """A rider likes a community route. One per rider and route."""
    __tablename__ = "community_route_hearts"

    route_id: Mapped[int] = mapped_column(ForeignKey("community_routes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RouteBookmark(Base):
    """A rider saved a community route to find it again on the Profile tab."""
    __tablename__ = "community_route_bookmarks"

    route_id: Mapped[int] = mapped_column(ForeignKey("community_routes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RouteFlag(Base):
    """A rider says a community route doesn't belong here (offensive name, not a bike route, ...)."""
    __tablename__ = "community_route_flags"

    route_id: Mapped[int] = mapped_column(ForeignKey("community_routes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

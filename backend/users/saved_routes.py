"""Saved routes of the logged-in user: save, list, delete. Only the newest MAX_SAVED_ROUTES are kept.

router.py includes this router, so backend/app.py doesn't need to change.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.users.database import get_db
from backend.users.models import SavedRoute
from backend.users.schemas import SavedRouteCreate, SavedRouteOut
from backend.users.security import CurrentUser

# How many routes each user keeps. Saving one more deletes the oldest.
MAX_SAVED_ROUTES = 3

router = APIRouter(prefix="/users/me/routes", tags=["Saved routes"])

DB = Annotated[Session, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SavedRouteOut,
             summary=f"Save a route (keeps the newest {MAX_SAVED_ROUTES})",
             responses={401: {"description": "Not logged in"}})
def save_route(body: SavedRouteCreate, user: CurrentUser, db: DB) -> SavedRoute:
    route = SavedRoute(user_id=user.id, **body.model_dump(exclude={"options"}),
                       options=body.options.model_dump())
    db.add(route)
    db.flush()  # gives the new route its id before the clean-up below

    # Delete this user's routes beyond the newest MAX_SAVED_ROUTES. Ids only grow, so the
    # highest ids are the newest (more reliable than created_at, which can tie).
    keep = select(SavedRoute.id).where(SavedRoute.user_id == user.id) \
        .order_by(SavedRoute.id.desc()).limit(MAX_SAVED_ROUTES)
    db.execute(delete(SavedRoute).where(SavedRoute.user_id == user.id, SavedRoute.id.not_in(keep)))

    db.commit()
    db.refresh(route)
    return route


@router.get("", response_model=list[SavedRouteOut], summary="The logged-in user's saved routes, newest first",
            responses={401: {"description": "Not logged in"}})
def list_routes(user: CurrentUser, db: DB) -> list[SavedRoute]:
    query = select(SavedRoute).where(SavedRoute.user_id == user.id).order_by(SavedRoute.id.desc())
    return list(db.scalars(query))


@router.delete("/{route_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved route",
               responses={401: {"description": "Not logged in"},
                          404: {"description": "No such route among this user's routes"}})
def delete_route(route_id: int, user: CurrentUser, db: DB) -> Response:
    route = db.get(SavedRoute, route_id)
    # Someone else's route answers 404 too, so ids of other users' routes aren't revealed.
    if route is None or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Saved route not found")
    db.delete(route)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
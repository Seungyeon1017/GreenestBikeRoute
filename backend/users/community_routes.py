"""Riders' leisure routes: rides a rider recorded with another app (GPX, see gpx.py) and published for everyone.

Publishing needs an account; browsing doesn't. A route is visible right away. Riders can heart it (the list puts the
most hearted first), save it to their Profile, or flag it: FLAGS_TO_HIDE flags from different accounts hide it until a
maintainer checks it. Blocking an account (users.is_active = False) hides all its routes.

    python -m backend.users.community_routes list --status hidden
    python -m backend.users.community_routes show 7      # publish again and forget its flags
    python -m backend.users.community_routes hide 7      # remove it (its author still sees it, as removed)

router.py includes this router, so backend/app.py doesn't need to change.
"""
import argparse
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.users import gpx
from backend.users.database import get_db, get_session_factory
from backend.users.models import CommunityRoute, RouteBookmark, RouteFlag, RouteHeart, User
from backend.users.schemas import CommunityRoute as CommunityRouteOut, CommunityRouteList, CommunityRouteSummary, \
    FlagBody, HeartState, RouteTag, TrackPreview
from backend.users.security import CurrentUser, OptionalUser

FLAGS_TO_HIDE = 3       # flags from different accounts that hide a route until a maintainer checks it
MAX_PER_DAY = 5         # routes one account may publish in 24 hours
MAX_TAGS = 4

router = APIRouter(tags=["Riders' routes"])

DB = Annotated[Session, Depends(get_db)]

NOT_FOUND = {404: {"description": "No such route, or it isn't published"}}
LOGIN = {401: {"description": "Not logged in"}}
GPX_ERRORS = {400: {"description": "The file isn't a recorded bike ride in the Heilbronn area. `detail` has a `code` "
                                   "(invalid, no_track, no_times, too_short, too_long, too_fast, outside, too_big) "
                                   "and a `message`"}}


async def _read_track(file: UploadFile) -> gpx.Track:
    data = await file.read(gpx.MAX_FILE_BYTES + 1)
    try:
        return gpx.read_track(data)
    except gpx.GpxError as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": str(e)}) from None


def _visible(route: CommunityRoute | None, user: User | None) -> bool:
    """Everyone sees published routes of active accounts; the author sees their own whatever its status."""
    if route is None:
        return False
    if user is not None and route.user_id == user.id:
        return True
    return route.status == "published" and route.user.is_active


def _get(db: Session, route_id: int, user: User | None) -> CommunityRoute:
    route = db.get(CommunityRoute, route_id)
    if not _visible(route, user):
        raise HTTPException(status_code=404, detail="Route not found")
    return route


def _marks(db: Session, user: User | None, ids: list[int]) -> tuple[set[int], set[int]]:
    """Which of the routes `ids` the user hearted and saved."""
    if user is None or not ids:
        return set(), set()
    hearted = set(db.scalars(select(RouteHeart.route_id).where(RouteHeart.user_id == user.id,
                                                               RouteHeart.route_id.in_(ids))))
    saved = set(db.scalars(select(RouteBookmark.route_id).where(RouteBookmark.user_id == user.id,
                                                                RouteBookmark.route_id.in_(ids))))
    return hearted, saved


def _summary(route: CommunityRoute, user: User | None, hearted: set[int], saved: set[int], full=False) -> dict:
    out = {
        "id": route.id, "name": route.name, "description": route.description, "tags": route.tags,
        "author": route.user.display_name, "length_m": route.length_m, "moving_s": route.moving_s,
        "recorded_on": route.recorded_on, "creator": route.creator, "is_loop": gpx.is_loop(route.coordinates),
        "start": route.coordinates[0], "preview": gpx.preview_line(route.coordinates), "hearts": route.hearts,
        "hearted": route.id in hearted, "saved": route.id in saved,
        "mine": user is not None and route.user_id == user.id, "status": route.status, "created_at": route.created_at,
    }
    if full:
        out["coordinates"] = route.coordinates
    return out


def _summaries(db: Session, routes: list[CommunityRoute], user: User | None) -> list[dict]:
    hearted, saved = _marks(db, user, [r.id for r in routes])
    return [_summary(r, user, hearted, saved) for r in routes]


@router.post("/community-routes/preview", response_model=TrackPreview, responses={**LOGIN, **GPX_ERRORS},
             summary="Check a GPX file and show the ride as it would be published")
async def preview(user: CurrentUser, file: Annotated[UploadFile, File(description="A recorded ride, as GPX")]) -> dict:
    """Nothing is stored. The answer is the line without its first and last 200 m (where a ride often starts: at
    home), simplified."""
    track = await _read_track(file)
    return {**track.__dict__, "is_loop": gpx.is_loop(track.coordinates)}


@router.post("/community-routes", status_code=status.HTTP_201_CREATED, response_model=CommunityRouteOut,
             summary="Publish a recorded ride as a leisure route for everyone",
             responses={**LOGIN, **GPX_ERRORS, 429: {"description": f"More than {MAX_PER_DAY} routes in 24 hours"}})
async def publish(
    user: CurrentUser, db: DB,
    file: Annotated[UploadFile, File(description="A recorded ride, as GPX (Komoot, Strava, Garmin Connect, OsmAnd, ...)")],
    name: Annotated[str, Form(min_length=3, max_length=80, description="e.g. Neckarrunde nach Lauffen")],
    description: Annotated[str, Form(max_length=500, description="What makes the ride nice")] = "",
    tags: Annotated[list[RouteTag], Form(description=f"At most {MAX_TAGS}")] = [],
) -> dict:
    name, description = name.strip(), description.strip()
    if len(name) < 3:
        raise HTTPException(status_code=422, detail="The name needs at least 3 characters")
    tags = list(dict.fromkeys(tags))
    if len(tags) > MAX_TAGS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_TAGS} tags")
    since = datetime.now(UTC) - timedelta(days=1)
    recent = db.scalar(select(func.count()).select_from(CommunityRoute)
                       .where(CommunityRoute.user_id == user.id, CommunityRoute.created_at >= since))
    if recent >= MAX_PER_DAY:
        raise HTTPException(status_code=429, detail=f"You can publish at most {MAX_PER_DAY} routes a day")
    track = await _read_track(file)

    route = CommunityRoute(user_id=user.id, name=name, description=description, tags=tags,
                           coordinates=track.coordinates, length_m=track.length_m, moving_s=track.moving_s,
                           recorded_on=track.recorded_on, creator=track.creator)
    db.add(route)
    db.commit()
    db.refresh(route)
    return _summary(route, user, set(), set(), full=True)


@router.get("/community-routes", response_model=CommunityRouteList, summary="Published leisure routes")
def list_routes(
    user: OptionalUser, db: DB,
    sort: Literal["hearts", "newest"] = Query("hearts", description="Most hearted first, or newest first"),
    tag: RouteTag | None = Query(None, description="Only routes with this tag"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
) -> dict:
    """Logged in, each route also says whether you hearted or saved it."""
    query = select(CommunityRoute).join(User).where(CommunityRoute.status == "published", User.is_active)
    if tag is not None:
        query = query.where(CommunityRoute.tags.contains([tag]))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = (CommunityRoute.hearts.desc(), CommunityRoute.id.desc()) if sort == "hearts" else (CommunityRoute.id.desc(),)
    routes = list(db.scalars(query.order_by(*order).limit(limit).offset(offset)))
    return {"routes": _summaries(db, routes, user), "total": total}


@router.get("/community-routes/{route_id}", response_model=CommunityRouteOut, responses=NOT_FOUND,
            summary="One leisure route with its whole line")
def read_route(route_id: int, user: OptionalUser, db: DB) -> dict:
    route = _get(db, route_id, user)
    hearted, saved = _marks(db, user, [route.id])
    return _summary(route, user, hearted, saved, full=True)


@router.delete("/community-routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses={**LOGIN, 404: {"description": "No such route among this user's routes"}},
               summary="Delete one of your routes")
def delete_route(route_id: int, user: CurrentUser, db: DB) -> Response:
    route = db.get(CommunityRoute, route_id)
    if route is None or route.user_id != user.id:
        raise HTTPException(status_code=404, detail="Route not found")
    db.delete(route)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _heart_state(db: Session, route: CommunityRoute, hearted: bool) -> dict:
    route.hearts = db.scalar(select(func.count()).select_from(RouteHeart).where(RouteHeart.route_id == route.id))
    db.commit()
    return {"hearts": route.hearts, "hearted": hearted}


@router.put("/community-routes/{route_id}/heart", response_model=HeartState,
            responses={**LOGIN, **NOT_FOUND, 400: {"description": "Your own route"}}, summary="Heart a route")
def heart(route_id: int, user: CurrentUser, db: DB) -> dict:
    route = _get(db, route_id, None)
    if route.user_id == user.id:
        raise HTTPException(status_code=400, detail="You can't heart your own route")
    db.execute(insert(RouteHeart).values(route_id=route.id, user_id=user.id).on_conflict_do_nothing())
    return _heart_state(db, route, True)


@router.delete("/community-routes/{route_id}/heart", response_model=HeartState, responses={**LOGIN, **NOT_FOUND},
               summary="Take your heart back")
def unheart(route_id: int, user: CurrentUser, db: DB) -> dict:
    route = _get(db, route_id, user)
    db.execute(delete(RouteHeart).where(RouteHeart.route_id == route.id, RouteHeart.user_id == user.id))
    return _heart_state(db, route, False)


@router.put("/community-routes/{route_id}/save", status_code=status.HTTP_204_NO_CONTENT,
            responses={**LOGIN, **NOT_FOUND}, summary="Save a route to your Profile")
def save(route_id: int, user: CurrentUser, db: DB) -> Response:
    route = _get(db, route_id, user)
    db.execute(insert(RouteBookmark).values(route_id=route.id, user_id=user.id).on_conflict_do_nothing())
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/community-routes/{route_id}/save", status_code=status.HTTP_204_NO_CONTENT,
               responses={**LOGIN}, summary="Remove a route from your Profile")
def unsave(route_id: int, user: CurrentUser, db: DB) -> Response:
    # Works for routes that were hidden since, so they can be cleared from the Profile.
    db.execute(delete(RouteBookmark).where(RouteBookmark.route_id == route_id, RouteBookmark.user_id == user.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/community-routes/{route_id}/flag", status_code=status.HTTP_204_NO_CONTENT,
             responses={**LOGIN, **NOT_FOUND, 400: {"description": "Your own route"}},
             summary=f"Say a route doesn't belong here ({FLAGS_TO_HIDE} flags hide it)")
def flag(route_id: int, body: FlagBody, user: CurrentUser, db: DB) -> Response:
    """One flag per account; flagging again replaces the reason."""
    route = _get(db, route_id, None)
    if route.user_id == user.id:
        raise HTTPException(status_code=400, detail="To take your own route down, delete it")
    db.execute(insert(RouteFlag).values(route_id=route.id, user_id=user.id, reason=body.reason)
               .on_conflict_do_update(index_elements=["route_id", "user_id"], set_={"reason": body.reason}))
    flags = db.scalar(select(func.count()).select_from(RouteFlag).where(RouteFlag.route_id == route.id))
    if flags >= FLAGS_TO_HIDE:
        route.status = "hidden"
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me/community-routes", response_model=list[CommunityRouteSummary], responses=LOGIN,
            summary="The routes you published, newest first, whatever their status")
def my_routes(user: CurrentUser, db: DB) -> list[dict]:
    routes = list(db.scalars(select(CommunityRoute).where(CommunityRoute.user_id == user.id)
                             .order_by(CommunityRoute.id.desc())))
    return _summaries(db, routes, user)


@router.get("/users/me/community-routes/saved", response_model=list[CommunityRouteSummary], responses=LOGIN,
            summary="The routes you saved, last saved first")
def saved_routes(user: CurrentUser, db: DB) -> list[dict]:
    """Saved routes that were hidden or removed since are left out."""
    routes = [r for r in db.scalars(select(CommunityRoute).join(RouteBookmark)
                                    .where(RouteBookmark.user_id == user.id)
                                    .order_by(RouteBookmark.created_at.desc(), CommunityRoute.id.desc()))
              if _visible(r, user)]
    return _summaries(db, routes, user)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check riders' leisure routes.")
    sub = parser.add_subparsers(dest="command", required=True)
    ls = sub.add_parser("list", help="list routes")
    ls.add_argument("--status", default="hidden", choices=["published", "hidden", "removed", "all"])
    for command, text in (("show", "publish a route again and forget its flags"), ("hide", "remove a route")):
        sub.add_parser(command, help=text).add_argument("id", type=int)
    args = parser.parse_args(argv)

    with get_session_factory()() as db:
        if args.command == "list":
            query = select(CommunityRoute).order_by(CommunityRoute.id)
            if args.status != "all":
                query = query.where(CommunityRoute.status == args.status)
            for r in db.scalars(query):
                flags = db.scalars(select(RouteFlag.reason).where(RouteFlag.route_id == r.id)).all()
                print(f"{r.id:>4} {r.status:<9} {r.length_m / 1000:5.1f} km  {r.hearts:>3} ♥  {len(flags)} flags  "
                      f"{r.user.email}  {r.name!r}  {r.description[:60]!r}")
                for reason in filter(None, flags):
                    print(f"       flag: {reason}")
            return
        route = db.get(CommunityRoute, args.id)
        if route is None:
            parser.exit(1, f"error: no route {args.id}\n")
        if args.command == "show":
            route.status = "published"
            db.execute(delete(RouteFlag).where(RouteFlag.route_id == route.id))
        else:
            route.status = "removed"
        db.commit()
        print(f"{route.status} {route.id}: {route.name}")


if __name__ == "__main__":
    main()

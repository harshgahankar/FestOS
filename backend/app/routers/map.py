"""GeoCommand API — role-scoped festival operations map.

Every operational figure is derived from the existing FestOS records via
``app.map_service``. Geography itself lives in ``map_locations`` and is only
plotted after an authorised organiser saves a real coordinate; no campus
coordinate is ever inferred from the CSV pack.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import config as C
from app import schemas
from app.audit import log_change
from app.auth import get_current_user, require_role
from app.db import get_db
from app.map_service import (accommodation_map, create_location,
                             duties_for, entity_catalog, events_map,
                             get_map_settings, incidents_map,
                             links_by_location, list_locations, location_detail,
                             location_visible, logistics_map, map_summary,
                             set_map_settings, unmapped_payload, update_location,
                             vendor_context, vendors_map, verify_location)
from app.models import MapDutyAssignment, MapLocation, Vendor

router = APIRouter(prefix="/map", tags=["map"])

MANAGER_GATE = require_role(*C.MAP_MANAGER_ROLES)
INCIDENT_GATE = require_role("director", "accommodation_lead", "events_lead",
                             "logistics_lead", "vendor_lead")


def _split(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _bbox(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parts = [float(p) for p in value.split(",")]
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "bbox must be min_lat,min_lng,max_lat,max_lng")
    if len(parts) != 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "bbox must be min_lat,min_lng,max_lat,max_lng")
    min_lat, min_lng, max_lat, max_lng = parts
    if not (-90 <= min_lat <= max_lat <= 90 and
            -180 <= min_lng <= max_lng <= 180):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "bbox values are out of range or inverted")
    return {"min_lat": min_lat, "min_lng": min_lng,
            "max_lat": max_lat, "max_lng": max_lng}


def _duty_ids(db: Session, user) -> set[int]:
    if user.role != "volunteer":
        return set()
    return {d.location_id for d in db.query(MapDutyAssignment).filter(
        MapDutyAssignment.username == user.username,
        MapDutyAssignment.active.is_(True)).all()}


def _get_visible(db: Session, user, location_id: int):
    location = db.get(MapLocation, location_id)
    if location is None or location.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "location not found")
    links = links_by_location(db).get(location.id, [])
    if not location_visible(user.role, location, links,
                            _duty_ids(db, user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "location not found")
    return location, links


def _approved(user) -> set[str]:
    return set(C.MAP_ROLE_TYPES.get(user.role, set()))


def _can_manage_location(db: Session, user, location: MapLocation) -> bool:
    if user.role == "director":
        return True
    if user.role not in C.MAP_MANAGER_ROLES:
        return False
    approved = _approved(user)
    if location.location_type in approved:
        return True
    return any(link.entity_type in approved
               for link in links_by_location(db).get(location.id, []))


def _check_type_permission(user, location_type: str) -> None:
    if user.role == "director":
        return
    if location_type not in _approved(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"role '{user.role}' may not manage '{location_type}' locations")


def _check_link_permissions(user, links: list[dict]) -> None:
    if user.role == "director":
        return
    approved = _approved(user)
    bad = sorted({str(link.get("entity_type")) for link in links
                  if str(link.get("entity_type")) not in approved})
    if bad:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"role '{user.role}' may not link: {', '.join(bad)}")


def _validate_pair(latitude, longitude) -> None:
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "latitude and longitude must be provided together (both or neither)")


# -------------------------------------------------------------------- reads --
@router.get("/locations")
def locations(user=Depends(get_current_user), db: Session = Depends(get_db),
              search: str | None = Query(default=None, max_length=200),
              types: str | None = Query(default=None),
              statuses: str | None = Query(default=None),
              at: str | None = Query(default=None),
              bbox: str | None = Query(default=None),
              include_unmapped: bool = Query(default=False),
              incident_only: bool = Query(default=False),
              limit: int = Query(default=200, ge=1),
              offset: int = Query(default=0, ge=0)):
    """Map pins the signed-in role is allowed to see."""
    data = list_locations(
        db, user.role, user.username, search=search,
        types=_split(types), statuses=_split(statuses),
        incident_only=incident_only, at=at,
        include_unmapped=include_unmapped,
        limit=min(limit, C.MAP["MAX_LOCATIONS_PER_PAGE"]), offset=offset,
        **_bbox(bbox))
    data["poll_seconds"] = C.MAP["POLL_SECONDS"]
    return data


@router.get("/locations/{location_id}")
def location(location_id: int, user=Depends(get_current_user),
             db: Session = Depends(get_db),
             at: str | None = Query(default=None)):
    loc, _ = _get_visible(db, user, location_id)
    payload = location_detail(db, loc, user.role, user.username, selected=at)
    payload["can_manage"] = _can_manage_location(db, user, loc)
    payload["role"] = user.role
    return payload


@router.get("/summary")
def summary(user=Depends(get_current_user), db: Session = Depends(get_db),
            at: str | None = Query(default=None)):
    data = map_summary(db, user.role, user.username, at=at)
    data["poll_seconds"] = C.MAP["POLL_SECONDS"]
    return data


@router.get("/accommodation")
def accommodation(user=Depends(require_role("director", "accommodation_lead")),
                  db: Session = Depends(get_db),
                  at: str | None = Query(default=None)):
    return accommodation_map(db, user.role, user.username, at=at)


@router.get("/events")
def events(user=Depends(require_role("director", "events_lead", "viewer")),
           db: Session = Depends(get_db),
           at: str | None = Query(default=None)):
    return events_map(db, user.role, user.username, at=at)


@router.get("/logistics")
def logistics(user=Depends(require_role("director", "logistics_lead")),
              db: Session = Depends(get_db),
              at: str | None = Query(default=None)):
    return logistics_map(db, user.role, user.username, at=at)


@router.get("/vendors")
def vendors(user=Depends(require_role("director", "vendor_lead")),
            db: Session = Depends(get_db),
            at: str | None = Query(default=None)):
    return vendors_map(db, user.role, user.username, at=at)


@router.get("/vendors/{vendor_id}")
def vendor_detail(vendor_id: int,
                  user=Depends(require_role("director", "vendor_lead")),
                  db: Session = Depends(get_db),
                  at: str | None = Query(default=None)):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vendor not found")
    from app.map_service import parse_selected_at
    at_aware, _, meta = parse_selected_at(at)
    return {**vendor_context(vendor, at_aware,
                             include_finance=user.role in
                             ("director", "vendor_lead")),
            **meta}


@router.get("/incidents")
def incidents(user=Depends(INCIDENT_GATE),
              db: Session = Depends(get_db)):
    return incidents_map(db, user.role, user.username)


@router.get("/unmapped")
def unmapped(user=Depends(MANAGER_GATE), db: Session = Depends(get_db)):
    return unmapped_payload(db, user.role, user.username)


@router.get("/entities")
def entities(user=Depends(MANAGER_GATE), db: Session = Depends(get_db)):
    rows = entity_catalog(db)
    if user.role != "director":
        approved = _approved(user)
        rows = [row for row in rows
                if row["entity_type"] in approved]
    return {"entities": rows,
            "counts": {
                "total": len(rows),
                "mapped": sum(1 for row in rows if row["mapped"]),
                "unmapped": sum(1 for row in rows if not row["mapped"]),
            }}


@router.get("/settings")
def settings(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return get_map_settings(db)


# ------------------------------------------------------------------- writes --
@router.post("/locations", status_code=status.HTTP_201_CREATED)
def create(body: schemas.MapLocationIn,
           user=Depends(MANAGER_GATE), db: Session = Depends(get_db)):
    _validate_pair(body.latitude, body.longitude)
    if body.location_type not in C.MAP_LOCATION_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"unknown location_type '{body.location_type}'")
    _check_type_permission(user, body.location_type)
    links = [link.model_dump() for link in body.links]
    _check_link_permissions(user, links)
    loc = create_location(
        db, user.username, body.name, body.location_type,
        latitude=body.latitude, longitude=body.longitude,
        address=body.address, campus_zone=body.campus_zone,
        parent_location_id=body.parent_location_id,
        source_reference=body.source_reference,
        links=links, reason=body.reason)
    payload = location_detail(db, loc, user.role, user.username)
    payload["can_manage"] = True
    return payload


@router.patch("/locations/{location_id}")
def update(location_id: int, body: schemas.MapLocationPatchIn,
           user=Depends(require_role(*C.MAP_MANAGER_ROLES)),
           db: Session = Depends(get_db)):
    loc, _ = _get_visible(db, user, location_id)
    if not _can_manage_location(db, user, loc):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "not allowed to manage this location")
    changes = body.model_dump(exclude_unset=True)
    links = changes.pop("links", None)
    reason = changes.pop("reason", None)
    if "name" in changes:
        changes["name"] = (changes["name"] or "").strip()
        if not changes["name"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "name cannot be blank")
    if "location_type" in changes:
        if changes["location_type"] not in C.MAP_LOCATION_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"unknown location_type '{changes['location_type']}'")
        _check_type_permission(user, changes["location_type"])
    if links is not None:
        _check_link_permissions(user, links)
        if user.role != "director":
            # A lead only ever sees links for their own entity types. Preserve
            # links owned by other roles so a scoped edit cannot silently
            # delete another team's attachment to the same pin.
            approved = _approved(user)
            preserved = [
                {"entity_type": link.entity_type, "entity_id": link.entity_id}
                for link in links_by_location(db).get(loc.id, [])
                if link.entity_type not in approved
            ]
            links = preserved + links
    _validate_pair(changes.get("latitude", loc.latitude),
                   changes.get("longitude", loc.longitude))
    loc = update_location(db, loc, user.username, changes, links, reason)
    payload = location_detail(db, loc, user.role, user.username)
    payload["can_manage"] = True
    return payload


@router.post("/locations/{location_id}/verify")
def verify(location_id: int, body: schemas.ReasonIn | None = None,
           user=Depends(require_role(*C.MAP_MANAGER_ROLES)),
           db: Session = Depends(get_db)):
    loc, _ = _get_visible(db, user, location_id)
    if not _can_manage_location(db, user, loc):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "not allowed to verify this location")
    loc = verify_location(db, loc, user.username,
                          body.reason if body else None)
    payload = location_detail(db, loc, user.role, user.username)
    payload["can_manage"] = True
    return payload


@router.patch("/settings")
def update_settings(body: schemas.MapSettingsIn,
                    user=Depends(require_role("director")),
                    db: Session = Depends(get_db)):
    return set_map_settings(db, body.latitude, body.longitude, body.zoom,
                            body.label, user.username, body.reason)


# ------------------------------------------------------------------- duties --
@router.get("/duties")
def duties(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return {"duties": duties_for(db, user.role, user.username)}


@router.post("/duties", status_code=status.HTTP_201_CREATED)
def create_duty(body: schemas.MapDutyIn,
                user=Depends(require_role("director")),
                db: Session = Depends(get_db)):
    from app.map_service import _parse_payload_dt
    if body.task_type not in C.MAP_TASK_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"unknown task_type '{body.task_type}'")
    loc = db.get(MapLocation, body.location_id)
    if loc is None or loc.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "location not found")
    starts_at = _parse_payload_dt(body.starts_at)
    ends_at = _parse_payload_dt(body.ends_at)
    if body.starts_at and starts_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "starts_at must be ISO 8601")
    if body.ends_at and ends_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "ends_at must be ISO 8601")
    if starts_at and ends_at and ends_at <= starts_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "ends_at must be after starts_at")
    duty = MapDutyAssignment(
        username=body.username.strip(), location_id=loc.id,
        task_type=body.task_type, label=body.label,
        starts_at=starts_at, ends_at=ends_at, active=True,
        created_by=user.username)
    db.add(duty)
    db.flush()
    log_change(db, user.username, "map_duty", duty.id, None,
               {"username": duty.username, "location_id": duty.location_id,
                "task_type": duty.task_type, "label": duty.label,
                "starts_at": duty.starts_at, "ends_at": duty.ends_at},
               "volunteer duty assigned on the operations map", kind="manual")
    db.commit()
    db.refresh(duty)
    from app.map_service import duty_dict
    return duty_dict(duty)


@router.delete("/duties/{duty_id}")
def remove_duty(duty_id: int, user=Depends(require_role("director")),
                db: Session = Depends(get_db)):
    duty = db.get(MapDutyAssignment, duty_id)
    if duty is None or not duty.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "duty not found")
    before = {"active": True}
    duty.active = False
    log_change(db, user.username, "map_duty", duty.id, before,
               {"active": False}, "volunteer duty deactivated",
               kind="manual")
    db.commit()
    from app.map_service import duty_dict
    return duty_dict(duty)


# ----------------------------------------------------------------- geocoding --
@router.post("/geocode")
async def geocode(body: schemas.MapGeocodeIn,
                  user=Depends(MANAGER_GATE)):
    """Search-place proxy for Nominatim. The returned point is a *suggestion*
    and stays unverified until an organiser places and verifies the pin."""
    if not C.GEOCODING_ENABLED:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "geocoding is disabled on this deployment")
    params = {"q": body.query, "format": "jsonv2", "limit": 5,
              "addressdetails": 1}
    headers = {"User-Agent": "FestOS-GeoCommand/1.0 (festival operations map)"}
    try:
        async with httpx.AsyncClient(timeout=C.HTTP_TIMEOUT_S) as client:
            response = await client.get(f"{C.NOMINATIM_URL}/search",
                                        params=params, headers=headers)
            response.raise_for_status()
            results = response.json()
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "geocoding provider unavailable")
    return {
        "query": body.query,
        "results": [{
            "display_name": item.get("display_name"),
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "category": item.get("category"),
            "type": item.get("type"),
            "address": item.get("address") or {},
        } for item in results if item.get("lat") and item.get("lon")],
        "attribution": "OpenStreetMap Nominatim",
        "note": "suggested point only; coordinates require on-site verification",
    }

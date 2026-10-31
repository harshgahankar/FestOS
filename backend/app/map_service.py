"""GeoCommand domain service.

The existing dataset has no verified GPS coordinates. This module therefore
keeps geography in a normalised, nullable registry and derives every operational
status from the same records and engines the rest of FestOS uses:

* accommodation occupancy  -> confirmed allocations only (active plan / audited
                              override / committed disruption rehousing)
* event status             -> stored start/end timestamps in Asia/Kolkata
* vendor availability      -> vendor compliance rules + selected service time
* inventory quantities     -> the movement ledger, never imported raw totals
* incidents                -> existing Disruption rows (preview = potential,
                              applied = verified); no second incident system

Nothing here invents coordinates, duties, participants or live tracking.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status as http_status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app import config as C
from app.models import (Allocation, AllocationPlan, ConfigRule, CoreTeam,
                        Disruption, Event, EventStaff, ExternalStay, HostelRoom,
                        InventoryItem, InventoryMovement, MapDutyAssignment,
                        MapLocation, MapLocationLink, Participant, Registration,
                        Venue, Vendor)
from engines.inventory import stock_levels
from engines.vendors import compliance as vendor_compliance

IST = ZoneInfo(C.MAP["TIMEZONE"])
UNKNOWN = "unknown"
STATUS_RANK = {
    "unknown": 0,
    "available": 1,
    "upcoming": 2,
    "ongoing": 2,
    "occupied": 2,
    "approaching": 2,
    "closed": 2,
    "empty": 3,
    "full": 3,
    "unavailable": 3,
    "interrupted": 3,
    "compliance_failed": 3,
    "conflict": 3,
    "incident": 4,
}
TONE_COLOR = {"good": "teal", "warn": "gold", "critical": "maroon",
              "unknown": "grey"}


# ----------------------------------------------------------------- utilities --
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _status(code: str, label: str, tone: str) -> dict:
    return {"code": code, "label": label, "tone": tone,
            "color": TONE_COLOR[tone]}


def parse_selected_at(value: str | None) -> tuple[datetime, datetime, dict]:
    """Return (aware IST datetime, naive DB-comparable datetime, response meta)."""
    if value:
        raw = str(value).strip()
        if not raw:
            value = None
        else:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                                    "selected time must be ISO 8601")
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=IST)
            aware = parsed.astimezone(IST)
            return aware, aware.replace(tzinfo=None), {
                "selected_at": aware.isoformat(),
                "timezone": C.MAP["TIMEZONE"],
                "date": aware.date().isoformat(),
            }
    aware = datetime.now(IST)
    return aware, aware.replace(tzinfo=None), {
        "selected_at": aware.isoformat(),
        "timezone": C.MAP["TIMEZONE"],
        "date": aware.date().isoformat(),
    }


def _parse_payload_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(IST).replace(tzinfo=None)
    return parsed


def _time_in_window(at: datetime, opens: time | None, closes: time | None,
                    crosses: bool = False) -> Optional[bool]:
    if opens is None or closes is None:
        return None
    moment = at.time()
    if crosses or closes <= opens:
        return moment >= opens or moment <= closes
    return opens <= moment <= closes


def _approved_types(role: str) -> set[str]:
    return set(C.MAP_ROLE_TYPES.get(role, set()))


def _visible_links(db: Session) -> list[MapLocationLink]:
    return db.query(MapLocationLink).all()


def links_by_location(db: Session) -> dict[int, list[MapLocationLink]]:
    out: dict[int, list[MapLocationLink]] = defaultdict(list)
    for link in _visible_links(db):
        out[link.location_id].append(link)
    return out


def link_index(db: Session) -> dict[tuple[str, str], MapLocationLink]:
    return {(link.entity_type, str(link.entity_id)): link
            for link in _visible_links(db)}


def _entity_label(db: Session, entity_type: str, entity_id: str) -> str:
    try:
        if entity_type == "hostel_block":
            return f"Hostel {entity_id}"
        if entity_type == "external_stay":
            row = db.query(ExternalStay).filter(
                ExternalStay.raw_id == entity_id).first()
            return row.property if row else entity_id
        if entity_type == "venue":
            row = db.query(Venue).filter(Venue.raw_id == entity_id).first()
            return row.name if row else entity_id
        if entity_type == "vendor":
            row = db.query(Vendor).filter(Vendor.raw_id == entity_id).first()
            return row.name if row else entity_id
        if entity_type == "inventory_location":
            return entity_id
        if entity_type == "incident":
            row = db.get(Disruption, int(entity_id))
            return f"Incident #{entity_id}" + (f" ({row.type})" if row else "")
    except (ValueError, TypeError):
        return entity_id
    return entity_id


def entity_exists(db: Session, entity_type: str, entity_id: str) -> bool:
    if entity_type == "hostel_block":
        return db.query(HostelRoom).filter(HostelRoom.hostel == entity_id).first() is not None
    if entity_type == "external_stay":
        return db.query(ExternalStay).filter(ExternalStay.raw_id == entity_id).first() is not None
    if entity_type == "venue":
        return db.query(Venue).filter(Venue.raw_id == entity_id).first() is not None
    if entity_type == "vendor":
        return db.query(Vendor).filter(Vendor.raw_id == entity_id).first() is not None
    if entity_type == "inventory_location":
        return entity_id in inventory_labels(db)
    if entity_type == "incident":
        try:
            return db.get(Disruption, int(entity_id)) is not None
        except (ValueError, TypeError):
            return False
    return False


def inventory_labels(db: Session) -> set[str]:
    labels: set[str] = set()
    for from_loc, to_loc in db.query(InventoryMovement.from_location,
                                     InventoryMovement.to_location).all():
        for label in (from_loc, to_loc):
            label = (label or "").strip()
            if not label:
                continue
            # merch-issue movements use participant raw ids as destinations;
            # those are not stock locations and must never become map markers.
            if label.upper().startswith("P") and label[1:].isdigit():
                continue
            labels.add(label)
    return labels


def location_visible(role: str, location: MapLocation,
                     links: list[MapLocationLink],
                     duty_location_ids: set[int] | None = None) -> bool:
    if role == "director":
        return True
    if role == "volunteer":
        return bool(duty_location_ids and location.id in duty_location_ids)
    allowed = _approved_types(role)
    if location.location_type in allowed:
        return True
    return any(link.entity_type in allowed for link in links)


def location_mapped(location: MapLocation) -> bool:
    return location.latitude is not None and location.longitude is not None


# ------------------------------------------------------------ allocation set --
def active_plan_ids(db: Session) -> list[int]:
    return [p.id for p in db.query(AllocationPlan)
            .filter(AllocationPlan.status == "active")
            .order_by(AllocationPlan.id).all()]


def confirmed_allocations(db: Session) -> list[Allocation]:
    """Live bed assignments only.

    Includes allocations belonging to an active plan plus audited manual
    overrides and committed disruption rehousing rows. Draft/superseded plans
    and unknown orphan rows are deliberately excluded.
    """
    plan_ids = active_plan_ids(db)
    clauses = []
    if plan_ids:
        clauses.append(Allocation.plan_id.in_(plan_ids))
    clauses.append(and_(Allocation.plan_id.is_(None),
                        Allocation.source.in_(("override", "disruption"))))
    rows = (db.query(Allocation)
            .join(Participant, Participant.id == Allocation.participant_id)
            .filter(or_(*clauses),
                    Participant.merged_into.is_(None),
                    Participant.status.in_(("active", "flagged")))
            .order_by(Allocation.id)
            .all())
    latest: dict[int, Allocation] = {}
    for row in rows:
        prev = latest.get(row.participant_id)
        if prev is None or (row.id or 0) > (prev.id or 0):
            latest[row.participant_id] = row
    return list(latest.values())


def _safe_person(p: Participant | None) -> dict | None:
    if p is None:
        return None
    return {
        "id": p.id,
        "raw_id": p.raw_id,
        "name": p.name,
        "accessibility_status": p.accessibility_status,
        "accessibility_details": p.accessibility_details,
        # phone/email/medical notes intentionally never enter map responses.
    }


# -------------------------------------------------------------- accommodation --
def block_context(db: Session, block: str, confirmed: list[Allocation],
                  include_rooms: bool = False) -> dict:
    rooms = (db.query(HostelRoom).filter(HostelRoom.hostel == block)
             .order_by(HostelRoom.floor, HostelRoom.raw_id).all())
    room_ids = {r.id for r in rooms}
    by_room: dict[int, list[Allocation]] = defaultdict(list)
    people = {p.id: p for p in db.query(Participant).filter(
        Participant.id.in_({a.participant_id for a in confirmed
                            if a.room_id in room_ids})).all()} if confirmed else {}
    allocated = 0
    for a in confirmed:
        if a.room_id in room_ids:
            by_room[a.room_id].append(a)
            allocated += 1

    total_beds = sum(int(r.beds or 0) for r in rooms)
    vacant = 0
    unavailable_beds = 0
    ready_rooms = 0
    accessible_rooms = 0
    accessible_beds = 0
    floors: dict[int, dict] = {}
    room_rows: list[dict] = []
    for room in rooms:
        beds = int(room.beds or 0)
        occupants = by_room.get(room.id, [])
        occupied = len(occupants)
        operational = room.status == "open" and room.readiness == "ready"
        room_vacant = max(beds - occupied, 0) if operational else 0
        vacant += room_vacant
        if not operational:
            unavailable_beds += max(beds - occupied, 0)
        if operational:
            ready_rooms += 1
        if room.accessible:
            accessible_rooms += 1
            accessible_beds += beds
        floor = int(room.floor or 0)
        agg = floors.setdefault(floor, {"floor": floor, "rooms": 0, "beds": 0,
                                        "allocated": 0, "vacant": 0,
                                        "accessible_rooms": 0})
        agg["rooms"] += 1
        agg["beds"] += beds
        agg["allocated"] += occupied
        agg["vacant"] += room_vacant
        if room.accessible:
            agg["accessible_rooms"] += 1
        if occupied >= beds and beds > 0:
            room_state = "full"
        elif not operational:
            room_state = "unavailable"
        elif occupied > 0:
            room_state = "partial"
        else:
            room_state = "available"
        room_row = {
            "id": room.id,
            "raw_id": room.raw_id,
            "floor": room.floor,
            "room_no": room.room_no,
            "beds": beds,
            "allocated": occupied,
            "vacant": room_vacant,
            "accessible": bool(room.accessible),
            "gender_block": room.gender_block,
            "readiness": room.readiness,
            "status": room.status,
            "allocation_status": room_state,
        }
        if include_rooms:
            room_row["allocations"] = [
                {"allocation_id": a.id,
                 "source": a.source,
                 "person": _safe_person(people.get(a.participant_id))}
                for a in occupants
            ]
        room_rows.append(room_row)

    pct = round((allocated / total_beds) * 100, 1) if total_beds else None
    if total_beds == 0:
        st = _status(UNKNOWN, "No bed data", "unknown")
    elif all(r.status != "open" for r in rooms):
        st = _status("unavailable", "Closed", "critical")
    elif pct is not None and pct >= 100:
        st = _status("full", "Full", "critical")
    elif pct is not None and pct >= C.MAP["OCCUPANCY_APPROACHING_PCT"]:
        st = _status("approaching", "Approaching capacity", "warn")
    else:
        st = _status("available", "Beds available", "good")

    floor_rows = [floors[k] for k in sorted(floors)]
    result = {
        "kind": "hostel_block",
        "block": block,
        "rooms_total": len(rooms),
        "ready_rooms": ready_rooms,
        "accessible_rooms": accessible_rooms,
        "accessible_beds": accessible_beds,
        "total_beds": total_beds,
        "allocated_beds": allocated,
        "vacant_beds": vacant,
        "unavailable_beds": unavailable_beds,
        "occupancy_pct": pct,
        "status": st,
        "floors": floor_rows,
        "summary": {
            "total_beds": total_beds, "allocated_beds": allocated,
            "vacant_beds": vacant, "occupancy_pct": pct,
            "rooms": len(rooms), "accessible_rooms": accessible_rooms,
        },
    }
    if include_rooms:
        result["rooms"] = room_rows
    return result


def external_context(ext: ExternalStay, confirmed: list[Allocation],
                     include_allocations: bool = False) -> dict:
    mine = [a for a in confirmed if a.external_stay_id == ext.id]
    allocated = len(mine)
    beds = int(ext.beds or 0)
    vacant = max(beds - allocated, 0)
    pct = round((allocated / beds) * 100, 1) if beds else None
    if ext.status != "open":
        st = _status("unavailable", "Closed", "critical")
    elif beds == 0:
        st = _status(UNKNOWN, "No bed data", "unknown")
    elif pct is not None and pct >= 100:
        st = _status("full", "Full", "critical")
    elif pct is not None and pct >= C.MAP["OCCUPANCY_APPROACHING_PCT"]:
        st = _status("approaching", "Approaching capacity", "warn")
    else:
        st = _status("available", "Beds available", "good")
    result = {
        "kind": "external_stay",
        "raw_id": ext.raw_id,
        "property": ext.property,
        "beds": beds,
        "allocated_beds": allocated,
        "vacant_beds": vacant,
        "occupancy_pct": pct,
        "distance_km": ext.distance_km,
        "travel_minutes": ext.travel_minutes,
        "transport_available": ext.transport_available,
        "safety_coverage": ext.safety_coverage,
        "status": st,
        "summary": {"total_beds": beds, "allocated_beds": allocated,
                    "vacant_beds": vacant, "occupancy_pct": pct},
    }
    if include_allocations:
        people = {p.id: p for p in db.query(Participant).filter(
            Participant.id.in_({a.participant_id for a in mine})).all()}
        result["allocations"] = [
            {"allocation_id": a.id, "source": a.source,
             "person": _safe_person(people.get(a.participant_id))}
            for a in mine
        ]
    return result


# -------------------------------------------------------------------- events --
def conflict_bundle(db: Session) -> dict:
    from app.routers.disruptions import _sched_check
    try:
        return _sched_check(db)
    except Exception:                 # the map must not go dark on a bad schedule row
        return {"conflicts": [], "suggestions": [], "checked_events": 0,
                "summary": {}}


def conflicts_by_event(bundle: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for conflict in bundle.get("conflicts", []):
        for key in (conflict.get("event"), conflict.get("event_1"),
                    conflict.get("event_2")):
            if key:
                out[str(key)].append(conflict)
    return out


def _staff_by_event(db: Session) -> dict[int, list[dict]]:
    rows = (db.query(EventStaff, CoreTeam)
            .join(CoreTeam, CoreTeam.id == EventStaff.core_team_id).all())
    out: dict[int, list[dict]] = defaultdict(list)
    for assignment, member in rows:
        out[assignment.event_id].append({
            "name": member.name,
            "role": assignment.role or member.role,
        })
    return out


def _registration_counts(db: Session) -> dict[int, int]:
    rows = (db.query(Registration.event_id, Registration.id)
            .filter(Registration.status == "registered").all())
    out: dict[int, int] = defaultdict(int)
    for event_id, _ in rows:
        if event_id is not None:
            out[event_id] += 1
    return out


def _event_is_valid(event: Event) -> bool:
    return bool(event.start_dt and event.end_dt and event.end_dt > event.start_dt)


def _event_status(event: Event, at_naive: datetime) -> str:
    if event.start_dt <= at_naive < event.end_dt:
        return "ongoing"
    if event.start_dt > at_naive:
        return "upcoming"
    return "completed"


def _event_public(event: Event, at_naive: datetime,
                  conflicts: dict[str, list[dict]],
                  regs: dict[int, int],
                  staff: dict[int, list[dict]],
                  include_ops: bool) -> dict:
    status = _event_status(event, at_naive)
    row = {
        "id": event.id,
        "raw_id": event.raw_id,
        "name": event.name,
        "type": event.type,
        "start": _iso(event.start_dt),
        "end": _iso(event.end_dt),
        "status": status,
        "conflicts": conflicts.get(event.raw_id, []),
        "registration_count": regs.get(event.id, 0),
        "rounds": event.rounds or [],
    }
    if include_ops:
        row["equipment_needs"] = event.equipment_needs or []
        row["venue_requirements"] = event.venue_requirements or []
        row["volunteers_needed"] = event.volunteers_needed
        row["staff"] = staff.get(event.id, [])
        row["setup_min"] = event.setup_min
        row["teardown_min"] = event.teardown_min
    return row


def venue_context(db: Session, venue: Venue, at_naive: datetime,
                  at_aware: datetime, bundle: dict,
                  include_ops: bool = True) -> dict:
    c_map = conflicts_by_event(bundle)
    regs = _registration_counts(db)
    staff = _staff_by_event(db)
    events = (db.query(Event).filter(Event.venue_id == venue.id)
              .order_by(Event.start_dt, Event.raw_id).all())
    valid = [e for e in events if _event_is_valid(e)]
    invalid = [e for e in events if not _event_is_valid(e)]
    rows = [_event_public(e, at_naive, c_map, regs, staff, include_ops)
            for e in valid]
    current = [r for r in rows if r["status"] == "ongoing"]
    upcoming = sorted([r for r in rows if r["status"] == "upcoming"],
                      key=lambda r: r["start"] or "")
    completed = [r for r in rows if r["status"] == "completed"]
    conflicts: list[dict] = []
    for r in rows:
        conflicts.extend(r["conflicts"])
    occupied = bool(current)
    upcoming_soon = False
    if upcoming:
        next_start = _parse_payload_dt(upcoming[0]["start"])
        if next_start is not None and \
                next_start - at_naive <= timedelta(minutes=C.MAP["UPCOMING_SOON_MINUTES"]):
            upcoming_soon = True
    if conflicts:
        st = _status("conflict", "Scheduling conflict", "critical")
    elif venue.status != "open":
        st = _status("unavailable", "Unavailable", "critical")
    elif occupied:
        st = _status("ongoing", "Ongoing event", "warn")
    elif upcoming_soon:
        st = _status("upcoming", "Event starting soon", "warn")
    elif rows:
        st = _status("available", "Venue available", "good")
    else:
        st = _status("available", "No session now", "good")

    result = {
        "kind": "venue",
        "raw_id": venue.raw_id,
        "name": venue.name,
        "capacity": venue.capacity,
        "indoor_outdoor": venue.location,
        "venue_status": venue.status,
        "availability_windows": venue.availability_windows or [],
        "status": st,
        "current_events": current,
        "upcoming_events": upcoming[:8],
        "completed_count": len(completed),
        "event_count": len(valid),
        "conflicts": conflicts,
        "unscheduled_count": len(invalid),
        "summary": {
            "capacity": venue.capacity,
            "current": current[0]["name"] if current else None,
            "current_registrations": current[0]["registration_count"] if current else 0,
            "upcoming": len(upcoming),
            "conflicts": len(conflicts),
        },
    }
    if include_ops and current:
        result["required_equipment"] = current[0].get("equipment_needs") or []
        result["assigned_staff"] = current[0].get("staff") or []
    return result


# ------------------------------------------------------------------- vendors --
def _vendor_dict(v: Vendor) -> dict:
    return {"id": v.id, "raw_id": v.raw_id, "name": v.name,
            "dietary_coverage": v.dietary_coverage or [],
            "hygiene_cert_expiry": v.hygiene_cert_expiry,
            "hours": v.hours, "capacity_per_day": v.capacity_per_day,
            "rate": v.rate, "payment_terms": v.payment_terms,
            "status": v.status}


def vendor_context(v: Vendor, at_aware: datetime, include_finance: bool = True) -> dict:
    service_day = at_aware.date().isoformat()
    comp = vendor_compliance([_vendor_dict(v)], service_day, service_day)
    cert = comp["vendors"][0] if comp["vendors"] else {}
    open_state = _time_in_window(at_aware, v.opens, v.closes,
                                 bool(v.opens and v.closes and v.closes <= v.opens))
    cert_code = cert.get("status_code", "UNKNOWN")
    verified_compliant = cert_code == "OK"
    if v.status == "interrupted":
        st = _status("interrupted", "Interrupted", "critical")
        availability = "interrupted"
    elif cert_code == "EXPIRED":
        st = _status("compliance_failed", "Hygiene certificate expired", "critical")
        availability = "compliance_blocked"
    elif cert_code in ("MISSING_CERT_DATE", "UNKNOWN"):
        st = _status(UNKNOWN, "Compliance not verified", "unknown")
        availability = "unknown"
    elif v.status != "active":
        st = _status("unavailable", "Not active", "critical")
        availability = "unavailable"
    elif open_state is False:
        st = _status("closed", "Outside operating hours", "warn")
        availability = "closed"
    elif open_state is None:
        st = _status(UNKNOWN, "Operating hours unknown", "unknown")
        availability = "unknown"
    elif cert_code == "EXPIRING_MID_FEST":
        st = _status("approaching", "Certificate expires today", "warn")
        availability = "serving"
    else:
        st = _status("available", "Serving", "good")
        availability = "serving"
    result = {
        "kind": "vendor",
        "raw_id": v.raw_id,
        "name": v.name,
        "menu": v.menu or [],
        "dietary_coverage": v.dietary_coverage or [],
        "hygiene_cert_expiry": _iso(v.hygiene_cert_expiry),
        "compliance_status": cert_code,
        "compliance_verified": verified_compliant,
        "verified_compliant": verified_compliant,
        "hours": v.hours,
        "opens": v.opens.isoformat() if v.opens else None,
        "closes": v.closes.isoformat() if v.closes else None,
        "is_open": open_state,
        "capacity_per_day": v.capacity_per_day,
        "availability": availability,
        "status": st,
        "summary": {
            "capacity_per_day": v.capacity_per_day,
            "compliance": cert_code,
            "verified_compliant": verified_compliant,
            "open": open_state,
        },
    }
    if include_finance:
        result["rate"] = v.rate
        result["payment_terms"] = v.payment_terms
    return result


# ----------------------------------------------------------------- inventory --
def _movement_location_slice(db: Session, label: str) -> list[InventoryMovement]:
    return (db.query(InventoryMovement)
            .filter(or_(InventoryMovement.from_location == label,
                        InventoryMovement.to_location == label))
            .order_by(InventoryMovement.at.desc(), InventoryMovement.id.desc())
            .all())


def inventory_context(db: Session, label: str) -> dict:
    movements = _movement_location_slice(db, label)
    item_ids = {m.item_id for m in movements}
    items = {i.id: i for i in db.query(InventoryItem)
             .filter(InventoryItem.id.in_(item_ids)).all()} if item_ids else {}
    all_items = [{"id": i.id, "sku": i.sku, "name": i.name,
                  "category": i.category, "size": i.size, "kind": i.kind,
                  "condition": i.condition}
                 for i in db.query(InventoryItem).all()]
    all_movements = [{"item_id": m.item_id, "qty": m.qty,
                      "status": m.status, "at": m.at, "id": m.id}
                     for m in db.query(InventoryMovement).all()]
    global_levels = stock_levels(all_items, all_movements)

    by_item: dict[int, list[InventoryMovement]] = defaultdict(list)
    for movement in movements:
        by_item[movement.item_id].append(movement)

    item_rows: list[dict] = []
    for item_id, rows in by_item.items():
        item = items.get(item_id)
        if item is None:
            continue
        on_hand = 0
        reserved = 0
        for m in rows:
            qty = int(m.qty or 0)
            # qty is the signed ledger delta (positive = stock in, negative =
            # stock out). A row touches this label either because it arrived
            # here or because it left from here; both apply the same delta.
            if m.to_location == label and m.from_location != label:
                on_hand += qty
            elif m.from_location == label and m.to_location != label:
                on_hand += qty
            elif m.from_location == label and m.to_location == label:
                continue
            if (m.status or "").lower() == "reserved" and \
                    m.to_location == label and qty > 0:
                reserved += qty
        under_repair = on_hand if (item.condition or "good").lower() != "good" else 0
        available = max(0, on_hand - reserved - under_repair)
        item_rows.append({
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "category": item.category,
            "kind": item.kind,
            "condition": item.condition,
            "on_hand": on_hand,
            "available": available,
            "reserved": reserved,
            "under_repair": under_repair,
            "global_available": global_levels.get(item.id, 0),
        })
    item_rows.sort(key=lambda r: (r["kind"], str(r["sku"])))

    recent = [{
        "id": m.id, "at": _iso(m.at),
        "item_id": m.item_id,
        "sku": items[m.item_id].sku if m.item_id in items else None,
        "name": items[m.item_id].name if m.item_id in items else None,
        "qty": m.qty,
        "from_location": m.from_location,
        "to_location": m.to_location,
        "status": m.status,
        "reference": m.reference,
    } for m in movements[:10]]

    total_on_hand = sum(max(0, r["on_hand"]) for r in item_rows)
    under_repair_total = sum(r["under_repair"] for r in item_rows)
    reserved_total = sum(r["reserved"] for r in item_rows)
    if not item_rows:
        st = _status(UNKNOWN, "No stock recorded", "unknown")
    elif total_on_hand <= 0:
        st = _status("empty", "No stock on hand", "critical")
    elif under_repair_total > 0:
        st = _status("approaching", "Equipment under repair", "warn")
    else:
        st = _status("available", "Stock on hand", "good")

    equipment_reqs: list[dict] = []
    skus = {r["sku"] for r in item_rows}
    if skus:
        for event in db.query(Event).filter(Event.equipment_needs.isnot(None)).all():
            needs = [n for n in (event.equipment_needs or [])
                     if (n.get("sku") if isinstance(n, dict) else n) in skus]
            if needs:
                equipment_reqs.append({
                    "event_id": event.raw_id, "event": event.name,
                    "start": _iso(event.start_dt), "needs": needs,
                })
    return {
        "kind": "inventory_location",
        "label": label,
        "items": item_rows,
        "item_count": len(item_rows),
        "total_on_hand": total_on_hand,
        "reserved_quantity": reserved_total,
        "under_repair_quantity": under_repair_total,
        "recent_movements": recent,
        "event_requirements": equipment_reqs,
        "status": st,
        "summary": {
            "items": len(item_rows), "on_hand": total_on_hand,
            "reserved": reserved_total, "under_repair": under_repair_total,
        },
    }


def movement_edges(db: Session, location_by_entity: dict[tuple[str, str], int],
                   locations: dict[int, MapLocation]) -> list[dict]:
    """Recent ledger transfers between two mapped inventory locations."""
    edges = []
    rows = (db.query(InventoryMovement)
            .filter(InventoryMovement.from_location.isnot(None),
                    InventoryMovement.to_location.isnot(None))
            .order_by(InventoryMovement.at.desc(), InventoryMovement.id.desc())
            .limit(50).all())
    for m in rows:
        from_id = location_by_entity.get(("inventory_location", m.from_location or ""))
        to_id = location_by_entity.get(("inventory_location", m.to_location or ""))
        if not (from_id and to_id and from_id != to_id):
            continue
        a, b = locations.get(from_id), locations.get(to_id)
        if not (a and b and location_mapped(a) and location_mapped(b)):
            continue
        edges.append({
            "movement_id": m.id, "at": _iso(m.at), "qty": m.qty,
            "status": m.status, "reference": m.reference,
            "from": {"location_id": a.id, "name": a.name,
                     "latitude": a.latitude, "longitude": a.longitude},
            "to": {"location_id": b.id, "name": b.name,
                   "latitude": b.latitude, "longitude": b.longitude},
        })
    return edges


# ------------------------------------------------------------------ incidents --
def _incident_targets(db: Session, d: Disruption) -> list[dict]:
    payload = d.payload or {}
    targets: list[dict] = []

    def add(entity_type: str, entity_id: str):
        key = (entity_type, str(entity_id))
        if not any((t["entity_type"], t["entity_id"]) == key for t in targets):
            targets.append({"entity_type": entity_type, "entity_id": str(entity_id),
                            "name": _entity_label(db, entity_type, str(entity_id))})

    if d.type == "hostel_closure":
        blocks = []
        if payload.get("hostel") or payload.get("block"):
            blocks = [payload.get("hostel") or payload.get("block")]
        elif payload.get("room_raw_ids"):
            blocks = [r.hostel for r in db.query(HostelRoom)
                      .filter(HostelRoom.raw_id.in_(payload["room_raw_ids"])).all()]
        for block in blocks:
            if block:
                add("hostel_block", block)
    elif d.type == "venue_change":
        event = db.query(Event).filter(
            Event.raw_id == (payload.get("event_raw_id") or "")).first()
        if event is not None:
            new_v = db.get(Venue, payload.get("new_venue_id")) \
                if payload.get("new_venue_id") is not None else None
            if event.venue_id:
                current = db.get(Venue, event.venue_id)
                if current is not None:
                    add("venue", current.raw_id)
            if new_v is not None:
                add("venue", new_v.raw_id)
    elif d.type == "equipment_failure":
        item = None
        if payload.get("sku"):
            item = db.query(InventoryItem).filter(
                InventoryItem.sku == payload["sku"]).first()
        if item is None and payload.get("item_id") is not None:
            item = db.get(InventoryItem, payload["item_id"])
        if item is not None:
            mv = (db.query(InventoryMovement)
                  .filter(InventoryMovement.item_id == item.id,
                          InventoryMovement.to_location.isnot(None))
                  .order_by(InventoryMovement.at.desc(),
                            InventoryMovement.id.desc()).first())
            if mv and mv.to_location:
                add("inventory_location", mv.to_location)
    elif d.type == "vendor_shutdown":
        vendor = None
        if payload.get("vendor_id") is not None:
            vendor = db.get(Vendor, payload["vendor_id"])
        else:
            raw = payload.get("raw_id") or payload.get("vendor_raw_id")
            if raw:
                vendor = db.query(Vendor).filter(Vendor.raw_id == raw).first()
        if vendor is not None:
            add("vendor", vendor.raw_id)
    return targets


def incident_dict(db: Session, d: Disruption, link_map: dict) -> dict:
    targets = _incident_targets(db, d)
    explicit = link_map.get(("incident", str(d.id)))
    location_ids = []
    for target in targets:
        link = link_map.get((target["entity_type"], target["entity_id"]))
        if link:
            target["location_id"] = link.location_id
            if link.location_id not in location_ids:
                location_ids.append(link.location_id)
    if explicit and explicit.location_id not in location_ids:
        location_ids.append(explicit.location_id)
    report = d.impact_report or {}
    affected = report.get("affected") or {}
    recovery = None
    if d.type == "hostel_closure" and d.status == "applied":
        snapshot = d.revert_snapshot or {}
        created = snapshot.get("created_allocation_ids") or []
        present = 0
        if created:
            present = db.query(Allocation).filter(
                Allocation.id.in_(created)).count()
        recovery = {"displaced": affected.get("count", 0),
                    "rehoused": present,
                    "status": "rehoused" if present else "displaced"}
    elif d.type == "vendor_shutdown" and d.status == "applied":
        snapshot = d.revert_snapshot or {}
        moves = snapshot.get("orders_moved") or []
        recovery = {"orders_rerouted": len(moves)}
    effect = "verified" if d.status == "applied" else "potential"
    return {
        "id": d.id,
        "type": d.type,
        "status": d.status,
        "effect": effect,
        "verified": effect == "verified",
        "applied_at": _iso(d.applied_at),
        "applied_by": d.applied_by,
        "targets": targets,
        "location_ids": location_ids,
        "impact_summary": {
            "affected": affected.get("count", 0) if isinstance(affected, dict) else 0,
            "violations": len(report.get("new_violations") or []),
            "cost_delta": report.get("cost_delta"),
        },
        "recovery": recovery,
    }


def build_incidents(db: Session, role: str) -> tuple[list[dict], list[dict]]:
    """Return (incidents with mapped locations, unlocated incidents)."""
    if role in ("viewer", "volunteer"):
        return [], []
    link_map = link_index(db)
    approved = _approved_types(role)
    mapped: list[dict] = []
    unlocated: list[dict] = []
    rows = (db.query(Disruption)
            .filter(Disruption.status.in_(("previewed", "applied")))
            .order_by(Disruption.id.desc()).all())
    for d in rows:
        inc = incident_dict(db, d, link_map)
        if role != "director":
            allowed_targets = [t for t in inc["targets"]
                               if t["entity_type"] in approved]
            if not allowed_targets:
                continue
            allowed_ids = {t["location_id"] for t in allowed_targets
                           if t.get("location_id")}
            inc["targets"] = allowed_targets
            inc["location_ids"] = [i for i in inc["location_ids"]
                                   if i in allowed_ids]
        if inc["location_ids"]:
            mapped.append(inc)
        else:
            unlocated.append(inc)
    return mapped, unlocated


def incidents_by_location(incidents: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = defaultdict(list)
    for inc in incidents:
        for loc_id in inc["location_ids"]:
            out[loc_id].append(inc)
    return out


# ----------------------------------------------------------- context helpers --
def _context_for_link(db: Session, link: MapLocationLink, role: str,
                      at_naive: datetime, at_aware: datetime,
                      confirmed: list[Allocation], bundle: dict) -> Optional[dict]:
    approved = _approved_types(role)
    if role != "director" and link.entity_type not in approved:
        return None
    entity_id = str(link.entity_id)
    if link.entity_type == "hostel_block":
        return block_context(db, entity_id, confirmed, include_rooms=False)
    if link.entity_type == "external_stay":
        ext = db.query(ExternalStay).filter(
            ExternalStay.raw_id == entity_id).first()
        return external_context(ext, confirmed) if ext else None
    if link.entity_type == "venue":
        venue = db.query(Venue).filter(Venue.raw_id == entity_id).first()
        if venue is None:
            return None
        return venue_context(db, venue, at_naive, at_aware, bundle,
                             include_ops=role in ("director", "events_lead"))
    if link.entity_type == "vendor":
        vendor = db.query(Vendor).filter(Vendor.raw_id == entity_id).first()
        if vendor is None:
            return None
        return vendor_context(vendor, at_aware,
                              include_finance=role in ("director", "vendor_lead"))
    if link.entity_type == "inventory_location":
        return inventory_context(db, entity_id)
    return None


def _choose_status(contexts: list[dict], incidents: list[dict]) -> dict:
    verified = [i for i in incidents if i.get("verified")]
    if verified:
        return _status("incident", "Active operational incident", "critical")
    statuses = [c["status"] for c in contexts if c.get("status")]
    if not statuses:
        return _status(UNKNOWN, "No operational data", "unknown")
    return max(statuses, key=lambda s: STATUS_RANK.get(s["code"], 0))


def location_payload(db: Session, location: MapLocation,
                     links: list[MapLocationLink], role: str,
                     at_naive: datetime, at_aware: datetime,
                     confirmed: list[Allocation], bundle: dict,
                     incidents: list[dict]) -> dict:
    contexts_list = []
    for link in links:
        context = _context_for_link(db, link, role, at_naive, at_aware,
                                    confirmed, bundle)
        if context is not None:
            contexts_list.append({**context,
                                  "entity_type": link.entity_type,
                                  "entity_id": str(link.entity_id),
                                  "label": _entity_label(db, link.entity_type,
                                                         str(link.entity_id))})
    contexts = {c["entity_type"]: c for c in contexts_list}
    op_status = _choose_status(contexts_list, incidents)
    # A role only sees links it is allowed to operate on; this prevents e.g. a
    # viewer opening a venue pin from seeing vendor or inventory links on it.
    allowed_links = links if role == "director" else \
        [l for l in links if l.entity_type in _approved_types(role)]
    return {
        "id": location.id,
        "name": location.name,
        "location_type": location.location_type,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "address": location.address,
        "campus_zone": location.campus_zone,
        "parent_location_id": location.parent_location_id,
        "source_reference": location.source_reference,
        "coordinate_verification_status": location.coordinate_verification_status,
        "last_verified_at": _iso(location.last_verified_at),
        "created_at": _iso(location.created_at),
        "updated_at": _iso(location.updated_at),
        "mapped": location_mapped(location),
        "coordinates_verified": location.coordinate_verification_status == "verified",
        "links": [{"entity_type": link.entity_type,
                   "entity_id": str(link.entity_id),
                   "label": _entity_label(db, link.entity_type, str(link.entity_id))}
                  for link in allowed_links],
        "layers": sorted({link.entity_type for link in allowed_links} |
                         {location.location_type}),
        "contexts": contexts,
        "operational_status": op_status,
        "has_incident": any(i.get("verified") for i in incidents),
        "incident_count": sum(1 for i in incidents if i.get("verified")),
        "potential_incident_count": sum(1 for i in incidents
                                        if not i.get("verified")),
        "incidents": incidents,
        "summary": {c["entity_type"]: c.get("summary", {})
                    for c in contexts_list},
        "layer_statuses": {c["entity_type"]: c["status"] for c in contexts_list
                           if c.get("status")} or (
            {"incident_location": op_status}
            if location.location_type == "incident_location" else {}),
    }


def visible_locations_for_user(db: Session, role: str,
                               username: str) -> tuple[list[MapLocation], dict]:
    loc_links = links_by_location(db)
    duty_ids: set[int] = set()
    if role == "volunteer":
        duty_ids = {d.location_id for d in db.query(MapDutyAssignment).filter(
            MapDutyAssignment.username == username,
            MapDutyAssignment.active.is_(True)).all()}
    rows = (db.query(MapLocation)
            .filter(MapLocation.deleted_at.is_(None))
            .order_by(MapLocation.name).all())
    visible = [loc for loc in rows
               if location_visible(role, loc, loc_links.get(loc.id, []), duty_ids)]
    return visible, loc_links


def location_detail(db: Session, location: MapLocation, role: str,
                    username: str, selected: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(selected)
    loc_links = links_by_location(db)
    links = loc_links.get(location.id, [])
    confirmed = confirmed_allocations(db)
    bundle = conflict_bundle(db)
    incidents_all, _ = build_incidents(db, role)
    incidents = [i for i in incidents_all if location.id in i["location_ids"]]
    payload = location_payload(db, location, links, role, at_naive, at_aware,
                               confirmed, bundle, incidents)
    payload.update(meta)
    if role in ("director", "accommodation_lead"):
        for link in links:
            if link.entity_type == "hostel_block":
                payload["contexts"]["hostel_block"] = block_context(
                    db, str(link.entity_id), confirmed, include_rooms=True)
            elif link.entity_type == "external_stay":
                ext = db.query(ExternalStay).filter(
                    ExternalStay.raw_id == str(link.entity_id)).first()
                if ext:
                    payload["contexts"]["external_stay"] = external_context(
                        ext, confirmed, include_allocations=True)
    duties = (db.query(MapDutyAssignment)
              .filter(MapDutyAssignment.location_id == location.id,
                      MapDutyAssignment.active.is_(True))
              .order_by(MapDutyAssignment.id).all())
    if role == "volunteer":
        duties = [d for d in duties if d.username == username]
    payload["duties"] = [duty_dict(d) for d in duties]
    if role == "volunteer":
        for ctx in payload["contexts"].values():
            ctx.pop("allocations", None)
            ctx.pop("rooms", None)
    return payload


# ------------------------------------------------------------- entity catalog --
def entity_catalog(db: Session) -> list[dict]:
    link_map = link_index(db)
    rows: list[dict] = []

    def add(entity_type: str, entity_id: str, name: str, detail: dict | None = None):
        link = link_map.get((entity_type, entity_id))
        rows.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "name": name,
            "location_type": entity_type,
            "mapped": link is not None,
            "location_id": link.location_id if link else None,
            "detail": detail or {},
        })

    blocks: dict[str, dict] = {}
    for room in db.query(HostelRoom).all():
        block = room.hostel or UNKNOWN
        agg = blocks.setdefault(block, {"rooms": 0, "beds": 0,
                                        "accessible_rooms": 0})
        agg["rooms"] += 1
        agg["beds"] += int(room.beds or 0)
        if room.accessible:
            agg["accessible_rooms"] += 1
    for block, detail in sorted(blocks.items()):
        add("hostel_block", block, f"Hostel {block}", detail)

    for ext in db.query(ExternalStay).order_by(ExternalStay.raw_id).all():
        add("external_stay", ext.raw_id, ext.property,
            {"beds": ext.beds, "distance_km": ext.distance_km})

    for venue in db.query(Venue).order_by(Venue.raw_id).all():
        add("venue", venue.raw_id, venue.name,
            {"capacity": venue.capacity, "location": venue.location})

    for vendor in db.query(Vendor).order_by(Vendor.raw_id).all():
        add("vendor", vendor.raw_id, vendor.name,
            {"capacity_per_day": vendor.capacity_per_day,
             "status": vendor.status})

    for label in sorted(inventory_labels(db)):
        add("inventory_location", label, label, {})

    for disruption in (db.query(Disruption)
                       .filter(Disruption.status.in_(("previewed", "applied")))
                       .order_by(Disruption.id.desc()).all()):
        add("incident", str(disruption.id),
            f"Incident #{disruption.id} — {disruption.type}",
            {"type": disruption.type, "status": disruption.status})
    return rows


def entity_coordinates(db: Session, entity_type: str,
                       entity_id: str) -> Optional[dict]:
    link = link_index(db).get((entity_type, entity_id))
    if link is None:
        return None
    loc = db.get(MapLocation, link.location_id)
    if loc is None:
        return None
    return {"location_id": loc.id, "latitude": loc.latitude,
            "longitude": loc.longitude, "name": loc.name,
            "verification": loc.coordinate_verification_status}


# ------------------------------------------------------------------ unmapped --
def unmapped_payload(db: Session, role: str, username: str) -> dict:
    visible, loc_links = visible_locations_for_user(db, role, username)
    visible_ids = {loc.id for loc in visible}
    link_map = link_index(db)
    no_coords = []
    unverified = []
    for loc in visible:
        if not location_mapped(loc):
            no_coords.append({
                "kind": "registry",
                "location_id": loc.id,
                "name": loc.name,
                "location_type": loc.location_type,
                "reason": "no_coordinates",
                "source_reference": loc.source_reference,
                "coordinate_verification_status": loc.coordinate_verification_status,
            })
        elif loc.coordinate_verification_status != "verified":
            unverified.append({
                "kind": "registry",
                "location_id": loc.id,
                "name": loc.name,
                "location_type": loc.location_type,
                "reason": "coordinates_unverified",
                "source_reference": loc.source_reference,
                "coordinate_verification_status": loc.coordinate_verification_status,
            })
    linked_entities = {(t, str(e)) for (t, e), link in link_map.items()
                       if link.location_id in visible_ids}
    if role not in ("viewer", "volunteer"):
        approved = _approved_types(role)
        for candidate in entity_catalog(db):
            if candidate["entity_type"] not in approved:
                continue
            if candidate["entity_type"] == "incident":
                continue
            key = (candidate["entity_type"], str(candidate["entity_id"]))
            if key in linked_entities or candidate["mapped"]:
                continue
            no_coords.append({
                "kind": "entity",
                "location_id": None,
                "entity_type": candidate["entity_type"],
                "entity_id": candidate["entity_id"],
                "name": candidate["name"],
                "location_type": candidate["location_type"],
                "reason": "not_mapped",
                "detail": candidate["detail"],
            })
    for item in no_coords:
        item["lat"] = None
    return {
        "total": len(no_coords),
        "unmapped": no_coords,
        "unverified": unverified,
        "unverified_total": len(unverified),
    }


# ------------------------------------------------------------------- listings --
def list_locations(db: Session, role: str, username: str,
                   search: str | None = None,
                   types: Iterable[str] | None = None,
                   statuses: Iterable[str] | None = None,
                   incident_only: bool = False,
                   at: str | None = None,
                   min_lat: float | None = None,
                   min_lng: float | None = None,
                   max_lat: float | None = None,
                   max_lng: float | None = None,
                   include_unmapped: bool = False,
                   limit: int = 200, offset: int = 0) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    visible, loc_links = visible_locations_for_user(db, role, username)
    confirmed = confirmed_allocations(db)
    bundle = conflict_bundle(db)
    incidents_all, _ = build_incidents(db, role)
    inc_by_loc = incidents_by_location(incidents_all)
    allowed_types = _approved_types(role)
    requested_types = {t.strip() for t in (types or []) if t} if types else set()

    rows = []
    for loc in visible:
        links = loc_links.get(loc.id, [])
        if requested_types and not (requested_types & ({loc.location_type} |
                                                       {l.entity_type for l in links}
                                                       )):
            continue
        payload = location_payload(db, loc, links, role, at_naive, at_aware,
                                   confirmed, bundle, inc_by_loc.get(loc.id, []))
        if not include_unmapped and not payload["mapped"]:
            continue
        if payload["coordinate_verification_status"] == "rejected" and \
                payload["mapped"]:
            continue
        if incident_only and not payload["has_incident"]:
            continue
        if statuses:
            wanted = {s.strip() for s in statuses if s}
            if payload["operational_status"]["code"] not in wanted:
                continue
        if search:
            needle = search.strip().lower()
            hay = " ".join([
                payload["name"] or "", payload["address"] or "",
                payload["campus_zone"] or "", payload["source_reference"] or "",
                *[f"{l['entity_id']} {l['label']}" for l in payload["links"]],
            ]).lower()
            if needle not in hay:
                continue
        if None not in (min_lat, min_lng, max_lat, max_lng) and payload["mapped"]:
            if not (min_lat <= payload["latitude"] <= max_lat and
                    min_lng <= payload["longitude"] <= max_lng):
                continue
        rows.append(payload)

    rows.sort(key=lambda r: ((r["name"] or "").lower(), r["id"]))
    total = len(rows)
    rows = rows[offset:offset + limit]
    return {"total": total, "limit": limit, "offset": offset,
            "locations": rows, **meta}


def map_summary(db: Session, role: str, username: str,
                at: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    visible, loc_links = visible_locations_for_user(db, role, username)
    confirmed = confirmed_allocations(db)
    bundle = conflict_bundle(db)
    incidents_all, unlocated = build_incidents(db, role)
    inc_by_loc = incidents_by_location(incidents_all)
    mapped = 0
    unverified = 0
    layers: dict[str, int] = defaultdict(int)
    statuses: dict[str, int] = defaultdict(int)
    incident_locations = set()
    for loc in visible:
        payload = location_payload(db, loc, loc_links.get(loc.id, []), role,
                                   at_naive, at_aware, confirmed, bundle,
                                   inc_by_loc.get(loc.id, []))
        if payload["mapped"]:
            mapped += 1
        if payload["coordinate_verification_status"] != "verified":
            unverified += 1
        for layer in payload["layers"]:
            layers[layer] += 1
        statuses[payload["operational_status"]["code"]] += 1
        if payload["has_incident"]:
            incident_locations.add(loc.id)
    unmap = unmapped_payload(db, role, username)
    summary: dict[str, Any] = {
        "mapped_locations": mapped,
        "registry_locations": len(visible),
        "unmapped_total": unmap["total"],
        "unverified_coordinates": unverified,
        "layers": dict(sorted(layers.items())),
        "status_counts": dict(sorted(statuses.items())),
        "incidents": {
            "active": sum(1 for i in incidents_all if i["verified"]),
            "potential": sum(1 for i in incidents_all if not i["verified"]),
            "affected_locations": len(incident_locations),
            "unlocated": len(unlocated),
        },
        "data_freshness": _data_freshness(db),
    }
    allowed = _approved_types(role)
    if role == "director" or "hostel_block" in allowed or "external_stay" in allowed:
        blocks, external = _accommodation_rows(db, role, confirmed, loc_links,
                                               at_naive, at_aware, inc_by_loc)
        allocation_plan = _active_plan_payload(db)
        total_beds = sum(b["totals"]["total_beds"] for b in blocks) + \
            sum(e["totals"]["beds"] for e in external)
        allocated = sum(b["totals"]["allocated_beds"] for b in blocks) + \
            sum(e["totals"]["allocated_beds"] for e in external)
        vacant = sum(b["totals"]["vacant_beds"] for b in blocks) + \
            sum(e["totals"]["vacant_beds"] for e in external)
        summary["accommodation"] = {
            "hostel_blocks": len(blocks),
            "external_properties": len(external),
            "total_beds": total_beds,
            "allocated_beds": allocated,
            "vacant_beds": vacant,
            "occupancy_pct": round((allocated / total_beds) * 100, 1)
            if total_beds else None,
            "active_plan": allocation_plan,
        }
    if role == "director" or "venue" in allowed:
        venues = db.query(Venue).all()
        contexts = [venue_context(db, v, at_naive, at_aware, bundle,
                                  include_ops=role in ("director", "events_lead"))
                    for v in venues]
        unscheduled = _unscheduled_events(db)
        summary["events"] = {
            "venues": len(venues),
            "ongoing": sum(len(c["current_events"]) for c in contexts),
            "upcoming": sum(len(c["upcoming_events"]) for c in contexts),
            "conflicts": len(bundle.get("conflicts", [])),
            "unscheduled": len(unscheduled),
            "available_venues": sum(1 for c in contexts
                                    if c["status"]["code"] == "available"),
        }
    if role == "director" or "inventory_location" in allowed:
        labels = sorted(inventory_labels(db))
        ctxs = [inventory_context(db, label) for label in labels]
        summary["logistics"] = {
            "stock_locations": len(labels),
            "items": sum(c["item_count"] for c in ctxs),
            "under_repair": sum(c["under_repair_quantity"] for c in ctxs),
            "empty_locations": sum(1 for c in ctxs
                                   if c["status"]["code"] == "empty"),
        }
    if role == "director" or "vendor" in allowed:
        vendors = db.query(Vendor).all()
        ctxs = [vendor_context(v, at_aware, include_finance=False)
                for v in vendors]
        summary["vendors"] = {
            "total": len(vendors),
            "serving": sum(1 for c in ctxs
                           if c["status"]["code"] == "available"),
            "interrupted": sum(1 for c in ctxs
                               if c["status"]["code"] == "interrupted"),
            "compliance_failed": sum(1 for c in ctxs
                                     if c["status"]["code"] == "compliance_failed"),
            "verified_compliant": sum(1 for c in ctxs
                                      if c["verified_compliant"]),
        }
    summary.update(meta)
    summary["role"] = role
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["can_manage_locations"] = role in C.MAP_MANAGER_ROLES
    return summary


def _unscheduled_events(db: Session) -> list[dict]:
    rows = (db.query(Event)
            .filter(or_(Event.venue_id.is_(None), Event.start_dt.is_(None),
                        Event.end_dt.is_(None))).order_by(Event.raw_id).all())
    out = []
    for event in rows:
        reasons = []
        if event.venue_id is None:
            reasons.append("no venue assignment")
        if event.start_dt is None or event.end_dt is None:
            reasons.append("no valid start/end time")
        elif event.end_dt <= event.start_dt:
            reasons.append("end is not after start")
        out.append({"id": event.id, "raw_id": event.raw_id, "name": event.name,
                    "reasons": reasons})
    return out


def _active_plan_payload(db: Session) -> dict | None:
    plan = (db.query(AllocationPlan)
            .filter(AllocationPlan.status == "active")
            .order_by(AllocationPlan.id.desc()).first())
    if plan is None:
        return None
    return {"id": plan.id, "preset": plan.preset,
            "summary": plan.summary or {},
            "unplaced": len(plan.unplaced or []),
            "activated_note": "only active-plan/audited override allocations count",
            "created_at": _iso(plan.created_at)}


def _data_freshness(db: Session) -> dict:
    latest_location = (db.query(MapLocation.updated_at)
                       .order_by(MapLocation.updated_at.desc()).first())
    latest_incident = (db.query(Disruption.updated_at)
                       .order_by(Disruption.updated_at.desc()).first())
    values = [v[0] for v in (latest_location, latest_incident) if v and v[0]]
    return {
        "last_location_update": _iso(max(values)) if values else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "FestOS operational database",
    }


# --------------------------------------------------- role-specific map datasets --
def _accommodation_rows(db: Session, role: str,
                        confirmed: list[Allocation],
                        loc_links: dict[int, list[MapLocationLink]],
                        at_naive: datetime, at_aware: datetime,
                        inc_by_loc: dict[int, list[dict]]) -> tuple[list, list]:
    link_map = link_index(db)
    blocks = []
    for block in sorted({r.hostel for r in db.query(HostelRoom).all() if r.hostel}):
        ctx = block_context(db, block, confirmed, include_rooms=False)
        link = link_map.get(("hostel_block", block))
        loc = db.get(MapLocation, link.location_id) if link else None
        incs = inc_by_loc.get(loc.id, []) if loc else []
        status = ctx["status"]
        if any(i["verified"] for i in incs):
            status = _status("incident", "Active operational incident", "critical")
        loc_payload = _location_stub(loc)
        blocks.append({
            "block": block,
            "name": loc.name if loc else f"Hostel {block}",
            "location": loc_payload,
            "mapped": bool(loc and location_mapped(loc)),
            "totals": {k: ctx[k] for k in
                       ("total_beds", "allocated_beds", "vacant_beds",
                        "unavailable_beds", "occupancy_pct", "rooms_total",
                        "accessible_rooms", "accessible_beds", "ready_rooms")},
            "floors": ctx["floors"],
            "status": status,
            "incidents": incs,
        })
    external = []
    for ext in db.query(ExternalStay).order_by(ExternalStay.raw_id).all():
        ctx = external_context(ext, confirmed)
        link = link_map.get(("external_stay", ext.raw_id))
        loc = db.get(MapLocation, link.location_id) if link else None
        incs = inc_by_loc.get(loc.id, []) if loc else []
        status = ctx["status"]
        if any(i["verified"] for i in incs):
            status = _status("incident", "Active operational incident", "critical")
        external.append({
            "raw_id": ext.raw_id,
            "name": loc.name if loc else ext.property,
            "location": _location_stub(loc),
            "mapped": bool(loc and location_mapped(loc)),
            "totals": {k: ctx[k] for k in
                       ("beds", "allocated_beds", "vacant_beds",
                        "occupancy_pct")},
            "transport_available": ext.transport_available,
            "distance_km": ext.distance_km,
            "status": status,
            "incidents": incs,
        })
    return blocks, external


def _location_stub(loc: MapLocation | None) -> dict | None:
    if loc is None:
        return None
    return {
        "id": loc.id, "name": loc.name, "latitude": loc.latitude,
        "longitude": loc.longitude, "address": loc.address,
        "campus_zone": loc.campus_zone,
        "coordinate_verification_status": loc.coordinate_verification_status,
        "last_verified_at": _iso(loc.last_verified_at),
    }


def accommodation_map(db: Session, role: str, username: str,
                      at: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    confirmed = confirmed_allocations(db)
    incidents_all, _ = build_incidents(db, role)
    inc_by_loc = incidents_by_location(incidents_all)
    loc_links = links_by_location(db)
    blocks, external = _accommodation_rows(db, role, confirmed, loc_links,
                                           at_naive, at_aware, inc_by_loc)
    unmapped = [{"kind": "hostel_block", "block": b["block"],
                 "name": b["name"], "reason": "not_mapped"}
                for b in blocks if not b["mapped"]]
    unmapped += [{"kind": "external_stay", "raw_id": e["raw_id"],
                  "name": e["name"], "reason": "not_mapped"}
                 for e in external if not e["mapped"]]
    plan = _active_plan_payload(db)
    return {
        "hostels": blocks,
        "blocks": blocks,
        "external_stays": external,
        "external": external,
        "unmapped": unmapped,
        "active_plan": plan,
        "shortage": {
            "has_active_plan": plan is not None,
            "unplaced_from_active_plan": plan["unplaced"] if plan else None,
            "note": "occupancy derives from active-plan and audited committed "
                    "allocations only; draft plans are ignored",
        },
        **meta,
    }


def events_map(db: Session, role: str, username: str,
               at: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    bundle = conflict_bundle(db)
    link_map = link_index(db)
    venues = []
    for venue in db.query(Venue).order_by(Venue.raw_id).all():
        ctx = venue_context(db, venue, at_naive, at_aware, bundle,
                            include_ops=role in ("director", "events_lead"))
        link = link_map.get(("venue", venue.raw_id))
        loc = db.get(MapLocation, link.location_id) if link else None
        venues.append({
            **ctx,
            "venue": {"id": venue.id, "raw_id": venue.raw_id,
                      "name": venue.name, "capacity": venue.capacity},
            "location": _location_stub(loc),
            "mapped": bool(loc and location_mapped(loc)),
        })
    return {
        "venues": venues,
        "unscheduled_events": _unscheduled_events(db),
        "conflicts": bundle.get("conflicts", []),
        "suggestions": bundle.get("suggestions", []),
        **meta,
    }


def logistics_map(db: Session, role: str, username: str,
                  at: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    link_map = link_index(db)
    locations = {loc.id: loc for loc in db.query(MapLocation).all()}
    rows = []
    for label in sorted(inventory_labels(db)):
        ctx = inventory_context(db, label)
        link = link_map.get(("inventory_location", label))
        loc = db.get(MapLocation, link.location_id) if link else None
        rows.append({
            **ctx,
            "location": _location_stub(loc),
            "mapped": bool(loc and location_mapped(loc)),
        })
    edges = movement_edges(db, {k: v.location_id for k, v in link_map.items()},
                           locations)
    return {"locations": rows, "movements": edges, **meta}


def vendors_map(db: Session, role: str, username: str,
                at: str | None = None) -> dict:
    at_aware, at_naive, meta = parse_selected_at(at)
    link_map = link_index(db)
    rows = []
    for vendor in db.query(Vendor).order_by(Vendor.raw_id).all():
        ctx = vendor_context(vendor, at_aware,
                             include_finance=role in ("director", "vendor_lead"))
        link = link_map.get(("vendor", vendor.raw_id))
        loc = db.get(MapLocation, link.location_id) if link else None
        rows.append({**ctx, "location": _location_stub(loc),
                     "mapped": bool(loc and location_mapped(loc))})
    return {"vendors": rows, **meta}


def incidents_map(db: Session, role: str, username: str) -> dict:
    mapped, unlocated = build_incidents(db, role)
    return {
        "incidents": mapped,
        "unlocated": unlocated,
        "counts": {
            "active": sum(1 for i in mapped if i["verified"]),
            "potential": sum(1 for i in mapped if not i["verified"]),
            "unlocated": len(unlocated),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "previewed disruptions are potential effects; only applied "
                "disruptions are verified operational impacts",
    }


# -------------------------------------------------------------------- duties --
def duty_dict(d: MapDutyAssignment) -> dict:
    return {"id": d.id, "username": d.username, "location_id": d.location_id,
            "task_type": d.task_type, "label": d.label,
            "starts_at": _iso(d.starts_at), "ends_at": _iso(d.ends_at),
            "active": bool(d.active), "created_by": d.created_by}


def duties_for(db: Session, role: str, username: str) -> list[dict]:
    q = db.query(MapDutyAssignment)
    if role != "director":
        q = q.filter(MapDutyAssignment.username == username)
    return [duty_dict(d) for d in q.order_by(MapDutyAssignment.id).all()]


# ------------------------------------------------------------ map settings ----
def get_map_settings(db: Session) -> dict:
    rule = db.query(ConfigRule).filter(ConfigRule.key == "MAP_CENTER").first()
    if rule is None or not rule.value:
        return {
            "configured": False,
            "center": {"latitude": C.MAP["FALLBACK_CENTER"][0],
                       "longitude": C.MAP["FALLBACK_CENTER"][1]},
            "zoom": C.MAP["FALLBACK_ZOOM"],
            "label": None,
            "note": "No festival map centre has been configured. The map opens "
                    "on a neutral country view; add the real site centre in "
                    "Location Management.",
            "updated_at": None,
        }
    value = rule.value or {}
    return {
        "configured": True,
        "center": {"latitude": value.get("latitude"),
                   "longitude": value.get("longitude")},
        "zoom": value.get("zoom", C.MAP["DEFAULT_ZOOM"]),
        "label": value.get("label"),
        "note": None,
        "updated_at": _iso(rule.updated_at),
    }


def set_map_settings(db: Session, latitude: float, longitude: float,
                     zoom: int, label: str | None, actor: str,
                     reason: str | None) -> dict:
    from app.audit import log_change
    rule = db.query(ConfigRule).filter(ConfigRule.key == "MAP_CENTER").first()
    before = rule.value if rule else None
    value = {"latitude": latitude, "longitude": longitude,
             "zoom": zoom, "label": label}
    if rule is None:
        rule = ConfigRule(key="MAP_CENTER", value=value,
                          description="Authorised festival map centre")
        db.add(rule)
    else:
        rule.value = value
    log_change(db, actor, "map_settings", "MAP_CENTER", before, value,
               reason or "map centre configured", kind="manual")
    db.commit()
    return get_map_settings(db)


# ------------------------------------------------------------ location writes --
def create_location(db: Session, actor: str, name: str, location_type: str,
                    latitude: float | None, longitude: float | None,
                    address: str | None, campus_zone: str | None,
                    parent_location_id: int | None, source_reference: str | None,
                    links: list[dict], reason: str | None) -> MapLocation:
    from app.audit import log_change
    if location_type not in C.MAP_LOCATION_TYPES:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                            f"unknown location_type '{location_type}'")
    if parent_location_id is not None and db.get(MapLocation, parent_location_id) is None:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                            "parent_location_id does not exist")
    loc = MapLocation(
        name=name.strip(), location_type=location_type,
        latitude=latitude, longitude=longitude, address=address,
        campus_zone=campus_zone, parent_location_id=parent_location_id,
        source_reference=source_reference,
        coordinate_verification_status="unverified",
    )
    db.add(loc)
    db.flush()
    _replace_links(db, loc, links, actor, reason)
    log_change(db, actor, "map_location", loc.id, None,
               _location_audit_payload(loc, _links_for(db, loc.id)),
               reason or "location created", kind="manual")
    db.commit()
    db.refresh(loc)
    return loc


def update_location(db: Session, loc: MapLocation, actor: str, changes: dict,
                    links: list[dict] | None, reason: str | None) -> MapLocation:
    from app.audit import log_change
    before = _location_audit_payload(loc, _links_for(db, loc.id))
    allowed = {"name", "location_type", "latitude", "longitude", "address",
               "campus_zone", "parent_location_id", "source_reference"}
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key == "location_type" and value not in C.MAP_LOCATION_TYPES:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                                f"unknown location_type '{value}'")
        setattr(loc, key, value)
    if "latitude" in changes or "longitude" in changes:
        loc.coordinate_verification_status = "unverified"
        loc.last_verified_at = None
    if links is not None:
        _replace_links(db, loc, links, actor, reason)
    after = _location_audit_payload(loc, _links_for(db, loc.id))
    log_change(db, actor, "map_location", loc.id, before, after,
               reason or "location updated", kind="manual")
    db.commit()
    db.refresh(loc)
    return loc


def verify_location(db: Session, loc: MapLocation, actor: str,
                    reason: str | None) -> MapLocation:
    from app.audit import log_change
    if loc.latitude is None or loc.longitude is None:
        raise HTTPException(http_status.HTTP_409_CONFLICT,
                            "cannot verify a location without coordinates")
    before = {"coordinate_verification_status":
              loc.coordinate_verification_status,
              "last_verified_at": _iso(loc.last_verified_at)}
    loc.coordinate_verification_status = "verified"
    loc.last_verified_at = now_utc()
    after = {"coordinate_verification_status": "verified",
             "last_verified_at": _iso(loc.last_verified_at)}
    log_change(db, actor, "map_location", loc.id, before, after,
               reason or "pin verified on site", kind="manual")
    db.commit()
    db.refresh(loc)
    return loc


def _links_for(db: Session, location_id: int) -> list[MapLocationLink]:
    return (db.query(MapLocationLink)
            .filter(MapLocationLink.location_id == location_id).all())


def _replace_links(db: Session, loc: MapLocation, links: list[dict],
                   actor: str, reason: str | None) -> None:
    from app.audit import log_change
    existing = {k: v for k, v in link_index(db).items()
                if v.location_id == loc.id}
    taken = link_index(db)
    wanted: dict[tuple[str, str], dict] = {}
    for raw in links:
        entity_type = str(raw.get("entity_type") or "").strip()
        entity_id = str(raw.get("entity_id") or "").strip()
        if entity_type not in C.MAP_ENTITY_TYPES:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                                f"unknown entity_type '{entity_type}'")
        if not entity_id:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST,
                                "entity_id is required for each link")
        if not entity_exists(db, entity_type, entity_id):
            raise HTTPException(http_status.HTTP_404_NOT_FOUND,
                                f"{entity_type} '{entity_id}' not found")
        key = (entity_type, entity_id)
        other = taken.get(key)
        if other is not None and other.location_id != loc.id:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"{entity_type} '{entity_id}' is already mapped to location "
                f"{other.location_id}")
        wanted[key] = raw

    for key, link in existing.items():
        if key not in wanted:
            log_change(db, actor, "map_location_link", link.id,
                       {"location_id": loc.id, "entity_type": key[0],
                        "entity_id": key[1]}, None,
                       reason or "location link removed", kind="manual")
            db.delete(link)
    db.flush()
    for key, raw in wanted.items():
        if key in existing:
            continue
        link = MapLocationLink(location_id=loc.id, entity_type=key[0],
                               entity_id=key[1])
        db.add(link)
        db.flush()
        log_change(db, actor, "map_location_link", link.id, None,
                   {"location_id": loc.id, "entity_type": key[0],
                    "entity_id": key[1]},
                   reason or "location link created", kind="manual")


def _location_audit_payload(loc: MapLocation,
                            links: list[MapLocationLink]) -> dict:
    return {
        "name": loc.name,
        "location_type": loc.location_type,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "address": loc.address,
        "campus_zone": loc.campus_zone,
        "parent_location_id": loc.parent_location_id,
        "source_reference": loc.source_reference,
        "coordinate_verification_status": loc.coordinate_verification_status,
        "last_verified_at": _iso(loc.last_verified_at),
        "links": [{"entity_type": l.entity_type, "entity_id": l.entity_id}
                  for l in links],
    }

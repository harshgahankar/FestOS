"""Disruption flow: preview -> apply (real DB state + revert snapshot) -> revert.

Everything audited. Apply stores `Disruption.revert_snapshot` with exactly what is
needed to restore the prior state; revert never guesses. Reuses the allocator for
hostel closure (displaced-only), the scheduler for venue change and the vendor
engine for shutdown rerouting.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.audit import log_change
from app.auth import require_role
from app.db import get_db
from app.models import (Allocation, CoreTeam, Disruption, Event,
                        EventStaff, ExternalStay, HostelRoom, InventoryItem,
                        InventoryMovement, MerchIssue, Participant, Registration,
                        Venue, Vendor, VendorOrder)
from engines import impact
from engines.allocator import _gender_class
from engines.inventory import stock_levels
from engines.scheduler import find_conflicts

router = APIRouter(prefix="/disruptions", tags=["disruptions"])

DISRUPTION_TYPES = ("late_contingent", "duplicate_record", "hostel_closure",
                    "equipment_failure", "venue_change", "vendor_shutdown",
                    "duplicate_merch_claim")


# ------------------------------------------------------------------ plumbing --
def _d(x):
    return x.isoformat() if hasattr(x, "isoformat") else x


def _parse_dt(v):
    return datetime.fromisoformat(v) if isinstance(v, str) and v else v


def _p_dict(p: Participant) -> dict:
    return {"id": p.id, "raw_id": p.raw_id, "name": p.name, "gender": p.gender,
            "contingent": p.contingent_id, "status": p.status,
            "merged_into": p.merged_into,
            "arrival": p.arrival_dt or "", "departure": p.departure_dt or "",
            "accommodation_requested": p.accommodation_requested or "",
            "accessibility_status": p.accessibility_status or "unknown",
            "accessibility_details": p.accessibility_details or "",
            "tshirt_size": p.tshirt_size or ""}


def _room_dict(r: HostelRoom) -> dict:
    return {"id": r.id, "raw_id": r.raw_id, "hostel": r.hostel, "floor": r.floor,
            "beds": r.beds, "accessible": r.accessible,
            "gender_block": r.gender_block, "readiness": r.readiness,
            "cleaning_until": r.cleaning_until, "status": r.status}


def _ext_dict(e: ExternalStay) -> dict:
    return {"id": e.id, "property": e.property, "beds": e.beds,
            "cost_per_bed_night": e.cost_per_bed_night,
            "transport_available": e.transport_available}


def _event_dict(e: Event) -> dict:
    return {"id": e.id, "raw_id": e.raw_id, "name": e.name,
            "duration_minutes": e.duration_minutes, "venue_id": e.venue_id,
            "start": e.start_dt, "end": e.end_dt, "setup_min": e.setup_min,
            "teardown_min": e.teardown_min,
            "volunteers_needed": e.volunteers_needed,
            "equipment_needs": e.equipment_needs or []}


def _venue_dict(v) -> dict:
    return {"id": v.id, "raw_id": v.raw_id, "name": v.name,
            "capacity": v.capacity,
            "availability_windows": v.availability_windows or []}


def _vendor_dict(v: Vendor) -> dict:
    return {"id": v.id, "raw_id": v.raw_id, "name": v.name,
            "dietary_coverage": v.dietary_coverage or [],
            "hygiene_cert_expiry": v.hygiene_cert_expiry,
            "capacity_per_day": v.capacity_per_day, "rate": v.rate,
            "status": v.status}


def _alloc_dict(a: Allocation) -> dict:
    return {"id": a.id, "participant_id": a.participant_id, "room_id": a.room_id,
            "external_stay_id": a.external_stay_id, "cost": a.cost or 0,
            "locked": a.locked, "source": a.source or "", "plan_id": a.plan_id,
            "version": a.version or 1, "reason": a.reason or "",
            "check_in": _d(a.check_in), "check_out": _d(a.check_out)}


def _active_allocations(db: Session) -> list:
    return db.query(Allocation).all()


def _item_label(db: Session, item_id: int) -> str:
    it = db.get(InventoryItem, item_id)
    return f"{it.name}|{it.size or 'UNKNOWN'}" if it else f"item:{item_id}"


def _sched_check(db: Session) -> dict:
    events = [_event_dict(e) for e in db.query(Event).all()]
    venues = [_venue_dict(v) for v in db.query(Venue).all()]
    regs = [{"participant": r.participant_raw_id,
             "event_raw_id": r.event_raw_id, "event_id": r.event_id}
            for r in db.query(Registration)
            .filter(Registration.status == "registered").all()]
    staff = [{"event_id": s.event_id, "core_team_id": s.core_team_id,
              "role": s.role} for s in db.query(EventStaff).all()]
    team = [{"id": t.id, "raw_id": t.raw_id, "name": t.name,
             "shift_start": t.shift_start, "shift_end": t.shift_end,
             "shift_crosses_midnight": t.shift_crosses_midnight}
            for t in db.query(CoreTeam).all()]
    return find_conflicts(events, venues, regs, staff, team)


def _summary(rep: dict) -> dict:
    r = rep["report"]
    return {"affected": r["affected"]["count"],
            "violations": len(r["new_violations"]),
            "cost_delta": r["cost_delta"]}


def _get_disruption(db: Session, disruption_id: int):
    d = db.get(Disruption, disruption_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"disruption {disruption_id} not found")
    return d


# -------------------------------------------------------------------- preview --
@router.post("/preview")
def preview(body: schemas.DisruptionIn,
            user=Depends(require_role("director")),
            db: Session = Depends(get_db)):
    _validate_type(body.type)
    fn = _PREVIEWS.get(body.type)
    if fn is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"no preview path for '{body.type}'")
    ctx = fn(db, body.payload)
    if ctx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "disruption target not found in the data")
    d = Disruption(type=body.type, payload=body.payload,
                   impact_report=ctx["report"], status="previewed")
    db.add(d)
    db.flush()
    log_change(db, user.username, "disruption", d.id, None,
               {"type": body.type, "payload": body.payload,
                "summary": _summary(ctx)},
               body.payload.get("reason") or "preview requested", kind="manual")
    db.commit()
    return {"disruption_id": d.id, "type": body.type, "report": ctx["report"],
            "report_id": d.id,
            "next": f"POST /disruptions/{d.id}/apply"}


def _validate_type(dtype: str) -> None:
    if dtype not in DISRUPTION_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"unknown disruption type '{dtype}'; "
                            f"one of {', '.join(DISRUPTION_TYPES)}")


# ---------------------------------------------------------------------- apply --
@router.post("/{disruption_id}/apply")
def apply(disruption_id: int, body: schemas.ReasonIn,
          user=Depends(require_role("director")),
          db: Session = Depends(get_db)):
    d = _get_disruption(db, disruption_id)
    if d.status != "previewed":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"disruption is {d.status}; only previewed rows apply")
    applier = _APPLIERS.get(d.type)
    if applier is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"no apply path for '{d.type}'")
    result = applier(db, user, d, body.reason)
    d.status = "applied"
    d.applied_by = user.username
    d.applied_at = datetime.utcnow()
    d.revert_snapshot = result["snapshot"]
    log_change(db, user.username, "disruption", d.id, None,
               {"snapshot_keys": sorted(result["snapshot"].keys()),
                "summary": result["summary"]},
               body.reason or "disruption applied", kind="override")
    db.commit()
    return {"disruption_id": d.id, "type": d.type, "status": d.status,
            "summary": result["summary"]}


# --------------------------------------------------------------------- revert --
@router.post("/{disruption_id}/revert")
def revert(disruption_id: int, body: schemas.ReasonIn,
           user=Depends(require_role("director")),
           db: Session = Depends(get_db)):
    d = _get_disruption(db, disruption_id)
    if d.status != "applied":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"disruption is {d.status}; only applied rows revert")
    if not d.revert_snapshot:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "no revert snapshot stored; refusing to guess")
    reverter = _REVERTERS.get(d.type)
    if reverter is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"no revert path for '{d.type}'")
    restored = reverter(db, user, d, body.reason)
    d.status = "reverted"
    log_change(db, user.username, "disruption", d.id, {"status": "applied"},
               {"status": "reverted", "restored": restored,
                "type": d.type},
               body.reason or "disruption reverted", kind="override")
    db.commit()
    return {"disruption_id": d.id, "type": d.type, "status": d.status,
            "restored": restored}


@router.get("")
def list_disruptions(user=Depends(require_role("director")),
                     db: Session = Depends(get_db)):
    rows = (db.query(Disruption).order_by(Disruption.id.desc()).all())
    return {"total": len(rows), "disruptions": [{
        "id": r.id, "type": r.type, "status": r.status, "payload": r.payload,
        "impact_report": r.impact_report, "applied_by": r.applied_by,
        "applied_at": _d(r.applied_at),
        "has_snapshot": r.revert_snapshot is not None} for r in rows]}


# ==================================================================== TYPE 1 ==
# late contingent: shift member arrivals/departures + aligned bed windows
def _pv_late_contingent(db: Session, payload: dict) -> dict:
    raw = payload.get("contingent") or payload.get("contingent_id")
    members = (db.query(Participant)
               .filter(Participant.contingent_id == raw,
                       Participant.status.in_(("active", "flagged")),
                       Participant.merged_into.is_(None))
               .all() if raw else [])
    if not members:
        return None
    if not payload.get("new_arrival"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "new_arrival (ISO datetime) is required")
    regs = db.query(Registration).filter(
        Registration.participant_id.in_([m.id for m in members])).all()
    events = [_event_dict(e) for e in db.query(Event).all()]
    return impact.late_contingent_preview(
        [_p_dict(m) for m in members],
        [{"event_raw_id": r.event_raw_id} for r in regs],
        events, payload["new_arrival"])


def _ap_late_contingent(db: Session, user, d, reason: str) -> dict:
    raw = d.payload.get("contingent") or d.payload.get("contingent_id")
    members = (db.query(Participant)
               .filter(Participant.contingent_id == raw,
                       Participant.status.in_(("active", "flagged")),
                       Participant.merged_into.is_(None)).all())
    arrivals = [m.arrival_dt for m in members if m.arrival_dt]
    latest = max(arrivals) if arrivals else None
    new_dt = _parse_dt(d.payload.get("new_arrival"))
    snap = {"participants": [], "allocations": []}
    if latest is None or new_dt is None or new_dt == latest:
        return {"snapshot": snap, "summary": {"shift": "none needed"}}
    delta = new_dt - latest
    for m in members:
        old_a = m.arrival_dt.isoformat() if m.arrival_dt else None
        old_d = m.departure_dt.isoformat() if m.departure_dt else None
        if m.arrival_dt is not None:
            m.arrival_dt = m.arrival_dt + delta
        if m.departure_dt is not None:
            m.departure_dt = m.departure_dt + delta
        snap["participants"].append({"id": m.id, "arrival": old_a,
                                     "departure": old_d})
        log_change(db, user.username, "participant", m.id,
                   {"arrival": old_a, "departure": old_d},
                   {"arrival": _d(m.arrival_dt), "departure": _d(m.departure_dt)},
                   reason or "contingent arrives late (disruption)",
                   kind="override")
        for a in db.query(Allocation).filter(Allocation.participant_id == m.id).all():
            if a.check_in is not None or a.check_out is not None:
                snap["allocations"].append(
                    {"id": a.id, "check_in": _d(a.check_in),
                     "check_out": _d(a.check_out)})
                if a.check_in is not None:
                    a.check_in = a.check_in + delta
                if a.check_out is not None:
                    a.check_out = a.check_out + delta
    return {"snapshot": snap,
            "summary": {"members_shifted": len(members),
                        "shift_hours": round(delta.total_seconds() / 3600.0, 1)}}


def _rv_late_contingent(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    n = 0
    for p in snap.get("participants", []):
        m = db.get(Participant, p["id"])
        if m is not None:
            m.arrival_dt = _parse_dt(p["arrival"])
            m.departure_dt = _parse_dt(p["departure"])
            n += 1
    for s in snap.get("allocations", []):
        a = db.get(Allocation, s["id"])
        if a is not None:
            a.check_in = _parse_dt(s["check_in"])
            a.check_out = _parse_dt(s["check_out"])
    return {"participants_restored": n}


# ==================================================================== TYPE 2 ==
# duplicate record: merge found post-import; reversible
def _pv_duplicate_record(db: Session, payload: dict) -> dict:
    craw = payload.get("canonical_raw_id") or payload.get("canonical")
    draw = payload.get("duplicate_raw_id") or payload.get("duplicate")
    if not draw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "duplicate_raw_id is required")
    dup = db.query(Participant).filter(Participant.raw_id == draw).first()
    if dup is None:
        return None
    canon = None
    if craw:
        canon = db.query(Participant).filter(Participant.raw_id == craw).first()
    regs = db.query(Registration).filter(Registration.participant_id == dup.id).all()
    return impact.duplicate_record_preview(
        _p_dict(canon) if canon else None, _p_dict(dup),
        [{"event_raw_id": r.event_raw_id} for r in regs])


def _ap_duplicate_record(db: Session, user, d, reason: str) -> dict:
    craw = d.payload.get("canonical_raw_id") or d.payload.get("canonical")
    draw = d.payload.get("duplicate_raw_id") or d.payload.get("duplicate")
    if not (craw and draw):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "canonical_raw_id and duplicate_raw_id are required")
    canon = db.query(Participant).filter(Participant.raw_id == craw).first()
    dup = db.query(Participant).filter(Participant.raw_id == draw).first()
    if canon is None or dup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "canonical/duplicate missing")
    if dup.id == canon.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "cannot link a record into itself")
    before = {"status": dup.status, "merged_into": dup.merged_into,
              "flags": list(dup.quality_flags or [])}
    dup.merged_into = canon.id
    dup.status = "duplicate"
    dup.quality_flags = sorted(set((dup.quality_flags or []) +
                                   ["DUPLICATE_LINKED", "MERGED_MANUAL"]))
    log_change(db, user.username, "participant", dup.id, before,
               {"status": "duplicate", "merged_into": canon.raw_id},
               reason or "post-import duplicate link (disruption)", kind="override")
    beds_moved = 0
    alloc_snap = []
    for a in db.query(Allocation).filter(Allocation.participant_id == dup.id).all():
        alloc_snap.append(_alloc_dict(a))
        a.participant_id = canon.id
        beds_moved += 1
        log_change(db, user.username, "allocation", a.id,
                   {"participant_id": alloc_snap[-1]["participant_id"]},
                   {"participant_id": canon.id},
                   "bed moves to canonical after dup link", kind="override")
    return {"snapshot": {"duplicate_id": dup.id, "canonical_id": canon.id,
                         "was": before, "allocations": alloc_snap},
            "summary": {"merged": dup.raw_id, "into": canon.raw_id,
                        "beds_moved": beds_moved}}


def _rv_duplicate_record(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    dup = db.get(Participant, snap.get("duplicate_id"))
    if dup is None:
        return {"nothing": True}
    was = snap.get("was") or {}
    dup.status = was.get("status") or "active"
    dup.merged_into = was.get("merged_into")
    flags = [f for f in (dup.quality_flags or [])
             if f not in ("DUPLICATE_LINKED", "MERGED_MANUAL")]
    dup.quality_flags = sorted(set(flags))
    log_change(db, user.username, "participant", dup.id,
               {"status": "duplicate"}, {"status": dup.status},
               reason or "revert duplicate link", kind="override")
    restored_beds = 0
    for a_dict in snap.get("allocations", []):
        a = db.get(Allocation, a_dict["id"])
        if a is not None and a.participant_id == snap.get("canonical_id"):
            a.participant_id = dup.id
            restored_beds += 1
    return {"unmerged": dup.raw_id, "beds_restored": restored_beds}


# ==================================================================== TYPE 3 ==
# hostel closure: displaced-only allocation via the allocator with initial occupancy
def _closure_rooms(db: Session, payload: dict) -> list:
    q = db.query(HostelRoom)
    if payload.get("hostel") or payload.get("block"):
        return q.filter(HostelRoom.hostel.in_(
            [payload.get("hostel") or payload.get("block")])).all()
    if payload.get("room_raw_ids"):
        return q.filter(HostelRoom.raw_id.in_(payload["room_raw_ids"])).all()
    raise HTTPException(status.HTTP_400_BAD_REQUEST,
                        "payload needs 'hostel' (block) or 'room_raw_ids'")


def _closure_context(db: Session, payload: dict):
    closed = _closure_rooms(db, payload)
    if not closed:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "no rooms match this closure")
    closed_ids = {r.id for r in closed}
    allocations = _active_allocations(db)
    displaced, locked_in = [], []
    current_taken, room_contingents = {}, {}
    for a in allocations:
        if a.room_id is None:
            continue
        if a.room_id in closed_ids and a.locked:
            occ = db.get(Participant, a.participant_id)
            locked_in.append({"participant_id": a.participant_id,
                              "raw_id": occ.raw_id if occ else None,
                              "room_id": a.room_id,
                              "room_raw": db.get(HostelRoom, a.room_id).raw_id})
        current_taken[a.room_id] = current_taken.get(a.room_id, 0) + 1
        occ2 = db.get(Participant, a.participant_id)
        if occ2 is not None and occ2.contingent_id:
            room_contingents.setdefault(a.room_id, occ2.contingent_id)
        if a.room_id in closed_ids and not a.locked:
            occ3 = db.get(Participant, a.participant_id)
            displaced.append({"alloc": _alloc_dict(a), "person": occ3})
    return closed, displaced, locked_in, current_taken, room_contingents


def _pv_hostel_closure(db: Session, payload: dict) -> dict:
    closed, displaced, locked_in, current_taken, room_contingents = \
        _closure_context(db, payload)
    closed_ids = {r.id for r in closed}
    rooms_open = [_room_dict(r) for r in db.query(HostelRoom)
                  .filter(HostelRoom.id.notin_(closed_ids)).all()]
    exts = [_ext_dict(e) for e in db.query(ExternalStay).all()]
    ext_taken, ext_cohorts = {}, {}
    for a in _active_allocations(db):
        if a.external_stay_id is not None:
            occ = db.get(Participant, a.participant_id)
            g = _gender_class(_p_dict(occ)) if occ is not None else "review"
            ext_cohorts.setdefault(a.external_stay_id, g)
            ext_taken[a.external_stay_id] = ext_taken.get(a.external_stay_id, 0) + 1
    engine_ppl = []
    for d in displaced:
        pd = _p_dict(d["person"])
        pd["old_cost"] = d["alloc"]["cost"]
        pd["old_room"] = d["alloc"]["room_id"]
        engine_ppl.append(pd)
    return impact.hostel_closure_preview(
        engine_ppl, rooms_open, exts,
        {k: v for k, v in current_taken.items() if k not in closed_ids},
        ext_taken, ext_cohorts, room_contingents, locked_in,
        closed_room_raws=[r.raw_id for r in closed])


def _ap_hostel_closure(db: Session, user, d, reason: str) -> dict:
    ctx = _pv_hostel_closure(db, d.payload)
    closed = _closure_rooms(db, d.payload)
    closed_ids = {r.id: r.raw_id for r in closed}
    _, displaced, locked_in, _, _ = _closure_context(db, d.payload)
    snap = {"room_ids": list(closed_ids.keys()), "room_statuses": {},
            "old_allocations": [], "created_allocation_ids": []}
    allocations = db.query(Allocation).all()
    displaced_alloc_ids = {d0["alloc"]["id"] for d0 in displaced}
    for a in allocations:
        if a.id in displaced_alloc_ids:
            snap["old_allocations"].append(_alloc_dict(a))
    for r in closed:
        snap["room_statuses"][r.id] = r.status
        r.status = "closed"
        log_change(db, user.username, "hostel_room", r.id, {"status": r.status},
                   {"status": "closed"}, reason or "hostel closure",
                   kind="override")
    for aid in displaced_alloc_ids:
        a = db.get(Allocation, aid)
        db.delete(a)
        log_change(db, user.username, "allocation", aid,
                   {"room_id": a.room_id}, None,
                   "displaced by hostel closure; rehousing follows",
                   kind="override")
    placed = 0
    for a in ctx["plan"]["assignments"]:
        row = Allocation(participant_id=a["participant_id"], room_id=a["room_id"],
                         external_stay_id=a["external_stay_id"],
                         check_in=_parse_dt(a.get("check_in")),
                         check_out=_parse_dt(a.get("check_out")),
                         reason="rehoused after hostel closure", locked=False,
                         plan_id=None, source="disruption", cost=a["cost"])
        db.add(row)
        db.flush()
        snap["created_allocation_ids"].append(row.id)
        placed += 1
        log_change(db, user.username, "allocation", row.id, None,
                   {"participant": a.get("raw_id"), "room_id": a["room_id"],
                    "external_stay_id": a["external_stay_id"]},
                   "rehouse after hostel closure", kind="override")
    return {"snapshot": snap,
            "summary": {"rooms_closed": len(closed), "displaced": len(displaced),
                        "rehoused": placed, "locked_left_untouched": len(locked_in),
                        "cost_delta": ctx["report"]["cost_delta"]}}


def _rv_hostel_closure(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    for r in snap.get("room_ids", []):
        room = db.get(HostelRoom, r)
        if room is not None:
            statuses = snap.get("room_statuses") or {}
            room.status = statuses.get(str(r), statuses.get(r, room.status))
    for aid in snap.get("created_allocation_ids", []):
        row = db.get(Allocation, aid)
        if row is not None:
            db.delete(row)
    restored = 0
    for orig in snap.get("old_allocations", []):
        row = db.get(Allocation, orig["id"])
        if row is None:
            db.add(Allocation(id=orig["id"],
                              participant_id=orig["participant_id"],
                              room_id=orig["room_id"],
                              external_stay_id=orig["external_stay_id"],
                              check_in=_parse_dt(orig["check_in"]),
                              check_out=_parse_dt(orig["check_out"]),
                              reason=orig["reason"], locked=orig["locked"],
                              plan_id=orig["plan_id"], version=orig["version"],
                              source=orig["source"], cost=orig["cost"]))
            restored += 1
        else:
            row.participant_id = orig["participant_id"]
            row.room_id = orig["room_id"]
            restored += 1
    db.flush()
    return {"rooms_reopened": len(snap.get("room_ids", [])),
            "allocations_restored": restored}


# ==================================================================== TYPE 4 ==
# equipment failure: movement out of the ledger + scheduler demand re-check
def _pv_equipment_failure(db: Session, payload: dict) -> dict:
    item = None
    if payload.get("sku"):
        item = db.query(InventoryItem).filter(
            InventoryItem.sku == payload["sku"]).first()
    if item is None and payload.get("item_id"):
        item = db.get(InventoryItem, payload["item_id"])
    if item is None:
        return None
    if payload.get("qty") in (None, 0):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "payload needs a qty")
    movs = [{"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()]
    levels = stock_levels([{"id": item.id, "sku": item.sku}], movs)
    events = [_event_dict(e) for e in db.query(Event).all()]
    ref = f"failure-{item.sku}-{d_id(payload)}"
    return impact.equipment_failure_preview(
        {"id": item.id, "sku": item.sku, "name": item.name},
        payload.get("qty", 1), events, levels.get(item.id, 0), ref)


def d_id(payload) -> str:
    return str(payload.get("reason") or "preview").replace(" ", "-")[:12]


def _ap_equipment_failure(db: Session, user, d, reason: str) -> dict:
    item = None
    if d.payload.get("sku"):
        item = db.query(InventoryItem).filter(
            InventoryItem.sku == d.payload["sku"]).first()
    else:
        item = db.get(InventoryItem, d.payload.get("item_id"))
    qty = -abs(d.payload.get("qty", 1))
    ref = f"failure-{item.sku}-{d_id(d.payload)}"
    mv = InventoryMovement(item_id=item.id, qty=qty, status="damaged",
                           to_location=None, reference=ref, actor=user.username)
    db.add(mv)
    db.flush()
    log_change(db, user.username, "inventory_movement", mv.id, None,
               {"item": item.sku, "qty": qty, "status": "damaged",
                "reference": ref},
               reason or "equipment failure", kind="override")
    recheck = _sched_check(db)
    con = [c for c in recheck["conflicts"] if c.get("type") == "EQUIPMENT_SHORTAGE" or
           (c.get("sku") and item.sku in str(c.get("message", "")))]
    return {"snapshot": {"movement_id": mv.id},
            "summary": {"item": item.sku, "lost": -qty,
                        "conflicts_after": con}}


def _rv_equipment_failure(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    mv = db.get(InventoryMovement, snap.get("movement_id"))
    if mv is not None:
        db.delete(mv)
    return {"movement_removed": snap.get("movement_id")}


# ==================================================================== TYPE 5 ==
# venue change: move event + scheduler recheck
def _target_event(db: Session, payload: dict):
    e = db.query(Event).filter(
        Event.raw_id == (payload.get("event_raw_id") or "")).first()
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"event {payload.get('event_raw_id')} not found")
    return e


def _pv_venue_change(db: Session, payload: dict) -> dict:
    e = _target_event(db, payload)
    if not payload.get("new_venue_id"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "new_venue_id is required")
    new_v = db.get(Venue, payload["new_venue_id"])
    if new_v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"venue {payload['new_venue_id']} not found")
    old_v = db.get(Venue, e.venue_id) if e.venue_id else None
    if old_v is not None and new_v.id == old_v.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "venue is not changing")
    regs = db.query(Registration).filter(
        Registration.event_id == e.id,
        Registration.status == "registered").count()
    staff = db.query(EventStaff).filter(EventStaff.event_id == e.id).count()
    others = [_event_dict(x) for x in db.query(Event).all()]
    return impact.venue_change_preview(
        _event_dict(e), _venue_dict(old_v) if old_v else None,
        _venue_dict(new_v), others, regs, staff)


def _ap_venue_change(db: Session, user, d, reason: str) -> dict:
    e = _target_event(db, d.payload)
    new_v = db.get(Venue, d.payload.get("new_venue_id"))
    old_venue_id = e.venue_id
    e.venue_id = new_v.id
    log_change(db, user.username, "event", e.id, {"venue_id": old_venue_id},
               {"venue_id": new_v.id}, reason or "venue change (disruption)",
               kind="override")
    recheck = _sched_check(db)
    ev_conflicts = [c for c in recheck["conflicts"]
                    if e.raw_id in (c.get("event_1"), c.get("event_2"),
                                    c.get("event"))]
    return {"snapshot": {"event_id": e.id, "old_venue_id": old_venue_id},
            "summary": {"event": e.raw_id, "venue": new_v.raw_id,
                        "conflicts_after": ev_conflicts}}


def _rv_venue_change(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    e = db.get(Event, snap.get("event_id"))
    if e is not None:
        e.venue_id = snap.get("old_venue_id")
    return {"event_restored": e.raw_id if e else None}


# ==================================================================== TYPE 6 ==
# vendor shutdown: reroute open orders (vendor engine)
def _target_vendor(db: Session, payload: dict) -> Vendor:
    vid = payload.get("vendor_id")
    if vid is not None:
        v = db.get(Vendor, vid)
    else:
        vid = payload.get("raw_id") or payload.get("vendor_raw_id")
        v = db.query(Vendor).filter(Vendor.raw_id == vid).first()
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vendor not found")
    if v.status == "interrupted":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "vendor already interrupted")
    return v


def _pv_vendor_shutdown(db: Session, payload: dict) -> dict:
    v = _target_vendor(db, payload)
    others = [_vendor_dict(x) for x in db.query(Vendor)
              .filter(Vendor.id != v.id).all()]
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "day": o.day, "meal": o.meal,
               "qty": o.qty, "dietary_tag": o.dietary_tag, "paid": o.paid}
              for o in db.query(VendorOrder)
              .filter(VendorOrder.vendor_id == v.id).all()]
    return impact.vendor_shutdown_preview(_vendor_dict(v), others, orders)


def _ap_vendor_shutdown(db: Session, user, d, reason: str) -> dict:
    v = _target_vendor(db, d.payload)
    others = [_vendor_dict(x) for x in db.query(Vendor)
              .filter(Vendor.id != v.id).all()]
    order_rows = db.query(VendorOrder).filter(
        VendorOrder.vendor_id == v.id).all()
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "day": o.day, "meal": o.meal,
               "qty": o.qty, "dietary_tag": o.dietary_tag, "paid": o.paid}
              for o in order_rows]
    plan = impact.vendor_shutdown_preview(
        _vendor_dict(v), others, orders)["reroute"]
    snap = {"old_status": v.status, "orders_moved": []}
    for m in plan["moves"]:
        order = db.get(VendorOrder, m["order"])
        snap["orders_moved"].append({"id": order.id, "from_vendor": order.vendor_id})
        order.vendor_id = m["to_vendor"]
        log_change(db, user.username, "vendor_order", order.id,
                   {"vendor_id": v.id}, {"vendor_id": m["to_vendor"]},
                   "rerouted after vendor shutdown", kind="override")
    v.status = "interrupted"
    log_change(db, user.username, "vendor", v.id, {"status": snap["old_status"]},
               {"status": "interrupted"},
               reason or "vendor shutdown (disruption)", kind="override")
    return {"snapshot": snap,
            "summary": {"moved": len(snap["orders_moved"]),
                        "unmet": len(plan["unmet"])}}


def _rv_vendor_shutdown(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    v = db.get(Vendor, d.payload.get("vendor_id")) \
        if d.payload.get("vendor_id") is not None else \
        db.query(Vendor).filter(
            Vendor.raw_id == (d.payload.get("raw_id") or
                              d.payload.get("vendor_raw_id"))).first()
    if v is not None:
        v.status = snap.get("old_status") or "active"
    restored = 0
    for m in snap.get("orders_moved", []):
        order = db.get(VendorOrder, m["id"])
        if order is not None:
            order.vendor_id = m["from_vendor"]
            restored += 1
    return {"vendor_status": v.status if v else None,
            "orders_restored": restored}


# ==================================================================== TYPE 7 ==
# duplicate merch claim: flag + refuse/reissue handling
def _pv_duplicate_merch_claim(db: Session, payload: dict) -> dict:
    praw = payload.get("participant_raw_id") or payload.get("raw_id")
    p = db.query(Participant).filter(Participant.raw_id == praw).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"participant {praw} not found")
    canonical_id = p.merged_into or p.id
    canonical = db.get(Participant, canonical_id)
    cluster_ids = [canonical_id] + [c.id for c in db.query(Participant)
                                    .filter(Participant.merged_into == canonical_id)
                                    .all()]
    prior = db.query(MerchIssue).filter(
        MerchIssue.canonical_participant_id.in_(cluster_ids)).all()
    item = None
    if payload.get("item_id") is not None:
        item = db.get(InventoryItem, payload["item_id"])
    elif prior:
        item = db.get(InventoryItem, prior[0].item_id)
    return impact.duplicate_merch_claim_preview(
        _p_dict(p), _p_dict(canonical),
        [{"id": i.id, "item": _item_label(db, i.item_id)} for i in prior],
        {"id": item.id, "sku": item.sku} if item else None)


def _ap_duplicate_merch_claim(db: Session, user, d, reason: str) -> dict:
    praw = d.payload.get("participant_raw_id") or d.payload.get("raw_id")
    p = db.query(Participant).filter(Participant.raw_id == praw).first()
    canonical_id = p.merged_into or p.id
    action = d.payload.get("action") or "refuse"
    flags_before = list(p.quality_flags or [])
    p.quality_flags = sorted(set((p.quality_flags or []) + ["DUPLICATE_MERCH_CLAIM"]))
    reissue_id = None
    if action == "reissue":
        if user.role != "director":
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "only a director may force a re-issue")
        item = db.get(InventoryItem, d.payload.get("item_id")) \
            if d.payload.get("item_id") is not None else None
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "reissue requires item_id")
        mv = InventoryMovement(item_id=item.id, qty=-1,
                               from_location="merch store", to_location=p.raw_id,
                               actor=user.username)
        db.add(mv)
        issue = MerchIssue(participant_id=p.id,
                           canonical_participant_id=canonical_id,
                           item_id=item.id, issued_by=user.username)
        db.add(issue)
        db.flush()
        reissue_id = issue.id
        log_change(db, user.username, "merch_issue", issue.id, None,
                   {"participant": p.raw_id, "item": item.sku, "forced": True},
                   reason or "director accepted duplicate claim",
                   kind="override")
    log_change(db, user.username, "participant", p.id, {"flags": flags_before},
               {"flags": p.quality_flags, "action": action,
                "canonical_id": canonical_id},
               reason or "duplicate merch claim handling", kind="override")
    return {"snapshot": {"participant_id": p.id, "flags_before": flags_before,
                         "reissue_issue_id": reissue_id},
            "summary": {"participant": p.raw_id, "action": action}}


def _rv_duplicate_merch_claim(db: Session, user, d, reason: str) -> dict:
    snap = d.revert_snapshot or {}
    p = db.get(Participant, snap.get("participant_id"))
    if p is not None:
        p.quality_flags = list(snap.get("flags_before") or [])
    reissue_id = snap.get("reissue_issue_id")
    reverted_issue = None
    if reissue_id:
        issue = db.get(MerchIssue, reissue_id)
        if issue is not None:
            mv = (db.query(InventoryMovement)
                  .filter(InventoryMovement.item_id == issue.item_id,
                          InventoryMovement.qty == -1,
                          InventoryMovement.to_location == p.raw_id)
                  .order_by(InventoryMovement.id.desc())
                  .first() if p is not None else None)
            if mv is not None:
                db.delete(mv)
            db.delete(issue)
            reverted_issue = reissue_id
    return {"flags_restored": True, "reissue_reverted": reverted_issue}


# ----------------------------------------------------------------- registry --
_PREVIEWS = {
    "late_contingent": _pv_late_contingent,
    "duplicate_record": _pv_duplicate_record,
    "hostel_closure": _pv_hostel_closure,
    "equipment_failure": _pv_equipment_failure,
    "venue_change": _pv_venue_change,
    "vendor_shutdown": _pv_vendor_shutdown,
    "duplicate_merch_claim": _pv_duplicate_merch_claim,
}
_APPLIERS = {
    "late_contingent": _ap_late_contingent,
    "duplicate_record": _ap_duplicate_record,
    "hostel_closure": _ap_hostel_closure,
    "equipment_failure": _ap_equipment_failure,
    "venue_change": _ap_venue_change,
    "vendor_shutdown": _ap_vendor_shutdown,
    "duplicate_merch_claim": _ap_duplicate_merch_claim,
}
_REVERTERS = {
    "late_contingent": _rv_late_contingent,
    "duplicate_record": _rv_duplicate_record,
    "hostel_closure": _rv_hostel_closure,
    "equipment_failure": _rv_equipment_failure,
    "venue_change": _rv_venue_change,
    "vendor_shutdown": _rv_vendor_shutdown,
    "duplicate_merch_claim": _rv_duplicate_merch_claim,
}

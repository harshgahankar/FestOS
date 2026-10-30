from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.models import (Allocation, AllocationPlan, ExternalStay, HostelRoom, Participant)
from app.audit import log_change
from app.auth import require_role

router = APIRouter(prefix="/accommodation", tags=["accommodation"])


def _participant_dicts(db: Session) -> list[dict]:
    out = []
    for p in db.query(Participant).filter(Participant.merged_into.is_(None)).all():
        out.append({
            "id": p.id, "raw_id": p.raw_id, "name": p.name, "gender": p.gender,
            "contingent": p.contingent_id,
            "arrival": p.arrival_dt, "departure": p.departure_dt,
            "accommodation_requested": p.accommodation_requested,
            "accessibility_status": p.accessibility_status or "unknown",
            "accessibility_details": p.accessibility_details,
        })
    return out


def _room_dicts(db: Session) -> list[dict]:
    return [{"id": r.id, "raw_id": r.raw_id, "hostel": r.hostel, "floor": r.floor,
             "beds": r.beds, "accessible": r.accessible, "gender_block": r.gender_block,
             "readiness": r.readiness, "cleaning_until": r.cleaning_until,
             "status": r.status}
            for r in db.query(HostelRoom).all()]


def _ext_dicts(db: Session) -> list[dict]:
    return [{"id": e.id, "property": e.property, "beds": e.beds,
             "cost_per_bed_night": e.cost_per_bed_night,
             "transport_available": e.transport_available}
            for e in db.query(ExternalStay).all()]


def _plan_summary(plan: dict) -> dict:
    return {"requested": plan["shortage"]["requested_count"],
            "hostel_beds_used": plan["shortage"]["hostel_beds_used"],
            "external_beds_used": plan["shortage"]["external_beds_used"],
            "review_queue": len(plan["review_queue"]),
            "unplaced": len(plan["unplaced"]),
            "violations": len(plan["violations"]),
            "cost": plan["cost"]}


@router.post("/allocate")
def allocate(body: schemas.AllocateIn,
             user=Depends(require_role("director", "accommodation_lead")),
             db: Session = Depends(get_db)):
    """Run the greedy allocator for a preset; stores a draft plan (does not touch beds)."""
    from engines.allocator import allocate as run_engine

    plan = run_engine(_participant_dicts(db), _room_dicts(db), _ext_dicts(db),
                      preset=body.preset)
    saved = AllocationPlan(preset=plan["preset"], created_by=user.username,
                           summary=_plan_summary(plan), violations=plan["violations"],
                           relaxations=plan["relaxations"], unplaced=plan["unplaced"],
                           total_cost=plan["cost"], status="draft")
    db.add(saved)
    db.flush()
    for a in plan["assignments"]:
        db.add(Allocation(participant_id=a["participant_id"], room_id=a["room_id"],
                          external_stay_id=a["external_stay_id"],
                          plan_id=saved.id, source=a["source"],
                          check_in=_parse_dt(a["check_in"]), check_out=_parse_dt(a["check_out"]),
                          reason=a["reason"], cost=a["cost"]))
    audit_id = log_change(db, user.username, "allocation_plan", saved.id, None,
                          {"summary": _plan_summary(plan), "preset": plan["preset"]},
                          body.reason or f"generated {plan['preset']} plan",
                          kind="system").id
    summary = _plan_summary(plan)
    db.commit()
    return {"plan_id": saved.id, "preset": plan["preset"], "summary": summary,
            "review_queue": plan["review_queue"],
            "violations": plan["violations"],
            "unplaced": plan["unplaced"], "cost": plan["cost"],
            "audit_entry": audit_id,
            "next": {"activate": f"POST /accommodation/plan/{saved.id}/activate"}}


def _parse_dt(v):
    from datetime import datetime
    return datetime.fromisoformat(v) if v else None


@router.post("/plan/{plan_id}/activate")
def activate(plan_id: int, user=Depends(require_role("director", "accommodation_lead")),
             db: Session = Depends(get_db)):
    """Apply a draft plan to live ALLOCATION rows (supersedes the previous active one)."""
    plan = db.get(AllocationPlan, plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"plan {plan_id} not found")
    if plan.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "plan already active")
    if plan.status == "superseded":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "superseded plans cannot be re-activated; regenerate")
    before_status = plan.status
    for other in db.query(AllocationPlan).filter(AllocationPlan.status == "active").all():
        other.status = "superseded"
        log_change(db, user.username, "allocation_plan", other.id, {"status": "active"},
                   {"status": "superseded"}, f"superseded by plan {plan_id}",
                   kind="manual")
    allocations = db.query(Allocation).filter(Allocation.plan_id == plan_id).all()
    for alloc in allocations:
        alloc.version = 2
        alloc.source = alloc.source
        alloc.locked = False
    plan.status = "active"
    after = {"status": "active", "allocations": len(allocations)}
    log_change(db, user.username, "allocation_plan", plan.id,
               {"status": before_status}, after, "plan activated", kind="manual")
    db.commit()
    return {"plan_id": plan_id, "status": plan.status, "allocations": len(allocations)}


@router.post("/plan/{plan_id}/lock")
def lock(plan_id: int, body: schemas.ReasonIn,
         user=Depends(require_role("director", "accommodation_lead")),
         db: Session = Depends(get_db)):
    """Lock every allocation of an active plan against automated regeneration."""
    plan = db.get(AllocationPlan, plan_id)
    if plan is None or plan.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "only active plans can be locked")
    allocs = db.query(Allocation).filter(Allocation.plan_id == plan_id).all()
    for a in allocs:
        a.locked = True
    log_change(db, user.username, "allocation_plan", plan_id, None,
               {"locked": len(allocs)}, body.reason, kind="manual")
    db.commit()
    return {"plan_id": plan_id, "locked": len(allocs)}


@router.post("/assign")
def assign(body: schemas.AssignIn,
           user=Depends(require_role("director", "accommodation_lead")),
           db: Session = Depends(get_db)):
    """Manual single-bed change (override). Audited with a mandatory reason."""
    p = db.get(Participant, body.participant_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "participant not found")
    if p.merged_into is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{p.raw_id} is a duplicate merged into participant "
                            f"{p.merged_into}; assign the canonical record")
    prev = (db.query(Allocation).filter(Allocation.participant_id == p.id)
            .order_by(Allocation.id.desc()).first())
    before = {"room_id": prev.room_id, "external_stay_id": prev.external_stay_id,
              "cost": prev.cost} if prev else None
    alloc = Allocation(participant_id=p.id, room_id=body.room_id,
                       external_stay_id=body.external_stay_id,
                       check_in=None, check_out=None,
                       reason=body.reason or "manual override", locked=True,
                       source="override", version=1)
    db.add(alloc)
    audit_id = log_change(db, user.username, "allocation", alloc.id, before,
                          {"room_id": body.room_id, "external_stay_id": body.external_stay_id},
                          body.reason or "manual override", kind="override").id
    db.commit()
    return {"allocation_id": alloc.id, "participant_id": p.id, "raw_id": p.raw_id,
            "audit_entry": audit_id}


@router.get("/shortage")
def shortage(user=Depends(require_role("director", "accommodation_lead")),
             db: Session = Depends(get_db)):
    from engines.allocator import allocate as run_engine
    plan = run_engine(_participant_dicts(db), _room_dicts(db), _ext_dicts(db),
                      preset="min_cost")
    return plan["shortage"]


@router.get("/review-queue")
def review_queue(user=Depends(require_role("director", "accommodation_lead")),
                 db: Session = Depends(get_db)):
    """Unclear gender or unclear consent: needs a human, never an automatic binary."""
    from engines.allocator import allocate as run_engine
    plan = run_engine(_participant_dicts(db), _room_dicts(db), _ext_dicts(db),
                      preset="min_cost")
    return {"count": len(plan["review_queue"]), "review_queue": plan["review_queue"]}


@router.get("/explain/{participant_id}")
def explain(participant_id: int,
            user=Depends(require_role("director", "accommodation_lead")),
            db: Session = Depends(get_db)):
    allocs = (db.query(Allocation).filter(Allocation.participant_id == participant_id)
              .order_by(Allocation.id.desc()).all())
    if not allocs:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no allocation for participant")
    a = allocs[0]
    return {"participant_id": participant_id, "room_id": a.room_id,
            "external_stay_id": a.external_stay_id, "source": a.source,
            "reason": a.reason, "cost": a.cost, "plan_id": a.plan_id,
            "locked": a.locked}

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.audit import log_change
from app.auth import require_role
from app.db import get_db
from app.models import CoreTeam, Event, EventStaff, Registration, Venue

router = APIRouter(prefix="/schedule", tags=["schedule"])


def _check(db: Session) -> dict:
    from engines.scheduler import find_conflicts
    events = []
    for e in db.query(Event).all():
        start = e.start_dt
        events.append({"id": e.id, "raw_id": e.raw_id, "name": e.name,
                       "duration_minutes": e.duration_minutes,
                       "venue_id": e.venue_id, "start": start, "end": e.end_dt,
                       "setup_min": e.setup_min, "teardown_min": e.teardown_min,
                       "volunteers_needed": e.volunteers_needed,
                       "equipment_needs": e.equipment_needs or []})
    venues = [{"id": v.id, "raw_id": v.raw_id, "name": v.name,
               "capacity": v.capacity,
               "availability_windows": v.availability_windows or []}
              for v in db.query(Venue).all()]
    regs = [{"participant": r.participant_raw_id, "event_raw_id": r.event_raw_id,
             "event_id": r.event_id}
            for r in db.query(Registration).filter(
                Registration.status == "registered").all()]
    staff = [{"event_id": s.event_id, "core_team_id": s.core_team_id, "role": s.role}
             for s in db.query(EventStaff).all()]
    team = [{"id": t.id, "raw_id": t.raw_id, "name": t.name,
             "shift_start": t.shift_start, "shift_end": t.shift_end,
             "shift_crosses_midnight": t.shift_crosses_midnight}
            for t in db.query(CoreTeam).all()]
    return find_conflicts(events, venues, regs, staff, team)


@router.get("/conflicts")
def conflicts(user=Depends(require_role("director", "events_lead")),
              db: Session = Depends(get_db)):
    """Full conflict sweep across every scheduler rule."""
    return _check(db)


@router.get("/events")
def list_events(
    scheduled_only: bool = False,
    user=Depends(require_role("director", "events_lead", "viewer")),
    db: Session = Depends(get_db),
):
    q = db.query(Event)
    if scheduled_only:
        q = q.filter(Event.start_dt.isnot(None))
    rows = q.order_by(Event.raw_id).all()
    return {"total": len(rows),
            "events": [{"id": e.id, "raw_id": e.raw_id, "name": e.name,
                        "type": e.type, "rounds": e.rounds or [],
                        "duration_minutes": e.duration_minutes,
                        "venue_id": e.venue_id, "start": e.start_dt, "end": e.end_dt,
                        "registration_count": db.query(Registration)
                        .filter(Registration.event_id == e.id,
                                Registration.status == "registered").count()}
                       for e in rows]}


@router.patch("/events/{event_id}")
def edit_event(event_id: int, body: schemas.EventEditIn,
               user=Depends(require_role("director", "events_lead")),
               db: Session = Depends(get_db)):
    """Operator schedules/edits an event (venue + times not in the pack, A-11). Audited."""
    from datetime import datetime

    e = db.get(Event, event_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"event {event_id} not found")
    before = {"name": e.name, "venue_id": e.venue_id,
              "start_dt": e.start_dt.isoformat() if e.start_dt else None,
              "end_dt": e.end_dt.isoformat() if e.end_dt else None,
              "duration_minutes": e.duration_minutes, "setup_min": e.setup_min,
              "teardown_min": e.teardown_min,
              "volunteers_needed": e.volunteers_needed,
              "equipment_needs": e.equipment_needs}
    changes = {}
    for field, value in body.model_dump(exclude_none=True, exclude={"reason"}).items():
        if field in ("start_dt", "end_dt") and value is not None:
            try:
                value = datetime.fromisoformat(str(value).replace("T", " "))
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    f"{field} must be ISO datetime")
        if getattr(e, field) != value:
            changes[field] = value
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no changes supplied")
    for field, value in changes.items():
        setattr(e, field, value)
    if e.start_dt and e.end_dt and e.end_dt <= e.start_dt:
        setattr(e, "end_dt", None)  # never store an impossible window silently
    audit_id = log_change(db, user.username, "event", e.id, before,
                          {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                           for k, v in changes.items()},
                          body.reason, kind="manual").id
    db.commit()
    after_check = _check(db)
    n_conflicts = len(after_check["conflicts"])
    return {"event_id": e.id, "raw_id": e.raw_id, "changed": list(changes),
            "audit_entry": audit_id,
            "post_edit_conflicts": n_conflicts,
            "conflicts_involved": [c for c in after_check["conflicts"]
                                   if e.raw_id in (c.get("event_1"), c.get("event_2"),
                                                   c.get("event"))][:10]}


@router.post("/move")
def move(body: schemas.ScheduleMoveIn,
         user=Depends(require_role("director", "events_lead")),
         db: Session = Depends(get_db)):
    """Move an event to a new venue/time; re-checks conflicts after the move."""
    from datetime import datetime

    e = db.query(Event).filter(Event.raw_id == body.event_raw_id).first()
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"event {body.event_raw_id} not found")
    before = {"venue_id": e.venue_id,
              "start_dt": e.start_dt.isoformat() if e.start_dt else None,
              "end_dt": e.end_dt.isoformat() if e.end_dt else None}
    if body.venue_id is not None and db.get(Venue, body.venue_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"venue {body.venue_id} not found")
    e.venue_id = body.venue_id if body.venue_id is not None else e.venue_id
    if body.start is not None:
        e.start_dt = datetime.fromisoformat(body.start.replace("T", " "))
    if body.end is not None:
        e.end_dt = datetime.fromisoformat(body.end.replace("T", " "))
    after = {"venue_id": e.venue_id,
             "start_dt": e.start_dt.isoformat() if e.start_dt else None,
             "end_dt": e.end_dt.isoformat() if e.end_dt else None}
    audit_id = log_change(db, user.username, "event", e.id, before, after,
                          f"schedule move of {e.raw_id}", kind="manual").id
    db.commit()
    check = _check(db)
    affected = [c for c in check["conflicts"]
                if e.raw_id in (c.get("event_1"), c.get("event_2"), c.get("event"))]
    return {"event_id": e.id, "raw_id": e.raw_id, "audit_entry": audit_id,
            "remaining_conflicts_for_event": affected,
            "suggestions": check["suggestions"][:5]}

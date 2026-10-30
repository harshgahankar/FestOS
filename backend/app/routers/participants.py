from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app import auth as auth_mod
from app import schemas
from app.audit import log_change
from app.auth import require_permission
from app.db import get_db
from app.models import Allocation, AuditLog, Contingent, MerchIssue, Participant, Registration

router = APIRouter(prefix="/participants", tags=["participants"])

EDITABLE_FIELDS = ("name", "age", "phone", "email", "tshirt_size",
                   "accessibility_details", "dietary_tags", "accommodation_requested")


def _snapshot(p: Participant) -> dict:
    return {"name": p.name, "age": p.age, "phone": p.phone, "email": p.email,
            "tshirt_size": p.tshirt_size, "accessibility_details": p.accessibility_details,
            "dietary_tags": p.dietary_tags or [],
            "accommodation_requested": p.accommodation_requested,
            "status": p.status, "merged_into": p.merged_into}


def _room_text(alloc: Allocation | None) -> str | None:
    if alloc is None:
        return None
    if alloc.room_id:
        return f"room {alloc.room_id}"
    if alloc.external_stay_id:
        return f"external stay #{alloc.external_stay_id}"
    return None


def participant_view(db: Session, p: Participant, role: str) -> dict:
    """Masked record view for a role; room shown only when an allocation exists."""
    alloc = (db.query(Allocation).filter(Allocation.participant_id == p.id)
             .order_by(Allocation.id.desc()).first())
    room = _room_text(alloc)
    view = auth_mod.mask_fields(role, {
        "id": p.id,
        "raw_id": p.raw_id,
        "name": p.name,
        "college": p.college,
        "contingent": p.contingent_id,
        "gender": p.gender,
        "age": p.age,
        "phone": p.phone,
        "email": p.email,
        "accessibility_status": p.accessibility_status,
        "accessibility_details": p.accessibility_details,
        "dietary_status": p.dietary_status,
        "dietary_tags": p.dietary_tags or [],
        "medical_notes": p.medical_notes,
        "tshirt_size": p.tshirt_size,
        "arrival": p.arrival_dt.isoformat() if p.arrival_dt else None,
        "departure": p.departure_dt.isoformat() if p.departure_dt else None,
        "accommodation_requested": p.accommodation_requested,
        "status": p.status,
        "merged_into": p.merged_into,
        "quality_flags": p.quality_flags or [],
    }, room=room)
    if room is not None:
        view.setdefault("room", room)
    return view


def _get_participant(db: Session, participant_id: int) -> Participant:
    p = db.get(Participant, participant_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"participant {participant_id} not found")
    return p


@router.get("")
def list_participants(
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    flag: str | None = None,
    contingent: str | None = None,
    arrival_day: str | None = None,
    limit: int = 50, offset: int = 0,
    user=Depends(require_permission("view_participants")),
    db: Session = Depends(get_db),
):
    q = db.query(Participant)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((Participant.name.like(like)) |
                     (Participant.raw_id.like(like)) |
                     (Participant.college.like(like)))
    if status_filter:
        q = q.filter(Participant.status == status_filter)
    if contingent:
        q = q.filter(Participant.contingent_id == contingent)
    if flag:
        q = q.filter(cast(Participant.quality_flags, String).like(f'%"{flag}"%'))
    if arrival_day:
        start = datetime.strptime(arrival_day, "%Y-%m-%d")
        q = q.filter(Participant.arrival_dt >= start,
                     Participant.arrival_dt < start + timedelta(days=1))
    total = q.count()
    rows = q.order_by(Participant.raw_id).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset,
            "participants": [participant_view(db, r, user.role) for r in rows]}


@router.get("/duplicates")
def duplicates(user=Depends(require_permission("view_participants")),
               db: Session = Depends(get_db)):
    """Duplicate clusters: linked duplicates grouped under their canonical record."""
    dups = (db.query(Participant).filter(Participant.merged_into.isnot(None))
            .order_by(Participant.raw_id).all())
    clusters: dict[int, list] = {}
    for p in dups:
        clusters.setdefault(p.merged_into, []).append(p)
    canon = {p.id: p for p in db.query(Participant)
             .filter(Participant.id.in_(list(clusters))).all()}
    out = []
    for cid, group in clusters.items():
        c = canon.get(cid)
        out.append({
            "canonical": {"id": cid, "raw_id": c.raw_id if c else None,
                          "name": c.name if c else None},
            "duplicates": [{"id": d.id, "raw_id": d.raw_id, "name": d.name,
                            "quality_flags": d.quality_flags or []} for d in group]})
    return {"clusters": out, "count": len(out)}


@router.get("/{participant_id}")
def get_participant(participant_id: int,
                    user=Depends(require_permission("view_participants")),
                    db: Session = Depends(get_db)):
    """360-degree record: participant + contingent + events + bed + merch + audit trail."""
    p = _get_participant(db, participant_id)
    cont = db.query(Contingent).filter(
        Contingent.raw_id == p.contingent_id).first() if p.contingent_id else None
    regs = db.query(Registration).filter(Registration.participant_id == p.id,
                                         Registration.status != "cancelled").all()
    alloc = (db.query(Allocation).filter(Allocation.participant_id == p.id)
             .order_by(Allocation.id.desc()).first())
    merch = db.query(MerchIssue).filter((MerchIssue.participant_id == p.id) |
                                        (MerchIssue.canonical_participant_id == p.id)).all()
    audits = (db.query(AuditLog).filter((AuditLog.entity_type == "participant") &
                                        (AuditLog.entity_id == str(p.id)))
              .order_by(AuditLog.id.desc()).limit(20).all())
    return {
        "participant": participant_view(db, p, user.role),
        "contingent": {
            "raw_id": cont.raw_id, "college": cont.college,
            "leader": cont.leader_name, "escort": cont.escort_name,
            "size_declared": cont.size_declared, "size_actual": cont.size_actual,
            "preferences": cont.preferences or [],
        } if cont else None,
        "events": [{"event_id": r.event_raw_id, "role": r.role,
                    "team_id": r.team_id, "status": r.status} for r in regs],
        "bed": _room_text(alloc),
        "merch_issued": [{"item_id": m.item_id, "at": m.issued_at.isoformat()}
                         for m in merch],
        "audit": [{"at": a.at.isoformat(), "actor": a.actor_id, "kind": a.kind,
                   "reason": a.reason} for a in audits],
    }


@router.post("/{participant_id}/reveal")
def reveal(participant_id: int, body: schemas.RevealIn,
           user=Depends(require_permission("view_participants")),
           db: Session = Depends(get_db)):
    """Return the requested sensitive fields unmasked; every call is audited."""
    allowed, denied = auth_mod.can_reveal(user.role, body.fields)
    if not allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"role '{user.role}' may not reveal: {', '.join(denied)} "
            f"(may reveal: {', '.join(auth_mod.revealable_fields(user.role)) or 'nothing'})")
    p = _get_participant(db, participant_id)
    values = {"phone": p.phone, "email": p.email, "medical_notes": p.medical_notes,
              "accessibility_details": p.accessibility_details,
              "accessibility_status": p.accessibility_status,
              "dietary_tags": p.dietary_tags or []}
    if "room" in body.fields:
        alloc = (db.query(Allocation).filter(Allocation.participant_id == p.id)
                 .order_by(Allocation.id.desc()).first())
        values["room"] = _room_text(alloc)
    out = {f: values.get(f) for f in body.fields}
    entry = log_change(db, user.username, "participant", p.id, None,
                       {"fields": body.fields}, body.reason, kind="reveal")
    db.commit()
    return {"participant_id": p.id, "raw_id": p.raw_id, "fields": out,
            "audit_entry": entry.id}


@router.patch("/{participant_id}")
def patch_participant(participant_id: int, body: schemas.ParticipantPatchIn,
                      user=Depends(require_permission("view_participants")),
                      db: Session = Depends(get_db)):
    """Audited field edit. Only allowlisted fields may change."""
    p = _get_participant(db, participant_id)
    before = _snapshot(p)
    changes = {k: v for k, v in
               body.model_dump(exclude_none=True, exclude={"note"}).items()
               if k in EDITABLE_FIELDS}
    if not changes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"no editable fields supplied; editable: {', '.join(EDITABLE_FIELDS)}")
    for k, v in changes.items():
        setattr(p, k, v)
    after = _snapshot(p)
    entry = log_change(db, user.username, "participant", p.id, before, after,
                       body.note or "operator edit", kind="manual")
    db.commit()
    return {"id": p.id, "raw_id": p.raw_id, "changed": list(changes),
            "audit_entry": entry.id, "participant": participant_view(db, p, user.role)}


@router.post("/merge")
def merge(body: schemas.MergeIn, user=Depends(require_permission("view_participants")),
          db: Session = Depends(get_db)):
    """Operator-driven duplicate merge: link duplicate -> canonical (reversible, audited)."""

    def resolve(pid, praw, label):
        if pid is not None:
            return _get_participant(db, pid)
        if praw is not None:
            p = db.query(Participant).filter(Participant.raw_id == praw).first()
            if p is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"participant {praw} not found")
            return p
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"supply an id or raw_id for the {label} record")

    canonical = resolve(body.canonical_id, body.canonical_raw_id, "canonical")
    dup = resolve(body.duplicate_id, body.duplicate_raw_id, "duplicate")
    if canonical.id == dup.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot merge a record into itself")
    if canonical.merged_into is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"canonical {canonical.raw_id} is itself merged into participant "
            f"{canonical.merged_into}; merge into the cluster head instead")
    if dup.status == "duplicate" and dup.merged_into == canonical.id:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{dup.raw_id} is already merged into {canonical.raw_id}")
    before = _snapshot(dup)
    dup.merged_into = canonical.id
    dup.status = "duplicate"
    flags = sorted(set((dup.quality_flags or []) + ["DUPLICATE_LINKED", "MERGED_MANUAL"]))
    dup.quality_flags = flags
    after = _snapshot(dup)
    entry = log_change(db, user.username, "participant", dup.id, before, after,
                       body.reason, kind="manual")
    db.commit()
    return schemas.MergeOut(canonical={"id": canonical.id, "raw_id": canonical.raw_id},
                            duplicate={"id": dup.id, "raw_id": dup.raw_id},
                            audit_id=entry.id)


@router.post("/{participant_id}/unmerge")
def unmerge(participant_id: int, body: schemas.ReasonIn,
            user=Depends(require_permission("view_participants")),
            db: Session = Depends(get_db)):
    """Revert a merge: the duplicate becomes active again (audited)."""
    p = _get_participant(db, participant_id)
    if p.merged_into is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{p.raw_id} is not merged into anything")
    before = _snapshot(p)
    canonical_id = p.merged_into
    p.merged_into = None
    p.status = "active"
    flags = [f for f in (p.quality_flags or []) if f != "DUPLICATE_LINKED"]
    p.quality_flags = sorted(set(flags + ["MERGE_REVERTED"]))
    after = _snapshot(p)
    entry = log_change(db, user.username, "participant", p.id, before, after,
                       body.reason + f"; was merged into participant {canonical_id}",
                       kind="manual")
    db.commit()
    return {"id": p.id, "raw_id": p.raw_id, "was_merged_into": canonical_id,
            "status": p.status, "audit_entry": entry.id}


@router.get("/{participant_id}/audit")
def participant_audit(participant_id: int, limit: int = 50,
                      user=Depends(require_permission("view_participants")),
                      db: Session = Depends(get_db)):
    rows = (db.query(AuditLog).filter(AuditLog.entity_id == str(participant_id))
            .order_by(AuditLog.id.desc()).limit(limit).all())
    return {"entries": [{"id": r.id, "at": r.at.isoformat(), "actor": r.actor_id,
                         "action": r.action, "entity_type": r.entity_type,
                         "kind": r.kind, "reason": r.reason,
                         "before": r.before, "after": r.after} for r in rows]}

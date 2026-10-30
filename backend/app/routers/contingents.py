from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Contingent, ImportIssue, Participant
from app.auth import require_permission
from app.routers.participants import participant_view as pv  # noqa: F401

router = APIRouter(prefix="/contingents", tags=["contingents"])


@router.get("")
def list_contingents(
    search: str | None = None,
    mismatched: bool | None = None,
    limit: int = 50, offset: int = 0,
    user=Depends(require_permission("view_participants")),
    db: Session = Depends(get_db),
):
    """All contingents with declared vs actual sizes and mismatch status."""
    q = db.query(Contingent)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter((Contingent.college.like(like)) |
                     (Contingent.raw_id.like(like)) |
                     (Contingent.name.like(like)))
    if mismatched:
        q = q.filter(Contingent.size_declared.isnot(None),
                     Contingent.size_actual.isnot(None),
                     Contingent.size_declared != Contingent.size_actual)
    total = q.count()
    rows = q.order_by(Contingent.raw_id).offset(offset).limit(limit).all()

    def view(c: Contingent) -> dict:
        mismatch = None
        if c.size_declared is not None and c.size_actual is not None:
            mismatch = c.size_actual - c.size_declared
        return {
            "id": c.id, "raw_id": c.raw_id, "college": c.college, "name": c.name,
            "leader": c.leader_name, "escort": c.escort_name,
            "escort_count": c.escort_count,
            "size_declared": c.size_declared, "size_actual": c.size_actual,
            "size_mismatch": mismatch,
            "arrival_window": c.arrival_window or {},
            "preferences": c.preferences or [],
        }

    return {"total": total, "limit": limit, "offset": offset,
            "contingents": [view(c) for c in rows]}


@router.get("/{contingent_id}")
def get_contingent(contingent_id: str,
                   user=Depends(require_permission("view_participants")),
                   db: Session = Depends(get_db)):
    """Contingent detail: leader, escorts, members (masked), split refusals."""
    c = db.query(Contingent).filter(Contingent.raw_id == contingent_id).first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"contingent {contingent_id} not found")
    members = (db.query(Participant).filter(Participant.contingent_id == c.raw_id)
               .order_by(Participant.raw_id).all())
    issues = (db.query(ImportIssue).filter(ImportIssue.row == c.raw_id,
                                           ImportIssue.status == "open").all())
    arrival_days = sorted({m.arrival_dt.date().isoformat() for m in members
                           if m.arrival_dt is not None})
    departure_days = sorted({m.departure_dt.date().isoformat() for m in members
                             if m.departure_dt is not None})
    return {
        "contingent": {
            "id": c.id, "raw_id": c.raw_id, "college": c.college, "name": c.name,
            "leader": c.leader_name, "leader_participant_id": c.leader_participant_id,
            "escort": c.escort_name, "escort_count": c.escort_count,
            "size_declared": c.size_declared, "size_actual": c.size_actual,
            "size_mismatch": (c.size_actual - c.size_declared)
                             if (c.size_declared is not None and c.size_actual is not None)
                             else None,
            "arrival_window": c.arrival_window or {},
            "preferences": c.preferences or [], "preferences_raw": c.preferences_raw,
        },
        "member_count": len(members),
        "members": [pv(db, m, user.role) for m in members],
        "arrival_days": arrival_days, "departure_days": departure_days,
        "open_issues": [{"code": i.code, "severity": i.severity, "message": i.message}
                        for i in issues],
    }

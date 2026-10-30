from __future__ import annotations

from datetime import datetime, time
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import log_change
from app.auth import get_current_user, require_role
from app.db import get_db
from app.models import CoreTeam, User

router = APIRouter(prefix="/team", tags=["team"])

ACCESS_MATRIX = [
    {
        "role": "director",
        "participants": "edit",
        "accommodation": "edit",
        "events": "edit",
        "logistics": "edit",
        "vendors": "edit",
        "team": "edit",
        "audit": "edit",
        "contact": "visible",
        "medical": "visible",
        "access_room": "visible",
    },
    {
        "role": "accommodation",
        "participants": "edit",
        "accommodation": "edit",
        "events": "view",
        "logistics": "—",
        "vendors": "—",
        "team": "—",
        "audit": "view",
        "contact": "visible",
        "medical": "masked",
        "access_room": "visible",
    },
    {
        "role": "events",
        "participants": "view",
        "accommodation": "—",
        "events": "edit",
        "logistics": "view",
        "vendors": "—",
        "team": "—",
        "audit": "view",
        "contact": "masked",
        "medical": "masked",
        "access_room": "masked",
    },
    {
        "role": "logistics",
        "participants": "view",
        "accommodation": "—",
        "events": "view",
        "logistics": "edit",
        "vendors": "—",
        "team": "—",
        "audit": "view",
        "contact": "masked",
        "medical": "masked",
        "access_room": "masked",
    },
    {
        "role": "hospitality",
        "participants": "view",
        "accommodation": "—",
        "events": "—",
        "logistics": "—",
        "vendors": "edit",
        "team": "—",
        "audit": "view",
        "contact": "masked",
        "medical": "visible",
        "access_room": "masked",
    },
    {
        "role": "volunteer",
        "participants": "view",
        "accommodation": "—",
        "events": "—",
        "logistics": "edit",
        "vendors": "—",
        "team": "—",
        "audit": "—",
        "contact": "masked",
        "medical": "masked",
        "access_room": "masked",
    },
]

AVAILABLE_ROLES = [
    "director",
    "accommodation",
    "events",
    "logistics",
    "hospitality",
    "volunteer",
]

AVAILABLE_SHIFTS = [
    {"key": "morning", "label": "morning (06:00-14:00)", "hours": "06:00-14:00"},
    {"key": "afternoon", "label": "afternoon (10:00-18:00)", "hours": "10:00-18:00"},
    {"key": "evening", "label": "evening (14:00-22:00)", "hours": "14:00-22:00"},
    {"key": "night", "label": "night (22:00-06:00)", "hours": "22:00-06:00"},
]


def _shift_to_label(shift_raw: str | None) -> str:
    if not shift_raw:
        return "morning"
    s = shift_raw.strip().lower()
    if s.startswith("night") or s == "night":
        return "night"
    if s.startswith("evening") or s == "evening":
        return "evening"
    if s.startswith("afternoon") or s == "afternoon":
        return "afternoon"
    if s.startswith("morning") or s == "morning":
        return "morning"
    if s.startswith("06:") or s.startswith("6:"):
        return "morning"
    if s.startswith("10:"):
        return "afternoon"
    if s.startswith("14:"):
        return "evening"
    if s.startswith("22:"):
        return "night"
    return "morning"


def _label_to_shift_parts(label: str) -> tuple[str, time, time, bool]:
    l = label.lower().strip()
    if l == "morning":
        return ("06:00-14:00", time(6, 0), time(14, 0), False)
    if l == "afternoon":
        return ("10:00-18:00", time(10, 0), time(18, 0), False)
    if l == "evening":
        return ("14:00-22:00", time(14, 0), time(22, 0), False)
    if l == "night":
        return ("22:00-06:00", time(22, 0), time(6, 0), True)
    return ("06:00-14:00", time(6, 0), time(14, 0), False)


def _role_to_label(role: str | None) -> str:
    if not role:
        return "volunteer"
    r = role.lower().strip()
    if "director" in r:
        return "director"
    if "event" in r:
        return "events"
    if "logistics" in r or "merchandise" in r:
        return "logistics"
    if "hospitality" in r or "food" in r:
        return "hospitality"
    if "registration" in r or "accommodation" in r:
        return "accommodation"
    if "volunteer" in r:
        return "volunteer"
    return "volunteer"


def _member_dict(m: CoreTeam) -> dict[str, Any]:
    return {
        "id": m.id,
        "raw_id": m.raw_id,
        "name": m.name,
        "role": _role_to_label(m.role),
        "original_role": m.role,
        "shift": _shift_to_label(m.shift_raw),
        "shift_raw": m.shift_raw,
        "shift_crosses_midnight": m.shift_crosses_midnight,
        "contact": m.contact,
    }


class UpdateMemberIn(BaseModel):
    role: Optional[str] = None
    shift: Optional[str] = None
    reason: Optional[str] = None


@router.get("")
def get_team_and_access(
    user: User = Depends(require_role("director", "accommodation_lead", "events_lead", "logistics_lead", "vendor_lead", "volunteer", "viewer")),
    db: Session = Depends(get_db),
):
    members = db.query(CoreTeam).order_by(CoreTeam.id.asc()).all()
    return {
        "access_matrix": ACCESS_MATRIX,
        "roles": AVAILABLE_ROLES,
        "shifts": [s["key"] for s in AVAILABLE_SHIFTS],
        "shift_details": AVAILABLE_SHIFTS,
        "members": [_member_dict(m) for m in members],
        "count": len(members),
    }


@router.patch("/{member_id}")
def update_team_member(
    member_id: int,
    body: UpdateMemberIn,
    user: User = Depends(require_role("director")),
    db: Session = Depends(get_db),
):
    member = db.query(CoreTeam).filter(CoreTeam.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    before = _member_dict(member)
    reason = body.reason or f"Role/shift update by {user.username}"

    if body.role is not None:
        if body.role not in AVAILABLE_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        member.role = body.role

    if body.shift is not None:
        raw, s_start, s_end, crosses = _label_to_shift_parts(body.shift)
        member.shift_raw = raw
        member.shift_start = s_start
        member.shift_end = s_end
        member.shift_crosses_midnight = crosses

    after = _member_dict(member)
    log_change(
        db,
        actor=user.username,
        entity_type="core_team",
        entity_id=member.id,
        before=before,
        after=after,
        reason=reason,
        kind="manual",
    )
    db.commit()
    db.refresh(member)

    return {"ok": True, "member": _member_dict(member)}

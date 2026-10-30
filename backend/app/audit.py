"""Audit: append-only change log. Every state-changing write path must call log_change()."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def _jsonable(obj: Any) -> Optional[dict]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "__table__"):  # SQLAlchemy model -> plain values
        return {c.name: _jsonable(getattr(obj, c.name)) for c in obj.__table__.columns}
    if isinstance(obj, (int, float, bool, str)) or obj is None:
        return obj
    if isinstance(obj, (list,)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def log_change(
    db: Session,
    actor: str | None,
    entity_type: str,
    entity_id: str | int | None,
    before: Any,
    after: Any,
    reason: str,
    kind: str = "system",
) -> AuditLog:
    """Append an audit entry and flush it. Never update or delete audit rows.

    kind: manual | system | override | reveal
    """
    if kind not in ("manual", "system", "override", "reveal"):
        raise ValueError(f"unknown audit kind: {kind}")
    entry = AuditLog(
        actor_id=actor,
        action="update" if before is not None and after is not None else
               ("create" if before is None else "change"),
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=_jsonable(before),
        after=_jsonable(after),
        reason=reason or "",
        kind=kind,
    )
    db.add(entry)
    db.flush()
    return entry

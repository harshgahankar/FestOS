"""Audit: every state write lands an audit row with before/after, actor, reason."""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from app import audit                      # noqa: E402
from app.models import AuditLog, Participant  # noqa: E402


def _snap(p):
    return {"status": p.status, "quality_flags": p.quality_flags}


def test_write_path_records_audit_row(seeded_db):
    p = seeded_db.query(Participant).filter(Participant.raw_id == "P001").one()
    before = _snap(p)
    p.status = "flagged"
    p.quality_flags = sorted((p.quality_flags or []) + ["OPERATOR_FLAG"])
    audit.log_change(seeded_db, "volunteer", "participant", p.id, before, _snap(p),
                     "ops review: identity unclear at desk", kind="manual")
    seeded_db.commit()

    rows = seeded_db.query(AuditLog).filter(
        AuditLog.entity_type == "participant",
        AuditLog.entity_id == str(p.id)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_id == "volunteer"
    assert row.reason == "ops review: identity unclear at desk"
    assert row.kind == "manual"
    assert row.before["status"] == "active" and row.after["status"] == "flagged"
    assert "OPERATOR_FLAG" in row.after["quality_flags"]


def test_import_writes_audits(seeded_db):
    rows = seeded_db.query(AuditLog).all()
    entity_kinds = {r.entity_type for r in rows}
    assert "participant" in entity_kinds
    assert "user" in entity_kinds                    # seed user creation is audited
    # duplicate links are audited with a before/after status change
    dup_audit = [r for r in rows if r.before and r.before.get("status") == "active"
                 and bool(r.after) and r.after.get("status") == "duplicate"]
    assert len(dup_audit) == 2                       # P002 -> P001, P004 -> P003
    assert "unmerge" in dup_audit[0].reason


def test_reveal_and_override_kinds_validated(seeded_db):
    import pytest
    with pytest.raises(ValueError):
        audit.log_change(seeded_db, "x", "participant", 1, None, {"a": 1},
                         "bad kind", kind="banana")

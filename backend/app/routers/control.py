"""Phase 6: control center. Aggregated attention queue, KPIs and the audit browser.

Fail loudly by design: every open finding surfaces here with severity + action hint,
nothing is silently dropped (blanks are 'unknown', not 'no', A-02).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import (AllocationPlan, AuditLog, Event, ImportIssue,
                        InventoryItem, InventoryMovement, MerchIssue,
                        Participant, Registration, Vendor, VendorOrder)
from app.routers.accommodation import (_ext_dicts, _participant_dicts,
                                       _room_dicts)
from app.routers.disruptions import _sched_check
from app.routers.inventory import _item_name, _p_dict as _inv_p_dict
from app.routers.vendors import _v_dict

from engines.allocator import allocate as run_allocator
from engines.inventory import merch_shortfall
from engines.vendors import compliance as run_compliance, coverage_matrix, settlement


router = APIRouter(prefix="/control", tags=["control"])

_FEST_DAYS = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]
_SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


def _item(source: str, severity: str, what: str, entity: str,
          action_hint: str) -> dict:
    return {"source": source, "severity": severity, "what": what,
            "entity": entity, "action_hint": action_hint}


# --------------------------------------------------------------- attention --
@router.get("/attention")
def attention(user=Depends(require_role("director")),
              db: Session = Depends(get_db)):
    """Merged inbox of everything that needs a human decision right now."""
    items: list[dict] = []

    for issue in (db.query(ImportIssue)
                  .filter(ImportIssue.status == "open").all()):
        sev = issue.severity if issue.severity in ("error", "warning") else "info"
        items.append(_item(
            "import", sev,
            f"{issue.file}: {issue.message}",
            f"import_issue:{issue.id}",
            "open the source CSV row (source-kept, never corrected) and re-import "
            "or accept with a note"))

    for p in (db.query(Participant).filter(Participant.status == "quarantined")
              .all()):
        items.append(_item(
            "participants", "error",
            f"{p.raw_id} quarantined: {', '.join(p.quality_flags or []) or 'invalid data'}",
            f"participant:{p.id}",
            "pend a corrected re-import; quarantined rows are never dropped"))

    for p in (db.query(Participant).filter(Participant.status == "flagged").all()):
        items.append(_item(
            "participants", "warning",
            f"{p.raw_id} flagged: {', '.join(p.quality_flags or [])}",
            f"participant:{p.id}",
            "verify against the source row; resolve the flag or quarantine"))

    plan = run_allocator(_participant_dicts(db), _room_dicts(db), _ext_dicts(db),
                         preset="min_cost")
    for q in plan["review_queue"]:
        items.append(_item(
            "accommodation", "warning",
            f"{q.get('raw_id')}: {q.get('reason_code')} â€” {q.get('reason')}",
            f"participant:{q.get('id')}",
            "resolve gender/accommodation consent before any bed is forced"))
    for u in plan["unplaced"]:
        items.append(_item(
            "accommodation", "error",
            f"{u.get('raw_id')}: {u.get('reason')}",
            f"participant:{u.get('id')}",
            "add beds (hostel/external) or assign manually with a reason"))
    if plan["shortage"]["unmet_count"] > 0:
        items.append(_item(
            "accommodation", "error",
            f"{plan['shortage']['unmet_count']} unmet bed requests "
            f"(requested {plan['shortage']['requested_count']}, "
            f"hostel used {plan['shortage']['hostel_beds_used']}, "
            f"external used {plan['shortage']['external_beds_used']})",
            "accommodation:shortage",
            "procure beds or accept documented dimmer (audit the reason)"))

    sched = _sched_check(db)
    for c in sched["conflicts"]:
        items.append(_item(
            "schedule", c.get("severity") or "warning",
            f"{c.get('type')}: {c.get('message')}",
            "schedule:" + "-".join(str(c.get(k)) for k in
                                   ("event", "event_1", "event_2") if c.get(k)),
            "use the schedule move/edit endpoints; the conflict list re-checks"))

    vendors = [_v_dict(v) for v in db.query(Vendor).all()]
    comp = run_compliance(vendors, _FEST_DAYS[0], _FEST_DAYS[-1])
    for raw in comp["expired"]:
        items.append(_item(
            "vendors", "error", f"{raw}: hygiene certificate expired",
            f"vendor:{raw}",
            "suspend service (interrupt) until a new certificate arrives"))
    for raw in comp["expiring"]:
        items.append(_item(
            "vendors", "warning", f"{raw}: certificate expires mid-fest",
            f"vendor:{raw}",
            "chase a renewed certificate before the fest starts"))

    cov = coverage_matrix(vendors, _participants_diet(db), _FEST_DAYS)
    for tag in cov["uncovered_tags"]:
        items.append(_item(
            "vendors", "warning",
            f"no active vendor covers diet tag '{tag}'",
            f"diet:{tag}",
            "add a vendor that covers the tag or change the menu (never assume "
            "an uncovered diet is fine)"))
        from app.models import Participant as P
        who = [p.raw_id for p in db.query(P).filter(
            P.merged_into.is_(None),
            P.status.in_(("active", "flagged")),
            P.dietary_tags.isnot(None)).all()
            if tag in [(str(t) or "").lower().strip() for t in (p.dietary_tags or [])]]
        if who:
            items.append(_item(
                "participants", "warning",
                f"diet tag '{tag}' carried by: {', '.join(sorted(who))}",
                f"diet:{tag}", "arrange specific meals for those participants"))

    inv = _merch_state(db)
    for size, s in inv["shortfall"].items():
        items.append(_item(
            "inventory", "warning",
            f"merch size {size}: need {s['needed']}, stock {s['stock']}, "
            f"short {s['missing']}",
            f"merch:{size}",
            "order more units or dimmer explicitly (never oversell)"))

    pending = _settlement_pending(db)
    if pending:
        items.append(_item(
            "vendors", "info",
            f"{len(pending)} settlement entries without a rate figure",
            "vendors:settlement",
            "record vendor rates (audited PATCH /vendors/{id}/rate) before "
            "settlement closes"))

    items.sort(key=lambda i: (_SEV_ORDER.get(i["severity"], 3), i["source"],
                              i["what"]))
    sev_count = {}
    for i in items:
        sev_count[i["severity"]] = sev_count.get(i["severity"], 0) + 1
    return {"count": len(items), "by_severity": sev_count, "items": items}


def _participants_diet(db: Session) -> list[dict]:
    return [{"id": p.id, "dietary_tags": p.dietary_tags or []}
            for p in db.query(Participant).filter(
                Participant.merged_into.is_(None),
                Participant.status.in_(("active", "flagged"))).all()]


def _merch_state(db: Session) -> dict:
    participants = [_inv_p_dict(p) for p in db.query(Participant)
                    .filter(Participant.merged_into.is_(None)).all()]
    items = [{"id": i.id, "name": i.name, "kind": i.kind, "size": i.size}
             for i in db.query(InventoryItem).filter(InventoryItem.kind == "merch").all()]
    movs = [{"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()]
    issued = {(i.participant_id, _item_name(db, i.item_id))
              for i in db.query(MerchIssue).all()}
    out = merch_shortfall(items, movs, participants, issued_pairs=issued)
    return {"demand": out["demand"], "shortfall": out["shortfall"],
            "issued": len(issued)}


def _settlement_pending(db: Session) -> list[dict]:
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "day": o.day,
               "meal": o.meal, "qty": o.qty, "dietary_tag": o.dietary_tag,
               "paid": o.paid}
              for o in db.query(VendorOrder).all()]
    return settlement([_v_dict(v) for v in db.query(Vendor).all()],
                      orders)["pending_entries"]


# -------------------------------------------------------------------- KPIs --
@router.get("/kpis")
def kpis(user=Depends(require_role("director")),
         db: Session = Depends(get_db)):
    """One-glance festival state. Never guesses: unknown stays null."""
    parts = db.query(Participant).all()
    active = [p for p in parts if p.status == "active"]
    flagged = [p for p in parts if p.status == "flagged"]
    quarantined = [p for p in parts if p.status == "quarantined"]
    dups = [p for p in parts if p.merged_into is not None]

    regs = db.query(Registration).all()
    events = db.query(Event).all()
    scheduled = [e for e in events if e.venue_id is not None and e.start_dt]

    active_plan = (db.query(AllocationPlan)
                   .filter(AllocationPlan.status == "active")
                   .order_by(AllocationPlan.id.desc()).first())
    occupancy = None
    if active_plan is not None and active_plan.summary:
        occupancy = {"plan_id": active_plan.id, "preset": active_plan.preset,
                     **active_plan.summary}

    inv = _merch_state(db)
    vendors = [_v_dict(v) for v in db.query(Vendor).all()]
    comp = run_compliance(vendors, _FEST_DAYS[0], _FEST_DAYS[-1])
    cov = coverage_matrix(vendors, _participants_diet(db), _FEST_DAYS)
    conflicts = _sched_check(db)
    return {
        "participants": {"active": len(active), "flagged": len(flagged),
                         "quarantined": len(quarantined),
                         "linked_duplicates": len(dups),
                         "total_rows": len(parts)},
        "registrations": {"rows": len(regs),
                          "matched_to_participant":
                              sum(1 for r in regs if r.participant_id is not None),
                          "issues_open": _open_import_issues(db)},
        "occupancy": occupancy,
        "events": {"total": len(events), "scheduled": len(scheduled),
                   "conflicts": len(conflicts["conflicts"])},
        "merch": {"issued": inv["issued"],
                  "shortfall_sizes": len(inv["shortfall"]),
                  "missing_units": sum(s["missing"]
                                       for s in inv["shortfall"].values())},
        "vendors": {"total": len(vendors),
                    "expired": len(comp["expired"]),
                    "expiring": len(comp["expiring"]),
                    "uncovered_diet_tags": cov["uncovered_tags"]},
    }


def _open_import_issues(db: Session) -> int:
    return (db.query(ImportIssue)
            .filter(ImportIssue.status == "open",
                    ImportIssue.severity.in_(("error", "warning"))).count())


# -------------------------------------------------------------------- audit --
def _audit_entries(db: Session, entity_type, entity_id, actor, kind,
                   limit: int, offset: int) -> dict:
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == str(entity_id))
    if actor:
        q = q.filter(AuditLog.actor_id == actor)
    if kind:
        q = q.filter(AuditLog.kind == kind)
    total = q.count()
    rows = (q.order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .offset(offset).limit(limit).all())
    return {"total": total, "limit": limit, "offset": offset, "entries": [
        {"id": a.id, "at": a.at.isoformat() if a.at else None,
         "actor": a.actor_id, "action": a.action, "kind": a.kind,
         "entity_type": a.entity_type, "entity_id": a.entity_id,
         "before": a.before, "after": a.after, "reason": a.reason}
        for a in rows]}


@router.get("/audit")
def audit(entity_type: str | None = Query(default=None),
          entity_id: str | None = Query(default=None),
          actor: str | None = Query(default=None),
          kind: str | None = Query(default=None),
          limit: int = Query(default=100, ge=1, le=500),
          offset: int = Query(default=0, ge=0),
          user=Depends(require_role("director")),
          db: Session = Depends(get_db)):
    """Append-only audit trail browser (filterable), director only."""
    return _audit_entries(db, entity_type, entity_id, actor, kind, limit, offset)


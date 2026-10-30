from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.audit import log_change
from app.auth import require_role
from app.db import get_db
from app.models import InventoryItem, InventoryMovement, MerchIssue, Participant

router = APIRouter(prefix="", tags=["inventory"])


@router.get("/inventory/levels")
def levels(user=Depends(require_role("director", "logistics_lead", "viewer")),
           db: Session = Depends(get_db)):
    from engines.inventory import stock_levels
    items = [{"id": i.id, "sku": i.sku, "name": i.name, "category": i.category,
              "size": i.size, "kind": i.kind, "condition": i.condition}
             for i in db.query(InventoryItem).all()]
    movs = [{"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()]
    stock = stock_levels(items, movs)
    out = []
    for it in sorted(items, key=lambda x: (x["kind"], str(x["sku"]))):
        out.append(it | {"qty": stock.get(it["id"], 0)})
    return {"items": out,
            "negative": [i["sku"] for i in out if i["qty"] < 0]}


@router.post("/inventory/movements")
def add_movement(body: schemas.InventoryMoveIn,
                 user=Depends(require_role("director", "logistics_lead")),
                 db: Session = Depends(get_db)):
    """Ledger movement (in/out). Stock is derived, never overwritten. Audited."""
    item = db.get(InventoryItem, body.item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"item {body.item_id} not found")
    if body.qty == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "qty must be non-zero")
    mv = InventoryMovement(item_id=item.id, qty=body.qty,
                           to_location=body.to_location, status=body.status,
                           reference=body.reference, actor=user.username)
    db.add(mv)
    db.flush()
    audit_id = log_change(db, user.username, "inventory_movement", mv.id,
                          None, {"item": item.sku, "qty": body.qty,
                                 "status": body.status, "reference": body.reference},
                          body.reference or "manual movement", kind="manual").id
    db.commit()
    return {"movement_id": mv.id, "item_id": item.id, "sku": item.sku,
            "audit_entry": audit_id}


@router.get("/merch/shortfall")
def merch_shortfall(user=Depends(require_role("director", "logistics_lead")),
                    db: Session = Depends(get_db)):
    from engines.inventory import merch_shortfall as shortfall_engine
    participants = [_p_dict(p) for p in db.query(Participant).filter(
        Participant.merged_into.is_(None)).all()]
    items = [{"id": i.id, "name": i.name, "kind": i.kind, "size": i.size}
             for i in db.query(InventoryItem).filter(InventoryItem.kind == "merch").all()]
    movs = [{"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()]
    issued = {(i.participant_id, _item_name(db, i.item_id))
              for i in db.query(MerchIssue).all()}
    return shortfall_engine(items, movs, participants, issued_pairs=issued)


def _item_name(db: Session, item_id: int) -> str:
    it = db.get(InventoryItem, item_id)
    return f"{it.name}|{it.size or 'UNKNOWN'}" if it else f"item:{item_id}"


def _p_dict(p) -> dict:
    return {"id": p.id, "raw_id": p.raw_id, "tshirt_size": p.tshirt_size,
            "status": p.status, "merged_into": p.merged_into}


@router.post("/merch/issue")
def issue_merch(body: schemas.MerchIssueIn,
                user=Depends(require_role("director", "logistics_lead", "volunteer")),
                db: Session = Depends(get_db)):
    """Issue merch once per canonical cluster. Duplicates and re-issues are refused
    unless force=True (director only), which is flagged in the audit trail."""
    p = db.query(Participant).filter(Participant.raw_id == body.participant_raw_id).first()
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            f"participant {body.participant_raw_id} not found")
    canonical_id = p.id
    if p.merged_into is not None:
        canonical_id = p.merged_into
    canonical = db.get(Participant, canonical_id)
    if canonical.status not in ("active", "flagged"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{canonical.raw_id} is {canonical.status}; merch goes to "
                            f"active participants only")
    if body.item_id is not None:
        item = db.get(InventoryItem, body.item_id)
    else:
        size = (canonical.tshirt_size or "").strip() or None
        item = (db.query(InventoryItem)
                .filter(InventoryItem.kind == "merch",
                        InventoryItem.name == "T-shirt",
                        InventoryItem.size == size)
                .first()) if size else None
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND,
                                f"no T-shirt stock row for size {size or 'UNKNOWN'}")
    cluster_ids = [p.id]
    cluster = db.query(Participant).filter(
        (Participant.id == canonical_id) | (Participant.merged_into == canonical_id)).all()
    cluster_ids = [c.id for c in cluster]
    prior = db.query(MerchIssue).filter(MerchIssue.canonical_participant_id.in_(cluster_ids),
                                        MerchIssue.item_id == item.id).all()
    if prior and not body.force:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{canonical.raw_id} cluster already received this item "
            f"(issue #{prior[0].id}); use force with a reason to re-issue")
    if body.force and user.role != "director":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only a director may force re-issue")
    mv = InventoryMovement(item_id=item.id, qty=-1, from_location="merch store",
                           to_location=canonical.raw_id, actor=user.username)
    db.add(mv)
    db.flush()
    issue = MerchIssue(participant_id=p.id, canonical_participant_id=canonical_id,
                       item_id=item.id, issued_by=user.username)
    db.add(issue)
    db.flush()
    flags = (canonical.quality_flags or []) + ["MERCH_ISSUED"]
    canonical.quality_flags = sorted(set(flags))
    audit_id = log_change(db, user.username, "merch_issue", issue.id, None,
                          {"participant": canonical.raw_id, "item": item.sku,
                           "size": item.size, "forced": body.force},
                          body.reason, kind="manual").id
    db.commit()
    return {"issue_id": issue.id, "canonical": canonical.raw_id,
            "item": {"id": item.id, "sku": item.sku, "size": item.size},
            "audit_entry": audit_id}

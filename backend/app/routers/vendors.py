from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.audit import log_change
from app.auth import require_role
from app.db import get_db
from app.models import Participant, Vendor

router = APIRouter(prefix="/vendors", tags=["vendors"])

FEST_START = "2026-10-30"
FEST_END = "2026-11-02"


def _v_dict(v: Vendor) -> dict:
    return {"id": v.id, "raw_id": v.raw_id, "name": v.name,
            "dietary_coverage": v.dietary_coverage or [],
            "hygiene_cert_expiry": v.hygiene_cert_expiry,
            "hours": v.hours,
            "capacity_per_day": v.capacity_per_day, "rate": v.rate,
            "payment_terms": v.payment_terms,
            "status": v.status}


def _participants_diet(db: Session) -> list[dict]:
    return [{"id": p.id, "dietary_tags": p.dietary_tags or []}
            for p in db.query(Participant).filter(
                Participant.merged_into.is_(None),
                Participant.status.in_(("active", "flagged"))).all()]


@router.get("")
def list_vendors(user=Depends(require_role("director", "vendor_lead")),
                 db: Session = Depends(get_db)):
    from engines.vendors import compliance
    vendors = [_v_dict(v) for v in db.query(Vendor).all()]
    comp = compliance(vendors, FEST_START, FEST_END)
    return {"days": {"start": FEST_START, "end": FEST_END},
            "vendors": vendors,
            "compliance": {"expired": comp["expired"], "expiring": comp["expiring"]}}


@router.get("/compliance")
def compliance(user=Depends(require_role("director", "vendor_lead")),
               db: Session = Depends(get_db)):
    from engines.vendors import compliance as run_compliance
    return run_compliance([_v_dict(v) for v in db.query(Vendor).all()],
                          FEST_START, FEST_END)


@router.get("/coverage")
def coverage(user=Depends(require_role("director", "vendor_lead")),
             db: Session = Depends(get_db)):
    """Dietary coverage matrix (participants' verified/declared diets vs vendor menus)."""
    from engines.vendors import coverage_matrix
    days = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]
    return coverage_matrix([_v_dict(v) for v in db.query(Vendor).all()],
                           _participants_diet(db), days)


@router.patch("/{vendor_id}/rate")
def set_rate(vendor_id: int, body: schemas.VendorRateIn,
             user=Depends(require_role("director", "vendor_lead")),
             db: Session = Depends(get_db)):
    """Manual rate entry (not in pack, A-13). Audited before settlement works."""
    v = db.get(Vendor, vendor_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vendor {vendor_id} not found")
    before = {"rate": v.rate}
    v.rate = body.rate
    log_change(db, user.username, "vendor", v.id, before, {"rate": body.rate},
               body.reason, kind="manual")
    db.commit()
    return {"vendor_id": v.id, "raw_id": v.raw_id, "rate": v.rate}


@router.post("/{vendor_id}/interrupt/preview")
def interrupt_preview(vendor_id: int,
                      user=Depends(require_role("director", "vendor_lead")),
                      db: Session = Depends(get_db)):
    from app.models import VendorOrder
    from engines.vendors import reroute_on_interruption
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "day": o.day,
               "meal": o.meal, "qty": o.qty, "dietary_tag": o.dietary_tag,
               "paid": o.paid}
              for o in db.query(VendorOrder).filter(VendorOrder.vendor_id == vendor_id).all()]
    plan = reroute_on_interruption(vendor_id,
                                   [_v_dict(v) for v in db.query(Vendor).all()],
                                   orders, [])
    return {"vendor_id": vendor_id, "moves": plan["moves"], "unmet": plan["unmet"],
            "note": "preview only; nothing changed until apply"}


@router.post("/{vendor_id}/interrupt/apply")
def interrupt_apply(vendor_id: int, body: schemas.VendorInterruptIn,
                    user=Depends(require_role("director", "vendor_lead")),
                    db: Session = Depends(get_db)):
    """Mark vendor interrupted and move its open orders. Audited; food safety first."""
    from app.models import VendorOrder
    from engines.vendors import reroute_on_interruption
    v = db.get(Vendor, vendor_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"vendor {vendor_id} not found")
    if v.status == "interrupted":
        raise HTTPException(status.HTTP_409_CONFLICT, "vendor already interrupted")
    before = {"status": v.status}
    v.status = "interrupted"
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "day": o.day,
               "meal": o.meal, "qty": o.qty, "dietary_tag": o.dietary_tag,
               "paid": o.paid}
              for o in db.query(VendorOrder).filter(
                  VendorOrder.vendor_id == vendor_id, VendorOrder.paid.is_(False)).all()]
    plan = reroute_on_interruption(vendor_id,
                                   [_v_dict(x) for x in db.query(Vendor).all()],
                                   orders, [])
    moved = 0
    for mv in plan["moves"]:
        order = db.get(VendorOrder, mv["order"])
        order.vendor_id = mv["to_vendor"]
        moved += 1
    log_change(db, user.username, "vendor", v.id, before, {"status": "interrupted"},
               (body.reason + "; " if body.reason else "")
               + f"{moved} orders rerouted", kind="override")
    db.commit()
    return {"vendor_id": v.id, "status": v.status, "orders_moved": moved,
            "unmet": plan["unmet"]}


@router.get("/settlement")
def settlement(user=Depends(require_role("director", "vendor_lead")),
               db: Session = Depends(get_db)):
    from app.models import VendorOrder
    from engines.vendors import settlement as run_settlement
    orders = [{"id": o.id, "vendor_id": o.vendor_id, "qty": o.qty, "paid": o.paid}
              for o in db.query(VendorOrder).all()]
    return run_settlement([_v_dict(v) for v in db.query(Vendor).all()], orders)

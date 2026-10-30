"""Phase 5: disruption engine — one test per type covering preview/apply/revert."""
import sqlalchemy as sa

from app.models import Allocation, Event, HostelRoom, Participant, Venue, Vendor, VendorOrder
from tests.test_phase3 import _login


def _pre(client, payload):
    r = client.post("/disruptions/preview", json=payload,
                    headers=_login(client, "director"))
    return r


def _apply(client, did, reason):
    return client.post(f"/disruptions/{did}/apply", json={"reason": reason},
                       headers=_login(client, "director"))


def _revert(client, did, reason):
    return client.post(f"/disruptions/{did}/revert", json={"reason": reason},
                       headers=_login(client, "director"))


def _allocate(client):
    r = client.post("/accommodation/allocate", json={"preset": "min_cost"},
                    headers=_login(client, "accommodation_lead"))
    assert r.status_code == 200, r.text
    return r.json()["plan_id"]


def test_type1_late_contingent_preview_apply_revert(seeded_db, client):
    r = _pre(client, {"type": "late_contingent",
                      "payload": {"contingent": "C01",
                                  "new_arrival": "2026-10-31 09:00"}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    rep = r.json()["report"]
    assert rep["affected"]["names"], "C01 members listed"
    r2 = _apply(client, did, "contingent bus delayed")
    assert r2.status_code == 200, r2.text
    assert seeded_db.query(Participant).filter_by(raw_id="P003", merged_into=None) \
        .first().arrival_dt.strftime("%Y-%m-%d %H:%M") == "2026-10-31 09:00"
    r3 = _revert(client, did, "bus is fine after all")
    assert r3.status_code == 200, r3.text
    assert seeded_db.query(Participant).filter_by(raw_id="P003", merged_into=None) \
        .first().arrival_dt.strftime("%Y-%m-%d %H:%M") == "2026-10-30 09:00"


def test_type2_duplicate_record_preview_apply_revert(seeded_db, client):
    # P002/P004 are already auto-merged by the importer; the operator-driven
    # post-import link is exercised on P005 (canonical, active) + P006
    r = _pre(client, {"type": "duplicate_record",
                      "payload": {"canonical_raw_id": "P005",
                                  "duplicate_raw_id": "P006"}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    assert r.json()["report"]["state_changes"][0]["to_status"] == "duplicate"
    r2 = _apply(client, did, "same person confirmed by college")
    assert r2.status_code == 200, r2.text
    dup = seeded_db.query(Participant).filter_by(raw_id="P006").first()
    canon = seeded_db.query(Participant).filter_by(raw_id="P005").first()
    assert dup.status == "duplicate" and dup.merged_into == canon.id
    r3 = _revert(client, did, "link was wrong")
    assert r3.status_code == 200, r3.text
    dup = seeded_db.query(Participant).filter_by(raw_id="P006").first()
    assert dup.status == "active" and dup.merged_into is None


def test_type3_hostel_closure_preview_apply_revert(seeded_db, client):
    _allocate(client)
    b1 = seeded_db.query(HostelRoom).filter_by(hostel="B1").first()
    before = [a.id for a in seeded_db.query(Allocation).all()]
    r = _pre(client, {"type": "hostel_closure", "payload": {"hostel": "B1"}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    rep = r.json()["report"]
    # P007 (male, requested, POST_FEST_ARRIVAL flag) sits in B1 -> displaced, and
    # with B1 shut the only bed left is the external Lodge
    assert any(str(a.get("to", "")).startswith("external")
               for a in rep["state_changes"] if a.get("entity") == "allocation")
    r2 = _apply(client, did, "water damage in module B1")
    assert r2.status_code == 200, r2.text
    assert seeded_db.query(HostelRoom).get(b1.id).status == "closed"
    assert all(a.room_id != b1.id for a in seeded_db.query(Allocation).all())
    new_allocs = [a.id for a in seeded_db.query(Allocation).all()]
    assert len(new_allocs) == len(before)
    r3 = _revert(client, did, "repair completed early")
    assert r3.status_code == 200, r3.text
    assert seeded_db.query(HostelRoom).get(b1.id).status == "open"
    assert sorted(a.id for a in seeded_db.query(Allocation).all()) == sorted(before)


def test_type4_equipment_failure_preview_apply_revert(seeded_db, client):
    with seeded_db.bind.connect() as conn:
        sku = conn.execute(sa.text(
            "SELECT sku FROM inventory_items WHERE name='mic'")).scalar()
    r = _pre(client, {"type": "equipment_failure",
                      "payload": {"sku": sku, "qty": 1}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    rep = r.json()["report"]
    assert rep["state_changes"][0]["qty"] == -1
    from app.models import InventoryMovement
    base = seeded_db.query(InventoryMovement).count()
    r2 = _apply(client, did, "dropped during setup")
    assert r2.status_code == 200, r2.text
    assert seeded_db.query(InventoryMovement).count() == base + 1
    levels = client.get("/inventory/levels", headers=_login(client, "logistics_lead")) \
        .json()["items"]
    assert [i["qty"] for i in levels if i["sku"] == sku][0] == 3
    r3 = _revert(client, did, "it actually survived")
    assert r3.status_code == 200, r3.text
    assert seeded_db.query(InventoryMovement).count() == base


def test_type5_venue_change_preview_apply_revert(seeded_db, client):
    import datetime as dt_mod
    v2 = Venue(raw_id="V02", name="Auditorium", capacity=100,
               availability_windows=[], status="open")
    seeded_db.add(v2)
    seeded_db.flush()
    ev = seeded_db.query(Event).filter_by(raw_id="E01").first()
    ev.venue_id = seeded_db.query(Venue).filter_by(raw_id="V01").first().id
    ev.start_dt = dt_mod.datetime(2026, 10, 31, 9, 0)
    ev.end_dt = dt_mod.datetime(2026, 10, 31, 11, 0)
    seeded_db.commit()
    r = _pre(client, {"type": "venue_change",
                      "payload": {"event_raw_id": "E01",
                                  "new_venue_id": v2.id}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    assert r.json()["report"]["state_changes"][0]["new_venue"] == "Auditorium"
    r2 = _apply(client, did, "stage flooded")
    assert r2.status_code == 200, r2.text
    assert seeded_db.query(Event).filter_by(raw_id="E01").first().venue_id == v2.id
    r3 = _revert(client, did, "stage repaired")
    assert r3.status_code == 200, r3.text
    assert seeded_db.query(Event).filter_by(raw_id="E01").first().venue_id == \
        seeded_db.query(Venue).filter_by(raw_id="V01").first().id


def test_type6_vendor_shutdown_preview_apply_revert(seeded_db, client):
    import datetime as dt_mod
    v2 = seeded_db.query(Vendor).filter_by(raw_id="VND02").first()
    v1 = seeded_db.query(Vendor).filter_by(raw_id="VND01").first()
    o = VendorOrder(vendor_id=v2.id, day=dt_mod.date(2026, 10, 31),
                    meal="lunch", qty=50, dietary_tag="vegetarian",
                    paid=False)
    seeded_db.add(o)
    seeded_db.commit()
    r = _pre(client, {"type": "vendor_shutdown",
                      "payload": {"raw_id": "VND02"}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    r2 = _apply(client, did, "kitchen closed by health dept")
    assert r2.status_code == 200, r2.text
    assert seeded_db.query(Vendor).get(v2.id).status == "interrupted"
    assert seeded_db.query(VendorOrder).get(o.id).vendor_id == v1.id
    r3 = _revert(client, did, "reopened with a new certificate")
    assert r3.status_code == 200, r3.text
    assert seeded_db.query(Vendor).get(v2.id).status == "active"
    assert seeded_db.query(VendorOrder).get(o.id).vendor_id == v2.id


def test_type7_duplicate_merch_claim_preview_apply_revert(seeded_db, client):
    hlogi = _login(client, "logistics_lead")
    assert client.post("/merch/issue", json={"participant_raw_id": "P001",
                                             "reason": "check-in desk"},
                       headers=hlogi).status_code == 200
    r = _pre(client, {"type": "duplicate_merch_claim",
                      "payload": {"participant_raw_id": "P002"}})
    assert r.status_code == 200, r.text
    did = r.json()["disruption_id"]
    rep = r.json()["report"]
    assert any(v["type"] == "MERCH_ALREADY_ISSUED" for v in rep["new_violations"])
    r2 = _apply(client, did, "suspected double claim at desk 2")
    assert r2.status_code == 200, r2.text
    dup = seeded_db.query(Participant).filter_by(raw_id="P002").first()
    assert "DUPLICATE_MERCH_CLAIM" in (dup.quality_flags or [])
    r3 = _revert(client, did, "claim was legitimate")
    assert r3.status_code == 200, r3.text
    dup = seeded_db.query(Participant).filter_by(raw_id="P002").first()
    assert "DUPLICATE_MERCH_CLAIM" not in (dup.quality_flags or [])

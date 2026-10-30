"""Phase 4 API integration tests: schedule, accommodation, inventory, vendors."""
from sqlalchemy import text

from tests.test_phase3 import _login


def _reg(db):
    """the smallest real event scheduled on an open venue"""
    with db.bind.connect() as conn:
        events = conn.execute(text(
            "SELECT id, raw_id FROM events ORDER BY raw_id LIMIT 5")).fetchall()
        venues = conn.execute(text(
            "SELECT id, raw_id FROM venues ORDER BY raw_id LIMIT 3")).fetchall()
    return events, venues


def test_schedule_conflicts_runs_on_seeded_pack(seeded_db, client):
    h = _login(client, "director")
    r = client.get("/schedule/conflicts", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"conflicts", "suggestions", "checked_events", "summary"}


def test_schedule_events_crud_and_conflict_feedback(seeded_db, client):
    h = _login(client, "events_lead")
    r = client.get("/schedule/events", headers=h)
    assert r.status_code == 200
    events = r.json()["events"]
    assert events, "events imported from pack"
    eid = events[0]["id"]
    # schedule it explicitly -> operator entered (A-11)
    r2 = client.patch(f"/schedule/events/{eid}",
                      json={"venue_id": 1,
                            "start_dt": "2026-10-31 09:00",
                            "end_dt": "2026-10-31 11:00",
                            "reason": "operator scheduling"},
                      headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json()["audit_entry"]
    # viewer cannot schedule
    hv = _login(client, "viewer")
    r3 = client.patch(f"/schedule/events/{eid}",
                      json={"start_dt": "2026-10-31 12:00", "reason": "x"},
                      headers=hv)
    assert r3.status_code in (403, 422)


def test_schedule_move_rechecks_conflicts(seeded_db, client):
    h = _login(client, "director")
    evs, venues = _reg(seeded_db)
    raw_id = evs[0][1]
    with seeded_db.bind.connect() as conn:
        conn.execute(text(
            f"UPDATE events SET venue_id=1, start_dt='2026-10-31 09:00', "
            f"end_dt='2026-10-31 11:00' WHERE raw_id='{raw_id}'"))
    seeded_db.commit()
    r = client.post("/schedule/move",
                    json={"event_raw_id": raw_id, "venue_id": venues[-1][0],
                          "start": "2026-10-31 09:00", "end": "2026-10-31 11:00"},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["audit_entry"]


# ---------------------------------------------------------------- accommodation --
def test_accommodation_allocate_creates_draft_plan(seeded_db, client):
    h = _login(client, "accommodation_lead")
    r = client.post("/accommodation/allocate",
                    json={"preset": "min_cost", "reason": "evening run"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preset"] == "min_cost" and body["plan_id"]
    assert body["summary"]["requested"] >= body["summary"]["review_queue"] or \
        body["summary"]["requested"] > 0
    # ~950 unclear-gender people land in the review queue, never forced
    assert body["review_queue"]
    assert all(x["reason_code"] in ("UNCLEAR_GENDER", "UNCLEAR_ACCOMMODATION")
               for x in body["review_queue"])


def test_accommodation_plan_activate_and_supersede(seeded_db, client):
    h = _login(client, "director")
    r1 = client.post("/accommodation/allocate", json={"preset": "balanced"},
                     headers=h)
    r2 = client.post("/accommodation/allocate", json={"preset": "min_cost"}, headers=h)
    p1, p2 = r1.json()["plan_id"], r2.json()["plan_id"]
    assert client.post(f"/accommodation/plan/{p1}/activate", headers=h).status_code == 200
    assert client.post(f"/accommodation/plan/{p2}/activate", headers=h).status_code == 200
    # re-activating an active plan conflicts
    assert client.post(f"/accommodation/plan/{p2}/activate", headers=h).status_code == 409


def test_accommodation_assign_and_lock(seeded_db, client):
    h = _login(client, "director")
    r_alloc = client.post("/accommodation/allocate", json={"preset": "min_cost"}, headers=h)
    plan_id = r_alloc.json()["plan_id"]
    client.post(f"/accommodation/plan/{plan_id}/activate", headers=h)
    r_lock = client.post(f"/accommodation/plan/{plan_id}/lock",
                         json={"reason": "verified by ops"}, headers=h)
    assert r_lock.status_code == 200
    assert r_lock.json()["locked"] > 0
    # manual override on a specific participant
    r = client.post("/accommodation/assign",
                    json={"participant_id": 1, "room_id": 1, "reason": "fan issue"},
                    headers=h)
    assert r.status_code == 200 and r.json()["audit_entry"]


def test_accommodation_review_queue_never_empty_for_pack(seeded_db, client):
    h = _login(client, "accommodation_lead")
    r = client.get("/accommodation/review-queue", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1       # blanks (P006: gender+accommodation) -> review
    codes = {x["reason_code"] for x in body["review_queue"]}
    assert codes <= {"UNCLEAR_GENDER", "UNCLEAR_ACCOMMODATION"}


def test_accommodation_needs_elevated_role(seeded_db, client):
    hv = _login(client, "viewer")
    assert client.post("/accommodation/allocate", json={"preset": "balanced"},
                       headers=hv).status_code == 403
    assert client.get("/accommodation/shortage", headers=hv).status_code == 403


# ------------------------------------------------------------------ inventory --
def test_inventory_levels_and_movement(seeded_db, client):
    h = _login(client, "logistics_lead")
    r = client.get("/inventory/levels", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    item_id = items[0]["id"]
    before = [i for i in items if i["id"] == item_id][0]["qty"]
    r2 = client.post("/inventory/movements",
                     json={"item_id": item_id, "qty": 3, "reference": "restock"},
                     headers=h)
    assert r2.status_code == 200 and r2.json()["movement_id"]
    after = [i for i in client.get("/inventory/levels", headers=h).json()["items"]
             if i["id"] == item_id][0]["qty"]
    assert after == before + 3


def test_inventory_movement_zero_qty_rejected(seeded_db, client):
    h = _login(client, "logistics_lead")
    items = client.get("/inventory/levels", headers=h).json()["items"]
    r = client.post("/inventory/movements", json={"item_id": items[0]["id"], "qty": 0},
                    headers=h)
    assert r.status_code == 400


def test_merch_issue_once_per_cluster(seeded_db, client):
    h = _login(client, "logistics_lead")
    r1 = client.post("/merch/issue", json={"participant_raw_id": "P001",
                                           "reason": "check-in desk"}, headers=h)
    assert r1.status_code == 200, r1.text
    # same cluster again -> 409 issue-once rule
    r2 = client.post("/merch/issue", json={"participant_raw_id": "P002",
                                           "reason": "dup desk"}, headers=h)
    assert r2.status_code == 409
    assert "already received" in r2.json()["detail"]
    # a different, unrelated cluster can still be issued (P006 is size M too)
    r3 = client.post("/merch/issue", json={"participant_raw_id": "P006",
                                           "reason": "check-in desk"}, headers=h)
    assert r3.status_code == 200, r3.text


def test_merch_double_issue_needs_director_force(seeded_db, client):
    hv = _login(client, "volunteer")
    r1 = client.post("/merch/issue", json={"participant_raw_id": "P001",
                                           "reason": "desk"}, headers=hv)
    assert r1.status_code == 200, r1.text
    # volunteer cannot force
    r2 = client.post("/merch/issue",
                     json={"participant_raw_id": "P001", "force": True,
                           "reason": "lost shirt"}, headers=hv)
    assert r2.status_code == 403
    # director may force, and it is flagged in the audit trail
    hd = _login(client, "director")
    r3 = client.post("/merch/issue",
                     json={"participant_raw_id": "P001", "force": True,
                           "reason": "lost shirt"}, headers=hd)
    assert r3.status_code == 200
    with seeded_db.bind.connect() as conn:
        row = conn.execute(text(
            "SELECT after FROM audit_log WHERE id = " + str(r3.json()["audit_entry"])
        )).fetchone()
    assert row and '"forced"' in str(row[0])


def test_merch_issue_unknown_participant_404(seeded_db, client):
    h = _login(client, "logistics_lead")
    r = client.post("/merch/issue", json={"participant_raw_id": "PNEIN",
                                          "reason": "x"}, headers=h)
    assert r.status_code == 404


# -------------------------------------------------------------------- vendors --
def test_vendor_list_flags_compliance(seeded_db, client):
    h = _login(client, "vendor_lead")
    r = client.get("/vendors", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["vendors"]
    r2 = client.get("/vendors/compliance", headers=h)
    assert r2.status_code == 200
    comp = r2.json()
    # synthetic pack: VND02 expired, VND01 fine; the real pack has 4+4 issues
    assert "VND02" in comp["expired"]
    assert comp["vendors"][0]["status_code"] in ("EXPIRED", "EXPIRING_MID_FEST", "OK")


def test_vendor_coverage_matrix(seeded_db, client):
    h = _login(client, "vendor_lead")
    r = client.get("/vendors/coverage", headers=h)
    assert r.status_code == 200
    assert r.json()["matrix"]
    # every demand row has a vendor list (possibly empty -> uncovered flagged)
    for tag, row in r.json()["matrix"].items():
        assert isinstance(row["vendors"], list)


def test_vendor_rate_settlement_flow(seeded_db, client):
    h = _login(client, "vendor_lead")
    vs = client.get("/vendors", headers=h).json()["vendors"]
    vid = vs[0]["id"]
    r = client.patch(f"/vendors/{vid}/rate", json={"rate": 45, "reason": "negotiated"},
                     headers=h)
    assert r.status_code == 200 and r.json()["rate"] == 45
    r2 = client.get("/vendors/settlement", headers=h)
    assert r2.status_code == 200
    # vendors without a rate figure in pending entries (never guessed, A-13)
    assert r2.json()["pending_entries"]


def test_vendor_interrupt_preview_and_apply(seeded_db, client):
    h = _login(client, "director")
    vs = client.get("/vendors", headers=h).json()["vendors"]
    vid = vs[0]["id"]
    pv = client.post(f"/vendors/{vid}/interrupt/preview", headers=h)
    assert pv.status_code == 200
    assert "preview only" in pv.json()["note"]
    r = client.post(f"/vendors/{vid}/interrupt/apply",
                    json={"reason": "health dept visit"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "interrupted"
    # applying twice conflicts
    assert client.post(f"/vendors/{vid}/interrupt/apply", json={"reason": "x"},
                       headers=h).status_code == 409

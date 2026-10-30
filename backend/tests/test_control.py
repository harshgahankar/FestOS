"""Phase 6: control center tests (attention queue, KPIs, audit browser)."""
from tests.test_phase3 import _login


def test_attention_queue_surfaces_all_sources(seeded_db, client):
    h = _login(client, "director")
    r = client.get("/control/attention", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == len(body["items"]) >= 1
    sources = {i["source"] for i in body["items"]}
    # synthetic pack exercises: import issues, quarantine (P011), flags (P007),
    # accommodation review (P006), vendor compliance (VND02), diet coverage (jain)
    assert {"import", "participants", "accommodation", "vendors"} <= sources
    # severity ordering: errors before warnings before info
    order = {"error": 0, "warning": 1, "info": 2}
    sevs = [order[i["severity"]] for i in body["items"]]
    assert sevs == sorted(sevs)
    # every item carries the full finding shape
    for item in body["items"]:
        assert set(item) == {"source", "severity", "what", "entity", "action_hint"}
    # no silent trim: quarantined participant makes it (never dropped)
    assert any("P011" in i["what"] and i["severity"] == "error" for i in body["items"])
    assert any("VND02" in i["what"] for i in body["items"])


def test_kpis_before_and_after_plan(seeded_db, client):
    h = _login(client, "director")
    r = client.get("/control/kpis", headers=h)
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["participants"]["quarantined"] >= 1        # P011
    assert k["participants"]["linked_duplicates"] >= 2  # P002, P004 auto-merged
    assert k["events"]["total"] >= 1
    assert k["vendors"]["expired"] >= 1                 # VND02
    assert "jain" in k["vendors"]["uncovered_diet_tags"]
    # occupancy is null until a plan goes active (never guessed)
    assert k["occupancy"] is None
    h2 = _login(client, "accommodation_lead")
    plan_id = client.post("/accommodation/allocate", json={"preset": "min_cost"},
                          headers=h2).json()["plan_id"]
    client.post(f"/accommodation/plan/{plan_id}/activate", headers=h2)
    k2 = client.get("/control/kpis", headers=h).json()
    assert k2["occupancy"] is not None
    assert k2["occupancy"]["plan_id"] == plan_id
    assert k2["occupancy"]["requested"] >= k2["occupancy"]["review_queue"]


def test_audit_browser_filters(seeded_db, client):
    hd = _login(client, "director")
    # generate audited writes across entities
    h2 = _login(client, "accommodation_lead")
    client.post("/accommodation/allocate", json={"preset": "min_cost"}, headers=h2)
    r = client.get("/control/audit", headers=hd)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == len(body["entries"]) >= 1
    r2 = client.get("/control/audit",
                    params={"entity_type": "allocation_plan"}, headers=hd)
    assert r2.json()["total"] >= 1
    assert all(e["entity_type"] == "allocation_plan" for e in r2.json()["entries"])
    r3 = client.get("/control/audit",
                    params={"actor": "accommodation_lead",
                            "entity_type": "allocation_plan"}, headers=hd)
    assert r3.json()["total"] >= 1
    assert all(e["actor"] == "accommodation_lead" for e in r3.json()["entries"])
    # paging honours limit
    r4 = client.get("/control/audit", params={"limit": 1}, headers=hd)
    assert len(r4.json()["entries"]) == 1


def test_control_center_is_director_only(seeded_db, client):
    hv = _login(client, "viewer")
    assert client.get("/control/attention", headers=hv).status_code == 403
    assert client.get("/control/kpis", headers=hv).status_code == 403
    assert client.get("/control/audit", headers=hv).status_code == 403

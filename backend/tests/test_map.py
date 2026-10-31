"""GeoCommand tests: role layers, real-data derivations, audit and honesty rules."""
from datetime import datetime

from app import config as C
from app.models import (Allocation, AuditLog, Event, HostelRoom,
                        InventoryMovement, MapLocationLink, Venue)
from tests.test_phase3 import _login


def _create_location(client, headers, name, location_type, latitude=12.9716,
                     longitude=77.5946, links=None, **extra):
    payload = {"name": name, "location_type": location_type,
               "latitude": latitude, "longitude": longitude,
               "links": links or [], **extra}
    response = client.post("/map/locations", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _location_ids(client, headers, **params):
    response = client.get("/map/locations", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["locations"]}


def test_role_scoped_location_visibility_and_write_gate(seeded_db, client):
    director = _login(client, "director")
    venue_pin = _create_location(
        client, director, "Main Stage Pin", "venue",
        links=[{"entity_type": "venue", "entity_id": "V01"}])
    hostel_pin = _create_location(
        client, director, "B1 Pin", "hostel_block",
        links=[{"entity_type": "hostel_block", "entity_id": "B1"}])

    viewer = _login(client, "viewer")
    ids = _location_ids(client, viewer)
    assert venue_pin["id"] in ids
    assert hostel_pin["id"] not in ids
    assert client.get(f"/map/locations/{venue_pin['id']}",
                      headers=viewer).status_code == 200
    assert client.get(f"/map/locations/{hostel_pin['id']}",
                      headers=viewer).status_code == 404
    for path in ("/map/accommodation", "/map/logistics", "/map/vendors",
                 "/map/incidents", "/map/unmapped", "/map/entities"):
        assert client.get(path, headers=viewer).status_code == 403, path

    accommodation = _login(client, "accommodation_lead")
    ids = _location_ids(client, accommodation)
    assert hostel_pin["id"] in ids
    assert venue_pin["id"] not in ids
    assert client.get("/map/accommodation",
                      headers=accommodation).status_code == 200
    assert client.get("/map/logistics",
                      headers=accommodation).status_code == 403

    volunteer = _login(client, "volunteer")
    assert _location_ids(client, volunteer) == set()
    denied = client.post("/map/locations",
                         json={"name": "Rogue", "location_type": "venue"},
                         headers=viewer)
    assert denied.status_code == 403


def test_location_links_replace_and_are_audited(seeded_db, client):
    director = _login(client, "director")
    location = _create_location(
        client, director, "Venue Ops Pin", "venue", latitude=None,
        longitude=None, links=[{"entity_type": "venue", "entity_id": "V01"}])
    assert location["mapped"] is False
    assert location["links"][0]["label"] == "Main Stage"

    detail = client.get(f"/map/locations/{location['id']}",
                        headers=director).json()
    assert detail["contexts"]["venue"]["name"] == "Main Stage"
    assert detail["summary"]["venue"]["capacity"] == 250

    response = client.patch(
        f"/map/locations/{location['id']}",
        json={"latitude": 12.97, "longitude": 77.59,
              "links": [{"entity_type": "inventory_location",
                         "entity_id": "Main Stage"}],
              "reason": "pin placed at the stage store"},
        headers=director)
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["mapped"] is True
    assert [link["entity_type"] for link in updated["links"]] == \
        ["inventory_location"]
    assert updated["links"][0]["label"] == "Main Stage"
    old = seeded_db.query(MapLocationLink).filter_by(
        entity_type="venue", entity_id="V01").first()
    assert old is None

    audits = seeded_db.query(AuditLog).filter(
        AuditLog.entity_type.in_(("map_location", "map_location_link"))).all()
    assert audits
    assert all(entry.actor_id == "director" for entry in audits)
    assert any(entry.action == "update" for entry in audits
               if entry.entity_type == "map_location")


def test_invalid_coordinates_and_unverified_pins(seeded_db, client):
    director = _login(client, "director")
    lone_lat = client.post("/map/locations",
                           json={"name": "Half pin", "location_type": "venue",
                                 "latitude": 12.9},
                           headers=director)
    assert lone_lat.status_code == 400
    out_of_range = client.post("/map/locations",
                               json={"name": "Bad pin", "location_type": "venue",
                                     "latitude": 91, "longitude": 77},
                               headers=director)
    assert out_of_range.status_code == 422
    bad_parent = client.post("/map/locations",
                             json={"name": "Orphan", "location_type": "venue",
                                   "parent_location_id": 99999},
                             headers=director)
    assert bad_parent.status_code == 400

    pin = _create_location(client, director, "Unverified Pin", "venue")
    verify = client.post(f"/map/locations/{pin['id']}/verify",
                         json={"reason": "checked on site"}, headers=director)
    assert verify.status_code == 200, verify.text
    assert verify.json()["coordinate_verification_status"] == "verified"
    assert verify.json()["coordinates_verified"] is True

    without_coords = _create_location(client, director, "No Pin", "venue",
                                      latitude=None, longitude=None)
    refusal = client.post(f"/map/locations/{without_coords['id']}/verify",
                          headers=director)
    assert refusal.status_code == 409


def test_unmapped_entities_and_fallback_centre(seeded_db, client):
    director = _login(client, "director")
    settings = client.get("/map/settings", headers=director).json()
    assert settings["configured"] is False
    assert settings["center"] == {"latitude": C.MAP["FALLBACK_CENTER"][0],
                                  "longitude": C.MAP["FALLBACK_CENTER"][1]}
    assert settings["zoom"] == C.MAP["FALLBACK_ZOOM"]

    unmapped = client.get("/map/unmapped", headers=director).json()
    keys = {(row.get("entity_type"), row.get("entity_id"))
            for row in unmapped["unmapped"] if row["kind"] == "entity"}
    assert ("hostel_block", "B1") in keys
    assert ("hostel_block", "G1") in keys
    assert ("external_stay", "EXT01") in keys
    assert ("venue", "V01") in keys
    assert ("vendor", "VND01") in keys
    assert ("inventory_location", "Main Stage") in keys
    assert not any(str(entity_id).startswith("P") for _, entity_id in keys)

    _create_location(client, director, "Main Stage Pin", "venue",
                     links=[{"entity_type": "venue", "entity_id": "V01"}])
    after = client.get("/map/unmapped", headers=director).json()
    keys_after = {(row.get("entity_type"), row.get("entity_id"))
                  for row in after["unmapped"] if row["kind"] == "entity"}
    assert ("venue", "V01") not in keys_after

    entities = client.get("/map/entities", headers=director).json()
    venue = [row for row in entities["entities"]
             if row["entity_type"] == "venue" and row["entity_id"] == "V01"][0]
    assert venue["mapped"] is True

    saved = client.patch("/map/settings",
                         json={"latitude": 12.9, "longitude": 77.5,
                               "zoom": 17, "label": "Main campus"},
                         headers=director)
    assert saved.status_code == 200, saved.text
    assert saved.json()["configured"] is True
    assert client.patch("/map/settings",
                        json={"latitude": 12.9, "longitude": 77.5},
                        headers=_login(client, "events_lead")).status_code == 403


def test_occupancy_comes_from_the_active_plan(seeded_db, client):
    accommodation = _login(client, "accommodation_lead")
    before = client.get("/map/accommodation", headers=accommodation).json()
    assert sum(block["totals"]["allocated_beds"]
               for block in before["hostels"]) == 0
    plan = client.post("/accommodation/allocate", json={"preset": "min_cost"},
                       headers=accommodation)
    assert plan.status_code == 200, plan.text
    draft = client.get("/map/accommodation", headers=accommodation).json()
    assert all(block["totals"]["allocated_beds"] == 0
               for block in draft["hostels"]), \
        "draft plans must not count as confirmed occupancy"
    assert draft["active_plan"] is None

    activated = client.post(
        f"/accommodation/plan/{plan.json()['plan_id']}/activate",
        headers=accommodation)
    assert activated.status_code == 200, activated.text

    room_ids = [room.id for room in seeded_db.query(HostelRoom)
                .filter(HostelRoom.hostel == "B1").all()]
    expected = len([allocation for allocation in
                    seeded_db.query(Allocation).all()
                    if allocation.room_id in room_ids])
    data = client.get("/map/accommodation", headers=accommodation).json()
    b1 = [block for block in data["hostels"] if block["block"] == "B1"][0]
    assert b1["totals"]["allocated_beds"] == expected
    assert b1["totals"]["allocated_beds"] > 0
    assert data["active_plan"]["id"] == plan.json()["plan_id"]


def test_map_summary_includes_external_beds(seeded_db, client):
    director = _login(client, "director")
    response = client.get("/map/summary", headers=director)
    assert response.status_code == 200, response.text
    accommodation = response.json()["accommodation"]
    assert accommodation["external_properties"] > 0
    assert accommodation["total_beds"] > 0
    assert accommodation["total_beds"] == (accommodation["allocated_beds"]
                                           + accommodation["vacant_beds"])


def test_event_status_at_start_and_end_boundaries(seeded_db, client):
    venue = seeded_db.query(Venue).filter_by(raw_id="V01").first()
    event = seeded_db.query(Event).filter_by(raw_id="E01").first()
    event.venue_id = venue.id
    event.start_dt = datetime(2026, 10, 30, 10, 0)
    event.end_dt = datetime(2026, 10, 30, 11, 0)
    seeded_db.commit()

    events_lead = _login(client, "events_lead")

    def venue_row(at):
        response = client.get("/map/events", params={"at": at},
                              headers=events_lead)
        assert response.status_code == 200, response.text
        return response.json()["venues"][0]

    at_start = venue_row("2026-10-30T10:00:00+05:30")
    assert at_start["current_events"][0]["status"] == "ongoing"
    assert at_start["status"]["code"] == "ongoing"

    before_end = venue_row("2026-10-30T10:59:59+05:30")
    assert before_end["current_events"][0]["status"] == "ongoing"

    at_end = venue_row("2026-10-30T11:00:00+05:30")
    assert at_end["current_events"] == []
    assert at_end["completed_count"] == 1

    before_start = venue_row("2026-10-30T09:59:00+05:30")
    assert before_start["upcoming_events"][0]["status"] == "upcoming"
    assert before_start["status"]["code"] == "upcoming"


def test_expired_vendor_is_never_verified_compliant(seeded_db, client):
    vendor_lead = _login(client, "vendor_lead")
    response = client.get("/map/vendors",
                          params={"at": "2026-10-30T12:00:00+05:30"},
                          headers=vendor_lead)
    assert response.status_code == 200, response.text
    rows = {row["raw_id"]: row for row in response.json()["vendors"]}
    assert rows["VND01"]["verified_compliant"] is True
    assert rows["VND01"]["status"]["code"] == "available"
    assert rows["VND02"]["compliance_status"] == "EXPIRED"
    assert rows["VND02"]["verified_compliant"] is False
    assert rows["VND02"]["status"]["code"] == "compliance_failed"

    late = client.get("/map/vendors",
                      params={"at": "2026-10-30T23:30:00+05:30"},
                      headers=vendor_lead).json()
    late_rows = {row["raw_id"]: row for row in late["vendors"]}
    assert late_rows["VND01"]["is_open"] is False
    assert late_rows["VND01"]["status"]["code"] == "closed"


def test_inventory_location_stock_matches_the_ledger(seeded_db, client):
    logistics = _login(client, "logistics_lead")
    first = client.get("/map/logistics", headers=logistics).json()
    main = [row for row in first["locations"]
            if row["label"] == "Main Stage"][0]
    mic = [item for item in main["items"] if item["name"] == "mic"][0]
    assert mic["on_hand"] == 4

    item_id = mic["id"]
    moved = client.post("/inventory/movements",
                        json={"item_id": item_id, "qty": 2,
                              "to_location": "Main Stage",
                              "reference": "top-up"},
                        headers=logistics)
    assert moved.status_code == 200, moved.text
    after = client.get("/map/logistics", headers=logistics).json()
    main = [row for row in after["locations"]
            if row["label"] == "Main Stage"][0]
    mic = [item for item in main["items"] if item["id"] == item_id][0]
    assert mic["on_hand"] == 6

    issued = client.post("/merch/issue",
                         json={"participant_raw_id": "P001",
                               "reason": "welcome kit"},
                         headers=logistics)
    assert issued.status_code == 200, issued.text
    labels = {row["label"] for row in
              client.get("/map/logistics", headers=logistics).json()["locations"]}
    assert "P001" not in labels
    merch = [row for row in
             client.get("/map/logistics", headers=logistics).json()["locations"]
             if row["label"] == "Merch Desk"][0]
    assert merch["reserved_quantity"] == 2
    assert merch["items"][0]["available"] == \
        merch["items"][0]["on_hand"] - 2

    movements = seeded_db.query(InventoryMovement).all()
    assert any(m.from_location == "merch store" and m.to_location == "P001"
               for m in movements)


def test_applied_disruption_marks_the_location(seeded_db, client):
    director = _login(client, "director")
    pin = _create_location(
        client, director, "B1 Pin", "hostel_block",
        links=[{"entity_type": "hostel_block", "entity_id": "B1"}])

    preview = client.post("/disruptions/preview",
                          json={"type": "hostel_closure",
                                "payload": {"hostel": "B1"}},
                          headers=director)
    assert preview.status_code == 200, preview.text
    disruption_id = preview.json()["disruption_id"]
    applied = client.post(f"/disruptions/{disruption_id}/apply",
                          json={"reason": "water damage"},
                          headers=director)
    assert applied.status_code == 200, applied.text

    detail = client.get(f"/map/locations/{pin['id']}", headers=director).json()
    assert detail["has_incident"] is True
    assert detail["incident_count"] == 1
    assert detail["operational_status"]["code"] == "incident"
    assert detail["contexts"]["hostel_block"]["status"]["code"] == "unavailable"

    incidents = client.get("/map/incidents", headers=director).json()
    assert incidents["counts"]["active"] == 1
    assert incidents["incidents"][0]["verified"] is True
    assert incidents["incidents"][0]["targets"][0]["entity_id"] == "B1"


def test_volunteer_sees_only_assigned_duties(seeded_db, client):
    director = _login(client, "director")
    assigned = _create_location(client, director, "Registration Desk",
                                "inventory_location")
    other = _create_location(client, director, "Store Room A",
                             "inventory_location")

    duty = client.post("/map/duties",
                       json={"username": "volunteer",
                             "location_id": assigned["id"],
                             "task_type": "pickup",
                             "label": "Collect merch boxes"},
                       headers=director)
    assert duty.status_code == 201, duty.text
    duty_id = duty.json()["id"]

    volunteer = _login(client, "volunteer")
    ids = _location_ids(client, volunteer)
    assert assigned["id"] in ids
    assert other["id"] not in ids
    detail = client.get(f"/map/locations/{assigned['id']}",
                        headers=volunteer).json()
    assert [row["id"] for row in detail["duties"]] == [duty_id]
    assert client.get(f"/map/locations/{other['id']}",
                      headers=volunteer).status_code == 404
    assert client.post("/map/duties",
                       json={"username": "volunteer",
                             "location_id": other["id"]},
                       headers=volunteer).status_code == 403

    removed = client.delete(f"/map/duties/{duty_id}", headers=director)
    assert removed.status_code == 200, removed.text
    assert removed.json()["active"] is False
    assert _location_ids(client, volunteer) == set()


def test_scoped_lead_edit_preserves_other_roles_links(seeded_db, client):
    director = _login(client, "director")
    shared = _create_location(
        client, director, "Shared venue/hostel pin", "venue",
        links=[{"entity_type": "venue", "entity_id": "V01"},
               {"entity_type": "hostel_block", "entity_id": "B1"}])

    accommodation = _login(client, "accommodation_lead")
    assert shared["id"] in _location_ids(client, accommodation)

    response = client.patch(
        f"/map/locations/{shared['id']}",
        json={"name": "Shared pin renamed",
              "links": [{"entity_type": "hostel_block", "entity_id": "B1"}],
              "reason": "accommodation note updated"},
        headers=accommodation)
    assert response.status_code == 200, response.text
    visible = {(link["entity_type"], link["entity_id"])
               for link in response.json()["links"]}
    assert visible == {("hostel_block", "B1")}

    director_detail = client.get(f"/map/locations/{shared['id']}",
                                 headers=director).json()
    links = {(link["entity_type"], link["entity_id"])
             for link in director_detail["links"]}
    assert links == {("venue", "V01"), ("hostel_block", "B1")}
    assert director_detail["name"] == "Shared pin renamed"

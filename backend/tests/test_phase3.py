"""Phase 3 masking / reveal / merge tests (permission matrix, spec p.10)."""
from sqlalchemy import text

from app import config as C

MASK = C.MASK_TEXT


def _login(client, role):
    r = client.post("/auth/login", json={"username": role,
                                         "password": C.DEMO_PASSWORDS[role]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _first_participant(client, headers, **params):
    r = client.get("/participants", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["participants"][0]


def _audit_kind(db, audit_id: int) -> str:
    with db.bind.connect() as conn:
        return conn.execute(text(
            f"SELECT kind FROM audit_log WHERE id = {audit_id}")).scalar()


def test_list_masks_phone_for_viewer(seeded_db, client):
    h = _login(client, "viewer")
    p = _first_participant(client, h, search="P001")
    assert p["phone"] == MASK


def test_director_sees_phone_without_reveal(seeded_db, client):
    h = _login(client, "director")
    p = _first_participant(client, h, search="P001")
    assert p["raw_id"] == "P001"
    assert p["phone"] and p["phone"] != MASK


def test_accommodation_lead_sees_accessibility_not_phone(seeded_db, client):
    h = _login(client, "accommodation_lead")
    p = _first_participant(client, h, flag="POST_FEST_ARRIVAL")
    assert p["raw_id"] == "P007"
    assert p["accessibility_details"] != MASK
    assert p["phone"] == MASK


def test_viewer_reveal_denied(seeded_db, client):
    h = _login(client, "viewer")
    p = _first_participant(client, h)
    r = client.post(f"/participants/{p['id']}/reveal",
                    json={"fields": ["phone"], "reason": "curiosity"}, headers=h)
    assert r.status_code == 403
    assert "may not reveal" in r.json()["detail"]


def test_reveal_returns_values_and_is_audited(seeded_db, client):
    h = _login(client, "director")
    p = _first_participant(client, h, search="P001")
    r = client.post(f"/participants/{p['id']}/reveal",
                    json={"fields": ["phone"], "reason": "caller follow-up"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["fields"]["phone"] == p["phone"]
    assert body["audit_entry"]
    assert _audit_kind(seeded_db, body["audit_entry"]) == "reveal"


def test_partial_reveal_403_never_leaks(seeded_db, client):
    h = _login(client, "events_lead")
    p = _first_participant(client, h, search="P001")
    r = client.post(f"/participants/{p['id']}/reveal",
                    json={"fields": ["dietary_tags", "phone"], "reason": "check"},
                    headers=h)
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert "phone" in detail          # only the denial reason is returned, no values


def test_patch_is_audited(seeded_db, client):
    h = _login(client, "director")
    p = _first_participant(client, h, search="P001")
    r = client.patch(f"/participants/{p['id']}",
                     json={"tshirt_size": "XXL", "note": "size fix"}, headers=h)
    assert r.status_code == 200 and r.json()["changed"] == ["tshirt_size"]
    assert _audit_kind(seeded_db, r.json()["audit_entry"]) == "manual"


def test_patch_empty_body_400(seeded_db, client):
    h = _login(client, "director")
    p = _first_participant(client, h, search="P001")
    r = client.patch(f"/participants/{p['id']}", json={"note": "only a note"}, headers=h)
    assert r.status_code == 400


def test_merge_unmerge_reversible_and_audited(seeded_db, client):
    h = _login(client, "director")
    p1 = _first_participant(client, h, search="P001")
    p2 = _first_participant(client, h, search="P002")
    # the importer auto-merged P002 -> P001; unmerge first, then exercise the endpoint
    client.post(f"/participants/{p2['id']}/unmerge", json={"reason": "restage"},
                headers=h)
    r = client.post("/participants/merge",
                    json={"canonical_id": p1["id"], "duplicate_id": p2["id"],
                          "reason": "manual registration error"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["duplicate"]["raw_id"] == "P002"
    out = client.get("/participants/duplicates", headers=h).json()
    canon_ids = {c["canonical"]["id"] for c in out["clusters"]}
    assert p1["id"] in canon_ids
    r2 = client.post(f"/participants/{p2['id']}/unmerge",
                     json={"reason": "false positive"}, headers=h)
    assert r2.status_code == 200 and r2.json()["status"] == "active"


def test_merge_into_merged_canonical_conflicts(seeded_db, client):
    h = _login(client, "director")
    p1 = _first_participant(client, h, search="P001")
    p2 = _first_participant(client, h, search="P002")
    p3 = _first_participant(client, h, search="P003")
    client.post(f"/participants/{p2['id']}/unmerge", json={"reason": "restage"}, headers=h)
    r = client.post("/participants/merge",
                    json={"canonical_id": p1["id"], "duplicate_id": p2["id"],
                          "reason": "ok"}, headers=h)
    assert r.status_code == 200, r.text
    r2 = client.post("/participants/merge",
                     json={"canonical_id": p2["id"], "duplicate_id": p3["id"],
                           "reason": "bad"}, headers=h)
    assert r2.status_code == 409


def test_merge_requires_reason(seeded_db, client):
    h = _login(client, "director")
    r = client.post("/participants/merge", json={}, headers=h)
    assert r.status_code == 422   # reason is required by schema


def test_participant_detail_views(seeded_db, client):
    hv = _login(client, "viewer")
    hd = _login(client, "director")
    p = _first_participant(client, hd, search="P001")
    det = client.get(f"/participants/{p['id']}", headers=hv).json()
    assert det["participant"]["raw_id"] == "P001"
    assert det["contingent"] is not None
    assert det["participant"]["contingent"] == "C01"   # csv contingent_id string
    audit = client.get(f"/participants/{p['id']}/audit", headers=hd).json()
    assert audit["entries"]

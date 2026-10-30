"""Auth: JWT login, require_role (403 for wrong role), permission gating."""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")


def _login(client, username, password, **kw):
    return client.post("/auth/login",
                       json={"username": username, "password": password})


def test_login_success_and_role(client):
    r = _login(client, "director", "director123")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "director"
    assert body["token_type"] == "bearer"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {"username": "director", "role": "director"}


def test_login_wrong_password_and_no_token(client):
    assert _login(client, "director", "bad").status_code == 401
    assert _login(client, "ghost", "x").status_code == 401
    assert client.get("/auth/me").status_code == 401                     # no token
    assert client.get("/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_wrong_role_gets_403(client):
    vol = _login(client, "volunteer", "vol123").json()["access_token"]
    dirr = _login(client, "director", "director123").json()["access_token"]
    r_vol = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {vol}"})
    r_dir = client.get("/auth/admin-only", headers={"Authorization": f"Bearer {dirr}"})
    assert r_vol.status_code == 403
    assert "requires one of" in r_vol.json()["detail"]
    assert r_dir.status_code == 200


def test_all_seeded_roles_can_login(client):
    roles = {"director": "director123", "accommodation_lead": "accom123",
             "events_lead": "events123", "logistics_lead": "logi123",
             "vendor_lead": "vendor123", "volunteer": "vol123", "viewer": "view123"}
    for username, password in roles.items():
        r = _login(client, username, password)
        assert r.status_code == 200, username
        assert r.json()["role"] == username


def test_import_endpoints_role_gated(client):
    vol = {"Authorization": "Bearer " + _login(client, "volunteer", "vol123").json()["access_token"]}
    dirr = {"Authorization": "Bearer " + _login(client, "director", "director123").json()["access_token"]}
    assert client.post("/imports/upload", headers=vol).status_code == 403
    assert client.post("/imports/reset", headers=vol).status_code == 403
    assert client.post("/imports/upload", headers=dirr).status_code == 200
    assert client.post("/imports/reset", headers=dirr).status_code == 200


def test_reconciliation_public_read(client):
    r = client.get("/imports/reconciliation")
    assert r.status_code == 200
    body = r.json()
    assert body["raw_imported"] == 8 and body["active"] == 4


def test_issues_endpoint(client):
    issues = client.get("/imports/issues").json()
    codes = {i["code"] for i in issues}
    assert "QUARANTINED_ROW" in codes
    assert "FK_MISSING_QUARANTINED" in codes

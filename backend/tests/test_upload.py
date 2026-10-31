"""End-to-end test of POST /imports/upload with real uploaded CSV files."""
from pathlib import Path


def test_upload_csv_files(seeded_db, client, tmp_path: Path):
    from tests.test_phase3 import _login

    h = _login(client, "director")
    src = Path(__import__("app.config", fromlist=["DATA_DIR"]).DATA_DIR)
    files = []
    for name in ("participants.csv", "contingents.csv", "registrations.csv"):
        p = src / name
        files.append(("files", (name, p.read_bytes(), "text/csv")))
    r = client.post("/imports/upload", files=files, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_ok"]
    assert set(body["files_loaded"]) >= {"participants.csv", "contingents.csv",
                                        "registrations.csv"}


def test_upload_rejects_unsupported_file(seeded_db, client):
    from tests.test_phase3 import _login

    h = _login(client, "director")
    r = client.post("/imports/upload",
                    files=[("files", ("junk.csv", b"a,b\n1,2", "text/csv"))],
                    headers=h)
    assert r.status_code == 400, r.text

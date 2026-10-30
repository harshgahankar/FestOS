import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

BASE = Path(__file__).resolve().parents[1]           # backend/
sys.path.insert(0, str(BASE))

# tests always run with the offline local-auth mode (no Supabase, no .env)
os.environ["FESTOS_LOAD_DOTENV"] = "0"
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_ANON_KEY", None)

REAL_PACK = BASE.parent / "dataset"


@pytest.fixture(scope="session")
def synthetic_pack_dir(tmp_path_factory):
    """Tiny CSV pack exercising dedupe, quarantine and integrity paths."""
    d = tmp_path_factory.mktemp("pack")
    (d / "venues.csv").write_text(
        "venue_id,venue_name,capacity,availability_windows,indoor_outdoor\n"
        "V01,Main Stage,250,2026-10-30 08:00-22:00,outdoor\n", encoding="utf-8")
    (d / "contingents.csv").write_text(
        "contingent_id,college,leader,escort,strength_declared,preferences\n"
        "C01,Alpha College,Asha Rao,Deepa Rai,3,low cost\n"
        "C02,Beta College,Ravi Iyer,Nita Bose,2,quiet rooms\n", encoding="utf-8")
    (d / "events.csv").write_text(
        "event_id,event_name,type,rounds,duration_minutes,venue_requirements,"
        "equipment_needs,volunteers_needed\n"
        "E01,Quiz,solo,single,60,seating,table,2\n", encoding="utf-8")
    (d / "hostels.csv").write_text(
        "room_id,block,floor,gender,capacity,accessibility,status\n"
        "B1-0-01,B1,0,boys,2,yes,available\n"
        "G1-0-01,G1,0,girls,3,no,available\n", encoding="utf-8")
    (d / "external_stays.csv").write_text(
        "property_id,property_name,beds,cost_per_bed_per_night,distance_km,"
        "transport_availability\nEXT01,Lodge,10,900,5,yes\n", encoding="utf-8")
    (d / "vendors.csv").write_text(
        "vendor_id,vendor_name,menu,dietary_options,hygiene_certificate_expiry,hours,"
        "capacity,payment_terms\n"
        "VND01,Veg Corner,South Indian,vegetarian,2027-01-01,07:00-23:00,200,"
        "minimum guarantee\n"
        "VND02,Old Stall,Chaat,vegetarian,2026-09-29,07:00-23:00,100,"
        "per item sold\n", encoding="utf-8")
    (d / "core_team.csv").write_text(
        "member_id,name,role,shift,phone\n"
        "ST01,Ops Lead,Festival Director,22:00-06:00,+91-9000000001\n", encoding="utf-8")
    (d / "inventory_logistics.csv").write_text(
        "item_id,item,quantity,location,condition\n"
        "L00-1,mic,4,Main Stage,good\n"
        "L00-2,speaker,2,Van 1,under repair\n", encoding="utf-8")
    (d / "inventory_merch.csv").write_text(
        "item,size,quantity,reserved_quantity\nT-shirt,M,10,2\n", encoding="utf-8")
    # P001/P002 exact twins (phone differs); P003/P004 fuzzy twins (name typo + junk
    # phone); P005 accessibility yes; P007 blank gender+blank dietary+blank accommodation
    # (three-state checks); P009 impossible travel -> flagged; P011 unparsable age ->
    # quarantined (never dropped)
    participants = (
        "participant_id,name,college,contingent_id,gender_as_given,age,contact,"
        "accessibility_needs,dietary_needs,arrival_datetime,departure_datetime,"
        "accommodation_requested,tshirt_size\n"
        "P001,Ana Roy,Alpha College,C01,Female,20,+91-8000000001,None,Vegetarian,"
        "2026-10-30 08:00,2026-11-01 18:00,yes,M\n"
        "P002,Ana Roy,Alpha College,C01,Female,20,+91-8000000099,None,Vegetarian,"
        "2026-10-30 08:00,2026-11-01 18:00,yes,M\n"
        "P003,Adi Sen,Alpha College,C01,Male,22,+91-8000000002,None,Non-vegetarian,"
        "2026-10-30 09:00,2026-11-01 19:00,no,L\n"
        "P004,Aadi Sen,Alpha College,C01,Male,22,+91-8888888888,None,Non-vegetarian,"
        "2026-10-30 09:00,2026-11-01 19:00,no,L\n"
        "P005,Lea Dsouza,Beta College,C02,Female,19,+91-8000000003,Wheelchair access,"
        "Jain,2026-10-30 10:00,2026-11-01 20:00,yes,S\n"
        "P006,Unspecified,Beta College,C02,,,+91-8000000004,None,,"
        "2026-10-30 08:00,2026-11-01 18:00,,M\n"
        "P007,Loop Travel,Beta College,C02,Male,23,+91-8000000007,None,Vegetarian,"
        "2026-11-02 02:00,2026-10-31 18:00,yes,M\n"
        "P011,Bad Age,Beta College,C02,Female,2X,+91-8000000008,None,Vegetarian,"
        "2026-10-30 08:00,2026-11-01 18:00,yes,M\n")
    (d / "participants.csv").write_text(participants, encoding="utf-8")
    (d / "registrations.csv").write_text(
        "participant_id,event_id,team_id\n"
        "P001,E01,\nP003,E01,\n"
        "P_INVALID,E01,\n", encoding="utf-8")
    return d


@pytest.fixture()
def db_session(synthetic_pack_dir, monkeypatch):
    """Isolated empty database session per test; DATA_DIR -> synthetic pack."""
    eng = create_engine("sqlite://",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    from app.db import Base
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    from app import config as C
    monkeypatch.setattr(C, "DATA_DIR", synthetic_pack_dir)
    yield session
    session.close()
    eng.dispose()


@pytest.fixture()
def seeded_db(db_session):
    """Synthetic pack imported into the test DB (users included)."""
    import seed as seed_mod
    seed_mod.rebuild_demo(db_session, verbose=False)
    return db_session


@pytest.fixture()
def client(seeded_db):
    """FastAPI TestClient wired to the isolated test DB (users + pack seeded)."""
    from app.main import app
    from app.db import get_db

    app.dependency_overrides[get_db] = lambda: seeded_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)

"""Importer: duplicate detection, quarantine, funnel math, idempotency, blank rules."""
import sys
from pathlib import Path
import sys as _sys

BASE = Path(__file__).resolve().parents[1]
_sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from engines.importer import (find_duplicate_clusters, link_duplicates,  # noqa: E402
                              reconciliation, run_import_all)
from app.models import Participant, Registration  # noqa: E402
from tests.conftest import REAL_PACK  # noqa: E402


def _raw(id_, **kw):
    base = {"participant_id": id_, "name": "X", "college": "Alpha College",
            "contingent_id": "C01", "gender_as_given": "Male", "age": "20",
            "contact": "+91-8000000000", "accessibility_needs": "None",
            "dietary_needs": "Vegetarian", "arrival_datetime": "2026-10-30 08:00",
            "departure_datetime": "2026-11-01 18:00", "accommodation_requested": "yes",
            "tshirt_size": "M"}
    base.update(kw)
    return base


def _funnel(session):
    r = reconciliation(session)
    return {k: r[k] for k in ("raw_imported", "duplicates_merged", "quarantined",
                              "cancelled_test_junk", "flagged", "active")}


# ---------------------------------------------------------------- pure function
def test_exact_duplicate_cluster_on_fingerprint():
    rows = [
        _raw("P0001"),
        _raw("P0002", contact="+91-8999999999"),          # only phone differs
        _raw("P0003", gender_as_given="Female"),          # different person
    ]
    clusters = find_duplicate_clusters(rows)
    assert clusters == [["P0001", "P0002"]]


def test_fuzzy_duplicate_tolerates_name_typo_with_junk_phone():
    rows = [
        _raw("P0001", name="Adi Sen"),
        _raw("P0002", name="Aadi Sen", contact="+91-8888888888"),  # typo + junk phone
        _raw("P0003", name="Bob Ray"),                     # different person entirely
    ]
    clusters = find_duplicate_clusters(rows)
    assert clusters == [["P0001", "P0002"]]


def test_name_reuse_alone_is_never_a_duplicate():
    # same test-anonymised name throughout; other fields disagree -> distinct people
    rows = [_raw("P0001"),
            _raw("P0002", contact="+91-8000000002", gender_as_given="Female",
                 tshirt_size="S", departure_datetime="2026-10-31 12:00"),
            _raw("P0003", contact="+91-8000000003", age="26",
                 dietary_needs="Jain", arrival_datetime="2026-10-29 08:00")]
    assert find_duplicate_clusters(rows) == []


# ------------------------------------------------------------- synthetic pack
def test_funnel_math_synthetic_pack(seeded_db):
    # 8 raw: 2 exact dup merge, 0 quarantine?? P011 bad age -> quarantined; P007 impossible
    # travel -> flagged.
    f = _funnel(seeded_db)
    assert f["raw_imported"] == 8
    assert f["duplicates_merged"] == 2            # P002 -> P001, P004 -> P003
    assert f["quarantined"] == 1                  # P011 (age 2X unparsable)
    assert f["flagged"] == 1                      # P007 (dep < arr, post-fest arrival)
    assert f["active"] == 4                       # P001, P003, P005, P006
    assert f["raw_imported"] == f["duplicates_merged"] + f["quarantined"] + \
        f["cancelled_test_junk"] + f["flagged"] + f["active"]


def test_duplicate_link_reversible(seeded_db):
    d1 = seeded_db.query(Participant).filter(Participant.raw_id == "P002").one()
    d2 = seeded_db.query(Participant).filter(Participant.raw_id == "P004").one()
    canon1 = seeded_db.get(Participant, d1.merged_into)
    canon2 = seeded_db.get(Participant, d2.merged_into)
    assert canon1.raw_id == "P001" and canon2.raw_id == "P003"
    assert d1.status == "duplicate" and "DUPLICATE_LINKED" in d1.quality_flags

    # reversible: unlink restores active status, then re-link reproduces the graph
    d1.merged_into, d2.merged_into = None, None
    d1.status = d2.status = "active"
    d1.quality_flags = [f for f in d1.quality_flags if f != "DUPLICATE_LINKED"]
    d2.quality_flags = [f for f in d2.quality_flags if f != "DUPLICATE_LINKED"]
    result = link_duplicates(seeded_db)
    assert result["duplicates_linked"] == 2
    seeded_db.refresh(d1)
    assert d1.status == "duplicate" and d1.merged_into == canon1.id


def test_quarantine_never_drops_rows(seeded_db):
    bad = seeded_db.query(Participant).filter(Participant.raw_id == "P011").one()
    assert bad.status == "quarantined"
    from app.models import ImportIssue
    codes = {i.code for i in seeded_db.query(ImportIssue).all()}
    assert "QUARANTINED_ROW" in codes
    # broken FK registration is quarantined too, and never silently dropped
    reg = seeded_db.query(Registration).filter(
        Registration.participant_raw_id == "P_INVALID").one()
    assert reg.status == "quarantined"
    assert seeded_db.query(Registration).count() == 3


def test_blanks_are_never_interpreted_as_no(seeded_db):
    p6 = seeded_db.query(Participant).filter(Participant.raw_id == "P006").one()
    assert p6.gender == "unknown"
    assert p6.dietary_status == "unknown" and p6.dietary_tags == []
    assert p6.accommodation_requested == "unknown"
    assert "DIETARY_UNVERIFIED" in p6.quality_flags
    assert "GENDER_UNDECLARED" in p6.quality_flags
    p5 = seeded_db.query(Participant).filter(Participant.raw_id == "P005").one()
    assert p5.accessibility_status == "yes"
    p1 = seeded_db.query(Participant).filter(Participant.raw_id == "P001").one()
    assert p1.accessibility_status == "no"      # explicit literal 'None'


def test_idempotent_reimport(seeded_db, synthetic_pack_dir):
    f1 = _funnel(seeded_db)
    report = run_import_all(seeded_db, synthetic_pack_dir)
    f2 = _funnel(seeded_db)
    assert f1 == f2                              # same funnel, no churn
    assert report["issues_by_code"].get("CHANGED_ON_REIMPORT", 0) == 0
    link = link_duplicates(seeded_db)
    assert link["duplicates_linked"] == 0        # already linked, nothing new


def test_contingent_size_mismatch_flagged(seeded_db):
    from app.models import ImportIssue
    msgs = [i.message for i in seeded_db.query(ImportIssue).filter(
        ImportIssue.code == "CONTINGENT_SIZE_MISMATCH").all()]
    assert any("Alpha College" in m for m in msgs)   # declared 3, actual 1


def test_real_pack_funnel_numbers():
    """Full real pack: 2,836 raw -> 2 duplicates -> 0 quarantined -> 0 junk ->
    3 flagged -> 2,831 active (expected 2,400; the +431 is surfaced, A-08)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    report = run_import_all(db, REAL_PACK)
    recon = report["reconciliation"]
    assert recon["raw_imported"] == 2836
    assert recon["duplicates_merged"] == 2
    assert recon["quarantined"] == 0
    assert recon["cancelled_test_junk"] == 0
    assert recon["flagged"] == 3
    assert recon["active"] == 2831
    assert recon["expected_participants"] == 2400
    assert recon["gap_vs_expected"] == 431
    # the two injected duplicates resolved to the documented canonicals
    for dup, canon in (("P_DUP01", "P0021"), ("P_DUP02", "P0119")):
        dup_row = db.query(Participant).filter(Participant.raw_id == dup).one()
        assert dup_row.status == "duplicate"
        assert db.get(Participant, dup_row.merged_into).raw_id == canon
    eng.dispose()

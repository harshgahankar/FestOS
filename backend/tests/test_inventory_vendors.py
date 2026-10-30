"""Inventory + vendor engine tests (Phase 4)."""
from engines.inventory import (can_issue_participant, merch_shortfall, stock_levels)
from engines.vendors import (compliance, coverage_matrix, normalize_tag,
                             reroute_on_interruption, settlement)

FEST_START, FEST_END = "2026-10-30", "2026-11-02"


# ------------------------------------------------------------------ inventory --
def test_stock_derived_from_ledger_only():
    items = [{"id": 1}, {"id": 2}]
    movs = [{"item_id": 1, "qty": 10, "at": "2026-10-01", "id": 1},
            {"item_id": 1, "qty": -3, "at": "2026-10-02", "id": 2},
            {"item_id": 2, "qty": 5, "at": "2026-10-01", "id": 3}]
    assert stock_levels(items, movs) == {1: 7, 2: 5}


def test_damaged_repair_entry_never_adds_stock():
    items = [{"id": 1}]
    movs = [{"item_id": 1, "qty": 4, "status": "damaged", "id": 1},
            {"item_id": 1, "qty": 10, "status": "available", "id": 2}]
    assert stock_levels(items, movs) == {1: 10}


def test_merch_shortfall_flags_missing_sizes():
    items = [{"id": 1, "kind": "merch", "size": "M"}]
    participants = [{"id": 1, "tshirt_size": "M", "status": "active"},
                    {"id": 2, "tshirt_size": "M", "status": "active"},
                    {"id": 3, "tshirt_size": "L", "status": "active"}]
    out = merch_shortfall(items, [], participants)
    assert out["stock"] == {"M": 1}
    assert out["shortfall"]["M"] == {"needed": 2, "stock": 1, "missing": 1}
    assert out["shortfall"]["L"]["stock"] == 0


def test_merch_demand_collapses_duplicates():
    participants = [{"id": 1, "tshirt_size": "M", "status": "active"},
                    {"id": 2, "tshirt_size": "M", "status": "duplicate",
                     "merged_into": 1}]
    out = merch_shortfall([{"id": 1, "kind": "merch", "size": "M"}], [], participants)
    assert out["demand"] == {"M": 1}      # duplicates are not demand


def test_issue_once_guard():
    ok, msg = can_issue_participant({"T-shirt|M"}, "T-shirt|M")
    assert not ok and "already issued" in msg
    ok, _ = can_issue_participant(set(), "T-shirt|M")
    assert ok


# --------------------------------------------------------------------- vendors --
def test_compliance_expired_vs_mid_fest():
    vendors = [{"id": 1, "raw_id": "VND01", "name": "Old", "hygiene_cert_expiry": "2026-09-29"},
               {"id": 2, "raw_id": "VND02", "name": "Edge", "hygiene_cert_expiry": "2026-11-01"},
               {"id": 3, "raw_id": "VND03", "name": "Good", "hygiene_cert_expiry": "2027-01-01"}]
    out = compliance(vendors, FEST_START, FEST_END)
    codes = {e["raw_id"]: e["status_code"] for e in out["vendors"]}
    assert codes["VND01"] == "EXPIRED"
    assert codes["VND02"] == "EXPIRING_MID_FEST"
    assert codes["VND03"] == "OK"
    assert out["expired"] == ["VND01"] and out["expiring"] == ["VND02"]


def test_compliance_missing_date_is_a_finding():
    out = compliance([{"id": 1, "raw_id": "VND01", "name": "No cert",
                       "hygiene_cert_expiry": None}], FEST_START, FEST_END)
    assert out["vendors"][0]["status_code"] == "MISSING_CERT_DATE"
    assert out["vendors"][0]["action_required"]


def test_normalize_tag_both_directions():
    assert normalize_tag("Vegetarian") == "vegetarian"
    assert normalize_tag("Nut allergy") == "nut allergy"
    assert normalize_tag("weird stuff") is None


def test_coverage_matrix_flags_uncovered_tags():
    vendors = [{"id": 1, "dietary_coverage": ["vegetarian"]},
               {"id": 2, "dietary_coverage": ["Non-vegetarian", "halal"]}]
    participants = [{"dietary_tags": ["vegetarian"]},
                    {"dietary_tags": ["Jain"]},
                    {"dietary_tags": ["halal"]}]
    out = coverage_matrix(vendors, participants, ["2026-10-30"])
    assert out["matrix"]["vegetarian"]["vendors"] == [1]
    assert out["matrix"]["jain"]["vendors"] == []
    assert "jain" in out["uncovered_tags"]


def test_reroute_respects_diet_coverage():
    vendors = [{"id": 1, "dietary_coverage": ["vegetarian"], "status": "active",
                "capacity_per_day": 100, "rate": None},
               {"id": 2, "dietary_coverage": ["vegetarian", "halal"], "status": "active",
                "capacity_per_day": 100, "rate": None}]
    orders = [{"id": 1, "vendor_id": 1, "dietary_tag": "halal", "meal": "lunch"},
              {"id": 2, "vendor_id": 1, "dietary_tag": "jain", "meal": "dinner"}]
    plan = reroute_on_interruption(1, vendors, orders, [])
    dests = {m["dietary_tag"]: m["to_vendor"] for m in plan["moves"]}
    assert dests["halal"] == 2
    assert any(u["reason"].startswith("no active vendor") for u in plan["unmet"])


def test_settlement_needs_entry_when_no_rate():
    vendors = [{"id": 1, "raw_id": "VND01", "name": "A", "rate": None},
               {"id": 2, "raw_id": "VND02", "name": "B", "rate": 50}]
    orders = [{"id": 1, "vendor_id": 1, "qty": 10, "paid": False},
              {"id": 2, "vendor_id": 2, "qty": 4, "paid": False}]
    out = settlement(vendors, orders)
    rows = {r["raw_id"]: r for r in out["rows"]}
    assert rows["VND01"]["amount"] is None
    assert rows["VND01"]["needs_manual_entry"] is True
    assert rows["VND02"]["amount"] == 200
    assert "VND01" in out["pending_entries"]

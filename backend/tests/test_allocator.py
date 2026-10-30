"""Allocator hard-constraint tests + engine behaviour (Phase 4)."""
from engines.allocator import allocate, _nights


def room(rid, gender="boys", floor=1, beds=4, accessible=False, readiness="ready",
         cleaning=None, status="open"):
    return {"id": rid, "raw_id": f"R{rid}", "hostel": "B1", "floor": floor,
            "beds": beds, "accessible": accessible, "gender_block": gender,
            "readiness": readiness, "cleaning_until": cleaning, "status": status}


def person(pid, gender="male", acc="no", details="", requested="yes", cont=None,
           arrival="2026-10-31 09:00", departure="2026-11-02 18:00"):
    return {"id": pid, "raw_id": f"P{pid:04}", "name": f"N{pid}", "gender": gender,
            "contingent": cont, "arrival": arrival, "departure": departure,
            "accommodation_requested": requested, "accessibility_status": acc,
            "accessibility_details": details}


def ext(eid, beds=5, cost=800, transport="yes"):
    return {"id": eid, "property": f"Stay{eid}", "beds": beds,
            "cost_per_bed_night": cost, "transport_available": transport}


# ------------------------------------------------------------- ACCESSIBILITY --
def test_accessibility_gets_accessible_room_only():
    rooms = [room(1, floor=2, accessible=False), room(2, floor=0, accessible=True)]
    plan = allocate([person(1, gender="male", acc="yes",
                            details="Wheelchair access")], rooms, [ext(100)])
    dest = [a for a in plan["assignments"] if a["participant_id"] == 1][0]
    assert dest["room_id"] == 2            # the ONLY acceptable room


def test_accessibility_never_spills_to_external():
    rooms = [room(1, floor=2, accessible=False), room(2, accessible=False)]
    plan = allocate([person(1, acc="yes")], rooms, [ext(100)])
    assert plan["unplaced"][0]["reason_code"] == "ACCESSIBILITY_NO_SUITABLE_BED"
    assert not any(a["external_stay_id"] for a in plan["assignments"])


def test_ground_floor_detail_requires_floor0():
    rooms = [room(1, floor=0), room(2, floor=1)]
    plan = allocate([person(1, details="Ground floor / no stairs")], rooms, [])
    assert [a for a in plan["assignments"]][0]["room_id"] == 1


def test_unknown_accessibility_treated_conservatively():
    rooms = [room(1, accessible=False)]
    plan = allocate([person(1, acc="unknown")], rooms, [ext(100)])
    assert plan["unplaced"][0]["reason_code"] == "ACCESSIBILITY_NO_SUITABLE_BED"


def test_unknown_accessibility_ok_when_details_say_none():
    rooms = [room(1)]
    plan = allocate([person(1, acc="unknown", details="no accessibility needs")],
                    rooms, [])
    assert plan["assignments"]


# ------------------------------------------------------- GENDER_SEGREGATION --
def test_male_never_in_girls_room_and_vice_versa():
    rooms = [room(1, gender="girls"), room(2, gender="boys")]
    plan = allocate([person(1, gender="male")], rooms, [ext(70, transport="yes")])
    dest = plan["assignments"][0]
    assert dest["room_id"] == 2
    plan2 = allocate([person(2, gender="female")], rooms, [ext(70)])
    assert plan2["assignments"][0]["room_id"] == 1


def test_unclear_gender_goes_to_review_never_forced():
    rooms = [room(1), room(2)]
    plan = allocate([person(1, gender="non_binary"), person(2, gender=None)],
                    rooms, [ext(100)])
    codes = {r["reason_code"] for r in plan["review_queue"]}
    assert codes == {"UNCLEAR_GENDER"}
    assert len(plan["review_queue"]) == 2
    assert not plan["assignments"]


def test_unknown_consent_goes_to_review():
    plan = allocate([person(1, requested="unknown")], [room(1)], [])
    assert plan["review_queue"][0]["reason_code"] == "UNCLEAR_ACCOMMODATION"
    assert not plan["assignments"]


def test_explicit_no_gets_no_bed_and_no_review():
    plan = allocate([person(1, requested="no")], [room(1)], [])
    assert not plan["assignments"] and not plan["review_queue"]


# -------------------------------------------------------------------- PRIVACY --
def test_external_stays_never_mix_gender_cohorts():
    rooms = [room(1, beds=0), room(2, gender="girls", beds=0)]   # no hostel space
    plan = allocate([person(1), person(2, gender="female")], rooms, [ext(100)])
    exts = [a["external_stay_id"] for a in plan["assignments"] if a["external_stay_id"]]
    assert len(exts) == 1               # ext either hosts boys or girls, never both
    assert plan["unplaced"][0]["reason_code"] == "NO_BED_AVAILABLE"  # 2nd cohort blocked


# ------------------------------------------------------------------ CAPACITY --
def test_capacity_never_exceeded_overflow_counts():
    rooms = [room(1, beds=1), room(2, gender="girls", beds=1)]
    people = [person(1), person(2), person(3)]
    plan = allocate(people, rooms, [ext(100, beds=2)])
    assert plan["shortage"]["hostel_beds_used"] == 1
    assert plan["shortage"]["external_beds_used"] == 2


def test_capacity_exhausted_everywhere_means_unmet():
    plan = allocate([person(1)], [room(1, beds=0)], [])
    assert plan["shortage"]["unmet_count"] == 1
    assert plan["unplaced"][0]["reason_code"] == "NO_BED_AVAILABLE"


# ----------------------------------------------------------------- READINESS --
def test_room_not_ready_blocks_bed():
    rooms = [room(1, beds=2, readiness="unavailable")]
    plan = allocate([person(1)], rooms, [])
    assert plan["shortage"]["unmet_count"] == 1


def test_cleaning_until_before_arrival_is_usable():
    rooms = [room(1, beds=2, readiness="cleaning", cleaning="2026-10-31 08:00")]
    plan = allocate([person(1, arrival="2026-10-31 09:00")], rooms, [])
    assert plan["shortage"]["hostel_beds_used"] == 1


def test_cleaning_until_after_arrival_blocks_then_overflow():
    rooms = [room(1, beds=2, readiness="cleaning", cleaning="2026-10-31 12:00")]
    plan = allocate([person(1, arrival="2026-10-31 09:00")], rooms, [ext(9)])
    assert plan["assignments"][0]["external_stay_id"] == 9


# ------------------------------------------------------------------ WINDOWS --
def test_windows_constraint_shows_in_explanation_when_stay_used():
    plan = allocate([person(1)], [room(1, beds=0)], [ext(1, transport="limited")])
    dest = plan["assignments"][0]
    assert dest["external_stay_id"] == 1
    assert "limited" in dest["reason"]


# ------------------------------------------------------------- COHESION/COST --
def test_contingent_members_house_together_when_space_allows():
    rooms = [room(1), room(2)]
    people = [person(1, cont="C1"), person(2, cont="C1"), person(3, cont="C2"),
              person(4, cont="C2")]
    plan = allocate(people, rooms, [])
    rooms_used = {a["participant_id"]: a["room_id"] for a in plan["assignments"]}
    assert rooms_used[1] == rooms_used[2]
    assert rooms_used[3] == rooms_used[4]


def test_unknown_travel_transport_is_flagged_not_guessed():
    plan = allocate([person(1)], [room(1, beds=0)],
                    [ext(5, transport="unknown")])
    assert plan["explanations"]


def test_nights_calculation():
    assert _nights("2026-10-31 09:00", "2026-11-02 18:00") == 2
    assert _nights(None, None) == 1


def test_locked_pin_violation_reported_not_accepted():
    rooms = [room(1, accessible=False), room(2, floor=0, accessible=True)]
    plan = allocate([person(1, acc="yes")], rooms, [],
                    locked=[{"participant_id": 1, "room_id": 1}])
    assert plan["violations"][0]["type"] == "ACCESSIBILITY"
    # the bad pin is declined, the person then lands on the good accessible room
    assert not any(a["room_id"] == 1 for a in plan["assignments"])
    assert any(a["room_id"] == 2 for a in plan["assignments"])


def test_locked_external_pin_violates_privacy():
    rooms = [room(1)]
    plan = allocate([person(1), person(2, gender="female")], rooms, [ext(3)],
                    locked=[{"participant_id": 1, "external_stay_id": 3},
                            {"participant_id": 2, "external_stay_id": 3}])
    assert any(v["type"] == "PRIVACY" for v in plan["violations"])


def test_relaxations_always_empty():
    rooms = [room(1, beds=0)]
    plan = allocate([person(1, acc="yes")], rooms, [])
    assert plan["relaxations"] == []

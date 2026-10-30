"""Scheduler conflict type tests (Phase 4)."""
from engines.scheduler import find_conflicts

DAY = "2026-11-01"


def ev(eid, start="09:00", end=None, duration=60, venue="V1", name=None,
       setup_min=None, teardown_min=None, needs=None, vol=0):
    return {"id": int(eid[1:]), "raw_id": eid, "name": name or eid,
            "duration_minutes": duration,
            "venue_id": 1 if venue == "V1" else 2,
            "start": f"{DAY} {start}", "end": end,
            "setup_min": setup_min, "teardown_min": teardown_min,
            "equipment_needs": needs or [], "volunteers_needed": vol}


def venue():
    return [{"id": 1, "raw_id": "V1", "name": "Main Stage",
             "capacity": 300,
             "availability_windows": [{"day": DAY, "start": "08:00", "end": "22:00"}]},
            {"id": 2, "raw_id": "V2", "name": "Auditorium",
             "capacity": 100,
             "availability_windows": [{"day": DAY, "start": "10:00", "end": "18:00"}]}]


def run(events, regs=None, staff=None, team=None, stock=None, venues=None):
    return find_conflicts(events, venues or venue(),
                          regs or [], staff or [], team or [], stock or [])


def test_participant_clash_two_overlapping_events():
    check = run([ev("E1", "09:00", duration=60), ev("E2", "09:30", duration=60)],
                regs=[{"participant": "P001", "event_raw_id": "E1"},
                      {"participant": "P001", "event_raw_id": "E2"}])
    assert any(c["type"] == "PARTICIPANT_CLASH" for c in check["conflicts"])


def test_no_participant_clash_when_not_overlapping():
    check = run([ev("E1", "09:00"), ev("E2", "10:30")],
                regs=[{"participant": "P001", "event_raw_id": "E1"},
                      {"participant": "P001", "event_raw_id": "E2"}])
    assert not any(c["type"] == "PARTICIPANT_CLASH" for c in check["conflicts"])


def test_venue_double_book():
    check = run([ev("E1", "09:00"), ev("E2", "09:30")])
    assert any(c["type"] == "VENUE_DOUBLE_BOOK" for c in check["conflicts"])


def test_setup_teardown_overlap_only():
    check = run([ev("E1", "09:00", duration=60), ev("E2", "10:20", duration=30)])
    kinds = {c["type"] for c in check["conflicts"]}
    assert kinds == {"SETUP_TEARDOWN_OVERLAP"}   # events themselves don't collide


def test_no_setup_teardown_overlap_with_gap():
    check = run([ev("E1", "09:00", duration=60), ev("E2", "10:35", duration=30)])
    assert check["conflicts"] == []


def test_venue_out_of_hours():
    check = run([ev("E1", "07:00")])
    assert any(c["type"] == "VENUE_OUT_OF_HOURS" for c in check["conflicts"])


def test_travel_buffer_warning_across_venues():
    check = run([ev("E1", "09:00", duration=60), ev("E2", "10:05", venue="V2")])
    kinds = {c["type"] for c in check["conflicts"]}
    assert "TRAVEL_BUFFER" in kinds
    assert not any(c["type"] == "VENUE_DOUBLE_BOOK" for c in check["conflicts"])


def test_no_travel_buffer_with_sufficient_gap():
    check = run([ev("E1", "09:00", duration=60), ev("E2", "10:30", venue="V2")])
    assert not any(c["type"] == "TRAVEL_BUFFER" for c in check["conflicts"])


def test_judge_clash():
    team = [{"id": 7, "raw_id": "ST07", "name": "Judge One",
             "shift_start": "08:00", "shift_end": "20:00",
             "shift_crosses_midnight": False}]
    staff = [{"event_id": 1, "core_team_id": 7, "role": "judge"},
             {"event_id": 2, "core_team_id": 7, "role": "judge"}]
    check = run([ev("E1", "09:00"), ev("E2", "09:30")], staff=staff, team=team)
    kinds = {c["type"] for c in check["conflicts"]}
    assert "JUDGE_CLASH" in kinds


def test_volunteer_clash_and_shift_mismatch():
    team = [{"id": 7, "raw_id": "ST07", "name": "Vol One",
             "shift_start": "12:00", "shift_end": "20:00",
             "shift_crosses_midnight": False}]
    staff = [{"event_id": 1, "core_team_id": 7, "role": "volunteer"},
             {"event_id": 2, "core_team_id": 7, "role": "volunteer"}]
    check = run([ev("E1", "09:00"), ev("E2", "09:30")], staff=staff, team=team)
    kinds = {c["type"] for c in check["conflicts"]}
    assert "VOLUNTEER_CLASH" in kinds
    assert "SHIFT_MISMATCH" in kinds


def test_volunteer_overload_per_day_cap():
    team = [{"id": 7, "raw_id": "ST07", "name": "Vol One",
             "shift_start": "08:00", "shift_end": "20:00",
             "shift_crosses_midnight": False}]
    events = [ev("E1", "09:00"), ev("E2", "11:00"), ev("E3", "13:00"), ev("E4", "15:00")]
    staff = [{"event_id": i, "core_team_id": 7, "role": "volunteer"}
             for i in range(1, 5)]
    check = run(events, staff=staff, team=team)
    assert any(c["type"] == "STAFF_OVERLOAD" for c in check["conflicts"])


def test_midnight_shift_covers_event():
    team = [{"id": 7, "raw_id": "ST07", "name": "Night Ops",
             "shift_start": "22:00", "shift_end": "06:00",
             "shift_crosses_midnight": True}]
    staff = [{"event_id": 1, "core_team_id": 7, "role": "volunteer"}]
    check = run([ev("E1", "01:00")], staff=staff, team=team)
    assert not any(c["type"] == "SHIFT_MISMATCH" for c in check["conflicts"])


def test_equipment_shortage():
    check = run([ev("E1", "09:00", needs=[{"sku": "MIC", "qty": 5}])],
                stock=[{"sku": "MIC", "available": 2}])
    assert any(c["type"] == "EQUIPMENT_SHORTAGE" for c in check["conflicts"])


def test_equipment_ok():
    check = run([ev("E1", "09:00", needs=[{"sku": "MIC", "qty": 5}])],
                stock=[{"sku": "MIC", "available": 5}])
    assert check["conflicts"] == []


def test_suggestions_ranked_by_blast_radius():
    check = run([ev("E1", "09:00"), ev("E2", "09:30")])
    assert check["suggestions"]
    options = check["suggestions"][0].get("options") or []
    radius = [o["blast_radius"] for o in options]
    assert radius == sorted(radius)


def test_summary_counts_by_type():
    check = run([ev("E1", "09:00"), ev("E2", "09:30"), ev("E3", "09:30")])
    # every collapsing PAIR counts: (E1,E2) (E1,E3) (E2,E3)
    assert check["summary"]["VENUE_DOUBLE_BOOK"] == 3

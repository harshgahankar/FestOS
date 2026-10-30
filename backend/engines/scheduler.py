"""Schedule conflict engine — pure functions, dicts in / out (no framework imports).

The pack has no venues or times on events (A-11): operators enter venue/time
through the API, then this engine validates the schedule.

Rules and thresholds live in app.config.SCHEDULER.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from app import config as C


def _dt(v) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def contains_time(window: dict, moment: datetime) -> bool:
    """window = {'day': '2026-11-01', 'start': 'HH:MM', 'end': 'HH:MM'} (multi-day ok)."""
    day = window.get("day")
    start, end = _parse_hm(window.get("start")), _parse_hm(window.get("end"))
    if day and moment.date().isoformat() != day:
        return False
    if start is None or end is None:
        return True  # unparseable/absent window is treated as open, not closed
    t = moment.time()
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end   # crossing midnight


def _parse_hm(v):
    try:
        h, m = str(v).split(":")[:2]
        return time(int(h), int(m))
    except (ValueError, AttributeError, TypeError):
        return None


def _overlap(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> bool:
    return a0 <= b1 and b0 <= a1


def event_window(ev: dict) -> tuple[datetime | None, datetime | None, datetime | None,
                                    datetime | None]:
    """start, end, setup_from, teardown_to for an event dict."""
    start = _dt(ev.get("start"))
    duration = int(ev.get("duration_minutes") or 0)
    end = _dt(ev.get("end")) or (start + timedelta(minutes=duration) if start else None)
    setup_min = int(ev.get("setup_min") if ev.get("setup_min") is not None
                    else C.SCHEDULER["SETUP_MIN_DEFAULT"])
    teardown_min = int(ev.get("teardown_min") if ev.get("teardown_min") is not None
                       else C.SCHEDULER["TEARDOWN_MIN_DEFAULT"])
    setup_from = start - timedelta(minutes=setup_min) if start else None
    teardown_to = end + timedelta(minutes=teardown_min) if end else None
    return start, end, setup_from, teardown_to


def _event_sorted(events: list[dict]) -> list[tuple[datetime, datetime, datetime,
                                                    datetime, dict]]:
    with_times = []
    for ev in events:
        start, end, sfrom, tto = event_window(ev)
        if start and end:
            with_times.append((start, end, sfrom, tto, ev))
    with_times.sort(key=lambda t: t[0])
    return with_times


# ------------------------------------------------------------------ engine --
def find_conflicts(events: list[dict], venues: list[dict],
                   registrations: list[dict], staff_assignments: list[dict],
                   core_team: list[dict], equipment_stock: list[dict] | None = None
                   ) -> dict:
    """Check every scheduler conflict type. Returns {'conflicts': [...], 'suggestions': [...]}.

    registrations: [{event_raw_id, raw_id (participant), event_id, participant}]
    staff_assignments: [{event_id, core_team_id, role}]
    core_team: [{id, raw_id, name, shift_start, shift_end, shift_crosses_midnight}]
    equipment_stock: [{sku, available}]
    """
    venue_by_id = {v["id"]: v for v in venues}
    conflicts: list[dict] = []
    times = _event_sorted(events)

    # --- registered-person clashes (same participant in overlapping events) ------
    by_person: dict[str, list[dict]] = {}
    for r in registrations:
        key = r.get("participant") or r.get("raw_id")
        if key:
            by_person.setdefault(key, []).append(r)
    for person, regs in sorted(by_person.items()):
        evs = [ev for ev in times
               if ev[4].get("raw_id") in {r.get("event_raw_id") for r in regs}]
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                e1, e2 = evs[i], evs[j]
                if _overlap(e1[0], e1[1], e2[0], e2[1]):
                    conflicts.append({
                        "type": "PARTICIPANT_CLASH", "severity": "error",
                        "actor": person,
                        "event_1": e1[4].get("raw_id"), "event_2": e2[4].get("raw_id"),
                        "message": f"{person} is registered in both events which overlap"})

    # --- venue double-booking + setup/teardown overlap -----------------------------
    by_venue: dict[str, list] = {}
    for ev in times:
        vid = ev[4].get("venue_id")
        if vid is not None:
            by_venue.setdefault(vid, []).append(ev)
    for vid, evs in sorted(by_venue.items()):
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                e1, e2 = evs[i], evs[j]
                kind = None
                if _overlap(e1[2], e1[1], e2[2], e2[1]) or \
                        _overlap(e2[2], e2[1], e1[2], e1[1]):
                    kind = ("SETUP_TEARDOWN_OVERLAP"
                            if not _overlap(e1[0], e1[1], e2[0], e2[1])
                            else "VENUE_DOUBLE_BOOK")
                if kind:
                    conflicts.append({
                        "type": kind, "severity": "error", "venue": vid,
                        "event_1": e1[4].get("raw_id"), "event_2": e2[4].get("raw_id"),
                        "message": f"{vid} has overlapping occupancy: "
                                   f"{e1[4].get('raw_id')} vs {e2[4].get('raw_id')} "
                                   f"({kind.replace('_', ' ').lower()})"})
        # venue hours
        for ev in evs:
            v = venue_by_id.get(vid) or {}
            v_hours = (v.get("availability_windows") or [])
            if v_hours and ev[0]:
                ok = any(contains_time(w, ev[0]) and (ev[1] is None or
                                                      _in_window_end(w, ev[1]))
                         for w in v_hours)
            else:
                ok = True   # venue with no hours data cannot be out of hours
            if v_hours and not ok:
                conflicts.append({
                    "type": "VENUE_OUT_OF_HOURS", "severity": "error", "venue": vid,
                    "event": ev[4].get("raw_id"),
                    "message": f"{ev[4].get('raw_id')} runs outside venue {vid} hours"})

    # --- travel buffer between consecutive venue changes --------------------------
    for i in range(len(times)):
        for j in range(i + 1, len(times)):
            e1, e2 = times[i], times[j]
            if e1[4].get("venue_id") and e2[4].get("venue_id") and \
                    e1[4].get("venue_id") != e2[4].get("venue_id"):
                gap = (e2[0] - e1[1]).total_seconds() / 60.0
                if 0 <= gap < C.SCHEDULER["TRAVEL_BUFFER_MIN"]:
                    conflicts.append({
                        "type": "TRAVEL_BUFFER", "severity": "warning",
                        "event_1": e1[4].get("raw_id"), "event_2": e2[4].get("raw_id"),
                        "message": f"only {gap:.0f} min between {e1[4].get('raw_id')} and "
                                   f"{e2[4].get('raw_id')} across venues "
                                   f"(<{C.SCHEDULER['TRAVEL_BUFFER_MIN']} min)"})

    # --- judge / volunteer clashes and shift fit ----------------------------------
    team_by_id = {t["id"]: t for t in core_team}
    by_team: dict[int, list] = {}
    for a in staff_assignments:
        by_team.setdefault(a["core_team_id"], []).append(a)
    for team_id, assigns in sorted(by_team.items()):
        evs = [ev for ev in times
               if ev[4].get("id") in {a.get("event_id") for a in assigns}]
        evs.sort(key=lambda e: e[0])
        roles = {a.get("role") for a in assigns}
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                if _overlap(evs[i][2], evs[i][3], evs[j][2], evs[j][3]):
                    conflict_type = "JUDGE_CLASH" if "judge" in roles \
                        else ("VOLUNTEER_CLASH" if "volunteer" in roles
                              else "STAFF_CLASH")
                    conflicts.append({
                        "type": conflict_type, "severity": "error",
                        "core_team_id": team_id,
                        "event_1": evs[i][4].get("raw_id"),
                        "event_2": evs[j][4].get("raw_id"),
                        "message": f"{team_by_id.get(team_id, {}).get('name', team_id)} "
                                   f"is double-booked ({', '.join(str(r) for r in roles)})"})
        # shift fit (one person, unordered events relative to shift)
        shift = team_by_id.get(team_id) or {}
        if (shift.get("shift_start") is not None and times):
            crosses = bool(shift.get("shift_crosses_midnight"))
            for ev in evs:
                covered = _within_shift(shift.get("shift_start"), shift.get("shift_end"),
                                        crosses, ev[0], ev[1])
                if not covered:
                    conflicts.append({
                        "type": "SHIFT_MISMATCH", "severity": "warning",
                        "core_team_id": team_id, "event": ev[4].get("raw_id"),
                        "message": f"{shift.get('name', team_id)} shift "
                                   f"({shift.get('shift_raw') or ''}) does not cover "
                                   f"{ev[4].get('raw_id')}"})
        cap = (C.SCHEDULER["JUDGE_MAX_EVENTS_PER_DAY"] if "judge" in roles
               else C.SCHEDULER["VOLUNTEER_MAX_EVENTS_PER_DAY"])
        per_day: dict[datetime, int] = {}
        for ev in evs:
            per_day[ev[0].date()] = per_day.get(ev[0].date(), 0) + 1
        for day, count in sorted(per_day.items()):
            if count > cap:
                conflicts.append({
                    "type": "STAFF_OVERLOAD", "severity": "warning",
                    "core_team_id": team_id, "day": day.isoformat(),
                    "message": f"{shift.get('name', team_id)} has {count} events on "
                               f"{day:%Y-%m-%d} (max {cap})"})

    # --- equipment demand vs stock --------------------------------------------------
    demand: dict[str, int] = {}
    for ev in times:
        for need in (ev[4].get("equipment_needs") or []):
            sku = (need.get("sku") if isinstance(need, dict) else need) or ""
            qty = need.get("qty", 1) if isinstance(need, dict) else 1
            demand[sku] = demand.get(sku, 0) + int(qty)
    stock_by_sku = {s["sku"]: int(s.get("available") or 0) for s in (equipment_stock or [])}
    for sku, need in sorted(demand.items()):
        if sku in stock_by_sku:
            avail = stock_by_sku[sku]
            if need > avail:
                conflicts.append({
                    "type": "EQUIPMENT_SHORTAGE", "severity": "error", "sku": sku,
                    "message": f"{sku}: {need} needed vs {avail} available"})
        else:
            # need named but there is NO tracked inventory row at all: flag as
            # untraced so the demand never silently disappears from the report.
            conflicts.append({
                "type": "EQUIPMENT_UNTRACED", "severity": "info", "sku": sku,
                "message": f"{sku}: {need} needed but not tracked in inventory "
                           f"(no matching stock row)"})

    suggestions = _suggest_fixes(conflicts, times, venues, staff_assignments)
    return {"conflicts": conflicts, "suggestions": suggestions,
            "checked_events": len(times),
            "summary": _by_type(conflicts)}


def _within_shift(shift_start, shift_end, crosses_midnight, start, end) -> bool:
    """Shift coverage on the event's own day; midnight-crossing shifts wrap.

    A shift 22:00-06:00 (+1 day) covers any time from 22:00 (included) through
    06:00 next morning, i.e. on the event's date: >= 22:00 OR <= 06:00.
    """
    ss, se = _parse_hm(shift_start), _parse_hm(shift_end)
    if ss is None or se is None:
        return True   # unparsed shift data cannot be judged as violating
    st = start.time() if start else ss
    et = end.time() if end else se
    if crosses_midnight:
        def inside(t):
            return t >= ss or t <= se
        return inside(st) and inside(et)
    return ss <= st and et <= se


def _in_window_end(window: dict, end: datetime) -> bool:
    start, endw = _parse_hm(window.get("start")), _parse_hm(window.get("end"))
    if start is None or endw is None:
        return True
    t = end.time()
    return t <= endw or start > endw   # allow overnight windows


def _by_type(conflicts: list[dict]) -> dict:
    out: dict[str, int] = {}
    for c in conflicts:
        out[c["type"]] = out.get(c["type"], 0) + 1
    return out


# ------------------------------------------------------------ suggestions --
def _blast_radius(shifted: tuple, others: list[tuple]) -> int:
    """How many other events the shift collides with (move-to-candidate scoring)."""
    start, end, sfrom, tto, _ev = shifted
    return sum(1 for o in others
               if o is not shifted and _overlap(sfrom, tto, o[2], o[3]))


def _suggest_fixes(conflicts: list[dict], times, venues, staff_assignments) -> list[dict]:
    """Greedy suggestions ranked by blast radius (fewest events disrupted)."""
    venue_ids = [v["id"] for v in venues]
    suggestions: list[dict] = []
    seen = set()
    for c in conflicts:
        if c["type"] in ("VENUE_DOUBLE_BOOK", "SETUP_TEARDOWN_OVERLAP",
                         "TRAVEL_BUFFER", "VENUE_OUT_OF_HOURS"):
            key = ("move", c.get("event_2"), c.get("event_1"))
            if key in seen:
                continue
            seen.add(key)
            target_ev = next((ev for ev in times
                              if ev[4].get("raw_id") == c.get("event_2")), None)
            if target_ev is None:
                continue
            cand = []
            for vid in venue_ids:
                if vid == c.get("venue"):
                    continue
                radius = _blast_radius((target_ev[0], target_ev[1], target_ev[2],
                                        target_ev[3], target_ev[4]), times)
                cand.append({"venue_id": vid, "blast_radius": radius})
            cand.sort(key=lambda x: x["blast_radius"])
            if cand:
                suggestions.append({
                    "conflict": c["type"], "action": "move",
                    "event": c.get("event_2"), "options": cand[:3]})
        elif c["type"] in ("JUDGE_CLASH", "VOLUNTEER_CLASH", "STAFF_CLASH"):
            suggestions.append({
                "conflict": c["type"], "action": "reassign_staff",
                "core_team_id": c.get("core_team_id"),
                "message": "move the second assignment to an idle core-team member "
                           "or shift the event start"})
        elif c["type"] == "STAFF_OVERLOAD":
            suggestions.append({
                "conflict": c["type"], "action": "rebalance",
                "core_team_id": c.get("core_team_id"),
                "message": "reduce to <= the per-day cap or recruit from other shifts"})
        elif c["type"] in ("EQUIPMENT_SHORTAGE", "EQUIPMENT_UNTRACED"):
            suggestions.append({
                "conflict": c["type"], "action": "source_equipment",
                "sku": c.get("sku"),
                "message": "log inventory movements or order/borrow "
                           + str(c.get('sku'))})
        elif c["type"] == "PARTICIPANT_CLASH":
            suggestions.append({
                "conflict": c["type"], "action": "reschedule",
                "event": c.get("event_1") if c.get("event_1") else c.get("event_2"),
                "message": "decouple the overlapping events for this participant "
                           "(rounds or parallel streams)"})
    sorted_by_impact = []
    # blast radius: suggestions that touch fewer events come first
    for s in suggestions:
        opts = s.get("options") or []
        s["impact"] = min((o["blast_radius"] for o in opts), default=999)
        sorted_by_impact.append(s)
    sorted_by_impact.sort(key=lambda s: s["impact"])
    return sorted_by_impact

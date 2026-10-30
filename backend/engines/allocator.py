"""Accommodation allocator — pure engine (no framework imports).

Greedy, accessibility-first. Hard constraints are never traded:
  ACCESSIBILITY, PRIVACY, GENDER_SEGREGATION, CAPACITY, READINESS, WINDOWS.
Blank/unknown fields stay unknown: unknown consent or unclear gender routes to a
manual review queue, never a forced binary.

All dicts in, plan dict out (spec section 7). Rules live in app.config.
"""
from __future__ import annotations

from datetime import datetime, date, time

from app import config as C


# ------------------------------------------------------------------ helpers --
def _dt(v) -> datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime.combine(v, time(12, 0))
    s = str(v).replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _nights(arrival, departure) -> int:
    a, d = _dt(arrival), _dt(departure)
    if a is None or d is None:
        return C.ALLOC_MIN_NIGHTS
    return max(C.ALLOC_MIN_NIGHTS, (d.date() - a.date()).days)


def _gender_class(p: dict) -> str:
    g = (p.get("gender") or "unknown").strip().lower()
    if g == "male":
        return "boys"
    if g == "female":
        return "girls"
    return "review"          # non_binary / prefer-not-to-say / unknown -> human call


class _State:
    """Placement bookkeeping for one run (pure: created per call)."""

    def __init__(self, rooms: list[dict], externals: list[dict],
                 initial_taken: dict[int, int] | None = None,
                 initial_ext_taken: dict[int, int] | None = None,
                 initial_room_contingent: dict[int, str] | None = None,
                 initial_ext_genders: dict[int, str] | None = None):
        self.rooms = {r["id"]: r for r in rooms}
        self.ext = {e["id"]: e for e in externals}
        self.taken: dict[int, int] = dict(initial_taken or {})
        self.ext_taken: dict[int, int] = dict(initial_ext_taken or {})
        self.ext_genders: dict[int, str] = dict(initial_ext_genders or {})
        self.room_contingent: dict[int, str] = dict(initial_room_contingent or {})
        self.assignments: list[dict] = []
        self.violations: list[dict] = []
        self.unplaced: list[dict] = []
        self.cost = 0

    def free_in_room(self, rid: int) -> int:
        return max(0, int((self.rooms.get(rid) or {}).get("beds") or 0)
                   - self.taken.get(rid, 0))

    def free_in_ext(self, eid: int) -> int:
        return max(0, int((self.ext.get(eid) or {}).get("beds") or 0)
                   - self.ext_taken.get(eid, 0))

    def assign_hostel(self, p: dict, room: dict, arrival, departure, reason: str,
                      source: str, contingent=None) -> None:
        nights = _nights(arrival, departure)
        cost = nights * C.ALLOC_HOSTEL_COST_PER_BED_NIGHT
        self.taken[room["id"]] = self.taken.get(room["id"], 0) + 1
        if contingent and room["id"] not in self.room_contingent:
            self.room_contingent[room["id"]] = str(contingent)
        self._assign(p, room["id"], None, arrival, departure, nights, cost, reason, source)

    def assign_external(self, p: dict, ext: dict, arrival, departure, reason: str,
                        source: str) -> None:
        nights = _nights(arrival, departure)
        cost = nights * int(ext.get("cost_per_bed_night") or 0)
        self.ext_taken[ext["id"]] = self.ext_taken.get(ext["id"], 0) + 1
        self._assign(p, None, ext["id"], arrival, departure, nights, cost, reason, source)

    def _assign(self, p: dict, room_id, ext_id, arrival, departure, nights, cost,
                reason: str, source: str) -> None:
        self.assignments.append({
            "participant_id": p["id"], "raw_id": p.get("raw_id"),
            "room_id": room_id, "external_stay_id": ext_id,
            "check_in": _dt(arrival).isoformat() if _dt(arrival) else None,
            "check_out": _dt(departure).isoformat() if _dt(departure) else None,
            "nights": nights, "cost": cost, "reason": reason, "source": source})
        self.cost += cost


# ----------------------------------------------------------- constraint check --
def room_problems(p: dict, room: dict, gclass: str) -> list[str]:
    """Hard-constraint check of participant vs room; returns violated constraint ids."""
    problems = []
    if _needs_accessible(p):
        if not room.get("accessible"):
            problems.append("ACCESSIBILITY")
        elif room.get("floor") not in (0, None) and _needs_ground_floor(p):
            problems.append("ACCESSIBILITY")
    if (room.get("gender_block") or "").lower() != gclass:
        problems.append("GENDER_SEGREGATION")
    if room.get("status") not in (None, "open"):
        problems.append("READINESS")
    return problems


def _needs_accessible(p: dict) -> bool:
    """Accessibility is hard; unknown is treated conservatively (never assumed fine)."""
    status = (p.get("accessibility_status") or "unknown").strip().lower()
    if status == "yes":
        return True
    if status == "unknown":
        details = (p.get("accessibility_details") or "").lower()
        return not any(tok in details for tok in ("no accessibility needs", "none", "n/a"))
    return False


def _needs_ground_floor(p: dict) -> bool:
    details = (p.get("accessibility_details") or "").lower()
    return any(tok.lower() in details for tok in C.ALLOC_GROUND_FLOOR_TOKENS)


def _room_ready_from(room: dict) -> datetime | None:
    """Cleaning window end, or None when none is recorded (ready for any arrival)."""
    if (room.get("readiness") or "ready") not in ("ready", "cleaning"):
        return None
    return _dt(room.get("cleaning_until"))


def _room_usable(room: dict, arrival, st) -> bool:
    ready = _room_ready_from(room)
    if ready is None and (room.get("readiness") or "ready") not in ("ready", "cleaning"):
        return False           # readiness not in the allowed set at all
    if ready is None:
        return True            # no recorded cleaning window -> ready
    arr = _dt(arrival)
    return arr is None or ready <= arr


def _ext_sort_key(rules: dict):
    if rules.get("external_order") == "capacity_then_cost":
        return lambda e: (-(int(e.get("beds") or 0)), int(e.get("cost_per_bed_night") or 0))
    return lambda e: (int(e.get("cost_per_bed_night") or 0), -(int(e.get("beds") or 0)))


# ------------------------------------------------------------------ engine --
def allocate(participants: list[dict], rooms: list[dict], externals: list[dict],
             locked: list[dict] | None = None, preset: str = "balanced",
             initial_taken: dict[int, int] | None = None,
             initial_ext_taken: dict[int, int] | None = None,
             initial_room_contingent: dict[int, str] | None = None,
             initial_ext_genders: dict[int, str] | None = None) -> dict:
    """Build an accommodation plan (spec section 7 shape).

    The initial_* parameters seed pre-existing occupancy (used by the disruption
    engine to re-house displaced people only, respecting beds already taken and
    the single-cohort rule for external stays that already host someone).
    """
    rules = dict(C.ALLOC_PRESETS.get(preset) or C.ALLOC_PRESETS["balanced"])
    rules["preset_name"] = preset
    st = _State(rooms, externals, initial_taken, initial_ext_taken,
                initial_room_contingent, initial_ext_genders)
    review_queue: list[dict] = []
    explanations: list[str] = []

    # --- review queue: never guess consent or gender ----------------------------
    pending: list[tuple[str, dict]] = []
    for p in participants:
        requested = (p.get("accommodation_requested") or "unknown").strip().lower()
        if requested in ("", "unknown"):
            review_queue.append({
                "participant_id": p["id"], "raw_id": p.get("raw_id"),
                "reason_code": "UNCLEAR_ACCOMMODATION",
                "reason": C.ALLOC_REVIEW_REASONS["UNCLEAR_ACCOMMODATION"]})
            continue
        if requested != "yes":
            continue                       # explicit no: no bed, no review
        gclass = _gender_class(p)
        if gclass == "review":
            review_queue.append({
                "participant_id": p["id"], "raw_id": p.get("raw_id"),
                "reason_code": "UNCLEAR_GENDER",
                "reason": C.ALLOC_REVIEW_REASONS["UNCLEAR_GENDER"]})
            continue
        pending.append((gclass, p))

    # --- pass 1: operator-pinned beds, re-verified against every hard constraint --
    locked_by_pid = {}
    for lock in locked or []:
        if lock.get("room_id") is not None:
            locked_by_pid[lock["participant_id"]] = ("room", lock["room_id"])
        elif lock.get("external_stay_id") is not None:
            locked_by_pid[lock["participant_id"]] = ("external", lock["external_stay_id"])
    unresolved = []
    for gclass, p in pending:
        pin = locked_by_pid.get(p["id"])
        arrival, departure = p.get("arrival"), p.get("departure")
        if pin is None:
            unresolved.append((gclass, p))
            continue
        kind, rid = pin
        if kind == "room":
            room = st.rooms.get(rid)
            if room is None:
                st.violations.append({"type": "LOCKED_ROOM_UNKNOWN",
                                      "participant_id": p["id"],
                                      "message": f"room {rid} does not exist"})
                unresolved.append((gclass, p))
                continue
            probs = room_problems(p, room, gclass)
            if probs or st.free_in_room(rid) <= 0 or not _room_usable(room, arrival, st):
                for prob in probs or (["CAPACITY/READINESS"] if st.free_in_room(rid) <= 0
                                      else []):
                    st.violations.append({
                        "type": prob, "participant_id": p["id"], "room_id": rid,
                        "message": f"pinned bed {p.get('raw_id')} -> room {rid} "
                                   f"violates {prob}"})
                unresolved.append((gclass, p))
                continue
            st.assign_hostel(p, room, arrival, departure,
                             "operator pin, verified against all hard constraints",
                             "locked")
        else:
            ext = st.ext.get(rid)
            if ext is None:
                st.violations.append({"type": "LOCKED_STAY_UNKNOWN",
                                      "participant_id": p["id"],
                                      "message": f"external stay {rid} does not exist"})
                unresolved.append((gclass, p))
                continue
            if st.ext_genders.get(rid) not in (None, gclass):
                st.violations.append({"type": "PRIVACY", "participant_id": p["id"],
                                      "external_stay_id": rid,
                                      "message": f"pinned stay {rid} already hosts "
                                                 f"{st.ext_genders.get(rid)}"})
                unresolved.append((gclass, p))
                continue
            if st.free_in_ext(rid) <= 0:
                st.violations.append({"type": "CAPACITY", "participant_id": p["id"],
                                      "external_stay_id": rid,
                                      "message": f"pinned stay {rid} is full"})
                unresolved.append((gclass, p))
                continue
            if st.ext_genders.get(rid) is None:
                st.ext_genders[rid] = gclass
            st.assign_external(p, ext, arrival, departure,
                               "operator pin", "locked")
    pending = unresolved

    # --- pass 2: greedy placement; contingent clusters stay together -------------
    # accessibility needs claim the scarce accessible beds first.
    pending.sort(key=lambda gp: (0 if _needs_accessible(gp[1]) else 1,
                                 str(gp[1].get("arrival") or ""),
                                 str(gp[1].get("raw_id") or "")))
    for gclass in ("boys", "girls"):
        gender_rooms = [r for r in rooms
                        if (r.get("gender_block") or "").lower() == gclass]
        members = [p for g, p in pending if g == gclass]
        for p in members:
            arrival, departure = p.get("arrival"), p.get("departure")
            need_access = _needs_accessible(p)
            contingent = p.get("contingent")

            candidates = []
            for room in gender_rooms:
                probs = room_problems(p, room, gclass)
                if probs:
                    continue
                if st.free_in_room(room["id"]) <= 0 or \
                        not _room_usable(room, arrival, st):
                    continue
                # contingent together: rooms already housing this contingent win
                contig = 0 if (contingent and
                               st.room_contingent.get(room["id"]) == str(contingent)
                               ) else 1
                # same-floor preference
                floor_pref = 1
                if rules.get("prefer_same_floor") and contingent:
                    floors = {st.rooms.get(a["room_id"], {}).get("floor")
                              for a in st.assignments
                              if a.get("room_id") and
                              st.room_contingent.get(a["room_id"]) == str(contingent)}
                    floor_pref = 0 if room.get("floor") in floors else 1
                candidates.append((contig, 0 if need_access else 1, floor_pref,
                                   st.free_in_room(room["id"]) - int(room.get("beds") or 0),
                                   str(room.get("raw_id") or room["id"]), room))
            if candidates:
                room = min(candidates, key=lambda t: t[:5])[-1]
                st.assign_hostel(p, room, arrival, departure,
                                 "accessible room" if need_access else
                                 ("hostel bed, contingent kept together" if contingent
                                  else "hostel bed"),
                                 preset, contingent=contingent)
                continue
            if need_access:
                # external stays carry no accessibility data in the pack:
                # unknown -> never assume; a human decides (hard constraint).
                st.unplaced.append({
                    "participant_id": p["id"], "raw_id": p.get("raw_id"),
                    "reason_code": "ACCESSIBILITY_NO_SUITABLE_BED",
                    "reason": "no accessible hostel bed matches; external stays carry "
                              "no accessibility data, so a person must decide"})
                continue
            placed = False
            for ext in sorted(st.ext.values(), key=_ext_sort_key(rules)):
                if st.free_in_ext(ext["id"]) <= 0:
                    continue
                if st.ext_genders.get(ext["id"]) not in (None, gclass):
                    continue   # PRIVACY: one gender cohort per external property
                st.ext_genders[ext["id"]] = gclass
                transport = (ext.get("transport_available") or "unknown").lower()
                reason = "hostel full; external stay" + \
                    (f" ({transport} transport)" if transport not in ("yes", "unknown")
                     else "")
                if transport == "unknown":
                    explanations.append(
                        f"{p.get('raw_id')}: external stay {ext.get('property')} has "
                        f"no transport data in the pack (A-14) — shuttle responsibility "
                        f"unassigned")
                st.assign_external(p, ext, arrival, departure, reason,
                                   preset + "_overflow")
                placed = True
                break
            if not placed:
                st.unplaced.append({
                    "participant_id": p["id"], "raw_id": p.get("raw_id"),
                    "reason_code": "NO_BED_AVAILABLE",
                    "reason": "all hostel and external beds for this cohort are exhausted"})

    hostel_beds = sum(int(r.get("beds") or 0) for r in rooms)
    ext_beds = sum(int(e.get("beds") or 0) for e in externals)
    requested_count = sum(
        1 for p in participants
        if (p.get("accommodation_requested") or "").strip().lower() == "yes")
    return {
        "preset": preset,
        "assignments": sorted(st.assignments,
                              key=lambda a: str(a.get("raw_id") or a["participant_id"])),
        "violations": st.violations,
        "relaxations": [],               # hard constraints are never relaxed
        "unplaced": st.unplaced,
        "shortage": {
            "requested_count": requested_count,
            "hostel_beds": hostel_beds, "hostel_beds_used": sum(st.taken.values()),
            "external_beds": ext_beds, "external_beds_used": sum(st.ext_taken.values()),
            "unmet_count": len(st.unplaced),
        },
        "cost": st.cost,
        "review_queue": sorted(review_queue, key=lambda r: str(r.get("raw_id") or "")),
        "explanations": explanations,
    }

"""Disruption engine — pure impact analysis (dicts in / out).

Seven disruption types (spec: preview / apply / revert). Every report follows one
schema: state_changes, affected {count, names}, new_violations, suggested_actions,
cost_delta. Functions are pure; routers persist proposals and snapshots.

Re-housing reuses engines.allocator (initial occupancy): displaced people only, with
locked allocations respected (reported, never moved) and a minimise-moves bias via
contingent/floor hints preserved from before.
"""
from __future__ import annotations

from datetime import datetime

from app import config as C
from engines import allocator as alloc_eng
from engines import vendors as vend_eng


def report(state_changes: list[dict], affected_names: list[str],
           new_violations: list[dict], suggested_actions: list[str],
           cost_delta: int) -> dict:
    """The uniform impact-report schema (spec)."""
    return {
        "state_changes": state_changes,
        "affected": {"count": len(affected_names), "names": affected_names},
        "new_violations": new_violations,
        "suggested_actions": suggested_actions,
        "cost_delta": cost_delta,
    }


def _dt(v) -> datetime | None:
    if v in (None, ""):
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


def _room_block(rooms: list[dict], room_id) -> str | None:
    for r in rooms:
        if r["id"] == room_id:
            return r.get("hostel")
    return None


# ------------------------------------------------------------ late contingent
def late_contingent_preview(members: list[dict], registrations: list[dict],
                            events: list[dict], new_arrival: str) -> dict:
    """members: participant dicts of one contingent; registrations carry event_raw_id."""
    names = [m.get("name") or m.get("raw_id") for m in members]
    arrivals = [_dt(m.get("arrival")) for m in members]
    arrivals = [a for a in arrivals if a is not None]
    new = _dt(new_arrival)
    shift = None
    if arrivals and new is not None:
        latest = max(arrivals)
        if new != latest:
            shift = new - latest
    events_referenced = sorted({r.get("event_raw_id") for r in registrations
                                if r.get("event_raw_id")})
    ev_by_id = {e.get("raw_id"): e for e in events}
    new_violations: list[dict] = []
    actions: list[str] = []
    if shift is None:
        actions.append("new arrival equals the current one: nothing to shift")
    else:
        for ev_id in events_referenced:
            ev = ev_by_id.get(ev_id)
            if ev is None or _dt(ev.get("start")) is None:
                actions.append(f"{ev_id}: unscheduled — keep its start after "
                               f"{new:%Y-%m-%d %H:%M}")
                continue
            ev_start = _dt(ev.get("start"))
            if ev_start < new:
                new_violations.append({
                    "type": "LATE_ARRIVAL_MISSES_EVENT", "event": ev_id,
                    "message": f"{ev_id} starts {ev_start:%Y-%m-%d %H:%M}, before "
                               f"the revised arrival {new:%Y-%m-%d %H:%M}"})
                actions.append(f"reschedule {ev_id} after the revised arrival or "
                               f"arrange a late substitution for the members")
            else:
                actions.append(f"{ev_id} still fine after the shift; check the "
                               f"arrival-to-start buffer")
    state_changes: list[dict] = []
    if shift is not None:
        for m in members:
            a = _dt(m.get("arrival"))
            d = _dt(m.get("departure"))
            state_changes.append({
                "entity": "participant", "raw_id": m.get("raw_id"),
                "old_arrival": a.isoformat() if a else None,
                "arrival": (a + shift).isoformat() if a else None,
                "departure": (d + shift).isoformat() if d else None})
    cost_delta = -int(shift.total_seconds() // 86400) * \
        C.ALLOC_HOSTEL_COST_PER_BED_NIGHT if shift else 0
    return {"report": report(state_changes, names, new_violations, actions, cost_delta),
            "shift_delta_hours": (shift.total_seconds() / 3600.0) if shift else 0.0,
            "members": [m.get("raw_id") for m in members],
            "events_referenced": events_referenced}


# ----------------------------------------------------------- duplicate record
def duplicate_record_preview(canonical: dict | None, duplicate: dict,
                             registrations_dup: list[dict]) -> dict:
    """Analysis for linking duplicate -> canonical."""
    if canonical is None:
        return {"report": report(
            [], [], [{"type": "CANONICAL_UNKNOWN"}],
            ["resolve the canonical record first"], 0),
            "can_apply": False}
    names = [n for n in (canonical.get("name"), duplicate.get("name")) if n]
    dup_events = sorted({r.get("event_raw_id") for r in registrations_dup
                         if r.get("event_raw_id")})
    state_changes = [{
        "entity": "participant", "raw_id": duplicate.get("raw_id"),
        "from_status": duplicate.get("status"), "to_status": "duplicate",
        "merged_into_raw": canonical.get("raw_id")}]
    violations = []
    if canonical.get("status") not in (None, "active", "flagged"):
        violations.append({"type": "CANONICAL_NOT_ACTIVE",
                           "message": f"canonical {canonical.get('raw_id')} is "
                                      f"{canonical.get('status')}"})
    actions = [
        "verify against the source CSV row before linking (reversible via unmerge)",
        "merch issuance for the cluster de-duplicates automatically",
        "review any bed assigned to the duplicate and re-house the canonical",
    ]
    return {"report": report(state_changes, names, violations, actions, 0),
            "can_apply": not violations,
            "duplicate_events": dup_events}


# ------------------------------------------------------------ hostel closure
def hostel_closure_preview(displaced: list[dict], rooms_open: list[dict],
                           externals: list[dict], current_taken: dict[int, int],
                           current_ext_taken: dict[int, int],
                           ext_cohorts: dict[int, str],
                           room_contingents: dict[int, str],
                           locked_in_closed: list[dict],
                           closed_room_raws: list[str]) -> dict:
    """Re-house ONLY the displaced using the allocator with initial occupancy.
    Locked allocations are respected (never moved)."""
    names = [d.get("name") or d.get("raw_id") for d in displaced]
    state_changes: list[dict] = []
    violations: list[dict] = []
    actions: list[str] = []

    if locked_in_closed:
        for l in locked_in_closed:
            violations.append({
                "type": "LOCKED_IN_CLOSED_ROOM", "participant": l.get("raw_id"),
                "room_id": l.get("room_id"),
                "message": f"{l.get('raw_id')} is locked into closed room "
                           f"{l.get('room_raw') or l.get('room_id')}; a human must "
                           f"unassign (engine leaves the bed untouched)"})
        actions.append("unlock + assign manually the locked participants in the "
                       "violations list")
        actions.append("or keep the room in service if closure is partial (dedupe "
                       "the closure room list)")

    initial_taken = dict(current_taken)
    initial_ext_taken = dict(current_ext_taken)
    plan = alloc_eng.allocate(
        [d for d in displaced], rooms_open, externals,
        preset="min_cost",
        initial_taken=initial_taken, initial_ext_taken=initial_ext_taken,
        initial_room_contingent=dict(room_contingents),
        initial_ext_genders=dict(ext_cohorts))
    for u in plan["unplaced"]:
        violations.append({"type": "NO_REHOUSING_AVAILABLE",
                           "participant": u.get("raw_id"), "message": u["reason"]})
    for u in plan["review_queue"]:
        violations.append({"type": "NEEDS_REVIEW", "participant": u.get("raw_id"),
                           "message": u["reason"]})
    state_changes.append({
        "entity": "room_set", "status": "closed", "rooms": sorted(
            closed_room_raws or [])})
    old_cost_total = sum(d.get("old_cost") or 0 for d in displaced)
    new_cost = sum(a["cost"] for a in plan["assignments"])
    for a in plan["assignments"]:
        state_changes.append({
            "entity": "allocation", "participant": a.get("raw_id"),
            "to": f"room {a['room_id']}" if a.get("room_id")
                  else f"external:{a.get('external_stay_id')}",
            "cost": a["cost"]})
    moves_campus = sum(1 for a in plan["assignments"] if a.get("room_id"))
    moves_external = sum(1 for a in plan["assignments"] if a.get("external_stay_id"))
    if not displaced:
        actions.append("no occupiable person is affected by this closure")
    else:
        actions.append(f"moves: {moves_campus} on campus, {moves_external} to "
                       f"external stays (cheapest first)")
    if plan["explanations"]:
        actions.extend(plan["explanations"][:3])
    return {
        "report": report(state_changes, names, violations, actions,
                         new_cost - old_cost_total),
        "plan": plan,
        "moves_within_campus": moves_campus,
        "moves_to_external": moves_external}


# --------------------------------------------------------- equipment failure
def equipment_failure_preview(item: dict, qty_lost: int, events: list[dict],
                              current_stock: int, movements_ref: str) -> dict:
    """Re-check equipment demand vs the reduced stock (scheduler rule)."""
    sku = item.get("sku")
    name_l = (item.get("name") or "").lower()
    needs = []
    for ev in events:
        for need in (ev.get("equipment_needs") or []):
            key = need.get("sku") if isinstance(need, dict) else need
            if not isinstance(key, str):
                continue
            kl = key.lower()
            if key == sku or kl == name_l or (name_l and name_l in kl) \
                    or (sku and sku.lower() in kl):
                qty = need.get("qty", 1) if isinstance(need, dict) else 1
                needs.append((ev, int(qty)))
    remaining = current_stock - abs(qty_lost)
    demand = sum(q for _, q in needs)
    violations = []
    if demand > remaining:
        violations.append({
            "type": "EQUIPMENT_SHORTAGE", "sku": sku,
            "message": f"{sku}: {demand} demanded vs {remaining} remaining after "
                       f"losing {qty_lost}"})
    names = [ev.get("name") or ev.get("raw_id") for ev, _ in needs]
    state_changes = [{
        "entity": "inventory_movement", "item": sku, "qty": -abs(qty_lost),
        "status": "damaged", "reference": movements_ref}]
    actions = []
    if remaining < demand:
        actions.append(f"source or borrow {demand - remaining} more '{sku}' "
                       f"(log a +qty movement once secured)")
        actions.append("or descope the requirement with the events lead (audited "
                       "event edit)")
    else:
        actions.append("stock still covers demand after the loss; ledger only")
    return {"report": report(state_changes, names, violations, actions, 0),
            "demanded_by": [{"event": ev.get("raw_id"), "qty": q} for ev, q in needs],
            "remaining": remaining}


# -------------------------------------------------------------- venue change
def venue_change_preview(event: dict, old_venue: dict | None, new_venue: dict,
                         other_events: list[dict], registrations_count: int,
                         staff_count: int) -> dict:
    """Simulate the scheduler AFTER the move and report the delta for THIS event."""
    simulated = dict(event)
    simulated["venue_id"] = new_venue["id"]
    events_after = [simulated if ev.get("raw_id") == event.get("raw_id") else ev
                    for ev in other_events]
    names = (["registered participants"] if registrations_count else []) + \
            (["staff"] if staff_count else [])
    state_changes = [{
        "entity": "event", "raw_id": event.get("raw_id"),
        "venue": (old_venue or {}).get("name"), "new_venue": new_venue.get("name")}]
    actions = [f"inform {registrations_count} registered participants and "
               f"{staff_count} assigned staff",
               "availability window, double-book and travel buffer are re-checked "
               "on apply and the result is returned"]
    return {"report": report(state_changes, names, [], actions, 0),
            "events_after": events_after}


# ------------------------------------------------------------ vendor shutdown
def vendor_shutdown_preview(vendor: dict, other_vendors: list[dict],
                            open_orders: list[dict]) -> dict:
    plan = vend_eng.reroute_on_interruption(vendor["id"],
                                            [vendor] + other_vendors, open_orders, [])
    names = [f"order #{m['order']} ({m.get('meal')} {m.get('day')}, "
             f"tag {m.get('dietary_tag')})" for m in plan["moves"]]
    names += [f"order #{u['order']} — {u['reason']}" for u in plan["unmet"]]
    state_changes = [{
        "entity": "vendor", "raw_id": vendor.get("raw_id"), "status": "interrupted",
        "orders_moved": len(plan["moves"]), "orders_unmet": len(plan["unmet"])}]
    actions = ["confirm each move with the receiving vendor before serving "
               "(compliance first: certificate must not be expired)",
               "for unmet orders arrange an alternative supplier or a menu change"]
    for m in plan["moves"]:
        actions.append(f"order #{m['order']} -> vendor "
                       f"{m.get('to_vendor_raw_id') or m.get('to_vendor')}")
    return {"report": report(state_changes, names, [], actions, 0),
            "reroute": plan}


# ------------------------------------------------------ duplicate merch claim
def duplicate_merch_claim_preview(participant: dict, canonical: dict,
                                  prior_issues: list[dict], item: dict | None) -> dict:
    names = [canonical.get("name") or canonical.get("raw_id")]
    state_changes = [{
        "entity": "participant", "raw_id": participant.get("raw_id"),
        "flag": "DUPLICATE_MERCH_CLAIM"}]
    violations = []
    for iss in prior_issues:
        violations.append({
            "type": "MERCH_ALREADY_ISSUED", "item": iss.get("item"),
            "issue_id": iss.get("id"),
            "message": f"cluster already holds issue #{iss.get('id')} for "
                       f"{iss.get('item')}; a second issue needs director force "
                       f"+ reason"})
    actions = ["refuse the claim (flag only, audited) or investigate before "
               "any second issue",
               "if the director accepts: re-issue via merch endpoint with "
               "force=True and the reason recorded"]
    return {"report": report(state_changes, names, violations, actions, 0),
            "prior_issue_ids": [i.get("id") for i in prior_issues]}

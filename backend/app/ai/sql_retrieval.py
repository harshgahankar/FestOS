"""Safe, read-only structured database retrieval service.

Authoritative source of truth:
- Pure SQLAlchemy expressions and engine calls only
- No arbitrary SQL generated or executed
- Role-based authorization enforced before every query
- Sensitive participant fields masked via app.auth.mask_fields
- Zero hallucinations: unknown or missing stays unknown
"""
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import auth as auth_mod
from app import config as C
from app.models import (
    Allocation, AllocationPlan, AuditLog, Contingent, CoreTeam, Disruption,
    Event, EventStaff, ExternalStay, HostelRoom, ImportIssue,
    InventoryItem, InventoryMovement, MerchIssue, Participant, Registration,
    Vendor, VendorOrder, Venue
)
from app.ai.schemas import SourceCitation

# Role permission mappings for querying operational domains
DOMAIN_PERMISSIONS = {
    "participants": {"director", "accommodation_lead", "events_lead", "logistics_lead", "vendor_lead", "volunteer", "viewer"},
    "contingents": {"director", "accommodation_lead", "events_lead", "logistics_lead", "vendor_lead", "volunteer", "viewer"},
    "accommodation": {"director", "accommodation_lead"},
    "schedule": {"director", "events_lead", "viewer"},
    "inventory": {"director", "logistics_lead", "volunteer", "viewer"},
    "vendors": {"director", "vendor_lead"},
    "control": {"director"},
    "disruptions": {"director"},
    "audit": {"director"},
}

FEST_DAYS = ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]


def _check_permission(role: str, domain: str) -> Optional[dict[str, Any]]:
    allowed = DOMAIN_PERMISSIONS.get(domain, set())
    if role != "director" and role not in allowed:
        return {
            "authorized": False,
            "error": f"Access to {domain} data is restricted to: {', '.join(sorted(allowed))}. Your role is '{role}'.",
            "citations": [
                SourceCitation(
                    type="authorization_notice",
                    label=f"Access denied: {domain}",
                    module=domain,
                    detail={"required_roles": sorted(list(allowed)), "user_role": role}
                )
            ]
        }
    return None


def _participant_dicts(db: Session) -> list[dict]:
    out = []
    for p in db.query(Participant).filter(Participant.merged_into.is_(None)).all():
        out.append({
            "id": p.id, "raw_id": p.raw_id, "name": p.name, "gender": p.gender,
            "contingent": p.contingent_id,
            "arrival": p.arrival_dt, "departure": p.departure_dt,
            "accommodation_requested": p.accommodation_requested,
            "accessibility_status": p.accessibility_status or "unknown",
            "accessibility_details": p.accessibility_details,
        })
    return out


def _room_dicts(db: Session) -> list[dict]:
    return [
        {
            "id": r.id, "raw_id": r.raw_id, "hostel": r.hostel, "floor": r.floor,
            "beds": r.beds, "accessible": r.accessible, "gender_block": r.gender_block,
            "readiness": r.readiness, "cleaning_until": r.cleaning_until, "status": r.status
        }
        for r in db.query(HostelRoom).all()
    ]


def _ext_dicts(db: Session) -> list[dict]:
    return [
        {
            "id": e.id, "property": e.property, "beds": e.beds,
            "cost_per_bed_night": e.cost_per_bed_night,
            "transport_available": e.transport_available
        }
        for e in db.query(ExternalStay).all()
    ]


def _v_dict(v: Vendor) -> dict:
    return {
        "id": v.id, "raw_id": v.raw_id, "name": v.name,
        "dietary_coverage": v.dietary_coverage or [],
        "hygiene_cert_expiry": v.hygiene_cert_expiry,
        "capacity_per_day": v.capacity_per_day, "rate": v.rate,
        "status": v.status
    }


def _sched_check(db: Session) -> dict:
    from engines.scheduler import find_conflicts
    events = []
    for e in db.query(Event).all():
        events.append({
            "id": e.id, "raw_id": e.raw_id, "name": e.name,
            "duration_minutes": e.duration_minutes, "venue_id": e.venue_id,
            "start": e.start_dt, "end": e.end_dt, "setup_min": e.setup_min,
            "teardown_min": e.teardown_min, "volunteers_needed": e.volunteers_needed,
            "equipment_needs": e.equipment_needs or []
        })
    venues = [
        {"id": v.id, "raw_id": v.raw_id, "name": v.name, "capacity": v.capacity,
         "availability_windows": v.availability_windows or []}
        for v in db.query(Venue).all()
    ]
    regs = [
        {"participant": r.participant_raw_id, "event_raw_id": r.event_raw_id, "event_id": r.event_id}
        for r in db.query(Registration).filter(Registration.status == "registered").all()
    ]
    staff = [
        {"event_id": s.event_id, "core_team_id": s.core_team_id, "role": s.role}
        for s in db.query(EventStaff).all()
    ]
    team = [
        {"id": t.id, "raw_id": t.raw_id, "name": t.name, "shift_start": t.shift_start,
         "shift_end": t.shift_end, "shift_crosses_midnight": t.shift_crosses_midnight}
        for t in db.query(CoreTeam).all()
    ]
    return find_conflicts(events, venues, regs, staff, team)


class SQLRetrievalService:
    """Provides verified, read-only operational answers from the live database."""

    @staticmethod
    def get_participant_counts(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "participants")
        if denied:
            return denied

        total_rows = db.query(Participant).count()
        active = db.query(Participant).filter(Participant.status == "active").count()
        flagged = db.query(Participant).filter(Participant.status == "flagged").count()
        quarantined = db.query(Participant).filter(Participant.status == "quarantined").count()
        duplicates = db.query(Participant).filter(Participant.status == "duplicate").count()
        registrations_count = db.query(Registration).filter(Registration.status == "registered").count()

        facts = {
            "total_registered_rows": total_rows,
            "active_participants": active,
            "flagged_participants": flagged,
            "quarantined_participants": quarantined,
            "linked_duplicates": duplicates,
            "event_registrations": registrations_count,
            "expected_participants": C.EXPECTED_PARTICIPANTS,
            "gap_vs_expected": active - C.EXPECTED_PARTICIPANTS,
        }

        summary = (
            f"The database currently records {total_rows} total participant rows. "
            f"Of these, {active} are active, {flagged} are flagged with data quality warnings, "
            f"{quarantined} are quarantined, and {duplicates} are linked duplicates. "
            f"Active attendance is {active} vs the expected {C.EXPECTED_PARTICIPANTS} (a gap of +{active - C.EXPECTED_PARTICIPANTS}). "
            f"There are {registrations_count} active event registrations."
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Participant Status Summary",
                    module="participants",
                    detail=facts
                )
            ]
        }

    @staticmethod
    def get_reconciliation(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "participants")
        if denied:
            return denied

        from engines.importer import reconciliation as funnel
        rec = funnel(db)

        summary = (
            f"Reconciliation Funnel:\n"
            f"- Raw imported rows: {rec['raw_imported']}\n"
            f"- Duplicates merged: {rec['duplicates_merged']}\n"
            f"- Quarantined rows: {rec['quarantined']}\n"
            f"- Flagged records: {rec['flagged']}\n"
            f"- Cancelled / test / junk: {rec['cancelled_test_junk']}\n"
            f"- Authoritative active participants: {rec['active']}\n"
            f"- Expected count: {rec['expected_participants']} (Gap: +{rec['gap_vs_expected']})\n"
            f"Operational note: {rec['note']}"
        )

        return {
            "authorized": True,
            "facts": rec,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Import Reconciliation Funnel",
                    module="participants",
                    detail={"active": rec["active"], "raw": rec["raw_imported"], "gap": rec["gap_vs_expected"]}
                )
            ]
        }

    @staticmethod
    def get_duplicate_records(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "participants")
        if denied:
            return denied

        dup_rows = db.query(Participant).filter(Participant.status == "duplicate").all()
        pairs = []
        for d in dup_rows:
            canonical = db.get(Participant, d.merged_into) if d.merged_into else None
            pairs.append({
                "duplicate_id": d.raw_id,
                "duplicate_name": d.name,
                "canonical_id": canonical.raw_id if canonical else "unknown",
                "canonical_name": canonical.name if canonical else "unknown",
                "college": d.college,
                "contingent": d.contingent_id,
                "quality_flags": d.quality_flags or []
            })

        summary = (
            f"There are {len(dup_rows)} duplicate participant records currently linked in the database:\n"
            + "\n".join([f"- Duplicate {p['duplicate_id']} ({p['duplicate_name']}) merged into canonical {p['canonical_id']} ({p['canonical_name']}) [{p['college']}]" for p in pairs])
        )

        return {
            "authorized": True,
            "facts": {"duplicate_count": len(dup_rows), "pairs": pairs},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Linked Duplicate Participants",
                    module="participants",
                    detail={"count": len(dup_rows)}
                )
            ]
        }

    @staticmethod
    def find_contingent(db: Session, query_str: str, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "contingents")
        if denied:
            return denied

        clean_q = query_str.strip()
        like = f"%{clean_q}%"
        contingents = db.query(Contingent).filter(
            (Contingent.raw_id.like(like)) |
            (Contingent.college.like(like)) |
            (Contingent.name.like(like))
        ).all()

        if not contingents:
            return {
                "authorized": True,
                "facts": {"matches_found": 0},
                "summary_text": f"No contingents matched '{clean_q}'.",
                "citations": [
                    SourceCitation(type="database_query", label=f"Contingent lookup: {clean_q}", module="contingents")
                ]
            }

        contingent = contingents[0]
        members = db.query(Participant).filter(Participant.contingent_id == contingent.raw_id).all()
        mismatch = (contingent.size_actual - contingent.size_declared) if (contingent.size_declared is not None and contingent.size_actual is not None) else None

        # Apply role-based masking on member details
        masked_members = []
        for m in members[:15]:  # limit preview
            room = None
            alloc = db.query(Allocation).filter(Allocation.participant_id == m.id).order_by(Allocation.id.desc()).first()
            if alloc:
                room = f"room {alloc.room_id}" if alloc.room_id else f"external stay #{alloc.external_stay_id}"
            masked = auth_mod.mask_fields(user_role, {
                "raw_id": m.raw_id,
                "name": m.name,
                "phone": m.phone,
                "email": m.email,
                "dietary_tags": m.dietary_tags or [],
                "status": m.status,
            }, room=room)
            masked_members.append(masked)

        facts = {
            "contingent_id": contingent.raw_id,
            "college": contingent.college,
            "leader": contingent.leader_name,
            "escort": contingent.escort_name,
            "size_declared": contingent.size_declared,
            "size_actual": contingent.size_actual,
            "size_mismatch": mismatch,
            "member_count": len(members),
            "members_sample": masked_members,
        }

        summary = (
            f"Contingent {contingent.raw_id} ({contingent.college}):\n"
            f"- Leader: {contingent.leader_name or 'unassigned'}\n"
            f"- Escort: {contingent.escort_name or 'unassigned'} (count: {contingent.escort_count})\n"
            f"- Declared strength: {contingent.size_declared}, Actual imported strength: {contingent.size_actual} (Mismatch: {mismatch or 0})\n"
            f"- Total registered members: {len(members)}"
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label=f"Contingent {contingent.raw_id} ({contingent.college})",
                    module="contingents",
                    detail={"raw_id": contingent.raw_id, "size_actual": contingent.size_actual}
                )
            ]
        }

    @staticmethod
    def get_all_contingents(db: Session, user_role: str, mismatched_only: bool = False) -> dict[str, Any]:
        denied = _check_permission(user_role, "contingents")
        if denied:
            return denied

        q = db.query(Contingent)
        if mismatched_only:
            q = q.filter(
                Contingent.size_declared.isnot(None),
                Contingent.size_actual.isnot(None),
                Contingent.size_declared != Contingent.size_actual
            )
        rows = q.order_by(Contingent.raw_id).all()

        mismatched_list = [
            f"{c.raw_id} ({c.college}): declared {c.size_declared}, actual {c.size_actual} (diff: {c.size_actual - c.size_declared})"
            for c in rows if c.size_declared != c.size_actual
        ]

        facts = {
            "total_contingents": len(rows),
            "mismatched_count": len(mismatched_list),
            "mismatches": mismatched_list,
        }

        summary = (
            f"There are {db.query(Contingent).count()} total contingents. "
            f"{len(mismatched_list)} contingents have a declared vs actual size mismatch:\n"
            + "\n".join([f"- {m}" for m in mismatched_list[:10]])
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Contingent Overview",
                    module="contingents",
                    detail={"mismatches": len(mismatched_list)}
                )
            ]
        }

    @staticmethod
    def get_accommodation_capacity(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "accommodation")
        if denied:
            return denied

        hostel_rooms = db.query(HostelRoom).count()
        hostel_beds = db.query(func.sum(HostelRoom.beds)).scalar() or 0
        ext_stays = db.query(ExternalStay).count()
        ext_beds = db.query(func.sum(ExternalStay.beds)).scalar() or 0
        total_beds = hostel_beds + ext_beds

        from engines.allocator import allocate as run_allocator
        plan = run_allocator(_participant_dicts(db), _room_dicts(db), _ext_dicts(db), preset="min_cost")
        shortage = plan["shortage"]

        active_plan = db.query(AllocationPlan).filter(AllocationPlan.status == "active").order_by(AllocationPlan.id.desc()).first()

        facts = {
            "hostel_rooms": hostel_rooms,
            "hostel_beds": int(hostel_beds),
            "external_properties": ext_stays,
            "external_beds": int(ext_beds),
            "total_bed_capacity": int(total_beds),
            "beds_requested": shortage["requested_count"],
            "hostel_beds_used": shortage["hostel_beds_used"],
            "external_beds_used": shortage["external_beds_used"],
            "unmet_count": shortage["unmet_count"],
            "active_plan_id": active_plan.id if active_plan else None,
            "active_plan_preset": active_plan.preset if active_plan else None,
        }

        active_note = f"Active Allocation Plan: Plan #{active_plan.id} (preset: {active_plan.preset})" if active_plan else "No allocation plan is currently activated (occupancy is officially pending)."

        summary = (
            f"Accommodation Capacity Summary:\n"
            f"- On-campus hostels: {hostel_rooms} rooms with {hostel_beds} total beds\n"
            f"- Off-campus external stays: {ext_stays} properties with {ext_beds} total beds\n"
            f"- Total bed inventory: {total_beds} beds\n"
            f"- Current accommodation demand: {shortage['requested_count']} participants requested housing\n"
            f"- Engine allocation result (min_cost preset): {shortage['hostel_beds_used']} hostel beds used, {shortage['external_beds_used']} external beds used, {shortage['unmet_count']} unmet shortage\n"
            f"- {active_note}"
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Accommodation Capacity & Shortage",
                    module="accommodation",
                    detail=facts
                )
            ]
        }

    @staticmethod
    def get_accommodation_shortage(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "accommodation")
        if denied:
            return denied

        from engines.allocator import allocate as run_allocator
        plan = run_allocator(_participant_dicts(db), _room_dicts(db), _ext_dicts(db), preset="min_cost")
        shortage = plan["shortage"]
        unplaced = plan["unplaced"]

        summary = (
            f"Accommodation Shortage Status:\n"
            f"- Beds requested: {shortage['requested_count']}\n"
            f"- Hostel beds allocated: {shortage['hostel_beds_used']}\n"
            f"- External beds allocated: {shortage['external_beds_used']}\n"
            f"- Unmet bed shortage: {shortage['unmet_count']}\n"
            f"- Unplaced participant records: {len(unplaced)}"
        )

        return {
            "authorized": True,
            "facts": {"shortage": shortage, "unplaced_count": len(unplaced)},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Accommodation Shortage Report",
                    module="accommodation",
                    detail=shortage
                )
            ]
        }

    @staticmethod
    def get_accommodation_review_queue(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "accommodation")
        if denied:
            return denied

        from engines.allocator import allocate as run_allocator
        plan = run_allocator(_participant_dicts(db), _room_dicts(db), _ext_dicts(db), preset="min_cost")
        queue = plan["review_queue"]

        summary = (
            f"The accommodation review queue has {len(queue)} participants requiring a human decision:\n"
            f"These involve non-binary or unstated gender, or unconfirmed accommodation consent. "
            f"By system rule A-02/A-24, housing decisions for unclear gender/consent must never be forced automatically into binary blocks."
        )

        return {
            "authorized": True,
            "facts": {"queue_count": len(queue), "sample": queue[:10]},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Accommodation Review Queue",
                    module="accommodation",
                    detail={"queue_count": len(queue)}
                )
            ]
        }

    @staticmethod
    def explain_participant_accommodation(db: Session, raw_id_or_name: str, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "accommodation")
        if denied:
            return denied

        p = db.query(Participant).filter(
            (Participant.raw_id == raw_id_or_name.strip()) |
            (Participant.name.like(f"%{raw_id_or_name.strip()}%"))
        ).first()

        if not p:
            return {
                "authorized": True,
                "facts": {"found": False},
                "summary_text": f"Participant '{raw_id_or_name}' was not found in the database.",
                "citations": [
                    SourceCitation(type="database_query", label=f"Participant lookup: {raw_id_or_name}", module="accommodation")
                ]
            }

        alloc = db.query(Allocation).filter(Allocation.participant_id == p.id).order_by(Allocation.id.desc()).first()
        if not alloc:
            return {
                "authorized": True,
                "facts": {"participant": p.raw_id, "allocated": False, "requested": p.accommodation_requested},
                "summary_text": f"Participant {p.raw_id} ({p.name}) has requested accommodation: '{p.accommodation_requested}', but currently has no bed allocation record in the database.",
                "citations": [
                    SourceCitation(type="database_query", label=f"Allocation for {p.raw_id}", module="accommodation")
                ]
            }

        room_desc = f"Hostel Room #{alloc.room_id}" if alloc.room_id else (f"External Stay #{alloc.external_stay_id}" if alloc.external_stay_id else "Unassigned")
        summary = (
            f"Allocation Explanation for Participant {p.raw_id} ({p.name}):\n"
            f"- Assigned: {room_desc}\n"
            f"- Allocation Source: {alloc.source} (Version {alloc.version})\n"
            f"- Reason / Constraint rationale: {alloc.reason or 'Standard allocation'}\n"
            f"- Cost: {alloc.cost or 0}\n"
            f"- Locked against regeneration: {alloc.locked}"
        )

        return {
            "authorized": True,
            "facts": {
                "participant_id": p.id,
                "raw_id": p.raw_id,
                "name": p.name,
                "room_id": alloc.room_id,
                "external_stay_id": alloc.external_stay_id,
                "source": alloc.source,
                "reason": alloc.reason,
                "cost": alloc.cost,
                "locked": alloc.locked,
            },
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label=f"Allocation explain: {p.raw_id}",
                    module="accommodation",
                    detail={"raw_id": p.raw_id, "room_id": alloc.room_id, "external_id": alloc.external_stay_id}
                )
            ]
        }

    @staticmethod
    def get_scheduling_conflicts(db: Session, user_role: str, venue_filter: Optional[str] = None) -> dict[str, Any]:
        denied = _check_permission(user_role, "schedule")
        if denied:
            return denied

        sched = _sched_check(db)
        conflicts = sched.get("conflicts", [])

        if venue_filter:
            conflicts = [
                c for c in conflicts
                if venue_filter.lower() in str(c.get("venue", "")).lower() or venue_filter.lower() in str(c.get("message", "")).lower()
            ]

        by_type: dict[str, int] = {}
        for c in conflicts:
            t = c.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        events_with_issues = set()
        for c in conflicts:
            for k in ("event", "event_1", "event_2"):
                val = c.get(k)
                if val:
                    events_with_issues.add(str(val))

        summary = (
            f"Scheduling Conflicts Report:\n"
            f"- Total unresolved conflicts: {len(conflicts)}\n"
            f"- Distinct events affected: {len(events_with_issues)}\n"
            f"- Conflict breakdown: {', '.join([f'{k}: {v}' for k, v in by_type.items()]) if by_type else 'No conflicts detected'}\n"
            + "\n".join([f"- [{c.get('severity', 'warning').upper()}] {c.get('type')}: {c.get('message')}" for c in conflicts[:8]])
        )

        return {
            "authorized": True,
            "facts": {
                "total_conflicts": len(conflicts),
                "by_type": by_type,
                "affected_events_count": len(events_with_issues),
                "conflicts_sample": conflicts[:15]
            },
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Scheduler Conflict Sweep",
                    module="schedule",
                    detail={"total_conflicts": len(conflicts), "by_type": by_type}
                )
            ]
        }

    @staticmethod
    def get_events_summary(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "schedule")
        if denied:
            return denied

        events = db.query(Event).all()
        venues = db.query(Venue).all()
        scheduled = [e for e in events if e.venue_id is not None and e.start_dt]
        unscheduled = [e for e in events if e.venue_id is None or not e.start_dt]

        facts = {
            "total_events": len(events),
            "scheduled_events": len(scheduled),
            "unscheduled_events": len(unscheduled),
            "total_venues": len(venues),
        }

        summary = (
            f"Event Schedule Status:\n"
            f"- Total events: {len(events)}\n"
            f"- Scheduled with venue and start time: {len(scheduled)}\n"
            f"- Unscheduled (operator input required per A-11): {len(unscheduled)}\n"
            f"- Total festival venues available: {len(venues)}"
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Event Scheduling Status",
                    module="schedule",
                    detail=facts
                )
            ]
        }

    @staticmethod
    def get_event_start_time(db: Session, event_name_or_id: Optional[str], user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "schedule")
        if denied:
            return denied

        if not event_name_or_id or not event_name_or_id.strip():
            return {
                "authorized": True,
                "needs_clarification": True,
                "facts": {},
                "summary_text": "Which event are you referring to? Share its name and I can check the available schedule.",
                "citations": [
                    SourceCitation(
                        type="notice",
                        label="Event clarification needed",
                        module="schedule"
                    )
                ]
            }

        q = event_name_or_id.strip()
        ev = db.query(Event).filter(
            (Event.raw_id == q.upper()) |
            (Event.name.ilike(q)) |
            (Event.name.ilike(f"%{q}%"))
        ).first()

        if not ev:
            return {
                "authorized": True,
                "found": False,
                "facts": {"query": q, "matched": False},
                "summary_text": "I couldn't find a matching event in the current FestOS records. Could you confirm the event name or provide its schedule?",
                "citations": [
                    SourceCitation(
                        type="notice",
                        label=f"Event not found in records",
                        module="schedule"
                    )
                ]
            }

        venue = db.get(Venue, ev.venue_id) if ev.venue_id else None
        venue_name = venue.name if venue else "Unassigned Venue"

        if not ev.start_dt:
            summary = f"The {ev.name} is listed in FestOS, but I couldn't find a confirmed start time. Please check with the event organizer or update the event schedule."
            return {
                "authorized": True,
                "found": True,
                "has_start_time": False,
                "facts": {
                    "event_name": ev.name,
                    "raw_id": ev.raw_id,
                    "venue_id": ev.venue_id,
                    "start_dt": None,
                    "duration_minutes": ev.duration_minutes
                },
                "summary_text": summary,
                "citations": [
                    SourceCitation(
                        type="database_query",
                        label=f"Event Schedule: {ev.name} ({ev.raw_id})",
                        module="schedule",
                        detail={"event_name": ev.name, "raw_id": ev.raw_id, "start_time": None}
                    )
                ]
            }

        start_str = ev.start_dt.strftime("%Y-%m-%d %I:%M %p")
        summary = f"The {ev.name} ({ev.raw_id}) is scheduled to start at {start_str} at {venue_name}."
        return {
            "authorized": True,
            "found": True,
            "has_start_time": True,
            "facts": {
                "event_name": ev.name,
                "raw_id": ev.raw_id,
                "venue_name": venue_name,
                "start_dt": start_str,
                "duration_minutes": ev.duration_minutes
            },
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label=f"Event Schedule: {ev.name} ({ev.raw_id})",
                    module="schedule",
                    detail={"event_name": ev.name, "start_time": start_str, "venue": venue_name}
                )
            ]
        }

    @staticmethod
    def check_item_inventory_status(db: Session, item_query: str, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "inventory")
        if denied:
            return denied

        q = item_query.strip().lower()
        items = db.query(InventoryItem).filter(InventoryItem.name.ilike(f"%{q}%")).all()
        if not items:
            return {
                "authorized": True,
                "found": False,
                "facts": {"query": item_query, "catalog_items": 0},
                "summary_text": f"FestOS database records currently do not list an active inventory entry or recorded shortage for '{item_query}'.",
                "citations": [
                    SourceCitation(
                        type="database_query",
                        label=f"Inventory lookup: {item_query}",
                        module="inventory",
                        detail={"query": item_query, "found": False}
                    )
                ]
            }

        return {
            "authorized": True,
            "found": True,
            "facts": {"item_query": item_query, "items_count": len(items)},
            "summary_text": f"FestOS inventory records show {len(items)} item(s) matching '{item_query}'.",
            "citations": [
                SourceCitation(
                    type="database_query",
                    label=f"Inventory status: {item_query}",
                    module="inventory",
                    detail={"items_count": len(items)}
                )
            ]
        }

    @staticmethod
    def get_inventory_levels(db: Session, user_role: str, low_stock_only: bool = False) -> dict[str, Any]:
        denied = _check_permission(user_role, "inventory")
        if denied:
            return denied

        from engines.inventory import stock_levels
        items = [
            {"id": i.id, "sku": i.sku, "name": i.name, "category": i.category,
             "size": i.size, "kind": i.kind, "condition": i.condition}
            for i in db.query(InventoryItem).all()
        ]
        movs = [
            {"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()
        ]
        stock = stock_levels(items, movs)

        items_with_qty = []
        for it in items:
            q = stock.get(it["id"], 0)
            items_with_qty.append({**it, "qty": q})

        low_stock = [i for i in items_with_qty if i["qty"] <= 2]
        repair_items = [i for i in items if (i.get("condition") or "").lower() in ("under repair", "damaged", "unserviceable")]

        facts = {
            "total_items": len(items),
            "low_stock_count": len(low_stock),
            "repair_condition_count": len(repair_items),
            "low_stock_items": [{"sku": i["sku"], "name": i["name"], "qty": i["qty"]} for i in low_stock],
            "repair_items": [{"sku": i["sku"], "name": i["name"], "condition": i["condition"]} for i in repair_items],
        }

        summary = (
            f"Inventory Status:\n"
            f"- Tracked item catalog: {len(items)} items\n"
            f"- Low stock items (<= 2 units): {len(low_stock)}\n"
            f"- Equipment requiring repair/unserviceable: {len(repair_items)}\n"
            + "\n".join([f"- {i['sku']} ({i['name']}): stock = {i['qty']}" for i in low_stock[:6]])
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Inventory Stock Ledger",
                    module="inventory",
                    detail={"low_stock_count": len(low_stock)}
                )
            ]
        }

    @staticmethod
    def get_merch_shortfall(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "inventory")
        if denied:
            return denied

        from engines.inventory import merch_shortfall as run_shortfall
        from app.routers.inventory import _item_name, _p_dict
        participants = [_p_dict(p) for p in db.query(Participant).filter(Participant.merged_into.is_(None)).all()]
        items = [
            {"id": i.id, "name": i.name, "kind": i.kind, "size": i.size}
            for i in db.query(InventoryItem).filter(InventoryItem.kind == "merch").all()
        ]
        movs = [
            {"item_id": m.item_id, "qty": m.qty, "status": m.status, "at": m.at}
            for m in db.query(InventoryMovement).all()
        ]
        issued = {(i.participant_id, _item_name(db, i.item_id)) for i in db.query(MerchIssue).all()}

        res = run_shortfall(items, movs, participants, issued_pairs=issued)
        shortfall = res["shortfall"]
        total_missing = sum(s["missing"] for s in shortfall.values())

        summary = (
            f"Merchandise Shortfall Summary:\n"
            f"- Total missing units across all sizes: {total_missing}\n"
            f"- Sizes with shortfalls: {len(shortfall)}\n"
            + "\n".join([f"- Size {sz}: needed {s['needed']}, stock {s['stock']}, missing {s['missing']}" for sz, s in shortfall.items()])
        )

        return {
            "authorized": True,
            "facts": {"demand": res["demand"], "shortfall": res["shortfall"], "total_missing": total_missing, "issued_count": len(issued)},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Merchandise Shortfall Calculation",
                    module="inventory",
                    detail={"total_missing": total_missing}
                )
            ]
        }

    @staticmethod
    def get_vendor_compliance(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "vendors")
        if denied:
            return denied

        from engines.vendors import compliance as run_compliance
        vendors = [_v_dict(v) for v in db.query(Vendor).all()]
        comp = run_compliance(vendors, FEST_DAYS[0], FEST_DAYS[-1])

        facts = {
            "total_vendors": len(vendors),
            "expired": comp["expired"],
            "expiring": comp["expiring"],
            "compliant_count": len(vendors) - len(comp["expired"]) - len(comp["expiring"]),
        }

        summary = (
            f"Vendor Compliance Report (Fest: {FEST_DAYS[0]} to {FEST_DAYS[-1]}):\n"
            f"- Total food vendors: {len(vendors)}\n"
            f"- Expired hygiene certificates: {len(comp['expired'])} ({', '.join(comp['expired']) or 'none'})\n"
            f"- Certificates expiring mid-festival: {len(comp['expiring'])} ({', '.join(comp['expiring']) or 'none'})\n"
            f"- In compliance: {facts['compliant_count']}"
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Vendor Food Safety Compliance",
                    module="vendors",
                    detail=facts
                )
            ]
        }

    @staticmethod
    def get_dietary_coverage(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "vendors")
        if denied:
            return denied

        from engines.vendors import coverage_matrix
        vendors = [_v_dict(v) for v in db.query(Vendor).all()]
        participants_diet = [
            {"id": p.id, "dietary_tags": p.dietary_tags or []}
            for p in db.query(Participant).filter(Participant.merged_into.is_(None), Participant.status.in_(("active", "flagged"))).all()
        ]
        cov = coverage_matrix(vendors, participants_diet, FEST_DAYS)

        facts = {
            "covered_tags": cov.get("covered_tags", []),
            "uncovered_tags": cov.get("uncovered_tags", []),
            "total_participants_checked": len(participants_diet),
        }

        summary = (
            f"Dietary Coverage Matrix:\n"
            f"- Fully covered diets: {', '.join(facts['covered_tags']) or 'none'}\n"
            f"- Uncovered dietary needs: {', '.join(facts['uncovered_tags']) or 'none'}\n"
            f"Operational note: Any uncovered diet requires explicit menu additions or separate meal arrangement (A-04)."
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Dietary Coverage Matrix",
                    module="vendors",
                    detail={"uncovered_tags": facts["uncovered_tags"]}
                )
            ]
        }

    @staticmethod
    def get_vendor_settlements(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "vendors")
        if denied:
            return denied

        from engines.vendors import settlement
        vendors = [_v_dict(v) for v in db.query(Vendor).all()]
        orders = [
            {"id": o.id, "vendor_id": o.vendor_id, "day": o.day, "meal": o.meal,
             "qty": o.qty, "dietary_tag": o.dietary_tag, "paid": o.paid}
            for o in db.query(VendorOrder).all()
        ]
        settle = settlement(vendors, orders)
        pending = settle.get("pending_entries", [])

        summary = (
            f"Vendor Settlement Status:\n"
            f"- Total vendor orders recorded: {len(orders)}\n"
            f"- Pending entries without rate figures: {len(pending)}\n"
            f"Operational note: Per rule A-13, the raw pack carries no rate column. Rates must be entered via audited PATCH /vendors/{{id}}/rate before settlement can finalize."
        )

        return {
            "authorized": True,
            "facts": {"order_count": len(orders), "pending_count": len(pending)},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Vendor Settlement Desk",
                    module="vendors",
                    detail={"pending_count": len(pending)}
                )
            ]
        }

    @staticmethod
    def get_control_center_status(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "control")
        if denied:
            return denied

        from app.routers.control import attention as get_attention, kpis as get_kpis
        # Direct query emulation without FastAPI Depends
        kpi_data = {
            "participants": {
                "active": db.query(Participant).filter(Participant.status == "active").count(),
                "flagged": db.query(Participant).filter(Participant.status == "flagged").count(),
                "quarantined": db.query(Participant).filter(Participant.status == "quarantined").count(),
                "total": db.query(Participant).count()
            },
            "events": {
                "total": db.query(Event).count(),
                "scheduled": db.query(Event).filter(Event.start_dt.isnot(None)).count(),
                "conflicts": len(_sched_check(db).get("conflicts", []))
            },
            "open_import_issues": db.query(ImportIssue).filter(ImportIssue.status == "open").count(),
            "recorded_disruptions": db.query(Disruption).count()
        }

        active_plan = db.query(AllocationPlan).filter(AllocationPlan.status == "active").order_by(AllocationPlan.id.desc()).first()
        kpi_data["occupancy"] = "active" if active_plan else "null (no active plan)"

        summary = (
            f"Director Control Center Status:\n"
            f"- Participants: {kpi_data['participants']['active']} active, {kpi_data['participants']['flagged']} flagged, {kpi_data['participants']['quarantined']} quarantined (total {kpi_data['participants']['total']})\n"
            f"- Open import issues: {kpi_data['open_import_issues']}\n"
            f"- Events: {kpi_data['events']['total']} total, {kpi_data['events']['scheduled']} scheduled, {kpi_data['events']['conflicts']} conflicts\n"
            f"- Accommodation occupancy: {kpi_data['occupancy']}\n"
            f"- Recorded disruptions: {kpi_data['recorded_disruptions']}"
        )

        return {
            "authorized": True,
            "facts": kpi_data,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Control Center High-Level KPIs",
                    module="control",
                    detail=kpi_data
                )
            ]
        }

    @staticmethod
    def get_pending_operational_issues(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "control")
        if denied:
            return denied

        from app.routers import control as ctrl_router
        # Execute attention logic safely
        fake_user = auth_mod._FestosUser(username="director", role="director")
        att = ctrl_router.attention(user=fake_user, db=db)
        items = att.get("items", [])
        by_sev = att.get("by_severity", {})

        summary = (
            f"Director Attention Queue ({att.get('count', 0)} total findings):\n"
            f"- Errors: {by_sev.get('error', 0)}\n"
            f"- Warnings: {by_sev.get('warning', 0)}\n"
            f"- Info: {by_sev.get('info', 0)}\n"
            + "\n".join([f"- [{i['severity'].upper()}] ({i['source']}) {i['what']} — Action: {i['action_hint']}" for i in items[:8]])
        )

        return {
            "authorized": True,
            "facts": {"total_findings": len(items), "by_severity": by_sev, "findings_sample": items[:15]},
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Director Attention Inbox",
                    module="control",
                    detail=by_sev
                )
            ]
        }

    @staticmethod
    def get_disruptions(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "disruptions")
        if denied:
            return denied

        disruptions = db.query(Disruption).order_by(Disruption.id.desc()).all()
        facts = {
            "total_disruptions": len(disruptions),
            "disruptions": [
                {"id": d.id, "type": d.type, "status": d.status, "applied_by": d.applied_by,
                 "applied_at": d.applied_at.isoformat() if d.applied_at else None}
                for d in disruptions
            ]
        }

        if not disruptions:
            summary = "No disruptions have been logged in the system yet. (Disruption types supported: late_contingent, duplicate_record, hostel_closure, equipment_failure, venue_change, vendor_shutdown, duplicate_merch_claim)."
        else:
            summary = f"Recorded disruptions ({len(disruptions)} total):\n" + "\n".join([
                f"- #{d['id']}: {d['type']} (status: {d['status']}, actor: {d['applied_by'] or 'none'})"
                for d in facts["disruptions"][:10]
            ])

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Disruption Register",
                    module="disruptions",
                    detail={"count": len(disruptions)}
                )
            ]
        }

    @staticmethod
    def get_audit_summary(db: Session, user_role: str) -> dict[str, Any]:
        denied = _check_permission(user_role, "audit")
        if denied:
            return denied

        total_audits = db.query(AuditLog).count()
        recent = db.query(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc()).limit(10).all()

        facts = {
            "total_audit_records": total_audits,
            "recent_entries": [
                {"id": a.id, "action": a.action, "entity_type": a.entity_type, "actor": a.actor_id,
                 "reason": a.reason, "kind": a.kind, "at": a.at.isoformat() if a.at else None}
                for a in recent
            ]
        }

        summary = (
            f"The audit trail contains {total_audits} immutable change records. "
            f"Recent logged actions include:\n"
            + "\n".join([f"- [{a['at'] or ''}] {a['actor']}: {a['action']} on {a['entity_type']} (reason: {a['reason']})" for a in facts["recent_entries"][:6]])
        )

        return {
            "authorized": True,
            "facts": facts,
            "summary_text": summary,
            "citations": [
                SourceCitation(
                    type="database_query",
                    label="Audit Trail Log",
                    module="audit",
                    detail={"total_records": total_audits}
                )
            ]
        }

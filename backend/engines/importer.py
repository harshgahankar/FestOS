"""CSV importer: validate, quarantine, dedupe, reconcile.

Pure engine: plain Python + SQLAlchemy only. No FastAPI imports.
Hard rules honoured here:
  * never delete or silently correct source data (quarantine/flag/link instead)
  * a blank is NEVER interpreted as "no" (gender, dietary, accessibility...)
  * rules and thresholds come from app.config, not literals
"""
from __future__ import annotations

import re
from datetime import datetime, date, time
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app import audit, config as C
from app.models import (Contingent, CoreTeam, Event, ExternalStay, HostelRoom,
                        ImportIssue, InventoryItem, InventoryMovement, Participant,
                        Registration, Venue, Vendor)

# --------------------------------------------------------------------- helpers
DT_FMT = "%Y-%m-%d %H:%M"


def parse_dt(value: str) -> datetime | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, DT_FMT)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    v = (value or "").strip()
    if not v or not re.fullmatch(r"-?\d+", v):
        return None
    return int(v)


def parse_float(value: str) -> float | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_date(value: str) -> date | None:
    v = (value or "").strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        return None


def split_multi(value: str, sep: str = ";") -> list[str]:
    return [p.strip() for p in (value or "").split(sep) if p.strip()]


def blank(value: str) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def three_state(value: str) -> str:
    """Never maps a blank to 'no' (three-state: yes/no/unknown)."""
    v = (value or "").strip().lower()
    if v == "yes":
        return "yes"
    if v == "no":
        return "no"
    return "unknown"


def id_sort_key(raw_id: str) -> int:
    """P0001 -> 1; P_DUP01 -> 90001 (canonicals keep lowest sort)."""
    m = re.fullmatch(r"P(\d+)", raw_id or "")
    if m:
        return int(m.group(1))
    return 90000 + len(raw_id or "")


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits


def suspect_phone(value: str) -> str | None:
    """Return a rule name if the phone looks fabricated; None if fine."""
    for name, pattern in C.SUSPECT_PHONE_RULES:
        if re.match(pattern, value or ""):
            return name
    return None


class Reporter:
    """Collects import_issues rows (quarantine/flag records, never silent drops)."""

    def __init__(self, db: Session):
        self.db = db
        self.counts: dict[str, int] = {}

    def add(self, file: str, row: str | None, field: str | None, severity: str,
            code: str, message: str) -> None:
        self.db.add(ImportIssue(file=file, row=row, field=field, severity=severity,
                                code=code, message=message, status="open"))
        self.counts[code] = self.counts.get(code, 0) + 1


# ------------------------------------------------------------------- upserting
def _existing_by_raw(db: Session, model, source_file: str | None = None) -> dict:
    """Prefetch raw_id -> row (first wins) so file loops run ONE query instead of
    one per row. Roundtrip-sensitive: remote DBs (e.g. Supabase Postgres) bill
    ~0.5s per query, a per-row lookup makes a 8k-row import take hours."""
    q = db.query(model)
    if source_file is not None:
        q = q.filter(model.source_file == source_file)
    out: dict = {}
    for m in q.order_by(model.id):
        out.setdefault(m.raw_id, m)
    return out


def _snapshot(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns
            if c.name not in ("id", "created_at", "updated_at", "deleted_at")}


def upsert(db: Session, model, existing, payload: dict, actor: str, file: str,
           row: str | None, reporter: Reporter) -> Any:
    """Insert or update-in-place. Updates are audited and recorded as issues
    (idempotent re-import: unchanged rows are no-ops, A-26)."""
    if existing is None:
        obj = model(**payload)
        db.add(obj)   # flushed once per file by _audit_file -> log_change -> flush
        return obj
    before = _snapshot(existing)
    changed = False
    for k, v in payload.items():
        if getattr(existing, k) != v:
            setattr(existing, k, v)
            changed = True
    if changed:
        audit.log_change(db, actor, model.__tablename__, existing.id, before,
                         {k: v for k, v in payload.items()}, "reimport changed row",
                         kind="system")
        reporter.add(file, row, None, "info", "CHANGED_ON_REIMPORT",
                     f"row {row} differed on re-import; updated in place (audited)")
    return existing


# ------------------------------------------------------------ field mappings
def participant_fields(r: dict) -> tuple[dict, list[str], list[str], list[str]]:
    """Return (payload, flags, hard-fail reasons, code-warnings)."""
    flags: list[str] = []
    hard: list[str] = []
    warns: list[str] = []

    gender_given = (r["gender_as_given"] or "").strip()
    gender = C.GENDER_AS_GIVEN_MAP.get(gender_given, C.UNKNOWN_TOKEN)

    acc_raw = (r["accessibility_needs"] or "").strip()
    if blank(acc_raw):
        acc_status = "unknown"          # blank is never 'no'
        warns.append("ACCESSIBILITY_UNKNOWN")
    elif acc_raw == C.ACCESSIBILITY_NONE_LITERAL:
        acc_status = "no"
    else:
        acc_status = "yes"

    diet_raw = (r["dietary_needs"] or "").strip()
    if blank(diet_raw):
        diet_status = "unknown"          # blank is never 'no dietary needs'
        flags.append("DIETARY_UNVERIFIED")
    else:
        diet_status = "known"

    if blank(gender_given) or gender == C.UNKNOWN_TOKEN:
        flags.append("GENDER_UNDECLARED")

    arrival = parse_dt(r["arrival_datetime"])
    departure = parse_dt(r["departure_datetime"])
    if arrival is None:
        hard.append("ARRIVAL_UNPARSED")
    if departure is None:
        hard.append("DEPARTURE_UNPARSED")

    arr_start = parse_dt(C.ARRIVAL_WINDOW_START)
    arr_end = parse_dt(C.ARRIVAL_WINDOW_END)
    fest_end = datetime.strptime(C.FEST_DAYS["end"] + " 23:59", "%Y-%m-%d %H:%M")
    if arrival is not None:
        if arrival < arr_start or arrival > arr_end:
            flags.append("ARRIVAL_OUT_OF_WINDOW")
        if arrival > fest_end:
            flags.append("POST_FEST_ARRIVAL")
    if arrival and departure and departure < arrival:
        flags.append("DEPARTURE_BEFORE_ARRIVAL")

    age = parse_int(r["age"])
    if blank(r["age"]):
        flags.append("AGE_UNKNOWN")        # blank is unknown, never compared/judged
    elif age is None:
        hard.append("AGE_UNPARSED")         # garbage value -> quarantine
    elif not (C.AGE_MIN <= age <= C.AGE_MAX):  # parse ok but implausible: flag, don't drop
        flags.append("AGE_IMPLAUSIBLE")

    phone = (r["contact"] or "").strip()
    spam = suspect_phone(phone)
    if spam:
        flags.append("SUSPECT_PHONE")

    if blank(r["name"]):
        hard.append("NAME_MISSING")
    if blank(r["college"]):
        hard.append("COLLEGE_MISSING")
    if blank(r["contingent_id"]):
        hard.append("CONTINGENT_MISSING")

    status_ = C.QUARANTINED_STATUS if hard else (
        C.FLAGGED_STATUS if any(
            f in ("POST_FEST_ARRIVAL", "DEPARTURE_BEFORE_ARRIVAL", "ARRIVAL_OUT_OF_WINDOW")
            for f in flags) else "active")

    payload = dict(
        raw_id=r["participant_id"],
        source_file="participants.csv",
        source_row_id=r["participant_id"],
        name=r["name"].strip(),
        college=(r["college"] or "").strip() or None,
        contingent_id=(r["contingent_id"] or "").strip() or None,
        gender=gender,
        gender_as_given=gender_given or None,
        age=age,
        phone=phone or None,
        phone_normalized=normalize_phone(phone) or None,
        email=None,
        arrival_dt=arrival,
        departure_dt=departure,
        accommodation_requested=three_state(r["accommodation_requested"]),
        housing_pref=None,
        accessibility_status=acc_status,
        accessibility_details=acc_raw or None,
        dietary_status=diet_status,
        dietary_tags=[] if diet_status == "unknown" else [diet_raw],
        tshirt_size=(r["tshirt_size"] or "").strip() or None,
        status=status_,
        merged_into=None,
        quality_flags=sorted(set(flags + warns)),
    )
    return payload, flags, hard, warns


# ------------------------------------------------------- duplication detection
def find_duplicate_clusters(rows: list[dict]) -> list[list[str]]:
    """Pure data-in/data-out duplicate detector.

    rows: dicts with keys participant_id, name, college, contingent_id,
    gender_as_given, age, contact, accessibility_needs, dietary_needs,
    arrival_datetime, departure_datetime, accommodation_requested, tshirt_size.
    Returns clusters like [canonical_id, dup_id, ...] (canonical = lowest id).

    Stage 1 (exact): every field except participant_id and contact identical.
    Stage 2 (fuzzy): remaining rows, same soft fingerprint (all fields except
    participant_id, contact AND name), name similarity >= DUP_NAME_FUZZ_THRESHOLD.
    """
    fields = [k for k in C.DUP_FLAGS_CORROBORATION_FIELDS if k != "contact"]
    rows = sorted(rows, key=lambda r: id_sort_key(r["participant_id"]))

    def soft_key(r: dict) -> str:
        return "|".join((r[k] or "").strip().lower() for k in fields)

    def name_key(r: dict) -> str:
        return (r["name"] or "").strip().lower()

    root_by_pid: dict[str, str] = {}
    exact_seen: dict[tuple[str, str], str] = {}
    soft_groups: dict[str, list[dict]] = {}

    for r in rows:
        pid = r["participant_id"]
        sk, nk = soft_key(r), name_key(r)
        root = exact_seen.get((sk, nk))
        if root is not None:                      # stage 1: exact duplicate
            root_by_pid[pid] = root
            root_by_pid.setdefault(root, root)
            continue
        exact_seen[(sk, nk)] = pid
        root_by_pid[pid] = pid
        soft_groups.setdefault(sk, []).append(r)

    for group in soft_groups.values():            # stage 2: fuzzy within fingerprint
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                cand = group[j]
                if root_by_pid[cand["participant_id"]] != cand["participant_id"]:
                    continue
                score = fuzz.token_sort_ratio(name_key(group[i]), name_key(cand))
                if score >= C.DUP_NAME_FUZZ_THRESHOLD:
                    root_by_pid[cand["participant_id"]] = group[i]["participant_id"]

    clusters_by_root: dict[str, list[str]] = {}
    for pid, root in root_by_pid.items():
        clusters_by_root.setdefault(root, []).append(pid)
    return [sorted(members) for members in clusters_by_root.values() if len(members) > 1]


# --------------------------------------------------------------------- importers
def import_participants(db: Session, df: pd.DataFrame, actor: str,
                        reporter: Reporter) -> dict:
    rows = df.to_dict("records")
    inserted = 0
    gender_blank: list[str] = []
    dietary_blank: list[str] = []
    by_raw = _existing_by_raw(db, Participant, source_file="participants.csv")

    for i, r in enumerate(rows):
        payload, flags, hard, warns = participant_fields(r)
        if blank(r["gender_as_given"]):
            gender_blank.append(r["participant_id"])
        if "DIETARY_UNVERIFIED" in flags:
            dietary_blank.append(r["participant_id"])
        if hard:
            reporter.add("participants.csv", r["participant_id"], ";".join(hard), "error",
                         "QUARANTINED_ROW",
                         f"{r['participant_id']}: {', '.join(hard)} — kept with status "
                         f"quarantined, never dropped")
        existing = by_raw.get(r["participant_id"])
        was_new = existing is None
        if existing is not None and existing.merged_into is not None:
            # don't clobber dedupe linkage state on re-import (idempotency, A-26)
            payload = {k: v for k, v in payload.items()
                       if k not in ("status", "merged_into", "quality_flags")}
        upsert(db, Participant, existing, payload, actor, "participants.csv",
                     r["participant_id"], reporter)
        if was_new:
            inserted += 1

    # aggregated quality warnings (one issue per code, not thousands per row)
    if gender_blank:
        reporter.add("participants.csv", "aggregate", "gender_as_given", "warning",
                     "GENDER_DECLARED_MISSING",
                     f"{len(gender_blank)} participants left gender blank; imported as "
                     f"unknown (never 'no'): {gender_blank[:8]}{'...' if len(gender_blank) > 8 else ''}")
    if dietary_blank:
        reporter.add("participants.csv", "aggregate", "dietary_needs", "warning",
                     "DIETARY_UNVERIFIED",
                     f"{len(dietary_blank)} participants left dietary_needs blank; imported as "
                     f"unknown, food plans need verification: "
                     f"{dietary_blank[:8]}{'...' if len(dietary_blank) > 8 else ''}")

    # contingent declared vs actual (cross-file integrity, A-09)
    contingents = db.query(Contingent).all()
    actuals: dict[str, int] = {}
    for r in rows:
        actuals[r["contingent_id"]] = actuals.get(r["contingent_id"], 0) + 1
    for cont in contingents:
        before = {"size_actual": cont.size_actual}
        cont.size_actual = actuals.get(cont.raw_id)
        if before["size_actual"] != cont.size_actual:
            audit.log_change(db, actor, "contingent", cont.id, before,
                             {"size_actual": cont.size_actual},
                             "size_actual derived from imported participant counts",
                             kind="system")
        if cont.size_declared is not None and cont.size_actual is not None \
                and cont.size_declared != cont.size_actual:
            reporter.add("contingents.csv", cont.raw_id, "strength_declared", "warning",
                         "CONTINGENT_SIZE_MISMATCH",
                         f"{cont.college} ({cont.raw_id}): declared "
                         f"{cont.size_declared} vs actual {cont.size_actual} imported "
                         f"participants (delta {cont.size_actual - cont.size_declared})")

    _audit_file(db, actor, "participants.csv", "participants", len(rows))
    return {"rows": len(rows), "inserted": inserted}


def import_contingents(db: Session, df: pd.DataFrame, actor: str,
                       reporter: Reporter) -> dict:
    inserted = 0
    by_raw = _existing_by_raw(db, Contingent)
    for r in df.to_dict("records"):
        payload = dict(
            raw_id=r["contingent_id"],
            source_file="contingents.csv",
            source_row_id=r["contingent_id"],
            name=r["college"],
            college=r["college"],
            leader_name=r["leader"] or None,
            escort_name=r["escort"] or None,
            escort_count=1 if (r["escort"] or "").strip() else 0,
            size_declared=parse_int(r["strength_declared"]),
            # size_actual is never touched here; import_participants derives it
            preferences=split_multi(r["preferences"]),
            preferences_raw=r["preferences"] or None,
        )
        if parse_int(r["strength_declared"]) is None:
            reporter.add("contingents.csv", r["contingent_id"], "strength_declared",
                         "error", "UNPARSED_INT",
                         f"{r['contingent_id']}: strength_declared {r['strength_declared']!r}")
        existing = by_raw.get(r["contingent_id"])
        was_new = existing is None
        upsert(db, Contingent, existing, payload, actor, "contingents.csv",
                     r["contingent_id"], reporter)
        if was_new:
            inserted += 1
    _audit_file(db, actor, "contingents.csv", "contingents", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_events(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    by_raw = _existing_by_raw(db, Event)
    for r in df.to_dict("records"):
        dm = parse_int(r["duration_minutes"])
        vn = parse_int(r["volunteers_needed"])
        if dm is None:
            reporter.add("events.csv", r["event_id"], "duration_minutes", "error",
                         "UNPARSED_INT", f"{r['event_id']}: duration_minutes unparsed")
        payload = dict(
            raw_id=r["event_id"],
            source_file="events.csv",
            source_row_id=r["event_id"],
            name=r["event_name"],
            type=r["type"],
            rounds=split_multi(r["rounds"], "|") if "|" in r["rounds"] else (
                ["single"] if r["rounds"] == "single" else [r["rounds"]]),
            rounds_raw=r["rounds"],
            duration_minutes=dm,
            venue_id=None,            # A-11: the pack defines no venues for events
            start_dt=None, end_dt=None,
            setup_min=None, teardown_min=None, capacity=None, judges_needed=None,
            venue_requirements=split_multi(r["venue_requirements"]),
            equipment_needs=[] if r["equipment_needs"] == "no special equipment"
                             else split_multi(r["equipment_needs"]),
            volunteers_needed=vn,
            status="planned",
        )
        existing = by_raw.get(r["event_id"])
        was_new = existing is None
        upsert(db, Event, existing, payload, actor, "events.csv", r["event_id"], reporter)
        if was_new:
            inserted += 1
    reporter.add("events.csv", "aggregate", None, "info", "EVENTS_NO_SCHEDULE",
                 "events.csv provides no venue_id/start/end times (A-11); scheduler needs "
                 "operator-entered slots — spec fields left nullable")
    _audit_file(db, actor, "events.csv", "events", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_venues(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    by_raw = _existing_by_raw(db, Venue)
    win_pat = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})-(\d{2}:\d{2})")
    for r in df.to_dict("records"):
        windows = []
        for m in win_pat.finditer(r["availability_windows"] or ""):
            windows.append({"date": m.group(1), "open": m.group(2), "close": m.group(3)})
        cap = parse_int(r["capacity"])
        if cap is None:
            reporter.add("venues.csv", r["venue_id"], "capacity", "error", "UNPARSED_INT",
                         f"{r['venue_id']}: capacity unparsed")
        payload = dict(
            raw_id=r["venue_id"], source_file="venues.csv", source_row_id=r["venue_id"],
            name=r["venue_name"], capacity=cap,
            availability_windows=windows, windows_raw=r["availability_windows"],
            status="open", location=r["indoor_outdoor"])
        existing = by_raw.get(r["venue_id"])
        was_new = existing is None
        upsert(db, Venue, existing, payload, actor, "venues.csv", r["venue_id"], reporter)
        if was_new:
            inserted += 1
    _audit_file(db, actor, "venues.csv", "venues", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_hostels(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    total_beds = 0
    by_raw = _existing_by_raw(db, HostelRoom)
    for r in df.to_dict("records"):
        beds = parse_int(r["capacity"])
        if beds is None:
            reporter.add("hostels.csv", r["room_id"], "capacity", "error", "UNPARSED_INT",
                         f"{r['room_id']}: capacity unparsed")
        else:
            total_beds += beds
        parts = (r["room_id"] or "").split("-")
        room_no = parts[-1] if len(parts) == 3 else r["room_id"]
        payload = dict(
            raw_id=r["room_id"], source_file="hostels.csv", source_row_id=r["room_id"],
            hostel=r["block"], floor=parse_int(r["floor"]), room_no=room_no, beds=beds,
            accessible=(r["accessibility"] == "yes"),
            gender_block=r["gender"],
            readiness="ready", cleaning_until=None,   # A-15: pack has no readiness
            status="open" if r["status"] == "available" else r["status"])
        existing = by_raw.get(r["room_id"])
        was_new = existing is None
        upsert(db, HostelRoom, existing, payload, actor, "hostels.csv", r["room_id"], reporter)
        if was_new:
            inserted += 1
    if total_beds != C.EXPECTED_HOSTEL_BEDS:
        reporter.add("hostels.csv", "aggregate", "capacity", "warning",
                     "HOSTEL_BED_TOTAL_MISMATCH",
                     f"bed checksum {total_beds} != expected {C.EXPECTED_HOSTEL_BEDS}")
    else:
        reporter.add("hostels.csv", "aggregate", "capacity", "info",
                     "HOSTEL_BED_CHECK_OK",
                     f"bed checksum {total_beds} matches expected {C.EXPECTED_HOSTEL_BEDS}")
    _audit_file(db, actor, "hostels.csv", "hostel_rooms", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_external_stays(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    by_raw = _existing_by_raw(db, ExternalStay)
    for r in df.to_dict("records"):
        beds = parse_int(r["beds"])
        cost = parse_int(r["cost_per_bed_per_night"])
        dist = parse_float(r["distance_km"])
        if None in (beds, cost):
            reporter.add("external_stays.csv", r["property_id"], None, "error",
                         "UNPARSED_NUMBER",
                         f"{r['property_id']}: beds/cost unparsed")
        transport = (r["transport_availability"] or "").strip().lower() or "unknown"
        payload = dict(
            raw_id=r["property_id"], source_file="external_stays.csv",
            source_row_id=r["property_id"], property=r["property_name"], beds=beds,
            cost_per_bed_night=cost, distance_km=dist,
            travel_minutes=None,                   # A-14: not in pack; engine estimates
            transport_available=transport,
            safety_coverage="unknown",             # A-14: not in pack
            status="open")
        existing = by_raw.get(r["property_id"])
        was_new = existing is None
        upsert(db, ExternalStay, existing, payload, actor, "external_stays.csv",
                     r["property_id"], reporter)
        if was_new:
            inserted += 1
        if transport == "limited":
            reporter.add("external_stays.csv", r["property_id"], "transport_availability",
                         "warning", "LIMITED_TRANSPORT",
                         f"{r['property_name']}: transport is 'limited' — late/early "
                         f"movement needs a plan, never assumed available")
    _audit_file(db, actor, "external_stays.csv", "external_stays", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_vendors(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    FestStart = datetime.strptime(C.FEST_DAYS["start"], "%Y-%m-%d").date()
    FestEnd = datetime.strptime(C.FEST_DAYS["end"], "%Y-%m-%d").date()
    by_raw = _existing_by_raw(db, Vendor)
    for r in df.to_dict("records"):
        expiry = parse_date(r["hygiene_certificate_expiry"])
        hours = (r["hours"] or "").split("-")
        try:
            opens = time.fromisoformat(hours[0].replace(" ", "")) if hours else None
            closes = time.fromisoformat(hours[1].replace(" ", "")) if len(hours) > 1 else None
        except ValueError:
            opens = closes = None
            reporter.add("vendors.csv", r["vendor_id"], "hours", "error", "UNPARSED_HOURS",
                         f"{r['vendor_id']}: hours {r['hours']!r}")
        if expiry is None:
            reporter.add("vendors.csv", r["vendor_id"], "hygiene_certificate_expiry",
                         "error", "UNPARSED_DATE",
                         f"{r['vendor_id']}: hygiene cert expiry unparsed")
        elif expiry < FestStart:
            reporter.add("vendors.csv", r["vendor_id"], "hygiene_certificate_expiry",
                         "error", "VENDOR_CERT_EXPIRED",
                         f"{r['vendor_name']}: hygiene cert expired {expiry} "
                         f"(fest starts {FestStart}) — blocked until re-verified")
        elif expiry < FestEnd:
            reporter.add("vendors.csv", r["vendor_id"], "hygiene_certificate_expiry",
                         "warning", "VENDOR_CERT_EXPIRING_MID_FEST",
                         f"{r['vendor_name']}: hygiene cert expires {expiry}, during the fest")
        payload = dict(
            raw_id=r["vendor_id"], source_file="vendors.csv", source_row_id=r["vendor_id"],
            name=r["vendor_name"], menu=[r["menu"]],
            dietary_coverage=split_multi(r["dietary_options"]),
            hygiene_cert_expiry=expiry,
            hours=r["hours"], opens=opens, closes=closes,
            capacity_per_day=parse_int(r["capacity"]), rate=None,       # A-13
            payment_terms=r["payment_terms"], status="active")
        existing = by_raw.get(r["vendor_id"])
        was_new = existing is None
        upsert(db, Vendor, existing, payload, actor, "vendors.csv", r["vendor_id"], reporter)
        if was_new:
            inserted += 1
    _audit_file(db, actor, "vendors.csv", "vendors", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_core_team(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    inserted = 0
    by_raw = _existing_by_raw(db, CoreTeam)
    for r in df.to_dict("records"):
        hours = (r["shift"] or "").split("-")
        try:
            st = time.fromisoformat(hours[0].replace(" ", "")) if hours else None
            en = time.fromisoformat(hours[1].replace(" ", "")) if len(hours) > 1 else None
        except ValueError:
            st = en = None
            reporter.add("core_team.csv", r["member_id"], "shift", "error", "UNPARSED_HOURS",
                         f"{r['member_id']}: shift {r['shift']!r}")
        payload = dict(
            raw_id=r["member_id"], source_file="core_team.csv", source_row_id=r["member_id"],
            name=r["name"], role=r["role"], shift_start=st, shift_end=en,
            shift_raw=r["shift"],
            shift_crosses_midnight=bool(st and en and en <= st),   # A-16
            skills=[], contact=r["phone"])
        existing = by_raw.get(r["member_id"])
        was_new = existing is None
        upsert(db, CoreTeam, existing, payload, actor, "core_team.csv", r["member_id"], reporter)
        if was_new:
            inserted += 1
    _audit_file(db, actor, "core_team.csv", "core_team", inserted)
    return {"rows": len(df), "inserted": inserted}


def import_registrations(db: Session, df: pd.DataFrame, actor: str, reporter: Reporter) -> dict:
    all_parts = db.query(Participant).order_by(Participant.id).all()
    p_by_raw: dict[str, Participant] = {}
    p_multi: dict[str, list[Participant]] = {}
    for p in all_parts:
        p_multi.setdefault(p.raw_id, []).append(p)
        if p.merged_into is None:
            p_by_raw.setdefault(p.raw_id, p)
    e_by_raw = {e.raw_id: e for e in db.query(Event).all()}
    type_by_event = {e.raw_id: e.type for e in e_by_raw.values()}
    existing_by_row: dict[str, Registration] = {}
    for reg in db.query(Registration).order_by(Registration.id):
        if reg.source_row_id:
            existing_by_row.setdefault(reg.source_row_id, reg)
    inserted = quarantine = 0
    canon_seen: set[tuple[int, int]] = set()
    solo_with_team = 0
    team_missing_team = 0

    for i, r in enumerate(df.to_dict("records")):
        row_ref = f"registrations.csv#r{i + 1}"
        pint = p_by_raw.get(r["participant_id"])
        eeve = e_by_raw.get(r["event_id"])
        if pint is None or eeve is None:
            # nearest participant (duplicate status) is mapped to canonical
            if pint is None:
                parts = p_multi.get(r["participant_id"], [])
                if len(parts) == 1 and parts[0].merged_into:
                    pint = parts[0]
            if pint is None or eeve is None:
                reporter.add("registrations.csv", row_ref, "participant_id/event_id",
                             "error", "FK_MISSING_QUARANTINED",
                             f"registration {r['participant_id']}->{r['event_id']} has "
                             f"missing {'participant' if pint is None else 'event'} FK")
                payload = dict(
                    source_file="registrations.csv", source_row_id=row_ref,
                    participant_id=None if pint is None else pint.id,
                    participant_raw_id=r["participant_id"],
                    event_id=None if eeve is None else eeve.id,
                    event_raw_id=r["event_id"], role=None,
                    team_id=(r["team_id"] or "").strip() or None,
                    status="quarantined")
                upsert(db, Registration, None, payload, actor, "registrations.csv",
                       row_ref, reporter)
                quarantine += 1
                continue
        # duplicates' registrations collapse onto the canonical cluster member (A-06)
        canonical_seen = (pint.id, eeve.id) in canon_seen
        if pint.status == C.DUPLICATE_STATUS and pint.merged_into:
            canon = db.get(Participant, pint.merged_into)
            reporter.add("registrations.csv", row_ref, "participant_id", "info",
                         "REGISTRATION_OF_DUPLICATE",
                         f"registration row of duplicate {r['participant_id']} mapped to "
                         f"canonical {canon.raw_id} ({r['event_id']})")
            pint = canon
            canonical_seen = (pint.id, eeve.id) in canon_seen
        if canonical_seen:
            reporter.add("registrations.csv", row_ref, "participant_id", "warning",
                         "REGISTRATION_REPEATED",
                         f"{pint.raw_id} already has a registration for {r['event_id']} "
                         f"(second row recorded as issue, not inserted twice silently)")
            continue
        canon_seen.add((pint.id, eeve.id))
        role = "solo" if type_by_event.get(eeve.raw_id) == "solo" else "member"
        team_raw = (r["team_id"] or "").strip() or None
        if team_raw and type_by_event.get(eeve.raw_id) == "solo":
            solo_with_team += 1
        elif not team_raw and type_by_event.get(eeve.raw_id) == "team":
            team_missing_team += 1
        payload = dict(
            source_file="registrations.csv", source_row_id=row_ref,
            participant_id=pint.id, participant_raw_id=r["participant_id"],
            event_id=eeve.id, event_raw_id=r["event_id"], role=role, team_id=team_raw,
            status="registered")
        existing = existing_by_row.get(row_ref)
        was_new = existing is None
        upsert(db, Registration, existing, payload, actor, "registrations.csv",
                     row_ref, reporter)
        if was_new:
            inserted += 1
    if team_missing_team:
        reporter.add("registrations.csv", "aggregate", "team_id", "warning",
                     "TEAM_EVENT_ROWS_NO_TEAM_ID",
                     f"{team_missing_team} team-event registrations have blank team_id; "
                     f"team membership not derivable (A-10)")
    if solo_with_team:
        reporter.add("registrations.csv", "aggregate", "team_id", "warning",
                     "SOLO_EVENT_ROWS_HAVE_TEAM_ID",
                     f"{solo_with_team} solo-event registrations carry team_id values "
                     f"(T{{event}}-C{{contingent}}-{{n}}, most with a single member); "
                     f"stored raw, not used as team truth (A-10)")
    _audit_file(db, actor, "registrations.csv", "registrations", inserted + quarantine)
    return {"rows": len(df), "inserted": inserted}

def import_inventory(db: Session, logistics: pd.DataFrame, merch: pd.DataFrame,
                     actor: str, reporter: Reporter) -> dict:
    inserted = 0
    by_sku: dict[str, InventoryItem] = {}
    for it in db.query(InventoryItem).order_by(InventoryItem.id):
        by_sku.setdefault(it.sku, it)
    pending: list[tuple[InventoryItem, int, str, str, str]] = []
    for r in logistics.to_dict("records"):
        qty = parse_int(r["quantity"])
        payload = dict(
            source_file="inventory_logistics.csv", source_row_id=r["item_id"],
            sku=r["item_id"], name=r["item"], category=r["item"], size=None,
            kind="logistics",
            condition=r["condition"])
        existing = by_sku.get(r["item_id"])
        was_new = existing is None
        obj = upsert(db, InventoryItem, existing, payload, actor,
                     "inventory_logistics.csv", r["item_id"], reporter)
        if was_new:
            inserted += 1
            pending.append((obj, qty or 0, r["location"], "available",
                            "opening stock (import)"))
        if r["condition"] != "good":
            reporter.add("inventory_logistics.csv", r["item_id"], "condition", "warning",
                         "ITEM_NOT_SERVICEABLE",
                         f"{r['item_id']} {r['item']} at {r['location']}: condition "
                         f"{r['condition']!r} — treat as unavailable until fixed")
    for i, r in enumerate(merch.to_dict("records")):
        qty = parse_int(r["quantity"])
        res = parse_int(r["reserved_quantity"])
        size = None if r["size"] == "NA" else r["size"]
        sku = f"MERCH-{r['item'].replace(' ', '_').upper()}-{r['size']}"
        payload = dict(
            source_file="inventory_merch.csv", source_row_id=sku, sku=sku,
            name=r["item"], category=r["item"], size=size, kind="merch",
            condition=None)
        existing = by_sku.get(sku)
        was_new = existing is None
        obj = upsert(db, InventoryItem, existing, payload, actor,
                     "inventory_merch.csv", sku, reporter)
        if was_new:
            inserted += 1
            pending.append((obj, qty or 0, "Merch Desk", "available",
                            "opening stock (import)"))
            if res:
                pending.append((obj, res, "Merch Desk", "reserved",
                                "csv reserved_quantity"))
    db.flush()   # one roundtrip: assign ids to freshly inserted items
    for obj, mv_qty, to_loc, status, reference in pending:
        db.add(InventoryMovement(item_id=obj.id, qty=mv_qty, from_location=None,
                                 to_location=to_loc, status=status,
                                 reference=reference, actor=actor))
    _audit_file(db, actor, "inventory_logistics.csv+inventory_merch.csv", "inventory_items", inserted)
    return {"rows": len(logistics) + len(merch), "inserted": inserted}


def _audit_file(db: Session, actor: str, file: str, entity: str, count: int) -> None:
    audit.log_change(db, actor, entity, file, None, {"rows": count},
                     f"imported {count} {entity} rows from {file}", kind="system")


# ---------------------------------------------------------------------- dedupe
def link_duplicates(db: Session, actor: str = "importer",
                    reporter: Reporter | None = None) -> dict:
    """Detect participant duplicates and link them (reversible, audited)."""
    rows = db.query(Participant).all()
    if not rows:
        return {"clusters": 0, "duplicates_linked": 0}
    dict_rows = []
    for p in rows:
        d = {
            "participant_id": p.raw_id,
            "name": p.name or "",
            "college": p.college or "",
            "contingent_id": p.contingent_id or "",
            "gender_as_given": p.gender_as_given or "",
            "age": "" if p.age is None else str(p.age),
            "contact": p.phone or "",
            "accessibility_needs": p.accessibility_details or "",
            "dietary_needs": "" if not p.dietary_tags else (p.dietary_tags[0] or ""),
            "arrival_datetime": p.arrival_dt.strftime(DT_FMT) if p.arrival_dt else "",
            "departure_datetime": p.departure_dt.strftime(DT_FMT) if p.departure_dt else "",
            "accommodation_requested": p.accommodation_requested or "",
            "tshirt_size": p.tshirt_size or "",
        }
        dict_rows.append(d)
    clusters = find_duplicate_clusters(dict_rows)

    id_by_raw = {p.raw_id: p for p in rows}
    linked = 0
    for cluster in clusters:
        parts = sorted(cluster, key=id_sort_key)
        canonical_raw, dup_raws = parts[0], parts[1:]
        canonical = id_by_raw[canonical_raw]
        if reporter is not None:
            reporter.add("participants.csv", canonical_raw, None, "warning",
                         "DUPLICATE_CLUSTER",
                         f"{len(cluster)} records form a duplicate cluster led by "
                         f"{canonical_raw}: {', '.join(cluster)} — linked via merged_into, "
                         f"reversible")
        for dup_raw in dup_raws:
            dup = id_by_raw[dup_raw]
            if dup.id == canonical.id or dup.merged_into == canonical.id:
                continue
            before = _snapshot(dup)
            dup.merged_into = canonical.id
            dup.status = C.DUPLICATE_STATUS
            flags = sorted(set((dup.quality_flags or []) + ["DUPLICATE_LINKED"]))
            dup.quality_flags = flags
            after = _snapshot(dup)
            audit.log_change(db, actor, "participant", dup.id, before, after,
                             f"duplicate of {canonical.raw_id}: same college, contingent, "
                             f"gender, age, accessibility, dietary, arrival, departure, "
                             f"accommodation and t-shirt (fuzzy name check); reversible "
                             f"via unmerge", kind="system")
            linked += 1
    return {"clusters": len(clusters), "duplicates_linked": linked}


# ------------------------------------------------------------------ funnel
def reconciliation(db: Session) -> dict:
    ps = db.query(Participant).all()
    total = len(ps)
    by_status: dict[str, list[str]] = {}
    for p in ps:
        by_status.setdefault(p.status, []).append(p.raw_id)
    duplicates = by_status.get(C.DUPLICATE_STATUS, [])
    quarantined = by_status.get(C.QUARANTINED_STATUS, [])
    flagged = by_status.get(C.FLAGGED_STATUS, [])
    cancelled_test_junk = [
        p.raw_id for p in ps
        if p.status == "cancelled" or "JUNK" in (p.quality_flags or [])
        or "TEST_ROW" in (p.quality_flags or [])
    ]
    active = [p.raw_id for p in ps if p.status == "active"]
    moths = {
        "raw_imported": {"count": total, "ids": []},
        "duplicates_merged": {"count": len(duplicates), "ids": duplicates},
        "quarantined": {"count": len(quarantined), "ids": quarantined},
        "cancelled_test_junk": {"count": len(cancelled_test_junk), "ids": cancelled_test_junk},
        "flagged": {"count": len(flagged), "ids": flagged},
        "active": {"count": len(active), "ids": []},
    }
    return {
        "raw_imported": total,
        "duplicates_merged": len(duplicates),
        "quarantined": len(quarantined),
        "cancelled_test_junk": len(cancelled_test_junk),
        "flagged": len(flagged),
        "active": len(active),
        "expected_participants": C.EXPECTED_PARTICIPANTS,
        "gap_vs_expected": len(active) - C.EXPECTED_PARTICIPANTS,
        "note": C.DEFAULT_CANCELLATION_RULE_NOTE,
        "detail": moths,
    }


# ------------------------------------------------------------------ main runner
FILE_ORDER = ["venues.csv", "contingents.csv", "events.csv", "hostels.csv",
              "external_stays.csv", "vendors.csv", "core_team.csv"]

FILE_IMPORTERS = {
    "venues.csv": import_venues,
    "contingents.csv": import_contingents,
    "events.csv": import_events,
    "hostels.csv": import_hostels,
    "external_stays.csv": import_external_stays,
    "vendors.csv": import_vendors,
    "core_team.csv": import_core_team,
}


def run_import_all(db: Session, data_dir: Path | None = None,
                   actor: str = "importer") -> dict:
    """Full pipeline. Raises only if a required file is missing entirely."""
    data_dir = Path(data_dir or C.DATA_DIR)
    loaded: list[str] = []
    rows = {}

    def _load(name: str) -> pd.DataFrame | None:
        path = data_dir / name
        if not path.exists():
            reporter = Reporter(db)
            reporter.add(name, None, None, "error", "FILE_MISSING", f"{path} not found")
            return None
        return pd.read_csv(path, dtype=str, keep_default_na=False)

    reporter = Reporter(db)

    frames = {name: _load(name) for name in list(FILE_ORDER) + [
        "participants.csv", "registrations.csv", "inventory_logistics.csv",
        "inventory_merch.csv"]}

    # ingest
    for name in FILE_ORDER:
        frame = frames.get(name)
        if frame is None:
            continue
        loaded.append(name)
        rows[name] = FILE_IMPORTERS[name](db, frame, actor, reporter)["inserted"]

    if frames.get("participants.csv") is not None:
        loaded.append("participants.csv")
        rows["participants.csv"] = import_participants(db, frames["participants.csv"],
                                                       actor, reporter)["inserted"]
        link = link_duplicates(db, actor, reporter)
        rows["participants_duplicate_links"] = link["duplicates_linked"]
    if frames.get("registrations.csv") is not None:
        loaded.append("registrations.csv")
        rows["registrations.csv"] = import_registrations(db, frames["registrations.csv"],
                                                         actor, reporter)["inserted"]
    if frames.get("inventory_logistics.csv") is not None and \
            frames.get("inventory_merch.csv") is not None:
        loaded += ["inventory_logistics.csv", "inventory_merch.csv"]
        rows["inventory_*.csv"] = import_inventory(db, frames["inventory_logistics.csv"],
                                                   frames["inventory_merch.csv"],
                                                   actor, reporter)["inserted"]

    recon = reconciliation(db)
    db.commit()
    return {
        "run_ok": True,
        "files_loaded": loaded,
        "rows_imported": rows,
        "issues_by_code": reporter.counts,
        "reconciliation": recon,
    }

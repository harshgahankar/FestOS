from datetime import datetime, date, time, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class _Base:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class User(_Base, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Participant(_Base, Base):
    __tablename__ = "participants"
    source_file: Mapped[str] = mapped_column(String, default="participants.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String, index=True)   # csv participant_id
    raw_id: Mapped[str] = mapped_column(String, unique=True, index=True)       # csv participant_id
    name: Mapped[str] = mapped_column(String, index=True)
    college: Mapped[Optional[str]] = mapped_column(String, index=True)
    contingent_id: Mapped[Optional[str]] = mapped_column(String, index=True)   # csv Cxx
    contingent: Mapped[Optional[int]] = mapped_column(
        ForeignKey("contingents.id", name="fk_participants_contingent", use_alter=True),
        nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String)              # male/female/non_binary/unknown
    gender_as_given: Mapped[Optional[str]] = mapped_column(String)     # verbatim csv value
    age: Mapped[Optional[int]] = mapped_column(Integer)
    phone: Mapped[Optional[str]] = mapped_column(String)               # masked via reveal
    phone_normalized: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # not present in pack (A-17)
    arrival_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    departure_dt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    accommodation_requested: Mapped[Optional[str]] = mapped_column(String)  # yes/no/unknown
    housing_pref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    accessibility_status: Mapped[Optional[str]] = mapped_column(String)      # yes/no/unknown
    accessibility_details: Mapped[Optional[str]] = mapped_column(String)     # masked via reveal
    dietary_status: Mapped[Optional[str]] = mapped_column(String)            # known/unknown
    dietary_tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    medical_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # not in pack (A-18)
    tshirt_size: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")  # active/duplicate/cancelled/flagged/quarantined
    merged_into: Mapped[Optional[int]] = mapped_column(ForeignKey("participants.id"), nullable=True)
    quality_flags: Mapped[Optional[list]] = mapped_column(JSON, default=list)


class Contingent(_Base, Base):
    __tablename__ = "contingents"
    source_file: Mapped[str] = mapped_column(String, default="contingents.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)     # csv contingent_id Cxx
    name: Mapped[str] = mapped_column(String)                    # college-based display name
    college: Mapped[str] = mapped_column(String)
    leader_name: Mapped[Optional[str]] = mapped_column(String)   # csv free text (A-19)
    leader_participant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("participants.id"), nullable=True)
    escort_name: Mapped[Optional[str]] = mapped_column(String)
    escort_count: Mapped[int] = mapped_column(Integer, default=1)
    size_declared: Mapped[Optional[int]] = mapped_column(Integer)
    size_actual: Mapped[Optional[int]] = mapped_column(Integer)
    arrival_window: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # derived window
    preferences: Mapped[Optional[list]] = mapped_column(JSON, default=list)      # parsed hints
    preferences_raw: Mapped[Optional[str]] = mapped_column(String)
    budget: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # not in pack


class Registration(_Base, Base):
    __tablename__ = "registrations"
    source_file: Mapped[str] = mapped_column(String, default="registrations.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)   # "registrations.csv#r0003"
    participant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("participants.id"))
    participant_raw_id: Mapped[Optional[str]] = mapped_column(String, index=True)  # csv P#### 
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"))
    event_raw_id: Mapped[Optional[str]] = mapped_column(String, index=True)        # csv Exx
    role: Mapped[Optional[str]] = mapped_column(String)   # solo/member (captain unknown, A-10)
    team_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # csv raw, unreliable (A-10)
    status: Mapped[str] = mapped_column(String, default="registered")  # registered/quarantined/cancelled


class Team(_Base, Base):
    __tablename__ = "teams"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    name: Mapped[Optional[str]] = mapped_column(String)
    contingent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contingents.id"))
    # NOTE: empty for the demo pack; memberships not derivable from registrations (A-10)


class Event(_Base, Base):
    __tablename__ = "events"
    source_file: Mapped[str] = mapped_column(String, default="events.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv event_id Exx
    name: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[Optional[str]] = mapped_column(String)           # solo/team
    rounds: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # parsed from "prelims|semis|finals"
    rounds_raw: Mapped[Optional[str]] = mapped_column(String)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    venue_id: Mapped[Optional[int]] = mapped_column(ForeignKey("venues.id"), nullable=True)  # not in pack (A-11)
    start_dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # operator entered
    end_dt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    setup_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)       # not in pack (A-11)
    teardown_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)        # not in pack (A-11)
    venue_requirements: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    equipment_needs: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    judges_needed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # not in pack (A-11)
    volunteers_needed: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="planned")


class EventStaff(_Base, Base):
    __tablename__ = "event_staff"
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    core_team_id: Mapped[int] = mapped_column(ForeignKey("core_team.id"))
    role: Mapped[Optional[str]] = mapped_column(String)  # judge/volunteer/coordinator


class Venue(_Base, Base):
    __tablename__ = "venues"
    source_file: Mapped[str] = mapped_column(String, default="venues.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv venue_id Vxx
    name: Mapped[str] = mapped_column(String, index=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    availability_windows: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # parsed windows
    windows_raw: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    location: Mapped[Optional[str]] = mapped_column(String)       # indoor/outdoor keyword


class HostelRoom(_Base, Base):
    __tablename__ = "hostel_rooms"
    source_file: Mapped[str] = mapped_column(String, default="hostels.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv room_id e.g. B1-0-01
    hostel: Mapped[Optional[str]] = mapped_column(String, index=True)   # block
    floor: Mapped[Optional[int]] = mapped_column(Integer)
    room_no: Mapped[Optional[str]] = mapped_column(String)
    beds: Mapped[Optional[int]] = mapped_column(Integer)          # csv capacity
    accessible: Mapped[bool] = mapped_column(Boolean, default=False)
    gender_block: Mapped[Optional[str]] = mapped_column(String)   # csv gender boys/girls
    readiness: Mapped[str] = mapped_column(String, default="ready")   # not in pack (A-15)
    cleaning_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")


class ExternalStay(_Base, Base):
    __tablename__ = "external_stays"
    source_file: Mapped[str] = mapped_column(String, default="external_stays.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv property_id
    property: Mapped[str] = mapped_column(String)
    beds: Mapped[Optional[int]] = mapped_column(Integer)
    cost_per_bed_night: Mapped[Optional[int]] = mapped_column(Integer)
    distance_km: Mapped[Optional[float]] = mapped_column(Float)
    travel_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # not in pack (A-14)
    transport_available: Mapped[Optional[str]] = mapped_column(String)  # yes/limited/unknown (A-23)
    safety_coverage: Mapped[Optional[str]] = mapped_column(String, default="unknown")  # not in pack
    status: Mapped[str] = mapped_column(String, default="open")


class Allocation(_Base, Base):
    __tablename__ = "allocations"
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hostel_rooms.id"), nullable=True)
    external_stay_id: Mapped[Optional[int]] = mapped_column(ForeignKey("external_stays.id"), nullable=True)
    check_in: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    check_out: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String)
    relaxed_constraints: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    cost: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("allocation_plans.id"), nullable=True)
    version: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    source: Mapped[Optional[str]] = mapped_column(String)  # engine/manual/override


class AllocationPlan(_Base, Base):
    __tablename__ = "allocation_plans"
    preset: Mapped[str] = mapped_column(String)
    created_by: Mapped[Optional[str]] = mapped_column(String)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    violations: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    relaxations: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    unplaced: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    total_cost: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft/active/superseded


class InventoryItem(_Base, Base):
    __tablename__ = "inventory_items"
    source_file: Mapped[Optional[str]] = mapped_column(String)
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    sku: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[Optional[str]] = mapped_column(String)   # logistics item type / merch item
    size: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # None when csv size == "NA"
    kind: Mapped[str] = mapped_column(String)                 # merch/logistics/equipment
    condition: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # logistics csv only


class InventoryMovement(_Base, Base):
    __tablename__ = "inventory_movements"                     # ledger; stock is derived
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    qty: Mapped[int] = mapped_column(Integer)
    from_location: Mapped[Optional[str]] = mapped_column(String)
    to_location: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[Optional[str]] = mapped_column(String)     # available/reserved/in_transit/damaged/awaiting_return
    at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    reference: Mapped[Optional[str]] = mapped_column(String)
    actor: Mapped[Optional[str]] = mapped_column(String)


class MerchIssue(_Base, Base):
    __tablename__ = "merch_issues"
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    canonical_participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    issued_by: Mapped[Optional[str]] = mapped_column(String)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class Vendor(_Base, Base):
    __tablename__ = "vendors"
    source_file: Mapped[str] = mapped_column(String, default="vendors.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv vendor_id VNDxx
    name: Mapped[str] = mapped_column(String, index=True)
    menu: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    dietary_coverage: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # csv dietary_options
    hygiene_cert_expiry: Mapped[Optional[date]] = mapped_column(Date)
    hours: Mapped[Optional[str]] = mapped_column(String)
    opens: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    closes: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    capacity_per_day: Mapped[Optional[int]] = mapped_column(Integer)
    rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)   # not in pack (A-13)
    payment_terms: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")  # active/interrupted/suspended


class VendorOrder(_Base, Base):
    __tablename__ = "vendor_orders"
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"))
    day: Mapped[Optional[date]] = mapped_column(Date)
    meal: Mapped[Optional[str]] = mapped_column(String)
    qty: Mapped[Optional[int]] = mapped_column(Integer)
    dietary_tag: Mapped[Optional[str]] = mapped_column(String)
    amount: Mapped[Optional[int]] = mapped_column(Integer)
    paid: Mapped[bool] = mapped_column(Boolean, default=False)


class CoreTeam(_Base, Base):
    __tablename__ = "core_team"
    source_file: Mapped[str] = mapped_column(String, default="core_team.csv")
    source_row_id: Mapped[Optional[str]] = mapped_column(String)
    raw_id: Mapped[str] = mapped_column(String, unique=True)      # csv member_id STxx
    name: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[Optional[str]] = mapped_column(String)           # csv role e.g. "Festival Director"
    shift_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    shift_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    shift_raw: Mapped[Optional[str]] = mapped_column(String)
    shift_crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)  # A-16
    skills: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # not in pack (A-16)
    contact: Mapped[Optional[str]] = mapped_column(String)


class AuditLog(_Base, Base):
    __tablename__ = "audit_log"                                  # append-only
    actor_id: Mapped[Optional[str]] = mapped_column(String, index=True)  # username
    action: Mapped[Optional[str]] = mapped_column(String)
    entity_type: Mapped[Optional[str]] = mapped_column(String, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    before: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String)
    kind: Mapped[Optional[str]] = mapped_column(String)          # manual/system/override/reveal
    at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        index=True)


class ImportIssue(_Base, Base):
    __tablename__ = "import_issues"
    file: Mapped[Optional[str]] = mapped_column(String, index=True)
    row: Mapped[Optional[str]] = mapped_column(String)           # source row id / "line N"
    field: Mapped[Optional[str]] = mapped_column(String)
    severity: Mapped[Optional[str]] = mapped_column(String, index=True)  # error/warning/info
    code: Mapped[Optional[str]] = mapped_column(String, index=True)
    message: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open/resolved/accepted
    resolution_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Assumption(_Base, Base):
    __tablename__ = "assumptions"
    code: Mapped[str] = mapped_column(String, unique=True, index=True)  # A-01 ...
    module: Mapped[Optional[str]] = mapped_column(String)
    text: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    created_by: Mapped[Optional[str]] = mapped_column(String)


class Disruption(_Base, Base):
    __tablename__ = "disruptions"
    type: Mapped[Optional[str]] = mapped_column(String, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    impact_report: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="previewed")  # previewed/applied/reverted
    applied_by: Mapped[Optional[str]] = mapped_column(String)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revert_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class ConfigRule(_Base, Base):
    __tablename__ = "config_rules"
    key: Mapped[str] = mapped_column(String, unique=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

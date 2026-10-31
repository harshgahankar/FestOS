from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class MeOut(BaseModel):
    username: str
    role: str


class FunnelStage(BaseModel):
    count: int
    ids: list[str] = Field(default_factory=list)


class ReconciliationOut(BaseModel):
    raw_imported: int
    duplicates_merged: int
    quarantined: int
    cancelled_test_junk: int
    flagged: int
    active: int
    expected_participants: int
    gap_vs_expected: int
    note: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ImportIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file: Optional[str]
    row: Optional[str]
    field: Optional[str]
    severity: Optional[str]
    code: Optional[str]
    message: Optional[str]
    status: str
    resolution_note: Optional[str]


class ImportReportOut(BaseModel):
    run_ok: bool
    files_loaded: list[str]
    rows_imported: dict[str, int]
    issues_by_code: dict[str, int]
    reconciliation: ReconciliationOut
    issues: list[ImportIssueOut] = Field(default_factory=list)


# ------------------------------------------------------------ participants P3 --
class RevealIn(BaseModel):
    fields: list[str]
    reason: str


class ParticipantPatchIn(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    tshirt_size: Optional[str] = None
    accessibility_details: Optional[str] = None
    dietary_tags: Optional[list[str]] = None
    accommodation_requested: Optional[str] = None
    note: Optional[str] = None


class MergeIn(BaseModel):
    canonical_id: Optional[int] = None
    canonical_raw_id: Optional[str] = None
    duplicate_id: Optional[int] = None
    duplicate_raw_id: Optional[str] = None
    reason: str


class MergeOut(BaseModel):
    canonical: dict[str, Any]
    duplicate: dict[str, Any]
    audit_id: int


class ReasonIn(BaseModel):
    reason: str


# ------------------------------------------------------------- accommodation --
class AllocateIn(BaseModel):
    preset: str = "balanced"               # min_cost | max_cohesion | balanced
    reason: Optional[str] = None


class AssignIn(BaseModel):
    participant_id: int
    room_id: Optional[int] = None
    external_stay_id: Optional[int] = None
    reason: Optional[str] = None


class EventEditIn(BaseModel):
    name: Optional[str] = None
    venue_id: Optional[int] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    duration_minutes: Optional[int] = None
    setup_min: Optional[int] = None
    teardown_min: Optional[int] = None
    volunteers_needed: Optional[int] = None
    equipment_needs: Optional[list[dict]] = None
    reason: str


class ScheduleMoveIn(BaseModel):
    event_raw_id: str
    venue_id: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None


class InventoryMoveIn(BaseModel):
    item_id: int
    qty: int
    to_location: Optional[str] = None
    status: Optional[str] = None
    reference: Optional[str] = None


class MerchIssueIn(BaseModel):
    participant_raw_id: str
    item_id: Optional[int] = None
    force: bool = False
    reason: str


class VendorRateIn(BaseModel):
    rate: int
    reason: str


class VendorInterruptIn(BaseModel):
    reason: str


# ---------------------------------------------------------------- disruptions --
class DisruptionIn(BaseModel):
    type: str
    payload: dict[str, Any]
    return_details: bool = False
    reason: Optional[str] = None


# ---------------------------------------------------------------- GeoCommand --
class MapLinkIn(BaseModel):
    entity_type: str
    entity_id: str


class MapLocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location_type: str
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    campus_zone: Optional[str] = Field(default=None, max_length=120)
    parent_location_id: Optional[int] = None
    source_reference: Optional[str] = Field(default=None, max_length=500)
    links: list[MapLinkIn] = Field(default_factory=list)
    reason: Optional[str] = None


class MapLocationPatchIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    location_type: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    campus_zone: Optional[str] = Field(default=None, max_length=120)
    parent_location_id: Optional[int] = None
    source_reference: Optional[str] = Field(default=None, max_length=500)
    links: Optional[list[MapLinkIn]] = None
    reason: Optional[str] = None


class MapSettingsIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    zoom: int = Field(default=16, ge=1, le=20)
    label: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = None


class MapDutyIn(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    location_id: int
    task_type: str = "task"
    label: Optional[str] = Field(default=None, max_length=200)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class MapGeocodeIn(BaseModel):
    query: str = Field(min_length=1, max_length=300)

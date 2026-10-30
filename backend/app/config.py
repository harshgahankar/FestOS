# FestOS configuration: thresholds, rules, weights. Nothing hard-coded in logic.
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent          # backend/app
BACKEND_DIR = BASE_DIR.parent                        # backend/
REPO_ROOT = BACKEND_DIR.parent                       # repo root
DATA_DIR = REPO_ROOT / "dataset"                     # real location of the CSV pack

# --- auth (Supabase, with local JWT fallback for offline dev/tests) -----------
def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (KEY=VALUE lines). Skipped when FESTOS_LOAD_DOTENV=0."""
    if os.getenv("FESTOS_LOAD_DOTENV", "1") != "1" or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(BACKEND_DIR / ".env")

# Fest tables live in local SQLite by default; set SUPABASE_DB_URL (Postgres
# pooler URI from Project Settings -> Database -> Connection string) to store
# them in the Supabase Postgres project instead. Tests always stay on SQLite.
DB_PATH = BACKEND_DIR / "festos.db"
DB_URL = (os.getenv("SUPABASE_DB_URL")
          or os.getenv("FESTOS_DB_URL")
          or os.getenv("DATABASE_URL")
          or f"sqlite:///{DB_PATH}")
if DB_URL.startswith("postgre"):
    DB_URL = DB_URL.replace("postgres://", "postgresql+psycopg2://", 1) \
        .replace("postgresql://", "postgresql+psycopg2://", 1)

DEMO_PASSWORDS = {
    "director": "director123",
    "accommodation_lead": "accom123",
    "events_lead": "events123",
    "logistics_lead": "logi123",
    "vendor_lead": "vendor123",
    "volunteer": "vol123",
    "viewer": "view123",
}

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "") or None

# supabase when configured; 'local' keeps the seeded passlib JWT mode for tests /
# offline demos (no network needed).
AUTH_MODE = "supabase" if (SUPABASE_URL and SUPABASE_ANON_KEY) else "local"

# Supabase login accepts either the email or the bare role name ('director').
DEMO_USER_EMAILS = {r: f"{r}@festos.local" for r in DEMO_PASSWORDS}
SUPABASE_TOKEN_CACHE_TTL = 300          # seconds for /auth/v1/user introspection
HTTP_TIMEOUT_S = 10

# --- security / auth ---------------------------------------------------------
SECRET_KEY = "dev-secret-festos-epinoia-2026-rotate-via-env-in-real-ops"  # local mode
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

ROLES = tuple(DEMO_PASSWORDS.keys())
# role -> capabilities used by require_permission (kept minimal in phases 0-2)
ROLE_PERMS = {
    "director": {"*"},
    "accommodation_lead": {"view_participants", "reveal_room_accessibility", "run_allocation",
                           "high_risk_override", "import_run"},
    "events_lead": {"view_participants", "edit_events", "import_run"},
    "logistics_lead": {"view_participants", "inventory_movements", "merch_issue", "import_run"},
    "vendor_lead": {"view_participants", "vendor_actions", "import_run"},
    "volunteer": {"view_participants", "merch_issue"},
    "viewer": {"view_participants"},
}

# ----------------------------------------------------------- masking (P3) ----
MASK_TEXT = "masked"
# role -> sensitive fields visible without a reveal call; everything else returns
# the MASK_TEXT placeholder. 'room' refers to assigned accommodation.
ROLE_FIELD_ACCESS = {
    "director": {"phone", "email", "medical_notes", "accessibility_details",
                 "dietary_tags", "room"},
    "accommodation_lead": {"accessibility_details", "dietary_tags", "room"},
    "events_lead": {"dietary_tags"},
    "vendor_lead": {"dietary_tags"},
    "logistics_lead": {"dietary_tags"},
    "volunteer": {"dietary_tags"},
    "viewer": set(),
}
# every field that participates in masking (interior set of all visible values)
MASKED_SENSITIVE_FIELDS = sorted(set().union(*ROLE_FIELD_ACCESS.values()) | {"room"})

# --- importer: schema definitions (REAL columns from the pack) ---------------
CSV_SCHEMAS = {
    "participants.csv": {
        "key": "participant_id",
        "cols": ["participant_id", "name", "college", "contingent_id", "gender_as_given",
                 "age", "contact", "accessibility_needs", "dietary_needs",
                 "arrival_datetime", "departure_datetime", "accommodation_requested",
                 "tshirt_size"],
    },
    "contingents.csv": {
        "key": "contingent_id",
        "cols": ["contingent_id", "college", "leader", "escort", "strength_declared",
                 "preferences"],
    },
    "registrations.csv": {
        "key": None,
        "cols": ["participant_id", "event_id", "team_id"],
    },
    "events.csv": {
        "key": "event_id",
        "cols": ["event_id", "event_name", "type", "rounds", "duration_minutes",
                 "venue_requirements", "equipment_needs", "volunteers_needed"],
    },
    "venues.csv": {
        "key": "venue_id",
        "cols": ["venue_id", "venue_name", "capacity", "availability_windows",
                 "indoor_outdoor"],
    },
    "hostels.csv": {
        "key": "room_id",
        "cols": ["room_id", "block", "floor", "gender", "capacity", "accessibility",
                 "status"],
    },
    "external_stays.csv": {
        "key": "property_id",
        "cols": ["property_id", "property_name", "beds", "cost_per_bed_per_night",
                 "distance_km", "transport_availability"],
    },
    "inventory_logistics.csv": {
        "key": "item_id",
        "cols": ["item_id", "item", "quantity", "location", "condition"],
    },
    "inventory_merch.csv": {
        "key": None,
        "cols": ["item", "size", "quantity", "reserved_quantity"],
    },
    "vendors.csv": {
        "key": "vendor_id",
        "cols": ["vendor_id", "vendor_name", "menu", "dietary_options",
                 "hygiene_certificate_expiry", "hours", "capacity", "payment_terms"],
    },
    "core_team.csv": {
        "key": "member_id",
        "cols": ["member_id", "name", "role", "shift", "phone"],
    },
}

# --- importer: validation rules ----------------------------------------------
UNKNOWN_TOKEN = "unknown"
THREE_STATE = "three_state"          # yes / no / unknown
GENDER_TOKENS = {"male", "female", "non_binary", UNKNOWN_TOKEN}

GENDER_AS_GIVEN_MAP = {
    "Male": "male",
    "Female": "female",
    "Non-binary": "non_binary",
    "Prefer not to say": UNKNOWN_TOKEN,   # kept verbatim in gender_as_given; logic reads lossy value
    "": UNKNOWN_TOKEN,
}

ACCESSIBILITY_NONE_LITERAL = "None"    # explicit declaration in data; blank would NOT mean this

AGE_MIN, AGE_MAX = 10, 80             # only true parse failures quarantine; out-of-range flags

FEST_DAYS = {                          # used for arrival-window flags
    "start": "2026-10-30",
    "end": "2026-11-01",
}
ARRIVAL_WINDOW_START = "2026-10-29 00:00"
ARRIVAL_WINDOW_END = "2026-11-03 23:59"

EXPECTED_PARTICIPANTS = 2400
EXPECTED_CONTINGENTS = 38
EXPECTED_EVENTS = 31
EXPECTED_VENUES = 9
EXPECTED_VENDORS = 14
EXPECTED_CORE_TEAM = 48
EXPECTED_HOSTEL_BEDS = 710

# duplicate detection
DUP_NAME_FUZZ_THRESHOLD = 88.0         # rapidfuzz token_sort_ratio for the fuzzy stage
DUP_FLAGS_CORROBORATION_FIELDS = ("college", "contingent_id", "gender_as_given", "age",
                                  "accessibility_needs", "dietary_needs", "arrival_datetime",
                                  "departure_datetime", "accommodation_requested", "tshirt_size")
DUPLICATE_STATUS = "duplicate"
FLAGGED_STATUS = "flagged"
QUARANTINED_STATUS = "quarantined"
JUNK_PHONE_PATTERNS = ("8888888888", "98765 43210")  # observed fake-contact examples
SUSPECT_PHONE_RULES = [
    ("all_same_digit", r"^\+91-(\d)\1{9}$"),
    ("non_standard_format", r"^(?!\+91-\d{10}$).+$"),
]

# external stays: distance -> travel minutes estimate (engine facing, tunable)
TRAVEL_MINUTES_PER_KM = 3.0

# reconciliation note text
DEFAULT_CANCELLATION_RULE_NOTE = (
    "The pack has no cancellation/test/junk marker; those funnel stages are 0. "
    "Cancellations must be marked explicitly with a reason (audited), never inferred."
)

# ----------------------------------------------------------- scheduling rules --
SCHEDULER = {
    "SETUP_MIN_DEFAULT": 30,          # A-11: events carry no setup/teardown in the pack
    "TEARDOWN_MIN_DEFAULT": 15,
    "TRAVEL_BUFFER_MIN": 10,          # min gap when consecutive events change venue
    "BUSY_GAP_MIN": 0,                # granularity for overlap checks
    "VOLUNTEER_MAX_EVENTS_PER_DAY": 3,
    "JUDGE_MAX_EVENTS_PER_DAY": 2,
}

# ------------------------------------------------------------ inventory rules --
INVENTORY = {
    "MERCH_ISSUE_STATUSES": ("available",),
}

# -------------------------------------------------------------- vendor rules --
VENDORS = {
    "DIET_TAGS": ("vegetarian", "non-vegetarian", "halal", "nut allergy",
                  "gluten-free", "vegan", "jain"),
    "PARTICIPANT_TAG_MAP": {          # csv dietary_needs -> canonical tag
        "Vegetarian": "vegetarian",
        "Non-vegetarian": "non-vegetarian",
        "Halal": "halal",
        "Nut allergy": "nut allergy",
        "Gluten-free": "gluten-free",
        "Jain": "jain",
    },
    "MEALS_PER_DAY": 2,               # per on-site participant per day (coverage unit)
}

# ------------------------------------------------------------ allocation rules --
ALLOC_HARD_CONSTRAINTS = ("ACCESSIBILITY", "PRIVACY", "GENDER_SEGREGATION",
                          "CAPACITY", "READINESS", "WINDOWS")
ALLOC_GROUND_FLOOR_TOKENS = ("Ground floor / no stairs", "Near washroom",
                             "Wheelchair access")
ALLOC_ACCESSIBLE_ROOM_TOKENS = ("Visual assistance", "Wheelchair access")
ALLOC_REVIEW_GENDERS = ("non_binary", "unknown")   # never forced into boys/girls
ALLOC_HOSTEL_COST_PER_BED_NIGHT = 0                # on-campus beds are free
ALLOC_MIN_NIGHTS = 1
ALLOC_REVIEW_REASONS = {
    "UNCLEAR_GENDER": "gender is non_binary/unknown/prefer-not-to-say; housing needs a "
                      "human decision, never a forced binary (spec feature 24)",
    "UNCLEAR_ACCOMMODATION": "accommodation_requested is unknown (blank); consent to "
                             "housing never inferred",
}
ALLOC_PRESETS = {
    "min_cost": {"external_order": "cost", "prefer_same_floor": False, "house_together": False},
    "max_cohesion": {"external_order": "capacity_then_cost", "prefer_same_floor": True,
                     "house_together": True},
    "balanced": {"external_order": "cost", "prefer_same_floor": True, "house_together": True},
}

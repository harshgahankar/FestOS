"""FestOS demo rebuild: wipe DB, seed users + assumptions + config, run importer.

Usage:  python seed.py   (from backend/)
Idempotent: every run produces the same fresh, deterministic demo state.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent          # backend/
sys.path.insert(0, str(BASE))

from app import audit, config as C              # noqa: E402
from app.db import Base, session_scope  # noqa: E402
from app.models import (Assumption, ConfigRule, Participant, Registration,  # noqa: E402
                        User)
from app.auth import hash_password             # noqa: E402
from engines.importer import run_import_all    # noqa: E402

DOCS = BASE.parent / "docs"
ASSUMPTIONS_MD = DOCS / "ASSUMPTIONS.md"


def _utcnow():
    from datetime import timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _supabase_provision_users() -> list[str]:
    """Create the 7 demo users in Supabase (server-side, requires service key).

    Idempotent: existing emails are left untouched (with the role ensured in metadata).
    Returns the log lines for inspection; failures never block seeding.
    """
    import httpx
    from app import config as C

    notes = []
    if not C.SUPABASE_SERVICE_ROLE_KEY:
        return ["[auth] supabase service key missing; skipping dashboard provisioning"]
    headers = {"apikey": C.SUPABASE_SERVICE_ROLE_KEY,
               "Authorization": f"Bearer {C.SUPABASE_SERVICE_ROLE_KEY}",
               "Content-Type": "application/json"}
    with httpx.Client(timeout=C.HTTP_TIMEOUT_S * 2) as client:
        listed = client.get(f"{C.SUPABASE_URL}/auth/v1/admin/users?per_page=100",
                            headers=headers)
        existing = {}
        if listed.status_code == 200:
            for u in listed.json().get("users") or []:
                existing[u.get("email", "").lower()] = u
        else:
            notes.append(f"[auth] supabase user list failed ({listed.status_code}); "
                         f"provisioning continues")
        for role, password in C.DEMO_PASSWORDS.items():
            email = C.DEMO_USER_EMAILS[role]
            if email in existing:
                notes.append(f"[auth] exists {email}")
                continue
            r = client.post(f"{C.SUPABASE_URL}/auth/v1/admin/users", headers=headers,
                            json={"email": email, "password": password,
                                  "email_confirm": True,
                                  "user_metadata": {"role": role, "festos_user": True}})
            notes.append(f"[auth] create {email} -> {r.status_code}"
                         + ("" if r.status_code in (200, 201)
                            else f" {r.json().get('msg', '')}"))
    return notes


def create_users(db) -> list[User]:
    users = []
    for role, password in C.DEMO_PASSWORDS.items():
        existing = db.query(User).filter(User.username == role).first()
        if existing:
            if C.AUTH_MODE == "local":
                existing.password_hash = hash_password(password)
            users.append(existing)
            continue
        u = User(username=role,
                 password_hash=hash_password(password) if C.AUTH_MODE == "local" else "",
                 role=role, active=True)
        db.add(u)
        users.append(u)
    audit.log_change(db, "seed", "user", "7 roles", None,
                     {"usernames": [u.username for u in users],
                      "auth_mode": C.AUTH_MODE},
                     "seeded demo identities (credentials documented in README)",
                     kind="system")
    if C.AUTH_MODE == "supabase":
        print("\n".join(_supabase_provision_users()))
    return users


def _parse_assumptions(path: Path) -> list[tuple[str, str, str]]:
    """Parse '## A-01 — Module — summary' head + body -> (code, module, text)."""
    items = []
    current = None
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (A-\d+) — (.+?) — (.+)$", line)
        if m:
            current = [m.group(1), m.group(2), m.group(3) + "\n"]
            items.append(current)
        elif current is not None and line.strip() and not line.startswith("#"):
            current[2] += line.strip() + "\n"
    return [(c, mod, txt.strip()) for c, mod, txt in items]


def seed_assumptions(db) -> int:
    db.query(Assumption).delete(synchronize_session=False)
    items = _parse_assumptions(ASSUMPTIONS_MD)
    for code, module, text in items:
        db.add(Assumption(code=code, module=module, text=text, status="open",
                          created_by="seed"))
    db.flush()
    return len(items)


def seed_config_rules(db) -> int:
    rules = [
        ("DUP_NAME_FUZZ_THRESHOLD", {"value": C.DUP_NAME_FUZZ_THRESHOLD},
         "rapidfuzz token_sort_ratio threshold for fuzzy participant dedupe"),
        ("EXPECTED_PARTICIPANTS", {"value": C.EXPECTED_PARTICIPANTS},
         "reconciliation target"),
        ("EXPECTED_HOSTEL_BEDS", {"value": C.EXPECTED_HOSTEL_BEDS}, "bed checksum"),
        ("TRAVEL_MINUTES_PER_KM", {"value": C.TRAVEL_MINUTES_PER_KM},
         "estimated distance-to-minutes factor for external stays"),
        ("AGE_BOUNDS", {"min": C.AGE_MIN, "max": C.AGE_MAX},
         "participants outside this range are flagged, not dropped"),
    ]
    db.query(ConfigRule).delete(synchronize_session=False)
    for k, v, d in rules:
        db.add(ConfigRule(key=k, value=v, description=d))
    db.flush()
    return len(rules)


def rebuild_demo(db, *, verbose: bool = True, data_dir: Path | None = None) -> dict:
    """Wipe + reseed everything, bound to the session's engine. Deterministic."""
    wipe_started = _utcnow()
    bind = db.get_bind()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)

    users = create_users(db)
    n_assumps = seed_assumptions(db)
    n_rules = seed_config_rules(db)
    report = run_import_all(db, data_dir or C.DATA_DIR, actor="seed")
    db.commit()

    if verbose:
        recon = report["reconciliation"]
        print(f"[seed] users: {len(users)} roles, assumptions: {n_assumps}, "
              f"config rules: {n_rules}")
        print(f"[seed] files: {len(report['files_loaded'])}")
        for f, n in report["rows_imported"].items():
            print(f"[seed]   {f}: {n}")
        print(f"[seed] reconciliation: "
              f"raw={recon['raw_imported']} dup={recon['duplicates_merged']} "
              f"quar={recon['quarantined']} junk={recon['cancelled_test_junk']} "
              f"flag={recon['flagged']} active={recon['active']} "
              f"(expected {recon['expected_participants']}, gap "
              f"{recon['gap_vs_expected']:+d})")
        codes = report["issues_by_code"]
        print(f"[seed] import issues: {sum(codes.values())} rows, "
              f"codes: {dict(sorted(codes.items()))}")
        parts = db.query(Participant).count()
        regs = db.query(Registration).count()
        print(f"[seed] db: participants={parts} registrations={regs} "
              f"({(_utcnow() - wipe_started).total_seconds():.1f}s)")
    return report


def main() -> None:
    with session_scope() as db:
        rebuild_demo(db, verbose=True)


if __name__ == "__main__":
    main()

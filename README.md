# FestOS — Epinoia 2026 backend

Internal control portal for the Aarohan inter-college fest (spec: `docs/BACKEND_SPEC.pdf`,
assumptions & data findings: `docs/ASSUMPTIONS.md`). Phases 0–6 complete:
skeleton, models/audit/auth, import & reconciliation, participants/contingents
(masking + reveal), the four pure engines (scheduler, inventory/merch,
vendors, accommodation allocator) behind audited API endpoints, the disruption
engine (preview/apply/revert), and the control center (attention queue, KPIs,
audit browser).

## Quick start

```
cd backend
python -m pip install -r requirements.txt
python seed.py            # wipes DB, imports CSVs from ../dataset, seeds users
python -m uvicorn app.main:app --reload
```

Open http://localhost:8000/docs — health at `/health`.

By default the data lives in a local SQLite file (`backend/festos.db`). Setting
`SUPABASE_DB_URL` in `backend/.env` (Postgres pooler URI, session pooler port
5432) stores all tables in the Supabase Postgres project instead, so they are
visible in the Supabase Table Editor; `seed.py` then creates + fills them there.
Tests always run against an isolated in-memory SQLite regardless of `.env`.
Note: seed over the remote pooler takes a few minutes (the importer batches
writes per file — one roundtrip per phase, not per row).

## Auth

Two modes (A-27):

- **Supabase (default when `backend/.env` has `SUPABASE_URL` + keys)**: demo users
  are provisioned in Supabase Auth by `seed.py` as `{role}@festos.local` with the
  role stored in `user_metadata.role`. Login accepts the bare role name or the
  email; tokens are verified via introspection (or HS256 locally if a JWT secret
  is configured).
- **Local JWT (offline/tests)**: same credentials, hashed with bcrypt by the app.

## Test credentials (demo passwords, username = role, email = `{role}@festos.local`)

| Username | Password |
|---|---|
| director | director123 |
| accommodation_lead | accom123 |
| events_lead | events123 |
| logistics_lead | logi123 |
| vendor_lead | vendor123 |
| volunteer | vol123 |
| viewer | view123 |

## Tests

```
cd backend
python -m pytest tests -q
```

## Endpoints

- `/health`
- `POST /auth/login`, `GET /auth/me`, `GET /auth/admin-only` (role-gate demo)
- `POST /imports/upload` (run pipeline), `GET /imports/reconciliation`,
  `GET /imports/issues`, `POST /imports/reset` (director only)
- `GET /participants` (search/filter, role-masked), `GET /participants/{id}`
  (360° record), `POST /participants/{id}/reveal` (audited unmask),
  `PATCH /participants/{id}`, `POST /participants/merge`,
  `POST /participants/{id}/unmerge`, `GET /participants/duplicates`,
  `GET /participants/{id}/audit`
- `GET /contingents?mismatched=true`, `GET /contingents/{id}`
- `POST /accommodation/allocate` (presets: `min_cost`, `max_cohesion`,
  `balanced`), `POST /accommodation/plan/{id}/activate`, `.../lock`,
  `POST /accommodation/assign` (audited override), `GET /accommodation/shortage`,
  `GET /accommodation/review-queue`, `GET /accommodation/explain/{pid}`
- `GET /schedule/events`, `PATCH /schedule/events/{id}` (operator scheduling,
  A-11), `POST /schedule/move`, `GET /schedule/conflicts`
- `GET /inventory/levels`, `POST /inventory/movements`,
  `GET /merch/shortfall`, `POST /merch/issue` (issue-once per dup cluster,
  `force` = director only)
- `GET /vendors`, `GET /vendors/compliance`, `GET /vendors/coverage`,
  `PATCH /vendors/{id}/rate`, `POST /vendors/{id}/interrupt/preview` +
  `.../apply`, `GET /vendors/settlement`
- Disruptions (director only, every step audited): `POST /disruptions/preview`,
  `POST /disruptions/{id}/apply`, `POST /disruptions/{id}/revert` (full revert
  snapshot, never guesses), `GET /disruptions`. Types: `late_contingent`,
  `duplicate_record`, `hostel_closure`, `equipment_failure`, `venue_change`,
  `vendor_shutdown`, `duplicate_merch_claim` (A-34).
- Control center (director only): `GET /control/attention` (merged findings
  inbox, severity-sorted), `GET /control/kpis` (occupancy is null until a plan
  is active), `GET /control/audit` (filterable audit browser, A-35).
- **FestOS AI Operations Assistant** ("Ask your festival operations data"):
  `GET /chatbot/health` (status & provider capabilities), `POST /chatbot/chat`
  (grounded natural-language operations query), `GET /chatbot/conversations`
  (authorized user history), `GET /chatbot/conversations/{id}` (conversation detail),
  `POST /chatbot/reindex` (refresh semantic vectors, director only). Complete spec:
  `docs/CHATBOT_ARCHITECTURE.md`.

## Known limitations

- Events carry no venues/times in the data pack; the scheduler needs
  operator-entered slots (A-11).
- Registrations' `team_id` is unreliable: blank on all team-event rows and
  populated on solo rows (A-10); the `teams` table stays empty.
- Vendor settlement needs manual rate capture — the pack has no rate column (A-13).
- Reconciliation is 2,836 → 2,831 active vs ~2,400 expected; the +431 gap is
  surfaced, not hidden (A-08).
- Engine purity: engines may touch SQLAlchemy sessions but never import FastAPI.

## Hard rules honoured

- No source row is ever deleted or silently corrected — quarantine/flag/link only.
- Blanks are `unknown`, never "no" (gender, dietary, accessibility, accommodation).
- Every write path calls `log_change()`; overrides need a reason.
- Names in this pack repeat heavily; dedupe is fingerprint+typosim based (A-05/A-06).

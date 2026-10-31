# FestOS — Epinoia 2026 backend

Internal control portal for the Aarohan inter-college fest (spec: `docs/BACKEND_SPEC.pdf`,
assumptions & data findings: `docs/ASSUMPTIONS.md`). Phases 0–6 complete:
skeleton, models/audit/auth, import & reconciliation, participants/contingents
(masking + reveal), the four pure engines (scheduler, inventory/merch,
vendors, accommodation allocator) behind audited API endpoints, the disruption
engine (preview/apply/revert), the control center (attention queue, KPIs,
audit browser), and GeoCommand — a role-scoped, database-backed operations map.

## Quick start

```
cd backend
python -m pip install -r requirements.txt
python seed.py            # wipes DB, imports CSVs from ../dataset, seeds users
python -m uvicorn app.main:app --reload

# in a second terminal — the browser UI (React/Vite)
cd ../frontend
npm install
npm run dev
```

Backend API docs: http://localhost:8000/docs — health at `/health`.
Frontend (FestOS UI): http://localhost:5173 — the vite dev proxy forwards
`/api/*` to the backend with no CORS setup needed.

### Browser UI walkthrough

The UI is a role-scoped control portal: **Command Center** (KPIs, attention
inbox, top-right **Upload CSV** button), **Participants / Accommodation /
Events & Venues / Logistics & Merch / Food Vendors**, and for the director:
**Disruption Desk, Team & Access, Audit & Decisions**, plus the floating
**FestOS AI** chatbot on every page.

## CSV data flow (papers not needed on demo day)

- `dataset/` is the data pack; the importer runs against it directly and is
  idempotent (upserts).
- **From the browser**: Command Center → **Upload CSV** accepts the data-pack
  CSVs (`multipart /imports/upload`) *and* judge disruption-scenario CSVs,
  which are auto-detected (presence of a `disruption_type` column) and routed
  to `POST /disruptions/scenario-pack` — every row becomes an impact-previewed
  ticket in the Disruption Desk, ready to apply.
- A ready-made 9-scenario live-test pack covering all seven disruption types
  sits at `judge_disruption_live_test.csv` (repo root); its T005 venue-change
  precondition needs one event scheduled on venue V01 (E01 was staged on it).
- `POST /imports/upload` without files re-runs the pipeline server-side from
  `dataset/`; `POST /imports/reset` (director) is the audited full rebuild.

By default the data lives in a local SQLite file (`backend/festos.db`). Setting
`SUPABASE_DB_URL` in `backend/.env` (Postgres pooler URI, session pooler port
5432) stores all tables in the Supabase Postgres project instead, so they are
visible in the Supabase Table Editor; `seed.py` then creates + fills them there.
Tests always run against an isolated in-memory SQLite regardless of `.env`.
Note: seed over the remote pooler takes a few minutes (the importer batches
writes per file — one roundtrip per phase, not per row).

### Frontend (including GeoCommand)

```
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to :8000
npm run build    # typecheck + production bundle
```

The operations map lives at `/map` for every signed-in role. It uses
OpenStreetMap tiles; address search optionally proxies Nominatim
(`FESTOS_GEOCODING_ENABLED=false` disables it, `FESTOS_NOMINATIM_URL` overrides
the provider). Set the site centre once as director via **GeoCommand → map
centre**; until then the map opens on a neutral country view.

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
- `POST /imports/upload` — multipart data-pack CSVs from the browser, or no
  files = re-run the pipeline against the server-side `dataset/` directory;
  `GET /imports/reconciliation`, `GET /imports/issues`, `POST /imports/reset`
  (director only)
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
  snapshot, never guesses), `GET /disruptions`, and
  `POST /disruptions/scenario-pack` — upload a judge scenario CSV; each row is
  mapped to an engine payload and auto-previewed into the registry. Types:
  `late_contingent`, `duplicate_record`, `hostel_closure`, `equipment_failure`,
  `venue_change`, `vendor_shutdown`, `duplicate_merch_claim` (A-34).
- Control center (director only): `GET /control/attention` (merged findings
  inbox, severity-sorted), `GET /control/kpis` (occupancy is null until a plan
  is active), `GET /control/audit` (filterable audit browser, A-35).
- GeoCommand map: `GET /map/locations`, `/locations/{id}`, `/summary`,
  `/accommodation`, `/events`, `/logistics`, `/vendors`, `/vendors/{id}`,
  `/incidents`, `/unmapped`, `/entities`, `/settings`, `/duties`;
  `POST /map/locations`, `/locations/{id}/verify`, `/duties`, `/geocode`;
  `PATCH /locations/{id}`, `/settings`; `DELETE /duties/{id}`. Geography is a
  nullable registry: no coordinate is inferred from the CSV pack, pins start
  `unverified`, and a lead's edit preserves links owned by other roles. Role
  visibility is enforced server-side (leads see their layer, volunteers only
  duty-linked pins, viewer venues only).
- **FestOS AI Operations Assistant** ("Ask your festival operations data"):
  `GET /chatbot/health` (status & provider capabilities), `POST /chatbot/chat`
  (grounded natural-language operations query), `GET /chatbot/conversations`
  (authorized user history), `GET /chatbot/conversations/{id}` (conversation
  detail), `POST /chatbot/reindex` (refresh semantic vectors, director only).
  Router notes: event-time questions are typo/name-tolerant — "what time is the
  MUN event" resolves to the scheduled DB fact rather than generic advice.
  Complete spec: `docs/CHATBOT_ARCHITECTURE.md`.

## Known limitations

- Events carry no venues/times in the data pack; the scheduler needs
  operator-entered slots (A-11).
- Registrations' `team_id` is unreliable: blank on all team-event rows and
  populated on solo rows (A-10); the `teams` table stays empty.
- Vendor settlement needs manual rate capture — the pack has no rate column (A-13).
- Reconciliation is 2,836 → 2,831 active vs ~2,400 expected; the +431 gap is
  surfaced, not hidden (A-08).
- Engine purity: engines may touch SQLAlchemy sessions but never import FastAPI.
- GeoCommand maps nothing until an organiser saves real coordinates; the picked
  or geocoded point stays unverified until confirmed on site. The dataset has no
  GPS, so an empty map is an honest result, not an error.

## Hard rules honoured

- No source row is ever deleted or silently corrected — quarantine/flag/link only.
- Blanks are `unknown`, never "no" (gender, dietary, accessibility, accommodation).
- Every write path calls `log_change()`; overrides need a reason.
- Names in this pack repeat heavily; dedupe is fingerprint+typosim based (A-05/A-06).

# FestOS — Assumptions Register

Source: profiling of every CSV in `dataset/` (row counts, null %, distinct values, ranges,
duplicate checks, cross-file integrity) performed before any code was written. No column
names are guessed; everything below uses the real headers found in the files.
Each item is also seeded into the `assumptions` table by `seed.py`.

> Summary: 11 CSVs, all fully populated except two blanks that must stay `unknown`.
> The pack has no "status", "email", "venue", "time" or "rate" columns for participants,
> events and vendors respectively. Verified counts: participants 2,836; colleges 38 (C01–C38);
> events 31; venues 9; hostels 200 rooms / 710 beds; external stays 6 properties / 740 beds;
> vendors 14; core team 48; registrations 5,580.

## A-01 — Import & reconciliation — Data lives in `dataset/`, not `data/`

The repo ships the raw pack in `dataset/`, while the spec refers to `data/`. `config.DATA_DIR`
points to `dataset/` (configurable). The CSVs are treated as immutable source data and are
never edited by the importer.

## A-02 — Import & reconciliation — Blank gender is `unknown`, "Prefer not to say" is kept

`participants.gender_as_given`: Female 831, Male 743, blank 417 (14.7%), "Prefer not to say" 430,
"Non-binary" 415. A blank is normalized to `unknown` — never "no" or "any". "Prefer not to say"
is preserved as its own declared value and treated as `unknown` for gender-segregation logic;
the raw string is kept in `gender_as_given`. No housing decisions may be inferred from it.

## A-03 — Import & reconciliation — `accessibility_needs = "None"` is an explicit "no", blanks would be `unknown`

`accessibility_needs` is fully populated (no blanks): "None" 2,321; "Ground floor / no stairs" 135;
"Visual assistance" 128; "Near washroom" 128; "Wheelchair access" 124. Because the literal
"None" was explicitly recorded (not a blank), `accessibility_status` = `no` only for it; any
blank future value maps to `unknown` and is honored as "need not yet cleared".

## A-04 — Import & reconciliation — Blank dietary needs stay `unknown`

`dietary_needs` has 394 blanks (13.9%): `dietary_status` = `unknown`, `dietary_tags` = [].
A blank is never "no dietary needs"; those participants still need verified clearance or
assumed-safe meals before food planning.

## A-05 — Import & reconciliation — Names are heavily reused; dedupe must not key on name

Only 191 distinct names cover 2,836 participants; e.g. "Raghav Joshi" appears 12× inside the
same contingent (C03). Naive name+college matching yields 364 clusters / ~2,460 false positives.
Phones are unique per row, so they cannot identify duplicates either. Duplicate detection is
therefore fingerprint-based: exact match on all non-ID fields (ignoring participant_id and
contact), plus a fuzzy-name pass (rapidfuzz) that additionally requires all other fields to match.

## A-06 — Import & reconciliation — The two injected duplicates and their canonical parents

`P_DUP01` ("Taanvi Daas", phone +91-8888888888) duplicates `P0021` ("Tanvi Das"): same college,
contingent, gender, age 25, accessibility, dietary, arrival 2026-10-31 22:00, departure
2026-11-02 22:00, accommodation yes, size M — only the name spelling and a fake phone differ.
`P_DUP02` ("Raghav Joshi", phone "98765 43210") duplicates `P0119` identically except a junk
phone format. Canonical = lowest numeric id; duplicates get status `duplicate` + `merged_into`,
which is reversible (`unmerge`).

## A-07 — Import & reconciliation — Three impossible-travel records are flagged, not dropped

P0037, P1189, P2034 arrive 2026-11-02 02:00 (after the fest ends 2026-11-01) and two of them
(P1189, P2034; P0037 as well) have `departure_datetime` before `arrival_datetime`. They are
imported with status `flagged` + quality flags `POST_FEST_ARRIVAL` / `DEPARTURE_BEFORE_ARRIVAL`
and stay visible in review queues. Nothing is deleted or auto-corrected.

## A-08 — Import & reconciliation — The pack contains no cancelled/test/junk markers

No status-like column exists in participants.csv, and only 2 junk-phone rows exist (counted as
duplicates in A-06). The funnel's cancelled/test/junk stage is therefore 0 for this pack and the
2,836 → 2,831 active count runs ~431 above the ~2,400 expected attendance. The gap is reported
explicitly by the reconciliation endpoint rather than hidden; if a contingency cancels, mark
participants (with a reason) rather than inferring cancellations from other fields.

## A-09 — Import & reconciliation — Contingent declared vs actual sizes differ in 7 contingents

`strength_declared` sums to 2,842 vs 2,836 imported; per-contingent deltas (actual − declared):
C02 +1, C03 +1, C09 +5, C27 +7, C05 −8, C18 −5, C32 −7; all others 0. Both numbers are stored
(`size_declared`, `size_actual`) and produce import issues (`CONTINGENT_SIZE_MISMATCH`);
mismatch direction can mean escorts joining or no-shows — needs contingent leader confirmation,
not guesswork.

## A-10 — Import & reconciliation — team_id is unreliable; teams stay undefined

`registrations.team_id` is blank on 100% of team-event registrations (1,810 rows) but populated
on 1,967 solo-event rows with pattern T{event#}-C{contingent#}-{n} (n up to 45, most "teams"
have size 1). Team membership cannot be derived from this pack: the `teams` table stays empty,
`team_id` is stored raw, and rows produce warning issues. Team scheduling/merch-cluster logic
will use participant duplicate links instead of team_id.

## A-11 — Import & reconciliation — Events carry no venue, no times, no capacity

`events.csv` columns are exactly: event_id, event_name, type (solo 21 / team 10), rounds
("prelims|semis|finals" ×24 / "single" ×7), duration_minutes (45–120), venue_requirements,
equipment_needs, volunteers_needed (2–12). There is no venue_id, start/end datetime, setup or
teardown. The scheduler must operate on operator-entered slots later (spec fields stay nullable);
the importer can only validate venue requirements against venue facilities once a schedule exists.

## A-12 — Import & reconciliation — Vendor hygiene certificates versus the fest window

`hygiene_certificate_expiry`: 2026-09-29 ×4 vendors (expired before the fest), 2026-10-31 ×4
(expires at midnight on fest day 2), 2026-11-10 ×1, 2027-10-29 ×5. Compliance classification:
`expired` if date < 2026-10-30, `expiring_mid_fest` if < 2026-11-01, else valid. Expired and
mid-fest-expiry vendors both produce issues; expiration blocks assignment until re-verified.

## A-13 — Import & reconciliation — No vendor rate column exists

vendors.csv has payment_terms ("50% advance; balance actuals" ×7, "minimum guarantee" ×4,
"per item sold" ×3) but no rate. `rate` stays nullable; settlement (rate × qty) requires
manual capture per order, recorded as an assumption for the vendor module.

## A-14 — Import & reconciliation — External stays: safety coverage unknown, distance not minutes

external_stays.csv: 6 properties, 740 beds total (120+120+180+140+100+80), cost 750–2,200
per bed-night, distance_km 1–9, transport_availability yes ×5 / limited ×1. There is no
safety_coverage column (→ `unknown`) and no travel_minutes; the distance→minutes conversion
factor lives in config and is only an estimate for engine use.

## A-15 — Import & reconciliation — Hostels map cleanly to the spec's room model

hostels.csv: 200 rooms (blocks B1/B2/B3/G1/G2 ×10 rooms ×4 floors), gender boys 120 / girls 80
rooms, capacity 2/3/4-bed rooms, accessibility "yes" on 10 rooms, all status "available".
Total beds 710 — exactly matching the spec's stated bed inventory, a good checksum. `readiness`
does not exist: all rooms are imported as `ready` with `cleaning_until` null (late cleaning
will be recorded at run time, not invented).

## A-16 — Import & reconciliation — Core-team shifts cross midnight

core_team.csv: 48 members, 8 roles × 6, shifts 06:00-14:00, 10:00-18:00, 14:00-22:00 and
22:00-06:00 (16 members). A shift whose end ≤ start is interpreted as ending the next day.
No skills column exists (`skills` stays empty/JSON []).

## A-17 — Import & reconciliation — Participants have no email; phones are the only contact

The pack has `contact` (a phone) but no email column, though the spec's participant model
includes email. `email` is imported as a nullable empty column; masking/réveal rules apply to
`phone` in the meantime.

## A-18 — Import & reconciliation — No medical_notes column exists in the pack

The spec's participants.medical_notes is absent from the data. The column exists in the model
and stays null; nothing may be inferred into it from dietary or accessibility fields.

## A-19 — Import & reconciliation — Contingent leaders/escorts are names, not participant ids

contingents.csv has `leader` and `escort` as free-text names. Given the name-reuse problem
(A-05), leader→participant resolution is only attempted when exactly one active participant in
that contingent matches; otherwise `leader_participant_id` stays null and an info issue is
written. Escort count is 1 per contingent (only one escort name is provided).

## A-20 — Import & reconciliation — Contingent preferences map to hints, not constraints

`preferences` values: "low cost" (9), "keep together; near venue" (9), "no preference" (8),
"quiet rooms" (6), "ground floor if possible" (6), "same floor" (3). These are treated as
soft preferences. Hard accessibility/privacy/gender rules always take precedence (spec rule);
"ground floor" interacts with floors 0–3 of hostels.

## A-21 — Import & reconciliation — Merch supply vs demand is already unbalanced

inventory_merch.csv: T-shirt stock S449 / M115 / L234 / XL713 / XXL136 (reserved 14/6/15/29/25)
vs participant demand S563 / M572 / L596 / XL569 / XXL536 → shortages of ~114 S, 457 M, 362 L,
400 XXL, surplus 144 XL. Also "winner medal" stock (2,269) is implausibly large vs "special
badge" (905); treated as given (ledger opening stock), flagged for ops review.

## A-22 — Import & reconciliation — Logistics inventory condition is tri-part

inventory_logistics.csv: 72 rows = 18 item types × 4 units, quantity 2–35 each, locations:
Sports Complex, Main Stage, Registration Desk, Van 1, Store Room A; condition: good ×35,
"under repair" ×22, "needs check" ×15. Non-good items are imported with a flag but stay in the
ledger (they are physical, just not serviceable) — shortfall logic may treat them as unavailable.

## A-23 — Import & reconciliation — External stays never state "no transport"

`transport_availability` = "limited" for one property is preserved verbatim. Blank future values
map to `unknown` and are read as "not cleared for late arrival / early departure" by any engine
that needs transport — never as available.

## A-24 — Import & reconciliation — Arrival window is Oct 29 – Nov 3, fest days Oct 30 – Nov 1

Data shows arrivals from 2026-10-29 08:00 (≈1,600 participants arrive on Oct 29 — significant
check-in load the day before the fest) and departures up to 2026-11-03 22:00. Only arrivals
after 2026-11-01 are flagged (A-07); Oct 29 arrivals are legitimate early arrivals, but they
create a bed-demand spike on night of Oct 29–30 that the allocator must respect.

## A-25 — Import & reconciliation — Quarantine is by status, never deletion

Rows that fail hard validation (unparseable dates/numbers, unknown category values, broken
cross-file FKs) are inserted with status `quarantined` (or registration status `quarantined`)
plus severity=error `import_issues` rows. Nothing is silently dropped; nothing is auto-corrected.
The pack as delivered contains zero hard-fail rows, so the funnel's quarantine count is 0 —
verified by tests using synthetic bad rows.

## A-26 — Import & reconciliation — Idempotent re-import is update-in-place with audit

Re-running the importer against the same CSVs upserts by (source_file, raw_id): unchanged rows
are skipped, changed rows are updated in place, each producing (a) an audit entry with
before/after and (b) an info issue `CHANGED_ON_REIMPORT`. `seed.py` is a full wipe-and-rebuild
(allowed because it resets the whole demo) and is deterministic.

## A-27 — Auth — Supabase accounts with role in user_metadata (fallback local JWT)

Dashboard users live in Supabase Auth (`{role}@festos.local`, provisioned by `seed.py` via the
service-key admin API, idempotent). The Festos role is read from `user_metadata.role`
(app_metadata `festos_role` and demo-email fallback also accepted). Tokens are verified by
`/auth/v1/user` introspection with a 300 s cache because no JWT secret was provided; if one is
later configured, verification switches to local HS256. Without Supabase env vars the backend
falls back to the offline local-JWT mode used by the test suite.

## A-28 — Masking — Sensitivity is config-driven per role; blanks stay blank

`config.ROLE_FIELD_ACCESS` (not hardcoded) decides which sensitive fields a role sees; masked
values show as "masked" and `POST /participants/{id}/reveal` returns unmasked values for
allowed fields only, with a mandatory reason and a `kind=reveal` audit entry. Blank/unknown
values pass through unchanged (they are not secrets and masking must not fabricate data).
A partial reveal with any denied field returns 403 and leaks nothing.

## A-29 — Merging — Reversible duplicate linking, never a hard delete

Manual merges (`POST /participants/merge`) set `merged_into` + status `duplicate` + flags
(`DUPLICATE_LINKED`, `MERGED_MANUAL`); `POST .../unmerge` reverts to active with
`MERGE_REVERTED`. Registrations/allocations of the duplicate are never re-pointed or deleted.
A record that is itself merged cannot be used as a merge target (409).

## A-30 — Accommodation — Hard constraints require agent availability or a human decision

The greedy allocator never trades ACCESSIBILITY, PRIVACY, GENDER_SEGREGATION, CAPACITY,
READINESS or stay WINDOWS (`relaxations` is always empty by construction). Consequences of
treating them as hard: (1) unclear gender (non_binary/prefer-not-to-say/unknown: ~950 people
in the pack requesting housing) and blank accommodation consent go to a manual review queue,
never a forced binary; (2) participants needing accessibility go unplaced with
`ACCESSIBILITY_NO_SUITABLE_BED` when no accessible hostel bed matches, because external stays
carry no accessibility data (never assumed fine); (3) an external stay never hosts two
different gender cohorts; (4) unknown accessibility is treated conservatively as needing an
accessible bed, except when the details text explicitly says no needs. Operator pins that
violate a hard constraint are reported, not silently honoured.

## A-31 — Accommodation — Cohesion preferences and costs

Hostel beds cost ₹0 per bed-night (external stays carry market rates). Cohesion is a
preference, not a constraint: contingent members prefer rooms already housing their contingent
and, under `prefer_same_floor` presets (max_cohesion, balanced), the same floor. Presets only
differ in external-fallback ordering (min_cost: cheapest first; max_cohesion: largest-capacity
then cost; balanced: cost first) and in cohesion softness. `cleaning_until` blank means ready;
a recorded window blocks only until it ends. Overseas-transport data is missing (A-14), so
overflow to a stay with unknown transport produces an explicit explanation instead of an
assignment of shuttle responsibility.

## A-32 — Scheduling — Conflicts are pairwise, suggestions are ranked by blast radius

Conflicts compare every event PAIR (3 simultaneous events in one venue = 3 VENUE_DOUBLE_BOOK
findings, because each pair might need a different fix). Suggestions are greedy: venue-move
options are scored by how many other events the shift would still collide with (fewest first),
and non-move conflicts (staff clash, overload, equipment shortage) map to an operator action.
Shift coverage treats 22:00-06:00 shifts as wrapping (day coverage >= 22:00 OR <= 06:00);
events exactly at shift boundaries are covered.

## A-33 — Inventory & vendors — Ledger-derived stock, manual rates, issue-once per cluster

Stock is never stored: it is the sum of the movement ledger (a `damaged` repair movement adds
nothing). Merch demand is derived from active participants' declared T-shirt size collapsed
onto canonical duplicate clusters (in the real pack demand exceeds stock in every size; the
shortfall endpoint reports per-size `missing`). Merch issuance is once per participant per
item across the whole dup cluster; re-issues need `force` (director only) and are flagged in
the audit trail. Vendor rates are absent from the pack (A-13): settlement shows amounts only
for vendors with an operator-entered rate and lists the rest under `pending_entries`.

## A-34 �?" Disruptions �?" Preview never mutates, apply carries a full revert snapshot

The seven disruption types flow preview -> apply -> revert, director only, every step audited
(kind "override" on apply/revert). Preview writes only an audit record plus a `Disruption` row
in status `previewed`; real state changes happen only on apply, which stores in
`revert_snapshot` exactly the prior values needed (old allocation rows incl. ids, room
statuses, participant flag lists, movement ids, prior venue_id, prior vendor status). Revert
refuses anything not in the snapshot (it never guesses); the JSON round-trip means snapshot
dict keys come back as strings, so restore lookups handle both. Hostel closure re-houses ONLY
displaced (non-locked) occupants by re-running the allocator seeded with current occupancy
(initial_taken/ext cohorts), so locked beds are respected and reported as
LOCKED_IN_CLOSED_ROOM violations; the closed block is set to status `closed` and excluded
from the room pool. Equipment failure adds a `-qty` movement with status `damaged` (stock is
ledger-derived, nothing is overwritten) and re-checks scheduler equipment demand. Venue
change updates the event row and returns the post-change scheduler conflict list for that
event. Vendor shutdown reroutes open orders via the vendor engine (menu coverage first) and
flags orders with no delivering vendor as unmet with a reason. Duplicate-record links a
record post-import (P002/P004 are already auto-merged by the importer; the operator flow is
for pairs the importer could not safely decide) and moves the duplicate's bed to the
canonical. Duplicate merch claim flags the participant (DUPLICATE_MERCH_CLAIM); a director
"reissue" additionally forces a merch issue + movement, both reverted together.

## A-35 �?" Control center �"? every open finding surfaces, sorted by severity

`GET /control/attention` merges fail-loud findings from all sources (open import issues,
quarantined/flagged participants, allocator review + unplaced + shortage, every scheduler
conflict, vendor certificate compliance, uncovered diet tags, merch shortfall, settlement
entries without rates) into one list of {source, severity, what, entity, action_hint} sorted
error -> warning -> info. KPIs never guess: occupancy is null until a plan is ACTIVE, rates
and unknown fields stay out. `GET /control/audit` is the filterable append-only audit browser
(director only, limit cap 500, pagination; kind and actor filters back the reveal/override
separations demanded by spec p.10).

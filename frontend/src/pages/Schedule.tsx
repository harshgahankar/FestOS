import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import type { Conflict, ConflictCheck, EditResp, EventsList, MoveResp, SchedEvent, SchedVenue, VenuesList } from "../schedTypes";
import { Badge, Btn, Paper, Spinner, Unknown } from "../components/ui";

const DAYS = [
  { id: "day1", label: "Day 1", date: "2026-10-30", display: "Friday, Oct 30" },
  { id: "day2", label: "Day 2", date: "2026-10-31", display: "Saturday, Oct 31" },
  { id: "day3", label: "Day 3", date: "2026-11-01", display: "Sunday, Nov 01" },
];

const HOURS = [
  "9:00", "10:00", "11:00", "12:00", "13:00",
  "14:00", "15:00", "16:00", "17:00", "18:00",
  "19:00", "20:00", "21:00"
];

// Timeline starts at 9:00 (540m) and ends at 22:00 (1320m) -> 780m total
const TIMELINE_START = 540;
const TIMELINE_DURATION = 780;

function getMinuteOfDay(dtStr: string | null): number {
  if (!dtStr) return TIMELINE_START;
  const timePart = dtStr.includes("T") ? dtStr.split("T")[1] : dtStr.split(" ")[1];
  if (!timePart) return TIMELINE_START;
  const [h, m] = timePart.split(":").map(Number);
  return (h || 0) * 60 + (m || 0);
}

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const timePart = iso.includes("T") ? iso.split("T")[1] : iso.split(" ")[1];
  return timePart ? timePart.slice(0, 5) : "";
}


function sevBad(s: string | undefined): "error" | "warning" | "info" {
  return s === "warning" ? "warning" : s === "info" ? "info" : "error";
}

function renderSuggestion(s: unknown): string {
  if (typeof s === "string") return s;
  if (s && typeof s === "object") {
    const obj = s as Record<string, unknown>;
    const action = obj.action ? String(obj.action) : "";
    const event = obj.event ? ` for event ${obj.event}` : "";
    const conf = obj.conflict ? ` (${obj.conflict})` : "";
    const options = Array.isArray(obj.options) && obj.options.length ? ` — Try venue: ${obj.options.slice(0, 3).join(", ")}` : "";
    return `${action}${event}${conf}${options}`.trim() || JSON.stringify(s);
  }
  return String(s);
}

export default function Schedule() {
  const [events, setEvents] = useState<EventsList | null>(null);
  const [venues, setVenues] = useState<SchedVenue[] | null>(null);
  const [check, setCheck] = useState<ConflictCheck | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedDay, setSelectedDay] = useState("day1");

  const [editFor, setEditFor] = useState<SchedEvent | null>(null);
  const [editErr, setEditErr] = useState("");
  const [modalBusy, setModalBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [moveOpen, setMoveOpen] = useState(false);
  const [moveTarget, setMoveTarget] = useState<string>("");
  const [moveErr, setMoveErr] = useState("");

  const [showConflicts, setShowConflicts] = useState(true);
  const [showUnscheduled, setShowUnscheduled] = useState(false);

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const [ev, ck, vn] = await Promise.all([
        api<EventsList>("/schedule/events"),
        api<ConflictCheck>("/schedule/conflicts"),
        api<VenuesList>("/schedule/venues"),
      ]);
      setEvents(ev);
      setCheck(ck);
      setVenues(vn.venues);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function saveEdit(e: SchedEvent, patch: Record<string, unknown>, reason: string) {
    setModalBusy(true);
    setEditErr("");
    try {
      const out = await api<EditResp>(`/schedule/events/${e.id}`, {
        method: "PATCH",
        body: { ...patch, reason },
      });
      setEditFor(null);
      const inv = out.conflicts_involved?.length
        ? ` — ${out.conflicts_involved.length} conflict(s) now involve this event`
        : " — no conflicts involve this event";
      setNotice(
        `${e.raw_id} edited (${out.changed.join(", ")}) — audit #${out.audit_entry}${inv}. ` +
        `board-wide conflicts after edit: ${out.post_edit_conflicts}`,
      );
      void load();
    } catch (e2) {
      setEditErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setModalBusy(false);
    }
  }

  async function doMove(rawId: string, venue: string, start: string, end: string) {
    setModalBusy(true);
    setMoveErr("");
    const body: Record<string, unknown> = { event_raw_id: rawId };
    if (venue) body.venue_id = Number(venue);
    if (start) body.start = start;
    if (end) body.end = end;
    try {
      const out = await api<MoveResp>("/schedule/move", { method: "POST", body });
      setMoveOpen(false);
      const rem = out.remaining_conflicts_for_event?.length
        ? ` — still in ${out.remaining_conflicts_for_event.length} conflict(s)`
        : " — clean after move";
      setNotice(
        `${out.raw_id} moved — audit #${out.audit_entry} (reason auto-recorded by the engine)${rem}. ` +
        (out.suggestions.length ? `engine suggests: ${renderSuggestion(out.suggestions[0])}` : "no suggestions"),
      );
      void load();
    } catch (e2) {
      setMoveErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setModalBusy(false);
    }
  }

  function handleExportCsv() {
    if (!events || !venues) return;
    const venueMap = new Map(venues.map((v) => [v.id, v]));
    const headers = [
      "Event ID", "Name", "Type", "Venue ID", "Venue Name",
      "Venue Capacity", "Start Time", "End Time", "Duration (min)",
      "Registrations", "Status", "Conflicts",
    ];
    const rows = events.events.map((ev) => {
      const venue = ev.venue_id ? venueMap.get(ev.venue_id) : null;
      const evConflicts = (check?.conflicts ?? []).filter(
        (c) => c.event === ev.raw_id || c.event_1 === ev.raw_id || c.event_2 === ev.raw_id
      );
      const conflictSummary = evConflicts.map((c) => c.type).join("; ");
      return [
        `"${ev.raw_id}"`,
        `"${(ev.name || "").replace(/"/g, '""')}"`,
        `"${ev.type || ""}"`,
        `"${ev.venue_id ?? ""}"`,
        `"${venue ? venue.name.replace(/"/g, '""') : ""}"`,
        `"${venue ? venue.capacity : ""}"`,
        `"${ev.start || ""}"`,
        `"${ev.end || ""}"`,
        `"${ev.duration_minutes ?? ""}"`,
        `"${ev.registration_count ?? 0}"`,
        `"${ev.start ? "Scheduled" : "Unscheduled"}"`,
        `"${conflictSummary.replace(/"/g, '""')}"`,
      ].join(",");
    });
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `festos_schedule_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  const activeDayObj = DAYS.find((d) => d.id === selectedDay) || DAYS[0];
  const activeDate = activeDayObj.date;

  // Unscheduled events
  const unscheduledEvents = (events?.events ?? []).filter((e) => !e.start);
  const scheduledCount = (events?.events ?? []).filter((e) => !!e.start).length;

  const totalConflictsCount = check
    ? Object.values(check.summary).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="space-y-4 pb-12">
      {/* Header bar matching user screenshot */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink md:text-3xl">
            Schedule &amp; conflicts
          </h1>
          <p className="text-xs font-medium text-ink/60 mt-0.5">
            Timeline matrix &amp; clash inspector &bull; {scheduledCount} scheduled, {unscheduledEvents.length} unscheduled
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExportCsv}
            disabled={!events}
            className="inline-flex items-center gap-2 rounded-lg border-2 border-crimson-dark/30 bg-white/80 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wider text-ink shadow-xs transition hover:bg-white hover:border-crimson-dark/70 focus:outline-none focus:ring-2 focus:ring-mustard"
          >
            <svg className="h-4 w-4 text-crimson-dark" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export schedule CSV
          </button>
        </div>
      </div>

      {notice && (
        <p className="paper rounded-md border-2 border-teal-dark/40 bg-teal/10 px-3 py-2 text-sm font-semibold text-teal-dark shadow-xs">
          {notice}
        </p>
      )}

      {err && (
        <p className="rounded-md border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream shadow-xs">
          {err}
        </p>
      )}

      {/* Day Selector Pills matching user screenshot */}
      <div className="flex items-center gap-2">
        {DAYS.map((d) => {
          const isActive = selectedDay === d.id;
          return (
            <button
              key={d.id}
              onClick={() => setSelectedDay(d.id)}
              className={`rounded-lg px-4 py-1.5 text-xs font-bold transition-all shadow-xs ${
                isActive
                  ? "bg-mustard text-ink border-2 border-mustard-dark/40 ring-1 ring-mustard/30 scale-[1.02]"
                  : "bg-white/60 hover:bg-white text-ink/75 hover:text-ink border-2 border-ink/15"
              }`}
            >
              {d.label}
            </button>
          );
        })}
        <span className="ml-2 text-xs font-medium text-ink/50 italic">
          {activeDayObj.display}
        </span>
      </div>

      {busy && !events && <Spinner label="Loading festival schedule matrix…" />}

      {/* Main Gantt Timeline Matrix */}
      {venues && events && (
        <div className="rounded-lg border-2 border-crimson-dark/25 bg-white/70 backdrop-blur-sm shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <div className="min-w-[1050px]">
              {/* Table Header: VENUE + 13 Hourly Intervals */}
              <div className="flex border-b border-ink/15 bg-crimson-dark/10">
                <div className="w-48 shrink-0 px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider text-ink/70">
                  VENUE
                </div>
                <div className="grid flex-1 grid-cols-[repeat(13,minmax(0,1fr))] text-center">
                  {HOURS.map((h) => (
                    <div
                      key={h}
                      className="border-l border-ink/10 py-3 text-xs font-mono font-semibold text-ink/70"
                    >
                      {h}
                    </div>
                  ))}
                </div>
              </div>

              {/* Venue Rows */}
              <div className="divide-y divide-ink/10">
                {venues.map((v) => {
                  // Find events for this venue on the active day
                  const venueEvents = events.events.filter((e) => {
                    if (e.venue_id !== v.id || !e.start) return false;
                    return e.start.includes(activeDate);
                  });

                  // Calculate overlap lanes
                  const parsed = venueEvents.map((e) => {
                    const sMin = getMinuteOfDay(e.start);
                    const dur = e.duration_minutes || 60;
                    const eMin = e.end ? getMinuteOfDay(e.end) : sMin + dur;
                    return {
                      event: e,
                      sMin,
                      eMin: Math.max(eMin, sMin + 30),
                    };
                  }).sort((a, b) => a.sMin - b.sMin);

                  const lanes: number[] = [];
                  const positioned = parsed.map((item) => {
                    let assignedLane = -1;
                    for (let l = 0; l < lanes.length; l++) {
                      if (lanes[l] <= item.sMin) {
                        assignedLane = l;
                        lanes[l] = item.eMin;
                        break;
                      }
                    }
                    if (assignedLane === -1) {
                      assignedLane = lanes.length;
                      lanes.push(item.eMin);
                    }
                    return { ...item, lane: assignedLane };
                  });

                  const totalLanes = Math.max(1, lanes.length);
                  const trackHeight = totalLanes === 1 ? 58 : totalLanes * 36 + 18;

                  return (
                    <div
                      key={v.id}
                      className="flex transition-colors hover:bg-mustard/5"
                      style={{ minHeight: `${trackHeight}px` }}
                    >
                      {/* Left: Venue info */}
                      <div className="w-48 shrink-0 border-r border-ink/15 bg-white/40 px-4 py-3 flex flex-col justify-center">
                        <div className="text-sm font-bold text-ink leading-tight truncate" title={v.name}>
                          {v.name}
                        </div>
                        <div className="mt-0.5 text-xs font-mono text-ink/50">
                          cap {v.capacity}
                        </div>
                      </div>

                      {/* Right: Timeline track */}
                      <div className="relative flex-1 bg-white/10 overflow-hidden">
                        {/* Background 13 column grid lines */}
                        <div className="absolute inset-0 grid grid-cols-[repeat(13,minmax(0,1fr))] pointer-events-none">
                          {HOURS.map((_, i) => (
                            <div key={i} className="border-l border-ink/10 h-full" />
                          ))}
                        </div>

                        {/* Event blocks */}
                        {positioned.map(({ event: ev, sMin, eMin, lane }) => {
                          const clampedStart = Math.max(TIMELINE_START, Math.min(1320, sMin));
                          const clampedEnd = Math.max(clampedStart + 25, Math.min(1320, eMin));
                          const leftPct = ((clampedStart - TIMELINE_START) / TIMELINE_DURATION) * 100;
                          const widthPct = ((clampedEnd - clampedStart) / TIMELINE_DURATION) * 100;

                          const hasConflict = (check?.conflicts ?? []).some(
                            (c) => c.event === ev.raw_id || c.event_1 === ev.raw_id || c.event_2 === ev.raw_id
                          );

                          const laneTop = totalLanes === 1 ? 12 : lane * 34 + 8;

                          return (
                            <div
                              key={ev.id}
                              onClick={() => {
                                setEditErr("");
                                setEditFor(ev);
                              }}
                              style={{
                                left: `${Math.max(0, Math.min(96, leftPct))}%`,
                                width: `${Math.max(4, Math.min(100 - leftPct, widthPct))}%`,
                                top: `${laneTop}px`,
                                height: "32px",
                              }}
                              className={`absolute z-10 flex items-center justify-between rounded-md px-2.5 py-1 text-xs font-semibold cursor-pointer transition-all duration-150 hover:scale-[1.01] hover:shadow-md truncate border-2 select-none ${
                                hasConflict
                                  ? "bg-crimson-dark/15 border-crimson-deep text-crimson-deep font-bold ring-1 ring-crimson-deep/40 shadow-xs"
                                  : "bg-[#FFF8E7] hover:bg-[#FFF2D4] border-[#D97706]/70 text-[#78350F] shadow-xs"
                              }`}
                              title={`${ev.name} (${fmtTime(ev.start)} → ${fmtTime(ev.end)}) • Click to edit/audit`}
                            >
                              <span className="truncate pr-1">{ev.name}</span>
                              {hasConflict ? (
                                <span className="ml-1 text-[11px] font-bold text-crimson-deep" title="Conflict detected">
                                  ⚠
                                </span>
                              ) : (
                                <span className="text-[10px] font-mono text-ink/50 opacity-0 group-hover:opacity-100 hidden md:inline">
                                  {fmtTime(ev.start)}
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Conflict Desk Findings Card */}
      {check && (
        <Paper
          title={
            <div className="flex items-center justify-between w-full">
              <span className="text-base font-bold text-ink">
                Conflict desk — {totalConflictsCount} findings across {check.checked_events} events
              </span>
              <button
                onClick={() => setShowConflicts(!showConflicts)}
                className="text-xs font-bold uppercase tracking-wider text-teal-dark hover:underline"
              >
                {showConflicts ? "Hide Details" : "Show Details"}
              </button>
            </div>
          }
        >
          <div className="mb-2 flex flex-wrap gap-1.5">
            {Object.entries(check.summary).map(([t, n]) => (
              <Badge
                key={t}
                sev={
                  /CLASH|DOUBLE|HOURS|SHORTAGE/.test(t)
                    ? "error"
                    : /BUFFER|MISMATCH|OVERLOAD/.test(t)
                    ? "warning"
                    : "info"
                }
              >
                {t} {n}
              </Badge>
            ))}
            {Object.keys(check.summary).length === 0 && (
              <Badge sev="good">no conflicts anywhere</Badge>
            )}
          </div>

          {showConflicts && (
            <>
              {check.conflicts.length > 0 && (
                <ul className="mt-3 max-h-56 space-y-1 overflow-y-auto pr-1 text-xs">
                  {check.conflicts.map((c, i) => (
                    <ConflictRow key={i} c={c} />
                  ))}
                </ul>
              )}
              {check.suggestions.length > 0 && (
                <details className="mt-3 pt-2 border-t border-ink/10">
                  <summary className="cursor-pointer text-xs font-bold uppercase text-teal-dark">
                    engine suggestions ({check.suggestions.length})
                  </summary>
                  <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-ink/80">
                    {check.suggestions.map((s, i) => (
                      <li key={i}>{renderSuggestion(s)}</li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </Paper>
      )}

      {/* Unscheduled Events Drawer / Action Bar */}
      {events && (
        <Paper
          title={
            <div className="flex items-center justify-between w-full">
              <span className="text-base font-bold text-ink">
                Unscheduled Events ({unscheduledEvents.length})
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => {
                    setMoveErr("");
                    setNotice("");
                    setMoveTarget("");
                    setMoveOpen(true);
                  }}
                  className="rounded-md border border-crimson-dark/40 bg-mustard/40 px-2.5 py-1 text-xs font-bold uppercase text-crimson-deep hover:bg-mustard/70 transition shadow-xs"
                >
                  Move / Place Event
                </button>
                <button
                  onClick={() => setShowUnscheduled(!showUnscheduled)}
                  className="text-xs font-bold uppercase tracking-wider text-teal-dark hover:underline"
                >
                  {showUnscheduled ? "Hide List" : "Show List"}
                </button>
              </div>
            </div>
          }
        >
          {showUnscheduled ? (
            <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
              <table className="w-full text-left">
                <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                  <tr>
                    <th className="px-2 py-2">raw id</th>
                    <th className="px-2 py-2">name</th>
                    <th className="px-2 py-2">type</th>
                    <th className="px-2 py-2">dur</th>
                    <th className="px-2 py-2">regs</th>
                    <th className="px-2 py-2">action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink/10">
                  {unscheduledEvents.map((ev) => (
                    <tr key={ev.id} className="hover:bg-mustard/15">
                      <td className="px-2 py-1.5 font-mono text-xs font-bold">{ev.raw_id}</td>
                      <td className="px-2 py-1.5 text-sm font-semibold">{ev.name}</td>
                      <td className="px-2 py-1.5 text-xs">
                        {ev.type ? <Badge sev="neutral">{ev.type}</Badge> : <Unknown />}
                      </td>
                      <td className="px-2 py-1.5 text-xs">
                        {ev.duration_minutes ? `${ev.duration_minutes}m` : <Unknown />}
                      </td>
                      <td className="px-2 py-1.5 text-xs">{ev.registration_count}</td>
                      <td className="px-2 py-1.5">
                        <span className="flex gap-1.5">
                          <button
                            onClick={() => {
                              setEditErr("");
                              setEditFor(ev);
                            }}
                            className="rounded-sm border border-teal-dark/50 bg-teal/20 px-2 py-0.5 text-[10px] font-bold uppercase text-teal-dark hover:bg-teal/40"
                          >
                            schedule ✏
                          </button>
                          <button
                            onClick={() => {
                              setMoveErr("");
                              setNotice("");
                              setMoveTarget(ev.raw_id);
                              setMoveOpen(true);
                            }}
                            className="rounded-sm border border-crimson-dark/50 bg-mustard/40 px-2 py-0.5 text-[10px] font-bold uppercase text-crimson-deep hover:bg-mustard/70"
                          >
                            move
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                  {unscheduledEvents.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-xs text-ink/60 italic">
                        All events are scheduled on the festival calendar!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-ink/70">
              {unscheduledEvents.length > 0
                ? `${unscheduledEvents.length} events are awaiting venue and time allocation per Assumption A-11.`
                : "All events have been successfully assigned to slots on the timeline."}
            </p>
          )}
        </Paper>
      )}

      {/* Audited Edit Modal */}
      {editFor && (
        <EditModal
          ev={editFor}
          busy={modalBusy}
          error={editErr}
          venues={venues ?? []}
          onClose={() => setEditFor(null)}
          onSave={saveEdit}
        />
      )}

      {/* Move Modal */}
      {moveOpen && (
        <ReasonlessModal
          title="Move event (venue/time)"
          description="The engine keeps its own reason ('schedule move of <id>') and re-checks conflicts after. Leave a field blank to keep it."
          busy={modalBusy}
          error={moveErr}
          initialEvent={moveTarget}
          events={events?.events.map((e) => e.raw_id) ?? []}
          venues={venues ?? []}
          onCancel={() => setMoveOpen(false)}
          onConfirm={(ev, venue, start, end) => {
            if (!ev || !/^[A-Za-z0-9\-_.]+$/.test(ev)) {
              setMoveErr("pick the event to move");
              return;
            }
            if (!venue && !start && !end) {
              setMoveErr("give at least one of venue / start / end");
              return;
            }
            void doMove(ev, venue, start, end);
          }}
        />
      )}
    </div>
  );
}

function ConflictRow({ c }: { c: Conflict }) {
  return (
    <li className="border-b border-ink/10 pb-1 flex items-baseline gap-2">
      <Badge sev={sevBad(c.severity)}>{c.type}</Badge>
      <span className="italic text-ink/85">{c.message}</span>
    </li>
  );
}

/* --------------------------------- modals --------------------------------- */

const DT_PLACEHOLDER = "YYYY-MM-DDTHH:MM";

function EditModal({
  ev,
  busy,
  error,
  venues,
  onClose,
  onSave,
}: {
  ev: SchedEvent;
  busy: boolean;
  error: string;
  venues: SchedVenue[];
  onClose: () => void;
  onSave: (e: SchedEvent, patch: Record<string, unknown>, reason: string) => void;
}) {
  const initial: Record<string, string> = {
    name: ev.name ?? "",
    venue_id: ev.venue_id == null ? "" : String(ev.venue_id),
    start_dt: ev.start ? ev.start.slice(0, 16) : "",
    end_dt: ev.end ? ev.end.slice(0, 16) : "",
    duration_minutes: ev.duration_minutes == null ? "" : String(ev.duration_minutes),
  };
  const [form, setForm] = useState(initial);
  const [reason, setReason] = useState("");
  const [noteErr, setNoteErr] = useState(false);

  function submit() {
    const patch: Record<string, unknown> = {};
    if (form.name !== initial.name) patch.name = form.name;
    if (form.venue_id !== initial.venue_id)
      patch.venue_id = form.venue_id === "" ? null : Number(form.venue_id);
    if (form.start_dt !== initial.start_dt)
      patch.start_dt = form.start_dt === "" ? null : form.start_dt;
    if (form.end_dt !== initial.end_dt)
      patch.end_dt = form.end_dt === "" ? null : form.end_dt;
    if (form.duration_minutes !== initial.duration_minutes)
      patch.duration_minutes =
        form.duration_minutes === "" ? null : Number(form.duration_minutes);
    if (Object.keys(patch).length === 0) {
      onClose();
      return;
    }
    if (!reason.trim()) {
      setNoteErr(true);
      return;
    }
    onSave(ev, patch, reason.trim());
  }

  return (
    <Overlay onClose={onClose}>
      <h3 className="font-display mb-1 text-xl text-ink">Edit {ev.raw_id} — audited</h3>
      <p className="mb-3 text-sm text-ink/75">
        Only fields you change are sent; before/after + reason land in the audit log.
      </p>
      {error && (
        <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">
          refused: {error}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <L label="name">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inp}
          />
        </L>
        <L label="venue">
          <select
            value={form.venue_id}
            onChange={(e) => setForm({ ...form, venue_id: e.target.value })}
            className={inp}
          >
            <option value="">(No venue / Unassigned)</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} (cap {v.capacity})
              </option>
            ))}
          </select>
        </L>
        <L label={`start (${DT_PLACEHOLDER})`}>
          <input
            value={form.start_dt}
            onChange={(e) => setForm({ ...form, start_dt: e.target.value })}
            className={inp}
            placeholder={DT_PLACEHOLDER}
          />
        </L>
        <L label={`end (${DT_PLACEHOLDER})`}>
          <input
            value={form.end_dt}
            onChange={(e) => setForm({ ...form, end_dt: e.target.value })}
            className={inp}
            placeholder={DT_PLACEHOLDER}
          />
        </L>
        <L label="duration minutes">
          <input
            value={form.duration_minutes}
            onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
            className={inp}
          />
        </L>
      </div>
      <label className="mt-3 block text-xs font-bold uppercase text-ink/70">
        Reason (required, audited)
        <textarea
          value={reason}
          onChange={(e) => {
            setReason(e.target.value);
            setNoteErr(false);
          }}
          rows={2}
          className={`mt-0.5 w-full rounded-sm border-2 bg-white/60 px-3 py-1.5 text-sm font-normal text-ink ${
            noteErr ? "border-saffron" : "border-teal-dark/40"
          }`}
        />
      </label>
      {noteErr && (
        <p className="text-xs font-bold text-crimson-deep">
          a reason is required — writes without reasons are refused
        </p>
      )}
      <ModalButtons busy={busy} onClose={onClose} onSubmit={submit} label="save" />
    </Overlay>
  );
}

/** Move flow keeps no local reason (engine writes its own audited reason). */
function ReasonlessModal({
  title,
  description,
  busy,
  error,
  initialEvent,
  events,
  venues,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  busy: boolean;
  error: string;
  initialEvent?: string;
  events: string[];
  venues: SchedVenue[];
  onCancel: () => void;
  onConfirm: (rawId: string, venue: string, start: string, end: string) => void;
}) {
  const [ev, setEv] = useState(initialEvent || events[0] || "");
  const [venue, setVenue] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  return (
    <Overlay onClose={onCancel}>
      <h3 className="font-display mb-1 text-xl text-ink">{title}</h3>
      <p className="mb-3 text-sm text-ink/75">{description}</p>
      {error && (
        <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">
          refused: {error}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <L label="event">
          <select
            value={ev}
            onChange={(e) => setEv(e.target.value)}
            className={`${inp} font-mono normal-case tracking-normal`}
          >
            {events.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </L>
        <L label="destination venue">
          <select
            value={venue}
            onChange={(e) => setVenue(e.target.value)}
            className={inp}
          >
            <option value="">(Leave unchanged)</option>
            {venues.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name} (cap {v.capacity})
              </option>
            ))}
          </select>
        </L>
        <L label={`new start (${DT_PLACEHOLDER})`}>
          <input
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className={inp}
            placeholder={DT_PLACEHOLDER}
          />
        </L>
        <L label={`new end (${DT_PLACEHOLDER})`}>
          <input
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className={inp}
            placeholder={DT_PLACEHOLDER}
          />
        </L>
      </div>
      <ModalButtons
        busy={busy}
        onClose={onCancel}
        onSubmit={() => onConfirm(ev, venue, start, end)}
        label="move"
      />
    </Overlay>
  );
}

const inp =
  "w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink normal-case tracking-normal";

function Overlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-crimson-dark/70 p-4"
      onClick={onClose}
    >
      <div
        className="paper torn-b relative max-h-[85vh] w-full max-w-md overflow-y-auto rounded-sm border-2 border-crimson-dark/50 p-5 pb-7 shadow-[0_10px_0_rgba(64,16,18,0.5)]"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

function L({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="text-xs font-bold uppercase text-ink/70">
      {label}
      <span className="mt-0.5 block">{children}</span>
    </label>
  );
}

function ModalButtons({
  busy,
  onClose,
  onSubmit,
  label,
}: {
  busy: boolean;
  onClose: () => void;
  onSubmit: () => void;
  label: string;
}) {
  return (
    <div className="mt-3 flex justify-end gap-2">
      <Btn variant="ghost" className="!border-ink/30 !text-ink/80" onClick={onClose}>
        cancel
      </Btn>
      <Btn disabled={busy} onClick={onSubmit}>
        {busy ? "saving…" : label}
      </Btn>
    </div>
  );
}

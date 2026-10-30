import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import type { Conflict, ConflictCheck, EditResp, EventsList, MoveResp, SchedEvent } from "../schedTypes";
import { PageHeader } from "../components/Listkit";
import { Badge, Btn, Paper, Spinner, Unknown } from "../components/ui";

export default function Schedule() {
  const [events, setEvents] = useState<EventsList | null>(null);
  const [check, setCheck] = useState<ConflictCheck | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [scheduledOnly, setScheduledOnly] = useState(false);
  const [editFor, setEditFor] = useState<SchedEvent | null>(null);
  const [editErr, setEditErr] = useState("");
  const [modalBusy, setModalBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [moveOpen, setMoveOpen] = useState(false);
  const [moveErr, setMoveErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const [ev, ck] = await Promise.all([
        api<EventsList>(`/schedule/events${scheduledOnly ? "?scheduled_only=true" : ""}`),
        api<ConflictCheck>("/schedule/conflicts"),
      ]);
      setEvents(ev);
      setCheck(ck);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, [scheduledOnly]);

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
        (out.suggestions.length ? `engine suggests: ${out.suggestions[0]}` : "no suggestions"),
      );
      void load();
    } catch (e2) {
      setMoveErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setModalBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Schedule & Conflict Desk" />
      {notice && (
        <p className="paper mb-3 rounded-sm border-2 border-teal-dark/40 px-3 py-2 text-sm font-semibold text-teal-dark">
          {notice}
        </p>
      )}
      {err && <p className="mb-3 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-cream">{err}</p>}
      {busy && <Spinner label="reading the board…" />}

      {check && (
        <Paper title={`Conflict desk — ${Object.values(check.summary).reduce((a, b) => a + b, 0)} findings across ${check.checked_events} events`} className="mb-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {Object.entries(check.summary).map(([t, n]) => (
              <Badge key={t} sev={
                /CLASH|DOUBLE|HOURS|SHORTAGE/.test(t) ? "error" : /BUFFER|MISMATCH|OVERLOAD/.test(t) ? "warning" : "info"
              }>{t} {n}</Badge>
            ))}
            {Object.keys(check.summary).length === 0 && <Badge sev="good">no conflicts anywhere</Badge>}
          </div>
          {check.conflicts.length > 0 && (
            <ul className="max-h-56 space-y-1 overflow-y-auto pr-1 text-xs">
              {check.conflicts.map((c, i) => <ConflictRow key={i} c={c} />)}
            </ul>
          )}
          {check.suggestions.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs font-bold uppercase text-teal-dark">
                engine suggestions ({check.suggestions.length})
              </summary>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-ink/80">
                {check.suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </details>
          )}
        </Paper>
      )}

      {events && (
        <Paper title={`Events board — every event starts unscheduled (A-11); nothing invented`}>
          <label className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase text-ink/70">
            <input type="checkbox" checked={scheduledOnly} onChange={(e) => setScheduledOnly(e.target.checked)} />
            scheduled only
          </label>
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-2">raw id</th><th className="px-2 py-2">name</th>
                  <th className="px-2 py-2">type</th><th className="px-2 py-2">when</th>
                  <th className="px-2 py-2">venue</th><th className="px-2 py-2">dur</th>
                  <th className="px-2 py-2">regs</th><th className="px-2 py-2">state</th>
                  <th className="px-2 py-2 col-span-1">actions</th>
                </tr>
              </thead>
              <tbody>
                {events.events.map((ev) => {
                  const scheduled = ev.start !== null;
                  return (
                    <tr key={ev.id} className="border-b border-ink/10 hover:bg-mustard/20">
                      <td className="px-2 py-1.5 font-mono text-xs font-bold">{ev.raw_id}</td>
                      <td className="px-2 py-1.5 text-sm font-semibold">{ev.name}</td>
                      <td className="px-2 py-1.5 text-xs">{ev.type ? <Badge sev="neutral">{ev.type}</Badge> : <Unknown />}</td>
                      <td className="px-2 py-1.5 text-xs">
                        {ev.start
                          ? `${fmt(ev.start)} → ${ev.end ? fmt(ev.end) : "?"}`
                          : <Unknown />}
                      </td>
                      <td className="px-2 py-1.5 text-xs font-mono">{ev.venue_id ?? <Unknown />}</td>
                      <td className="px-2 py-1.5 text-xs">{ev.duration_minutes ? `${ev.duration_minutes}m` : <Unknown />}</td>
                      <td className="px-2 py-1.5 text-xs">{ev.registration_count}</td>
                      <td className="px-2 py-1.5">
                        {scheduled ? <Badge sev="good">scheduled</Badge> : <Badge sev="warning">unscheduled</Badge>}
                      </td>
                      <td className="px-2 py-1.5">
                        <span className="flex gap-1">
                          <button onClick={() => { setEditErr(""); setEditFor(ev); }}
                            className="rounded-sm border border-teal-dark/50 bg-teal/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-teal-dark hover:bg-teal/40">
                            edit ✏
                          </button>
                          <button onClick={() => { setMoveErr(""); setNotice(""); setMoveOpen(true); }}
                            className="rounded-sm border border-crimson-dark/50 bg-mustard/40 px-1.5 py-0.5 text-[10px] font-bold uppercase text-crimson-deep hover:bg-mustard/70"
                            data-raw={ev.raw_id}>
                            move
                          </button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Paper>
      )}

      {editFor && (
        <EditModal ev={editFor} busy={modalBusy} error={editErr}
          onClose={() => setEditFor(null)} onSave={saveEdit} />
      )}
      {moveOpen && (
        <ReasonlessModal
          title="Move event (venue/time)"
          description="The engine keeps its own reason ('schedule move of <id>') and re-checks conflicts after. Leave a field blank to keep it."
          busy={modalBusy}
          error={moveErr}
          events={events?.events.map((e) => e.raw_id) ?? []}
          onCancel={() => setMoveOpen(false)}
          onConfirm={(ev, venue, start, end) => {
            if (!ev || !/^[A-Za-z0-9\-_.]+$/.test(ev)) { setMoveErr("pick the event to move"); return; }
            if (!venue && !start && !end) { setMoveErr("give at least one of venue / start / end"); return; }
            void doMove(ev, venue, start, end);
          }}
        />
      )}
    </div>
  );
}

function fmt(iso: string) {
  return iso.replace("T", " ").slice(0, 16);
}

function sevBad(s: string | undefined): "error" | "warning" | "info" {
  return s === "warning" ? "warning" : s === "info" ? "info" : "error";
}

function ConflictRow({ c }: { c: Conflict }) {
  return (
    <li className="border-b border-ink/10 pb-1">
      <Badge sev={sevBad(c.severity)}>{c.type}</Badge>{" "}
      <span className="italic">{c.message}</span>
    </li>
  );
}

/* --------------------------------- modals --------------------------------- */

const DT_PLACEHOLDER = "YYYY-MM-DDTHH:MM";

function EditModal({ ev, busy, error, onClose, onSave }: {
  ev: SchedEvent; busy: boolean; error: string;
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
    if (form.venue_id !== initial.venue_id) patch.venue_id = form.venue_id === "" ? null : Number(form.venue_id);
    if (form.start_dt !== initial.start_dt) patch.start_dt = form.start_dt === "" ? null : form.start_dt;
    if (form.end_dt !== initial.end_dt) patch.end_dt = form.end_dt === "" ? null : form.end_dt;
    if (form.duration_minutes !== initial.duration_minutes)
      patch.duration_minutes = form.duration_minutes === "" ? null : Number(form.duration_minutes);
    if (Object.keys(patch).length === 0) { onClose(); return; }
    if (!reason.trim()) { setNoteErr(true); return; }
    onSave(ev, patch, reason.trim());
  }

  return (
    <Overlay onClose={onClose}>
      <h3 className="font-display mb-1 text-xl text-ink">Edit {ev.raw_id} — audited</h3>
      <p className="mb-3 text-sm text-ink/75">Only fields you change are sent; before/after + reason land in the audit log.</p>
      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">refused: {error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <L label="name">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inp} />
        </L>
        <L label="venue id (numeric, blank to clear)">
          <input value={form.venue_id} onChange={(e) => setForm({ ...form, venue_id: e.target.value })} className={inp} />
        </L>
        <L label={`start (${DT_PLACEHOLDER})`}>
          <input value={form.start_dt} onChange={(e) => setForm({ ...form, start_dt: e.target.value })} className={inp} placeholder={DT_PLACEHOLDER} />
        </L>
        <L label={`end (${DT_PLACEHOLDER})`}>
          <input value={form.end_dt} onChange={(e) => setForm({ ...form, end_dt: e.target.value })} className={inp} placeholder={DT_PLACEHOLDER} />
        </L>
        <L label="duration minutes">
          <input value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} className={inp} />
        </L>
      </div>
      <label className="mt-3 block text-xs font-bold uppercase text-ink/70">
        Reason (required, audited)
        <textarea value={reason} onChange={(e) => { setReason(e.target.value); setNoteErr(false); }} rows={2}
          className={`mt-0.5 w-full rounded-sm border-2 bg-white/60 px-3 py-1.5 text-sm font-normal text-ink ${noteErr ? "border-saffron" : "border-teal-dark/40"}`} />
      </label>
      {noteErr && <p className="text-xs font-bold text-crimson-deep">a reason is required — writes without reasons are refused</p>}
      <ModalButtons busy={busy} onClose={onClose} onSubmit={submit} label="save" />
    </Overlay>
  );
}

/** Move flow keeps no local reason (engine writes its own audited reason). */
function ReasonlessModal({ title, description, busy, error, events, onCancel, onConfirm }: {
  title: string; description: string; busy: boolean; error: string;
  events: string[];
  onCancel: () => void;
  onConfirm: (rawId: string, venue: string, start: string, end: string) => void;
}) {
  const [ev, setEv] = useState(events[0] ?? "");
  const [venue, setVenue] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  return (
    <Overlay onClose={onCancel}>
      <h3 className="font-display mb-1 text-xl text-ink">{title}</h3>
      <p className="mb-3 text-sm text-ink/75">{description}</p>
      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">refused: {error}</p>}
      <div className="grid grid-cols-2 gap-2">
        <L label="event">
          <select value={ev} onChange={(e) => setEv(e.target.value)}
            className={`${inp} font-mono normal-case tracking-normal`}>
            {events.map((r) => <option key={r}>{r}</option>)}
          </select>
        </L>
        <L label="venue id (numeric)">
          <input value={venue} onChange={(e) => setVenue(e.target.value)} className={inp} />
        </L>
        <L label={`new start (${DT_PLACEHOLDER})`}>
          <input value={start} onChange={(e) => setStart(e.target.value)} className={inp} placeholder={DT_PLACEHOLDER} />
        </L>
        <L label={`new end (${DT_PLACEHOLDER})`}>
          <input value={end} onChange={(e) => setEnd(e.target.value)} className={inp} placeholder={DT_PLACEHOLDER} />
        </L>
      </div>
      <ModalButtons busy={busy} onClose={onCancel}
        onSubmit={() => onConfirm(ev, venue, start, end)} label="move" />
    </Overlay>
  );
}

const inp = "w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink normal-case tracking-normal";

function Overlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-crimson-dark/70 p-4" onClick={onClose}>
      <div className="paper torn-b relative max-h-[85vh] w-full max-w-md overflow-y-auto rounded-sm border-2 border-crimson-dark/50 p-5 pb-7 shadow-[0_10px_0_rgba(64,16,18,0.5)]" onClick={(e) => e.stopPropagation()}>
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

function ModalButtons({ busy, onClose, onSubmit, label }: {
  busy: boolean; onClose: () => void; onSubmit: () => void; label: string;
}) {
  return (
    <div className="mt-3 flex justify-end gap-2">
      <Btn variant="ghost" className="!border-ink/30 !text-ink/80" onClick={onClose}>cancel</Btn>
      <Btn disabled={busy} onClick={onSubmit}>{busy ? "saving…" : label}</Btn>
    </div>
  );
}

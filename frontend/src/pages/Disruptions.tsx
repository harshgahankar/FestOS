import { useEffect, useState } from "react";
import { api } from "../api";
import type { DisruptionRow, ActResp, ListResp, PreviewResp, Report, Venue } from "../disTypes";
import { TICKET_TYPES } from "../disTypes";
import ReasonModal from "../components/ReasonModal";
import { PageHeader } from "../components/Listkit";
import { Badge, Paper, Spinner } from "../components/ui";

type Modal =
  | { kind: "apply"; id: number; type: string }
  | { kind: "revert"; id: number; type: string }
  | null;

const statusSev = { previewed: "warning", applied: "error", reverted: "good" } as const;

export default function Disruptions() {
  const [rows, setRows] = useState<DisruptionRow[] | null>(null);
  const [venues, setVenues] = useState<Venue[]>([]);
  const [events, setEvents] = useState<{ id: number; raw_id: string; name: string; venue_id: number | null }[]>([]);
  const [dtype, setDtype] = useState<string>("late_contingent");
  const [f, setF] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<{ id: number; type: string; report: Report } | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [modalBusy, setModalBusy] = useState(false);
  const [modalErr, setModalErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const [l, vs, es] = await Promise.all([
        api<ListResp>("/disruptions"),
        api<{ venues: Venue[] }>("/schedule/venues"),
        api<{ events: typeof events }>("/schedule/events"),
      ]);
      setRows(l.disruptions);
      setVenues(vs.venues);
      setEvents(es.events.map((e) => ({ id: e.id, raw_id: e.raw_id, name: e.name, venue_id: e.venue_id })));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function runPreview() {
    setErr("");
    setNotice("");
    const p = payloadOf(dtype, f);
    if (p === null) { setErr("fill the payload fields for this ticket type first"); return; }
    setBusy(true);
    try {
      const out = await api<PreviewResp>("/disruptions/preview", {
        method: "POST",
        body: { type: dtype, payload: { ...p, reason: (f._reason ?? "").trim() || "preview requested from disruption desk" } },
      });
      setPreview({ id: out.disruption_id, type: out.type, report: out.report });
      setF((s) => ({ ...s, _reason: "" }));
      void load();
    } catch (e) {
      setErr(`refused: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function act(kind: "apply" | "revert", id: number, reason: string) {
    setModalBusy(true);
    setModalErr("");
    try {
      const out = await api<ActResp>(`/disruptions/${id}/${kind}`, { method: "POST", body: { reason } });
      setModal(null);
      setNotice(
        kind === "apply"
          ? `disruption #${out.disruption_id} (${out.type}) APPLIED — snapshot stored, revert possible`
          : `disruption #${out.disruption_id} (${out.type}) REVERTED — prior state restored from the snapshot`,
      );
      setSummary({ id: out.disruption_id, type: out.type, what: kind, summary: out.summary });
      setModalBusy(false);
      setPreview(null);
      void load();
    } catch (e) {
      setModalErr(e instanceof Error ? e.message : String(e));
      setModalBusy(false);
    }
  }

  const [summary, setSummary] = useState<{ id: number; type: string; what: string; summary: Record<string, unknown> } | null>(null);

  return (
    <div>
      <PageHeader title="Disruption desk" />
      {notice && (
        <p className="paper mb-3 rounded-sm border-2 border-teal-dark/40 px-3 py-2 text-sm font-semibold text-teal-dark">
          {notice}
        </p>
      )}
      {err && <p className="mb-3 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-cream">{err}</p>}
      {busy && !rows && <Spinner label="waking the war-room…" />}

      {/* preview cards from earlier actions */}
      {summary && (
        <Paper title={`last action — ${summary.what} of #${summary.id} (${summary.type})`}>
          <pre className="overflow-x-auto rounded-sm bg-crimson-dark/10 p-2 text-xs">{JSON.stringify(summary.summary, null, 2)}</pre>
        </Paper>
      )}

      {/* preview report */}
      {preview && (
        <Paper title={`Impact report — disruption #${preview.id} (${preview.type})`}>
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge sev="error">{preview.report.affected.count} affected</Badge>
            <Badge sev={preview.report.new_violations.length ? "warning" : "good"}>
              {preview.report.new_violations.length} new violations
            </Badge>
            <Badge sev="neutral">cost delta: {preview.report.cost_delta}</Badge>
          </div>
          {preview.report.affected.names.length > 0 && (
            <p className="mb-2 text-xs"><strong>affected:</strong> {preview.report.affected.names.join(", ")}</p>
          )}
          {preview.report.state_changes.length > 0 && (
            <details className="mb-2">
              <summary className="cursor-pointer text-xs font-bold uppercase text-ink/60">
                state changes ({preview.report.state_changes.length})
              </summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded-sm bg-crimson-dark/10 p-2 text-xs">
                {JSON.stringify(preview.report.state_changes, null, 2)}
              </pre>
            </details>
          )}
          {preview.report.new_violations.length > 0 && (
            <p className="mb-2 text-xs">
              <strong>violations:</strong>{" "}
              {preview.report.new_violations.map((v) => v.type).join(", ")}
            </p>
          )}
          {preview.report.suggested_actions.length > 0 && (
            <ul className="mb-3 list-inside list-disc text-xs italic text-ink/70">
              {preview.report.suggested_actions.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
          )}
          <button
            onClick={() => { setModalErr(""); setModal({ kind: "apply", id: preview.id, type: preview.type }); }}
            className="rounded-sm bg-crimson-dark px-4 py-2 text-xs font-bold uppercase tracking-wider text-cream hover:bg-crimson-deep">
            apply this — commit the impact ⚠
          </button>
          <p className="mt-1 text-[11px] italic text-ink/60">
            preview stored nothing but the report; apply is the irreversible-looking step (revert snapshot is saved with it)
          </p>
        </Paper>
      )}

      {/* new ticket form */}
      <Paper title="Raise a disruption">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {TICKET_TYPES.map((t) => (
            <button key={t}
              onClick={() => { setDtype(t); setF({}); setErr(""); }}
              className={`rounded-sm border-2 px-2 py-1 text-[11px] font-bold uppercase tracking-wider ${
                dtype === t ? "border-crimson-dark bg-crimson-dark text-cream" : "border-ink/25 text-ink/70 hover:border-crimson-dark/50"
              }`}>
              {t.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <PayloadFields dtype={dtype} f={f} setF={setF} venues={venues} events={events} />
        <label className="mb-1 mt-2 block text-xs font-bold uppercase tracking-wider text-ink/70">
          Why (audited, required)
        </label>
        <textarea
          rows={2}
          value={f._reason ?? ""}
          onChange={(e) => setF((s) => ({ ...s, _reason: e.target.value }))}
          className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-3 py-2 text-sm text-ink"
        />
        <div className="mt-3">
          <button
            onClick={() => void runPreview()}
            disabled={busy}
            className="rounded-sm bg-mustard px-4 py-2 text-xs font-bold uppercase tracking-wider text-crimson-deep hover:bg-saffron disabled:opacity-50">
            preview impact
          </button>
        </div>
      </Paper>

      {/* registry */}
      <Paper title={`Registry (${rows?.length ?? 0}) — every ticket, every status`}>
        <div className="space-y-2">
          {(rows ?? []).map((r) => (
            <div key={r.id} className="rounded-sm border-2 border-crimson-dark/20 bg-white/40 p-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-bold">#{r.id}</span>
                <Badge sev={statusSev[r.status] as "warning" | "error" | "good"}>{r.status}</Badge>
                <span className="text-sm font-semibold">{r.type.replace(/_/g, " ")}</span>
                <span className="ml-auto text-[11px] text-ink/60">
                  {r.applied_by ? `${r.applied_by} @ ${r.applied_at ?? "?"}` : "not applied yet"}
                </span>
              </div>
              <details className="mt-1">
                <summary className="cursor-pointer text-[11px] font-bold uppercase text-teal-dark">
                  payload + impact report
                </summary>
                <pre className="mt-1 max-h-40 overflow-auto rounded-sm bg-crimson-dark/10 p-2 text-xs">
                  {JSON.stringify(r.payload, null, 2)}
                  {r.impact_report ? `\n\ncost_delta: ${r.impact_report.cost_delta}; affected: ${r.impact_report.affected.count}` : ""}
                </pre>
              </details>
              <div className="mt-2 flex gap-2">
                {r.status === "previewed" && (
                  <button
                    onClick={() => { setModalErr(""); setModal({ kind: "apply", id: r.id, type: r.type }); }}
                    className="rounded-sm border border-crimson-dark/50 bg-mustard/40 px-2 py-0.5 text-[10px] font-bold uppercase text-crimson-deep hover:bg-mustard/70">
                    apply ⚠
                  </button>
                )}
                {r.status === "applied" && r.has_snapshot && (
                  <button
                    onClick={() => { setModalErr(""); setModal({ kind: "revert", id: r.id, type: r.type }); }}
                    className="rounded-sm border border-teal-dark/50 bg-teal/20 px-2 py-0.5 text-[10px] font-bold uppercase text-teal-dark hover:bg-teal/40">
                    revert ⇥
                  </button>
                )}
                {r.status === "applied" && !r.has_snapshot && (
                  <span className="text-[10px] font-bold uppercase text-crimson-deep">no snapshot — cannot revert</span>
                )}
              </div>
            </div>
          ))}
          {rows && rows.length === 0 && <p className="text-sm italic text-ink/60">no disruptions raised yet — may it stay that way</p>}
        </div>
      </Paper>

      {modal && (
        <ReasonModal
          title={modal.kind === "apply"
            ? `Apply disruption #${modal.id} (${modal.type}) — real-world impact follows`
            : `Revert disruption #${modal.id} (${modal.type}) — restore from snapshot`}
          description={modal.kind === "apply"
            ? "Engine writes commit now; the pre-apply state is snapshotted so revert stays possible."
            : "The stored snapshot is replayed; nothing is guessed."}
          confirmLabel={modal.kind === "apply" ? "apply for real" : "revert"}
          busy={modalBusy}
          error={modalErr}
          onCancel={() => { setModal(null); setModalErr(""); }}
          onConfirm={(reason) => void act(modal.kind, modal.id, reason)}
        />
      )}
    </div>
  );
}

/* ---------------- payload field construction ---------------- */

export function payloadOf(dtype: string, f: Record<string, string>): Record<string, unknown> | null {
  const p: Record<string, unknown> = {};
  if (dtype === "late_contingent") {
    if (!f.contingent?.trim() || !f.new_arrival?.trim()) return null;
    p.contingent = f.contingent.trim();
    p.new_arrival = f.new_arrival.trim();
  } else if (dtype === "duplicate_record") {
    if (!f.duplicate_raw_id?.trim()) return null;
    p.duplicate_raw_id = f.duplicate_raw_id.trim();
    if (f.canonical_raw_id?.trim()) p.canonical_raw_id = f.canonical_raw_id.trim();
  } else if (dtype === "hostel_closure") {
    if (f.hostel?.trim()) p.hostel = f.hostel.trim();
    else if (f.room_raw_ids?.trim())
      p.room_raw_ids = f.room_raw_ids.split(",").map((s) => s.trim()).filter(Boolean);
    else return null;
  } else if (dtype === "equipment_failure") {
    if (f.sku?.trim()) p.sku = f.sku.trim();
    else if (f.item_id?.trim()) p.item_id = Number(f.item_id);
    else return null;
    if (!f.qty?.trim()) return null;
    p.qty = Number(f.qty);
  } else if (dtype === "venue_change") {
    if (!f.event_raw_id?.trim() || !f.new_venue_id?.trim()) return null;
    p.event_raw_id = f.event_raw_id.trim();
    p.new_venue_id = Number(f.new_venue_id);
  } else if (dtype === "vendor_shutdown") {
    if (!f.vendor_raw_id?.trim()) return null;
    p.raw_id = f.vendor_raw_id.trim();
  } else if (dtype === "duplicate_merch_claim") {
    if (!f.participant_raw_id?.trim()) return null;
    p.participant_raw_id = f.participant_raw_id.trim();
    p.action = f.action || "refuse";
    if (p.action === "reissue" && f.item_id?.trim()) p.item_id = Number(f.item_id);
  } else {
    return null;
  }
  return p;
}

function Inp({ label, f, setF, key_, ...rest }: {
  label: string; f: Record<string, string>; setF: (fn: (s: Record<string, string>) => Record<string, string>) => void; key_: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={rest.className ?? "mb-2 min-w-0 grow"}>
      <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-ink/70">{label}</label>
      <input
        value={f[key_] ?? ""}
        onChange={(e) => setF((s) => ({ ...s, [key_]: e.target.value }))}
        className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm text-ink"
        {...Object.fromEntries(Object.entries(rest).filter(([k]) => k !== "className"))}
      />
    </div>
  );
}

function PayloadFields({ dtype, f, setF, venues, events }: {
  dtype: string; f: Record<string, string>; setF: (fn: (s: Record<string, string>) => Record<string, string>) => void;
  venues: Venue[];
  events: { id: number; raw_id: string; name: string; venue_id: number | null }[];
}) {
  if (dtype === "late_contingent") {
    return (
      <div>
        <Inp label="contingent raw id (which one is late)" key_="contingent" f={f} setF={setF} />
        <Inp label="new arrival (e.g. 2026-10-31T06:00)" key_="new_arrival" f={f} setF={setF} />
        <p className="text-[11px] italic text-ink/60">members land later — arrivals/departures shift and bed windows follow</p>
      </div>
    );
  }
  if (dtype === "duplicate_record") {
    return (
      <div>
        <Inp label="duplicate raw id (the record to link away)" key_="duplicate_raw_id" f={f} setF={setF} />
        <Inp label="canonical raw id (optional — blank lets the engine judge)" key_="canonical_raw_id" f={f} setF={setF} />
        <p className="text-[11px] italic text-ink/60">post-import twin discovered; reversible merge</p>
      </div>
    );
  }
  if (dtype === "hostel_closure") {
    return (
      <div>
        <Inp label="hostel / block name (closes every room in it)" key_="hostel" f={f} setF={setF} />
        <Inp label="— or specific room raw ids, comma-separated" key_="room_raw_ids" f={f} setF={setF} />
        <p className="text-[11px] italic text-ink/60">locked occupants stay untouched; everyone else is rehoused displaced-only</p>
      </div>
    );
  }
  if (dtype === "equipment_failure") {
    return (
      <div>
        <Inp label="sku (e.g. L00-1) — or item id below" key_="sku" f={f} setF={setF} />
        <Inp label="— or numeric item id" key_="item_id" f={f} setF={setF} />
        <Inp label="qty lost" key_="qty" f={f} setF={setF} />
        <p className="text-[11px] italic text-ink/60">movement leaves the ledger as damaged; equipment-demand recheck follows</p>
      </div>
    );
  }
  if (dtype === "venue_change") {
    return (
      <div>
        <div className="mb-2">
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-ink/70">event</label>
          <select
            value={f.event_raw_id ?? ""}
            onChange={(e) => setF((s) => ({ ...s, event_raw_id: e.target.value }))}
            className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm text-ink">
            <option value="">— pick the event —</option>
            {events.map((e) => (
              <option key={e.id} value={e.raw_id}>
                {e.raw_id} {e.name}{e.venue_id ? ` (now venue #${e.venue_id})` : " (unscheduled)"}
              </option>
            ))}
          </select>
        </div>
        <div className="mb-2">
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-ink/70">new venue</label>
          <select
            value={f.new_venue_id ?? ""}
            onChange={(e) => setF((s) => ({ ...s, new_venue_id: e.target.value }))}
            className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm text-ink">
            <option value="">— pick the venue —</option>
            {venues.map((v) => (
              <option key={v.id} value={String(v.id)}>
                {v.raw_id} {v.name}{v.capacity ? ` (cap ${v.capacity})` : ""}
              </option>
            ))}
          </select>
        </div>
        <p className="text-[11px] italic text-ink/60">scheduler re-checks after the move; new conflicts surface immediately</p>
      </div>
    );
  }
  if (dtype === "vendor_shutdown") {
    return (
      <div>
        <Inp label="vendor raw id (e.g. VND05)" key_="vendor_raw_id" f={f} setF={setF} />
        <p className="text-[11px] italic text-ink/60">open orders reroute to compliant alternate vendors; unmet is never dropped</p>
      </div>
    );
  }
  if (dtype === "duplicate_merch_claim") {
    return (
      <div>
        <Inp label="participant raw id claiming twice" key_="participant_raw_id" f={f} setF={setF} />
        <div className="mb-2">
          <label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-ink/70">handling</label>
          <select
            value={f.action ?? "refuse"}
            onChange={(e) => setF((s) => ({ ...s, action: e.target.value }))}
            className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm text-ink">
            <option value="refuse">refuse — flag only</option>
            <option value="reissue">reissue — director overrides a second kit out</option>
          </select>
        </div>
        {f.action === "reissue" && <Inp label="numeric item id to reissue" key_="item_id" f={f} setF={setF} />}
        <p className="text-[11px] italic text-ink/60">claim is judged against the whole dedupe cluster, not the dupe row alone</p>
      </div>
    );
  }
  return null;
}

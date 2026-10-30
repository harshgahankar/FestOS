import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Participant360, ParticipantView } from "../peopleTypes";
import ReasonModal from "../components/ReasonModal";
import { FlagChips, MaskedValue, PageHeader, StatusBadge } from "../components/Listkit";
import { Badge, Btn, Paper, Spinner, Unknown } from "../components/ui";

const EDITABLE: { field: keyof ParticipantView; label: string }[] = [
  { field: "name", label: "name" },
  { field: "age", label: "age" },
  { field: "phone", label: "phone" },
  { field: "email", label: "email" },
  { field: "tshirt_size", label: "t-shirt size" },
  { field: "accessibility_details", label: "accessibility details" },
  { field: "dietary_tags", label: "dietary tags (comma-separated)" },
  { field: "accommodation_requested", label: "accommodation requested" },
];

type Action =
  | { kind: "reveal"; field: keyof ParticipantView }
  | { kind: "edit" }
  | { kind: "merge" };

export default function Participant({ id }: { id: number }) {
  const [data, setData] = useState<Participant360 | null>(null);
  const [error, setError] = useState("");
  const [action, setAction] = useState<Action | null>(null);
  const [actionErr, setActionErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");

  async function load() {
    setError("");
    try {
      setData(await api<Participant360>(`/participants/${id}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    }
  }
  useEffect(() => {
    setRevealed({});
    setMsg("");
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (error)
    return (
      <div>
        <PageHeader title={<span>participant <span className="font-body text-lg opacity-80">#{id}</span></span>} back="/people" />
        <p className="paper rounded-sm border-2 border-saffron bg-crimson-dark/90 p-4 text-sm font-semibold text-cream">refused: {error}</p>
      </div>
    );
  if (!data)
    return <div className="beige p-4"><Spinner label="loading 360° record…" /></div>;

  const p = data.participant;

  async function doReveal(reason: string, field: keyof ParticipantView) {
    if (!action || action.kind !== "reveal") return;
    setBusy(true);
    setActionErr("");
    try {
      const out = await api<{ fields: Record<string, unknown>; audit_entry: number }>(
        `/participants/${id}/reveal`,
        { method: "POST", body: { fields: [field], reason } },
      );
      setRevealed({ ...revealed, [field]: String(out.fields[field] ?? "unknown") });
      setMsg(`"${field}" revealed — reason "${reason}" audited as audit #${out.audit_entry}`);
      setAction(null);
      setBusy(false);
    } catch (e) {
      setActionErr(e instanceof ApiError ? e.detail : String(e));
      setBusy(false);
    }
  }

  async function doEdit(patch: Record<string, unknown>, note: string) {
    setBusy(true);
    setActionErr("");
    try {
      await api(`/participants/${id}`, { method: "PATCH", body: { ...patch, note } });
      setMsg(`saved ${Object.keys(patch).join(", ")} — reason "${note}" audited`);
      setAction(null);
      setBusy(false);
      void load();
    } catch (e) {
      setActionErr(e instanceof ApiError ? e.detail : String(e));
      setBusy(false);
    }
  }

  async function doMerge(dupRawId: string, reason: string) {
    setBusy(true);
    setActionErr("");
    try {
      const out = await api<{ audit_id: number }>("/participants/merge", {
        method: "POST",
        body: { canonical_id: id, duplicate_raw_id: dupRawId, reason },
      });
      setMsg(`${dupRawId} linked into this record — audit #${out.audit_id} added (reversible via unmerge)`);
      setAction(null);
      setBusy(false);
      void load();
    } catch (e) {
      setActionErr(e instanceof ApiError ? e.detail : String(e));
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={<span>participant <span className="font-body text-lg opacity-80">{p.raw_id}</span></span>} back="/people" />

      {msg && (
        <p className="paper mb-3 rounded-sm border-2 border-teal-dark/40 px-3 py-2 text-sm font-semibold text-teal-dark">
          {msg}
        </p>
      )}

      <Paper>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <h3 className="font-display text-xl text-ink">{p.name}</h3>
          <StatusBadge status={p.status} />
          <FlagChips flags={p.quality_flags} />
          <span className="ml-auto flex gap-2">
            <Btn onClick={() => { setActionErr(""); setAction({ kind: "edit" }); }}>edit</Btn>
            {!p.merged_into && (
              <Btn variant="danger" onClick={() => { setActionErr(""); setAction({ kind: "merge" }); }}>
                merge another into this ⧉
              </Btn>
            )}
          </span>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
          <Field label="college" v={p.college} />
          <Field label="contingent" v={p.contingent} mono />
          <Field label="gender" v={p.gender} />
          <Field label="age" v={p.age} />
          <Field label="phone" v={revealed.phone ?? p.phone} onReveal={p.phone === "masked" ? () => { setActionErr(""); setAction({ kind: "reveal", field: "phone" }); } : undefined} />
          <Field label="email" v={revealed.email ?? p.email} onReveal={p.email === "masked" ? () => { setActionErr(""); setAction({ kind: "reveal", field: "email" }); } : undefined} />
          <Field label="access status" v={p.accessibility_status} />
          <Field label="access details" v={revealed.accessibility_details ?? p.accessibility_details} onReveal={p.accessibility_details === "masked" ? () => { setActionErr(""); setAction({ kind: "reveal", field: "accessibility_details" }); } : undefined} />
          <Field label="dietary status" v={p.dietary_status} />
          <Field label="dietary tags" v={revealed.dietary_tags ?? (p.dietary_tags?.length ? p.dietary_tags.join(", ") : "")} onReveal={
            String(p.dietary_tags ?? "") === "masked"
              ? () => { setActionErr(""); setAction({ kind: "reveal", field: "dietary_tags" }); }
              : undefined} />
          <Field label="t-shirt" v={p.tshirt_size} />
          <Field label="arrival" v={p.arrival} />
          <Field label="departure" v={p.departure} />
          <Field label="accom requested" v={p.accommodation_requested} />
          <Field label="room / bed" v={revealed.room ?? (data.bed ?? "")} onReveal={p.room === "masked" && data.bed ? (() => { setActionErr(""); setAction({ kind: "reveal", field: "room" }); }) : undefined} />
          <Field label="merged into" v={p.merged_into === null ? "" : `participant #${p.merged_into}`} />
        </dl>
      </Paper>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Paper title="Contingent">
          {data.contingent ? (
            <ul className="space-y-1 text-sm text-ink/80">
              <li>
                <span className="font-mono text-xs font-bold">{data.contingent.raw_id}</span> · {data.contingent.college}
              </li>
              <li><span className="font-semibold">leader:</span> {data.contingent.leader ?? <Unknown />} · <span className="font-semibold">escort:</span> {data.contingent.escort ?? <Unknown />}</li>
              <li>
                <span className="font-semibold">declared:</span> {data.contingent.size_declared ?? <Unknown />} ·
                <span className="font-semibold"> actual:</span> {data.contingent.size_actual ?? <Unknown />}
                {data.contingent.size_declared !== null && data.contingent.size_actual !== null &&
                  data.contingent.size_declared !== data.contingent.size_actual && (
                    <Badge sev="warning">{"mismatch " + (data.contingent.size_actual - data.contingent.size_declared)}</Badge>
                  )}
              </li>
            </ul>
          ) : (
            <p className="text-sm italic text-ink/60">no contingent is on record — the source row had none, so none is invented here</p>
          )}
        </Paper>

        <Paper title="Events & team registrations">
          {data.events.length ? (
            <ul className="space-y-1 text-sm">
              {data.events.map((e, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs font-bold">{e.event_id}</span>
                  <Badge sev="neutral">{e.role ?? "unknown role"}</Badge>
                  <span className="text-xs text-ink/70">team {e.team_id ? e.team_id : <Unknown />} · {e.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm italic text-ink/60">not registered for any event (cancelled reg rows excluded)</p>
          )}
        </Paper>

        <Paper title="Bed & merch">
          <p className="mb-2 text-sm">
            <span className="font-semibold">room:</span>{" "}
            {revealed.room ? revealed.room : data.bed ? data.bed : <UncastType />}
          </p>
          {data.merch_issued.length ? (
            <ul className="text-sm">
              {data.merch_issued.map((m, i) => (
                <li key={i}><span className="font-mono text-xs font-bold">{m.item_id}</span> · issued {m.at.replace("T", " ")}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm italic text-ink/60">no merch issued to this participant or their canonical record yet</p>
          )}
        </Paper>

        <Paper title="Audit trail (last 20)">
          <ul className="max-h-44 space-y-1 overflow-y-auto pr-1 text-xs">
            {data.audit.map((a, i) => (
              <li key={i} className="border-b border-ink/10 pb-1">
                <span className="font-mono">{a.at.replace("T", " ")}</span> ·{" "}
                <Badge sev={a.kind === "reveal" || a.kind === "override" ? "warning" : "neutral"}>{a.kind ?? "?"}</Badge>{" "}
                {a.actor && <>by <span className="font-semibold">{a.actor}</span> </>}— <span className="italic">{a.reason}</span>
              </li>
            ))}
            {!data.audit.length && <li className="italic text-ink/60">no audit history on this participant yet</li>}
          </ul>
        </Paper>
      </div>

      {/* ---------------------------- action modals ---------------------------- */}
      {action?.kind === "reveal" && (
        <ReasonModal
          title={`Reveal "${action.field}"`}
          description="Unmasked viewing is itself an audited act. Say why this is needed."
          confirmLabel="reveal"
          busy={busy}
          error={actionErr}
          onCancel={() => setAction(null)}
          onConfirm={(reason) => void doReveal(reason, action.field)}
        />
      )}

      {action?.kind === "merge" && (
        <ReasonModal
          title="Merge another record into this one"
          description={`A duplicate becomes linked to ${p.raw_id}. Nothing is deleted — the duplicate stays readable and the merge is reversible.`}
          confirmLabel="link merge"
          busy={busy}
          error={actionErr}
          extra={
            <div className="mb-3">
              <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-ink/70">
                duplicate raw_id (e.g. participant CSV row id)
              </label>
              <input
                id="merge-dup-id"
                className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-3 py-2 text-sm text-ink"
              />
            </div>
          }
          onCancel={() => setAction(null)}
          onConfirm={(reason) => {
            const el = document.getElementById("merge-dup-id") as HTMLInputElement | null;
            const val = (el?.value ?? "").trim();
            if (!val) { setActionErr("supply the duplicate's raw_id from the source CSV"); setBusy(false); return; }
            void doMerge(val, reason);
          }}
        />
      )}

      {action?.kind === "edit" && (
        <EditModal
          view={p} busy={busy} error={actionErr}
          onClose={() => setAction(null)}
          onSave={doEdit}
        />
      )}
    </div>
  );
}

function UncastType() {
  return <span className="text-xs italic text-ink/60">no allocation exists yet — nothing is guessed</span>;
}

function Field({ label, v, mono = false, onReveal }: {
  label: string;
  v: string | number | null | undefined;
  mono?: boolean;
  onReveal?: () => void;
}) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-wider text-ink/60">{label}</dt>
      <dd className={`flex items-center gap-1.5 ${mono ? "font-mono text-xs" : ""}`}>
        <MaskedValue value={v ?? ""} />
        {onReveal && (
          <button
            onClick={onReveal}
            className="rounded-sm border border-teal-dark/50 bg-teal/20 px-1.5 text-[10px] font-bold uppercase text-teal-dark hover:bg-teal/40"
          >
            reveal ✎
          </button>
        )}
      </dd>
    </div>
  );
}

function EditModal({ view, busy, error, onClose, onSave }: {
  view: ParticipantView;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSave: (patch: Record<string, unknown>, note: string) => void;
}) {
  const initial: Record<string, string> = {
    name: view.name ?? "",
    age: view.age == null ? "" : String(view.age),
    phone: view.phone === "masked" ? "leave untouched to keep masked" : view.phone == null ? "" : String(view.phone),
    email: view.email === "masked" ? "leave untouched to keep masked" : view.email ?? "",
    tshirt_size: view.tshirt_size ?? "",
    accessibility_details: view.accessibility_details === "masked" ? "" : view.accessibility_details ?? "",
    dietary_tags: (view.dietary_tags ?? []).join(", "),
    accommodation_requested: view.accommodation_requested ?? "",
  };
  const [form, setForm] = useState(initial);
  const [note, setNote] = useState("");
  const [noteErr, setNoteErr] = useState(false);

  function submit() {
    const patch: Record<string, unknown> = {};
    for (const { field } of EDITABLE) {
      const before = String(initial[field] ?? "");
      const after = String(form[field] ?? "");
      if (field === "phone" && form.phone.startsWith("leave untouched")) continue;
      if (field === "email" && form.email.startsWith("leave untouched")) continue;
      if (before !== after) {
        if (field === "dietary_tags") {
          patch[field] = after.split(",").map((s) => s.trim()).filter(Boolean);
        } else if (field === "age") {
          if (after !== "") patch[field] = Number(after);
        } else {
          patch[field] = after;
        }
      }
    }
    if (Object.keys(patch).length === 0) { onClose(); return; }
    if (!note.trim()) { setNoteErr(true); return; }
    onSave(patch, note.trim());
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-crimson-dark/70 p-4" onClick={onClose}>
      <div className="paper torn-b relative max-h-[85vh] w-full max-w-md overflow-y-auto rounded-sm border-2 border-crimson-dark/50 p-5 pb-7 shadow-[0_10px_0_rgba(64,16,18,0.5)]" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display mb-1 text-xl text-ink">Edit — audited field change</h3>
        <p className="mb-3 text-sm text-ink/75">
          only fields you actually change are sent; before/after and your note land in the audit log
        </p>
        {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">refused: {error}</p>}
        <div className="space-y-2">
          {EDITABLE.filter((f) => {
            if (f.field === "phone" && view.phone === "masked") return false;
            if (f.field === "email" && view.email === "masked") return false;
            return true;
          }).map(({ field, label }) => (
            <label key={field} className="block text-xs font-bold uppercase text-ink/70">
              {label}
              <input
                value={form[field]}
                onChange={(e) => setForm({ ...form, [field]: e.target.value })}
                className={`mt-0.5 ${field === "dietary_tags" ? "w-full" : "w-full"} rounded-sm border-2 ${" "}border-teal-dark/40 bg-white/60 px-3 py-1.5 text-sm font-normal text-ink normal-case tracking-normal`}
              />
            </label>
          ))}
        </div>
        <label className="mt-3 block text-xs font-bold uppercase text-ink/70">
          Reason (required, audited)
          <textarea value={note} onChange={(e) => { setNote(e.target.value); setNoteErr(false); }} rows={2}
            className={`mt-0.5 w-full rounded-sm border-2 bg-white/60 px-3 py-1.5 text-sm font-normal text-ink ${noteErr ? "border-saffron" : "border-teal-dark/40"}`} />
        </label>
        {noteErr && <p className="text-xs font-bold text-crimson-deep">a reason is required — writes without reasons are refused</p>}
        <div className="mt-3 flex justify-end gap-2">
          <Btn variant="ghost" className="!border-ink/30 !text-ink/80" onClick={onClose}>cancel</Btn>
          <Btn disabled={busy} onClick={submit}>{busy ? "saving…" : "save"}</Btn>
        </div>
      </div>
    </div>
  );
}




import { useState } from "react";
import { api } from "../api";
import type { AllocateResp, Explain } from "../accomTypes";
import { AutoLoader } from "../accomData";
import ReasonModal from "../components/ReasonModal";
import { PageHeader } from "../components/Listkit";
import { Badge, Btn, Paper, Unknown } from "../components/ui";

const PRESETS = ["min_cost", "max_cohesion", "balanced"] as const;

const PRESET_LABELS: Record<string, string> = {
  min_cost: "Lowest cost",
  max_cohesion: "Keep groups together",
  balanced: "Balanced",
};

const PRESET_DESCS: Record<string, string> = {
  min_cost: "cheapest stays first — contingents may be split",
  max_cohesion: "same floor & rooms kept together; biggest stay first",
  balanced: "cheapest first, but prefers same floor & groups together",
};

type Modal =
  | { kind: "lock"; planId: string }
  | { kind: "assign" }
  | null;

export default function Accommodation() {
  const [notice, setNotice] = useState("");
  const [alloc, setAlloc] = useState<AllocateResp | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [modalBusy, setModalBusy] = useState(false);
  const [modalErr, setModalErr] = useState("");
  const [planId, setPlanId] = useState("");

  async function generate(preset: string, reason: string) {
    setGenBusy(true);
    try {
      const out = await api<AllocateResp>("/accommodation/allocate", {
        method: "POST",
        body: { preset, reason },
      });
      setAlloc(out);
      setPlanId(String(out.plan_id));
      setNotice(
        `draft plan #${out.plan_id} generated (${preset}) — summary audited as #${out.audit_entry}. ` +
        `beds are untouched until you activate.`,
      );
    } catch (e) {
      setNotice(`refused: ${msg(e)}`);
    } finally {
      setGenBusy(false);
    }
  }

  async function activate() {
    if (!planId) { setNotice("refused: give a plan id first"); return; }
    try {
      const out = await api<{ plan_id: number; status: string; allocations: number }>(
        `/accommodation/plan/${planId}/activate`, { method: "POST" });
      setNotice(
        `plan #${out.plan_id} is ${out.status} — ${out.allocations} allocations are now live. ` +
        `previous active plan, if any, was superseded.`,
      );
    } catch (e) {
      setNotice(`refused: ${msg(e)}`);
    }
  }

  async function lockAll(planIdArg: string, reason: string) {
    setModalBusy(true);
    setModalErr("");
    try {
      const out = await api<{ plan_id: number; locked: number }>(`/accommodation/plan/${planIdArg}/lock`, {
        method: "POST",
        body: { reason },
      });
      setModal(null);
      setNotice(`plan #${out.plan_id} locked — ${out.locked} allocations frozen against regeneration (reason kept)`);
    } catch (e) {
      setModalErr(msg(e));
    } finally {
      setModalBusy(false);
    }
  }

  async function doAssign(reason: string) {
    const pid = (el("assign-pid")?.value ?? "").trim();
    const room = (el("assign-room")?.value ?? "").trim();
    const ext = (el("assign-ext")?.value ?? "").trim();
    if (!/^\d+$/.test(pid)) { setModalErr("participant id must be numeric (see People 360°)"); return; }
    if (!room && !ext) { setModalErr("supply a room id or an external stay id"); return; }
    if (room && ext) { setModalErr("give exactly one of room id / external stay id"); return; }
    setModalBusy(true);
    setModalErr("");
    const body: Record<string, unknown> = { participant_id: Number(pid), reason };
    if (room) body.room_id = Number(room);
    if (ext) body.external_stay_id = Number(ext);
    try {
      const out = await api<{ allocation_id: number; raw_id: string; audit_entry: number }>(
        "/accommodation/assign", { method: "POST", body });
      setModal(null);
      setNotice(`assigned ${out.raw_id} — allocation #${out.allocation_id} (locked override), audit #${out.audit_entry}`);
    } catch (e) {
      setModalErr(msg(e));
    } finally {
      setModalBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="Accommodation" />
      {notice && (
        <p className="paper mb-3 rounded-sm border-2 border-teal-dark/40 px-3 py-2 text-sm font-semibold text-teal-dark">
          {notice}
        </p>
      )}
      <div className="space-y-3">
        <Paper title="Runbook — generate a draft, then activate, then lock">
          <AllocateForm busy={genBusy} onRun={generate} />
          {alloc && <PlanCard plan={alloc} />}
          <LifecycleRow planId={planId} onChangeId={setPlanId} onActivate={activate} onLock={(id) => { setModalErr(""); setModal({ kind: "lock", planId: id }); }} />
        </Paper>

        <div className="grid gap-3 lg:grid-cols-2">
          <Paper title="Beds check" className="flex flex-col">
            <AutoLoader url="/accommodation/shortage">
              {(d) => (
                <div className="flex flex-1 items-center">
                  <ShortageView d={d as Record<string, number>} />
                </div>
              )}
            </AutoLoader>
          </Paper>
          <Paper title="Review queue — unclear gender/consent needs a human">
            <AutoLoader url="/accommodation/review-queue">
              {(d) => <QueueView d={d as { count: number; review_queue: { participant_id: number; raw_id: string | null; reason_code: string; reason: string }[] }} />}
            </AutoLoader>
          </Paper>
        </div>

        <ExplainPanel />
        <Paper title="Manual single-bed change (audited override)">
          <p className="mb-2 text-sm text-ink/80">
            Overrides one participant's bed with a mandatory reason. Merged duplicates are refused — assign the canonical record.
          </p>
          <Btn variant="danger" onClick={() => { setModalErr(""); setModal({ kind: "assign" }); }}>
            open assign form ⧉
          </Btn>
        </Paper>
      </div>

      {modal?.kind === "lock" && (
        <ReasonModal
          title={`Lock all beds of plan ${modal.planId}`}
          description="Locks every allocation of that active plan against automated regeneration."
          confirmLabel="lock"
          busy={modalBusy}
          error={modalErr}
          onCancel={() => { setModal(null); setModalErr(""); }}
          onConfirm={(reason) => void lockAll(modal.planId, reason)}
        />
      )}

      {modal?.kind === "assign" && (
        <ReasonModal
          title="Manual bed assignment (override)"
          description="A single participant is moved directly. The override is itself locked and fully audited."
          confirmLabel="assign"
          busy={modalBusy}
          error={modalErr}
          extra={<AssignInputs />}
          onCancel={() => { setModal(null); setModalErr(""); }}
          onConfirm={(reason) => void doAssign(reason)}
        />
      )}
    </div>
  );
}

/* helper strips the obvious server prefixes for display if any */
function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
function el(id: string): HTMLInputElement | null {
  return document.getElementById(id) as HTMLInputElement | null;
}

function AllocateForm({ busy, onRun }: { busy: boolean; onRun: (preset: string, reason: string) => Promise<void> }) {
  const [preset, setPreset] = useState<(typeof PRESETS)[number]>("min_cost");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState(false);
  return (
    <div className="mb-4 flex flex-wrap items-end gap-2">
      <label className="text-xs font-bold uppercase text-ink/70">
        preset
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value as (typeof PRESETS)[number])}
          className="mt-1 block rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink normal-case tracking-normal"
        >
          {PRESETS.map((p) => <option key={p} value={p}>{PRESET_LABELS[p]} — {PRESET_DESCS[p]}</option>)}
        </select>
      </label>
      <label className="min-w-[16rem] flex-1 text-xs font-bold uppercase text-ink/70">
        Reason (required, audited)
        <input
          value={reason}
          onChange={(e) => { setReason(e.target.value); setErr(false); }}
          placeholder="e.g. annual pre-fest regeneration after roster freeze"
          className={`mt-1 w-full rounded-sm border-2 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink tracking-normal normal-case ${err ? "border-saffron" : "border-teal-dark/40"}`}
        />
      </label>
      <Btn
        disabled={busy}
        onClick={() => (reason.trim() ? void onRun(preset, reason.trim()) : setErr(true))}
      >
        {busy ? "running allocator…" : "generate draft"}
      </Btn>
    </div>
  );
}

function PlanCard({ plan }: { plan: AllocateResp }) {
  const s = plan.summary;
  return (
    <div className="mb-3 rounded-sm border-2 border-teal-dark/40 bg-white/55 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge sev="info">plan #{plan.plan_id}</Badge>
        <Badge sev="neutral">{PRESET_LABELS[plan.preset] ?? plan.preset}</Badge>
        <Badge sev={plan.violations.length ? "error" : "good"}>
          {plan.violations.length ? `${plan.violations.length} violations` : "no violations"}
        </Badge>
        <span className="text-xs font-semibold text-ink/70">cost ₹{plan.cost}</span>
        <span className="text-xs text-ink/60">audit #{plan.audit_entry}</span>
      </div>
      <div className="grid grid-cols-3 gap-4 sm:grid-cols-5">
        <Mini n={s.requested} l="requests" />
        <Mini n={s.hostel_beds_used} l="hostel beds" />
        <Mini n={s.external_beds_used} l="external beds" />
        <Mini n={s.unplaced} l="unplaced" bad={!!s.unplaced} />
        <Mini n={s.review_queue} l="review queue" bad={!!s.review_queue} />
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-bold uppercase text-teal-dark">
          review queue ({plan.review_queue.length}) · violations ({plan.violations.length}) · unplaced ({plan.unplaced.length})
        </summary>
        <div className="mt-2 grid gap-3 lg:grid-cols-3">
          <List title="review queue — a human decides (unclear gender / consent)"
            rows={plan.review_queue.map((q) => [q.raw_id ?? `#${q.participant_id}`, `${q.reason_code} — ${q.reason}`])} />
          <List title="violations — pinned allocations that could not stand"
            rows={plan.violations.map((v) => [`#${v.participant_id}`, `${v.type}: ${v.message}`])} />
          <List title="unplaced — no bed found; a procurement or decision is needed"
            rows={plan.unplaced.map((u) => [u.raw_id ?? `#${u.participant_id}`, `${u.reason_code} — ${u.reason}`])} />
        </div>
      </details>
    </div>
  );
}

function LifecycleRow({ planId, onChangeId, onActivate, onLock }: {
  planId: string;
  onChangeId: (v: string) => void;
  onActivate: () => Promise<void>;
  onLock: (planId: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-x-4 gap-y-3 rounded-sm border border-ink/20 bg-white/40 p-3">
      <label className="text-xs font-bold uppercase text-ink/70">
        plan id
        <input value={planId} onChange={(e) => { onChangeId(e.target.value); setErr(""); }}
          className="mt-1 block w-24 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink" />
      </label>
      <Btn disabled={busy} onClick={() => { setBusy(true); onActivate().finally(() => setBusy(false)); }}>
        activate → live beds
      </Btn>
      <Btn variant="danger" onClick={() => planId ? onLock(planId) : setErr("give a plan id first")}>
        lock all beds 🔒
      </Btn>
      {err && <span className="text-sm font-semibold text-crimson-deep">refused: {err}</span>}
    </div>
  );
}

function ShortageView({ d }: { d: Record<string, number> }) {
  return (
    <div className="grid h-full auto-rows-fr grid-cols-2 gap-4 sm:grid-cols-4">
      <Mini n={d.requested_count ?? 0} l="requested" />
      <Mini n={d.hostel_beds_used ?? 0} l="hostel used" />
      <Mini n={d.external_beds_used ?? 0} l="external used" />
      <Mini n={d.unmet_count ?? 0} l="unmet" bad={!!(d.unmet_count)} />
    </div>
  );
}

function QueueView({ d }: { d: { count: number; review_queue: { participant_id: number; raw_id: string | null; reason_code: string; reason: string }[] } }) {
  if (!d.count) return <p className="text-sm italic text-ink/60">clear — nothing is waiting on a human decision</p>;
  return (
    <ul className="max-h-40 space-y-1 overflow-y-auto pr-1 text-xs">
      {d.review_queue.map((r) => (
        <li key={r.participant_id} className="border-b border-ink/10 pb-1">
          <span className="font-mono font-bold">{r.raw_id ?? `#${r.participant_id}`}</span>{" "}
          <Badge sev="warning">{r.reason_code}</Badge>{" "}
          <span className="italic">{r.reason}</span>
        </li>
      ))}
    </ul>
  );
}

function ExplainPanel() {
  const [pid, setPid] = useState("");
  const [data, setData] = useState<Explain | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function go() {
    if (!/^\d+$/.test(pid)) { setErr("enter the numeric participant id (shown on the People 360° page)"); return; }
    setBusy(true); setErr("");
    try {
      setData(await api<Explain>(`/accommodation/explain/${pid}`));
    } catch (e) {
      setErr(msg(e));
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper title="Why this bed? — allocation explain">
      <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); void go(); }}>
        <label className="text-xs font-bold uppercase text-ink/70">
          participant id
          <input value={pid} onChange={(e) => { setPid(e.target.value); setErr(""); }}
            className="mt-1 block w-32 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
        </label>
        <Btn type="submit" disabled={busy}>explain</Btn>
      </form>
      {err && <p className="mt-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {err}</p>}
      {busy && <p className="mt-2 text-sm italic text-ink/60">looking up…</p>}
      {data && (
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
          <F2 label="room" v={data.room_id === null ? "hostel only via external" : `room ${data.room_id}`} />
          <F2 label="external stay" v={data.external_stay_id === null ? "" : `stay #${data.external_stay_id}`} />
          <F2 label="source" v={data.source} />
          <F2 label="cost" v={data.cost === null ? "" : `₹${data.cost}`} />
          <F2 label="plan" v={data.plan_id === null ? "" : `#${data.plan_id}`} />
          <F2 label="locked" v={data.locked ? "yes — stays put" : "no"} />
          <div className="col-span-2 sm:col-span-4">
            <dt className="text-[10px] font-bold uppercase text-ink/60">reason kept from the assignment</dt>
            <dd className="italic">{data.reason || <Unknown />}</dd>
          </div>
        </dl>
      )}
    </Paper>
  );
}

function F2({ label, v }: { label: string; v: string }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase text-ink/60">{label}</dt>
      <dd>{v === "" ? <Unknown /> : v}</dd>
    </div>
  );
}

function Mini({ n, l, bad = false }: { n: number; l: string; bad?: boolean }) {
  return (
    <div className={`flex h-full flex-col items-center justify-center rounded-sm border-2 px-3 py-4 text-center shadow-xs ${bad ? "border-crimson-dark/40 bg-mustard/25" : "border-crimson-dark/20 bg-white/50"}`}>
      <p className="font-display text-3xl text-ink">{n}</p>
      <p className="mt-1 text-[11px] font-bold uppercase tracking-wider text-ink/60">{l}</p>
    </div>
  );
}

function List({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div>
      <p className="mb-1 text-xs font-bold uppercase text-ink/70">{title}</p>
      <ul className="max-h-36 space-y-1 overflow-y-auto text-xs">
        {rows.length === 0 && <li className="italic text-ink/60">none</li>}
        {rows.map(([a, b], i) => (
          <li key={i} className="border-b border-ink/10 pb-0.5">
            <span className="font-mono font-bold">{a}</span> — {b}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AssignInputs() {
  return (
    <div className="mb-3 grid grid-cols-2 gap-2">
      <label className="text-xs font-bold uppercase text-ink/70">
        participant id
        <input id="assign-pid" className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
      </label>
      <label className="text-xs font-bold uppercase text-ink/70">
        room id <span className="font-normal normal-case">(or leave blank)</span>
        <input id="assign-room" className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
      </label>
      <label className="col-span-2 text-xs font-bold uppercase text-ink/70">
        external stay id <span className="font-normal normal-case">(if room left blank)</span>
        <input id="assign-ext" className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
      </label>
    </div>
  );
}

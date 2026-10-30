import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "../auth";
import { api } from "../api";
import type { IssueResp, Levels, Shortfall } from "../invTypes";
import { PageHeader } from "../components/Listkit";
import { Badge, Btn, Paper, Spinner, Unknown } from "../components/ui";

const IN = new Set(["director", "logistics_lead"]);

export default function Inventory() {
  const { user } = useAuth();
  const role = user?.role ?? "viewer";
  return (
    <div>
      <PageHeader title="Inventory & Merch desk" />
      <div className="space-y-3">
        {IN.has(role) ? (
          <div className="grid gap-3 lg:grid-cols-2">
            <LevelsPanel />
            <ShortfallPanel />
          </div>
        ) : (
          <p className="paper rounded-sm border-2 border-crimson-dark/30 p-3 text-sm text-ink/70">
            Stock levels and shortfall are logistics_lead / director areas. Volunteers: use the issue desk below.
          </p>
        )}
        <IssueDesk role={role} />
      </div>
    </div>
  );
}

/* ------------------------------- stock levels ------------------------------ */

function LevelsPanel() {
  const [data, setData] = useState<Levels | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({ item: "", qty: "", to: "", status: "", ref: "" });
  const [formErr, setFormErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      setData(await api<Levels>("/inventory/levels"));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function move(e: FormEvent) {
    e.preventDefault();
    const item = Number(form.item);
    const qty = Number(form.qty);
    if (!item) { setFormErr("pick an item"); return; }
    if (!qty) { setFormErr("qty must be non-zero — positive adds stock, negative removes"); return; }
    setFormErr("");
    try {
      const body: Record<string, unknown> = { item_id: item, qty };
      if (form.to) body.to_location = form.to;
      if (form.status) body.status = form.status;
      if (form.ref) body.reference = form.ref;
      const out = await api<{ movement_id: number; sku: string; audit_entry: number }>(
        "/inventory/movements", { method: "POST", body });
      setNotice(`movement #${out.movement_id} booked (${out.sku} × ${qty}) — audit #${out.audit_entry}`);
      setForm({ item: "", qty: "", to: "", status: "", ref: "" });
      void load();
    } catch (e2) {
      setFormErr(e2 instanceof Error ? e2.message : String(e2));
    }
  }

  return (
    <Paper title="Stock levels — derived from the movement ledger, never overwritten">
      {err && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {err}</p>}
      {busy && <Spinner label="counting the shelves…" />}
      {data && (
        <>
          {data.negative.length > 0 && (
            <p className="mb-2 rounded-sm border border-mustard bg-mustard/30 px-2 py-1.5 text-xs font-bold text-ink">
              negative stock (ledger is honest, never fabricated): {data.negative.join(", ")}
            </p>
          )}
          <div className="max-h-60 overflow-y-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="sticky top-0 bg-crimson-dark/10 text-[10px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-1.5">sku</th><th className="px-2 py-1.5">name</th>
                  <th className="px-2 py-1.5">kind</th><th className="px-2 py-1.5">size</th>
                  <th className="px-2 py-1.5">cond</th><th className="px-2 py-1.5">qty</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((it) => (
                  <tr key={it.id} className="border-b border-ink/10">
                    <td className="px-2 py-1 font-mono text-[11px]">{it.sku}</td>
                    <td className="px-2 py-1 text-xs font-semibold">{it.name}</td>
                    <td className="px-2 py-1 text-[11px]">{it.kind}</td>
                    <td className="px-2 py-1 text-[11px]">{it.size ?? <Unknown />}</td>
                    <td className="px-2 py-1 text-[11px]">{it.condition ?? <Unknown />}</td>
                    <td className={`px-2 py-1 text-xs font-bold ${it.qty < 0 ? "text-crimson-deep" : it.qty === 0 ? "text-ink/60" : ""}`}>
                      {it.qty}{it.qty < 0 ? " ⚠" : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form className="mt-3 grid grid-cols-2 gap-2" onSubmit={move}>
            <label className="text-xs font-bold uppercase text-ink/70">
              item
              <select value={form.item} onChange={(e) => setForm({ ...form, item: e.target.value })}
                className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-xs font-normal text-ink normal-case tracking-normal">
                <option value="">— pick —</option>
                {data.items.map((it) =>
                  <option key={it.id} value={it.id}>{it.sku} · {it.name}{it.size ? ` (${it.size})` : ""}</option>)}
              </select>
            </label>
            <label className="text-xs font-bold uppercase text-ink/70">
              qty (+in / −out)
              <input value={form.qty} onChange={(e) => setForm({ ...form, qty: e.target.value })}
                className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
            </label>
            <label className="text-xs font-bold uppercase text-ink/70">
              to location (optional)
              <input value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })}
                className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-xs font-normal text-ink normal-case tracking-normal" />
            </label>
            <label className="text-xs font-bold uppercase text-ink/70">
              status (optional: damaged/return…)
              <input value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-xs font-normal text-ink normal-case tracking-normal" />
            </label>
            <label className="col-span-2 text-xs font-bold uppercase text-ink/70">
              reference (the audited reason)
              <input value={form.ref} onChange={(e) => setForm({ ...form, ref: e.target.value })}
                placeholder="e.g. shipment SH-12 received / issued for decor build"
                className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-xs font-normal text-ink normal-case tracking-normal" />
            </label>
            {formErr && <p className="col-span-2 text-xs font-bold text-crimson-deep">refused: {formErr}</p>}
            {notice && <p className="col-span-2 rounded-sm border-2 border-teal-dark/40 px-2 py-1.5 text-xs font-semibold text-teal-dark">{notice}</p>}
            <Btn type="submit" className="col-span-2 !px-3">book movement</Btn>
          </form>
        </>
      )}
    </Paper>
  );
}

/* -------------------------------- shortfall -------------------------------- */

function ShortfallPanel() {
  const [data, setData] = useState<Shortfall | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<Shortfall>("/merch/shortfall")
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <Paper title="T-shirt shortfall — demand vs derived stock (cluster-aware)">
      {err && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {err}</p>}
      {!err && !data && <Spinner label="counting demand…" />}
      {data && (
        <>
          <p className="mb-2 text-xs font-semibold text-ink/70">
            issued-guard pairs already handled: {data.issued_guard}
          </p>
          <div className="grid grid-cols-2 gap-2 xs:grid-cols-3">
            <div className="rounded-sm border-2 border-crimson-dark/20 bg-white/50 p-2">
              <p className="text-[10px] font-bold uppercase text-ink/60">sizes demanded</p>
              {Object.entries(data.demand).map(([s, n]) => (
                <p key={s} className="text-xs">{s}: <strong>{n}</strong> (stock {data.stock[s] ?? 0})</p>
              ))}
              {Object.keys(data.demand).length === 0 && <p className="text-xs italic text-ink/60">no demand computed</p>}
            </div>
          </div>
          <p className="mt-3 mb-1 text-[10px] font-bold uppercase text-ink/60">short of stock</p>
          {Object.keys(data.shortfall).length === 0 ? (
            <p className="text-sm italic text-ink/60">no size is short — demand covered</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.shortfall).map(([size, s]) => (
                <Badge key={size} sev="warning">
                  {size}: need {s.needed} · stock {s.stock} · short {s.missing}
                </Badge>
              ))}
            </div>
          )}
        </>
      )}
    </Paper>
  );
}

/* ------------------------------- merch desk -------------------------------- */

/** Issue-once-per-cluster flow: 409 from the backend offers a force path for directors. */
function IssueDesk({ role }: { role: string }) {
  const [rawId, setRawId] = useState("");
  const [itemId, setItemId] = useState("");
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<IssueResp | null>(null);
  const [err, setErr] = useState("");
  const [conflict, setConflict] = useState("");
  const [busy, setBusy] = useState(false);
  const isDirector = role === "director";

  async function issue(force = false) {
    if (!rawId.trim()) { setErr("participant raw_id is required (the CSV row id)"); return; }
    if (!reason.trim()) { setErr("a reason is required — writes are refused without one"); return; }
    setBusy(true);
    setErr("");
    const body: Record<string, unknown> = {
      participant_raw_id: rawId.trim(),
      force,
      reason: force ? `${reason.trim()} (forced re-issue)` : reason.trim(),
    };
    if (itemId) body.item_id = Number(itemId);
    try {
      const out = await api<IssueResp>("/merch/issue", { method: "POST", body });
      setResult(out);
      setConflict("");
      setRawId("");
      setItemId("");
      setReason("");
    } catch (e) {
      const m = e instanceof Error ? e.message : String(e);
      setResult(null);
      if (/already received|force/.test(m)) setConflict(m);
      else setErr(m);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper title="Merch issue desk — one item per cluster; duplicates refused unless forced">
      <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); void issue(false); }}>
        <label className="text-xs font-bold uppercase text-ink/70">
          participant raw_id
          <input value={rawId} onChange={(e) => { setRawId(e.target.value); setErr(""); }}
            placeholder="as in the source CSV, e.g. P001"
            className="mt-1 block w-44 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
        </label>
        <label className="text-xs font-bold uppercase text-ink/70">
          item id <span className="font-normal normal-case">(blank = auto T-shirt by their size)</span>
          <input value={itemId} onChange={(e) => setItemId(e.target.value)}
            className="mt-1 block w-24 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink" />
        </label>
        <label className="min-w-[14rem] flex-1 text-xs font-bold uppercase text-ink/70">
          Reason (required, audited)
          <input value={reason} onChange={(e) => { setReason(e.target.value); setErr(""); }}
            placeholder="handed out at contingent check-in"
            className="mt-1 w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1.5 text-sm font-normal text-ink tracking-normal normal-case" />
        </label>
        <Btn type="submit" disabled={busy}>{busy ? "issuing…" : "issue"}</Btn>
      </form>

      {err && <p className="mt-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {err}</p>}

      {conflict && (
        <div className="mt-2 rounded-sm border-2 border-crimson-dark/40 bg-mustard/25 p-2.5">
          <p className="text-sm font-bold text-crimson-deep">system refused: <span className="font-normal">{conflict}</span></p>
          <p className="mt-1 text-xs italic text-ink/70">
            {isDirector
              ? "as director you may force a re-issue; it will be flagged in the audit trail."
              : "a director can force a re-issue with a reason — volunteers cannot. Nothing changed."}
          </p>
          {isDirector && (
            <Btn variant="danger" className="mt-2 !px-3" disabled={busy} onClick={() => void issue(true)}>
              force re-issue ⚠
            </Btn>
          )}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-sm border-2 border-teal-dark/40 bg-white/55 p-3 text-sm">
          <Badge sev="good">issued</Badge>{" "}
          <span className="font-semibold">{result.canonical}</span> · {result.item.sku}
          {result.item.size ? ` (size ${result.item.size})` : ""} · issue #{result.issue_id} · audit #{result.audit_entry}
        </div>
      )}
    </Paper>
  );
}

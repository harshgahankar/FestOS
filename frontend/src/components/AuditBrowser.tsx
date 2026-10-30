import { useEffect, useState } from "react";
import { api } from "../api";
import type { AuditEntry, AuditResp } from "../types";
import { Badge, Btn, Paper, Spinner, Unknown } from "./ui";
import type { Severity } from "./ui";

const PAGE = 50;

const DEFAULT_FILTERS = { entity_type: "", entity_id: "", actor: "", kind: "" };

/** changed keys of before -> after; every audit row shows honest before/after */
function diff(before: Record<string, unknown> | null, after: Record<string, unknown> | null) {
  const keys = new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]);
  const out: { key: string; from: string; to: string }[] = [];
  for (const k of keys) {
    const f = JSON.stringify(before?.[k]) ?? "undefined";
    const t = JSON.stringify(after?.[k]) ?? "undefined";
    if (f !== t) out.push({ key: k, from: f, to: t });
  }
  return out;
}

function EntryRow({ e }: { e: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const rows = diff(e.before, e.after);
  const sev: Severity = e.kind === "override" || e.kind === "disruption" ? "error" : e.kind === "delete" ? "warning" : "neutral";
  return (
    <>
      <tr className="cursor-pointer border-b border-ink/10 align-top hover:bg-mustard/20" onClick={() => setOpen(!open)}>
        <td className="px-2 py-1.5 text-xs">{e.at ? e.at.replace("T", " ") : <Unknown />}</td>
        <td className="px-2 py-1.5 text-xs font-semibold">{e.actor ?? <Unknown />}</td>
        <td className="px-2 py-1.5 text-xs">{e.action ?? <Unknown />}</td>
        <td className="px-2 py-1.5"><Badge sev={e.kind === "import" ? "neutral" : sev}>{e.kind ?? "?"}</Badge></td>
        <td className="px-2 py-1.5 text-xs font-mono">{e.entity_type}:{e.entity_id}</td>
        <td className="px-2 py-1.5 text-xs italic">{e.reason || <span className="text-ink/40">—</span>}</td>
      </tr>
      {open && (
        <tr className="bg-crimson-dark/5">
          <td colSpan={6} className="px-4 py-2">
            {rows.length === 0 ? (
              <p className="text-xs text-ink/60 italic">no field-level change recorded for this entry</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-ink/60">
                    <th className="pb-1">field</th><th className="pb-1">before</th><th className="pb-1">after</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.key} className="border-t border-ink/10">
                      <td className="py-1 font-mono font-bold pr-2">{r.key}</td>
                      <td className="py-1 font-mono text-crimson-deep pr-2 max-w-[18rem] break-all">{r.from}</td>
                      <td className="py-1 font-mono text-teal-dark max-w-[18rem] break-all">{r.to}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function AuditBrowser() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [active, setActive] = useState(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<AuditResp | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(f: typeof DEFAULT_FILTERS, off: number) {
    setBusy(true);
    setError("");
    try {
      const p = new URLSearchParams({ limit: String(PAGE), offset: String(off) });
      for (const [k, v] of Object.entries(f)) if (v) p.set(k, v);
      setData(await api<AuditResp>(`/control/audit?${p}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(DEFAULT_FILTERS, 0); }, []);

  const total = data?.total ?? 0;

  return (
    <Paper title="Audit trail — append-only, every write with its reason">
      <form
        className="mb-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setOffset(0);
          setActive(filters);
          void load(filters, 0);
        }}
      >
        {(["entity_type", "entity_id", "actor", "kind"] as const).map((k) => (
          <label key={k} className="text-xs font-bold uppercase tracking-wider text-ink/70">
            {k.replace("_", " ")}
            <input
              value={filters[k]}
              onChange={(ev) => setFilters({ ...filters, [k]: ev.target.value })}
              className="mt-1 w-36 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink"
            />
          </label>
        ))}
        <Btn type="submit">apply</Btn>
      </form>

      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">{error}</p>}
      {busy && <Spinner label="reading the ledger…" />}

      {data && (
        <>
          <p className="mb-2 text-xs font-semibold text-ink/70">
            {total} entries — showing {offset + 1}–{Math.min(offset + PAGE, total)}
          </p>
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-2">at</th><th className="px-2 py-2">actor</th><th className="px-2 py-2">action</th>
                  <th className="px-2 py-2">kind</th><th className="px-2 py-2">entity</th><th className="px-2 py-2">reason</th>
                </tr>
              </thead>
              <tbody>{data.entries.map((e) => <EntryRow key={e.id} e={e} />)}</tbody>
            </table>
          </div>
          <div className="mt-3 flex gap-2">
            <Btn variant="ghost" disabled={offset === 0 || busy}
              onClick={() => { const o = Math.max(0, offset - PAGE); setOffset(o); void load(active, o); }}>
              ← prev
            </Btn>
            <Btn variant="ghost" disabled={offset + PAGE >= total || busy}
              onClick={() => { const o = offset + PAGE; setOffset(o); void load(active, o); }}>
              next →
            </Btn>
          </div>
        </>
      )}
    </Paper>
  );
}

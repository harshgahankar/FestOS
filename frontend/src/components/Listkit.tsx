import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import { Badge, Unknown } from "./ui";
import type { Severity } from "./ui";

const STATUS_SEV: Record<string, Severity> = {
  active: "good", flagged: "warning", quarantined: "error", duplicate: "neutral", cancelled: "neutral",
};

export function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <Unknown />;
  return <Badge sev={STATUS_SEV[status] ?? "neutral"}>{status}</Badge>;
}

export function FlagChips({ flags }: { flags: string[] | null }) {
  if (!flags?.length) return null;
  return (
    <span className="flex flex-wrap gap-1">
      {flags.map((f) => (
        <span key={f} className={`rounded-sm px-1.5 text-[10px] font-bold uppercase tracking-wide ${
          f === "DUPLICATE_LINKED" ? "bg-teal/30 text-teal-dark" : "bg-mustard/60 text-ink"}`}>
          {f.toLowerCase()}
        </span>
      ))}
    </span>
  );
}

/** Value cell: honest handling — "unknown" stays unknown, "masked" gets a lock. */
export function MaskedValue({ value }: { value: string | number | null }) {
  const v = value ?? "";
  if (v === "unknown") return <Unknown />;
  if (v === "masked")
    return (
      <span className="inline-flex items-center gap-1 rounded-sm border border-ink/30 bg-ink/10 px-1.5 py-0 text-[11px] font-bold text-ink/70">
        locked 🔒
      </span>
    );
  return <>{String(v).length ? v : <Unknown />}</>;
}

export function Pager({ total, limit, offset, onPage }: {
  total: number; limit: number; offset: number; onPage: (off: number) => void;
}) {
  if (total === 0) return null;
  return (
    <div className="mt-3 flex items-center gap-2 text-xs text-ink/70">
      <button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}
        className="rounded-sm border border-ink/30 px-2 py-1 font-bold disabled:opacity-40">
        ← prev
      </button>
      <span className="font-semibold">{offset + 1}–{Math.min(offset + limit, total)} of {total}</span>
      <button disabled={offset + limit >= total} onClick={() => onPage(offset + limit)}
        className="rounded-sm border border-ink/30 px-2 py-1 font-bold disabled:opacity-40">
        next →
      </button>
    </div>
  );
}

/** Wrapper that loads a detail endpoint, shows refusals verbatim. */
export function DetailLoader({ url, children }: { url: string; children: (data: unknown) => ReactNode }) {
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState("");
  const loc = useLocation();

  useEffect(() => {
    setData(null);
    setError("");
    let dead = false;
    api(url).then((d) => { if (!dead) setData(d); }).catch((e: Error) => { if (!dead) setError(e.message); });
    return () => { dead = true; };
  }, [url, loc.state]);

  if (error)
    return (
      <p className="paper rounded-sm border-2 border-saffron bg-crimson-dark/90 p-4 text-sm font-semibold text-cream">
        refused: {error}
      </p>
    );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return data ? <>{children(data as any)}</> : <p className="paper p-4 text-sm italic text-ink/60">loading…</p>;
}

export function useGoBack() {
  const nav = useNavigate();
  return () => nav(-1);
}

export function PageHeader({ title, back }: { title: ReactNode; back?: string }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      {back && (
        <NavLink to={back} className="rounded-sm border-2 border-crimson-dark/50 px-2 py-1 text-xs font-bold uppercase text-crimson-deep hover:bg-crimson-dark/10">
          ← back
        </NavLink>
      )}
      <h2 className="font-display text-2xl text-crimson-deep">{title}</h2>
    </div>
  );
}

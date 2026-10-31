import type { ReactNode } from "react";
import type { MapIncident, MapStatus } from "../../mapTypes";

const TONE_STYLE: Record<string, string> = {
  teal: "bg-teal text-ink border-teal-dark",
  gold: "bg-mustard text-ink border-crimson-dark",
  maroon: "bg-crimson-dark text-cream border-saffron",
  grey: "bg-cream-dim text-ink/70 border-ink/30",
};

const TONE_DOT: Record<string, string> = {
  teal: "bg-teal",
  gold: "bg-mustard",
  maroon: "bg-crimson-dark",
  grey: "bg-ink/30",
};

export function StatusChip({
  status,
  compact = false,
}: {
  status?: MapStatus | null;
  compact?: boolean;
}) {
  const tone = status?.color ?? "grey";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm border font-bold uppercase tracking-wider ${
        compact ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-[11px]"
      } ${TONE_STYLE[tone] ?? TONE_STYLE.grey}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full bg-current opacity-70`} />
      {status?.label ?? "unknown"}
    </span>
  );
}

export function ToneDot({ tone }: { tone?: string }) {
  return (
    <span
      className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-ink/25 ${
        TONE_DOT[tone ?? "grey"] ?? TONE_DOT.grey
      }`}
    />
  );
}

export function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-sm border border-ink/15 bg-white/45 px-2 py-1.5">
      <p className="text-[9px] font-mono font-bold uppercase tracking-[0.12em] text-ink/55">
        {label}
      </p>
      <p
        className={`mt-0.5 font-display text-xl leading-none ${
          tone === "maroon"
            ? "text-crimson-deep"
            : tone === "teal"
              ? "text-teal-dark"
              : tone === "gold"
                ? "text-saffron"
                : "text-ink"
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-0.5 text-[10px] text-ink/55">{hint}</p>}
    </div>
  );
}

export function Legend() {
  const rows: { tone: string; label: string }[] = [
    { tone: "teal", label: "Available / healthy" },
    { tone: "gold", label: "Attention / approaching" },
    { tone: "maroon", label: "Critical / incident" },
    { tone: "grey", label: "Unknown / no data" },
  ];
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 z-[500] rounded-sm border-2 border-crimson-dark/30 bg-cream/95 px-2.5 py-2 shadow-md">
      <p className="mb-1 text-[9px] font-mono font-bold uppercase tracking-[0.18em] text-crimson-dark/70">
        Legend
      </p>
      <div className="space-y-0.5">
        {rows.map((row) => (
          <p key={row.tone} className="flex items-center gap-1.5 text-[10px] font-semibold text-ink/80">
            <ToneDot tone={row.tone} />
            {row.label}
          </p>
        ))}
      </div>
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <p className="mb-1.5 text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-crimson-dark/65">
      {children}
    </p>
  );
}

export function IncidentRow({
  incident,
  onOpen,
}: {
  incident: MapIncident;
  onOpen?: (id: number) => void;
}) {
  const verified = incident.verified;
  const target = incident.targets[0];
  const clickable = Boolean(target?.location_id && onOpen);
  return (
    <button
      type="button"
      disabled={!clickable}
      onClick={() => target?.location_id && onOpen?.(target.location_id)}
      className={`w-full rounded-sm border px-2 py-1.5 text-left transition ${
        verified
          ? "border-crimson-dark/40 bg-crimson-dark/10"
          : "border-mustard/60 bg-mustard/15"
      } ${clickable ? "hover:border-crimson-dark/70 hover:bg-crimson-dark/15 cursor-pointer" : "cursor-default"}`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="truncate text-[11px] font-bold text-ink">
          {incident.type.replaceAll("_", " ")}
        </span>
        <span
          className={`shrink-0 rounded-sm px-1 py-0 text-[9px] font-bold uppercase tracking-wide ${
            verified ? "bg-crimson-dark text-cream" : "bg-mustard text-ink"
          }`}
        >
          {verified ? "verified" : "potential"}
        </span>
      </span>
      <span className="mt-0.5 block truncate text-[10px] text-ink/65">
        {target?.name ?? "unlocated"} · #{incident.id}
      </span>
    </button>
  );
}

export function VerificationChip({ verified }: { verified: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
        verified
          ? "border-teal-dark/50 bg-teal/20 text-teal-dark"
          : "border-dashed border-saffron bg-mustard/20 text-crimson-deep"
      }`}
    >
      {verified ? "verified pin" : "pin unverified"}
    </span>
  );
}

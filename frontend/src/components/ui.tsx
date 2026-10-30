import type { ReactNode } from "react";

/* ---------- Badge / severity chips ---------- */

export type Severity = "error" | "warning" | "info" | "neutral" | "good";

const sevStyle: Record<Severity, string> = {
  error: "bg-crimson-dark text-cream border-saffron",
  warning: "bg-mustard text-ink border-crimson-dark",
  info: "bg-teal-dark text-cream border-teal",
  good: "bg-teal text-ink border-teal-dark",
  neutral: "bg-cream-dim text-ink border-ink/30",
};

export function Badge({ sev, children }: { sev: Severity; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded-sm border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${sevStyle[sev]}`}
    >
      {children}
    </span>
  );
}

export function Unknown() {
  return (
    <span
      title="source value missing — shown as-is, never guessed"
      className="inline-block rounded-sm border border-dashed border-ink/40 bg-cream-dim px-1.5 py-0 text-[11px] font-semibold uppercase tracking-wide text-ink/60"
    >
      unknown
    </span>
  );
}

/* ---------- Buttons ---------- */

type BtnProps = {
  variant?: "primary" | "ghost" | "danger";
  children: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

export function Btn({ variant = "primary", children, className = "", ...rest }: BtnProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-bold uppercase tracking-wider transition active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50";
  const styles = {
    primary: "plaque bg-mustard text-ink hover:bg-saffron",
    ghost: "border-2 border-ink/40 text-ink hover:bg-ink/10",
    danger: "plaque bg-crimson-dark text-cream border-saffron hover:bg-crimson-deep",
  } as const;
  return (
    <button className={`${base} ${styles[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

/* ---------- Panel / card ---------- */

export function Paper({
  children,
  className = "",
  title,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <section
      className={`paper relative rounded-sm border-2 border-crimson-dark/30 p-4 shadow-[0_3px_0_rgba(64,16,18,0.35)] ${className}`}
    >
      {title && <h2 className="mb-3 font-display text-lg text-ink">{title}</h2>}
      {children}
    </section>
  );
}

export function Spinner({ label = "loading…", tone = "dark" }: { label?: string; tone?: "dark" | "light" }) {
  return (
    <div className={`flex items-center gap-3 ${tone === "dark" ? "text-ink/70" : "text-cream/85"}`}>
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-mustard border-t-transparent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-ink/60">{children}</p>;
}

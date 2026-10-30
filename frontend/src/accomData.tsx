import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import type { Explain, Shortage } from "./accomTypes";

/** Load-on-mount panel with verbatim error surface + manual retry. */
export function AutoLoader({ url, children }: {
  url: string | null;
  children: (data: unknown) => ReactNode;
}) {
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!url) return;
    setData(null);
    setError("");
    api(url).then(setData).catch((e: Error) => setError(e.message));
  }, [url, tick]);

  if (error)
    return (
      <div className="flex items-center justify-between rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">
        <span>refused: {error}</span>
        <button onClick={() => setTick(tick + 1)} className="font-bold uppercase">retry</button>
      </div>
    );
  if (!data) return <SpinnerSmall label="reading accommodation state…" />;
  return <>{children(data)}</>;
}

export function SpinnerSmall({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink/70">
      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-crimson border-t-transparent" />
      {label}
    </div>
  );
}

export async function fetchShortage(): Promise<Shortage> {
  return api<Shortage>("/accommodation/shortage");
}

export async function fetchExplain(participantId: number): Promise<Explain> {
  return api<Explain>(`/accommodation/explain/${participantId}`);
}

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { ContigDetail } from "../peopleTypes";
import { FlagChips, MaskedValue, PageHeader, StatusBadge } from "../components/Listkit";
import { Badge, Paper, Spinner, Unknown } from "../components/ui";

export default function ContingentDetail({ rawId }: { rawId: string }) {
  const nav = useNavigate();
  const [data, setData] = useState<ContigDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
    api<ContigDetail>(`/contingents/${rawId}`)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.detail : String(e)));
  }, [rawId]);

  if (error) {
    return (
      <div>
        <PageHeader title={<span>contingent <span className="font-body text-lg opacity-80">{rawId}</span></span>} back="/people" />
        <p className="paper rounded-sm border-2 border-saffron bg-crimson-dark/90 p-4 text-sm font-semibold text-cream">refused: {error}</p>
      </div>
    );
  }
  if (!data)
    return <div className="beige p-4"><Spinner label="loading contingent…" /></div>;

  const c = data.contingent;
  return (
    <div>
      <PageHeader title={<span>contingent <span className="font-body text-lg opacity-80">{c.raw_id}</span></span>} back="/people" />

      <div className="space-y-3">
        <Paper title="Contingent card">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            <F label="college" v={c.college} />
            <F label="name" v={c.name} />
            <F label="leader" v={c.leader} />
            <F label="escort" v={c.escort ? `${c.escort}${c.escort_count ? ` (+${c.escort_count})` : ""}` : ""} />
            <F label="declared size" v={c.size_declared} />
            <F label="actual size" v={c.size_actual} />
            <F label="size mismatch" v={c.size_mismatch === null ? "" : String(c.size_mismatch)}
              badge={c.size_mismatch === null ? undefined
                : c.size_mismatch === 0 ? <Badge sev="good">clean</Badge>
                : <Badge sev={c.size_mismatch > 0 ? "warning" : "error"}>{c.size_mismatch > 0 ? `+${c.size_mismatch} extra` : `${c.size_mismatch} short`}</Badge>} />
            <F label="member count" v={data.member_count} />
          </dl>
          {data.open_issues.length > 0 && (
            <div className="mt-3 rounded-sm border border-mustard bg-mustard/20 p-2">
              <p className="mb-1 text-xs font-bold uppercase text-ink/70">open import issues on this contingent</p>
              <ul className="space-y-1 text-sm">
                {data.open_issues.map((i, k) => (
                  <li key={k}><Badge sev={i.severity === "error" ? "error" : "warning"}>{i.code}</Badge> {i.message}</li>
                ))}
              </ul>
            </div>
          )}
        </Paper>

        <div className="grid gap-3 lg:grid-cols-2">
          <Paper title="Arrival / departure pattern">
            <p className="text-sm">
              <span className="font-semibold">arrival days:</span>{" "}
              {data.arrival_days.length ? data.arrival_days.join(", ") : <Unknown />}
            </p>
            <p className="text-sm">
              <span className="font-semibold">departure days:</span>{" "}
              {data.departure_days.length ? data.departure_days.join(", ") : <Unknown />}
            </p>
            <p className="mt-1 text-xs italic text-ink/60">counted from member rows only — blanks stay unknown, never assumed</p>
          </Paper>
          <Paper title="Stated preferences">
            {c.preferences?.length ? (
              <ul className="list-inside list-disc text-sm">{c.preferences.map((pr, i) => <li key={i}>{pr}</li>)}</ul>
            ) : (
              <p className="text-sm italic text-ink/60">none recorded</p>
            )}
          </Paper>
        </div>

        <Paper title={`Members (${data.members.length}) — masked per your role`}>
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-2">raw id</th><th className="px-2 py-2">name</th>
                  <th className="px-2 py-2">status</th><th className="px-2 py-2">flags</th>
                  <th className="px-2 py-2">arrival</th><th className="px-2 py-2">departure</th>
                  <th className="px-2 py-2">t-shirt</th><th className="px-2 py-2">phone</th><th className="px-2 py-2">room</th>
                </tr>
              </thead>
              <tbody>
                {data.members.map((m) => (
                  <tr key={m.id} className="cursor-pointer border-b border-ink/10 hover:bg-mustard/20" onClick={() => nav(`/people/${m.id}`)}>
                    <td className="px-2 py-1.5 font-mono text-xs">{m.raw_id}</td>
                    <td className="px-2 py-1.5 text-sm font-semibold">{m.name}</td>
                    <td className="px-2 py-1.5"><StatusBadge status={m.status} /></td>
                    <td className="px-2 py-1.5"><FlagChips flags={m.quality_flags} /></td>
                    <td className="px-2 py-1.5 text-xs">{m.arrival ? m.arrival.replace("T", " ").slice(0, 16) : <Unknown />}</td>
                    <td className="px-2 py-1.5 text-xs">{m.departure ? m.departure.replace("T", " ").slice(0, 16) : <Unknown />}</td>
                    <td className="px-2 py-1.5 text-xs">{m.tshirt_size ? m.tshirt_size : <Unknown />}</td>
                    <td className="px-2 py-1.5"><MaskedValue value={m.phone} /></td>
                    <td className="px-2 py-1.5"><MaskedValue value={m.room ?? ""} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Paper>
      </div>
    </div>
  );
}

function F({ label, v, badge }: {
  label: string;
  v: string | number | null | undefined;
  badge?: ReactNode;
}) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-wider text-ink/60">{label}</dt>
      <dd className="flex items-center gap-1.5">
        {v === "" ? <Unknown /> : String(v ?? "")}
        {badge ?? null}
      </dd>
    </div>
  );
}

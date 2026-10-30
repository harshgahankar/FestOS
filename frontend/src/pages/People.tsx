import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { ContigList, DuplicatesResp, PeopleList } from "../peopleTypes";
import ReasonModal from "../components/ReasonModal";
import { FlagChips, MaskedValue, PageHeader, Pager, StatusBadge } from "../components/Listkit";
import { Badge, Btn, Paper, Spinner, Unknown } from "../components/ui";

type Tab = "participants" | "contingents" | "duplicates";

export default function People() {
  const [tab, setTab] = useState<Tab>("participants");
  const nav = useNavigate();
  return (
    <div>
      <PageHeader title="People & Contingents" />
      <div className="mb-3 flex gap-2">
        {(["participants", "contingents", "duplicates"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-sm border-2 px-3 py-1.5 text-sm font-bold uppercase tracking-wider ${
              tab === t ? "plaque bg-mustard text-ink" : "border-crimson-dark/40 text-crimson-deep hover:bg-crimson-dark/5"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "participants" && <ParticipantsTab nav={nav} />}
      {tab === "contingents" && <ContingentsTab nav={nav} />}
      {tab === "duplicates" && <DuplicatesTab />}
    </div>
  );
}

/* ------------------------------- participants ------------------------------ */

const STATUSES = ["active", "flagged", "quarantined", "duplicate"];

function ParticipantsTab({ nav }: { nav: (to: string) => void }) {
  const [rows, setRows] = useState<PeopleList | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [flag, setFlag] = useState("");
  const [contingent, setContingent] = useState("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  async function load(o = 0) {
    setBusy(true);
    setError("");
    try {
      const p = new URLSearchParams({ limit: String(LIMIT), offset: String(o) });
      if (search.trim()) p.set("search", search.trim());
      if (status) p.set("status", status);
      if (flag) p.set("flag", flag);
      if (contingent) p.set("contingent", contingent);
      setRows(await api<PeopleList>(`/participants?${p}`));
      setOffset(o);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Paper title="Participants — masked to what your role may see">
      <form
        className="mb-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => { e.preventDefault(); void load(0); }}
      >
        <label className="text-xs font-bold uppercase text-ink/70">
          search
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            className="mt-1 w-44 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink" />
        </label>
        <label className="text-xs font-bold uppercase text-ink/70">
          status
          <select value={status} onChange={(e) => setStatus(e.target.value)}
            className="mt-1 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink">
            <option value="">all</option>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label className="text-xs font-bold uppercase text-ink/70">
          flag
          <input value={flag} onChange={(e) => setFlag(e.target.value)} placeholder="e.g. MISSING_PHONE"
            className="mt-1 w-40 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink" />
        </label>
        <label className="text-xs font-bold uppercase text-ink/70">
          contingent
          <input value={contingent} onChange={(e) => setContingent(e.target.value)} placeholder="e.g. EG-CP-01"
            className="mt-1 w-32 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink" />
        </label>
        <Btn type="submit">find</Btn>
      </form>

      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {error}</p>}
      {busy && <Spinner label="reading registrations…" />}

      {rows && (
        <>
          <Pager total={rows.total} limit={rows.limit} offset={offset} onPage={(o) => void load(o)} />
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-2">raw id</th><th className="px-2 py-2">name</th>
                  <th className="px-2 py-2">college</th><th className="px-2 py-2">contingent</th>
                  <th className="px-2 py-2">status</th><th className="px-2 py-2">flags</th>
                  <th className="px-2 py-2">t-shirt</th><th className="px-2 py-2">phone</th>
                  <th className="px-2 py-2">room</th>
                </tr>
              </thead>
              <tbody>
                {rows.participants.map((p) => (
                  <tr key={p.id} className="cursor-pointer border-b border-ink/10 hover:bg-mustard/20" onClick={() => nav(`/people/${p.id}`)}>
                    <td className="px-2 py-1.5 font-mono text-xs">{p.raw_id}</td>
                    <td className="px-2 py-1.5 text-sm font-semibold">{p.name}</td>
                    <td className="px-2 py-1.5 text-xs">{p.college}</td>
                    <td className="px-2 py-1.5 font-mono text-xs">{p.contingent ?? <Unknown />}</td>
                    <td className="px-2 py-1.5"><StatusBadge status={p.status} /></td>
                    <td className="px-2 py-1.5"><FlagChips flags={p.quality_flags} /></td>
                    <td className="px-2 py-1.5 text-xs">{p.tshirt_size ? p.tshirt_size : <Unknown />}</td>
                    <td className="px-2 py-1.5"><MaskedValue value={p.phone} /></td>
                    <td className="px-2 py-1.5"><MaskedValue value={p.room ?? ""} /></td>
                  </tr>
                ))}
                {rows.participants.length === 0 && (
                  <tr><td colSpan={9} className="px-2 py-4 text-center text-sm italic text-ink/60">no rows match those filters</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Paper>
  );
}

/* --------------------------------- contingents ----------------------------- */

function ContingentsTab({ nav }: { nav: (to: string) => void }) {
  const [rows, setRows] = useState<ContigList | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [mismatched, setMismatched] = useState(false);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  async function load(o = 0) {
    setBusy(true);
    setError("");
    try {
      const p = new URLSearchParams({ limit: String(LIMIT), offset: String(o) });
      if (search.trim()) p.set("search", search.trim());
      if (mismatched) p.set("mismatched", "true");
      setRows(await api<ContigList>(`/contingents?${p}`));
      setOffset(o);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Paper title="Contingents — declared vs actual, honestly counted">
      <form className="mb-3 flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); void load(0); }}>
        <label className="text-xs font-bold uppercase text-ink/70">
          search
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            className="mt-1 w-44 rounded-sm border-2 border-teal-dark/40 bg-white/60 px-2 py-1 text-sm font-normal text-ink" />
        </label>
        <label className="flex items-center gap-1 text-xs font-bold uppercase text-ink/70">
          <input type="checkbox" checked={mismatched} onChange={(e) => setMismatched(e.target.checked)} />
          size mismatch only
        </label>
        <Btn type="submit">find</Btn>
      </form>

      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {error}</p>}
      {busy && <Spinner label="reading contingents…" />}

      {rows && (
        <>
          <Pager total={rows.total} limit={rows.limit} offset={offset} onPage={(o) => void load(o)} />
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-2 py-2">raw id</th><th className="px-2 py-2">college</th>
                  <th className="px-2 py-2">leader</th><th className="px-2 py-2">escort</th>
                  <th className="px-2 py-2">declared</th><th className="px-2 py-2">actual</th>
                  <th className="px-2 py-2">mismatch</th>
                </tr>
              </thead>
              <tbody>
                {rows.contingents.map((c) => (
                  <tr key={c.id} className="cursor-pointer border-b border-ink/10 hover:bg-mustard/20" onClick={() => nav(`/contingents/${c.raw_id}`)}>
                    <td className="px-2 py-1.5 font-mono text-xs">{c.raw_id}</td>
                    <td className="px-2 py-1.5 text-sm font-semibold">{c.college}</td>
                    <td className="px-2 py-1.5 text-xs">{c.leader ?? <Unknown />}</td>
                    <td className="px-2 py-1.5 text-xs">
                      {c.escort ? `${c.escort}${c.escort_count ? ` (+${c.escort_count})` : ""}` : <Unknown />}
                    </td>
                    <td className="px-2 py-1.5 text-sm">{c.size_declared ?? <Unknown />}</td>
                    <td className="px-2 py-1.5 text-sm">{c.size_actual ?? <Unknown />}</td>
                    <td className="px-2 py-1.5">
                      {c.size_mismatch === null
                        ? <Unknown />
                        : c.size_mismatch === 0
                          ? <Badge sev="good">clean</Badge>
                          : <Badge sev={c.size_mismatch > 0 ? "warning" : "error"}>
                              {c.size_mismatch > 0 ? `+${c.size_mismatch} extra` : `${c.size_mismatch} short`}
                            </Badge>}
                    </td>
                  </tr>
                ))}
                {rows.contingents.length === 0 && (
                  <tr><td colSpan={7} className="px-2 py-4 text-center text-sm italic text-ink/60">no contingents match</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Paper>
  );
}

/* --------------------------------- duplicates ------------------------------ */

function DuplicatesTab() {
  const [data, setData] = useState<DuplicatesResp | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [unmergeId, setUnmergeId] = useState<number | null>(null);
  const [modalErr, setModalErr] = useState("");
  const [modalBusy, setModalBusy] = useState(false);

  async function load() {
    setBusy(true);
    setError("");
    try {
      setData(await api<DuplicatesResp>("/participants/duplicates"));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function doUnmerge(reason: string) {
    if (unmergeId === null) return;
    setModalBusy(true);
    setModalErr("");
    try {
      await api(`/participants/${unmergeId}/unmerge`, { method: "POST", body: { reason } });
      setUnmergeId(null);
      const d = await api<DuplicatesResp>("/participants/duplicates");
      setData(d);
    } catch (e) {
      setModalErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setModalBusy(false);
    }
  }

  return (
    <Paper title="Duplicate clusters — linked duplicates stay readable, never deleted">
      {error && <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-sm text-cream">refused: {error}</p>}
      {busy && <Spinner />}
      {data && (
        data.count === 0 ? <p className="text-sm italic text-ink/60">no linked duplicates exist</p> :
        <div className="space-y-2">
          {data.clusters.map((c) => (
            <div key={c.canonical.id} className="rounded-sm border border-teal-dark/30 bg-white/50 p-3">
              <p className="text-sm font-bold text-ink">
                canonical: <span className="font-mono">{c.canonical.raw_id}</span> — {c.canonical.name}
                <span className="ml-2 font-normal text-xs text-ink/60">({c.duplicates.length} duplicate{c.duplicates.length > 1 ? "s" : ""} linked)</span>
              </p>
              <ul className="mt-1.5 space-y-1">
                {c.duplicates.map((d) => (
                  <li key={d.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-mono text-xs">{d.raw_id}</span>
                    <span>{d.name}</span>
                    <FlagChips flags={d.quality_flags} />
                    <button
                      onClick={() => { setModalErr(""); setUnmergeId(d.id); }}
                      className="rounded-sm border-2 border-crimson-dark/40 bg-white/60 px-2 py-0.5 text-[11px] font-bold uppercase text-crimson-deep hover:bg-crimson/10"
                    >
                      unmerge ←
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {unmergeId !== null && (
        <ReasonModal
          title={`Unmerge participant ${unmergeId}`}
          description="The duplicate returns to active status. The merge stays fully audited; reversals are allowed, deletes are not."
          confirmLabel="unmerge"
          busy={modalBusy}
          error={modalErr}
          onCancel={() => { setUnmergeId(null); setModalErr(""); }}
          onConfirm={doUnmerge}
        />
      )}
    </Paper>
  );
}

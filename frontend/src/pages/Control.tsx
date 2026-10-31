import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUpload, ApiError } from "../api";
import type { AttentionItem, AttentionResp, ImportReport, Kpis } from "../types";
import { Badge, Btn, EmptyState, Paper, Spinner } from "../components/ui";
import type { Severity } from "../components/ui";

function Tile({ big, label, sub = [] }: { big: string | number; label: string; sub?: string[] }) {
  return (
    <div className="paper rounded-sm border-2 border-crimson-dark/25 p-3 shadow-[0_2px_0_rgba(64,16,18,0.3)]">
      <p className="font-display text-3xl text-crimson">{big}</p>
      <p className="text-xs font-bold uppercase tracking-wider text-ink/70">{label}</p>
      {sub.filter(Boolean).map((s) => (
        <p key={s} className="text-[11px] text-ink/60">{s}</p>
      ))}
    </div>
  );
}

const PRESET_LABELS: Record<string, string> = {
  min_cost: "Lowest cost",
  max_cohesion: "Keep groups together",
  balanced: "Balanced",
};

const ALLOWED_CSVS = [
  "participants.csv", "contingents.csv", "registrations.csv", "events.csv",
  "venues.csv", "hostels.csv", "external_stays.csv", "vendors.csv",
  "core_team.csv", "inventory_logistics.csv", "inventory_merch.csv",
];

type PackReport = ImportReport;
type ScenarioReport = {
  total: number;
  imported: number;
  failed: { scenario_id: string; error: string }[];
  disruption_ids: number[];
};

function ImportCsvModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [picked, setPicked] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [report, setReport] = useState<PackReport | null>(null);
  const [scenario, setScenario] = useState<ScenarioReport | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  function pick(list: FileList | null) {
    const files = list ? Array.from(list) : [];
    const nonCsv = files.filter((f) => !f.name.toLowerCase().endsWith(".csv"));
    setError(nonCsv.length
      ? `not a CSV: ${nonCsv.map((f) => f.name).join(", ")} — upload the data-pack CSVs here, or a judge scenario CSV (auto-routed to the Disruption Desk).`
      : "");
    setReport(null);
    setScenario(null);
    setPicked(nonCsv.length ? picked : files);
  }

  async function run() {
    if (!picked.length) return;
    setBusy(true);
    setError("");
    try {
      const pack = picked.filter((f) => ALLOWED_CSVS.includes(f.name));
      const others = picked.filter((f) => !ALLOWED_CSVS.includes(f.name));
      if (pack.length) {
        const form = new FormData();
        pack.forEach((f) => form.append("files", f));
        setReport(await apiUpload<PackReport>("/imports/upload", form));
      }
      if (others.length) {
        for (const f of others) {
          const head = (await f.text()).split("\n", 1)[0] ?? "";
          if (!/disruption_type/i.test(head)) {
            throw new ApiError(400,
              `${f.name} is neither a data-pack CSV nor a disruption scenario pack (no "disruption_type" column)`);
          }
          const form = new FormData();
          form.append("file", f);
          setScenario(await apiUpload<ScenarioReport>("/disruptions/scenario-pack", form));
        }
      }
      setPicked([]);
      if (inputRef.current) inputRef.current.value = "";
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : `network error — ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  }

  const recon = report?.reconciliation;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-crimson-dark/70 p-4" onClick={onClose}>
      <div className="paper torn-b relative w-full max-w-lg rounded-sm border-2 border-crimson-dark/50 p-5 pb-7 shadow-[0_10px_0_rgba(64,16,18,0.5)]"
        onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-start justify-between">
          <h3 className="font-display text-xl text-ink">Upload CSV pack</h3>
          <button onClick={onClose} className="text-ink/50 hover:text-ink" title="close">✕</button>
        </div>

        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files); }}
          className="block cursor-pointer rounded-sm border-2 border-dashed border-crimson-dark/40 bg-white/40 p-3 text-center hover:bg-teal/15"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={(e) => pick(e.target.files)}
            disabled={busy}
          />
          <p className="text-sm font-bold text-ink">drop CSV files here, or click to choose</p>
          <p className="mt-0.5 text-[11px] italic text-ink/50">
            data-pack: {ALLOWED_CSVS.join(" · ")}
          </p>
          <p className="text-[11px] italic text-ink/50">
            judge scenarioCSVs (with a disruption_type column) are auto-routed to the Disruption Desk
          </p>
        </label>

        {picked.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {picked.map((f) => (
              <li key={f.name} className="rounded-sm border border-teal-dark/40 bg-teal/15 px-2 py-0.5 text-xs font-semibold text-ink">
                {f.name} <span className="text-ink/50">({Math.round(f.size / 1024)} KB)</span>
              </li>
            ))}
          </ul>
        )}

        {error && <p className="mt-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-xs text-cream">refused: {error}</p>}
        {busy && <Spinner label="running the import pipeline…" />}

        {report && (
          <div className="mt-3 rounded-sm border border-teal-dark/30 bg-teal/10 p-3">
            <p className="text-xs font-bold uppercase tracking-wider text-teal-dark">
              import finished · {report.files_loaded.length} file{report.files_loaded.length === 1 ? "" : "s"} loaded
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {Object.entries(report.rows_imported).map(([k, v]) => (
                <Badge key={k} sev="neutral">{k}: {v}</Badge>
              ))}
            </div>
            {Object.keys(report.issues_by_code).length > 0 && (
              <>
                <p className="mt-2 text-xs font-bold uppercase tracking-wider text-crimson-dark">issues by code</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {Object.entries(report.issues_by_code).map(([code, n]) => (
                    <Badge key={code} sev={code.startsWith("UNK") || code === "FILE_MISSING" ? "error" : "warning"}>
                      {code}: {n}
                    </Badge>
                  ))}
                </div>
              </>
            )}
            {recon && (
              <p className="mt-2 text-[11px] text-ink/70">
                funnel: {recon.raw_imported} raw → {recon.active} active
                ({recon.duplicates_merged} dup-merged, {recon.quarantined} quarantined, {recon.flagged} flagged) ·
                expected {recon.expected_participants}, gap {recon.gap_vs_expected >= 0 ? "+" : ""}{recon.gap_vs_expected}
                <span className="italic"> — {recon.note}</span>
              </p>
            )}
          </div>
        )}

        {scenario && (
          <div className="mt-3 rounded-sm border border-crimson-dark/30 bg-mustard/10 p-3">
            <p className="text-xs font-bold uppercase tracking-wider text-crimson-dark">
              scenario pack → {scenario.imported}/{scenario.total} previewed as tickets in the Disruption Desk
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              {scenario.disruption_ids.map((id) => (
                <Badge key={id} sev="warning">#{id}</Badge>
              ))}
            </div>
            {scenario.failed.length > 0 && (
              <ul className="mt-1.5 list-inside list-disc text-[11px] text-crimson-deep">
                {scenario.failed.map((f) => (
                  <li key={f.scenario_id}><strong>{f.scenario_id}</strong> — {f.error}</li>
                ))}
              </ul>
            )}
            <p className="mt-1.5 text-[11px] italic text-ink/60">
              open the Disruption Desk (sidebar) to apply each ticket — or download nothing, just apply from there
            </p>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-2">
          <Link to="/disruptions" onClick={onClose} className="text-xs font-bold uppercase tracking-wider text-teal-dark underline hover:text-ink">
            open the disruption desk
          </Link>
          <div className="flex gap-2">
            <Btn variant="ghost" onClick={onClose} className="!text-ink/80 !border-ink/30">close</Btn>
            <Btn onClick={run} disabled={busy || picked.length === 0 || !!error}>
              {busy ? "importing…" : `import ${picked.length || ""} file${picked.length === 1 ? "" : "s"}`}
            </Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

function OccupancyTile({ occ }: { occ: Kpis["occupancy"] }) {
  if (!occ) {
    return (
      <div className="paper rounded-sm border-2 border-dashed border-ink/40 p-3">
        <p className="font-display text-xl text-ink/50">unknown</p>
        <p className="text-xs font-bold uppercase tracking-wider text-ink/70">occupancy</p>
        <p className="text-[11px] text-ink/60">no allocation plan is ACTIVE yet — numbers appear once activated, never guessed</p>
      </div>
    );
  }
  const parts = Object.entries(occ)
    .filter(([k]) => k !== "plan_id" && k !== "preset")
    .map(([k, v]) => `${k}: ${String(v)}`);
  return <Tile big={PRESET_LABELS[occ.preset] ?? occ.preset} label={`occupancy · plan #${occ.plan_id}`} sub={parts} />;
}

export default function Control() {
  const [attn, setAttn] = useState<AttentionResp | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sevFilter, setSevFilter] = useState<"all" | "error" | "warning" | "info">("all");
  const [openItem, setOpenItem] = useState<AttentionItem | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  async function load() {
    setBusy(true);
    setError("");
    try {
      const [a, k] = await Promise.all([
        api<AttentionResp>("/control/attention"),
        api<Kpis>("/control/kpis"),
      ]);
      setAttn(a);
      setKpis(k);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : `network error — ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const filtered = attn
    ? attn.items.filter((i) => sevFilter === "all" || i.severity === sevFilter)
    : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="font-display text-lg text-ink">Command Center</p>
        <Btn onClick={() => setUploadOpen(true)} className="!py-1.5 !text-xs">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3v12" />
            <path d="m7 8 5-5 5 5" />
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
          </svg>
          Upload CSV
        </Btn>
      </div>

      <ImportCsvModal open={uploadOpen} onClose={() => setUploadOpen(false)} onDone={load} />

      {error && <p className="rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-cream">{error}</p>}
      {busy && <Spinner label="sweeping the whole festival state…" />}

      {kpis && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Tile big={kpis.participants.active} label="participants"
            sub={[`flagged ${kpis.participants.flagged}`, `quarantined ${kpis.participants.quarantined}`, `dup-linked ${kpis.participants.linked_duplicates}`]} />
          <Tile big={kpis.registrations.rows} label="registration rows"
            sub={[`matched ${kpis.registrations.matched_to_participant}`, `open issues ${kpis.registrations.issues_open}`]} />
          <OccupancyTile occ={kpis.occupancy} />
          <Tile big={kpis.events.total} label="events"
            sub={[`scheduled ${kpis.events.scheduled}`, `conflicts ${kpis.events.conflicts}`]} />
          <Tile big={kpis.merch.issued} label="merch issued"
            sub={[`short sizes ${kpis.merch.shortfall_sizes}`, `missing units ${kpis.merch.missing_units}`]} />
          <Tile big={kpis.vendors.total} label="vendors"
            sub={[`expired ${kpis.vendors.expired}`, `expiring ${kpis.vendors.expiring}`, `no-diet-cover ${kpis.vendors.uncovered_diet_tags.length}`]} />
        </div>
      )}

      {attn && (
        <Paper title={`Attention — everything open, nothing hidden (${attn.count})`}>
          <div className="flex gap-2">
            {(["all", "error", "warning", "info"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSevFilter(s)}
                className="rounded-sm border-2 border-teal-dark/50 bg-teal/15 px-2 py-1 text-xs font-bold uppercase text-ink/80 hover:bg-teal/30"
              >
                {s === "all" ? `all ${attn.count}` : `${s} ${attn.by_severity[s] ?? 0}`}
              </button>
            ))}
          </div>

          {attn.count === 0 ? (
            <EmptyState>nothing open — the fest is clean</EmptyState>
          ) : (
            <ul className="mt-3 max-h-[28rem] overflow-y-auto space-y-1.5 pr-1">
              {filtered.map((i) => (
                <li
                  key={i.entity + "|" + i.what}
                  onClick={() => setOpenItem(openItem === i ? null : i)}
                  className="cursor-pointer rounded-sm border border-crimson-dark/25 bg-white/50 p-2 hover:bg-white/70"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge sev={i.severity as Severity}>{i.severity}</Badge>
                    <Badge sev="neutral">{i.source}</Badge>
                    <span className="text-sm font-semibold text-ink">{i.what}</span>
                  </div>
                  {openItem === i && (
                    <div className="mt-1.5 border-l-2 border-teal pl-2">
                      <p className="text-xs font-semibold text-teal-dark">reference: {i.entity}</p>
                      <p className="text-xs italic text-ink/70">hint: {i.action_hint}</p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Paper>
      )}
    </div>
  );
}

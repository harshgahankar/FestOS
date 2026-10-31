import type {
  MapDuty,
  MapIncidentsResponse,
  MapSummary,
} from "../../mapTypes";
import { typeLabel } from "../../mapTypes";
import {
  IncidentRow,
  Metric,
  SectionTitle,
  ToneDot,
} from "./MapWidgets";

function Check({
  checked,
  label,
  count,
  onChange,
}: {
  checked: boolean;
  label: string;
  count?: number;
  onChange: () => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-sm px-1 py-0.5 text-[11px] font-semibold text-ink/80 hover:bg-teal/10">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="h-3.5 w-3.5 accent-[#a3242b]"
      />
      <span className="flex-1 truncate">{label}</span>
      {count !== undefined && (
        <span className="font-mono text-[10px] text-ink/50">{count}</span>
      )}
    </label>
  );
}

export default function FilterSidebar({
  role,
  summary,
  layerOptions,
  selectedLayers,
  onToggleLayer,
  onAllLayers,
  statusOptions,
  selectedStatuses,
  onToggleStatus,
  search,
  onSearch,
  at,
  onAt,
  onNow,
  onFit,
  canManage,
  isDirector,
  unmappedCount,
  onAdd,
  onSettings,
  onUnmapped,
  incidents,
  canViewIncidents,
  showIncidentLayer,
  onToggleIncidentLayer,
  onSelectIncident,
  duties,
}: {
  role: string;
  summary: MapSummary | null;
  layerOptions: string[];
  selectedLayers: string[];
  onToggleLayer: (layer: string) => void;
  onAllLayers: () => void;
  statusOptions: string[];
  selectedStatuses: string[];
  onToggleStatus: (status: string) => void;
  search: string;
  onSearch: (value: string) => void;
  at: string;
  onAt: (value: string) => void;
  onNow: () => void;
  onFit: () => void;
  canManage: boolean;
  isDirector: boolean;
  unmappedCount: number;
  onAdd: () => void;
  onSettings: () => void;
  onUnmapped: () => void;
  incidents: MapIncidentsResponse | null;
  canViewIncidents: boolean;
  showIncidentLayer: boolean;
  onToggleIncidentLayer: () => void;
  onSelectIncident: (locationId: number) => void;
  duties: MapDuty[];
}) {
  const scope =
    role === "director"
      ? "Full operational picture, all layers."
      : role === "volunteer"
        ? "Only locations with a duty assigned to you."
        : role === "viewer"
          ? "Read-only venue overview."
          : `Your operational layer: ${role.replaceAll("_", " ")}.`;

  return (
    <aside className="paper custom-scrollbar flex max-h-[68vh] flex-col gap-0 overflow-y-auto rounded-sm border-2 border-crimson-dark/30 shadow-[0_3px_0_rgba(64,16,18,0.35)] lg:max-h-[calc(100vh-12.5rem)]">
      <div className="border-b border-ink/15 p-3">
        <p className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-saffron">
          GeoCommand
        </p>
        <h3 className="font-display text-xl leading-tight text-crimson-deep">
          Operations map
        </h3>
        <p className="mt-1 text-[11px] leading-snug text-ink/65">{scope}</p>
      </div>

      <div className="grid grid-cols-2 gap-1.5 border-b border-ink/15 p-2.5">
        <Metric label="Pins" value={summary?.mapped_locations ?? "—"} tone="teal" />
        <Metric
          label="Incidents"
          value={summary?.incidents.active ?? 0}
          hint={`${summary?.incidents.potential ?? 0} potential`}
          tone={summary?.incidents.active ? "maroon" : undefined}
        />
        <Metric
          label="Unverified"
          value={summary?.unverified_coordinates ?? "—"}
          hint="pins needing a site check"
          tone={summary?.unverified_coordinates ? "gold" : undefined}
        />
        <Metric
          label="Unmapped"
          value={summary?.unmapped_total ?? "—"}
          hint="records without a pin"
        />
      </div>

      <div className="border-b border-ink/15 p-2.5">
        <SectionTitle>Time on the map</SectionTitle>
        <div className="flex items-center gap-1.5">
          <input
            type="datetime-local"
            value={at}
            onChange={(event) => onAt(event.target.value)}
            className="min-w-0 flex-1 rounded-sm border border-ink/30 bg-white/70 px-1.5 py-1 text-[11px] font-semibold text-ink"
          />
          <button
            type="button"
            onClick={onNow}
            className="rounded-sm border border-crimson-dark/40 px-1.5 py-1 text-[10px] font-bold uppercase text-crimson-deep hover:bg-crimson-dark/10"
          >
            now
          </button>
        </div>
        <p className="mt-1 text-[9px] text-ink/50">
          Occupancy, events and vendors are evaluated at this instant ({summary?.timezone ?? "Asia/Kolkata"}).
        </p>
      </div>

      <div className="border-b border-ink/15 p-2.5">
        <SectionTitle>Search</SectionTitle>
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="name, zone, entity id…"
          className="w-full rounded-sm border border-ink/30 bg-white/70 px-2 py-1 text-[11px] font-semibold text-ink placeholder:text-ink/35"
        />
      </div>

      <div className="border-b border-ink/15 p-2.5">
        <div className="flex items-center justify-between">
          <SectionTitle>Layers</SectionTitle>
          <button
            type="button"
            onClick={onAllLayers}
            className="mb-1.5 text-[9px] font-bold uppercase text-teal-dark hover:underline"
          >
            all
          </button>
        </div>
        {layerOptions.length === 0 ? (
          <p className="text-[10px] italic text-ink/55">No layers available for this role.</p>
        ) : (
          <div className="space-y-0.5">
            {layerOptions.map((layer) => (
              <Check
                key={layer}
                label={typeLabel(layer)}
                checked={selectedLayers.includes(layer)}
                count={summary?.layers[layer]}
                onChange={() => onToggleLayer(layer)}
              />
            ))}
          </div>
        )}
      </div>

      {statusOptions.length > 0 && (
        <div className="border-b border-ink/15 p-2.5">
          <SectionTitle>Status filter</SectionTitle>
          <div className="flex flex-wrap gap-1">
            {statusOptions.map((status) => {
              const active = selectedStatuses.includes(status);
              return (
                <button
                  key={status}
                  type="button"
                  onClick={() => onToggleStatus(status)}
                  className={`rounded-sm border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide transition ${
                    active
                      ? "border-crimson-dark bg-crimson-dark text-cream"
                      : "border-ink/25 bg-white/50 text-ink/65 hover:border-teal-dark/50"
                  }`}
                >
                  {status.replaceAll("_", " ")} · {summary?.status_counts[status] ?? 0}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {canViewIncidents && (
        <div className="border-b border-ink/15 p-2.5">
          <div className="flex items-center justify-between">
            <SectionTitle>Incidents</SectionTitle>
            <button
              type="button"
              onClick={onToggleIncidentLayer}
              className={`mb-1.5 rounded-sm border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${
                showIncidentLayer
                  ? "border-crimson-dark bg-crimson-dark text-cream"
                  : "border-ink/25 text-ink/60"
              }`}
            >
              {showIncidentLayer ? "on map" : "hidden"}
            </button>
          </div>
          <div className="mb-1.5 flex items-center gap-2 text-[10px] font-semibold text-ink/65">
            <ToneDot tone="maroon" />
            {incidents?.counts.active ?? 0} verified
            <ToneDot tone="gold" />
            {incidents?.counts.potential ?? 0} potential
            <span className="ml-auto font-mono text-ink/45">
              {incidents?.counts.unlocated ?? 0} unlocated
            </span>
          </div>
          <div className="space-y-1">
            {(incidents?.incidents ?? []).slice(0, 3).map((incident) => (
              <IncidentRow
                key={incident.id}
                incident={incident}
                onOpen={onSelectIncident}
              />
            ))}
            {incidents && incidents.incidents.length === 0 && (
              <p className="text-[10px] italic text-ink/55">
                No applied/previewed disruption is mapped to a pin.
              </p>
            )}
          </div>
        </div>
      )}

      <div className="border-b border-ink/15 p-2.5">
        <SectionTitle>{role === "volunteer" ? "Your duties" : "Duty assignments"}</SectionTitle>
        {duties.length === 0 ? (
          <p className="text-[10px] italic text-ink/55">
            {role === "volunteer"
              ? "No duties have been assigned to you yet."
              : "No volunteer duties assigned."}
          </p>
        ) : (
          <div className="space-y-1">
            {duties.slice(0, 5).map((duty) => (
              <div key={duty.id} className="rounded-sm border border-ink/15 bg-white/45 px-1.5 py-1">
                <p className="truncate text-[10px] font-bold text-ink">
                  {duty.label || duty.task_type}
                </p>
                <p className="truncate font-mono text-[9px] text-ink/55">
                  {duty.username} · {duty.task_type}
                  {duty.starts_at ? ` · ${duty.starts_at.slice(11, 16)}` : ""}
                </p>
              </div>
            ))}
            {duties.length > 5 && (
              <p className="text-[9px] text-ink/50">+{duties.length - 5} more</p>
            )}
          </div>
        )}
      </div>

      <div className="p-2.5">
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={onFit}
            className="rounded-sm border-2 border-teal-dark/40 bg-teal/15 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-teal-dark hover:bg-teal/25"
          >
            fit pins
          </button>
          {canManage ? (
            <button
              type="button"
              onClick={onAdd}
              className="rounded-sm border-2 border-crimson-dark/40 bg-mustard px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-ink hover:bg-saffron"
            >
              add location
            </button>
          ) : (
            <span className="rounded-sm border border-ink/15 px-2 py-1 text-center text-[10px] font-semibold text-ink/45">
              read only
            </span>
          )}
          {canManage && (
            <button
              type="button"
              onClick={onUnmapped}
              className="rounded-sm border border-crimson-dark/30 bg-white/50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-crimson-deep hover:bg-crimson-dark/10"
            >
              unmapped · {unmappedCount}
            </button>
          )}
          {isDirector && (
            <button
              type="button"
              onClick={onSettings}
              className="rounded-sm border border-crimson-dark/30 bg-white/50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-crimson-deep hover:bg-crimson-dark/10"
            >
              map centre
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

import { useMemo, useState } from "react";
import { api } from "../../api";
import type {
  GeocodeResult,
  MapEntity,
  MapLink,
} from "../../mapTypes";
import { LOCATION_TYPES, typeLabel } from "../../mapTypes";
import { Btn, Spinner } from "../ui";
import { SectionTitle } from "./MapWidgets";

export type LocationFormValues = {
  name: string;
  location_type: string;
  latitude: number | null;
  longitude: number | null;
  address: string;
  campus_zone: string;
  source_reference: string;
  links: MapLink[];
};

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export default function LocationEditor({
  mode,
  values,
  locationTypes,
  entities,
  picking,
  busy,
  error,
  onChange,
  onTogglePick,
  onSave,
  onClose,
}: {
  mode: "create" | "edit";
  values: LocationFormValues;
  locationTypes: string[];
  entities: MapEntity[];
  picking: boolean;
  busy: boolean;
  error: string;
  onChange: (values: LocationFormValues) => void;
  onTogglePick: () => void;
  onSave: (reason: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [linkType, setLinkType] = useState("");
  const [linkId, setLinkId] = useState("");
  const [geoQuery, setGeoQuery] = useState("");
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoError, setGeoError] = useState("");
  const [geoResults, setGeoResults] = useState<GeocodeResult[]>([]);

  const typeOptions = useMemo(
    () =>
      (locationTypes.length ? locationTypes : LOCATION_TYPES).filter(
        (type, index, all) => all.indexOf(type) === index,
      ),
    [locationTypes],
  );

  const linkTypes = useMemo(
    () =>
      entities
        .map((entity) => entity.entity_type)
        .filter((type, index, all) => all.indexOf(type) === index),
    [entities],
  );

  const activeLinkType = linkTypes.includes(linkType)
    ? linkType
    : (linkTypes[0] ?? "");

  const idOptions = useMemo(
    () =>
      entities.filter(
        (entity) =>
          entity.entity_type === activeLinkType &&
          !entity.mapped &&
          !values.links.some(
            (link) =>
              link.entity_type === entity.entity_type &&
              link.entity_id === entity.entity_id,
          ),
        ),
    [entities, activeLinkType, values.links],
  );

  function patch(change: Partial<LocationFormValues>) {
    onChange({ ...values, ...change });
  }

  function addLink() {
    const entity = idOptions.find((row) => row.entity_id === linkId);
    if (!entity) return;
    patch({
      links: [
        ...values.links,
        {
          entity_type: entity.entity_type,
          entity_id: entity.entity_id,
          label: entity.name,
        },
      ],
    });
    setLinkId("");
  }

  async function geocode() {
    if (!geoQuery.trim()) return;
    setGeoBusy(true);
    setGeoError("");
    setGeoResults([]);
    try {
      const response = await api<{ results: GeocodeResult[] }>("/map/geocode", {
        method: "POST",
        body: { query: geoQuery.trim() },
      });
      setGeoResults(response.results);
      if (response.results.length === 0) setGeoError("no place matched");
    } catch (err) {
      setGeoError(err instanceof Error ? err.message : "geocoding unavailable");
    } finally {
      setGeoBusy(false);
    }
  }

  return (
    <div className="fixed inset-y-0 right-0 z-[1200] w-full max-w-md p-2 sm:p-3">
      <div className="paper custom-scrollbar h-full overflow-y-auto rounded-sm border-2 border-crimson-dark/40 shadow-[0_8px_0_rgba(64,16,18,0.35)]">
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-ink/15 bg-cream px-4 py-3">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-saffron">
              GeoCommand
            </p>
            <h3 className="font-display text-xl text-crimson-deep">
              {mode === "create" ? "Add a location pin" : "Edit location pin"}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm border border-ink/25 px-1.5 py-0.5 text-xs font-bold text-ink/60 hover:bg-ink/10"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 p-4">
          <div>
            <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
              Name
            </label>
            <input
              value={values.name}
              onChange={(event) => patch({ name: event.target.value })}
              className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-sm font-semibold text-ink"
              placeholder="e.g. Main Stage"
            />
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
                Type
              </label>
              <select
                value={values.location_type}
                onChange={(event) => patch({ location_type: event.target.value })}
                className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-sm font-semibold text-ink"
              >
                {!typeOptions.includes(values.location_type) && (
                  <option value={values.location_type}>
                    {typeLabel(values.location_type)} (current)
                  </option>
                )}
                {typeOptions.map((type) => (
                  <option key={type} value={type}>{typeLabel(type)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
                Campus zone
              </label>
              <input
                value={values.campus_zone}
                onChange={(event) => patch({ campus_zone: event.target.value })}
                className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-sm font-semibold text-ink"
                placeholder="north / food court…"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
              Address / description
            </label>
            <input
              value={values.address}
              onChange={(event) => patch({ address: event.target.value })}
              className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-sm font-semibold text-ink"
              placeholder="human-described position on site"
            />
          </div>

          <div className="rounded-sm border border-ink/20 bg-white/40 p-2.5">
            <div className="flex items-center justify-between">
              <SectionTitle>Coordinates</SectionTitle>
              <button
                type="button"
                onClick={onTogglePick}
                className={`rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                  picking
                    ? "border-crimson-dark bg-crimson-dark text-cream"
                    : "border-teal-dark/40 bg-teal/15 text-teal-dark"
                }`}
              >
                {picking ? "click the map…" : "pick on map"}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                step="0.000001"
                min={-90}
                max={90}
                value={values.latitude ?? ""}
                onChange={(event) => patch({ latitude: numberOrNull(event.target.value) })}
                placeholder="latitude"
                className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 font-mono text-xs text-ink"
              />
              <input
                type="number"
                step="0.000001"
                min={-180}
                max={180}
                value={values.longitude ?? ""}
                onChange={(event) => patch({ longitude: numberOrNull(event.target.value) })}
                placeholder="longitude"
                className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 font-mono text-xs text-ink"
              />
            </div>
            <p className="mt-1 text-[9px] leading-snug text-ink/55">
              Both coordinates are optional together. FestOS never guesses a
              position: a pin you save here stays <strong>unverified</strong> until
              somebody confirms it on site.
            </p>

            <div className="mt-2 border-t border-ink/10 pt-2">
              <div className="flex gap-1">
                <input
                  value={geoQuery}
                  onChange={(event) => setGeoQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") geocode();
                  }}
                  placeholder="search an address (optional)"
                  className="min-w-0 flex-1 rounded-sm border border-ink/30 bg-white/75 px-2 py-1 text-[11px] font-semibold text-ink"
                />
                <button
                  type="button"
                  onClick={geocode}
                  disabled={geoBusy || !geoQuery.trim()}
                  className="rounded-sm border border-ink/30 bg-mustard px-2 py-1 text-[9px] font-bold uppercase text-ink disabled:opacity-40"
                >
                  search
                </button>
              </div>
              {geoBusy && <div className="mt-1"><Spinner label="searching…" /></div>}
              {geoError && <p className="mt-1 text-[9px] font-semibold text-crimson-deep">{geoError}</p>}
              {geoResults.length > 0 && (
                <div className="mt-1 max-h-28 space-y-1 overflow-y-auto custom-scrollbar">
                  {geoResults.map((result, index) => (
                    <button
                      key={`${result.display_name}-${index}`}
                      type="button"
                      onClick={() => {
                        patch({
                          latitude: result.latitude,
                          longitude: result.longitude,
                        });
                        setGeoResults([]);
                      }}
                      className="block w-full rounded-sm border border-ink/15 bg-white/60 px-1.5 py-1 text-left text-[10px] font-semibold text-ink/75 hover:border-teal-dark/50"
                    >
                      {result.display_name}
                    </button>
                  ))}
                </div>
              )}
              <p className="mt-1 text-[8px] text-ink/45">
                Suggestions come from OpenStreetMap Nominatim; always verify on site.
              </p>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
              Source reference
            </label>
            <input
              value={values.source_reference}
              onChange={(event) => patch({ source_reference: event.target.value })}
              className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-xs font-semibold text-ink"
              placeholder="map sheet / GPS device / organiser note"
            />
          </div>

          <div className="rounded-sm border border-ink/20 bg-white/40 p-2.5">
            <SectionTitle>Linked Festival records</SectionTitle>
            {values.links.length === 0 ? (
              <p className="text-[10px] italic text-ink/55">No records linked yet.</p>
            ) : (
              <div className="flex flex-wrap gap-1">
                {values.links.map((link) => (
                  <span
                    key={`${link.entity_type}-${link.entity_id}`}
                    className="inline-flex items-center gap-1 rounded-sm border border-ink/25 bg-cream px-1.5 py-0.5 text-[10px] font-semibold text-ink/75"
                  >
                    {typeLabel(link.entity_type)}: {link.label}
                    <button
                      type="button"
                      onClick={() =>
                        patch({
                          links: values.links.filter(
                            (row) =>
                              !(row.entity_type === link.entity_type &&
                                row.entity_id === link.entity_id),
                          ),
                        })
                      }
                      className="text-crimson-deep"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="mt-2 grid grid-cols-[1fr_1.4fr_auto] gap-1">
              <select
                value={activeLinkType}
                onChange={(event) => {
                  setLinkType(event.target.value);
                  setLinkId("");
                }}
                className="rounded-sm border border-ink/30 bg-white/75 px-1 py-1 text-[10px] font-semibold text-ink"
              >
                {linkTypes.map((type) => (
                  <option key={type} value={type}>{typeLabel(type)}</option>
                ))}
              </select>
              <select
                value={linkId}
                onChange={(event) => setLinkId(event.target.value)}
                className="min-w-0 rounded-sm border border-ink/30 bg-white/75 px-1 py-1 text-[10px] font-semibold text-ink"
              >
                <option value="">choose record…</option>
                {idOptions.map((entity) => (
                  <option key={`${entity.entity_type}-${entity.entity_id}`} value={entity.entity_id}>
                    {entity.entity_id} — {entity.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={addLink}
                disabled={!linkId}
                className="rounded-sm border border-ink/30 bg-mustard px-2 py-1 text-[9px] font-bold uppercase text-ink disabled:opacity-40"
              >
                add
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-[10px] font-mono font-bold uppercase tracking-wide text-ink/60">
              Reason (audit note)
            </label>
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1.5 text-xs font-semibold text-ink"
              placeholder="why this pin / record link is correct"
            />
          </div>

          {error && (
            <p className="rounded-sm border border-crimson-dark/40 bg-crimson-dark/10 px-2 py-1.5 text-[11px] font-semibold text-crimson-deep">
              {error}
            </p>
          )}
        </div>

        <div className="sticky bottom-0 flex items-center justify-end gap-2 border-t border-ink/15 bg-cream px-4 py-3">
          <Btn variant="ghost" onClick={onClose} disabled={busy}>cancel</Btn>
          <Btn onClick={() => onSave(reason)} disabled={busy || !values.name.trim()}>
            {busy ? "saving…" : mode === "create" ? "create pin" : "save changes"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

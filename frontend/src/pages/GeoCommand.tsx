import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import type { Role } from "../auth";
import FilterSidebar from "../components/map/FilterSidebar";
import LocationDrawer from "../components/map/LocationDrawer";
import LocationEditor from "../components/map/LocationEditor";
import type { LocationFormValues } from "../components/map/LocationEditor";
import MapCanvas from "../components/map/MapCanvas";
import type { LatLng } from "../components/map/MapCanvas";
import { Legend } from "../components/map/MapWidgets";
import UnmappedPanel from "../components/map/UnmappedPanel";
import { Btn, Spinner } from "../components/ui";
import type {
  MapDuty,
  MapEntitiesResponse,
  MapEntity,
  MapIncidentsResponse,
  MapLocation,
  MapLocationsResponse,
  MapSettings,
  MapSummary,
  MapUnmapped,
  MapUnmappedItem,
} from "../mapTypes";
import { ROLE_LAYERS, nowLocalInput } from "../mapTypes";

const MANAGER_ROLES: Role[] = [
  "director",
  "accommodation_lead",
  "events_lead",
  "logistics_lead",
  "vendor_lead",
];

const FALLBACK_CENTER = { latitude: 20.5937, longitude: 78.9629 };
const FALLBACK_ZOOM = 4;

type EditorState = {
  mode: "create" | "edit";
  id?: number;
  original: LocationFormValues;
  values: LocationFormValues;
};

type SettingsForm = {
  latitude: string;
  longitude: string;
  zoom: string;
  label: string;
  reason: string;
};

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : "request failed";
}

export default function GeoCommand() {
  const { user } = useAuth();
  const role: Role = user?.role ?? "viewer";
  const isDirector = role === "director";
  const canManage = MANAGER_ROLES.includes(role);
  const canViewIncidents = role !== "volunteer" && role !== "viewer";
  const layerOptions = useMemo(() => ROLE_LAYERS[role] ?? [], [role]);

  const [at, setAt] = useState(nowLocalInput);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedLayers, setSelectedLayers] = useState<string[]>(layerOptions);
  const [selectedStatuses, setSelectedStatuses] = useState<string[]>([]);
  const [showIncidentLayer, setShowIncidentLayer] = useState(true);

  const [locations, setLocations] = useState<MapLocation[]>([]);
  const [summary, setSummary] = useState<MapSummary | null>(null);
  const [settings, setSettings] = useState<MapSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [lastLoaded, setLastLoaded] = useState<Date | null>(null);
  const [dataTick, setDataTick] = useState(0);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<MapLocation | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailTick, setDetailTick] = useState(0);

  const [duties, setDuties] = useState<MapDuty[]>([]);
  const [incidents, setIncidents] = useState<MapIncidentsResponse | null>(null);

  const [fitRequest, setFitRequest] = useState(0);
  const [notice, setNotice] = useState("");

  const [editor, setEditor] = useState<EditorState | null>(null);
  const [editorBusy, setEditorBusy] = useState(false);
  const [editorError, setEditorError] = useState("");
  const [picking, setPicking] = useState(false);
  const [entities, setEntities] = useState<MapEntity[]>([]);

  const [showUnmapped, setShowUnmapped] = useState(false);
  const [unmapped, setUnmapped] = useState<MapUnmapped | null>(null);
  const [unmappedBusy, setUnmappedBusy] = useState(false);
  const [unmappedError, setUnmappedError] = useState("");

  const [showSettings, setShowSettings] = useState(false);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsError, setSettingsError] = useState("");
  const [settingsForm, setSettingsForm] = useState<SettingsForm>({
    latitude: "",
    longitude: "",
    zoom: "16",
    label: "",
    reason: "",
  });

  const requestRef = useRef(0);
  const notify = useCallback((message: string) => setNotice(message), []);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(handle);
  }, [search]);

  useEffect(() => {
    if (!notice) return;
    const handle = window.setTimeout(() => setNotice(""), 4500);
    return () => window.clearTimeout(handle);
  }, [notice]);

  const pollSeconds = summary?.poll_seconds ?? 60;

  useEffect(() => {
    let cancelled = false;
    const requestId = ++requestRef.current;

    async function load(initial: boolean) {
      if (initial) setLoading(true);
      const params = new URLSearchParams();
      if (at) params.set("at", at);
      if (debouncedSearch) params.set("search", debouncedSearch);
      if (selectedStatuses.length) params.set("statuses", selectedStatuses.join(","));
      try {
        const [locationsResponse, summaryResponse] = await Promise.all([
          api<MapLocationsResponse>(`/map/locations?${params.toString()}`),
          api<MapSummary>(`/map/summary?at=${encodeURIComponent(at)}`),
        ]);
        if (cancelled || requestId !== requestRef.current) return;
        setLocations(locationsResponse.locations);
        setSummary(summaryResponse);
        setLoadError("");
        setLastLoaded(new Date());
      } catch (err) {
        if (!cancelled && requestId === requestRef.current) {
          setLoadError(errorText(err));
        }
      } finally {
        if (!cancelled && requestId === requestRef.current) setLoading(false);
      }
    }

    void load(true);
    const handle = window.setInterval(() => void load(false), pollSeconds * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [at, debouncedSearch, selectedStatuses, pollSeconds, dataTick]);

  const loadSupport = useCallback(async () => {
    try {
      const dutiesResponse = await api<{ duties: MapDuty[] }>("/map/duties");
      setDuties(dutiesResponse.duties);
      if (canViewIncidents) {
        const incidentResponse = await api<MapIncidentsResponse>("/map/incidents");
        setIncidents(incidentResponse);
      }
    } catch {
      /* supporting panels fail quietly; the map itself surfaces load errors */
    }
  }, [canViewIncidents]);

  useEffect(() => {
    void loadSupport();
  }, [loadSupport]);

  useEffect(() => {
    api<MapSettings>("/map/settings").then(setSettings).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null);
      setDetailError("");
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setDetailError("");
    api<MapLocation>(`/map/locations/${selectedId}?at=${encodeURIComponent(at)}`)
      .then((payload) => {
        if (!cancelled) setDetail(payload);
      })
      .catch((err) => {
        if (!cancelled) {
          setDetail(null);
          setDetailError(errorText(err));
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, at, detailTick]);

  const visibleLocations = useMemo(() => {
    if (layerOptions.length === 0) return locations;
    if (selectedLayers.length === 0) return [];
    const active = new Set(selectedLayers);
    return locations.filter((location) =>
      location.layers.some((layer) => active.has(layer)),
    );
  }, [locations, selectedLayers, layerOptions]);

  const draft: LatLng | null =
    editor &&
    editor.values.latitude !== null &&
    editor.values.longitude !== null
      ? {
          latitude: editor.values.latitude,
          longitude: editor.values.longitude,
        }
      : null;

  const mapCenter = {
    latitude: settings?.center?.latitude ?? FALLBACK_CENTER.latitude,
    longitude: settings?.center?.longitude ?? FALLBACK_CENTER.longitude,
  };
  const mapZoom = settings?.zoom ?? FALLBACK_ZOOM;

  function refresh() {
    setDataTick((value) => value + 1);
    setDetailTick((value) => value + 1);
    void loadSupport();
    if (showUnmapped) void loadUnmapped();
  }

  function toggleLayer(layer: string) {
    setSelectedLayers((current) =>
      current.includes(layer)
        ? current.filter((row) => row !== layer)
        : [...current, layer],
    );
  }

  function toggleStatus(status: string) {
    setSelectedStatuses((current) =>
      current.includes(status)
        ? current.filter((row) => row !== status)
        : [...current, status],
    );
  }

  async function ensureEntities(force = false) {
    if (!force && entities.length > 0) return;
    try {
      const response = await api<MapEntitiesResponse>("/map/entities");
      setEntities(response.entities);
    } catch (err) {
      setEditorError(errorText(err));
    }
  }

  async function loadUnmapped() {
    setUnmappedBusy(true);
    setUnmappedError("");
    try {
      const payload = await api<MapUnmapped>("/map/unmapped");
      setUnmapped(payload);
    } catch (err) {
      setUnmappedError(errorText(err));
    } finally {
      setUnmappedBusy(false);
    }
  }

  function openUnmapped() {
    setShowUnmapped(true);
    void loadUnmapped();
  }

  function openCreate(prefill: Partial<LocationFormValues> = {}) {
    const values: LocationFormValues = {
      name: "",
      location_type: layerOptions[0] ?? "venue",
      latitude: null,
      longitude: null,
      address: "",
      campus_zone: "",
      source_reference: "",
      links: [],
      ...prefill,
    };
    setEditor({ mode: "create", original: values, values });
    setEditorError("");
    setPicking(false);
    setSelectedId(null);
    setDetail(null);
    void ensureEntities();
  }

  function openEdit() {
    if (!detail) return;
    const values: LocationFormValues = {
      name: detail.name,
      location_type: detail.location_type,
      latitude: detail.latitude,
      longitude: detail.longitude,
      address: detail.address ?? "",
      campus_zone: detail.campus_zone ?? "",
      source_reference: detail.source_reference ?? "",
      links: detail.links,
    };
    setEditor({ mode: "edit", id: detail.id, original: values, values });
    setEditorError("");
    setPicking(false);
    void ensureEntities();
  }

  async function saveEditor(reason: string) {
    if (!editor) return;
    setEditorBusy(true);
    setEditorError("");
    const values = editor.values;
    const body: Record<string, unknown> = {
      name: values.name.trim(),
      address: values.address.trim() || null,
      campus_zone: values.campus_zone.trim() || null,
      source_reference: values.source_reference.trim() || null,
      links: values.links.map((link) => ({
        entity_type: link.entity_type,
        entity_id: link.entity_id,
      })),
      reason: reason.trim() || null,
    };
    if (
      editor.mode === "create" ||
      values.location_type !== editor.original.location_type
    ) {
      body.location_type = values.location_type;
    }
    try {
      let saved: MapLocation;
      if (editor.mode === "create") {
        body.latitude = values.latitude;
        body.longitude = values.longitude;
        saved = await api<MapLocation>("/map/locations", {
          method: "POST",
          body,
        });
      } else {
        if (
          values.latitude !== editor.original.latitude ||
          values.longitude !== editor.original.longitude
        ) {
          body.latitude = values.latitude;
          body.longitude = values.longitude;
        }
        saved = await api<MapLocation>(`/map/locations/${editor.id}`, {
          method: "PATCH",
          body,
        });
      }
      setDetail(saved);
      setSelectedId(saved.id);
      setEditor(null);
      setPicking(false);
      notify(
        "location saved — a pin is only trusted after someone verifies it on site",
      );
      setDataTick((value) => value + 1);
      setDetailTick((value) => value + 1);
      void ensureEntities(true);
      if (showUnmapped) void loadUnmapped();
    } catch (err) {
      setEditorError(errorText(err));
    } finally {
      setEditorBusy(false);
    }
  }

  async function verifySelected() {
    if (!detail) return;
    try {
      const saved = await api<MapLocation>(
        `/map/locations/${detail.id}/verify`,
        {
          method: "POST",
          body: { reason: "pin confirmed on site via GeoCommand" },
        },
      );
      setDetail(saved);
      notify(`'${saved.name}' verified on site`);
      setDataTick((value) => value + 1);
    } catch (err) {
      notify(errorText(err));
    }
  }

  function handlePick(point: LatLng) {
    if (!editor || !picking) return;
    setEditor({
      ...editor,
      values: {
        ...editor.values,
        latitude: point.latitude,
        longitude: point.longitude,
      },
    });
    setPicking(false);
    notify("draft point captured — it is still unverified");
  }

  function pinEntity(item: MapUnmappedItem) {
    if (!item.entity_type || !item.entity_id) return;
    setShowUnmapped(false);
    openCreate({
      name: item.name,
      location_type: item.location_type,
      source_reference: item.source_reference ?? "",
      links: [
        {
          entity_type: item.entity_type,
          entity_id: item.entity_id,
          label: item.name,
        },
      ],
    });
  }

  function openSettings() {
    setSettingsForm({
      latitude: String(settings?.center?.latitude ?? ""),
      longitude: String(settings?.center?.longitude ?? ""),
      zoom: String(settings?.zoom ?? 16),
      label: settings?.label ?? "",
      reason: "",
    });
    setSettingsError("");
    setShowSettings(true);
  }

  async function saveSettings() {
    const latitude = Number(settingsForm.latitude);
    const longitude = Number(settingsForm.longitude);
    const zoom = Number(settingsForm.zoom);
    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude) ||
      !Number.isFinite(zoom)
    ) {
      setSettingsError("enter numeric latitude, longitude and zoom");
      return;
    }
    setSettingsBusy(true);
    setSettingsError("");
    try {
      const saved = await api<MapSettings>("/map/settings", {
        method: "PATCH",
        body: {
          latitude,
          longitude,
          zoom,
          label: settingsForm.label.trim() || null,
          reason: settingsForm.reason.trim() || null,
        },
      });
      setSettings(saved);
      setShowSettings(false);
      notify("festival map centre saved");
    } catch (err) {
      setSettingsError(errorText(err));
    } finally {
      setSettingsBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-[290px_minmax(0,1fr)] lg:items-start">
        <FilterSidebar
          role={role}
          summary={summary}
          layerOptions={layerOptions}
          selectedLayers={selectedLayers}
          onToggleLayer={toggleLayer}
          onAllLayers={() => setSelectedLayers(layerOptions)}
          statusOptions={Object.keys(summary?.status_counts ?? {})}
          selectedStatuses={selectedStatuses}
          onToggleStatus={toggleStatus}
          search={search}
          onSearch={setSearch}
          at={at}
          onAt={setAt}
          onNow={() => setAt(nowLocalInput())}
          onFit={() => setFitRequest((value) => value + 1)}
          canManage={canManage}
          isDirector={isDirector}
          unmappedCount={summary?.unmapped_total ?? 0}
          onAdd={() => openCreate()}
          onSettings={openSettings}
          onUnmapped={openUnmapped}
          incidents={incidents}
          canViewIncidents={canViewIncidents}
          showIncidentLayer={showIncidentLayer}
          onToggleIncidentLayer={() => setShowIncidentLayer((value) => !value)}
          onSelectIncident={(locationId) => setSelectedId(locationId)}
          duties={duties}
        />

        <div className="paper overflow-hidden rounded-sm border-2 border-crimson-dark/30 shadow-[0_3px_0_rgba(64,16,18,0.35)]">
          <div className="flex flex-wrap items-center gap-2 border-b-2 border-crimson-dark/20 bg-cream-dim/70 px-3 py-1.5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.14em] text-crimson-dark/70">
              {visibleLocations.length} pins shown · {locations.length} in role scope
            </p>
            {!settings?.configured && (
              <span className="rounded-sm border border-dashed border-saffron bg-mustard/25 px-1.5 py-0.5 text-[9px] font-bold uppercase text-crimson-deep">
                no site centre configured
              </span>
            )}
            <div className="ml-auto flex items-center gap-2">
              {loadError && (
                <span className="max-w-[260px] truncate text-[10px] font-semibold text-crimson-deep">
                  {loadError}
                </span>
              )}
              <span className="hidden font-mono text-[9px] text-ink/50 sm:inline">
                {lastLoaded ? `updated ${lastLoaded.toLocaleTimeString()}` : "loading…"}
              </span>
              <button
                type="button"
                onClick={refresh}
                className="rounded-sm border border-ink/25 bg-white/60 px-1.5 py-0.5 text-[9px] font-bold uppercase text-ink/70 hover:bg-teal/15"
              >
                refresh
              </button>
            </div>
          </div>

          <div className="relative h-[62vh] min-h-[440px] lg:h-[calc(100vh-13rem)]">
            <MapCanvas
              locations={visibleLocations}
              center={mapCenter}
              zoom={mapZoom}
              selectedId={selectedId}
              picking={picking}
              draft={draft}
              fitRequest={fitRequest}
              showIncidents={showIncidentLayer}
              onSelect={(id) => setSelectedId(id)}
              onPick={handlePick}
            />
            <Legend />

            {loading && locations.length === 0 && (
              <div className="pointer-events-none absolute inset-0 z-[550] flex items-center justify-center bg-cream/45">
                <div className="rounded-sm border-2 border-crimson-dark/30 bg-cream px-4 py-3 shadow-md">
                  <Spinner label="loading operations map…" />
                </div>
              </div>
            )}

            {!loading && visibleLocations.length === 0 && (
              <div className="pointer-events-none absolute inset-0 z-[550] flex items-center justify-center p-4">
                <div className="pointer-events-auto max-w-sm rounded-sm border-2 border-crimson-dark/35 bg-cream/95 p-4 text-center shadow-[0_4px_0_rgba(64,16,18,0.3)]">
                  <p className="font-display text-lg leading-tight text-crimson-deep">
                    {locations.length === 0
                      ? "No registered pins are visible to this role yet"
                      : "No pins match the current filters"}
                  </p>
                  <p className="mt-1.5 text-[11px] leading-snug text-ink/65">
                    {locations.length === 0
                      ? "FestOS never invents a position. Verified coordinates are added by an authorised organiser; records missing a pin stay listed as unmapped."
                      : "Clear a layer or status filter, or search for a different record."}
                  </p>
                  {canManage && (
                    <div className="mt-2.5 flex justify-center gap-1.5">
                      <Btn
                        className="!px-2 !py-1 !text-[10px]"
                        onClick={() => openCreate()}
                      >
                        add location
                      </Btn>
                      <Btn
                        variant="ghost"
                        className="!px-2 !py-1 !text-[10px]"
                        onClick={openUnmapped}
                      >
                        review unmapped
                      </Btn>
                    </div>
                  )}
                </div>
              </div>
            )}

            {detail && !editor && (
              <div className="absolute inset-y-0 right-0 z-[1100] w-full sm:w-[400px]">
                <LocationDrawer
                  detail={detail}
                  loading={detailLoading}
                  error={detailError}
                  canManage={detail.can_manage ?? canManage}
                  isDirector={isDirector}
                  onClose={() => {
                    setSelectedId(null);
                    setDetail(null);
                  }}
                  onEdit={openEdit}
                  onVerify={verifySelected}
                  onRefresh={() => {
                    setDetailTick((value) => value + 1);
                    setDataTick((value) => value + 1);
                    void loadSupport();
                  }}
                  onSelectLocation={(id) => setSelectedId(id)}
                  notify={notify}
                />
              </div>
            )}

            {notice && (
              <div className="pointer-events-none absolute left-1/2 top-3 z-[1150] w-[min(92%,420px)] -translate-x-1/2 rounded-sm border-2 border-teal-dark/40 bg-cream/95 px-3 py-1.5 text-center text-[11px] font-semibold text-ink shadow-md">
                {notice}
              </div>
            )}

            <div className="pointer-events-none absolute bottom-3 right-3 z-[550] hidden rounded-sm border border-ink/20 bg-cream/90 px-2 py-1 text-right font-mono text-[9px] text-ink/55 sm:block">
              <p>evaluated at {summary?.selected_at?.replace("T", " ").slice(0, 16) ?? at}</p>
              <p>
                {summary?.timezone ?? "Asia/Kolkata"} · poll {pollSeconds}s
              </p>
            </div>
          </div>
        </div>
      </div>

      {editor && (
        <LocationEditor
          mode={editor.mode}
          values={editor.values}
          locationTypes={layerOptions}
          entities={entities}
          picking={picking}
          busy={editorBusy}
          error={editorError}
          onChange={(values) => setEditor({ ...editor, values })}
          onTogglePick={() => setPicking((value) => !value)}
          onSave={(reason) => void saveEditor(reason)}
          onClose={() => {
            setEditor(null);
            setPicking(false);
            setEditorError("");
          }}
        />
      )}

      {showUnmapped && (
        <UnmappedPanel
          data={unmapped}
          loading={unmappedBusy}
          error={unmappedError}
          onClose={() => setShowUnmapped(false)}
          onOpenRegistry={(locationId) => {
            setShowUnmapped(false);
            setSelectedId(locationId);
            setDetailTick((value) => value + 1);
          }}
          onPinEntity={pinEntity}
          onRefresh={() => void loadUnmapped()}
        />
      )}

      {showSettings && isDirector && (
        <div className="fixed inset-0 z-[1300] flex items-center justify-center bg-ink/45 p-3">
          <div className="paper w-full max-w-sm rounded-sm border-2 border-crimson-dark/40 p-4 shadow-[0_8px_0_rgba(64,16,18,0.35)]">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-saffron">
              Director setting
            </p>
            <h3 className="font-display text-xl text-crimson-deep">Festival map centre</h3>
            <p className="mt-1 text-[10px] leading-snug text-ink/60">
              This only sets where the map opens. It never moves or invents any
              record pin — those need their own saved coordinates and verification.
            </p>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <label className="text-[10px] font-mono font-bold uppercase text-ink/60">
                latitude
                <input
                  value={settingsForm.latitude}
                  onChange={(event) =>
                    setSettingsForm({ ...settingsForm, latitude: event.target.value })
                  }
                  className="mt-0.5 w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1 font-mono text-xs"
                  placeholder="20.5937"
                />
              </label>
              <label className="text-[10px] font-mono font-bold uppercase text-ink/60">
                longitude
                <input
                  value={settingsForm.longitude}
                  onChange={(event) =>
                    setSettingsForm({ ...settingsForm, longitude: event.target.value })
                  }
                  className="mt-0.5 w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1 font-mono text-xs"
                  placeholder="78.9629"
                />
              </label>
            </div>
            <div className="mt-2 grid grid-cols-[90px_1fr] gap-2">
              <label className="text-[10px] font-mono font-bold uppercase text-ink/60">
                zoom
                <input
                  value={settingsForm.zoom}
                  onChange={(event) =>
                    setSettingsForm({ ...settingsForm, zoom: event.target.value })
                  }
                  className="mt-0.5 w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1 font-mono text-xs"
                />
              </label>
              <label className="text-[10px] font-mono font-bold uppercase text-ink/60">
                label
                <input
                  value={settingsForm.label}
                  onChange={(event) =>
                    setSettingsForm({ ...settingsForm, label: event.target.value })
                  }
                  className="mt-0.5 w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1 text-xs font-semibold"
                  placeholder="Aarohan festival grounds"
                />
              </label>
            </div>
            <label className="mt-2 block text-[10px] font-mono font-bold uppercase text-ink/60">
              reason (audit)
              <input
                value={settingsForm.reason}
                onChange={(event) =>
                  setSettingsForm({ ...settingsForm, reason: event.target.value })
                }
                className="mt-0.5 w-full rounded-sm border border-ink/30 bg-white/75 px-2 py-1 text-xs font-semibold"
                placeholder="site centre confirmed with organiser map"
              />
            </label>
            {settingsError && (
              <p className="mt-2 rounded-sm border border-crimson-dark/40 bg-crimson-dark/10 px-2 py-1 text-[10px] font-semibold text-crimson-deep">
                {settingsError}
              </p>
            )}
            <div className="mt-3 flex justify-end gap-2">
              <Btn
                variant="ghost"
                className="!px-2 !py-1 !text-[10px]"
                onClick={() => setShowSettings(false)}
                disabled={settingsBusy}
              >
                cancel
              </Btn>
              <Btn
                className="!px-2 !py-1 !text-[10px]"
                onClick={() => void saveSettings()}
                disabled={
                  settingsBusy ||
                  !settingsForm.latitude.trim() ||
                  !settingsForm.longitude.trim()
                }
              >
                {settingsBusy ? "saving…" : "save centre"}
              </Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from "react";
import { api } from "../../api";
import type {
  MapContext,
  MapDuty,
  MapLocation,
  MapRoom,
} from "../../mapTypes";
import { TASK_TYPES, typeLabel } from "../../mapTypes";
import { Badge, Btn, EmptyState, Spinner } from "../ui";
import {
  IncidentRow,
  SectionTitle,
  StatusChip,
  VerificationChip,
} from "./MapWidgets";

function fmtTime(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 16);
}

function fmtNum(value: unknown, digits = 0): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return digits ? value.toFixed(digits) : String(value);
}

function OccupancyBar({ pct }: { pct: number | null | undefined }) {
  const value = Math.max(0, Math.min(100, pct ?? 0));
  return (
    <div className="mt-1.5">
      <div className="h-2 overflow-hidden rounded-full bg-ink/10">
        <div
          className={`h-full rounded-full ${
            value >= 100 ? "bg-crimson-dark" : value >= 80 ? "bg-mustard" : "bg-teal"
          }`}
          style={{ width: `${value}%` }}
        />
      </div>
      <p className="mt-0.5 text-right font-mono text-[9px] text-ink/55">
        {pct === null || pct === undefined ? "occupancy unknown" : `${pct}% allocated`}
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-sm border border-ink/15 bg-white/45 px-1.5 py-1">
      <p className="text-[9px] font-mono uppercase tracking-wide text-ink/50">{label}</p>
      <p className="font-display text-base leading-tight text-ink">{value}</p>
    </div>
  );
}

function RoomRow({ room }: { room: MapRoom }) {
  const tone =
    room.allocation_status === "full"
      ? "bg-crimson-dark text-cream"
      : room.allocation_status === "unavailable"
        ? "bg-ink/20 text-ink/60"
        : room.allocation_status === "partial"
          ? "bg-mustard text-ink"
          : "bg-teal/25 text-teal-dark";
  return (
    <div className="flex items-center gap-2 border-b border-ink/10 py-1 last:border-0">
      <span className="w-20 shrink-0 font-mono text-[10px] font-bold text-ink">{room.raw_id}</span>
      <span className="text-[10px] text-ink/60">
        {room.allocated}/{room.beds} beds
      </span>
      <span className="text-[10px] text-ink/60">vacant {room.vacant}</span>
      {room.accessible && (
        <span className="rounded-sm bg-teal/20 px-1 text-[9px] font-bold text-teal-dark">accessible</span>
      )}
      <span className={`ml-auto rounded-sm px-1 py-0 text-[9px] font-bold uppercase ${tone}`}>
        {room.allocation_status}
      </span>
    </div>
  );
}

function HostelContext({ ctx }: { ctx: MapContext }) {
  const rooms = ctx.rooms ?? [];
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-display text-base text-ink">{ctx.block ? `Block ${ctx.block}` : "Hostel block"}</p>
        <span className="font-mono text-[10px] text-ink/55">{ctx.rooms_total ?? 0} rooms</span>
      </div>
      <OccupancyBar pct={ctx.occupancy_pct} />
      <div className="mt-1.5 grid grid-cols-3 gap-1">
        <Stat label="Beds" value={fmtNum(ctx.total_beds)} />
        <Stat label="Allocated" value={fmtNum(ctx.allocated_beds)} />
        <Stat label="Vacant" value={fmtNum(ctx.vacant_beds)} />
        <Stat label="Ready rooms" value={fmtNum(ctx.ready_rooms)} />
        <Stat label="Accessible" value={fmtNum(ctx.accessible_rooms)} />
        <Stat label="Unavailable" value={fmtNum(ctx.unavailable_beds)} />
      </div>
      {(ctx.floors ?? []).length > 0 && (
        <div className="mt-2">
          <SectionTitle>Floors</SectionTitle>
          <div className="space-y-0.5">
            {(ctx.floors ?? []).map((floor) => (
              <div key={floor.floor} className="flex items-center gap-2 text-[10px] text-ink/70">
                <span className="w-12 font-mono font-bold">F{floor.floor}</span>
                <span>{floor.rooms} rooms</span>
                <span>{floor.beds} beds</span>
                <span className="text-teal-dark">vacant {floor.vacant}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {rooms.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-[10px] font-bold uppercase tracking-wide text-crimson-deep">
            Room explorer ({rooms.length})
          </summary>
          <div className="mt-1 max-h-52 overflow-y-auto pr-1 custom-scrollbar">
            {rooms.map((room) => (
              <RoomRow key={room.id} room={room} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function VenueContext({ ctx }: { ctx: MapContext }) {
  const current = ctx.current_events ?? [];
  const upcoming = ctx.upcoming_events ?? [];
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-display text-base text-ink">{ctx.name ?? "Venue"}</p>
        <span className="font-mono text-[10px] text-ink/55">capacity {fmtNum(ctx.capacity)}</span>
      </div>
      {current.length > 0 ? (
        <div className="mt-1.5 space-y-1">
          <SectionTitle>Happening now</SectionTitle>
          {current.map((event) => (
            <div key={event.id} className="rounded-sm border border-mustard/60 bg-mustard/15 px-2 py-1">
              <p className="text-[11px] font-bold text-ink">{event.name}</p>
              <p className="text-[10px] text-ink/60">
                {fmtTime(event.start)} → {fmtTime(event.end)} · {event.registration_count} registered
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-1.5 text-[10px] italic text-ink/55">No session at the selected time.</p>
      )}
      {upcoming.length > 0 && (
        <div className="mt-2">
          <SectionTitle>Next up</SectionTitle>
          <div className="space-y-0.5">
            {upcoming.slice(0, 4).map((event) => (
              <div key={event.id} className="flex items-center gap-2 text-[10px] text-ink/70">
                <span className="font-mono text-ink/50">{fmtTime(event.start).slice(11)}</span>
                <span className="truncate">{event.name}</span>
                <span className="ml-auto shrink-0 text-ink/45">{event.registration_count} reg</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-2 grid grid-cols-3 gap-1">
        <Stat label="Events" value={fmtNum(ctx.event_count)} />
        <Stat label="Done" value={fmtNum(ctx.completed_count)} />
        <Stat label="Conflicts" value={fmtNum((ctx.conflicts ?? []).length)} />
        <Stat label="Unscheduled" value={fmtNum(ctx.unscheduled_count)} />
        <Stat label="Volunteers" value={fmtNum((ctx.assigned_staff ?? []).length)} />
        <Stat label="Equipment" value={fmtNum((ctx.required_equipment ?? []).length)} />
      </div>
      {(ctx.required_equipment ?? []).length > 0 && (
        <div className="mt-2">
          <SectionTitle>Required equipment now</SectionTitle>
          <div className="flex flex-wrap gap-1">
            {(ctx.required_equipment ?? []).map((need, index) => (
              <span key={index} className="rounded-sm border border-ink/20 bg-white/50 px-1.5 py-0.5 text-[10px] font-semibold">
                {typeof need === "string" ? need : JSON.stringify(need)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function VendorContext({ ctx }: { ctx: MapContext }) {
  const verified = Boolean(ctx.verified_compliant);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-display text-base text-ink">{ctx.name ?? "Vendor"}</p>
        <span className={`rounded-sm px-1.5 py-0.5 text-[9px] font-bold uppercase ${
          verified ? "bg-teal/25 text-teal-dark" : "bg-mustard/40 text-crimson-deep"
        }`}>
          {verified ? "compliance verified" : "compliance not verified"}
        </span>
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-1">
        <Stat label="Certificate" value={ctx.compliance_status ?? "unknown"} />
        <Stat label="Expiry" value={ctx.hygiene_cert_expiry ?? "unknown"} />
        <Stat label="Hours" value={ctx.hours ?? "unknown"} />
        <Stat label="Open now" value={ctx.is_open === null || ctx.is_open === undefined ? "unknown" : ctx.is_open ? "yes" : "no"} />
        <Stat label="Capacity/day" value={fmtNum(ctx.capacity_per_day)} />
        <Stat label="Availability" value={String(ctx.availability ?? "unknown")} />
      </div>
      {(ctx.dietary_coverage ?? []).length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {(ctx.dietary_coverage ?? []).map((tag) => (
            <Badge key={tag} sev="info">{tag}</Badge>
          ))}
        </div>
      )}
      {(ctx.menu ?? []).length > 0 && (
        <p className="mt-1.5 text-[10px] text-ink/65">
          Menu: {(ctx.menu ?? []).join(", ")}
        </p>
      )}
      {ctx.rate !== undefined && ctx.rate !== null && (
        <p className="mt-1 text-[10px] font-semibold text-ink/70">
          Rate: ₹{ctx.rate} · {ctx.payment_terms ?? "terms unknown"}
        </p>
      )}
    </div>
  );
}

function InventoryContext({ ctx }: { ctx: MapContext }) {
  const items = ctx.items ?? [];
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-display text-base text-ink">{ctx.label ?? "Stock location"}</p>
        <span className="font-mono text-[10px] text-ink/55">{items.length} items</span>
      </div>
      <div className="mt-1.5 grid grid-cols-3 gap-1">
        <Stat label="On hand" value={fmtNum(ctx.total_on_hand)} />
        <Stat label="Reserved" value={fmtNum(ctx.reserved_quantity)} />
        <Stat label="Repair" value={fmtNum(ctx.under_repair_quantity)} />
      </div>
      {items.length > 0 && (
        <div className="mt-2 max-h-44 overflow-y-auto pr-1 custom-scrollbar">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-left font-mono uppercase text-ink/45">
                <th className="py-0.5">item</th>
                <th className="py-0.5 text-right">on hand</th>
                <th className="py-0.5 text-right">avail</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 30).map((item) => (
                <tr key={item.id} className="border-t border-ink/10">
                  <td className="max-w-[140px] truncate py-0.5 font-semibold text-ink/75">
                    {item.name}
                    {item.condition && item.condition !== "good" && (
                      <span className="ml-1 text-[9px] font-bold uppercase text-crimson-deep">
                        {item.condition}
                      </span>
                    )}
                  </td>
                  <td className="py-0.5 text-right font-mono">{item.on_hand}</td>
                  <td className={`py-0.5 text-right font-mono ${item.available > 0 ? "text-teal-dark" : "text-crimson-deep"}`}>
                    {item.available}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(ctx.recent_movements ?? []).length > 0 && (
        <div className="mt-2">
          <SectionTitle>Recent ledger movements</SectionTitle>
          <div className="space-y-0.5">
            {(ctx.recent_movements ?? []).slice(0, 4).map((movement) => (
              <p key={movement.id} className="truncate text-[10px] text-ink/65">
                <span className="font-mono">{movement.qty > 0 ? `+${movement.qty}` : movement.qty}</span>{" "}
                {movement.name ?? movement.sku} · {movement.to_location ?? movement.from_location}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ExternalContext({ ctx }: { ctx: MapContext }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <p className="font-display text-base text-ink">{ctx.property ?? "External stay"}</p>
        <span className="font-mono text-[10px] text-ink/55">{fmtNum(ctx.distance_km, 1)} km</span>
      </div>
      <OccupancyBar pct={ctx.occupancy_pct} />
      <div className="mt-1.5 grid grid-cols-3 gap-1">
        <Stat label="Beds" value={fmtNum(ctx.beds)} />
        <Stat label="Allocated" value={fmtNum(ctx.allocated_beds)} />
        <Stat label="Vacant" value={fmtNum(ctx.vacant_beds)} />
      </div>
      <p className="mt-1.5 text-[10px] text-ink/65">
        transport: {ctx.transport_available ?? "unknown"} · travel:{" "}
        {ctx.travel_minutes ? `${ctx.travel_minutes} min` : "unknown"} · safety:{" "}
        {ctx.safety_coverage ?? "unknown"}
      </p>
    </div>
  );
}

function ContextView({ context }: { context: MapContext }) {
  if (context.kind === "hostel_block") return <HostelContext ctx={context} />;
  if (context.kind === "external_stay") return <ExternalContext ctx={context} />;
  if (context.kind === "venue") return <VenueContext ctx={context} />;
  if (context.kind === "vendor") return <VendorContext ctx={context} />;
  if (context.kind === "inventory_location") return <InventoryContext ctx={context} />;
  return (
    <p className="text-[10px] text-ink/60">
      No map detail for {context.kind ?? "this record"}.
    </p>
  );
}

export default function LocationDrawer({
  detail,
  loading,
  error,
  canManage,
  isDirector,
  onClose,
  onEdit,
  onVerify,
  onRefresh,
  onSelectLocation,
  notify,
}: {
  detail: MapLocation | null;
  loading: boolean;
  error: string;
  canManage: boolean;
  isDirector: boolean;
  onClose: () => void;
  onEdit: () => void;
  onVerify: () => void;
  onRefresh: () => void;
  onSelectLocation: (id: number) => void;
  notify: (message: string) => void;
}) {
  const [dutyUser, setDutyUser] = useState("volunteer");
  const [dutyType, setDutyType] = useState("task");
  const [dutyLabel, setDutyLabel] = useState("");
  const [dutyBusy, setDutyBusy] = useState(false);
  const [dutyError, setDutyError] = useState("");

  async function addDuty() {
    if (!detail) return;
    setDutyBusy(true);
    setDutyError("");
    try {
      await api("/map/duties", {
        method: "POST",
        body: {
          username: dutyUser.trim(),
          location_id: detail.id,
          task_type: dutyType,
          label: dutyLabel.trim() || null,
        },
      });
      setDutyLabel("");
      notify(`duty assigned to ${dutyUser.trim()}`);
      onRefresh();
    } catch (err) {
      setDutyError(err instanceof Error ? err.message : "could not assign duty");
    } finally {
      setDutyBusy(false);
    }
  }

  async function removeDuty(duty: MapDuty) {
    setDutyBusy(true);
    setDutyError("");
    try {
      await api(`/map/duties/${duty.id}`, { method: "DELETE" });
      notify(`duty #${duty.id} deactivated`);
      onRefresh();
    } catch (err) {
      setDutyError(err instanceof Error ? err.message : "could not remove duty");
    } finally {
      setDutyBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="paper flex h-full items-center justify-center border-2 border-crimson-dark/30">
        <Spinner label="loading location…" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="paper flex h-full flex-col justify-center gap-3 border-2 border-crimson-dark/30 p-4">
        <p className="text-sm font-semibold text-crimson-deep">refused: {error}</p>
        <Btn variant="ghost" onClick={onClose}>close</Btn>
      </div>
    );
  }
  if (!detail) return null;

  const contexts = Object.values(detail.contexts ?? {});
  const duties = detail.duties ?? [];

  return (
    <div className="paper flex h-full flex-col border-2 border-crimson-dark/30 shadow-[-4px_0_0_rgba(64,16,18,0.2)]">
      <div className="border-b border-ink/15 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-saffron">
              {typeLabel(detail.location_type)}
            </p>
            <h3 className="truncate font-display text-xl leading-tight text-crimson-deep">
              {detail.name}
            </h3>
            <p className="mt-0.5 font-mono text-[10px] text-ink/55">
              #{detail.id}
              {detail.mapped
                ? ` · ${detail.latitude?.toFixed(5)}, ${detail.longitude?.toFixed(5)}`
                : " · no coordinates"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm border border-ink/25 px-1.5 py-0.5 text-xs font-bold text-ink/60 hover:bg-ink/10"
          >
            ✕
          </button>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <StatusChip status={detail.operational_status} />
          <VerificationChip verified={detail.coordinates_verified} />
          {detail.has_incident && <Badge sev="error">incident</Badge>}
        </div>
        {detail.campus_zone && (
          <p className="mt-1 text-[10px] text-ink/60">zone: {detail.campus_zone}</p>
        )}
        {detail.address && (
          <p className="text-[10px] text-ink/60">{detail.address}</p>
        )}
      </div>

      <div className="custom-scrollbar flex-1 space-y-3 overflow-y-auto p-3">
        {contexts.length === 0 && (
          <EmptyState>
            No operational data is linked to this pin for your role.
          </EmptyState>
        )}
        {contexts.map((context, index) => (
          <section key={`${context.kind}-${index}`} className="rounded-sm border border-ink/15 bg-white/40 p-2.5">
            <ContextView context={context} />
          </section>
        ))}

        {detail.incidents.length > 0 && (
          <section className="rounded-sm border border-crimson-dark/25 bg-crimson-dark/5 p-2.5">
            <SectionTitle>Operational incidents</SectionTitle>
            <div className="space-y-1">
              {detail.incidents.map((incident) => (
                <IncidentRow
                  key={incident.id}
                  incident={incident}
                  onOpen={onSelectLocation}
                />
              ))}
            </div>
            <p className="mt-1 text-[9px] text-ink/50">
              Previewed disruptions are potential effects; applied disruptions are verified.
            </p>
          </section>
        )}

        <section className="rounded-sm border border-ink/15 bg-white/40 p-2.5">
          <SectionTitle>Linked records</SectionTitle>
          {detail.links.length === 0 ? (
            <p className="text-[10px] italic text-ink/55">No records linked.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {detail.links.map((link) => (
                <span
                  key={`${link.entity_type}-${link.entity_id}`}
                  className="rounded-sm border border-ink/20 bg-cream px-1.5 py-0.5 text-[10px] font-semibold text-ink/75"
                >
                  {typeLabel(link.entity_type)}: {link.label}
                </span>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-sm border border-ink/15 bg-white/40 p-2.5">
          <SectionTitle>Duties at this location</SectionTitle>
          {duties.length === 0 ? (
            <p className="text-[10px] italic text-ink/55">No active duty assigned.</p>
          ) : (
            <div className="space-y-1">
              {duties.map((duty) => (
                <div key={duty.id} className="flex items-center gap-2 rounded-sm border border-ink/15 px-1.5 py-1">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[10px] font-bold text-ink">
                      {duty.label || duty.task_type}
                    </p>
                    <p className="truncate font-mono text-[9px] text-ink/55">
                      {duty.username} · {duty.task_type} · {fmtTime(duty.starts_at)}
                    </p>
                  </div>
                  {isDirector && (
                    <button
                      type="button"
                      disabled={dutyBusy}
                      onClick={() => removeDuty(duty)}
                      className="rounded-sm border border-crimson-dark/40 px-1 py-0.5 text-[9px] font-bold uppercase text-crimson-deep disabled:opacity-40"
                    >
                      remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          {isDirector && (
            <div className="mt-2 space-y-1 border-t border-ink/10 pt-2">
              <div className="flex gap-1">
                <input
                  value={dutyUser}
                  onChange={(event) => setDutyUser(event.target.value)}
                  placeholder="username"
                  className="min-w-0 flex-1 rounded-sm border border-ink/25 bg-white/70 px-1.5 py-1 text-[10px] font-semibold"
                />
                <select
                  value={dutyType}
                  onChange={(event) => setDutyType(event.target.value)}
                  className="rounded-sm border border-ink/25 bg-white/70 px-1 py-1 text-[10px] font-semibold"
                >
                  {TASK_TYPES.map((task) => (
                    <option key={task} value={task}>{task}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-1">
                <input
                  value={dutyLabel}
                  onChange={(event) => setDutyLabel(event.target.value)}
                  placeholder="what should they do here?"
                  className="min-w-0 flex-1 rounded-sm border border-ink/25 bg-white/70 px-1.5 py-1 text-[10px] font-semibold"
                />
                <button
                  type="button"
                  disabled={dutyBusy || !dutyUser.trim()}
                  onClick={addDuty}
                  className="rounded-sm bg-mustard px-2 py-1 text-[9px] font-bold uppercase text-ink disabled:opacity-40"
                >
                  assign
                </button>
              </div>
              {dutyError && <p className="text-[9px] font-semibold text-crimson-deep">{dutyError}</p>}
            </div>
          )}
        </section>
      </div>

      {canManage && (
        <div className="flex gap-1.5 border-t border-ink/15 p-2.5">
          <Btn variant="ghost" className="flex-1 !px-2 !py-1.5 !text-[10px]" onClick={onEdit}>
            edit pin
          </Btn>
          {detail.mapped && !detail.coordinates_verified && (
            <Btn className="flex-1 !px-2 !py-1.5 !text-[10px]" onClick={onVerify}>
              verify pin
            </Btn>
          )}
        </div>
      )}
    </div>
  );
}

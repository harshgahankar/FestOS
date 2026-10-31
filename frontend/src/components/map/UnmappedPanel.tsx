import type { MapUnmapped, MapUnmappedItem } from "../../mapTypes";
import { typeLabel } from "../../mapTypes";
import { Btn, Spinner } from "../ui";

function ItemRow({
  item,
  onOpen,
  onPin,
}: {
  item: MapUnmappedItem;
  onOpen: (locationId: number) => void;
  onPin: (item: MapUnmappedItem) => void;
}) {
  return (
    <div className="flex items-start gap-2 border-b border-ink/10 py-1.5 last:border-0">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[11px] font-bold text-ink">{item.name}</p>
        <p className="truncate text-[9px] text-ink/55">
          {typeLabel(item.location_type)}
          {item.entity_id ? ` · ${item.entity_id}` : ""}
          {item.reason === "coordinates_unverified" ? " · coordinates unverified" : ""}
          {item.reason === "no_coordinates" ? " · no coordinates" : ""}
          {item.reason === "not_mapped" ? " · no pin" : ""}
        </p>
      </div>
      {item.kind === "entity" ? (
        <button
          type="button"
          onClick={() => onPin(item)}
          className="shrink-0 rounded-sm border border-crimson-dark/40 bg-mustard px-1.5 py-0.5 text-[9px] font-bold uppercase text-ink"
        >
          pin
        </button>
      ) : (
        <button
          type="button"
          onClick={() => item.location_id && onOpen(item.location_id)}
          className="shrink-0 rounded-sm border border-teal-dark/40 bg-teal/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-teal-dark"
        >
          open
        </button>
      )}
    </div>
  );
}

export default function UnmappedPanel({
  data,
  loading,
  error,
  onClose,
  onOpenRegistry,
  onPinEntity,
  onRefresh,
}: {
  data: MapUnmapped | null;
  loading: boolean;
  error: string;
  onClose: () => void;
  onOpenRegistry: (locationId: number) => void;
  onPinEntity: (item: MapUnmappedItem) => void;
  onRefresh: () => void;
}) {
  const records = (data?.unmapped ?? []).filter((item) => item.kind === "entity");
  const registry = (data?.unmapped ?? []).filter((item) => item.kind === "registry");
  const unverified = data?.unverified ?? [];

  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-ink/40 p-3">
      <div className="paper custom-scrollbar max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-sm border-2 border-crimson-dark/40 shadow-[0_8px_0_rgba(64,16,18,0.3)]">
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-ink/15 bg-cream px-4 py-3">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-saffron">
              Coverage check
            </p>
            <h3 className="font-display text-xl text-crimson-deep">Unmapped records</h3>
            <p className="mt-0.5 text-[10px] text-ink/60">
              Every operational record should have a verified pin — nothing here is auto-placed.
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

        <div className="space-y-3 p-4">
          {loading && <Spinner label="checking coverage…" />}
          {error && (
            <p className="rounded-sm border border-crimson-dark/40 bg-crimson-dark/10 px-2 py-1.5 text-[11px] font-semibold text-crimson-deep">
              {error}
            </p>
          )}
          {data && (
            <div className="grid grid-cols-3 gap-1.5">
              <div className="rounded-sm border border-ink/15 bg-white/50 px-2 py-1">
                <p className="text-[9px] font-mono uppercase text-ink/50">records</p>
                <p className="font-display text-lg text-crimson-deep">{records.length}</p>
              </div>
              <div className="rounded-sm border border-ink/15 bg-white/50 px-2 py-1">
                <p className="text-[9px] font-mono uppercase text-ink/50">registry</p>
                <p className="font-display text-lg text-crimson-deep">{registry.length}</p>
              </div>
              <div className="rounded-sm border border-ink/15 bg-white/50 px-2 py-1">
                <p className="text-[9px] font-mono uppercase text-ink/50">unverified</p>
                <p className="font-display text-lg text-saffron">{unverified.length}</p>
              </div>
            </div>
          )}

          <section>
            <p className="mb-1 text-[10px] font-mono font-bold uppercase tracking-wide text-crimson-dark/65">
              Records without a pin ({records.length})
            </p>
            {records.length === 0 ? (
              <p className="text-[10px] italic text-ink/55">All visible records are pinned.</p>
            ) : (
              <div>
                {records.map((item) => (
                  <ItemRow
                    key={`${item.entity_type}-${item.entity_id}`}
                    item={item}
                    onOpen={onOpenRegistry}
                    onPin={onPinEntity}
                  />
                ))}
              </div>
            )}
          </section>

          {registry.length > 0 && (
            <section>
              <p className="mb-1 text-[10px] font-mono font-bold uppercase tracking-wide text-crimson-dark/65">
                Registry pins missing coordinates ({registry.length})
              </p>
              <div>
                {registry.map((item) => (
                  <ItemRow
                    key={`registry-${item.location_id}`}
                    item={item}
                    onOpen={onOpenRegistry}
                    onPin={onPinEntity}
                  />
                ))}
              </div>
            </section>
          )}

          {unverified.length > 0 && (
            <section>
              <p className="mb-1 text-[10px] font-mono font-bold uppercase tracking-wide text-crimson-dark/65">
                Pins awaiting on-site verification ({unverified.length})
              </p>
              <div>
                {unverified.map((item) => (
                  <ItemRow
                    key={`unverified-${item.location_id}`}
                    item={item}
                    onOpen={onOpenRegistry}
                    onPin={onPinEntity}
                  />
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="sticky bottom-0 flex justify-end gap-2 border-t border-ink/15 bg-cream px-4 py-3">
          <Btn variant="ghost" onClick={onRefresh}>refresh</Btn>
          <Btn onClick={onClose}>done</Btn>
        </div>
      </div>
    </div>
  );
}

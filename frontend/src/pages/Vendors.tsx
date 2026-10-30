import { useEffect, useState } from "react";
import { api } from "../api";
import type { ApplyResp, Coverage, PreviewResp, Settlement, Vendor, VendorsList } from "../vendorTypes";
import ReasonModal from "../components/ReasonModal";
import { PageHeader } from "../components/Listkit";
import { Badge, Paper, Spinner, Unknown } from "../components/ui";

export default function Vendors() {
  const [list, setList] = useState<VendorsList | null>(null);
  const [cov, setCov] = useState<Coverage | null>(null);
  const [stl, setStl] = useState<Settlement | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<
    | { kind: "rate"; vendor: Vendor }
    | { kind: "interrupt"; vendor: Vendor; preview: PreviewResp }
    | null
  >(null);
  const [modalBusy, setModalBusy] = useState(false);
  const [modalErr, setModalErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const [l, c, s] = await Promise.all([
        api<VendorsList>("/vendors"),
        api<Coverage>("/vendors/coverage"),
        api<Settlement>("/vendors/settlement"),
      ]);
      setList(l);
      setCov(c);
      setStl(s);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function previewInterrupt(v: Vendor) {
    setNotice("");
    setModalErr("");
    try {
      const pv = await api<PreviewResp>(`/vendors/${v.id}/interrupt/preview`, { method: "POST" });
      setModal({ kind: "interrupt", vendor: v, preview: pv });
    } catch (e2) {
      setNotice(`refused: ${e2 instanceof Error ? e2.message : String(e2)}`);
    }
  }

  async function applyInterrupt(v: Vendor, reason: string) {
    setModalBusy(true);
    setModalErr("");
    try {
      const out = await api<ApplyResp>(`/vendors/${v.id}/interrupt/apply`, {
        method: "POST",
        body: { reason },
      });
      setModal(null);
      const un = out.unmet.length ? ` ${out.unmet.length} order(s) could NOT be rerouted — every refusal is listed, none were silently dropped.` : "";
      setNotice(`${v.raw_id} interrupted — ${out.orders_moved} order(s) moved to other vendors.${un}`);
      setModalBusy(false);
      void load();
    } catch (e2) {
      setModalErr(e2 instanceof Error ? e2.message : String(e2));
      setModalBusy(false);
    }
  }

  async function setRate(v: Vendor, rateStr: string, reason: string) {
    if (!/^\d+$/.test(rateStr)) { setModalErr("rate must be a plain number (₹)"); return; }
    setModalBusy(true);
    setModalErr("");
    try {
      const out = await api<{ vendor_id: number; raw_id: string; rate: number }>(
        `/vendors/${v.id}/rate`, { method: "PATCH", body: { rate: Number(rateStr), reason } });
      setModal(null);
      setNotice(`rate for ${out.raw_id} set to ₹${out.rate} — audited; settlement row now closes`);
      setModalBusy(false);
      void load();
    } catch (e2) {
      setModalErr(e2 instanceof Error ? e2.message : String(e2));
      setModalBusy(false);
    }
  }

  const byId = new Map((list?.vendors ?? []).map((v) => [v.id, v]));
  const stlByVendor = new Map((stl?.rows ?? []).map((r) => [r.vendor_id, r]));
  const expSet = new Set(list?.compliance?.expired ?? []);
  const expingSet = new Set(list?.compliance?.expiring ?? []);

  return (
    <div>
      <PageHeader title="Vendor board" />
      {notice && (
        <p className="paper mb-3 rounded-sm border-2 border-teal-dark/40 px-3 py-2 text-sm font-semibold text-teal-dark">
          {notice}
        </p>
      )}
      {err && <p className="mb-3 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-2 text-cream">{err}</p>}
      {busy && <Spinner label="checking the kitchens…" />}

      {list && (
        <Paper title={`Vendors (${list.vendors?.length ?? 0}) — fest window ${list.days?.start ?? "—"} → ${list.days?.end ?? "—"}`}>
          <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
            <table className="w-full text-left">
              <thead className="bg-crimson-dark/10 text-[11px] uppercase tracking-wider text-ink/70">
                <tr>
                  <th className="px-3 py-2.5">Vendor</th>
                  <th className="px-3 py-2.5">Diets</th>
                  <th className="px-3 py-2.5">Cap/meal</th>
                  <th className="px-3 py-2.5">Hours</th>
                  <th className="px-3 py-2.5">Hygiene cert</th>
                  <th className="px-3 py-2.5">Rate</th>
                  <th className="px-3 py-2.5">Terms</th>
                  <th className="px-3 py-2.5">Served</th>
                  <th className="px-3 py-2.5">Due</th>
                  <th className="px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {(list.vendors ?? []).map((v) => {
                  const exp = expSet.has(v.raw_id);
                  const exping = expingSet.has(v.raw_id);
                  const stlRow = stlByVendor.get(v.id);
                  return (
                    <tr key={v.id} className="border-b border-ink/10 align-top hover:bg-mustard/5 transition-colors">
                      {/* Vendor */}
                      <td className="px-3 py-2.5">
                        <div className="text-sm font-bold text-ink leading-tight">{v.name}</div>
                        <div className="font-mono text-xs text-ink/60 mt-0.5">{v.raw_id}</div>
                      </td>

                      {/* Diets */}
                      <td className="px-3 py-2.5">
                        <span className="flex flex-wrap gap-1 max-w-[180px]">
                          {(v.dietary_coverage ?? []).length
                            ? v.dietary_coverage.map((t) => <Badge key={t} sev="neutral">{t}</Badge>)
                            : <Unknown />}
                        </span>
                      </td>

                      {/* Cap/meal */}
                      <td className="px-3 py-2.5 text-xs font-mono">
                        {v.capacity_per_day ?? <Unknown />}
                      </td>

                      {/* Hours */}
                      <td className="px-3 py-2.5 text-xs font-mono">
                        {v.hours ?? <Unknown />}
                      </td>

                      {/* Hygiene cert */}
                      <td className="px-3 py-2.5 text-xs">
                        <div>{v.hygiene_cert_expiry ?? <Unknown />}</div>
                        {exp ? (
                          <div className="mt-1"><Badge sev="error">expired</Badge></div>
                        ) : exping ? (
                          <div className="mt-1"><Badge sev="warning">mid-fest expiry</Badge></div>
                        ) : null}
                      </td>

                      {/* Rate */}
                      <td className="px-3 py-2.5 text-xs">
                        {v.rate === null ? (
                          <button
                            onClick={() => { setModalErr(""); setModal({ kind: "rate", vendor: v }); }}
                            className="rounded-sm border border-teal-dark/50 bg-teal/20 px-1.5 py-0.5 text-[10px] font-bold uppercase text-teal-dark hover:bg-teal/40"
                          >
                            + set rate
                          </button>
                        ) : (
                          <span className="font-semibold text-xs flex items-center gap-1">
                            ₹{v.rate}
                            <button
                              onClick={() => { setModalErr(""); setModal({ kind: "rate", vendor: v }); }}
                              className="text-[10px] text-teal-dark hover:underline ml-0.5"
                              title="Edit rate"
                            >
                              ✏
                            </button>
                          </span>
                        )}
                      </td>

                      {/* Terms */}
                      <td className="px-3 py-2.5 text-xs italic text-ink/75 max-w-[140px]" title={v.payment_terms ?? ""}>
                        {v.payment_terms ?? <Unknown />}
                      </td>

                      {/* Served */}
                      <td className="px-3 py-2.5 text-xs font-mono font-semibold">
                        {stlRow ? stlRow.qty : 0}
                      </td>

                      {/* Due */}
                      <td className="px-3 py-2.5 text-xs font-semibold">
                        {stlRow?.amount !== null && stlRow?.amount !== undefined ? (
                          <span>
                            ₹{stlRow.amount}
                            {stlRow.paid && (
                              <span className="ml-1 text-[10px] text-teal-dark font-bold">(paid)</span>
                            )}
                          </span>
                        ) : (
                          <Unknown />
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <Badge sev={v.status === "interrupted" ? "error" : "good"}>{v.status}</Badge>
                          {v.status !== "interrupted" && (
                            <button
                              onClick={() => void previewInterrupt(v)}
                              className="rounded-sm border border-crimson-dark/50 bg-mustard/40 px-1.5 py-0.5 text-[10px] font-bold uppercase text-crimson-deep hover:bg-mustard/70 transition"
                            >
                              interrupt ⚠
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] italic text-ink/60">
            compliance flags come from certification dates vs the fest window — expired or mid-fest-expiry certs are red flags, never silently hidden
          </p>
        </Paper>
      )}

      {cov && (
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <Paper title="Dietary coverage — participant diet tags vs vendor menus">
            {(() => {
              const dietTags = cov.tags_with_players ?? Object.keys(cov.matrix ?? {});
              return dietTags.length === 0 ? (
                <p className="text-sm italic text-ink/60">no diet tags are carried by any active participant — nothing to cover from the matrix</p>
              ) : (
                <ul className="text-sm">
                  {dietTags.map((t) => (
                    <li key={t} className="mb-1 flex items-center gap-2">
                      <Badge sev="neutral">{t}</Badge>
                      {(cov.matrix?.[t]?.vendors ?? []).length > 0
                        ? <span className="text-xs">covered by {(cov.matrix?.[t]?.vendors ?? []).map((i) => byId.get(i)?.raw_id ?? `#${i}`).join(", ")}</span>
                        : <Badge sev="error">no vendor covers this</Badge>}
                    </li>
                  ))}
                </ul>
              );
            })()}
            {(cov.uncovered_tags ?? []).length > 0 && (
              <div className="mt-2 rounded-sm border-2 border-mustard bg-mustard/20 p-2 text-xs">
                <strong>Engine flags (all participants incl. pending):</strong>{" "}
                {cov.uncovered_tags.join(", ")} — with {cov.matrix?.[cov.uncovered_tags[0]]?.unmet ?? 0} declared
                portion-demand and zero vendor coverage. No kitchen can serve these guests as things stand.
              </div>
            )}
          </Paper>

          <Paper title="Settlement — qty × rate per vendor">
            {stl && (
              <>
                <p className="mb-2 text-xs font-bold uppercase text-ink/70">
                  total estimated (rate-known vendors only): ₹{stl.total_estimated}
                </p>
                <div className="overflow-x-auto rounded-sm border-2 border-crimson-dark/20 bg-white/40">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-crimson-dark/10 uppercase text-[10px] text-ink/70">
                      <tr>
                        <th className="px-2 py-1.5">vendor</th><th className="px-2 py-1.5">orders</th>
                        <th className="px-2 py-1.5">qty</th><th className="px-2 py-1.5">rate</th>
                        <th className="px-2 py-1.5">amount</th><th className="px-2 py-1.5">paid</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stl.rows.map((r) => (
                        <tr key={r.vendor_id} className={`border-b border-ink/10 ${r.needs_manual_entry ? "bg-mustard/20" : ""}`}>
                          <td className="px-2 py-1 font-mono font-bold">{r.raw_id}</td>
                          <td className="px-2 py-1">{r.orders}</td>
                          <td className="px-2 py-1">{r.qty}</td>
                          <td className="px-2 py-1">{r.rate === null ? <Unknown /> : `₹${r.rate}`}</td>
                          <td className="px-2 py-1 font-semibold">{r.amount === null ? <Unknown /> : `₹${r.amount}`}</td>
                          <td className="px-2 py-1">
                            {r.orders === 0 ? <span className="text-ink/40">no orders</span>
                              : r.paid ? <Badge sev="good">fully paid</Badge> : <Badge sev="warning">unpaid</Badge>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {stl.pending_entries.length > 0 && (
                  <div className="mt-2 rounded-sm border-2 border-mustard bg-mustard/20 p-2 text-xs">
                    <strong>A-13 — rate is not in the source pack</strong> for {stl.pending_entries.join(", ")}.
                    Enter each negotiated rate via the rate button (audited) before settlement closes; the engine never guesses.
                  </div>
                )}
              </>
            )}
          </Paper>
        </div>
      )}

      {modal?.kind === "rate" && (
        <ReasonModal
          title={`Record rate for ${modal.vendor.raw_id}`}
          description="Rates are not in the source pack (A-13); entering one makes settlement trustworthy. Every write is audited."
          confirmLabel="save rate"
          busy={modalBusy}
          error={modalErr}
          extra={<RateInput />}
          onCancel={() => { setModal(null); setModalErr(""); }}
          onConfirm={(reason) => {
            const el = document.getElementById("vendor-rate") as HTMLInputElement | null;
            void setRate(modal.vendor, (el?.value ?? "").trim(), reason);
          }}
        />
      )}

      {modal?.kind === "interrupt" && (
        <ReasonModal
          title={`Interrupt ${modal.vendor.raw_id} — food-safety override`}
          description={
            <>
              <p className="mb-2">Preview — <strong>nothing changes until you confirm with a reason</strong>:</p>
              <ul className="max-h-32 list-inside list-disc overflow-y-auto text-xs">
                {modal.preview.moves.map((m) => (
                  <li key={`m${m.order}`}>
                    order #{m.order} ({m.meal}, {m.day}{m.dietary_tag ? `, ${m.dietary_tag}` : ""}) →{" "}
                    <span className="font-bold">{m.to_vendor_raw_id}</span>
                  </li>
                ))}
                {modal.preview.unmet.map((u) => (
                  <li key={`u${u.order}`} className="text-crimson-deep">
                    order #{u.order} ({u.meal}, {u.day}{u.dietary_tag ? `, ${u.dietary_tag}` : ""}) — UNMET: {u.reason}
                  </li>
                ))}
                {modal.preview.moves.length === 0 && modal.preview.unmet.length === 0 && (
                  <li>no open orders to move</li>
                )}
              </ul>
            </>
          }
          confirmLabel="apply interrupt"
          busy={modalBusy}
          error={modalErr}
          onCancel={() => { setModal(null); setModalErr(""); }}
          onConfirm={(reason) => void applyInterrupt(modal.vendor, reason)}
        />
      )}
    </div>
  );
}

function RateInput() {
  return (
    <div className="mb-3">
      <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-ink/70">
        rate per meal (₹)
      </label>
      <input
        id="vendor-rate"
        inputMode="numeric"
        className="w-full rounded-sm border-2 border-teal-dark/40 bg-white/60 px-3 py-2 text-sm text-ink"
      />
    </div>
  );
}

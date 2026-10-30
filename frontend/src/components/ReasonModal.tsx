import { useState } from "react";
import type { ReactNode } from "react";
import { Btn } from "./ui";

/**
 * Every write needs a reason (A-01): this modal enforces a non-empty
 * explanation before the call even leaves the browser.
 */
export default function ReasonModal({
  title, description, confirmLabel = "confirm", busy = false, error = "",
  onCancel, onConfirm, extra,
}: {
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  error?: string;
  extra?: ReactNode;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const [localErr, setLocalErr] = useState(false);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-crimson-dark/70 p-4" onClick={onCancel}>
      <div className="paper torn-b relative w-full max-w-md rounded-sm border-2 border-crimson-dark/50 p-5 pb-7 shadow-[0_10px_0_rgba(64,16,18,0.5)]"
        onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display mb-1 text-xl text-ink">{title}</h3>
        {description && <p className="mb-3 text-sm text-ink/75">{description}</p>}
        {extra}
        {error && (
          <p className="mb-2 rounded-sm border border-saffron bg-crimson-dark/90 px-3 py-1.5 text-sm text-cream">
            refused: {error}
          </p>
        )}
        <label className="mb-1 block text-xs font-bold uppercase tracking-wider text-ink/70">
          Reason (audited, required)
        </label>
        <textarea
          value={reason}
          onChange={(e) => { setReason(e.target.value); setLocalErr(false); }}
          rows={3}
          autoFocus
          className={`w-full rounded-sm border-2 bg-white/60 px-3 py-2 text-sm text-ink ${
            localErr ? "border-saffron" : "border-teal-dark/40"
          }`}
        />
        {localErr && <p className="mb-1 text-xs font-bold text-crimson-deep">a reason is required — nothing changes without one</p>}
        <div className="mt-3 flex justify-end gap-2">
          <Btn variant="ghost" onClick={onCancel} className="!text-ink/80 !border-ink/30">cancel</Btn>
          <Btn
            disabled={busy}
            onClick={() => reason.trim() ? onConfirm(reason.trim()) : setLocalErr(true)}
          >
            {busy ? "saving…" : confirmLabel}
          </Btn>
        </div>
      </div>
    </div>
  );
}

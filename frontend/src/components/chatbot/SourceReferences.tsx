import { useState } from "react";
import type { SourceCitation } from "../../chatbotTypes";

export function SourceReferences({ sources }: { sources: SourceCitation[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 border-t border-crimson-dark/20 pt-2 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-bold uppercase tracking-wider text-ink/60 text-[10px]">
          Verified Sources ({sources.length})
        </span>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="cursor-pointer text-[11px] font-semibold text-teal-dark hover:underline"
        >
          {expanded ? "Hide Details" : "Inspect Sources"}
        </button>
      </div>

      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {sources.map((s, idx) => {
          const isDb = s.type === "database_query";
          const badgeClass = isDb
            ? "border-teal-dark/40 bg-teal/15 text-teal-dark"
            : "border-mustard/60 bg-mustard/20 text-crimson-deep";

          return (
            <span
              key={`${s.label}-${idx}`}
              className={`inline-flex items-center gap-1 rounded-sm border px-2 py-0.5 text-[11px] font-medium ${badgeClass}`}
            >
              <span className="font-bold uppercase text-[9px]">
                {isDb ? "DB" : s.type === "semantic_document" ? "DOC" : "RULE"}:
              </span>
              <span>{s.label}</span>
            </span>
          );
        })}
      </div>

      {expanded && (
        <div className="mt-2 space-y-1.5 rounded-sm bg-cream-dim/60 p-2 font-mono text-[10.5px] text-ink/80">
          {sources.map((s, idx) => (
            <div key={`detail-${idx}`} className="border-b border-ink/10 pb-1 last:border-b-0 last:pb-0">
              <span className="font-bold text-crimson-dark">[{s.module}]</span> {s.label}
              {s.detail && (
                <pre className="mt-0.5 overflow-x-auto whitespace-pre-wrap text-[10px] text-ink/70">
                  {JSON.stringify(s.detail, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

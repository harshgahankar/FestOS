type Props = {
  onSelect: (question: string) => void;
  disabled?: boolean;
  role?: string;
};

export function SuggestedQuestions({ onSelect, disabled = false, role = "viewer" }: Props) {
  const suggestionsByRole: Record<string, string[]> = {
    director: [
      "Summarize current festival operations & KPIs.",
      "How many active participants are registered?",
      "Which scheduling conflicts are unresolved?",
      "Are there any accommodation shortages?",
      "Which inventory items have low stock?",
      "Review vendor food safety compliance.",
      "What are the most important pending operational issues?",
    ],
    accommodation_lead: [
      "How many accommodation places are available?",
      "Are there any accommodation shortages?",
      "Which accommodation allocations need review?",
      "How many active participants are registered?",
    ],
    events_lead: [
      "Which scheduling conflicts are unresolved?",
      "Which events have scheduling issues?",
      "What happens if we move a particular event?",
      "How many events are scheduled vs unscheduled?",
    ],
    logistics_lead: [
      "Which inventory items have low stock?",
      "What merchandise shortfalls are present?",
      "Summarize recent inventory movements.",
      "Which equipment is under repair?",
    ],
    vendor_lead: [
      "Which vendors have compliance issues?",
      "What is the current dietary coverage?",
      "Which vendor settlements need attention?",
      "Are any vendor hygiene certificates expired?",
    ],
    volunteer: [
      "What merchandise shortfalls are present?",
      "How many active participants are registered?",
      "Show scheduled festival events.",
    ],
    viewer: [
      "How many active participants are registered?",
      "How many events are scheduled?",
      "How many venues are available?",
    ],
  };

  const list = suggestionsByRole[role] || suggestionsByRole.viewer;

  return (
    <div className="space-y-1.5 p-3">
      <p className="text-[11px] font-bold uppercase tracking-wider text-ink/60">
        Suggested Operational Questions:
      </p>
      <div className="flex flex-wrap gap-1.5">
        {list.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(q)}
            className="rounded-sm border border-crimson-dark/30 bg-cream px-2 py-1 text-left text-xs font-semibold text-ink/80 transition hover:bg-mustard/40 hover:text-ink active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

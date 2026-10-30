import type { ChatMessage } from "../../chatbotTypes";
import { SourceReferences } from "./SourceReferences";

type Props = {
  msg: ChatMessage;
  onFollowUpClick?: (question: string) => void;
};

export function ChatMessageItem({ msg, onFollowUpClick }: Props) {
  const isUser = msg.sender === "user";

  if (isUser) {
    return (
      <div className="flex justify-end pl-8">
        <div className="rounded-sm border-2 border-crimson-dark/40 bg-mustard px-3.5 py-2 text-sm font-semibold text-ink shadow-[0_2px_0_rgba(64,16,18,0.25)]">
          {msg.content}
        </div>
      </div>
    );
  }

  // Assistant Message
  const getBadgeStyle = (answerType?: string, confidence?: string) => {
    switch (answerType) {
      case "FESTOS DATABASE":
        return "bg-teal/20 text-teal-dark border-teal-dark/50";
      case "DATABASE + AI RECOMMENDATIONS":
        return "bg-mustard/30 text-ink border-mustard/60";
      case "GENERAL EVENT KNOWLEDGE":
        return "bg-amber-100/70 text-ink/90 border-crimson-dark/30";
      case "CLARIFICATION NEEDED":
        return "bg-mustard/20 text-crimson-deep border-mustard/50";
      default:
        return confidence === "high"
          ? "bg-teal/20 text-teal-dark border-teal-dark/40"
          : confidence === "medium"
          ? "bg-mustard/20 text-ink border-mustard/50"
          : "bg-crimson-dark/15 text-crimson-deep border-crimson-dark/30";
    }
  };

  const badgeLabel = msg.answer_type || (msg.confidence ? `${msg.confidence} Grounding` : null);
  const badgeStyle = getBadgeStyle(msg.answer_type, msg.confidence);

  return (
    <div className="flex justify-start pr-6">
      <div className="paper w-full rounded-sm border-2 border-crimson-dark/30 p-3.5 shadow-[0_2px_0_rgba(64,16,18,0.2)]">
        {/* Header with identity & source / answer-type label */}
        <div className="mb-2 flex items-center justify-between border-b border-crimson-dark/15 pb-1.5 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="font-display text-sm tracking-wide text-crimson-deep font-bold">
              FestOS AI
            </span>
            <span className="rounded-sm bg-crimson-dark/10 px-1.5 py-0.2 text-[10px] font-bold uppercase tracking-wider text-crimson-dark">
              Operations Assistant
            </span>
          </div>

          {badgeLabel && !msg.isError && (
            <span
              className={`rounded-sm border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${badgeStyle}`}
              title={`Answer origin: ${badgeLabel}`}
            >
              {badgeLabel}
            </span>
          )}
        </div>

        {/* Message body */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink/90 font-sans">
          {msg.content}
        </div>

        {/* Citations */}
        {msg.sources && msg.sources.length > 0 && (
          <SourceReferences sources={msg.sources} />
        )}

        {/* Follow-up Question Chips */}
        {msg.follow_ups && msg.follow_ups.length > 0 && onFollowUpClick && (
          <div className="mt-3 border-t border-crimson-dark/15 pt-2">
            <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-ink/60">
              Suggested Follow-ups:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {msg.follow_ups.map((f, i) => (
                <button
                  key={`${f}-${i}`}
                  type="button"
                  onClick={() => onFollowUpClick(f)}
                  className="rounded-sm border border-teal-dark/30 bg-teal/10 px-2 py-0.5 text-left text-xs font-medium text-teal-dark transition hover:bg-teal/25 hover:text-ink active:translate-y-px"
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

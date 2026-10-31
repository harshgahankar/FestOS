import type { ChatMessage } from "../../chatbotTypes";
import { SourceReferences } from "./SourceReferences";
import { MarkdownContent } from "./MarkdownContent";

type Props = {
  msg: ChatMessage;
};

export function ChatMessageItem({ msg }: Props) {
  const isUser = msg.sender === "user";

  if (isUser) {
    return (
      <div className="flex justify-end pl-10 animate-in fade-in slide-in-from-bottom-1">
        <div className="rounded-2xl rounded-tr-xs border border-crimson-dark/20 bg-mustard/35 px-4 py-2.5 text-[13px] font-semibold text-ink shadow-2xs max-w-[85%] leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }

  // Assistant Message
  const getBadgeStyle = (answerType?: string, confidence?: string) => {
    switch (answerType) {
      case "FESTOS DATABASE":
        return "bg-teal/15 text-teal-dark border-teal-dark/30";
      case "DATABASE + AI RECOMMENDATIONS":
        return "bg-mustard/25 text-crimson-deep border-mustard/50";
      case "GENERAL EVENT KNOWLEDGE":
        return "bg-amber-50 text-ink/80 border-crimson-dark/20";
      case "CLARIFICATION NEEDED":
        return "bg-mustard/20 text-crimson-deep border-mustard/40";
      default:
        return confidence === "high"
          ? "bg-teal/15 text-teal-dark border-teal-dark/30"
          : confidence === "medium"
          ? "bg-mustard/20 text-ink border-mustard/40"
          : "bg-crimson-dark/10 text-crimson-deep border-crimson-dark/20";
    }
  };

  const badgeLabel = msg.answer_type || (msg.confidence ? `${msg.confidence} Grounding` : null);
  const badgeStyle = getBadgeStyle(msg.answer_type, msg.confidence);

  return (
    <div className="flex justify-start pr-4 animate-in fade-in slide-in-from-bottom-1">
      <div className="w-full rounded-xl border border-crimson-dark/15 bg-white/80 p-4 shadow-xs">
        {/* Header with AI emblem, identity & source badge */}
        <div className="mb-2.5 flex items-center justify-between border-b border-crimson-dark/10 pb-2 text-xs">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-crimson-dark text-mustard shadow-2xs">
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6L12 2Z" />
              </svg>
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-display text-xs font-bold tracking-wide text-crimson-deep">
                FestOS AI
              </span>
              <span className="text-[10px] font-mono text-ink/50 uppercase tracking-wider">
                Operations
              </span>
            </div>
          </div>

          {badgeLabel && !msg.isError && (
            <span
              className={`rounded border px-2 py-0.5 text-[9.5px] font-mono font-bold uppercase tracking-wider ${badgeStyle}`}
              title={`Answer origin: ${badgeLabel}`}
            >
              {badgeLabel}
            </span>
          )}
        </div>

        {/* Message body with Markdown formatting */}
        <div className="text-ink/90 font-sans">
          {msg.isError ? (
            <p className="text-xs font-semibold text-destructive-red">{msg.content}</p>
          ) : (
            <MarkdownContent content={msg.content} />
          )}
        </div>

        {/* Citations / Sources */}
        {msg.sources && msg.sources.length > 0 && (
          <SourceReferences sources={msg.sources} />
        )}
      </div>
    </div>
  );
}

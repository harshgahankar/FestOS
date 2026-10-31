import { useState, useEffect, useRef } from "react";
import type { ChatMessage, ChatbotHealth, ConversationSummary } from "../../chatbotTypes";
import {
  fetchChatbotHealth,
  sendChatMessage,
  fetchConversations,
  fetchConversation,
  triggerReindex,
} from "../../chatbotApi";
import { ChatMessageItem } from "./ChatMessageItem";
import { ChatInput } from "./ChatInput";
import { ChatLoading } from "./ChatLoading";
import { speak, stopSpeaking, ttsSupported } from "./voice";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  userRole?: string;
};

const PROMPT_STARTERS: Record<string, string[]> = {
  director: [
    "Summarize current festival operations and key metrics.",
    "Which scheduling conflicts or venue overlaps exist?",
    "Check food vendor hygiene certifications and expirations.",
    "Are there any accommodation or inventory shortages?",
  ],
  accommodation_lead: [
    "How many accommodation places are available?",
    "Are there any hostel room shortages or capacity issues?",
    "Show pending room allocations needing review.",
  ],
  events_lead: [
    "Which scheduling conflicts or judge overlaps are unresolved?",
    "Show events scheduled in the main auditorium.",
    "What events have equipment requirements not yet met?",
  ],
  logistics_lead: [
    "Which inventory items have low stock or need reordering?",
    "Show current merchandise shortfall and issued counts.",
    "Summarize recent sound equipment movements.",
  ],
  vendor_lead: [
    "Which food vendors have expired or mid-fest certs?",
    "What is the current dietary coverage across all vendors?",
    "Show vendor settlements and pending payment terms.",
  ],
  volunteer: [
    "Show scheduled festival events for today.",
    "What merchandise packages are ready for distribution?",
  ],
  viewer: [
    "How many active participants are registered?",
    "Show scheduled festival events and venues.",
  ],
};

export function ChatbotPanel({ isOpen, onClose, userRole = "viewer" }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<ChatbotHealth | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexSuccess, setReindexSuccess] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load health on mount
  useEffect(() => {
    fetchChatbotHealth()
      .then(setHealth)
      .catch(() => {
        setHealth({
          status: "offline",
          ai_enabled: false,
          provider: "deterministic",
          model: "built-in",
          embedding_provider: "local",
          vector_store_chunks: 0,
          deterministic_fallback_available: true,
        });
      });
  }, []);

  // Load conversation list when history is toggled
  useEffect(() => {
    if (showHistory) {
      fetchConversations()
        .then(setConversations)
        .catch(() => setConversations([]));
    }
  }, [showHistory]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Stop speech when the panel closes or unmounts
  useEffect(() => {
    if (!isOpen) stopSpeaking();
    return () => stopSpeaking();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSend = async (text: string) => {
    setErrorMsg(null);
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChatMessage(text, conversationId);
      setConversationId(res.conversation_id);
      const asstMsg: ChatMessage = {
        id: `a-${Date.now()}`,
        sender: "assistant",
        content: res.answer,
        sources: res.sources,
        confidence: res.confidence,
        answer_type: res.answer_type,
        follow_ups: res.follow_up_questions,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, asstMsg]);
      if (voiceOn) speak(res.answer);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Failed to communicate with FestOS AI.";
      setErrorMsg(detail);
      const errItem: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        content: `Error: ${detail}`,
        confidence: "low",
        isError: true,
      };
      setMessages((prev) => [...prev, errItem]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId(null);
    setErrorMsg(null);
    setShowHistory(false);
    stopSpeaking();
  };

  const handleLoadConversation = async (convId: string) => {
    setLoading(true);
    setShowHistory(false);
    setErrorMsg(null);
    try {
      const detail = await fetchConversation(convId);
      setConversationId(detail.conversation_id);
      const mapped: ChatMessage[] = detail.messages.map((m) => ({
        id: String(m.id),
        sender: m.sender === "assistant" ? "assistant" : "user",
        content: m.content,
        sources: m.sources,
        confidence: m.confidence,
        answer_type: m.answer_type,
        follow_ups: m.follow_ups,
        timestamp: m.created_at || undefined,
      }));
      setMessages(mapped);
    } catch {
      setErrorMsg("Could not load that conversation history.");
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    setReindexSuccess(null);
    try {
      const res = await triggerReindex();
      setReindexSuccess(res.message);
      fetchChatbotHealth().then(setHealth).catch(() => {});
    } catch {
      setErrorMsg("Failed to reindex semantic documents.");
    } finally {
      setReindexing(false);
    }
  };

  const starters = PROMPT_STARTERS[userRole] || PROMPT_STARTERS.viewer;

  return (
    <aside
      aria-label="FestOS AI Operations Assistant"
      className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l-2 border-crimson-dark/30 bg-cream shadow-2xl sm:w-[480px]"
    >
      {/* Refined Executive Panel Header */}
      <div className="border-b border-crimson-dark/20 bg-crimson-dark px-3 py-2.5 text-cream">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-cream/10 border border-cream/20 text-mustard shadow-xs">
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6L12 2Z" />
              </svg>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="font-display text-sm font-bold tracking-wide text-cream truncate">
                  FestOS Assistant
                </h2>
                <span className="flex shrink-0 items-center gap-1 rounded-full bg-crimson-deep/80 px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider text-cream/90 border border-cream/15">
                  <span className={`h-1.5 w-1.5 rounded-full ${health?.status === "ok" ? "bg-teal animate-pulse" : "bg-mustard"}`} />
                  {health?.ai_enabled ? "Active" : "Deterministic"}
                </span>
              </div>
              <p className="text-[10px] text-cream/65 truncate">Event Operations Intelligence</p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => setShowHistory(!showHistory)}
              title="View past chats"
              className="flex items-center gap-1 rounded-md border border-cream/20 bg-crimson-deep/60 px-1.5 py-1 text-xs font-semibold text-cream/90 hover:bg-crimson-deep hover:text-cream transition"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span className="hidden sm:inline">{showHistory ? "Chat" : "History"}</span>
            </button>
            {ttsSupported && (
              <button
                type="button"
                onClick={() => {
                  const next = !voiceOn;
                  setVoiceOn(next);
                  if (!next) stopSpeaking();
                }}
                title={voiceOn ? "Voice replies on — click to mute" : "Voice replies muted — click to speak"}
                aria-label={voiceOn ? "Mute assistant voice" : "Speak assistant replies"}
                className={`flex items-center rounded-md border px-2 py-1 text-xs font-bold transition ${
                  voiceOn
                    ? "border-teal/60 bg-teal/30 text-cream hover:bg-teal/50"
                    : "border-cream/20 bg-crimson-deep/60 text-cream/60 hover:bg-crimson-deep hover:text-cream"
                }`}
              >
                {voiceOn ? (
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 5 6 9H2v6h4l5 4z" />
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                  </svg>
                ) : (
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 5 6 9H2v6h4l5 4z" />
                    <line x1="23" y1="9" x2="17" y2="15" />
                    <line x1="17" y1="9" x2="23" y2="15" />
                  </svg>
                )}
              </button>
            )}
            <button
              type="button"
              onClick={handleNewChat}
              title="Start new conversation"
              className="flex items-center gap-0.5 rounded-md border border-mustard/50 bg-mustard/90 px-1.5 py-1 text-xs font-bold text-ink hover:bg-mustard hover:shadow-xs transition"
            >
              <span>+</span>
              <span className="hidden sm:inline">New</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Close panel"
              aria-label="Close FestOS AI panel"
              className="rounded-md p-1.5 text-cream/70 hover:bg-crimson-deep hover:text-cream transition"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Vector Index status bar for Director */}
      {userRole === "director" && (
        <div className="flex items-center justify-between border-b border-crimson-dark/15 bg-cream-dim/60 px-3.5 py-1 text-[11px] text-ink/75 font-mono">
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-teal" />
            <span>Index: {health?.vector_store_chunks ?? 0} operational chunks</span>
          </span>
          <button
            type="button"
            disabled={reindexing}
            onClick={handleReindex}
            className="cursor-pointer text-[10.5px] font-bold uppercase text-crimson-deep hover:underline disabled:opacity-50"
          >
            {reindexing ? "Indexing…" : "Refresh"}
          </button>
        </div>
      )}

      {reindexSuccess && (
        <div className="bg-teal/20 px-3 py-1.5 text-xs font-semibold text-teal-dark border-b border-teal/40">
          {reindexSuccess}
        </div>
      )}

      {/* Conversation History Drawer */}
      {showHistory ? (
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-2 bg-cream-dim/40">
          <h3 className="font-display text-xs font-bold uppercase tracking-wider text-ink/70">Past Operations Chats</h3>
          {conversations.length === 0 ? (
            <p className="text-xs italic text-ink/60">No previous conversations recorded.</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.conversation_id}
                type="button"
                onClick={() => handleLoadConversation(c.conversation_id)}
                className={`w-full rounded-lg border p-3 text-left text-xs transition hover:bg-mustard/20 ${
                  c.conversation_id === conversationId
                    ? "border-crimson-dark/40 bg-mustard/30 font-bold shadow-2xs"
                    : "border-crimson-dark/15 bg-white/70"
                }`}
              >
                <div className="truncate text-ink font-semibold">{c.title || "Untitled Conversation"}</div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-ink/50 font-mono">
                  <span>{c.message_count} messages</span>
                  <span>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : ""}</span>
                </div>
              </button>
            ))
          )}
        </div>
      ) : (
        /* Active Chat Message Area */
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3.5">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center min-h-[360px] text-center px-2 py-6">
              {/* Modern Minimalist Welcome Emblem */}
              <div className="mb-3.5 flex h-12 w-12 items-center justify-center rounded-2xl bg-crimson-dark text-mustard shadow-md border border-crimson-dark/30">
                <svg className="h-6 w-6" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6L12 2Z" />
                </svg>
              </div>

              <h3 className="font-display text-lg font-bold text-crimson-deep tracking-tight">
                FestOS Event Intelligence
              </h3>
              <p className="mt-1 text-xs text-ink/70 max-w-[340px] leading-relaxed">
                Direct natural language query engine for participant data, venue schedules,
                inventory levels, and vendor compliance.
              </p>

              <div className="mt-2.5 inline-flex items-center gap-1.5 rounded-full border border-teal-dark/30 bg-teal/10 px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider text-teal-dark">
                <span>Scope:</span>
                <span>{userRole}</span>
              </div>

              {/* Minimal modern prompt starters without the old title */}
              <div className="mt-6 w-full space-y-2">
                {starters.map((q) => (
                  <button
                    key={q}
                    type="button"
                    disabled={loading}
                    onClick={() => handleSend(q)}
                    className="group flex w-full items-center justify-between rounded-lg border border-crimson-dark/15 bg-white/70 p-2.5 text-left text-xs font-medium text-ink/80 shadow-2xs transition hover:border-crimson-dark/30 hover:bg-white hover:text-ink active:translate-y-px"
                  >
                    <span>{q}</span>
                    <span className="text-ink/30 transition-transform group-hover:translate-x-0.5 group-hover:text-crimson-deep">
                      →
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m) => (
                <ChatMessageItem
                  key={m.id}
                  msg={m}
                />
              ))}

              {loading && <ChatLoading />}
              <div ref={messagesEndRef} />
            </>
          )}

          {errorMsg && (
            <div className="rounded-lg border border-crimson-dark/30 bg-crimson-dark/10 p-2.5 text-xs text-destructive-red font-semibold animate-in fade-in">
              {errorMsg}
            </div>
          )}
        </div>
      )}

      {/* Modern AI Chat Input */}
      <ChatInput
        disabled={loading}
        onSend={(t) => handleSend(t)}
        placeholder="ask anything"
      />
    </aside>
  );
}

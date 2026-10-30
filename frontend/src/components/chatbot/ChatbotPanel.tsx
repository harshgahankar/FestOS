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
import { SuggestedQuestions } from "./SuggestedQuestions";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  userRole?: string;
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

  return (
    <aside
      aria-label="FestOS AI Operations Assistant"
      className="fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l-2 border-crimson-dark bg-cream shadow-2xl sm:w-[480px]"
    >
      {/* Panel Header */}
      <div className="border-b-2 border-crimson-dark/40 bg-crimson-dark px-4 py-3 text-cream">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="flex items-baseline gap-0.5 font-display text-xl font-bold tracking-tight text-cream">
              <span>FEST</span>
              <span className="text-saffron">·</span>
              <span className="text-mustard">OS</span>
              <span className="ml-1 rounded bg-mustard/20 px-1 py-0.5 text-[10px] font-mono font-bold uppercase tracking-wider text-mustard border border-mustard/30">
                AI
              </span>
            </h2>
            <span className="flex items-center gap-1 rounded-sm bg-crimson-deep px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-cream/90">
              <span className={`inline-block h-1.5 w-1.5 rounded-full ${health?.status === "ok" ? "bg-teal" : "bg-mustard"}`} />
              {health?.ai_enabled ? "Online" : "Deterministic"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowHistory(!showHistory)}
              title="View past chats"
              className="rounded-sm border border-cream/30 bg-crimson-deep/60 px-2 py-1 text-xs font-semibold text-cream hover:bg-crimson-deep"
            >
              {showHistory ? "Chat" : "History"}
            </button>
            <button
              type="button"
              onClick={handleNewChat}
              title="Start new conversation"
              className="rounded-sm border border-mustard/60 bg-mustard px-2 py-1 text-xs font-bold text-ink hover:bg-saffron"
            >
              + New
            </button>
            <button
              type="button"
              onClick={onClose}
              title="Close panel"
              aria-label="Close FestOS AI panel"
              className="rounded-sm p-1 text-cream/70 hover:bg-crimson-deep hover:text-cream"
            >
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
        <p className="mt-0.5 text-xs text-cream/70">Ask your festival operations data.</p>
      </div>

      {/* Reindex Banner for Director */}
      {userRole === "director" && (
        <div className="flex items-center justify-between border-b border-crimson-dark/20 bg-cream-dim px-3 py-1.5 text-xs text-ink/80">
          <span>Vector Index: {health?.vector_store_chunks ?? 0} operational chunks</span>
          <button
            type="button"
            disabled={reindexing}
            onClick={handleReindex}
            className="cursor-pointer text-[11px] font-bold uppercase text-crimson-deep hover:underline disabled:opacity-50"
          >
            {reindexing ? "Indexing…" : "Refresh Index"}
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
        <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-cream-dim/50">
          <h3 className="font-display text-sm font-bold text-ink">Past Operations Chats</h3>
          {conversations.length === 0 ? (
            <p className="text-xs italic text-ink/60">No previous conversations recorded.</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.conversation_id}
                type="button"
                onClick={() => handleLoadConversation(c.conversation_id)}
                className={`w-full rounded-sm border p-2.5 text-left text-xs transition hover:bg-mustard/30 ${
                  c.conversation_id === conversationId
                    ? "border-crimson-dark bg-mustard/40 font-bold"
                    : "border-crimson-dark/20 bg-cream"
                }`}
              >
                <div className="truncate text-ink font-semibold">{c.title || "Untitled Conversation"}</div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-ink/60">
                  <span>{c.message_count} messages</span>
                  <span>{c.updated_at ? new Date(c.updated_at).toLocaleDateString() : ""}</span>
                </div>
              </button>
            ))
          )}
        </div>
      ) : (
        /* Active Chat Message Area */
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 ? (
            <div className="space-y-4 pt-2">
              <div className="paper rounded-sm border-2 border-crimson-dark/25 p-4 text-center">
                <p className="font-display text-base font-bold text-crimson-deep">
                  Welcome to FestOS AI
                </p>
                <p className="mt-1 text-xs text-ink/75 leading-relaxed">
                  Direct natural language querying over verified festival attendance,
                  accommodation plans, inventory shortages, and vendor compliance.
                </p>
                <div className="mt-2 text-[11px] font-semibold text-teal-dark">
                  Role: <span className="uppercase">{userRole}</span> (Authorized data scope applied)
                </div>
              </div>

              <SuggestedQuestions
                role={userRole}
                disabled={loading}
                onSelect={(q) => handleSend(q)}
              />
            </div>
          ) : (
            <>
              {messages.map((m) => (
                <ChatMessageItem
                  key={m.id}
                  msg={m}
                  onFollowUpClick={(q) => handleSend(q)}
                />
              ))}

              {loading && <ChatLoading />}
              <div ref={messagesEndRef} />
            </>
          )}

          {errorMsg && (
            <div className="rounded-sm border border-crimson-dark/40 bg-crimson-dark/10 p-2 text-xs text-destructive-red font-semibold">
              {errorMsg}
            </div>
          )}
        </div>
      )}

      {/* Input Box */}
      <ChatInput
        disabled={loading}
        onSend={(t) => handleSend(t)}
        placeholder={
          userRole === "director"
            ? "Ask about participants, conflicts, shortages, or vendor compliance…"
            : `Ask a question within ${userRole} scope…`
        }
      />
    </aside>
  );
}

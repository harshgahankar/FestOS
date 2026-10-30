export type SourceCitation = {
  type: string;
  label: string;
  module: string;
  detail?: Record<string, unknown> | null;
};

export type ChatMessage = {
  id: string;
  sender: "user" | "assistant";
  content: string;
  sources?: SourceCitation[];
  confidence?: "high" | "medium" | "low";
  answer_type?: string;
  follow_ups?: string[];
  timestamp?: string;
  isError?: boolean;
};

export type ChatbotHealth = {
  status: string;
  ai_enabled: boolean;
  provider: string;
  model: string;
  embedding_provider: string;
  vector_store_chunks: number;
  deterministic_fallback_available: boolean;
};

export type ChatResponse = {
  answer: string;
  conversation_id: string;
  sources: SourceCitation[];
  confidence: "high" | "medium" | "low";
  answer_type?: string;
  follow_up_questions: string[];
};

export type ConversationSummary = {
  conversation_id: string;
  title: string;
  message_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type ConversationDetail = {
  conversation_id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
  messages: Array<{
    id: number;
    sender: string;
    content: string;
    sources: SourceCitation[];
    confidence: "high" | "medium" | "low";
    answer_type?: string;
    follow_ups: string[];
    created_at: string | null;
  }>;
};

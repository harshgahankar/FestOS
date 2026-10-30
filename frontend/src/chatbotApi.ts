import { api } from "./api";
import type { ChatbotHealth, ChatResponse, ConversationDetail, ConversationSummary } from "./chatbotTypes";

export async function fetchChatbotHealth(): Promise<ChatbotHealth> {
  return api<ChatbotHealth>("/chatbot/health");
}

export async function sendChatMessage(
  message: string,
  conversationId?: string | null
): Promise<ChatResponse> {
  return api<ChatResponse>("/chatbot/chat", {
    method: "POST",
    body: {
      message,
      conversation_id: conversationId || undefined,
    },
  });
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  return api<ConversationSummary[]>("/chatbot/conversations");
}

export async function fetchConversation(conversationId: string): Promise<ConversationDetail> {
  return api<ConversationDetail>(`/chatbot/conversations/${conversationId}`);
}

export async function triggerReindex(): Promise<{
  run_ok: boolean;
  indexed_chunks: number;
  modules: string[];
  message: string;
}> {
  return api("/chatbot/reindex", {
    method: "POST",
  });
}

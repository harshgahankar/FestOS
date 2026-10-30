from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChatMessageIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Natural language question")
    conversation_id: Optional[str] = Field(None, description="Existing conversation ID to continue")


class SourceCitation(BaseModel):
    type: str = Field(..., description="database_query, semantic_document, system_rule, or notice")
    label: str = Field(..., description="Human-readable citation label")
    module: str = Field(..., description="Functional module (participants, accommodation, etc.)")
    detail: Optional[dict[str, Any]] = Field(default=None, description="Verified facts or metadata")


class ChatbotResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: list[SourceCitation] = Field(default_factory=list)
    confidence: str = Field("high", description="high, medium, or low")
    answer_type: str = Field("FESTOS DATABASE", description="FESTOS DATABASE, DATABASE + AI RECOMMENDATIONS, GENERAL EVENT KNOWLEDGE, or CLARIFICATION NEEDED")
    follow_up_questions: list[str] = Field(default_factory=list)


class ChatbotHealth(BaseModel):
    status: str
    ai_enabled: bool
    provider: str
    model: str
    embedding_provider: str
    vector_store_chunks: int
    deterministic_fallback_available: bool


class ConversationMessageOut(BaseModel):
    id: int
    sender: str
    content: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: Optional[str] = "high"
    answer_type: Optional[str] = "FESTOS DATABASE"
    follow_ups: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class ConversationOut(BaseModel):
    conversation_id: str
    title: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    messages: list[ConversationMessageOut] = Field(default_factory=list)


class ConversationSummaryOut(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReindexReportOut(BaseModel):
    run_ok: bool
    indexed_chunks: int
    modules: list[str]
    message: str

"""Chatbot API router for FestOS AI Operations Assistant."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import config as C
from app.auth import get_current_user, require_role
from app.db import get_db
from app.models import ChatConversation, ChatMessageRecord, User
from app.ai.schemas import (
    ChatbotHealth,
    ChatbotResponse,
    ChatMessageIn,
    ConversationOut,
    ConversationMessageOut,
    ConversationSummaryOut,
    ReindexReportOut,
)
from app.ai.orchestrator import ChatOrchestrator
from app.ai.vector_store import build_semantic_index, get_vector_store
from app.ai.llm_provider import get_llm_provider

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.get("/health", response_model=ChatbotHealth)
def health():
    """Returns chatbot operational status and capabilities without exposing secret credentials."""
    v_store = get_vector_store()
    provider = get_llm_provider()
    return ChatbotHealth(
        status="ok",
        ai_enabled=C.FESTOS_AI_ENABLED,
        provider=C.FESTOS_LLM_PROVIDER,
        model=C.FESTOS_LLM_MODEL,
        embedding_provider=C.FESTOS_EMBEDDING_PROVIDER,
        vector_store_chunks=v_store.count(),
        deterministic_fallback_available=True,
    )


@router.post("/chat", response_model=ChatbotResponse)
def chat(
    body: ChatMessageIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Processes natural language questions grounded in authoritative database facts."""
    if not body.message or not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    return ChatOrchestrator.handle_message(
        db=db,
        message=body.message,
        conversation_id=body.conversation_id,
        user=user,
    )


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List only conversations authorized to the currently authenticated user."""
    convs = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == user.username)
        .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())
        .limit(30)
        .all()
    )

    out = []
    for c in convs:
        count = (
            db.query(ChatMessageRecord)
            .filter(ChatMessageRecord.conversation_id == c.conversation_id)
            .count()
        )
        out.append(
            ConversationSummaryOut(
                conversation_id=c.conversation_id,
                title=c.title or "Conversation",
                message_count=count,
                created_at=c.created_at.isoformat() if c.created_at else None,
                updated_at=c.updated_at.isoformat() if c.updated_at else None,
            )
        )
    return out


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves conversation history with strict owner authorization."""
    conv = (
        db.query(ChatConversation)
        .filter(ChatConversation.conversation_id == conversation_id)
        .first()
    )
    if not conv or conv.user_id != user.username:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied."
        )

    messages = (
        db.query(ChatMessageRecord)
        .filter(ChatMessageRecord.conversation_id == conversation_id)
        .order_by(ChatMessageRecord.id.asc())
        .all()
    )

    msg_outs = [
        ConversationMessageOut(
            id=m.id,
            sender=m.sender,
            content=m.content,
            sources=m.sources or [],
            confidence=m.confidence or "high",
            answer_type=getattr(m, "answer_type", None) or "FESTOS DATABASE",
            follow_ups=m.follow_ups or [],
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in messages
    ]

    return ConversationOut(
        conversation_id=conv.conversation_id,
        title=conv.title or "Conversation",
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        messages=msg_outs,
    )


@router.post("/reindex", response_model=ReindexReportOut)
def reindex(
    user=Depends(require_role("director")),
):
    """Refresh the semantic vector index from operational documentation (director only)."""
    result = build_semantic_index()
    return ReindexReportOut(**result)

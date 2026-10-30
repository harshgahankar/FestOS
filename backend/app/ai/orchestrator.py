"""Main orchestration service combining intent routing, database queries, and RAG.

Implements the four-category event-aware hybrid AI chatbot pipeline:
- Category A: FestOS Data Questions (authoritative DB facts, event start times, missing fact clarification)
- Category B: General Event-Management Questions (expertise, checklists, overcrowding, volunteers)
- Category C: Hybrid Questions (verified operational situation + actionable recommendations)
- Category D: Unrelated / Inappropriate Questions (polite redirection or secure refusal)
"""
import uuid
from typing import Any, Optional
from sqlalchemy.orm import Session

from app import config as C
from app.models import ChatConversation, ChatMessageRecord
from app.ai.schemas import ChatbotResponse, SourceCitation
from app.ai.intent_router import IntentRouter
from app.ai.sql_retrieval import SQLRetrievalService
from app.ai.vector_store import get_vector_store
from app.ai.llm_provider import get_llm_provider
from app.ai.prompts import format_grounded_prompt
from app.ai.answer_validator import AnswerValidator
from app.ai.event_knowledge import get_general_event_advice


def _format_history_for_prompt(records: list[ChatMessageRecord]) -> list[dict[str, str]]:
    history = []
    for r in records[-6:]:
        history.append({
            "role": "assistant" if r.sender == "assistant" else "user",
            "content": r.content
        })
    return history


class ChatOrchestrator:
    """End-to-end pipeline for the FestOS Event-Aware Operations Assistant."""

    @staticmethod
    def handle_message(
        db: Session,
        message: str,
        conversation_id: Optional[str],
        user: Any
    ) -> ChatbotResponse:
        user_role = getattr(user, "role", "viewer")
        user_name = getattr(user, "username", "anonymous")

        # 1. Resolve or create conversation with strict ownership checks
        conv = None
        if conversation_id:
            conv = db.query(ChatConversation).filter(ChatConversation.conversation_id == conversation_id).first()
            if conv and conv.user_id != user_name:
                conv = None
                conversation_id = None

        if not conv:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
            title = message.strip()[:40] + ("…" if len(message.strip()) > 40 else "")
            conv = ChatConversation(
                conversation_id=conversation_id,
                user_id=user_name,
                title=title
            )
            db.add(conv)
            db.flush()

        # 2. Retrieve conversation history
        history_records = (
            db.query(ChatMessageRecord)
            .filter(ChatMessageRecord.conversation_id == conversation_id)
            .order_by(ChatMessageRecord.id.asc())
            .all()
        )
        history_dicts = [
            {"sender": r.sender, "content": r.content, "sources": r.sources or []}
            for r in history_records
        ]

        # 3. Classify intent into the 4 categories
        intent = IntentRouter.classify(message, history=history_dicts)
        category = intent.get("category", "festos_data")
        domain = intent.get("domain", "general")
        query_type = intent.get("query_type", "general_inquiry")
        retrieval_mode = intent.get("retrieval_mode", "structured")

        # =========================================================================
        # FAST PATH: UNSAFE & OUT-OF-SCOPE QUESTIONS
        # =========================================================================
        if category in ("unsafe_request", "out_of_scope"):
            validated = AnswerValidator.validate_and_ground(
                raw_answer="",
                structured_result={},
                semantic_chunks=[],
                user_role=user_role,
                category=category
            )
            follow_ups = IntentRouter.get_suggested_follow_ups(domain, query_type)
            return ChatOrchestrator._persist_and_return(
                db=db,
                conversation_id=conversation_id,
                user_message=message,
                validated=validated,
                follow_ups=follow_ups
            )

        # =========================================================================
        # PATH: GENERAL EVENT-MANAGEMENT QUESTIONS (Category B)
        # =========================================================================
        if category == "general_event":
            provider = get_llm_provider()
            advice = ""

            if provider.is_configured() and not getattr(provider, "is_deterministic", False):
                history_prompts = _format_history_for_prompt(history_records)
                messages = format_grounded_prompt(
                    user_query=message,
                    user_role=user_role,
                    structured_evidence="",
                    semantic_evidence="",
                    conversation_history=history_prompts,
                    category="general_event"
                )
                try:
                    llm_out = provider.generate_chat_response(messages)
                    advice = llm_out.get("content", "")
                except Exception:
                    # Provider timeout or failure -> safe deterministic event knowledge fallback
                    advice = get_general_event_advice(message, history_dicts)
            else:
                advice = get_general_event_advice(message, history_dicts)

            validated = AnswerValidator.validate_and_ground(
                raw_answer=advice,
                structured_result={},
                semantic_chunks=[],
                user_role=user_role,
                category="general_event",
                default_summary=advice
            )
            follow_ups = IntentRouter.get_suggested_follow_ups("general_event", query_type)
            return ChatOrchestrator._persist_and_return(
                db=db,
                conversation_id=conversation_id,
                user_message=message,
                validated=validated,
                follow_ups=follow_ups
            )

        # =========================================================================
        # PATH: HYBRID QUESTIONS (Category C)
        # =========================================================================
        if category == "hybrid_event":
            structured_result: dict[str, Any] = {}
            default_facts = ""
            recommendation_body = ""
            assumptions_body = ""

            if query_type == "hybrid_schedule_conflicts":
                structured_result = SQLRetrievalService.get_scheduling_conflicts(db, user_role)
                default_facts = structured_result.get("summary_text", "")
                recommendation_body = (
                    "Based on these verified conflicts, consider the following actions:\n"
                    "1. Stagger Start Times: Add minimum 30-minute buffers between consecutive stage performances to satisfy Assumption A-11.\n"
                    "2. Reallocate Venues: Move solo or parallel sessions to secondary seminar halls (e.g. V03 or V04) to prevent double-booking the Main Auditorium.\n"
                    "3. Adjust Volunteer Shifts: Update staff assignments so no core team coordinator overlaps between simultaneous stages (Assumption A-16)."
                )
                assumptions_body = (
                    "- Venue availability windows remain fixed per the published timetable.\n"
                    "- Campus sound curfews require evening headliner performances to conclude before 10:00 PM."
                )

            elif query_type == "hybrid_venue_scheduling":
                structured_result = SQLRetrievalService.get_events_summary(db, user_role)
                default_facts = structured_result.get("summary_text", "")
                recommendation_body = (
                    "To improve scheduling when multiple events share a venue:\n"
                    "1. Implement Turnaround Buffers: Schedule at least 30–45 minutes between events for stage reset and audience transit.\n"
                    "2. Relocate Preliminary Rounds: Move prelim heats to outdoor amphitheaters or departmental seminar rooms.\n"
                    "3. Publish Run-of-Show: Distribute precise minute-by-minute cue sheets to stage managers to prevent runtime overruns."
                )
                assumptions_body = (
                    "- Target venue has adequate technical AV coverage for back-to-back performances."
                )

            elif query_type == "hybrid_microphone_shortage":
                structured_result = SQLRetrievalService.check_item_inventory_status(db, "microphone", user_role)
                default_facts = (
                    "FestOS database records currently do not list an active inventory entry or recorded shortage "
                    "for microphones (microphones are not tracked in the current equipment catalog)."
                )
                recommendation_body = (
                    "If you are experiencing an on-site shortage of microphones, consider these immediate actions:\n"
                    "1. Rapid Vendor Dispatch: Contact local audio-visual rental vendors for immediate spot delivery of wireless and dynamic microphones.\n"
                    "2. Stage Equipment Prioritization: Reallocate functional microphones to live music and debate stages first, using podium mics for announcements.\n"
                    "3. Backstage Mic Sharing Protocol: Establish a dedicated backstage sanitization and handoff desk to share microphone sets between staggered non-overlapping programs."
                )
                assumptions_body = (
                    "- Microphone shortage is reported from live field observations rather than warehouse checkout ledgers."
                )

            elif query_type in ("hybrid_inventory_procurement", "inventory_levels"):
                structured_result = SQLRetrievalService.get_inventory_levels(db, user_role, low_stock_only=True)
                default_facts = structured_result.get("summary_text", "")
                recommendation_body = (
                    "Based on current stock levels, consider the following actions:\n"
                    "1. Emergency Procurement: Issue purchase or spot-hire orders for items below safety stock thresholds.\n"
                    "2. Vendor SLA Expediting: Request same-day delivery guarantees from contracted fest vendors.\n"
                    "3. Internal Buffer Re-allocation: Check campus department reserves before placing new rental orders."
                )
                assumptions_body = "- Vendor delivery turnaround can be completed within 12 hours."

            else:  # accommodation alternatives / registered participants
                structured_result = SQLRetrievalService.get_accommodation_capacity(db, user_role)
                default_facts = structured_result.get("summary_text", "")
                recommendation_body = (
                    "Based on current housing capacity and participant requirements:\n"
                    "1. Activate External Stay Blocks: Engage contracted partner hotels with a 10% safety buffer to accommodate overflow contingents.\n"
                    "2. Shuttle Route Scheduling: Run dedicated buses every 30 minutes connecting external accommodations to the main campus.\n"
                    "3. Gender-Segregated Blocks: Ensure verified male/female wing allocation and assign female wardens to external stays."
                )
                assumptions_body = (
                    "- External stay properties have confirmed room readiness and verified safety coverage."
                )

            # Build deterministic hybrid answer structure
            hybrid_answer = (
                f"Current situation:\nFestOS shows {default_facts}\n\n"
                f"Recommendation:\n{recommendation_body}\n\n"
                f"Assumptions:\n{assumptions_body}"
            )

            # If LLM is available, allow synthesis
            provider = get_llm_provider()
            if provider.is_configured() and not getattr(provider, "is_deterministic", False):
                history_prompts = _format_history_for_prompt(history_records)
                messages = format_grounded_prompt(
                    user_query=message,
                    user_role=user_role,
                    structured_evidence=default_facts,
                    semantic_evidence="",
                    conversation_history=history_prompts,
                    category="hybrid_event"
                )
                try:
                    llm_out = provider.generate_chat_response(messages)
                    if llm_out.get("content"):
                        hybrid_answer = llm_out["content"]
                except Exception:
                    pass

            validated = AnswerValidator.validate_and_ground(
                raw_answer=hybrid_answer,
                structured_result=structured_result,
                semantic_chunks=[],
                user_role=user_role,
                category="hybrid_event",
                default_summary=hybrid_answer
            )
            follow_ups = IntentRouter.get_suggested_follow_ups("hybrid", query_type)
            return ChatOrchestrator._persist_and_return(
                db=db,
                conversation_id=conversation_id,
                user_message=message,
                validated=validated,
                follow_ups=follow_ups
            )

        # =========================================================================
        # PATH: FESTOS DATABASE QUESTIONS (Category A)
        # =========================================================================
        structured_result = {}
        semantic_chunks: list[dict[str, Any]] = []
        is_clarification = False

        if query_type == "event_start_time":
            target_event = intent.get("target_event")
            is_ambig = intent.get("is_ambiguous_event_time", False)
            if is_ambig or not target_event:
                is_clarification = True
                structured_result = {
                    "authorized": True,
                    "needs_clarification": True,
                    "summary_text": "Which event are you referring to? Share its name and I can check the available schedule.",
                    "citations": [
                        SourceCitation(type="notice", label="Event clarification needed", module="schedule")
                    ]
                }
            else:
                structured_result = SQLRetrievalService.get_event_start_time(db, target_event, user_role)
                if structured_result.get("needs_clarification"):
                    is_clarification = True

        elif query_type == "participant_counts":
            structured_result = SQLRetrievalService.get_participant_counts(db, user_role)
        elif query_type == "reconciliation":
            structured_result = SQLRetrievalService.get_reconciliation(db, user_role)
        elif query_type == "duplicates":
            structured_result = SQLRetrievalService.get_duplicate_records(db, user_role)
        elif query_type == "contingent_participants":
            entity = intent.get("entity") or message
            structured_result = SQLRetrievalService.find_contingent(db, entity, user_role)
        elif query_type == "contingent_summary":
            mismatched = intent.get("mismatched_only", False)
            structured_result = SQLRetrievalService.get_all_contingents(db, user_role, mismatched_only=mismatched)
        elif query_type == "accommodation_capacity":
            structured_result = SQLRetrievalService.get_accommodation_capacity(db, user_role)
        elif query_type == "accommodation_shortage":
            structured_result = SQLRetrievalService.get_accommodation_shortage(db, user_role)
        elif query_type == "accommodation_review_queue":
            structured_result = SQLRetrievalService.get_accommodation_review_queue(db, user_role)
        elif query_type == "explain_accommodation":
            entity = intent.get("entity") or message
            structured_result = SQLRetrievalService.explain_participant_accommodation(db, entity, user_role)
        elif query_type == "scheduling_conflicts":
            venue_filter = intent.get("venue_filter")
            structured_result = SQLRetrievalService.get_scheduling_conflicts(db, user_role, venue_filter=venue_filter)
        elif query_type in ("event_schedule_issues", "move_event_impact"):
            structured_result = SQLRetrievalService.get_events_summary(db, user_role)
        elif query_type == "inventory_levels":
            low_stock = intent.get("low_stock_only", False)
            structured_result = SQLRetrievalService.get_inventory_levels(db, user_role, low_stock_only=low_stock)
        elif query_type == "inventory_movements":
            structured_result = SQLRetrievalService.get_inventory_movements(db, user_role)
        elif query_type == "merch_shortfall":
            structured_result = SQLRetrievalService.get_merch_shortfall(db, user_role)
        elif query_type == "vendor_compliance":
            structured_result = SQLRetrievalService.get_vendor_compliance(db, user_role)
        elif query_type == "dietary_coverage":
            structured_result = SQLRetrievalService.get_dietary_coverage(db, user_role)
        elif query_type == "vendor_settlements":
            structured_result = SQLRetrievalService.get_vendor_settlements(db, user_role)
        elif query_type == "control_kpis":
            structured_result = SQLRetrievalService.get_control_center_status(db, user_role)
        elif query_type == "pending_operational_issues":
            structured_result = SQLRetrievalService.get_pending_operational_issues(db, user_role)
        elif query_type == "disruptions_summary":
            structured_result = SQLRetrievalService.get_disruptions(db, user_role)
        elif query_type == "audit_summary":
            structured_result = SQLRetrievalService.get_audit_summary(db, user_role)

        # Semantic Vector Retrieval if applicable
        if (retrieval_mode in ("semantic", "hybrid") or not structured_result) and not is_clarification:
            v_store = get_vector_store()
            mod_filter = domain if domain not in ("general", "semantic_rule") else None
            semantic_chunks = v_store.search(
                query=message,
                user_role=user_role,
                module_filter=mod_filter,
                top_k=3
            )

        # Move event state change advisory note
        if query_type == "move_event_impact":
            workflow_note = (
                "\n\n[FestOS Workflow Note]: To move or reschedule an event, operators must use "
                "POST /schedule/move or PATCH /schedule/events/{id}. "
                "The chatbot does not autonomously reschedule events. "
                "Moving an event triggers pure scheduler checks for venue availability windows, "
                "setup/teardown buffers (A-11), volunteer shift bounds (A-16), and participant clashes."
            )
            if structured_result.get("summary_text"):
                structured_result["summary_text"] += workflow_note

        default_summary = structured_result.get("summary_text", "")
        if not default_summary and semantic_chunks:
            default_summary = "\n\n".join([f"**{c.get('title')}**\n{c.get('text')}" for c in semantic_chunks])

        # LLM Synthesis or Safe Deterministic Text
        raw_answer = ""
        provider = get_llm_provider()

        if structured_result and not structured_result.get("authorized", True):
            raw_answer = structured_result.get("error", "Access denied.")
        elif is_clarification:
            raw_answer = default_summary
        elif provider.is_configured() and not getattr(provider, "is_deterministic", False):
            history_prompts = _format_history_for_prompt(history_records)
            structured_text = structured_result.get("summary_text", "")
            semantic_text = "\n\n".join([f"[{c['title']}]: {c['text']}" for c in semantic_chunks])

            messages = format_grounded_prompt(
                user_query=message,
                user_role=user_role,
                structured_evidence=structured_text,
                semantic_evidence=semantic_text,
                conversation_history=history_prompts,
                category="festos_data"
            )
            try:
                llm_out = provider.generate_chat_response(messages)
                raw_answer = llm_out.get("content", "")
            except Exception:
                raw_answer = default_summary
        else:
            raw_answer = default_summary

        validated = AnswerValidator.validate_and_ground(
            raw_answer=raw_answer,
            structured_result=structured_result,
            semantic_chunks=semantic_chunks,
            user_role=user_role,
            category="festos_data",
            default_summary=default_summary,
            is_clarification=is_clarification
        )

        follow_ups = IntentRouter.get_suggested_follow_ups(domain, query_type)

        return ChatOrchestrator._persist_and_return(
            db=db,
            conversation_id=conversation_id,
            user_message=message,
            validated=validated,
            follow_ups=follow_ups
        )

    @staticmethod
    def _persist_and_return(
        db: Session,
        conversation_id: str,
        user_message: str,
        validated: dict[str, Any],
        follow_ups: list[str]
    ) -> ChatbotResponse:
        """Helper to record user/assistant turns in SQLite and return schema response."""
        user_rec = ChatMessageRecord(
            conversation_id=conversation_id,
            sender="user",
            content=user_message,
            sources=[],
            confidence="high",
            answer_type=validated.get("answer_type", "FESTOS DATABASE"),
            follow_ups=[]
        )
        asst_rec = ChatMessageRecord(
            conversation_id=conversation_id,
            sender="assistant",
            content=validated["answer"],
            sources=[c.model_dump() for c in validated["citations"]],
            confidence=validated["confidence"],
            answer_type=validated.get("answer_type", "FESTOS DATABASE"),
            follow_ups=follow_ups
        )
        db.add(user_rec)
        db.add(asst_rec)
        db.commit()

        return ChatbotResponse(
            answer=validated["answer"],
            conversation_id=conversation_id,
            sources=validated["citations"],
            confidence=validated["confidence"],
            answer_type=validated.get("answer_type", "FESTOS DATABASE"),
            follow_up_questions=follow_ups
        )

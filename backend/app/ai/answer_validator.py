"""Validation layer to prevent hallucinations, check evidence grounding, and redact leaks.

Accurately attributes sources and answers across the 4 categories:
- FESTOS DATABASE
- DATABASE + AI RECOMMENDATIONS
- GENERAL EVENT KNOWLEDGE
- CLARIFICATION NEEDED
"""
import re
from typing import Any, Optional
from app.ai.schemas import SourceCitation


PHONE_PATTERN = re.compile(r"(\+91[- ]?\d{10}|\b\d{10}\b)")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


class AnswerValidator:
    @staticmethod
    def validate_and_ground(
        raw_answer: str,
        structured_result: dict[str, Any],
        semantic_chunks: list[dict[str, Any]],
        user_role: str,
        category: str = "festos_data",
        default_summary: str = "",
        is_clarification: bool = False,
        recommendation_text: str = ""
    ) -> dict[str, Any]:
        """Validates grounding, attaches source citations, and protects against data leaks."""

        # 1. Authorization failure takes strict precedence
        if structured_result and not structured_result.get("authorized", True):
            return {
                "answer": structured_result.get("error", "Access denied by FestOS security policy."),
                "citations": structured_result.get("citations", []),
                "confidence": "high",
                "answer_type": "FESTOS DATABASE",
            }

        # 2. Category D: Unsafe requests
        if category == "unsafe_request":
            return {
                "answer": (
                    "I cannot fulfill unauthorized requests to extract credentials, user authentication data, "
                    "system secrets, or dump database contents. FestOS security policies strictly protect operational records "
                    "and administrative access."
                ),
                "citations": [
                    SourceCitation(
                        type="notice",
                        label="Security policy restriction",
                        module="security"
                    )
                ],
                "confidence": "high",
                "answer_type": "SYSTEM NOTICE",
            }

        # 3. Category D: Out of Scope
        if category == "out_of_scope":
            return {
                "answer": (
                    "I'm FestOS AI, your assistant for festivals and event operations. "
                    "I can help with event planning, schedules, participants, accommodation, logistics, "
                    "vendors, and operational recommendations. What would you like help with?"
                ),
                "citations": [
                    SourceCitation(
                        type="notice",
                        label="General festival assistant scope",
                        module="general"
                    )
                ],
                "confidence": "high",
                "answer_type": "GENERAL EVENT KNOWLEDGE",
            }

        # 4. Clarification Needed (e.g. Ambiguous event start time)
        if is_clarification or (structured_result and structured_result.get("needs_clarification")):
            clarification_answer = raw_answer or default_summary or (
                "Which event are you referring to? Share its name and I can check the available schedule."
            )
            return {
                "answer": clarification_answer,
                "citations": structured_result.get("citations") or [
                    SourceCitation(
                        type="notice",
                        label="Event clarification needed",
                        module="schedule"
                    )
                ],
                "confidence": "medium",
                "answer_type": "CLARIFICATION NEEDED",
            }

        # 5. Category B: General Event Knowledge (No DB/Vector required!)
        if category == "general_event":
            answer = (raw_answer or default_summary).strip()
            return {
                "answer": answer,
                "citations": [
                    SourceCitation(
                        type="general_event_knowledge",
                        label="General event-management knowledge",
                        module="event_planning",
                        detail={"domain": "festival_operations"}
                    )
                ],
                "confidence": "high",
                "answer_type": "GENERAL EVENT KNOWLEDGE",
            }

        # 6. Category C: Hybrid Event Questions
        if category == "hybrid_event":
            answer = (raw_answer or default_summary).strip()

            # Assemble citations from structured DB queries and domain knowledge
            citations: list[SourceCitation] = []
            if structured_result and "citations" in structured_result:
                citations.extend(structured_result["citations"])

            citations.append(
                SourceCitation(
                    type="general_event_knowledge",
                    label="General event-management knowledge",
                    module="event_planning"
                )
            )

            # Privacy redactions
            if user_role != "director":
                answer = PHONE_PATTERN.sub("[masked contact]", answer)
                for em in EMAIL_PATTERN.findall(answer):
                    if not em.endswith("@festos.local"):
                        answer = answer.replace(em, "[masked email]")

            return {
                "answer": answer,
                "citations": citations,
                "confidence": "high",
                "answer_type": "DATABASE + AI RECOMMENDATIONS",
            }

        # 7. Category A: FestOS Database Questions
        has_structured = bool(structured_result and (structured_result.get("facts") or structured_result.get("summary_text")))
        has_semantic = bool(semantic_chunks)

        if not has_structured and not has_semantic:
            return {
                "answer": (
                    "I couldn't verify that information from the currently available FestOS data. "
                    "The database does not contain recorded entries or rules matching your request."
                ),
                "citations": [
                    SourceCitation(
                        type="notice",
                        label="No database or document matches found",
                        module="general"
                    )
                ],
                "confidence": "low",
                "answer_type": "FESTOS DATABASE",
            }

        answer = raw_answer.strip() if raw_answer else default_summary

        # Privacy redactions for non-director roles
        if user_role != "director":
            answer = PHONE_PATTERN.sub("[masked contact]", answer)
            for em in EMAIL_PATTERN.findall(answer):
                if not em.endswith("@festos.local"):
                    answer = answer.replace(em, "[masked email]")

        citations = []
        if has_structured and "citations" in structured_result:
            citations.extend(structured_result["citations"])

        for c in semantic_chunks[:3]:
            citations.append(
                SourceCitation(
                    type="semantic_document",
                    label=c.get("title") or f"{c.get('source_type')}: {c.get('source_id')}",
                    module=c.get("module", "operations"),
                    detail={"source_id": c.get("source_id"), "relevance": c.get("score")}
                )
            )

        confidence = "high" if has_structured else ("medium" if has_semantic else "low")

        return {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
            "answer_type": "FESTOS DATABASE",
        }

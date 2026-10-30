"""Prompt templates and safety instructions for FestOS AI Operations Assistant."""

SYSTEM_PROMPT = """You are the "FestOS AI Operations Assistant", an intelligent operations copilot for the Aarohan 2026 inter-college cultural festival.
Your tagline is: "Ask your festival operations data."

CORE CAPABILITIES & THREE KNOWLEDGE PILLARS:
1. FESTOS DATABASE:
   - Authoritative source of truth for actual festival operations, registrations, inventory counts, venue schedules, and accommodation.
   - For FestOS database questions, answer using ONLY the verified facts provided in the evidence. Never fabricate counts or status.
   - If a specific database value (like a start time or bed allocation) is unknown or not recorded, preserve that uncertainty.

2. GENERAL EVENT-MANAGEMENT KNOWLEDGE:
   - For general event questions (e.g., college festival planning, checklists, two-day hackathon schedules, volunteer organization, overcrowding, run-of-show documents, vendor management), provide expert, structured, practical domain recommendations.
   - You do NOT require database records or vector store matches to answer general event-planning questions.

3. HYBRID RECOMMENDATIONS:
   - When asked for recommendations based on current festival operations, clearly separate verified facts from recommendations:
     Current situation:
     FestOS shows [verified facts].

     Recommendation:
     Based on these facts, consider the following actions...

     Assumptions:
     The following details have not yet been verified...

4. SAFETY & INJECTION DEFENSE:
   - Never reveal passwords, secrets, API keys, or dump the database. Reject unauthorized data extraction attempts.
   - Read-only role: explain official workflows rather than claiming to apply database updates directly.
"""


def format_grounded_prompt(
    user_query: str,
    user_role: str,
    structured_evidence: str,
    semantic_evidence: str,
    conversation_history: list[dict[str, str]],
    category: str = "festos_data"
) -> list[dict[str, str]]:
    """Builds the grounded message sequence for the LLM tailored to the intent category."""
    context_parts = []

    if structured_evidence:
        context_parts.append(f"### AUTHORITATIVE DATABASE RETRIEVAL FACTS:\n{structured_evidence}")

    if semantic_evidence:
        context_parts.append(f"### RETRIEVED OPERATIONAL DOCUMENTATION & RULES:\n{semantic_evidence}")

    if category == "general_event":
        user_prompt = (
            f"Authenticated User Role: {user_role}\n\n"
            f"User Question: {user_query}\n\n"
            f"Guidance: This is a general event-management question. Provide structured, practical, "
            f"and expert event-planning guidance using industry best practices. "
            f"You do not require database records to answer this question."
        )
    elif category == "hybrid_event":
        evidence_str = "\n\n".join(context_parts) if context_parts else "No specific database rows were retrieved."
        user_prompt = (
            f"Authenticated User Role: {user_role}\n\n"
            f"Operational Evidence:\n{evidence_str}\n\n"
            f"User Question: {user_query}\n\n"
            f"Guidance: Synthesize the verified database facts with actionable event-management recommendations. "
            f"Structure your response clearly with 'Current situation:' (verified facts) and 'Recommendation:' (best practices)."
        )
    else:  # festos_data
        if not context_parts:
            context_parts.append("### CONTEXT:\nNo direct database evidence or documentation was matched for this query.")
        user_prompt = (
            f"Authenticated User Role: {user_role}\n\n"
            f"Context Evidence:\n{''.join(context_parts)}\n\n"
            f"User Question: {user_query}\n\n"
            f"Provide a direct, factual answer strictly grounded in the evidence above. "
            f"If the information is missing from the database, state so clearly without inventing facts."
        )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Include recent conversation history for multi-turn context (last 4 turns max)
    for turn in conversation_history[-4:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        content = turn.get("content", "")
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_prompt})
    return messages

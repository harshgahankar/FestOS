"""Question normalization, intent classification, and multi-turn context resolution.

Classifies user questions into a four-category router:
- festos_data: Authoritative operational facts from the database and operational rules.
- general_event: General festival planning, advice, checklists, and domain best practices.
- hybrid_event: Verified current situation combined with actionable recommendations.
- out_of_scope: Polite redirection for unrelated topics.
- unsafe_request: Refusal for credential extraction, prompt injection, and database dumps.
"""
import re
from typing import Any, Optional


def normalize_query(query: str) -> str:
    """Normalize input query text by trimming, collapsing spaces, and lowercasing."""
    q = query.strip()
    q = re.sub(r"\s+", " ", q)
    return q


def extract_entities(query: str) -> dict[str, Any]:
    """Extracts known operational entity references (IDs, codes, numbers)."""
    entities: dict[str, Any] = {}

    # Contingent ID (e.g. C01, C27, C38)
    c_match = re.search(r"\b(C\d{1,2})\b", query, re.IGNORECASE)
    if c_match:
        entities["contingent_id"] = c_match.group(1).upper()

    # Participant ID (e.g. P0001, P001, P_DUP01, P_DUP02)
    p_match = re.search(r"\b(P_DUP\d{2}|P\d{3,4})\b", query, re.IGNORECASE)
    if p_match:
        entities["participant_id"] = p_match.group(1).upper()

    # Event ID (e.g. E01, E12)
    e_match = re.search(r"\b(E\d{1,2})\b", query, re.IGNORECASE)
    if e_match:
        entities["event_id"] = e_match.group(1).upper()

    # Vendor ID (e.g. VND01, VND14)
    v_match = re.search(r"\b(VND\d{1,2})\b", query, re.IGNORECASE)
    if v_match:
        entities["vendor_id"] = v_match.group(1).upper()

    # Venue ID (e.g. V01, V09)
    venue_match = re.search(r"\b(V\d{1,2})\b", query, re.IGNORECASE)
    if venue_match:
        entities["venue_id"] = venue_match.group(1).upper()

    # Assumption Code (e.g. A-02, A-11)
    a_match = re.search(r"\b(A-\d{1,2})\b", query, re.IGNORECASE)
    if a_match:
        entities["assumption_code"] = a_match.group(1).upper()

    return entities


class IntentRouter:
    """Classifies user queries into the four-category intent routing model."""

    @staticmethod
    def classify(query: str, history: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        norm = normalize_query(query).lower()
        entities = extract_entities(query)
        last_intent = None

        # Check conversation history for follow-up interpretation
        if history and len(history) >= 2:
            last_bot_msg = history[-1]
            last_sources = last_bot_msg.get("sources") or []
            if last_sources:
                last_intent = last_sources[0].get("module")

        # =========================================================================
        # 1. SAFETY & SECURITY CHECKS (unsafe_request)
        # =========================================================================
        unsafe_pattern = re.compile(
            r"\b(password|passwords|dump\s+the\s+database|dump\s+database|drop\s+table|"
            r"drop\s+database|truncate\s+table|system\s+prompt|ignore\s+(all\s+)?instructions|"
            r"ignore\s+your\s+instructions|reveal\s+every\s+user|show\s+all\s+passwords|"
            r"api_key|token\s+secret|exfiltrat)\b",
            re.IGNORECASE
        )
        if unsafe_pattern.search(norm):
            return {
                "category": "unsafe_request",
                "domain": "security",
                "query_type": "unsafe_refusal",
                "retrieval_mode": "none",
                "requires_database": False,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Request violates security or safety boundary."
            }

        # =========================================================================
        # 2. OUT-OF-SCOPE CHECKS (out_of_scope)
        # =========================================================================
        # Explicit test and common unrelated questions
        out_of_scope_triggers = [
            "capital of france", "capital of", "tell me a random joke", "tell me a joke",
            "write a romantic poem", "write a poem", "solve an unrelated", "solve 2+2",
            "what is 2 + 2", "celebrity gossip", "who is the president of", "recipe for",
            "weather in antarctica"
        ]
        is_explicit_oos = any(t in norm for t in out_of_scope_triggers)
        if is_explicit_oos:
            return {
                "category": "out_of_scope",
                "domain": "out_of_scope",
                "query_type": "out_of_scope_redirection",
                "retrieval_mode": "none",
                "requires_database": False,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "The question is outside the scope of festival and event operations."
            }

        # =========================================================================
        # 3. EVENT START TIME QUERIES (Category A vs B distinction)
        # =========================================================================
        # General advice on festival start time ("What time should we start a college festival?")
        if ("what time should" in norm or "when should" in norm) and ("start" in norm or "begin" in norm) and "festival" in norm:
            return {
                "category": "general_event",
                "domain": "general_event",
                "query_type": "festival_start_time_advice",
                "retrieval_mode": "none",
                "requires_database": False,
                "requires_rag": False,
                "requires_llm": True,
                "reason": "The user asks for general advice on when to start a festival program."
            }

        # Operational event start time queries ("At what time does Event A start?")
        time_query_match = re.search(
            r"(?:at\s+what\s+time|what\s+time|when)\s+(?:does|will|is)?\s*(?:the\s+)?(.*?)\s*(?:start|begin|commence|scheduled)",
            norm
        )
        # Verb-less variant ("what time is the MUN event", "when is the MUN event")
        name_time_match = re.search(
            r"(?:what\s+time|when|at\s+what\s+time)\s+(?:is|does|will|for|was)?\s*(?:the\s+)?(.*?)\s*event\b",
            norm
        )
        if time_query_match or name_time_match or (("what time" in norm or "at what time" in norm or "when does" in norm) and ("start" in norm or "begin" in norm)):
            if time_query_match:
                raw_event = time_query_match.group(1).strip()
            elif name_time_match:
                raw_event = name_time_match.group(1).strip()
            else:
                raw_event = ""
            # Clean filler words and the trailing "event(s)" the phrasing added
            clean_event = re.sub(r"^(the|an|our)\s+", "", raw_event).strip()
            if len(clean_event.split()) >= 2 or "event" in clean_event:
                clean_event = re.sub(r"\s+events?$", "", clean_event, flags=re.IGNORECASE).strip()

            if clean_event in ("", "event", "the event", "program", "session") and not entities.get("event_id"):
                # Ambiguous: user did not identify the event
                return {
                    "category": "festos_data",
                    "domain": "schedule",
                    "query_type": "event_start_time",
                    "is_ambiguous_event_time": True,
                    "target_event": None,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Event start time inquiry requiring specific event clarification."
                }
            else:
                target = entities.get("event_id") or clean_event
                return {
                    "category": "festos_data",
                    "domain": "schedule",
                    "query_type": "event_start_time",
                    "is_ambiguous_event_time": False,
                    "target_event": target,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": f"Authoritative start time inquiry for event '{target}'."
                }

        # =========================================================================
        # 4. HYBRID EVENT QUESTIONS (Category C)
        # =========================================================================
        # Conditioned recommendations combining database data + event expertise
        is_hybrid = False
        hybrid_type = None

        if "based on our current schedule" in norm or "reduce scheduling conflicts" in norm or (
            "schedule" in norm and ("conflict" in norm or "clash" in norm) and ("reduce" in norm or "improve" in norm or "recommend" in norm)
        ):
            is_hybrid = True
            hybrid_type = "hybrid_schedule_conflicts"

        elif "multiple events at the same venue" in norm or ("same venue" in norm and "improve" in norm):
            is_hybrid = True
            hybrid_type = "hybrid_venue_scheduling"

        elif "based on our current inventory" in norm or ("inventory" in norm and "procure" in norm):
            is_hybrid = True
            hybrid_type = "hybrid_inventory_procurement"

        elif "shortage of microphones" in norm or ("microphone" in norm and ("shortage" in norm or "what should we do" in norm)):
            is_hybrid = True
            hybrid_type = "hybrid_microphone_shortage"

        elif "accommodation capacity is insufficient" in norm or ("accommodation" in norm and "alternatives" in norm):
            is_hybrid = True
            hybrid_type = "hybrid_accommodation_alternatives"

        elif "registered participants" in norm and ("how should we organize accommodation" in norm or "how should we arrange accommodation" in norm):
            is_hybrid = True
            hybrid_type = "hybrid_accommodation_for_registered"

        if is_hybrid:
            return {
                "category": "hybrid_event",
                "domain": "hybrid",
                "query_type": hybrid_type,
                "retrieval_mode": "hybrid",
                "requires_database": True,
                "requires_rag": True,
                "requires_llm": True,
                "item_query": "microphone" if "microphone" in norm else None,
                "reason": "Combines authoritative FestOS operational facts with general event recommendations."
            }

        # =========================================================================
        # 5. GENERAL EVENT-MANAGEMENT QUESTIONS (Category B)
        # =========================================================================
        general_event_phrases = [
            "how should i plan a college festival", "plan a college festival", "organize a college festival",
            "event checklist", "event safety checklist", "checklist",
            "schedule for a two-day hackathon", "hackathon schedule", "two-day hackathon",
            "manage registration queues", "registration queues", "queues",
            "reduce overcrowding", "overcrowding at an event", "overcrowding", "crowd control",
            "difference between internal and external accommodation", "internal and external accommodation",
            "how should we organize volunteers", "organize volunteers effectively", "organize volunteers",
            "volunteer structure", "volunteer shifts",
            "run-of-show document", "run of show", "run-of-show",
            "prevent event scheduling conflicts", "prevent scheduling conflicts", "prevent clashes",
            "best practices for vendor management", "vendor management best practices",
            "estimate accommodation requirements", "arrange accommodation for 500", "accommodation for 500",
            "manage multiple events running simultaneously"
        ]

        if any(p in norm for p in general_event_phrases):
            return {
                "category": "general_event",
                "domain": "general_event",
                "query_type": "general_event_advice",
                "retrieval_mode": "none",
                "requires_database": False,
                "requires_rag": False,
                "requires_llm": True,
                "reason": "The user requests general event-planning advice and domain expertise."
            }

        # Multi-turn conversational follow-up for general event topics
        if history and ("volunteer" in norm or "volunteers" in norm):
            # Check if previous context established a festival plan
            past_texts = " ".join([str(h.get("content", "")).lower() for h in history])
            if "festival" in past_texts or "hackathon" in past_texts or "college" in past_texts:
                return {
                    "category": "general_event",
                    "domain": "general_event",
                    "query_type": "general_event_advice",
                    "retrieval_mode": "none",
                    "requires_database": False,
                    "requires_rag": False,
                    "requires_llm": True,
                    "reason": "Follow-up question on volunteers within conversational festival context."
                }

        # =========================================================================
        # 6. FESTOS DATABASE QUESTIONS (Category A)
        # =========================================================================
        # ------------------- PARTICIPANTS & CONTINGENTS -------------------
        if ("participant" in norm or "attendee" in norm or "registered" in norm) and (
            "count" in norm or "how many" in norm or "total" in norm or "number of" in norm
        ):
            return {
                "category": "festos_data",
                "domain": "participants",
                "query_type": "participant_counts",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative query for registered participant counts."
            }

        if "reconcil" in norm:
            return {
                "category": "festos_data",
                "domain": "participants",
                "query_type": "reconciliation",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative import reconciliation funnel query."
            }

        if "duplicate" in norm:
            return {
                "category": "festos_data",
                "domain": "participants",
                "query_type": "duplicates",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative query for duplicate participant records."
            }

        if "contingent" in norm:
            if entities.get("contingent_id") or "belonging to" in norm or "from" in norm:
                return {
                    "category": "festos_data",
                    "domain": "contingents",
                    "query_type": "contingent_participants",
                    "entity": entities.get("contingent_id") or query,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Query for contingent membership records."
                }
            if "mismatch" in norm:
                return {
                    "category": "festos_data",
                    "domain": "contingents",
                    "query_type": "contingent_summary",
                    "mismatched_only": True,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Query for contingents with size mismatches."
                }
            return {
                "category": "festos_data",
                "domain": "contingents",
                "query_type": "contingent_summary",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative summary of festival contingents."
            }

        if "active participant" in norm:
            return {
                "category": "festos_data",
                "domain": "participants",
                "query_type": "participant_counts",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative count of active participants."
            }

        # ------------------- ACCOMMODATION -------------------
        if "accommodation" in norm or "housing" in norm or "hostel" in norm or "bed" in norm or "room" in norm:
            if "shortage" in norm or "unmet" in norm or "lack" in norm:
                return {
                    "category": "festos_data",
                    "domain": "accommodation",
                    "query_type": "accommodation_shortage",
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative report on accommodation shortage."
                }
            if "review" in norm or "queue" in norm or "unclear" in norm or "consent" in norm:
                return {
                    "category": "festos_data",
                    "domain": "accommodation",
                    "query_type": "accommodation_review_queue",
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative review queue query."
                }
            if "explain" in norm or entities.get("participant_id"):
                return {
                    "category": "festos_data",
                    "domain": "accommodation",
                    "query_type": "explain_accommodation",
                    "entity": entities.get("participant_id") or query,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Explanation of participant accommodation allocation."
                }
            return {
                "category": "festos_data",
                "domain": "accommodation",
                "query_type": "accommodation_capacity",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative accommodation capacity status."
            }

        # ------------------- SCHEDULING & EVENTS -------------------
        # Event listing / count by festival day ("how many events on day 2?", "what events are there on day 2?")
        day_match = re.search(r"\bday\s*(\d+|[a-z]+)\b", norm)
        if day_match and ("event" in norm or "events" in norm):
            day_word = day_match.group(1)
            day_num = {
                "one": 1, "two": 2, "three": 3, "first": 1, "second": 2, "third": 3,
            }.get(day_word) or (int(day_word) if day_word.isdigit() else None)
            if day_num:
                return {
                    "category": "festos_data",
                    "domain": "schedule",
                    "query_type": "event_list",
                    "day": day_num,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative listing of events scheduled on a festival day."
                }

        # Event listing without explicit day ("how many events are there?")
        if ("how many" in norm or "list" in norm or "which" in norm) and "event" in norm:
            return {
                "category": "festos_data",
                "domain": "schedule",
                "query_type": "event_list",
                "day": None,
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative listing of scheduled events."
            }

        if "conflict" in norm or "clash" in norm or "double-booked" in norm or "overlap" in norm:
            return {
                "category": "festos_data",
                "domain": "schedule",
                "query_type": "scheduling_conflicts",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative report on unresolved scheduling conflicts."
            }

        if "move" in norm and ("event" in norm or entities.get("event_id")):
            return {
                "category": "festos_data",
                "domain": "schedule",
                "query_type": "move_event_impact",
                "retrieval_mode": "hybrid",
                "entity": entities.get("event_id"),
                "requires_database": True,
                "requires_rag": True,
                "requires_llm": True,
                "reason": "Impact analysis for moving an event."
            }

        if "event" in norm and ("issue" in norm or "unscheduled" in norm or "problem" in norm or "schedule" in norm or "tomorrow" in norm):
            return {
                "category": "festos_data",
                "domain": "schedule",
                "query_type": "event_schedule_issues",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Operational status of scheduled vs unscheduled events."
            }

        # ------------------- INVENTORY & MERCH -------------------
        if "inventory" in norm or "equipment" in norm or "stock" in norm:
            if "movement" in norm or "log" in norm or "ledger" in norm:
                return {
                    "category": "festos_data",
                    "domain": "inventory",
                    "query_type": "inventory_movements",
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative ledger of inventory movements."
                }
            if "low" in norm or "shortage" in norm or "repair" in norm or "condition" in norm:
                return {
                    "category": "festos_data",
                    "domain": "inventory",
                    "query_type": "inventory_levels",
                    "low_stock_only": True,
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative check for low inventory items."
                }
            return {
                "category": "festos_data",
                "domain": "inventory",
                "query_type": "inventory_levels",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative summary of inventory levels."
            }

        if "merch" in norm or "t-shirt" in norm or "tshirt" in norm or "merchandise" in norm:
            return {
                "category": "festos_data",
                "domain": "inventory",
                "query_type": "merch_shortfall",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative merchandise shortfall report."
            }

        # ------------------- VENDORS & DIETARY -------------------
        # Diet-specific questions (e.g. "which vendor serves vegetarian and halal")
        # must win over generic vendor compliance routing.
        diet_tags: list[str] = []
        t = norm.replace("-", " ")
        if "non veg" in t or "nonvegetarian" in t:
            diet_tags.append("non-vegetarian")
        if "vegetarian" in t or re.search(r"\bveg\b", t):
            diet_tags.append("vegetarian")
        if "vegan" in t:
            diet_tags.append("vegan")
        if "halal" in t:
            diet_tags.append("halal")
        if "jain" in t:
            diet_tags.append("jain")
        if "nut" in t and ("allergy" in t or "free" in t):
            diet_tags.append("nut allergy")
        if "gluten" in t:
            diet_tags.append("gluten-free")
        if diet_tags or "dietary coverage" in norm or "diet coverage" in norm:
            return {
                "category": "festos_data",
                "domain": "vendors",
                "query_type": "dietary_coverage",
                "tags": diet_tags or None,
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative dietary coverage and vendor menu lookup."
            }

        if "vendor" in norm:
            if "compliance" in norm or "hygiene" in norm or "certificate" in norm or "expired" in norm:
                return {
                    "category": "festos_data",
                    "domain": "vendors",
                    "query_type": "vendor_compliance",
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative vendor compliance status."
                }
            if "settlement" in norm or "rate" in norm or "payment" in norm or "order" in norm:
                return {
                    "category": "festos_data",
                    "domain": "vendors",
                    "query_type": "vendor_settlements",
                    "retrieval_mode": "structured",
                    "requires_database": True,
                    "requires_rag": False,
                    "requires_llm": False,
                    "reason": "Authoritative vendor settlement review."
                }
            return {
                "category": "festos_data",
                "domain": "vendors",
                "query_type": "vendor_compliance",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative vendor compliance records."
            }

        if "diet" in norm or "coverage" in norm or "meal" in norm or "vegan" in norm or "halal" in norm or "jain" in norm:
            return {
                "category": "festos_data",
                "domain": "vendors",
                "query_type": "dietary_coverage",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative dietary coverage check."
            }

        # ------------------- OPERATIONS & CONTROL CENTER -------------------
        if "attention" in norm or "pending operational issue" in norm or ("director" in norm and "issue" in norm):
            return {
                "category": "festos_data",
                "domain": "control",
                "query_type": "pending_operational_issues",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative list of pending operational issues."
            }

        if "control center" in norm or "kpi" in norm or "operations status" in norm or "status of the fest" in norm:
            return {
                "category": "festos_data",
                "domain": "control",
                "query_type": "control_kpis",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative Control Center KPI overview."
            }

        if "disruption" in norm:
            return {
                "category": "festos_data",
                "domain": "disruptions",
                "query_type": "disruptions_summary",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative report on simulated disruptions."
            }

        if "audit" in norm:
            return {
                "category": "festos_data",
                "domain": "audit",
                "query_type": "audit_summary",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Authoritative audit log activity."
            }

        # ------------------- FOLLOW-UP RESOLUTION -------------------
        if last_intent == "schedule" and ("venue" in norm or "which of them" in norm or "them" in norm):
            return {
                "category": "festos_data",
                "domain": "schedule",
                "query_type": "scheduling_conflicts",
                "venue_filter": "venue",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Filtered scheduling conflicts follow-up."
            }

        if last_intent == "accommodation" and ("which of them" in norm or "shortage" in norm):
            return {
                "category": "festos_data",
                "domain": "accommodation",
                "query_type": "accommodation_shortage",
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Accommodation shortage follow-up."
            }

        if last_intent == "contingents" and ("members" in norm or "who" in norm or entities.get("contingent_id")):
            return {
                "category": "festos_data",
                "domain": "contingents",
                "query_type": "contingent_participants",
                "entity": entities.get("contingent_id") or query,
                "retrieval_mode": "structured",
                "requires_database": True,
                "requires_rag": False,
                "requires_llm": False,
                "reason": "Contingent participant roster follow-up."
            }

        # ------------------- SEMANTIC RULE / HYBRID -------------------
        if "why" in norm or "rule" in norm or "policy" in norm or "how does" in norm or "assumption" in norm or entities.get("assumption_code"):
            return {
                "category": "festos_data",
                "domain": "semantic_rule",
                "query_type": "operational_rule_lookup",
                "entity": entities.get("assumption_code"),
                "retrieval_mode": "semantic",
                "requires_database": False,
                "requires_rag": True,
                "requires_llm": True,
                "reason": "Lookup of documented FestOS operating rules and assumptions."
            }

        # Event-related keyword heuristic check before marking out of scope
        event_terms = [
            "festival", "fest", "event", "stage", "venue", "schedule", "participant",
            "contingent", "hostel", "accommodation", "vendor", "artist", "food",
            "volunteer", "judge", "sound", "lighting", "mic", "microphone", "logistics"
        ]
        if any(t in norm for t in event_terms):
            return {
                "category": "general_event",
                "domain": "general_event",
                "query_type": "general_event_advice",
                "retrieval_mode": "none",
                "requires_database": False,
                "requires_rag": False,
                "requires_llm": True,
                "reason": "General festival query handled via event-management expertise."
            }

        # Final Fallback to out_of_scope to avoid pointless DB scans on unrelated chat
        return {
            "category": "out_of_scope",
            "domain": "out_of_scope",
            "query_type": "out_of_scope_redirection",
            "retrieval_mode": "none",
            "requires_database": False,
            "requires_rag": False,
            "requires_llm": False,
            "reason": "Topic is outside the scope of festival operations."
        }

    @staticmethod
    def get_suggested_follow_ups(domain: str, query_type: str) -> list[str]:
        suggestions_map = {
            "participants": [
                "Are there duplicate participant records?",
                "Which participant records require reconciliation?",
                "Find participants belonging to contingent C01."
            ],
            "contingents": [
                "Show contingents with size mismatches.",
                "How many active participants do we have?",
                "Check accommodation capacity for contingents."
            ],
            "accommodation": [
                "Are there any accommodation shortages?",
                "Which accommodation allocations need review?",
                "How many hostel beds vs external beds are available?"
            ],
            "schedule": [
                "Which of them are related to venues?",
                "What happens if we move a particular event?",
                "Summarize the current scheduling conflicts."
            ],
            "inventory": [
                "What merchandise shortfalls are present?",
                "Summarize recent inventory movements.",
                "Which equipment items are under repair?"
            ],
            "vendors": [
                "What is the current dietary coverage?",
                "Which vendor settlements need attention?",
                "Which vendors have compliance issues?"
            ],
            "control": [
                "What are the most important pending operational issues?",
                "What disruptions have been recorded?",
                "Summarize current scheduling conflicts."
            ],
            "disruptions": [
                "Summarize the current control center status.",
                "Show recent audit records.",
                "Which inventory items have low stock?"
            ],
            "audit": [
                "Summarize current control center status.",
                "What disruptions have been recorded?",
                "Show pending operational alerts."
            ],
            "general_event": [
                "What should be included in an event checklist?",
                "How can we organize volunteers effectively?",
                "What is a good schedule for a two-day hackathon?",
                "How can we reduce overcrowding at an event?"
            ],
            "hybrid": [
                "Based on our current schedule, how can we reduce scheduling conflicts?",
                "Our inventory shows a shortage of microphones. What should we do?",
                "What are the alternative options if hostel capacity is exceeded?"
            ]
        }
        return suggestions_map.get(domain, [
            "How many active participants are registered?",
            "Which scheduling conflicts are unresolved?",
            "Are there any accommodation shortages?",
            "What should be included in an event checklist?"
        ])

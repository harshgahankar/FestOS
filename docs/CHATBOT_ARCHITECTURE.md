# FestOS AI Operations Assistant — Architecture & Integration Guide

**Name:** FestOS AI Operations Assistant  
**Tagline:** *"Ask your festival operations data."*  
**UI Branding:** `FestOS AI`  

---

## 1. System Overview & Hybrid Architecture

FestOS AI Operations Assistant is an authoritative, database-aware conversational assistant integrated directly into the FestOS portal for the Aarohan 2026 inter-college festival. It bridges natural language queries with verified relational data and operational rules.

### Core Philosophy
1. **The Database is the Source of Truth:** Counts, inventory levels, scheduling conflicts, and accommodation numbers are always calculated from authoritative database models and pure backend engines. Never hallucinated or guessed.
2. **Read-Only Advisory Safety:** The chatbot strictly advises and explains workflows. It never executes arbitrary SQL or autonomous database mutations.
3. **Engine Purity & Reuse:** Calculations reuse existing authoritative pure engines (`engines.scheduler`, `engines.allocator`, `engines.inventory`, `engines.vendors`, `engines.importer`) rather than inventing conflicting ad-hoc business logic.
4. **Zero-Leak Field Masking:** Participant private fields (phones, emails, medical notes) are masked according to the user's role using `app.auth.mask_fields`.
5. **No Blind Failures:** Missing AI credentials do not break system startup. The chatbot features a deterministic fallback mode that directly returns verified database queries and citations.

```
                                User Question
                                      │
                                      ▼
                        Authentication & Authorization
                          (JWT / Supabase Session)
                                      │
                                      ▼
                           Question Normalization
                        (Entity Extraction, Trimming)
                                      │
                                      ▼
                      Four-Category Intent Router
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    Category A: FestOS Data   Category B: General     Category C: Hybrid
    - Authoritative DB SQL    - Event-planning advice - Real DB situation
    - Start time lookups      - Checklists & queues   - Actionable recs
    - Clarification needed    - Zero DB req.          - Explicit structure
              │                       │                       │
              └───────────────┬───────┴───────────────────────┘
                              │
              (Category D fast-path: polite redirect / secure refusal)
                              │
                              ▼
                     Evidence Validation
            (Grounding Check & Privacy Masking)
                              │
                              ▼
                    LLM / Fallback Engine
             (OpenAI-compatible / Deterministic)
                              │
                              ▼
                     Citation Attribution
       - FESTOS DATABASE
       - DATABASE + AI RECOMMENDATIONS
       - GENERAL EVENT KNOWLEDGE
       - CLARIFICATION NEEDED
                              │
                              ▼
                       Validated Answer
```

---

## 2. Supported Question Domains & Authoritative Sources

| Domain | Example Questions | Authoritative Backend Handler |
|---|---|---|
| **Participants** | "How many participants are registered?", "How many active participants do we have?", "Are there duplicate participant records?" | `SQLRetrievalService.get_participant_counts`, `get_duplicate_records` |
| **Reconciliation** | "Which participant records require reconciliation?", "Show the reconciliation funnel." | `engines.importer.reconciliation` via `SQLRetrievalService.get_reconciliation` |
| **Contingents** | "Find participants belonging to contingent C01", "Show contingents with size mismatches." | `SQLRetrievalService.find_contingent`, `get_all_contingents` |
| **Accommodation** | "How many accommodation places are available?", "Are there any accommodation shortages?", "Which allocations need review?" | `SQLRetrievalService.get_accommodation_capacity`, `get_accommodation_shortage`, `get_accommodation_review_queue` |
| **Allocation Explanation** | "Explain the accommodation allocation for participant P001." | `SQLRetrievalService.explain_participant_accommodation` (role-gated) |
| **Scheduling** | "Which scheduling conflicts are unresolved?", "Which events have scheduling issues?" | `engines.scheduler.find_conflicts` via `SQLRetrievalService.get_scheduling_conflicts` |
| **Event Re-scheduling** | "What happens if we move a particular event?" | Explains required operator workflow (`POST /schedule/move`), buffer constraints (A-11), shift constraints (A-16). Never mutates DB. |
| **Inventory & Equipment** | "Which inventory items have low stock?", "What equipment shortages exist?" | `engines.inventory.stock_levels` via `SQLRetrievalService.get_inventory_levels` |
| **Merchandise** | "What merchandise shortfalls are present?", "How many t-shirts are missing?" | `engines.inventory.merch_shortfall` via `SQLRetrievalService.get_merch_shortfall` |
| **Food Vendors** | "Which vendors have compliance issues?", "Are any hygiene certificates expired?" | `engines.vendors.compliance` via `SQLRetrievalService.get_vendor_compliance` |
| **Dietary Coverage** | "What is the current dietary coverage?", "Which diets are uncovered?" | `engines.vendors.coverage_matrix` via `SQLRetrievalService.get_dietary_coverage` |
| **Vendor Settlement** | "Which vendor settlements need attention?" | `engines.vendors.settlement` via `SQLRetrievalService.get_vendor_settlements` |
| **Operations & KPIs** | "What are the most important pending operational issues?", "Summarize current control center status." | `SQLRetrievalService.get_control_center_status`, `get_pending_operational_issues` (director only) |
| **Disruptions** | "What disruptions have been recorded?" | `SQLRetrievalService.get_disruptions` (director only) |
| **Audit Log** | "Show recent audit records." | `SQLRetrievalService.get_audit_summary` (director only) |
| **Operational Rules** | "Why is blank gender treated as unknown?", "Explain rule A-02." | Semantic retrieval against `docs/ASSUMPTIONS.md` |

---

## 3. Role-Based Access Control (RBAC) & Privacy Protections

The assistant inherits FestOS's role hierarchy:

| User Role | Permitted Chatbot Domains | Sensitive Data Protections |
|---|---|---|
| **director** | All domains (full access to control KPIs, disruptions, audit logs, vendor settlements) | Visible according to director clearance. |
| **accommodation_lead** | Participants (masked), Contingents, Accommodation, Capacity, Shortages, Review queue | Sensitive fields (phone, email) masked unless audited reveal occurs. Cannot access vendor rates or director control inbox. |
| **events_lead** | Participants (masked), Contingents, Schedule, Conflicts, Venues, Events | Cannot access accommodation allocations, vendor rates, or director control inbox. |
| **logistics_lead** | Participants (masked), Contingents, Inventory levels, Merch shortfall, Movements | Cannot access schedule conflicts or director control inbox. |
| **vendor_lead** | Participants (dietary only), Vendors, Food compliance, Dietary coverage, Settlements | Cannot access accommodation allocations or schedule conflicts. |
| **volunteer** | Participant validation (dietary tags only), Merch issues, Public schedule | Cannot view phone, email, medical notes, audit logs, or director control inbox. |
| **viewer** | Read-only general statistics, event schedule, venues | All sensitive participant fields are masked. Restricted from financial or administrative queries. |

If a user asks for information outside their role scope (e.g. a `volunteer` asking for the director's attention inbox), the chatbot politely refuses with an informative authorization notice without leaking whether specific private records exist.

---

## 4. Configuration & Environment Variables

Configure the AI assistant in `backend/.env` (refer to `backend/.env.example`):

```bash
# Enable or disable AI assistant operations (true/false)
FESTOS_AI_ENABLED=true

# LLM Provider: openai_compatible (works with OpenAI, Groq, Ollama, vLLM, LMStudio, etc.)
FESTOS_LLM_PROVIDER=openai_compatible
FESTOS_LLM_API_KEY=your-api-key-here
FESTOS_LLM_BASE_URL=https://api.openai.com/v1
FESTOS_LLM_MODEL=gpt-4o-mini

# Embedding Provider: local (offline, zero-cost, no API key needed) or openai_compatible
FESTOS_EMBEDDING_PROVIDER=local
FESTOS_EMBEDDING_MODEL=text-embedding-3-small

# Persistent vector store path
FESTOS_VECTOR_STORE_PATH=./data/festos_vectors.json
```

> **Zero-Cost Startup:** When `FESTOS_LLM_API_KEY` is omitted, the assistant seamlessly runs in deterministic fallback mode, using direct queries and pure engine calculations with zero external API calls or billing costs.

---

## 5. API Endpoints

All endpoints live under `/chatbot`:

### 1. `GET /chatbot/health`
Returns system status without exposing secret keys:
```json
{
  "status": "ok",
  "ai_enabled": true,
  "provider": "openai_compatible",
  "model": "gpt-4o-mini",
  "embedding_provider": "local",
  "vector_store_chunks": 81,
  "deterministic_fallback_available": true
}
```

### 2. `POST /chatbot/chat`
Ask questions grounded in the database:
- **Request:**
  ```json
  {
    "message": "How many active participants are registered?",
    "conversation_id": null
  }
  ```
- **Response:**
  ```json
  {
    "answer": "The database currently records 2836 total participant rows. Of these, 2831 are active...",
    "conversation_id": "conv_9fc7f3d52b6d",
    "sources": [
      {
        "type": "database_query",
        "label": "Participant Status Summary",
        "module": "participants",
        "detail": {
          "total_registered_rows": 2836,
          "active_participants": 2831,
          "gap_vs_expected": 431
        }
      }
    ],
    "confidence": "high",
    "follow_up_questions": [
      "Are there duplicate participant records?",
      "Which participant records require reconciliation?",
      "Find participants belonging to contingent C01."
    ]
  }
  ```

### 3. `GET /chatbot/conversations`
List previous conversations owned by the authenticated user.

### 4. `GET /chatbot/conversations/{conversation_id}`
Retrieve a specific conversation history. Strictly ownership-checked (returns 404 if accessed by another user).

### 5. `POST /chatbot/reindex`
Refreshes the semantic index from `docs/ASSUMPTIONS.md` and `README.md`. Restricted to `director` role.

---

## 6. Frontend Integration

The frontend UI components are built in React + TypeScript + TailwindCSS, fully styled to match the Aarohan Indian street poster theme:

- **`ChatbotLauncher`**: Positioned both in the application header and as an accessible floating pill at bottom-right (`Ask FestOS AI`).
- **`ChatbotPanel`**: Slide-over responsive drawer with conversation switching, status badge, suggested questions, and message stream.
- **`ChatMessageItem`**: Renders distinct user and assistant speech blocks, confidence indicators, and interactive source references.
- **`SourceReferences`**: Expandable inspection panel showing verified database queries, rule citations, and calculation metadata.
- **`SuggestedQuestions`**: Clickable starter questions triggering real operational queries.
- **`ChatInput`**: Multi-line expandable input supporting Enter-to-send and Shift+Enter for newlines.

---

## 7. Automated Testing & Verification

Run the test suite:
```bash
cd backend
python -m pytest tests/test_chatbot.py -v
```

Tests cover:
- Health endpoint status and secret redaction
- Bearer token authentication enforcement
- Empty and invalid message handling
- Exact participant count grounding
- Reconciliation funnel numbers
- Duplicate participant linking
- Role-based field masking on contingent members
- Accommodation capacity and shortage retrieval
- Scheduling conflict checks via pure scheduler engine
- Inventory stock and merch shortfall calculations
- Vendor compliance and dietary coverage
- Role-based permission denial without data leaks
- Move-event workflow guidance without database writes
- Prompt-injection resistance
- SQL-injection safety via parameterized ORM
- Conversation ownership isolation between users
- Multi-turn contextual follow-up questions
- Provider failure graceful fallback to deterministic answers
- Director-only reindexing authorization

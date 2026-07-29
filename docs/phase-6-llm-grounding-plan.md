# Phase 6 Plan: LLM Orchestration, Grounding, and Citations

Goal: replace the Phase 3 stub assistant flow with a grounded PydanticAI-backed assistant that answers only from retrieved corpus evidence and persists normalized citations.

This plan assumes Phase 5 retrieval is complete and continues using RRF-only retrieval (no reranker).

## Success criteria

- `POST /chat/stream` runs a real assistant turn through PydanticAI instead of stub text.
- Assistant output is grounded in retrieved passages from `app/retrieval/*`.
- Every factual answer contains citations that map to retrieved passages.
- If evidence is insufficient, assistant returns a controlled refusal.
- User + assistant messages and normalized citation rows are persisted atomically.
- Unit tests cover grounding invariants and insufficient-evidence behavior.

## Current baseline (from completed phases)

- Auth and thread ownership checks are implemented in `app/api/chat.py`.
- Stub streaming lifecycle is in `app/chat/orchestrator.py` + `app/chat/streaming.py`.
- Retrieval pipeline is available in `app/retrieval/` and includes neighbor context.
- Relevance/tuning notes exist in `docs/phase-5-retrieval-tuning-notes.md`.
- Semantic retrieval quality is currently constrained by OpenAI embedding quota availability.

## Scope

In scope:

- `app/assistant/instructions.md`
- `app/assistant/outputs.py`
- `app/assistant/deps.py`
- `app/assistant/agent.py`
- `app/grounding/validator.py`
- chat orchestrator wiring to retrieval + agent + persistence
- DB schema/model updates for citation persistence
- unit tests for grounding and refusal paths

Out of scope:

- frontend citation UX (Phase 7)
- reranker introduction
- non-corpus external tools/data

## Implementation plan

### 1. Add assistant contract and typed outputs

Create `backend/app/assistant/instructions.md` with product constraints:

- answer only from provided retrieved passages
- cite every factual claim
- refuse when evidence is insufficient
- no stock recommendations / no external facts

Create `backend/app/assistant/outputs.py`:

- `Citation`: `chunk_id`, `document_id`, optional `quote`, optional `page_number`
- `SourcePassage`: retrieval metadata echoed back for transparency
- `GroundedAnswer`: `answer_text`, `citations`, `insufficient_evidence`, optional `refusal_reason`

Design note:

- Keep output schema strict and small; avoid free-form nested structures that are hard to validate.

### 2. Define runtime dependency container

Create `backend/app/assistant/deps.py` with a dataclass (or pydantic model) holding:

- `user_id`
- `thread_id`
- `retriever` (Phase 5 `RetrieverProtocol`)
- `grounding_validator`
- optional model/runtime config knobs

This keeps orchestration explicit and testable.

### 3. Implement PydanticAI agent boundary

Create `backend/app/assistant/agent.py`:

- construct `Agent` with configured chat model (`settings.chat_model`)
- attach instructions from `assistant/instructions.md`
- define bounded retrieval tool(s), such as:
- `search_passages(query: str) -> list[SourcePassage]`

Suggested turn flow inside agent wrapper:

1. retrieve passages for user query
2. pass top passages as context/tool output
3. produce `GroundedAnswer` typed output

Guardrails:

- no unconstrained tool set
- no direct SQL generation by model
- no external web/search tools

### 4. Grounding validator and invariants

Create `backend/app/grounding/validator.py` enforcing:

1. If `insufficient_evidence == False`, at least one citation is required.
2. Each citation `chunk_id` must be present in retrieval results for that turn.
3. Citation/document consistency must hold (`chunk -> document`).
4. Citation count must be bounded (to prevent noise/abuse).
5. If validation fails, convert to controlled failure/refusal event.

Validation output should be a normalized, persistence-ready citation set.

### 5. Database updates for citation persistence

Add new SQLAlchemy model under `app/database/models/`:

- `message_citations` table with fields:
- `id` UUID PK
- `message_id` FK -> `chat_messages.id` (cascade delete)
- `chunk_id` FK -> `document_chunks.id`
- `source_document_id` FK -> `source_documents.id`
- `quote` TEXT nullable
- `page_number` INT nullable
- `created_at` timestamptz

Migration tasks:

- Alembic revision for `message_citations`
- indexes on `message_id`, `chunk_id`, `source_document_id`

Update DB helpers in `app/database/chats.py`:

- add helper to persist assistant turn and citations in one transaction
- return persisted assistant message + citation ids for logging/debug

### 6. Orchestrator integration

Refactor `app/chat/orchestrator.py`:

- replace `stream_stub_turn(...)` lifecycle with `stream_grounded_turn(...)`
- keep streaming shape compatible with existing AI SDK event stream

Execution outline:

1. extract latest user text (existing behavior)
2. run retriever
3. invoke PydanticAI agent with retrieval context
4. validate output via grounding validator
5. stream assistant text deltas
6. persist user message, assistant message, and citations atomically

Failure behavior:

- retrieval failure -> backend error event
- invalid grounding output -> controlled refusal text + no unsupported claims
- persistence failure after generation -> fail request (no partial citation writes)

### 7. Route wiring

Update `app/api/chat.py`:

- keep route contracts stable (`POST /chat/stream` remains)
- swap orchestrator call from stub to grounded flow
- preserve auth/thread ownership checks as-is

### 8. Testing plan

Add `backend/tests/assistant/`:

- `test_outputs.py` for schema constraints
- `test_agent.py` with model call mocked; verify structured output handling

Add `backend/tests/grounding/`:

- `test_validator.py`:
- citation-required rule
- citations must come from retrieved set
- refusal allowed without citations

Extend `backend/tests/chat/test_chat_stream_api.py`:

- successful grounded stream persists messages + citations
- insufficient-evidence stream persists refusal-style assistant message
- invalid citations from mocked agent are rejected/normalized

Optional integration test marker:

- live OpenAI + Supabase turn with one known question and citation persistence assertion

## Suggested execution order

1. Create `assistant/` and `grounding/` modules (`instructions`, `outputs`, `deps`, `validator`).
2. Add `message_citations` model + migration.
3. Add DB persistence helpers for citations.
4. Implement `assistant/agent.py` wrapper with mocked-first tests.
5. Refactor orchestrator to grounded flow.
6. Wire API route to new orchestrator function.
7. Run unit tests, then optional integration test.

## Deliverables checklist

- [ ] `backend/app/assistant/instructions.md`
- [ ] `backend/app/assistant/outputs.py`
- [ ] `backend/app/assistant/deps.py`
- [ ] `backend/app/assistant/agent.py`
- [ ] `backend/app/grounding/validator.py`
- [ ] `backend/app/database/models/message_citation.py`
- [ ] Alembic migration for `message_citations`
- [ ] `backend/app/database/chats.py` citation persistence helpers
- [ ] `backend/app/chat/orchestrator.py` grounded orchestration
- [ ] tests for assistant/grounding/orchestrator integration

## Risks and mitigations

- Embedding quota unavailable: retrieval may fall back to lexical-only quality.
- Mitigation: complete semantic re-check once quota is restored; keep refusal behavior strict.

- Model returns malformed citations.
- Mitigation: strict typed output + grounding validator gate before persistence.

- Streaming regressions with AI SDK wire format.
- Mitigation: keep existing stream event writer and add regression test in `tests/chat/test_streaming.py`.

## What you may need to provide

- Valid OpenAI quota/key for hybrid retrieval + generation tests.
- Confirmation on citation payload shape desired by Phase 7 UI (`quote` required vs optional).
- Decision on refusal copy style for insufficient evidence (short vs detailed).

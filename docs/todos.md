# Document Copilot — implementation checklist

Work top-to-bottom. Each phase ends with something you can run or verify before moving on.

Strategy: build vertical slices early. Phase 3 is the end-to-end stub chat milestone (auth + thread CRUD + streaming stub) before retrieval and grounding.

Definition of done (client brief): 5 senior analysts use it for a week and report >=3 hours saved per analyst per week. Use the 10 example questions in `client-brief.md` as acceptance tests before pilot sign-off.

---

## Phase 1 — Prerequisites and project setup

- [X] Install toolchain: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, [pnpm](https://pnpm.io/)
- [X] Create Supabase project ([guide](guides/supabase-setup.md)); save URL, anon key, service role key, direct DB connection string
- [X] Create OpenAI API key
- [X] Edit `USER_AGENT` in `data/download.py` with your real email (SEC requirement)
- [X] Run `uv run data/download.py`; confirm 25 filings in `data/downloads/` with `manifest.json`
- [X] Copy env templates: `backend/.env.example` -> `backend/.env`, `frontend/.env.example` -> `frontend/.env`

---

## Phase 2 — Backend foundation and schema

Goal: FastAPI boots, Alembic owns schema, core tables exist.

- [X] Initialize backend dependencies ([guide](guides/backend-setup.md))
- [X] Create `app/main.py` with CORS and `GET /health`
- [X] Create `app/config.py` with validated settings and fail-fast required config
- [X] Initialize Alembic and wire metadata + `DATABASE_URL`
- [X] Create SQLAlchemy models for `users`, `source_documents`, `document_chunks`, `chat_threads`, `chat_messages`
- [X] Generate and review initial migration including `vector` extension and `VECTOR(1536)`
- [X] Apply migrations (`uv run alembic upgrade head`)
- [X] Verify backend boot and health endpoint

---

## Phase 3 — Vertical slice: auth + chat stub streaming (no retrieval yet)

Goal: authenticated user can create a thread, send a message, see streamed stub output, and reload persisted history.

### Backend API and persistence

- [X] `app/auth/dependencies.py` verifies `Authorization: Bearer <supabase_jwt>` and exposes current user
- [X] `app/database/session.py` database session dependency for request-scoped DB access
- [X] `app/database/chats.py` user-scoped thread and message CRUD helpers
- [X] `app/chat/messages.py` parses AI SDK-like message payloads and extracts user text
- [X] `app/api/chat.py` routes:
- [X] `GET /chat/threads` list user threads
- [X] `POST /chat/threads` create thread
- [X] `GET /chat/threads/{id}/messages` load thread history
- [X] `POST /chat/stream` accept AI SDK-like payload, stream stub assistant reply
- [X] Persist both user and assistant messages for each streamed turn
- [ ] `app/database/supabase.py` user-scoped + service-role client factories (optional for SQLAlchemy-first flow)
- [ ] `app/chat/streaming.py` AI SDK event writer module (currently inline streaming)
- [ ] `app/chat/orchestrator.py` turn lifecycle coordinator (deferred until retrieval/grounding phases)

### Frontend integration for the Phase 3 slice

- [X] `src/lib/env.ts` validate required frontend env vars
- [X] `src/lib/supabase.ts` browser Supabase client with persisted session
- [X] `src/lib/http.ts` fetch wrapper with bearer token injection, timeout handling, typed `ApiError`
- [X] `src/lib/api.ts` thread list/create/history and stream helpers
- [X] React Router routes: `/login`, `/chat`, `/chat/:threadId`
- [X] Protected route behavior for unauthenticated users
- [X] Login/sign-up flow and sign-out shell
- [X] Thread sidebar and past conversation list
- [X] New thread action + route to active thread
- [X] Basic message list + input composer
- [X] Streaming indicator while assistant response is in flight
- [X] Load message history from `GET /chat/threads/{id}/messages`
- [X] `pnpm tsc --noEmit` and `pnpm lint` clean
- [ ] Replace custom stream client with AI SDK `useChat` + `DefaultChatTransport`
- [ ] Validate AI SDK wire format compatibility end-to-end

### Phase 3 verification checklist

- [ ] Verify with token + API client: create thread -> send message -> receive streamed stub -> messages persisted
- [ ] Browser verify loop: sign in -> create thread -> send -> stream observed -> reload -> history intact

---

## Phase 4 — Corpus ingestion pipeline

Goal: sample corpus is parsed, chunked, embedded, and stored.

- [X] Create ingestion module reading `data/downloads/manifest.json`
- [X] Parse SEC HTML into normalized markdown and metadata
- [X] Chunk filings into retrieval-sized passages with chunk metadata
- [X] Generate embeddings and store `vector(1536)`
- [X] Persist documents and chunks
- [X] Populate full-text `tsvector`
- [X] Ingest full sample corpus (~25 filings)
- [X] Smoke test document/chunk counts and non-null embeddings
- [X] Unit tests for chunking, metadata extraction, idempotent re-ingest

---

## Phase 5 — Retrieval layer (hybrid search)

Goal: given a query, return ranked source passages without LLM generation.

- [ ] `app/retrieval/queries.py` semantic search over embeddings (pgvector)
- [ ] `app/retrieval/queries.py` lexical search over `search_vector` (Postgres FTS)
- [ ] `app/retrieval/fusion.py` reciprocal rank fusion
- [ ] `app/retrieval/retriever.py` orchestrate embed -> dual search -> fuse -> neighbor fetch
- [ ] `app/database/documents.py` typed chunk/document lookup helpers
- [ ] Unit tests for fusion and retriever ranking behavior
- [ ] Manual relevance checks with client-brief questions

---

## Phase 6 — LLM orchestration, grounding, and citations

Goal: grounded answers only, with enforced citation policy.

- [ ] `app/assistant/instructions.md` product contract (cite all facts, refuse without evidence, no stock picks)
- [ ] `app/assistant/outputs.py` typed `GroundedAnswer`, `Citation`, `SourcePassage`
- [ ] `app/assistant/deps.py` runtime dependency dataclass
- [ ] `app/assistant/agent.py` PydanticAI agent with bounded retrieval tools
- [ ] Wire orchestrator to retrieval + agent + persistence
- [ ] `app/grounding/validator.py` enforce citation invariants and failure behavior
- [ ] Persist `message_citations` with assistant messages
- [ ] Unit tests for grounding and insufficient-evidence paths
- [ ] Integration test against live OpenAI + Supabase

---

## Phase 7 — Frontend AI SDK and citations UX

Goal: move frontend streaming to AI SDK primitives and display citation-first answer UX.

- [ ] Add AI SDK UI packages and switch to `useChat` + `DefaultChatTransport`
- [ ] Keep thread sidebar and message history pre-load integrated with AI SDK in-flight state
- [ ] Add citation chips (company, filing, date, page/section)
- [ ] Add expandable source passage excerpts for one-click verification
- [ ] Add grounding-specific error states (401, network, validation failure)
- [ ] Verify full loop with cited answers and reload-safe history

---

## Phase 8 — Deployment and pilot readiness

Goal: production deployment on Railway + Supabase and pilot execution.

- [ ] Deploy backend service (Uvicorn) with production env vars
- [ ] Deploy frontend static build with production `VITE_*` vars
- [ ] Confirm backend CORS includes production frontend origin
- [ ] Confirm Supabase Auth redirect URLs include production frontend origin
- [ ] Re-run ingestion against production Supabase (or migrate data)
- [ ] Production smoke test: auth, chat, citations, source passage display
- [ ] Prepare pilot feedback loop for the 10 analyst questions

---

## Phase 9 — Acceptance gate and hardening

Goal: pass pilot criteria and finalize operational quality.

- [ ] Pilot gate: each of the 10 example questions yields cited, verifiable answers or explicit insufficient-evidence refusal
- [ ] Analysts can sign in with Driftwood email and view only their own thread history
- [ ] No stock picks, no external-data leakage, no hallucinated factual claims
- [ ] Add README "Running locally" section with exact commands
- [ ] Add structured JSON logging (`structlog`) for Railway log drains
- [ ] Optional: thread title generation from first user message
- [ ] Optional: basic rate limiting/abuse protection for `/chat/stream`

---

## Dependency map (9-phase vertical slice)

```text
Phase 1 (prereqs)
    -> Phase 2 (backend + schema)
    -> Phase 3 (auth + chat stub vertical slice)
    -> Phase 4 (ingestion)
    -> Phase 5 (retrieval)
    -> Phase 6 (LLM + grounding)
    -> Phase 7 (AI SDK + citations UX)
    -> Phase 8 (deploy)
    -> Phase 9 (acceptance + hardening)
```

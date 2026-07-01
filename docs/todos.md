# Document Copilot — implementation checklist

Work top-to-bottom. Each phase ends with something you can run or verify before moving on.

**Strategy:** Backend-first foundation (schema → corpus → retrieval → chat API), then frontend wired to real endpoints, then deploy. The trust contract — citations, grounding, refusal — lives in the backend; build that before polishing UI.

**Definition of done (client brief):** 5 senior analysts use it for a week and report ≥3 hours saved per analyst per week. Use the [10 example questions](client-brief.md#example-analyst-questions) as your acceptance test before the pilot.

---

## Phase 0 — Prerequisites & corpus

- [X] Install toolchain: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, [pnpm](https://pnpm.io/)
- [X] Create Supabase project ([guide](guides/supabase-setup.md)) — save URL, anon key, service role key, direct DB connection string
- [X] Create OpenAI API key (needed from Phase 3 onward)
- [X] Edit `USER_AGENT` in `data/download.py` with your real email (SEC requirement)
- [X] Run `uv run data/download.py` — confirm 25 10-K filings (5 tickers × 5 years) land in `data/downloads/` with `manifest.json`
- [X] Copy env templates: `backend/.env.example` → `backend/.env`, `frontend/.env.example` → `frontend/.env`

---

## Phase 1 — Backend scaffold & database

Goal: FastAPI boots, Alembic owns schema, empty tables exist in Supabase.

- [X] Init backend deps ([guide](guides/backend-setup.md)):
  ```bash
  cd backend && uv sync
  uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector
  uv add --dev pytest ruff
  ```
- [X] Create `app/main.py` — FastAPI app, CORS from `ALLOWED_ORIGINS`, health route `GET /health`
- [X] Create `app/config.py` — pydantic-settings for all backend env vars; fail fast on missing required values
- [ ] Init Alembic: `uv run alembic init alembic`; wire `env.py` to import SQLAlchemy metadata + read `DATABASE_URL` from settings (direct/session connection, not pooler)
- [ ] Create `app/database/models.py` — SQLAlchemy models for:
  - [ ] `profiles` (user id from Supabase auth)
  - [ ] `source_documents` (filing metadata + normalized Markdown)
  - [ ] `document_chunks` (text, embedding, tsvector, metadata JSON)
  - [ ] `chat_threads`, `chat_messages`, `message_citations`
- [ ] Generate & review initial migration — explicitly add in migration file:
  - [ ] `create extension if not exists vector`
  - [ ] `vector(1536)` embedding column
  - [ ] generated `tsvector` column on chunks
  - [ ] HNSW index (vectors), GIN index (full-text + metadata)
  - [ ] RLS policies (users see only their own chats; corpus readable by authenticated users)
- [ ] Apply: `uv run alembic upgrade head`
- [ ] Verify: `uv run uvicorn app.main:app --reload` → `GET /health` returns OK

---

## Phase 2 — Ingestion pipeline

Goal: Sample corpus is parsed, chunked, embedded, and stored in Supabase.

- [ ] Create `backend/ingest/` module (or CLI script) that reads `data/downloads/manifest.json`
- [ ] **Parse:** SEC HTML → normalized Markdown per filing; extract metadata (ticker, company, filing type, fiscal year, accession number, source URL)
- [ ] **Chunk:** split Markdown into retrieval-sized passages; preserve page/section metadata and chunk index
- [ ] **Embed:** batch OpenAI embeddings (`text-embedding-3-small` or configured model); store `vector(1536)`
- [ ] **Persist:** upsert `source_documents` + `document_chunks` via service-role Supabase client or direct SQLAlchemy session
- [ ] **Full-text:** ensure generated `tsvector` is populated for each chunk
- [ ] Run ingestion against full sample corpus (~25 filings)
- [ ] Smoke test: query Supabase — confirm document count, chunk count, non-null embeddings
- [ ] Unit tests: chunking boundaries, metadata extraction, idempotent re-ingest

---

## Phase 3 — Retrieval layer

Goal: Given a query string, return ranked source passages with metadata — no LLM yet.

- [ ] `app/retrieval/queries.py` — semantic search SQL over `document_chunks.embedding` (pgvector cosine distance)
- [ ] `app/retrieval/queries.py` — lexical search SQL over `document_chunks.search_vector` (Postgres full-text)
- [ ] `app/retrieval/fusion.py` — Reciprocal Rank Fusion merging the two ranked lists
- [ ] `app/retrieval/retriever.py` — orchestrate embed query → dual search → fuse → fetch chunks + neighboring context
- [ ] `app/database/documents.py` — typed helpers for chunk/document lookups
- [ ] Unit tests: RRF fusion logic, retriever ranking with mocked DB results
- [ ] Manual test: run retriever against 2–3 questions from the client brief; inspect returned passages for relevance

---

## Phase 4 — Auth & chat API (stubbed assistant)

Goal: Authenticated users can create threads, send messages, and receive a streamed stub response persisted to DB.

- [ ] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>` via Supabase Auth; expose `get_current_user`
- [ ] `app/database/supabase.py` — user-scoped and service-role client factories
- [ ] `app/database/chats.py` — CRUD for threads, messages, citations (always scoped to `user_id`)
- [ ] `app/api/chat.py` routes:
  - [ ] `GET /chat/threads` — list user's threads
  - [ ] `POST /chat/threads` — create thread
  - [ ] `GET /chat/threads/{id}/messages` — message history
  - [ ] `POST /chat/stream` — accept AI SDK message format; return stub streamed text (no LLM yet)
- [ ] `app/chat/messages.py` — convert AI SDK wire format ↔ internal Pydantic models
- [ ] `app/chat/streaming.py` — emit AI SDK-compatible streaming events
- [ ] `app/chat/orchestrator.py` — turn lifecycle skeleton (retrieve → generate → validate → persist)
- [ ] Verify with curl/httpx: sign-in token → create thread → stream stub → messages persisted

---

## Phase 5 — LLM agent, grounding & real answers

Goal: Streaming answers are grounded in retrieved passages with enforced citations.

- [ ] `app/assistant/instructions.md` — product contract: cite everything, refuse when evidence missing, no stock picks
- [ ] `app/assistant/outputs.py` — `GroundedAnswer`, `Citation`, `SourcePassage` Pydantic models
- [ ] `app/assistant/deps.py` — `DocumentAgentDeps` dataclass (user, thread, retriever, validator)
- [ ] `app/assistant/agent.py` — PydanticAI agent with bounded tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [ ] Wire orchestrator: retrieve → agent run → stream text deltas + citation metadata parts
- [ ] `app/grounding/validator.py` — enforce invariants:
  - [ ] every factual answer has citations OR explicitly says insufficient evidence
  - [ ] every citation maps to a retrieved passage
  - [ ] model cannot cite documents not retrieved this turn
  - [ ] validation failure → controlled error, not a polished hallucination
- [ ] Persist final user message, assistant message, and `message_citations` after successful run
- [ ] Unit tests: citation validation, grounding enforcement, "insufficient evidence" path
- [ ] Integration test (marked `@pytest.mark.integration`): end-to-end turn against live OpenAI + Supabase
- [ ] Manual test: run all [10 example analyst questions](client-brief.md#example-analyst-questions); verify citations point to real passages

---

## Phase 6 — Frontend scaffold & auth

Goal: Analyst can sign in with email and see a shell app.

- [ ] Init frontend ([guide](guides/frontend-setup.md)):
  ```bash
  cd frontend && pnpm create vite . --template react-ts
  pnpm install && pnpm add react-router-dom @supabase/supabase-js
  pnpm add -D tailwindcss @tailwindcss/vite && pnpm dlx shadcn@latest init
  ```
- [ ] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [ ] `src/lib/supabase.ts` — browser Supabase client
- [ ] `src/lib/http.ts` — fetch wrapper with bearer token injection, timeouts, typed `ApiError`
- [ ] `src/lib/api.ts` — thread list/create, message history calls
- [ ] Auth pages: sign-in / sign-up (email only); redirect unauthenticated users
- [ ] App shell: layout, nav, sign-out; React Router routes
- [ ] Verify: sign up → sign in → session persists on refresh

---

## Phase 7 — Chat UI & citations

Goal: Full analyst workflow in the browser — ask questions, stream answers, click through to source passages.

- [ ] Add Vercel AI SDK UI packages; wire `useChat` with `DefaultChatTransport` pointing at `POST /chat/stream`
- [ ] `src/pages/chat/*` — thread list sidebar, active thread view, new chat action
- [ ] `src/components/chat/*`:
  - [ ] message list with streaming status
  - [ ] user input + submit
  - [ ] citation chips (company, filing, date, page/section)
  - [ ] expandable source passage excerpts (verify-in-one-click)
  - [ ] empty state for new threads
  - [ ] error states (401, network, grounding failure)
- [ ] Load initial messages from `GET /chat/threads/{id}/messages`; let AI SDK manage in-flight state
- [ ] Verify: full loop sign-in → new thread → ask question → streamed cited answer → reload → history intact
- [ ] `pnpm tsc --noEmit && pnpm lint` clean

---

## Phase 8 — Deploy & pilot readiness

Goal: Hosted on Railway; ready for the 5-analyst pilot week.

- [ ] Railway: deploy backend service (Uvicorn) with all env vars
- [ ] Railway: deploy frontend static build with `VITE_*` vars pointing at production backend + Supabase
- [ ] Confirm CORS `ALLOWED_ORIGINS` includes frontend URL
- [ ] Confirm Supabase Auth redirect URLs include production frontend origin
- [ ] Re-run ingestion against production Supabase (or migrate data)
- [ ] Smoke test production: auth, chat, citations, source passage display
- [ ] Prepare pilot feedback loop (which of the 10 example questions work well / fail?)
- [ ] **Pilot gate:** each of the 10 example questions returns cited, verifiable answers or an honest "not enough evidence" refusal

---

## Parallel work (optional)

These can happen alongside the main phases without blocking:

- [ ] README "Running locally" section with exact commands once Phases 1 + 6 are done
- [ ] `structlog` JSON logging in backend for Railway log drains
- [ ] Thread title auto-generation from first user message
- [ ] Rate limiting or basic abuse protection on `/chat/stream`

---

## Quick reference — dependency graph

```text
Phase 0 (corpus + keys)
    ↓
Phase 1 (schema) ──→ Phase 2 (ingest) ──→ Phase 3 (retrieval)
                                                    ↓
Phase 6 (frontend auth) ←── Phase 4 (auth + stub API) ←──┘
    ↓                              ↓
Phase 7 (chat UI) ←──────── Phase 5 (LLM + grounding)
    ↓
Phase 8 (deploy + pilot)
```

---

## Acceptance criteria checklist (client brief)

Before calling the project done:

- [ ] Analysts sign in with Driftwood email (Supabase email auth)
- [ ] Analysts ask plain-English questions about the curated 10-K corpus
- [ ] Every factual claim in an answer links to a specific filing + page/section
- [ ] Underlying passage is visible so the analyst can verify in one click
- [ ] Bot refuses to infer beyond the filings when evidence is insufficient (Q10 is the key test)
- [ ] Analysts see their own past conversations (per-user thread history)
- [ ] No stock picks, no external data, no hallucinated facts
- [ ] Runs on a small cloud footprint (Railway + Supabase, no infra team required)

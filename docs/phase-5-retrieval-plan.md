# Phase 5 Retrieval Plan (Hybrid Search)

Goal: implement a production-ready hybrid retrieval pipeline that returns ranked, grounded source passages from the SEC corpus using semantic search + Postgres full-text search, fused in Python.

This plan is Phase 5 only, but it deliberately defines interfaces that plug directly into PydanticAI in Phase 6.

## Success criteria

- Given a user query, backend returns ranked source passages with chunk text and document metadata.
- Retrieval combines both:
- pgvector semantic ranking over `document_chunks.embedding`
- Postgres full-text ranking over `document_chunks.search_vector`
- Final ranking uses Reciprocal Rank Fusion (RRF) in Python.
- Retrieval behavior is deterministic and covered by unit tests.
- Retrieval module exposes a clean service interface that can be injected into PydanticAI agent dependencies next phase.

## Scope for this phase

In scope:

- Build retrieval modules under `backend/app/retrieval/`
- Add typed lookup helpers under `backend/app/database/documents.py`
- Add unit tests for fusion and retriever orchestration
- Add manual relevance verification loop using questions from `docs/client-brief.md`

Out of scope:

- LLM answer generation
- citation extraction and validation
- assistant streaming changes beyond wiring to retrieval later

## Implementation shape

### 1. Retrieval query primitives

Create `backend/app/retrieval/queries.py` with two DB query functions:

1. `semantic_search(...)`
- Input: embedded query vector, optional filters, limit
- SQL shape: order by vector distance (`embedding <=> :query_embedding`)
- Returns ranked chunk candidates with score, rank, and chunk/document identifiers

2. `lexical_search(...)`
- Input: raw query string, optional filters, limit
- SQL shape: `search_vector @@ plainto_tsquery('english', :query)`
- Ranking: `ts_rank_cd(search_vector, plainto_tsquery(...))`
- Returns ranked chunk candidates with score, rank, and chunk/document identifiers

Notes:

- Keep both query functions side-effect free.
- Keep SQL explicit and parameterized.
- Exclude rows with null embeddings in semantic search.
- Keep lexical parser simple first (`plainto_tsquery`) and evaluate `websearch_to_tsquery` only if needed after baseline checks.

### 2. Typed retrieval records

Define retrieval domain models (either in `retrieval/retriever.py` or a small `retrieval/types.py`):

- `RetrievedCandidate`:
- `chunk_id: UUID`
- `source_document_id: UUID`
- `semantic_rank: int | None`
- `lexical_rank: int | None`
- `semantic_score: float | None`
- `lexical_score: float | None`
- `fused_score: float`

- `RetrievedPassage`:
- `chunk_id: str`
- `document_id: str`
- `content: str`
- `page_number: int | None`
- `ticker: str | None`
- `company_name: str | None`
- `filing_type: str | None`
- `filing_year: int | None`
- `filing_date: str | None`
- `accession_number: str | None`
- `source_url: str | None`
- `fused_score: float`

Use these as the retrieval contract that later maps directly to PydanticAI tool outputs.

### 3. Reciprocal Rank Fusion

Create `backend/app/retrieval/fusion.py`:

- Implement RRF:
- `rrf_score(doc) = Σ (1 / (k + rank_i))` across available rank lists
- Use configurable constant `k` (default 60)
- Fuse by `chunk_id`
- Preserve provenance (which list contributed)

Implementation constraints:

- No external dependency needed.
- Stable sorting for tie cases (secondary key: best individual rank, then deterministic UUID string).

### 4. Document lookup helpers

Create `backend/app/database/documents.py`:

- `get_chunks_by_ids(db, chunk_ids)` returns chunk rows in a caller-specified order
- `get_documents_by_ids(db, document_ids)` returns document metadata map
- Optional helper: `get_neighbor_chunks(db, source_document_id, chunk_id, window=1)` for Phase 6 grounding context

Why here:

- Keeps retrieval SQL focused on ranking.
- Keeps chunk/document hydration reusable for retrieval and assistant orchestration.

### 5. Retriever orchestration

Create `backend/app/retrieval/retriever.py` with a class like `HybridRetriever`:

- Dependencies:
- DB session
- embedding function (OpenAI-backed callable injected from composition layer)
- retrieval settings (`semantic_limit`, `lexical_limit`, `final_limit`, `rrf_k`)

- Main method:
- `retrieve(query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]`

Flow:

1. Embed user query.
2. Run semantic and lexical search independently.
3. Fuse ranked candidates with RRF.
4. Truncate to `final_limit`.
5. Hydrate top chunk content + source document metadata via `database/documents.py`.
6. Return typed `RetrievedPassage` list.

Failure behavior:

- Embedding failure bubbles as retriever error (handled later in API/orchestrator layer).
- Empty result is valid and returns `[]`.

### 6. PydanticAI integration boundary (Phase 5 prep)

Even though full agent orchestration is Phase 6, define retrieval with PydanticAI in mind now.

Prepare:

- `HybridRetriever` as a plain injected dependency (no globals).
- Return pydantic-friendly models (or dataclasses trivially convertible to pydantic models).
- Add a lightweight protocol interface for future agent deps:
- `class RetrieverProtocol(Protocol):`
- `async def retrieve(self, query: str, *, filters: RetrievalFilters | None = None) -> list[RetrievedPassage]: ...`

This allows `assistant/deps.py` in Phase 6 to accept the retriever without refactoring query/fusion internals.

### 7. API/dev verification hook

For fast validation in Phase 5, add one minimal non-user-facing verification path (pick one):

Option A:

- Add a temporary internal-only endpoint (guarded in dev) that accepts query and returns retrieval passages.

Option B:

- Add a CLI/test harness script in `backend/` that runs retrieval for a query and prints top passages.

Preferred here: Option B to avoid premature API surface changes.

## SQL and indexing checklist

Confirm migration state supports retrieval performance:

- `document_chunks.embedding` exists as `vector(1536)`
- `document_chunks.search_vector` exists and is populated by ingestion
- `document_chunks.search_vector` has GIN index (if current index is btree/default, add follow-up migration)
- vector index strategy verified (HNSW or IVFFlat) based on corpus size and Supabase support

Important:

- Postgres full-text should use a GIN index on `search_vector` for realistic query performance.
- If current migration created a plain index, create a corrective migration in this phase.

## Testing plan

### Unit tests

Add `backend/tests/retrieval/`:

- `test_fusion.py`
- validates RRF score math
- validates tie-break determinism
- validates single-list and dual-list behavior

- `test_retriever.py`
- mocks embedder and DB query functions
- verifies orchestration order: embed -> dual query -> fuse -> hydrate
- verifies empty-result behavior
- verifies final limit truncation and ordering

- `test_queries.py` (optional unit-level SQL shape checks)
- verify query builders apply expected filters and limits

### Integration/manual checks

- Run retrieval against local Supabase-backed dataset after ingestion.
- For each of the 10 questions in `docs/client-brief.md`, capture:
- top 5 fused passages
- whether passages appear relevant
- notes on false positives/negatives

Store findings as a short markdown report under `docs/` for tuning phase handoff.

## Suggested execution order

1. Create retrieval types + fusion module.
2. Add semantic and lexical query primitives.
3. Add document hydration helpers.
4. Implement `HybridRetriever` orchestration.
5. Add tests for fusion and retriever.
6. Run manual relevance loop and record tuning notes.
7. If needed, add migration to correct FTS/vector indexes.

## Deliverables checklist

- [ ] `backend/app/retrieval/queries.py`
- [ ] `backend/app/retrieval/fusion.py`
- [ ] `backend/app/retrieval/retriever.py`
- [ ] `backend/app/database/documents.py`
- [ ] `backend/tests/retrieval/test_fusion.py`
- [ ] `backend/tests/retrieval/test_retriever.py`
- [ ] optional index migration for FTS/vector performance
- [ ] retrieval relevance notes doc in `docs/`

## Definition of done for Phase 5

- Hybrid retrieval returns ranked passages using semantic + lexical + fused ranking.
- Tests pass for fusion math and retriever flow.
- Manual relevance check completed across client-brief sample questions.
- Interfaces are ready for direct injection into PydanticAI dependencies in Phase 6.

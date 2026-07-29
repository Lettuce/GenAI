# Retrieval Module

This module implements the Phase 5 hybrid retrieval pipeline for Document Copilot.

It combines:

- semantic search over pgvector embeddings
- lexical search over Postgres full-text search (`search_vector`)
- Reciprocal Rank Fusion (RRF) to merge ranked candidates
- passage hydration with source metadata and neighbor context

## File map

- `types.py`: shared retrieval dataclasses and protocol contracts
- `embeddings.py`: query embedding client + embedding call
- `queries.py`: semantic and lexical search query functions
- `fusion.py`: RRF scoring and ranked list fusion
- `passages.py`: hydrates fused chunk ids into rich `RetrievedPassage` objects
- `retriever.py`: `HybridRetriever` orchestration entry point

## Default settings

### `HybridRetriever` defaults (`retriever.py`)

- `semantic_limit=30`
- `lexical_limit=30`
- `final_limit=8`
- `rrf_k=60`
- `neighbor_window=1`

### Phase 6 settings (`app/schemas/config.py`)

- `retrieval_top_k` (default `8`): target number of passages returned by retrieval.
- `rf_60` (default `60`): Reciprocal Rank Fusion constant (RRF K value).
- `grounding_threshold` (default `0.75`): minimum grounding score target for grounded answer acceptance.

### Embedding defaults (`embeddings.py` + `app/config.py`)

- model: `settings.embedding_model` (default `text-embedding-3-small`)
- dimensions: `settings.embedding_dimensions` (default `1536`)

### Fusion defaults (`fusion.py`)

- `DEFAULT_RRF_K=60`

### Lexical query defaults (`queries.py`)

- language config: `english`
- tokenization: alphanumeric keyword extraction
- keyword selection: 3 to 5 high-signal terms via `app.assistant.tools`
- stopword filtering: internal stopword set + conversational filler filtering
- max tokens used for FTS query: `5`
- query shape: OR-based `to_tsquery('english', 'term1 | term2 | ...')`

## Pipeline behavior

1. `HybridRetriever.retrieve(query)` receives the user query.
2. If `semantic_limit > 0`, the query is embedded via OpenAI.
3. Semantic candidates are fetched from `document_chunks.embedding` using cosine distance ordering.
4. Lexical candidates are fetched from `document_chunks.search_vector` using Postgres FTS ranking (`ts_rank_cd`).
5. Candidate lists are fused by chunk id using RRF.
6. Top fused candidates are truncated to `final_limit`.
7. Candidate chunk ids are hydrated into full passages + source metadata.
8. Neighbor passages are fetched per result using `neighbor_window`.
9. A list of typed `RetrievedPassage` objects is returned.

## Mermaid flow

```mermaid
flowchart LR
    Q([User query]) --> R[HybridRetriever.retrieve]

    subgraph BR[Candidate generation]
        direction TB
        GATE{semantic_limit > 0}

        subgraph SEM[Semantic branch]
            direction TB
            EMB[Embed query via OpenAI]
            VEC[semantic_search\npgvector cosine distance]
            EMB --> VEC
        end

        subgraph LEX[Lexical branch]
            direction TB
            FTS[lexical_search\nFTS to_tsquery + ts_rank_cd]
        end

        GATE -- yes --> EMB
        GATE -- no --> SKIP[Skip semantic branch]
    end

    R --> GATE
    R --> FTS

    VEC --> FUSE[RRF fusion]
    FTS --> FUSE
    SKIP -.-> FUSE

    subgraph HYD[Hydration and output]
        direction TB
        TOP[Take top N fused chunks\nfinal_limit]
        META[get_passage_rows\nchunk + document metadata]
        NB[get_neighbor_passage_rows\nneighbor_window]
        BUILD[build_passages]
        OUT([RetrievedPassage[]])

        TOP --> META
        TOP --> NB
        META --> BUILD
        NB --> BUILD
        BUILD --> OUT
    end

    FUSE --> TOP

    classDef entry fill:#f4f8ff,stroke:#4c6ef5,stroke-width:1.5px,color:#1c2b5a;
    classDef branch fill:#f8f9fa,stroke:#495057,stroke-width:1px,color:#212529;
    classDef core fill:#fff4e6,stroke:#f08c00,stroke-width:1.5px,color:#5f3b00;
    classDef output fill:#e6fcf5,stroke:#0ca678,stroke-width:1.5px,color:#0b462f;

    class Q,R entry;
    class EMB,VEC,FTS,GATE,SKIP,TOP,META,NB,BUILD branch;
    class FUSE core;
    class OUT output;
```

## Notes

- This module currently uses RRF-only fusion (no reranker).
- Retrieval quality is best when semantic embeddings are available.
- If semantic retrieval is disabled (`semantic_limit=0`), the pipeline still runs in lexical-only mode.

## Grounding model (Phase 6)

Grounding is defined as: every material claim in the final assistant response should be supported by one or more retrieved passages.

Current state in this codebase:

- Retrieval is fully implemented and returns typed `RetrievedPassage` objects with metadata and neighbor context.
- A configurable `grounding_threshold` exists in settings.
- A dedicated grounding validator/scorer is not yet implemented in `app/retrieval` or `app/chat`.

Practical implication:

- Today, retrieval can provide evidence candidates, but final answer validation against a numeric grounding score is not enforced in code yet.

Recommended validation flow for implementation:

1. Generate draft answer from retrieved context.
2. Split draft into atomic claims.
3. For each claim, compute support against top passages (semantic overlap, exact span match, or citation alignment).
4. Aggregate claim support into a grounding score in $[0, 1]$.
5. If score is below `grounding_threshold`, either:
    - ask retrieval for broader context, or
    - return a constrained response that explicitly states insufficient evidence.

Suggested score shape:

$$
grounding\_score = \frac{\sum_{i=1}^{n} w_i \cdot supported_i}{\sum_{i=1}^{n} w_i}
$$

Where $supported_i \in \{0, 1\}$ for each claim and $w_i$ is optional claim importance.

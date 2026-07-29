# Phase 5 Retrieval Tuning Notes

Date: 2026-07-29

## Scope

This note captures tuning observations from the Phase 5 retrieval implementation using:

- HybridRetriever with RRF-only fusion (no reranker)
- Postgres full-text search (FTS)
- pgvector semantic search path (when embeddings are available)

## Exact 10 client-brief questions

Source: docs/client-brief.md

1. Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change, and which category appears to have contributed most to any mix shift?
2. For Amazon, compare AWS operating income and margin against North America and International from 2021-2025. In which years did AWS appear to fund losses or weaker profitability elsewhere?
3. How did NVIDIA describe demand drivers, customer concentration, and supply constraints for its Data Center business from fiscal 2021 through fiscal 2025?
4. Across Microsoft's 2021-2025 filings, what changed in the way the company describes Azure, AI infrastructure, and cloud capacity constraints?
5. For Alphabet, how did Google Search, YouTube ads, Google Network, subscriptions/platforms/devices, and Google Cloud revenue trends differ across the available 10-Ks?
6. Which of the five companies added, removed, or materially changed risk-factor language related to AI, cloud infrastructure, export controls, supply chain concentration, or regulation between 2021 and 2025?
7. For Apple and NVIDIA, what do the filings say about supplier concentration or dependence on third-party manufacturing, and did the wording become more or less urgent over time?
8. Compare capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and timing of AI/cloud infrastructure investment?
9. For each company, summarize the most important geographic revenue exposures disclosed in the latest 10-K, then identify any year-over-year changes that could matter to an analyst.
10. If an analyst asks whether the filings prove that generative AI improved margins for any of these companies, what evidence exists in the corpus, and where should the bot refuse to infer beyond the filings?

## Data readiness checks

Observed in database:

- source_documents: 25
- document_chunks: 1575
- chunks_with_embedding: 1575
- chunks_with_search_vector: 1575
- lexical_revenue_hits: 436

Conclusion: corpus ingestion and FTS vector population are present.

## Retrieval run summary

Run artifact: docs/phase-5-relevance-report.md

Runtime condition:

- OpenAI embeddings returned quota error (429 insufficient_quota)
- Harness switched to lexical-only fallback for this run

Behavior observed:

- After lexical query tuning, all 10 questions returned top-5 passages
- Precision was poor for cross-company prompts (many top hits concentrated in Microsoft filings)

Interpretation:

- Recall improved after FTS query broadening
- Precision remains weak without semantic embeddings and without query-time company/entity filtering

## Tuning change applied

In app/retrieval/queries.py:

- Replaced strict FTS parsing with safe OR-keyword tsquery generation
- Approach: extract normalized keyword tokens and build `to_tsquery('english', 'token1 | token2 | ...')`

Impact:

- Eliminated zero-result failure mode for long natural-language analyst prompts
- Increased candidate recall significantly

## Remaining tuning opportunities

1. Re-run with real semantic embeddings once OpenAI quota is restored.
2. Add lightweight query-entity filtering (ticker/company extraction) to narrow lexical candidates.
3. Add lexical query weighting for domain terms (for example: segment names, filing section terms).
4. Consider minimum lexical score threshold to remove generic filing boilerplate chunks.
5. Re-balance semantic and lexical candidate limits after semantic path is available again.

## User action required

1. Restore OpenAI API quota/billing so semantic retrieval can run in normal hybrid mode.
2. Re-run:

   `uv run python scripts/run_phase5_relevance_checks.py`

3. Review the updated `docs/phase-5-relevance-report.md` and confirm relevance quality before Phase 6 integration.

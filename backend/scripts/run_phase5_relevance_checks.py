from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from openai import RateLimitError

from app.database.session import SessionLocal
from app.retrieval.retriever import HybridRetriever

QUESTIONS = [
    "Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change, and which category appears to have contributed most to any mix shift?",
    "For Amazon, compare AWS operating income and margin against North America and International from 2021-2025. In which years did AWS appear to fund losses or weaker profitability elsewhere?",
    "How did NVIDIA describe demand drivers, customer concentration, and supply constraints for its Data Center business from fiscal 2021 through fiscal 2025?",
    "Across Microsoft's 2021-2025 filings, what changed in the way the company describes Azure, AI infrastructure, and cloud capacity constraints?",
    "For Alphabet, how did Google Search, YouTube ads, Google Network, subscriptions/platforms/devices, and Google Cloud revenue trends differ across the available 10-Ks?",
    "Which of the five companies added, removed, or materially changed risk-factor language related to AI, cloud infrastructure, export controls, supply chain concentration, or regulation between 2021 and 2025?",
    "For Apple and NVIDIA, what do the filings say about supplier concentration or dependence on third-party manufacturing, and did the wording become more or less urgent over time?",
    "Compare capital expenditures and purchase commitments for Microsoft, Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and timing of AI/cloud infrastructure investment?",
    "For each company, summarize the most important geographic revenue exposures disclosed in the latest 10-K, then identify any year-over-year changes that could matter to an analyst.",
    "If an analyst asks whether the filings prove that generative AI improved margins for any of these companies, what evidence exists in the corpus, and where should the bot refuse to infer beyond the filings?",
]


def _truncate(text: str, *, limit: int = 220) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def main() -> None:
    report_path = Path(__file__).resolve().parents[2] / "docs" / "phase-5-relevance-report.md"

    with SessionLocal() as db:
        retriever = HybridRetriever(db, semantic_limit=40, lexical_limit=40, rrf_k=60, neighbor_window=1)
        fallback_mode = False

        lines: list[str] = []
        lines.append("# Phase 5 Retrieval Relevance Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
        lines.append("")
        lines.append("Configuration:")
        lines.append("- semantic_limit=40")
        lines.append("- lexical_limit=40")
        lines.append("- final_limit=unlimited (all fused candidates from the configured search windows)")
        lines.append("- rrf_k=60")
        lines.append("- neighbor_window=1")
        lines.append("")

        for index, question in enumerate(QUESTIONS, start=1):
            try:
                passages = retriever.retrieve(question)
            except RateLimitError:
                if not fallback_mode:
                    retriever = HybridRetriever(
                        db,
                        semantic_limit=0,
                        lexical_limit=40,
                        rrf_k=60,
                        neighbor_window=1,
                    )
                    fallback_mode = True
                    lines.append("## Runtime Note")
                    lines.append("OpenAI embedding quota was unavailable during this run.")
                    lines.append("Switched to lexical-only fallback (semantic_limit=0) to complete manual retrieval checks.")
                    lines.append("")
                passages = retriever.retrieve(question)

            lines.append(f"## Q{index}")
            lines.append(question)
            lines.append("")
            lines.append(f"Top passages returned: {len(passages)}")

            if not passages:
                lines.append("- No passages returned")
                lines.append("")
                continue

            for rank, passage in enumerate(passages, start=1):
                heading_bits = [
                    f"{rank}.",
                    passage.ticker or "unknown-ticker",
                    passage.filing_type or "unknown-filing",
                    str(passage.filing_year) if passage.filing_year is not None else "unknown-year",
                    f"score={passage.fused_score:.6f}",
                ]
                lines.append("- " + " | ".join(heading_bits))
                lines.append(f"  accession={passage.accession_number or 'n/a'}")
                lines.append(f"  page={passage.page_number if passage.page_number is not None else 'n/a'}")
                lines.append(f"  excerpt={_truncate(passage.content)}")
                if passage.neighbor_passages:
                    neighbor_excerpt = _truncate(passage.neighbor_passages[0].content)
                    lines.append(
                        f"  neighbor_excerpt={neighbor_excerpt}"
                    )
            lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote relevance report to {report_path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.assistant.agent import GroundedAssistantAgent
from app.assistant.deps import AssistantRuntimeDeps
from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.chat.streaming import iter_ai_sdk_data_stream_events
from app.database import chats
from app.database.chats import CitationWrite
from app.grounding.validator import GroundingValidationError, GroundingValidator
from app.retrieval.retriever import HybridRetriever


def _fallback_refusal(reason: str) -> GroundedAnswer:
    return GroundedAnswer(
        answer_text="I do not have enough evidence in the retrieved filings to answer this safely.",
        citations=[],
        insufficient_evidence=True,
        refusal_reason=reason,
    )


def _format_sectioned_answer(*, user_text: str, answer: GroundedAnswer, retrieved_passages: list[SourcePassage]) -> str:
    analyzed = user_text.strip() or "No query text was provided."

    sources = [
        f"{passage.company_name or passage.ticker or 'Unknown issuer'} - "
        f"{passage.filing_type or 'Filing'} {passage.filing_year or ''}".strip()
        for passage in retrieved_passages[:3]
    ]
    searching = "\n".join(f"- {source}" for source in sources) if sources else "- No relevant filings found"

    reading_lines = []
    for passage in retrieved_passages[:2]:
        snippet = passage.content.replace("\n", " ").strip()[:220]
        reading_lines.append(f"- {snippet}")
    reading = "\n".join(reading_lines) if reading_lines else "- No passage excerpts available"

    if answer.insufficient_evidence:
        verifying = "- Evidence is insufficient to produce a safe, grounded factual response"
    else:
        verifying = f"- Verified against {len(answer.citations)} citation(s) from this retrieval turn"

    answering = answer.answer_text.strip() or "No answer text generated."

    return (
        "Analyzing\n"
        f"- {analyzed}\n\n"
        "Searching\n"
        f"{searching}\n\n"
        "Reading\n"
        f"{reading}\n\n"
        "Verifying\n"
        f"{verifying}\n\n"
        "Answering\n"
        f"{answering}"
    )


def _recover_answer_with_retrieved_citations(
    *,
    answer: GroundedAnswer,
    retrieved_passages: list[SourcePassage],
) -> GroundedAnswer:
    if answer.insufficient_evidence:
        return answer

    if answer.citations:
        return answer

    recovered_citations = [
        Citation(
            chunk_id=passage.chunk_id,
            document_id=passage.document_id,
            quote=passage.content[:320],
            page_number=passage.page_number,
        )
        for passage in retrieved_passages[:3]
    ]
    if not recovered_citations:
        return answer

    return GroundedAnswer(
        answer_text=answer.answer_text,
        citations=recovered_citations,
        insufficient_evidence=False,
        refusal_reason=None,
    )


def _citation_writes(answer: GroundedAnswer) -> list[CitationWrite]:
    citation_rows: list[CitationWrite] = []
    for citation in answer.citations:
        citation_rows.append(
            CitationWrite(
                chunk_id=uuid.UUID(citation.chunk_id),
                source_document_id=uuid.UUID(citation.document_id),
                quote=citation.quote,
                page_number=citation.page_number,
            )
        )
    return citation_rows


async def stream_grounded_turn(
    *,
    db: Session,
    thread_id: uuid.UUID,
    user_text: str,
    user_id: uuid.UUID,
) -> AsyncGenerator[str, None]:
    retriever = HybridRetriever(db)
    assistant_agent = GroundedAssistantAgent()
    validator = GroundingValidator()

    deps = AssistantRuntimeDeps(
        user_id=user_id,
        thread_id=thread_id,
        retriever=retriever,
        retrieval_query=user_text,
    )

    retrieved_passages: list[SourcePassage] = []
    try:
        retrieved_passages = assistant_agent.retrieve_passages(deps, user_text)
    except Exception as exc:  # Retrieval can fail due to transient DB/index issues.
        grounded = _fallback_refusal(f"Retrieval failed: {exc}")
    else:
        if not retrieved_passages:
            grounded = _fallback_refusal("No supporting passages were retrieved for this query.")
        else:
            try:
                raw_answer = assistant_agent.answer(
                    user_query=user_text,
                    deps=deps,
                    retrieved_passages=retrieved_passages,
                )
                raw_answer = await raw_answer
                grounded = validator.validate(answer=raw_answer, retrieved_passages=retrieved_passages)
            except GroundingValidationError as exc:
                recovered = _recover_answer_with_retrieved_citations(answer=raw_answer, retrieved_passages=retrieved_passages)
                try:
                    grounded = validator.validate(answer=recovered, retrieved_passages=retrieved_passages)
                except GroundingValidationError:
                    grounded = _fallback_refusal(f"Grounding validation failed: {exc}")
            except Exception as exc:  # Model/tool runtime errors should not produce uncited claims.
                grounded = _fallback_refusal(f"Assistant generation failed: {exc}")

    assistant_text = _format_sectioned_answer(
        user_text=user_text,
        answer=grounded,
        retrieved_passages=retrieved_passages,
    )

    async for event in iter_ai_sdk_data_stream_events(assistant_text):
        yield event

    try:
        citation_rows = _citation_writes(grounded)
    except Exception:
        citation_rows = []

    if citation_rows:
        try:
            chats.add_turn_with_citations(
                db,
                thread_id=thread_id,
                user_content=user_text,
                assistant_content=assistant_text,
                citations=citation_rows,
            )
            return
        except Exception:
            # Keep chat usable even if citation persistence is not available (e.g., missing migration).
            db.rollback()
            pass

    chats.add_turn_messages(
        db,
        thread_id=thread_id,
        user_content=user_text,
        assistant_content=assistant_text,
    )

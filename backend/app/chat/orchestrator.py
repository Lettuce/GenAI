from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.assistant.agent import GroundedAssistantAgent
from app.assistant.deps import AssistantRuntimeDeps
from app.assistant.outputs import GroundedAnswer, SourcePassage
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
                grounded = validator.validate(answer=raw_answer, retrieved_passages=retrieved_passages)
            except GroundingValidationError as exc:
                grounded = _fallback_refusal(f"Grounding validation failed: {exc}")
            except Exception as exc:  # Model/tool runtime errors should not produce uncited claims.
                grounded = _fallback_refusal(f"Assistant generation failed: {exc}")

    assistant_text = grounded.answer_text

    async for event in iter_ai_sdk_data_stream_events(assistant_text):
        yield event

    try:
        citation_rows = _citation_writes(grounded)
    except Exception:
        citation_rows = []

    if citation_rows:
        chats.add_turn_with_citations(
            db,
            thread_id=thread_id,
            user_content=user_text,
            assistant_content=assistant_text,
            citations=citation_rows,
        )
        return

    chats.add_turn_messages(
        db,
        thread_id=thread_id,
        user_content=user_text,
        assistant_content=assistant_text,
    )

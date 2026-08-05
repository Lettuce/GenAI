from __future__ import annotations

import uuid

from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.chat.orchestrator import _citation_writes, _citations_for_persistence


def _source_passage(*, chunk_id: str, document_id: str, content: str) -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        page_number=7,
        ticker='MSFT',
        company_name='Microsoft',
        filing_type='10-K',
        filing_year=2024,
        filing_date=None,
        accession_number=None,
        source_url='https://example.com/filing',
    )


def test_citations_for_persistence_includes_all_retrieved_passages() -> None:
    retrieved_chunk_a = str(uuid.uuid4())
    retrieved_chunk_b = str(uuid.uuid4())
    retrieved_document = str(uuid.uuid4())

    answer = GroundedAnswer(
        answer_text='Insufficient evidence summary.',
        citations=[],
        insufficient_evidence=True,
        refusal_reason='No evidence.',
    )

    citations = _citations_for_persistence(
        answer=answer,
        retrieved_passages=[
            _source_passage(chunk_id=retrieved_chunk_a, document_id=retrieved_document, content='A chunk excerpt'),
            _source_passage(chunk_id=retrieved_chunk_b, document_id=retrieved_document, content='B chunk excerpt'),
        ],
    )

    assert len(citations) == 2
    assert {citation.chunk_id for citation in citations} == {retrieved_chunk_a, retrieved_chunk_b}


def test_citation_writes_skips_invalid_ids_but_keeps_valid_rows() -> None:
    valid_chunk_id = str(uuid.uuid4())
    valid_document_id = str(uuid.uuid4())

    answer = GroundedAnswer(
        answer_text='Answer text',
        citations=[
            Citation(
                chunk_id=valid_chunk_id,
                document_id=valid_document_id,
                quote='valid citation',
                page_number=12,
            ),
            Citation(
                chunk_id='not-a-uuid',
                document_id=valid_document_id,
                quote='invalid citation',
                page_number=13,
            ),
        ],
        insufficient_evidence=False,
        refusal_reason=None,
    )

    rows = _citation_writes(answer)

    assert len(rows) == 1
    assert rows[0].chunk_id == uuid.UUID(valid_chunk_id)
    assert rows[0].source_document_id == uuid.UUID(valid_document_id)

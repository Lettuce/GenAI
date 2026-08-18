from __future__ import annotations

import uuid

from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.chat.orchestrator import (
    _citation_writes,
    _citations_for_persistence,
    _recover_answer_with_retrieved_citations,
    _select_relevant_passages,
)


def _source_passage(
    *,
    chunk_id: str,
    document_id: str,
    content: str,
    ticker: str | None = 'MSFT',
    company_name: str | None = 'Microsoft',
) -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk_id,
        document_id=document_id,
        content=content,
        page_number=7,
        ticker=ticker,
        company_name=company_name,
        filing_type='10-K',
        filing_year=2024,
        filing_date=None,
        accession_number=None,
        source_url='https://example.com/filing',
    )


def test_citations_for_persistence_uses_only_answer_citations() -> None:
    chunk_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    answer = GroundedAnswer(
        answer_text='Grounded answer.',
        citations=[
            Citation(
                chunk_id=chunk_id,
                document_id=document_id,
                quote='grounded citation',
                page_number=4,
            )
        ],
        insufficient_evidence=False,
        refusal_reason=None,
    )

    citations = _citations_for_persistence(answer=answer)

    assert len(citations) == 1
    assert citations[0].chunk_id == chunk_id
    assert citations[0].document_id == document_id


def test_recover_answer_with_retrieved_citations_prefers_query_relevant_passages() -> None:
    nvidia_chunk = str(uuid.uuid4())
    microsoft_chunk = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    recovered = _recover_answer_with_retrieved_citations(
        answer=GroundedAnswer(
            answer_text='NVIDIA summary.',
            citations=[],
            insufficient_evidence=False,
            refusal_reason=None,
        ),
        user_text='Summarize NVIDIA gross margin trends',
        retrieved_passages=[
            _source_passage(
                chunk_id=nvidia_chunk,
                document_id=document_id,
                content='NVIDIA gross margin expanded due to data center demand.',
            ),
            _source_passage(
                chunk_id=microsoft_chunk,
                document_id=document_id,
                content='Microsoft cloud demand remained strong year over year.',
            ),
        ],
    )

    assert len(recovered.citations) == 1
    assert recovered.citations[0].chunk_id == nvidia_chunk


def test_select_relevant_passages_keeps_more_than_three_results_across_companies() -> None:
    passages = [
        _source_passage(chunk_id=str(uuid.uuid4()), document_id='doc-nvda-1', content='NVIDIA operating margin improved in data center.', ticker='NVDA', company_name='NVIDIA'),
        _source_passage(chunk_id=str(uuid.uuid4()), document_id='doc-nvda-2', content='NVIDIA gross margin remains healthy in AI revenue.', ticker='NVDA', company_name='NVIDIA'),
        _source_passage(chunk_id=str(uuid.uuid4()), document_id='doc-nvda-3', content='NVIDIA supply chain costs remain elevated.', ticker='NVDA', company_name='NVIDIA'),
        _source_passage(chunk_id=str(uuid.uuid4()), document_id='doc-msft-1', content='Microsoft cloud services margin expanded across Azure.', ticker='MSFT', company_name='Microsoft'),
        _source_passage(chunk_id=str(uuid.uuid4()), document_id='doc-msft-2', content='Microsoft operating income grew on productivity and cloud demand.', ticker='MSFT', company_name='Microsoft'),
    ]

    selected = _select_relevant_passages(
        user_text='Compare Microsoft and NVIDIA operating margin trends across recent filings',
        retrieved_passages=passages,
        max_items=5,
    )

    assert len(selected) == 5
    assert {passage.company_name for passage in selected} == {'Microsoft', 'NVIDIA'}


def test_recover_answer_with_retrieved_citations_prefers_relevant_company_for_single_company_query() -> None:
    nvidia_chunk = str(uuid.uuid4())
    microsoft_chunk = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    recovered = _recover_answer_with_retrieved_citations(
        answer=GroundedAnswer(
            answer_text='NVIDIA summary.',
            citations=[],
            insufficient_evidence=False,
            refusal_reason=None,
        ),
        user_text='Summarize NVIDIA gross margin trends',
        retrieved_passages=[
            _source_passage(
                chunk_id=nvidia_chunk,
                document_id=document_id,
                content='NVIDIA gross margin expanded due to data center demand.',
                ticker='NVDA',
                company_name='NVIDIA',
            ),
            _source_passage(
                chunk_id=microsoft_chunk,
                document_id=document_id,
                content='Microsoft cloud demand remained strong year over year.',
                ticker='MSFT',
                company_name='Microsoft',
            ),
        ],
    )

    assert len(recovered.citations) == 1
    assert recovered.citations[0].chunk_id == nvidia_chunk


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

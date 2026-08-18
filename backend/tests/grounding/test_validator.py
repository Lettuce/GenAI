from __future__ import annotations

import asyncio

import pytest

from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage
from app.grounding.validator import GroundingValidationError, GroundingValidator


def _passages() -> list[SourcePassage]:
    return [
        SourcePassage(
            chunk_id="11111111-1111-1111-1111-111111111111",
            document_id="22222222-2222-2222-2222-222222222222",
            content="Services revenue increased year over year.",
            page_number=12,
            ticker="AAPL",
            company_name="Apple",
            filing_type="10-K",
            filing_year=2024,
            filing_date="2024-10-31T00:00:00+00:00",
            accession_number="0000000000-24-000001",
            source_url="https://example.com",
        )
    ]


def test_validator_accepts_refusal_without_citations() -> None:
    validator = GroundingValidator()
    answer = GroundedAnswer(
        answer_text="I do not have enough evidence.",
        citations=[
            Citation(
                chunk_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
            )
        ],
        insufficient_evidence=True,
        refusal_reason="Missing coverage for requested detail.",
    )

    validated = asyncio.run(validator.validate(answer=answer, retrieved_passages=_passages()))

    assert validated.insufficient_evidence is True
    assert validated.citations == []


def test_validator_requires_citation_for_factual_answer() -> None:
    validator = GroundingValidator()
    answer = GroundedAnswer(answer_text="Apple services grew.", citations=[], insufficient_evidence=False)

    with pytest.raises(GroundingValidationError):
        asyncio.run(validator.validate(answer=answer, retrieved_passages=_passages()))


def test_validator_rejects_citation_outside_retrieved_set() -> None:
    validator = GroundingValidator()
    answer = GroundedAnswer(
        answer_text="Apple services grew.",
        citations=[
            Citation(
                chunk_id="33333333-3333-3333-3333-333333333333",
                document_id="22222222-2222-2222-2222-222222222222",
            )
        ],
        insufficient_evidence=False,
    )

    with pytest.raises(GroundingValidationError):
        asyncio.run(validator.validate(answer=answer, retrieved_passages=_passages()))


def test_validator_normalizes_duplicate_citations() -> None:
    validator = GroundingValidator()
    answer = GroundedAnswer(
        answer_text="Apple services grew.",
        citations=[
            Citation(
                chunk_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
                quote="Services revenue increased.",
            ),
            Citation(
                chunk_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
                quote="Services revenue increased.",
            ),
        ],
        insufficient_evidence=False,
    )

    validated = asyncio.run(validator.validate(answer=answer, retrieved_passages=_passages()))

    assert validated.insufficient_evidence is False
    assert len(validated.citations) == 1
    assert validated.citations[0].page_number == 12


def test_validator_keeps_distinct_multi_company_citations() -> None:
    validator = GroundingValidator()
    retrieved = [
        SourcePassage(
            chunk_id="11111111-1111-1111-1111-111111111111",
            document_id="22222222-2222-2222-2222-222222222222",
            content="Apple services revenue increased.",
            page_number=12,
            ticker="AAPL",
            company_name="Apple",
            filing_type="10-K",
            filing_year=2024,
        ),
        SourcePassage(
            chunk_id="33333333-3333-3333-3333-333333333333",
            document_id="44444444-4444-4444-4444-444444444444",
            content="Microsoft Azure revenue accelerated.",
            page_number=21,
            ticker="MSFT",
            company_name="Microsoft",
            filing_type="10-K",
            filing_year=2024,
        ),
    ]
    answer = GroundedAnswer(
        answer_text="Apple and Microsoft both reported strong growth.",
        citations=[
            Citation(
                chunk_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
                quote="Apple services revenue increased.",
                page_number=12,
            ),
            Citation(
                chunk_id="33333333-3333-3333-3333-333333333333",
                document_id="44444444-4444-4444-4444-444444444444",
                quote="Microsoft Azure revenue accelerated.",
                page_number=21,
            ),
        ],
        insufficient_evidence=False,
    )

    validated = asyncio.run(validator.validate(answer=answer, retrieved_passages=retrieved))

    assert validated.insufficient_evidence is False
    assert len(validated.citations) == 2
    assert {citation.document_id for citation in validated.citations} == {
        "22222222-2222-2222-2222-222222222222",
        "44444444-4444-4444-4444-444444444444",
    }

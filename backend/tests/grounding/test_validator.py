import uuid
from datetime import date

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.validator import GroundingValidator, prune_unreferenced_citations
from app.retrieval.types import RetrievedPassage


def _passage(text: str = "Services revenue grew 12% year over year.") -> RetrievedPassage:
    chunk_id = uuid.uuid4()
    return RetrievedPassage(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        chunk_index=0,
        text=text,
        page="10",
        section="Item 7",
        fusion_score=0.8,
        ticker="AAPL",
        company_name="Apple Inc.",
        form="10-K",
        filing_date=date(2024, 10, 31),
        fiscal_year=2024,
        accession_number="0000320193-24-000123",
    )


def test_valid_grounded_answer_passes() -> None:
    passage = _passage()
    registry = TurnRegistry()
    registry.register(passage)
    answer = GroundedAnswer(
        answer="Services revenue grew [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=passage.chunk_id,
                excerpt="Services revenue grew 12% year over year.",
            )
        ],
    )
    result = GroundingValidator().validate(answer, registry)
    assert result.ok


def test_insufficient_evidence_requires_empty_citations() -> None:
    registry = TurnRegistry()
    answer = GroundedAnswer(
        answer="The corpus does not contain enough evidence to answer.",
        citations=[],
        insufficient_evidence=True,
    )
    result = GroundingValidator().validate(answer, registry)
    assert result.ok


def test_insufficient_evidence_rejects_citations() -> None:
    passage = _passage()
    registry = TurnRegistry()
    registry.register(passage)
    answer = GroundedAnswer(
        answer="Not enough evidence.",
        citations=[
            Citation(citation_index=1, chunk_id=passage.chunk_id, excerpt="x"),
        ],
        insufficient_evidence=True,
    )
    result = GroundingValidator().validate(answer, registry)
    assert not result.ok


def test_unknown_chunk_id_fails() -> None:
    passage = _passage("Registered chunk text for another id.")
    registry = TurnRegistry()
    registry.register(passage)
    unknown_id = uuid.uuid4()
    answer = GroundedAnswer(
        answer="Claim [1].",
        citations=[
            Citation(citation_index=1, chunk_id=unknown_id, excerpt="Claim"),
        ],
    )
    result = GroundingValidator().validate(answer, registry)
    assert not result.ok
    assert "not retrieved" in (result.error or "")


def test_bad_excerpt_fails() -> None:
    passage = _passage()
    registry = TurnRegistry()
    registry.register(passage)
    answer = GroundedAnswer(
        answer="Claim [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=passage.chunk_id,
                excerpt="Fabricated quote not in chunk.",
            )
        ],
    )
    result = GroundingValidator().validate(answer, registry)
    assert not result.ok


def test_missing_marker_fails() -> None:
    passage = _passage()
    registry = TurnRegistry()
    registry.register(passage)
    answer = GroundedAnswer(
        answer="Services revenue grew without marker.",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=passage.chunk_id,
                excerpt="Services revenue grew 12% year over year.",
            )
        ],
    )
    result = GroundingValidator().validate(answer, registry)
    assert not result.ok


def test_empty_citations_on_normal_answer_fails() -> None:
    registry = TurnRegistry()
    registry.register(_passage())
    answer = GroundedAnswer(answer="No citations here.")
    result = GroundingValidator().validate(answer, registry)
    assert not result.ok


def test_prune_unreferenced_citations_removes_extra_metadata() -> None:
    passage = _passage()
    extra_passage = _passage("Mac revenue declined.")
    registry = TurnRegistry()
    registry.register(passage)
    registry.register(extra_passage)
    answer = GroundedAnswer(
        answer="Services revenue grew [1].",
        citations=[
            Citation(
                citation_index=1,
                chunk_id=passage.chunk_id,
                excerpt="Services revenue grew 12% year over year.",
            ),
            Citation(
                citation_index=2,
                chunk_id=extra_passage.chunk_id,
                excerpt="Mac revenue declined.",
            ),
        ],
    )

    pruned = prune_unreferenced_citations(answer)

    assert [citation.citation_index for citation in pruned.citations] == [1]
    assert GroundingValidator().validate(pruned, registry).ok

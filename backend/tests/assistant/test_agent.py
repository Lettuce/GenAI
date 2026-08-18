from __future__ import annotations

import asyncio
import types
import uuid

from app.assistant.agent import GroundedAssistantAgent
from app.assistant.deps import AssistantRuntimeDeps
from app.assistant.outputs import Citation, GroundedAnswer
from app.retrieval.types import NeighborPassage, RetrievedPassage


class _FakeRetriever:
    def __init__(self, passages: list[RetrievedPassage]) -> None:
        self._passages = passages

    def retrieve(self, query: str, *, filters=None) -> list[RetrievedPassage]:
        return list(self._passages)


def _retrieved_passage() -> RetrievedPassage:
    return RetrievedPassage(
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
        fused_score=0.91,
        semantic_rank=1,
        lexical_rank=2,
        neighbor_passages=[NeighborPassage(chunk_id="n1", content="Neighbor", page_number=11)],
    )


def test_grounded_agent_returns_refusal_when_no_passages() -> None:
    agent = GroundedAssistantAgent(model_name="test")
    deps = AssistantRuntimeDeps(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        retriever=_FakeRetriever(passages=[]),
    )

    answer = asyncio.run(agent.answer(user_query="What drove services growth?", deps=deps))

    assert answer.insufficient_evidence is True
    assert answer.citations == []


def test_grounded_agent_accepts_structured_model_output() -> None:
    agent = GroundedAssistantAgent(model_name="test")
    deps = AssistantRuntimeDeps(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        retriever=_FakeRetriever(passages=[_retrieved_passage()]),
    )
    passages = agent.retrieve_passages(deps, "What drove services growth?")

    fake_output = GroundedAnswer(
        answer_text="Apple reported services growth supported by recurring subscriptions.",
        citations=[
            Citation(
                chunk_id="11111111-1111-1111-1111-111111111111",
                document_id="22222222-2222-2222-2222-222222222222",
                quote="Services revenue increased year over year.",
            )
        ],
        insufficient_evidence=False,
    )
    async def _fake_run(prompt: str, deps: AssistantRuntimeDeps) -> object:
        return types.SimpleNamespace(output=fake_output)

    agent._run = _fake_run

    answer = asyncio.run(
        agent.answer(
            user_query="What drove services growth?",
            deps=deps,
            retrieved_passages=passages,
        )
    )

    assert answer.insufficient_evidence is False
    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == "11111111-1111-1111-1111-111111111111"


def test_grounded_agent_fallback_is_readable_and_cites_all_passages() -> None:
    agent = GroundedAssistantAgent(model_name="test")
    deps = AssistantRuntimeDeps(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        retriever=_FakeRetriever(passages=[_retrieved_passage()]),
    )
    passages = agent.retrieve_passages(deps, "What drove services growth?")

    async def _failing_run(prompt: str, deps: AssistantRuntimeDeps) -> object:
        raise ValueError("structured output formatting failed")

    agent._run = _failing_run

    answer = asyncio.run(
        agent.answer(
            user_query="What drove services growth?",
            deps=deps,
            retrieved_passages=passages,
        )
    )

    assert answer.insufficient_evidence is False
    assert "trouble completing the final response formatting" not in answer.answer_text
    assert len(answer.citations) == len(passages)
    assert answer.citations[0].chunk_id == passages[0].chunk_id

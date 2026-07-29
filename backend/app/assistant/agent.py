from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic_ai import Agent, RunContext

from app.assistant.deps import AssistantRuntimeDeps
from app.assistant.depths import DEPTH_CONFIG, SearchDepth
from app.assistant.outputs import AssistantSearchPlan, AssistantSearchResult, GroundedAnswer, SourcePassage
from app.assistant.progress import AssistantProgressTracker
from app.assistant.tools import build_fts_query_terms, extract_search_terms
from app.retrieval.types import RetrievedPassage
from app.schemas.config import settings


ASSISTANT_DIR = Path(__file__).resolve().parent
INSTRUCTIONS_PATH = ASSISTANT_DIR / "instructions.md"


def _load_instructions() -> str:
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def _format_passages(passages: list[SourcePassage]) -> str:
    return json.dumps([passage.model_dump() for passage in passages], ensure_ascii=True)


def _to_source_passage(passage: RetrievedPassage) -> SourcePassage:
    return SourcePassage(
        chunk_id=passage.chunk_id,
        document_id=passage.document_id,
        content=passage.content,
        page_number=passage.page_number,
        ticker=passage.ticker,
        company_name=passage.company_name,
        filing_type=passage.filing_type,
        filing_year=passage.filing_year,
        filing_date=passage.filing_date,
        accession_number=passage.accession_number,
        source_url=passage.source_url,
    )


class AssistantSearchAgent:
    def build_plan(self, query: str, *, depth: SearchDepth = SearchDepth.STANDARD) -> AssistantSearchPlan:
        config = DEPTH_CONFIG[depth]
        extracted_terms = extract_search_terms(query, min_terms=config.min_terms, max_terms=config.max_terms)
        tsquery_terms = build_fts_query_terms(query, min_terms=config.min_terms, max_terms=config.max_terms)
        return AssistantSearchPlan(
            query=query,
            depth=depth,
            extracted_terms=extracted_terms,
            tsquery_terms=tsquery_terms,
        )

    def run(self, query: str, *, depth: SearchDepth = SearchDepth.STANDARD) -> AssistantSearchResult:
        tracker = AssistantProgressTracker()
        tracker.add("start", "Assistant search planning started")
        plan = self.build_plan(query, depth=depth)
        tracker.add("terms", f"Selected {len(plan.extracted_terms)} keyword terms")
        tracker.add("finish", "Assistant search planning finished")
        return AssistantSearchResult(plan=plan, progress=tracker.snapshot())


class GroundedAssistantAgent:
    def __init__(self, *, model_name: str | None = None) -> None:
        configured_model = model_name or settings.chat_model
        if ":" not in configured_model:
            configured_model = f"openai-chat:{configured_model}"

        self._agent = Agent(
            model=configured_model,
            output_type=GroundedAnswer,
            deps_type=AssistantRuntimeDeps,
            instructions=_load_instructions(),
            retries=1,
            name="document-copilot-grounded-agent",
            tool_timeout=20.0,
        )
        self._run_sync: Callable[..., object] = self._agent.run_sync

        @self._agent.tool
        async def search_passages(ctx: RunContext[AssistantRuntimeDeps], query: str) -> list[SourcePassage]:
            return self.retrieve_passages(ctx.deps, query)

    @staticmethod
    def retrieve_passages(deps: AssistantRuntimeDeps, query: str) -> list[SourcePassage]:
        retrieved = deps.retriever.retrieve(query, filters=deps.filters)
        return [_to_source_passage(passage) for passage in retrieved]

    def answer(
        self,
        *,
        user_query: str,
        deps: AssistantRuntimeDeps,
        retrieved_passages: list[SourcePassage] | None = None,
    ) -> GroundedAnswer:
        passages = retrieved_passages or self.retrieve_passages(deps, deps.retrieval_query or user_query)
        if not passages:
            return GroundedAnswer(
                answer_text="I do not have enough evidence in the retrieved filings to answer this safely.",
                citations=[],
                insufficient_evidence=True,
                refusal_reason="No supporting passages were retrieved for this query.",
            )

        prompt = (
            "Answer the user using only these retrieved passages. "
            "Every factual claim must be cited with chunk_id and document_id. "
            "If evidence is insufficient, set insufficient_evidence=true and explain briefly.\n\n"
            f"User query: {user_query}\n"
            f"Retrieved passages JSON: {_format_passages(passages)}"
        )

        result = self._run_sync(prompt, deps=deps)
        answer = getattr(result, "output", result)
        if isinstance(answer, GroundedAnswer):
            return answer

        # Defensive fallback if tool/model output shape drifts.
        return GroundedAnswer(
            answer_text="I do not have enough evidence in the retrieved filings to answer this safely.",
            citations=[],
            insufficient_evidence=True,
            refusal_reason="Model output could not be parsed as GroundedAnswer.",
        )

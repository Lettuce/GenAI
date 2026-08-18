from __future__ import annotations

import json
import uuid
from pathlib import Path

from pydantic_ai import Agent, RunContext
from sqlalchemy.orm import Session

from app.assistant.deps import AssistantRuntimeDeps
from app.assistant.depths import DEPTH_CONFIG, SearchDepth
from app.assistant.outputs import AssistantSearchPlan, AssistantSearchResult, Citation, GroundedAnswer, SourcePassage
from app.assistant.progress import AssistantProgressTracker
from app.assistant.tools import build_fts_query_terms, extract_search_terms
from app.database import documents
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


def _to_source_passage_from_row(row: documents.PassageRow) -> SourcePassage:
    return SourcePassage(
        chunk_id=str(row.chunk_id),
        document_id=str(row.source_document_id),
        content=row.content,
        page_number=row.page_number,
        ticker=row.ticker,
        company_name=row.company_name,
        filing_type=row.filing_type,
        filing_year=row.filing_year,
        filing_date=row.filing_date_iso,
        accession_number=row.accession_number,
        source_url=row.source_url,
    )


def _get_retriever_db_session(deps: AssistantRuntimeDeps) -> Session:
    db = getattr(deps.retriever, "_db", None)
    if not isinstance(db, Session):
        raise RuntimeError("Retriever does not expose a SQLAlchemy session for chunk reads")
    return db


def _parse_chunk_ids(chunk_ids: list[str]) -> list[uuid.UUID]:
    parsed_ids: list[uuid.UUID] = []
    for chunk_id in chunk_ids:
        try:
            parsed_ids.append(uuid.UUID(chunk_id))
        except ValueError as exc:
            raise ValueError(f"Invalid chunk_id: {chunk_id}") from exc
    return parsed_ids


def getDocumentAgent(*, model_name: str | None = None) -> Agent[AssistantRuntimeDeps, GroundedAnswer]:
    configured_model = model_name or settings.chat_model
    if ":" not in configured_model:
        configured_model = f"openai-chat:{configured_model}"

    agent = Agent(
        model=configured_model,
        output_type=GroundedAnswer,
        deps_type=AssistantRuntimeDeps,
        instructions=_load_instructions(),
        retries=1,
        name="document-copilot-grounded-agent",
        tool_timeout=20.0,
    )

    @agent.tool
    async def search_filings(ctx: RunContext[AssistantRuntimeDeps], query: str) -> list[SourcePassage]:
        retrieved = ctx.deps.retriever.retrieve(query, filters=ctx.deps.filters)
        return [_to_source_passage(passage) for passage in retrieved]

    @agent.tool
    async def read_chunks(ctx: RunContext[AssistantRuntimeDeps], chunk_ids: list[str]) -> list[SourcePassage]:
        if not chunk_ids:
            return []
        db = _get_retriever_db_session(ctx.deps)
        parsed_chunk_ids = _parse_chunk_ids(chunk_ids)
        rows = documents.get_passage_rows(db, parsed_chunk_ids)
        return [_to_source_passage_from_row(row) for row in rows]

    @agent.tool
    async def read_chunk(ctx: RunContext[AssistantRuntimeDeps], chunk_id: str) -> SourcePassage | None:
        chunks = await read_chunks(ctx, [chunk_id])
        return chunks[0] if chunks else None

    @agent.tool
    async def read_surrounding_chunks(
        ctx: RunContext[AssistantRuntimeDeps],
        chunk_id: str,
        window: int = 1,
    ) -> list[SourcePassage]:
        parsed_chunk_id = _parse_chunk_ids([chunk_id])[0]
        db = _get_retriever_db_session(ctx.deps)
        neighbor_rows_by_seed = documents.get_neighbor_passage_rows(
            db,
            seed_chunk_ids=[parsed_chunk_id],
            window=max(1, window),
        )
        neighbor_rows = neighbor_rows_by_seed.get(parsed_chunk_id, [])
        if not neighbor_rows:
            return []

        neighbor_ids = [neighbor.chunk_id for neighbor in neighbor_rows]
        rows = documents.get_passage_rows(db, neighbor_ids)
        return [_to_source_passage_from_row(row) for row in rows]

    # Backward-compatible tool alias used by the current system prompt and call path.
    @agent.tool
    async def search_passages(ctx: RunContext[AssistantRuntimeDeps], query: str) -> list[SourcePassage]:
        return await search_filings(ctx, query)

    return agent


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
        self._agent = getDocumentAgent(model_name=model_name)
        self._run = self._agent.run

    @staticmethod
    def retrieve_passages(deps: AssistantRuntimeDeps, query: str) -> list[SourcePassage]:
        retrieved = deps.retriever.retrieve(query, filters=deps.filters)
        return [_to_source_passage(passage) for passage in retrieved]

    async def answer(
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

        try:
            result = await self._run(prompt, deps=deps)
        except Exception as exc:
            return self._build_best_effort_answer(passages, failure_reason=str(exc))

        answer = getattr(result, "output", result)
        if isinstance(answer, GroundedAnswer):
            return answer

        # Defensive fallback if tool/model output shape drifts.
        return self._build_best_effort_answer(passages, failure_reason="Model output could not be parsed as GroundedAnswer.")

    @staticmethod
    def _build_best_effort_answer(passages: list[SourcePassage], *, failure_reason: str) -> GroundedAnswer:
        citations: list[Citation] = []
        selected: list[SourcePassage] = []
        seen_companies: set[str] = set()
        seen_documents: set[str] = set()

        for passage in passages:
            company_key = passage.company_name or passage.ticker or "Unknown issuer"
            document_key = passage.document_id
            if company_key not in seen_companies:
                selected.append(passage)
                seen_companies.add(company_key)
                seen_documents.add(document_key)
                if len(selected) >= 8:
                    break
                continue

            if document_key not in seen_documents:
                selected.append(passage)
                seen_documents.add(document_key)
                if len(selected) >= 8:
                    break

        for passage in selected:
            citations.append(
                Citation(
                    chunk_id=passage.chunk_id,
                    document_id=passage.document_id,
                    quote=passage.content[:320],
                    page_number=passage.page_number,
                )
            )

        if not citations:
            return GroundedAnswer(
                answer_text="I do not have enough evidence in the retrieved filings to answer this safely.",
                citations=[],
                insufficient_evidence=True,
                refusal_reason=failure_reason,
            )

        answer_lines = ["I found relevant filing evidence but had trouble completing the final response formatting."]
        for index, passage in enumerate(selected, start=1):
            company = passage.company_name or passage.ticker or "Unknown issuer"
            filing = passage.filing_type or "filing"
            year = str(passage.filing_year) if passage.filing_year is not None else "unknown year"
            snippet = passage.content.replace("\n", " ").strip()[:220]
            answer_lines.append(f"{index}. {company} ({filing} {year}): {snippet}")

        return GroundedAnswer(
            answer_text="\n".join(answer_lines),
            citations=citations,
            insufficient_evidence=False,
            refusal_reason=None,
        )

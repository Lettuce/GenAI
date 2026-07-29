from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel, Field

from app.assistant.depths import SearchDepth


@dataclass(frozen=True)
class AssistantSearchPlan:
    query: str
    depth: SearchDepth
    extracted_terms: list[str]
    tsquery_terms: str


@dataclass(frozen=True)
class AssistantSearchProgress:
    stage: str
    detail: str


@dataclass(frozen=True)
class AssistantSearchResult:
    plan: AssistantSearchPlan
    progress: list[AssistantSearchProgress]


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    quote: str | None = Field(default=None, max_length=1500)
    page_number: int | None = Field(default=None, ge=1)


class SourcePassage(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    page_number: int | None = Field(default=None, ge=1)
    ticker: str | None = None
    company_name: str | None = None
    filing_type: str | None = None
    filing_year: int | None = None
    filing_date: str | None = None
    accession_number: str | None = None
    source_url: str | None = None


class GroundedAnswer(BaseModel):
    answer_text: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    insufficient_evidence: bool = False
    refusal_reason: str | None = None

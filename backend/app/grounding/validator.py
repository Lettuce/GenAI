"""Fail-closed citation validation against the turn registry."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import GroundedAnswer

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    error: str | None = None


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _citation_markers(text: str) -> set[int]:
    return {int(match.group(1)) for match in _CITATION_MARKER_RE.finditer(text)}


def prune_unreferenced_citations(answer: GroundedAnswer) -> GroundedAnswer:
    marker_indices = _citation_markers(answer.answer)
    if not marker_indices:
        return answer

    citations = [
        citation
        for citation in answer.citations
        if citation.citation_index in marker_indices
    ]
    if len(citations) == len(answer.citations):
        return answer

    return answer.model_copy(update={"citations": citations})


class GroundingValidator:
    def validate(self, answer: GroundedAnswer, registry: TurnRegistry) -> ValidationResult:
        if not answer.answer.strip():
            return ValidationResult(ok=False, error="Answer text is empty.")

        if answer.insufficient_evidence:
            if answer.citations:
                return ValidationResult(
                    ok=False,
                    error="insufficient_evidence answers must not include citations.",
                )
            return ValidationResult(ok=True)

        if not answer.citations:
            return ValidationResult(
                ok=False,
                error="Grounded answers must include at least one citation.",
            )

        if not registry.passages_by_chunk_id:
            return ValidationResult(
                ok=False,
                error="Citations present but no passages were retrieved this turn.",
            )

        indices = [citation.citation_index for citation in answer.citations]
        if len(indices) != len(set(indices)):
            return ValidationResult(ok=False, error="Duplicate citation_index values.")

        expected_indices = list(range(1, len(indices) + 1))
        if sorted(indices) != expected_indices:
            return ValidationResult(
                ok=False,
                error="citation_index values must be unique, 1-based, and contiguous.",
            )

        marker_indices = _citation_markers(answer.answer)
        if marker_indices != set(indices):
            return ValidationResult(
                ok=False,
                error="Answer [n] markers must match citation_index values exactly.",
            )

        for citation in answer.citations:
            passage = registry.passages_by_chunk_id.get(citation.chunk_id)
            if passage is None:
                return ValidationResult(
                    ok=False,
                    error=f"Citation references chunk {citation.chunk_id} that was not retrieved.",
                )

            normalized_excerpt = _normalize_text(citation.excerpt)
            normalized_chunk = _normalize_text(passage.text)
            if normalized_excerpt not in normalized_chunk:
                return ValidationResult(
                    ok=False,
                    error=(
                        f"Excerpt for citation [{citation.citation_index}] "
                        "is not a substring of the retrieved chunk text."
                    ),
                )

        return ValidationResult(ok=True)

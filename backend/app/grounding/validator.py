from __future__ import annotations

from dataclasses import dataclass

from app.assistant.outputs import Citation, GroundedAnswer, SourcePassage


class GroundingValidationError(ValueError):
    pass


@dataclass(frozen=True)
class GroundingValidator:
    model_name: str | None = None

    async def validate(self, *, answer: GroundedAnswer, retrieved_passages: list[SourcePassage]) -> GroundedAnswer:
        return self._validate(answer=answer, retrieved_passages=retrieved_passages)

    def validate_sync(self, *, answer: GroundedAnswer, retrieved_passages: list[SourcePassage]) -> GroundedAnswer:
        return self._validate(answer=answer, retrieved_passages=retrieved_passages)

    def _validate(self, *, answer: GroundedAnswer, retrieved_passages: list[SourcePassage]) -> GroundedAnswer:
        if answer.insufficient_evidence:
            return GroundedAnswer(
                answer_text=answer.answer_text,
                citations=[],
                insufficient_evidence=True,
                refusal_reason=answer.refusal_reason or "Insufficient evidence in retrieved corpus.",
            )

        if not answer.citations:
            raise GroundingValidationError("At least one citation is required for factual answers.")

        allowed_by_chunk = {passage.chunk_id: passage for passage in retrieved_passages}
        if not allowed_by_chunk:
            raise GroundingValidationError("No retrieved passages available for citation validation.")

        normalized: list[Citation] = []
        seen_pairs: set[tuple[str, str]] = set()
        for citation in answer.citations:
            matched = allowed_by_chunk.get(citation.chunk_id)
            if matched is None:
                raise GroundingValidationError(f"Citation chunk_id {citation.chunk_id} was not retrieved this turn.")
            if citation.document_id != matched.document_id:
                raise GroundingValidationError(
                    f"Citation document mismatch for chunk_id {citation.chunk_id}: "
                    f"expected {matched.document_id}, got {citation.document_id}."
                )

            key = (citation.chunk_id, citation.document_id)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            normalized.append(
                Citation(
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    quote=citation.quote,
                    page_number=citation.page_number or matched.page_number,
                )
            )

        if not normalized:
            raise GroundingValidationError("All citations were duplicates or invalid after normalization.")

        return GroundedAnswer(
            answer_text=answer.answer_text,
            citations=normalized,
            insufficient_evidence=False,
            refusal_reason=None,
        )

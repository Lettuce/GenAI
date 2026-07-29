from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SearchDepth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass(frozen=True)
class SearchDepthConfig:
    min_terms: int
    max_terms: int
    semantic_limit: int
    lexical_limit: int
    final_limit: int


DEPTH_CONFIG: dict[SearchDepth, SearchDepthConfig] = {
    SearchDepth.QUICK: SearchDepthConfig(min_terms=3, max_terms=3, semantic_limit=12, lexical_limit=12, final_limit=4),
    SearchDepth.STANDARD: SearchDepthConfig(min_terms=3, max_terms=5, semantic_limit=30, lexical_limit=30, final_limit=8),
    SearchDepth.DEEP: SearchDepthConfig(min_terms=5, max_terms=5, semantic_limit=50, lexical_limit=50, final_limit=12),
}

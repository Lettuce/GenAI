from __future__ import annotations

import re

from nltk.corpus import stopwords

_FALLBACK_FILLER_WORDS = frozenset({
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "over",
    "that",
    "the",
    "this",
    "to",
    "with",
    "your",
})


def _get_stopwords() -> frozenset[str]:
    try:
        stopword_set = frozenset(stopwords.words("english"))
        return stopword_set | _FALLBACK_FILLER_WORDS
    except LookupError:
        return _FALLBACK_FILLER_WORDS


_FILLER_WORDS = _get_stopwords()


def _normalize_token(token: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", token.lower()).strip()
    return normalized


def extract_keywords(text: str, *, min_terms: int = 3, max_terms: int = 5) -> list[str]:
    if not text:
        return []

    tokens = [token for token in re.split(r"\s+", text.strip()) if token]
    if not tokens:
        return []

    normalized = [_normalize_token(token) for token in tokens]
    keywords = [term for term in normalized if term and len(term) > 2]
    keywords = [term for term in keywords if term not in _FILLER_WORDS]

    if len(keywords) < min_terms:
        return keywords[:max_terms]

    return keywords[:max_terms]


def build_keyword_query_terms(text: str, *, min_terms: int = 3, max_terms: int = 5) -> str:
    keywords = extract_keywords(text, min_terms=min_terms, max_terms=max_terms)
    if not keywords:
        return ""

    return " | ".join(keywords)

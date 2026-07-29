from __future__ import annotations

import re
from typing import NamedTuple

_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "for",
    "from",
    "with",
    "that",
    "this",
    "what",
    "when",
    "where",
    "which",
    "were",
    "does",
    "did",
    "into",
    "across",
    "through",
    "about",
    "their",
    "then",
    "than",
    "have",
    "has",
    "had",
    "could",
    "would",
    "should",
    "can",
    "not",
    "yet",
    "all",
    "any",
    "you",
    "your",
    "yours",
    "we",
    "our",
    "ours",
    "they",
    "them",
    "their",
    "who",
    "whom",
    "why",
    "how",
}

_INTENT_FILLER = {
    "question",
    "questions",
    "answer",
    "answers",
    "source",
    "sources",
    "tell",
    "show",
    "summarize",
    "summary",
    "explain",
    "using",
    "used",
    "use",
    "information",
    "details",
    "insight",
    "insights",
}

_DOMAIN_HINTS = {
    "revenue",
    "growth",
    "margin",
    "gross",
    "operating",
    "cash",
    "flow",
    "segment",
    "services",
    "guidance",
    "demand",
    "headwinds",
    "outlook",
    "apple",
    "microsoft",
    "amazon",
    "google",
    "meta",
    "nvidia",
    "filing",
    "10k",
    "10q",
}


class _TermCandidate(NamedTuple):
    token: str
    score: int
    index: int


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def extract_search_terms(query_text: str, *, min_terms: int = 3, max_terms: int = 5) -> list[str]:
    if min_terms <= 0:
        raise ValueError("min_terms must be greater than zero")
    if max_terms < min_terms:
        raise ValueError("max_terms must be >= min_terms")

    tokens = _tokenize(query_text)
    if not tokens:
        return []

    seen: set[str] = set()
    candidates: list[_TermCandidate] = []

    for index, token in enumerate(tokens):
        if token in seen:
            continue
        seen.add(token)

        if token in _STOPWORDS:
            continue
        if token in _INTENT_FILLER:
            continue
        if len(token) < 3 and not token.isdigit():
            continue

        score = len(token)

        if token in _DOMAIN_HINTS:
            score += 5
        if token.isdigit():
            score -= 1

        candidates.append(_TermCandidate(token=token, score=score, index=index))

    if not candidates:
        return []

    ranked = sorted(candidates, key=lambda c: (-c.score, c.index))

    selected = ranked[:max_terms]
    if len(selected) < min_terms:
        selected_tokens = {candidate.token for candidate in selected}
        for candidate in ranked[max_terms:]:
            if candidate.token in selected_tokens:
                continue
            selected.append(candidate)
            selected_tokens.add(candidate.token)
            if len(selected) >= min_terms:
                break

    selected = sorted(selected, key=lambda c: c.index)
    return [candidate.token for candidate in selected[:max_terms]]


def build_fts_query_terms(query_text: str, *, min_terms: int = 3, max_terms: int = 5) -> str:
    terms = extract_search_terms(query_text, min_terms=min_terms, max_terms=max_terms)
    if not terms:
        return ""

    # OR semantics gives lexical recall while semantic retrieval handles meaning.
    return " | ".join(terms)

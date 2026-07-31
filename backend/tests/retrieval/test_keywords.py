from app.retrieval.keywords import build_keyword_query_terms, extract_keywords


def test_extract_keywords_returns_non_empty_terms() -> None:
    keywords = extract_keywords("Revenue growth and margins in 2024", min_terms=2, max_terms=4)

    assert len(keywords) >= 2
    assert "revenue" in keywords
    assert "growth" in keywords


def test_build_keyword_query_terms_joins_terms() -> None:
    query_terms = build_keyword_query_terms("Revenue growth and margins", min_terms=2, max_terms=4)

    assert isinstance(query_terms, str)
    assert query_terms
    assert "revenue" in query_terms


def test_extract_keywords_uses_stopwords_from_a_library() -> None:
    keywords = extract_keywords("the quick fox over the hill", min_terms=2, max_terms=4)

    assert "quick" in keywords
    assert "fox" in keywords
    assert "the" not in keywords
    assert "over" not in keywords

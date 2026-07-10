from __future__ import annotations

from unittest.mock import Mock

from openai import RateLimitError
from openai._base_client import make_request_options

from ingest.pipeline import _create_embedding, chunk_markdown, extract_filing_metadata, parse_html_to_markdown


def test_extract_filing_metadata_uses_manifest_fields() -> None:
    metadata = extract_filing_metadata(
        {
            "ticker": "AAPL",
            "accession_number": "0000320193-21-000105",
            "filing_date": "2021-10-29",
            "source_url": "https://example.com/filing",
            "form": "10-K",
        },
        filing_year=2021,
    )

    assert metadata["ticker"] == "AAPL"
    assert metadata["accession_number"] == "0000320193-21-000105"
    assert metadata["filing_year"] == 2021
    assert metadata["filing_type"] == "10-K"
    assert metadata["source_url"] == "https://example.com/filing"


def test_parse_html_to_markdown_preserves_headings_and_text() -> None:
    html = "<html><body><h1>Item 1</h1><p>Revenue grew.</p><h2>Risk Factors</h2><p>Competition remains.</p></body></html>"

    markdown = parse_html_to_markdown(html)

    assert "# Item 1" in markdown
    assert "Revenue grew." in markdown
    assert "## Risk Factors" in markdown


def test_chunk_markdown_splits_large_content() -> None:
    text = "\n\n".join([f"Paragraph {index} with enough content to exceed the chunk size." for index in range(3)])

    chunks = chunk_markdown(text, max_chars=80)

    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)


def test_create_embedding_falls_back_when_openai_rate_limited() -> None:
    client = Mock()
    response = Mock()
    response.status_code = 429
    response.headers = {}
    response.request = Mock()
    response.request.method = "POST"
    response.request.url = "https://api.openai.com/v1/embeddings"
    response.text = "quota exceeded"
    client.embeddings.create.side_effect = RateLimitError(
        message="quota exceeded",
        response=response,
        body=None,
    )

    embedding = _create_embedding("fallback text", client)

    assert len(embedding) == 1536
    assert all(isinstance(value, float) for value in embedding)

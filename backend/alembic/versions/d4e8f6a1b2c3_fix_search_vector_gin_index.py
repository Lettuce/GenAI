"""fix search vector index and backfill values

Revision ID: d4e8f6a1b2c3
Revises: c2b7f42f8a59
Create Date: 2026-08-18 00:00:00.000000
"""

from alembic import op


revision = "d4e8f6a1b2c3"
down_revision = "2f2f0ff7ef01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks")
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        """
        UPDATE document_chunks
        SET search_vector = to_tsvector('english', left(content, 8000))
        WHERE search_vector IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks")
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        unique=False,
    )
"""add_document_metadata_search_vector

Revision ID: c2b7f42f8a59
Revises: c1c54648856d
Create Date: 2026-07-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision = 'c2b7f42f8a59'
down_revision = 'c1c54648856d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('source_documents', sa.Column('filing_type', sa.String(length=50), nullable=True))
    op.add_column('source_documents', sa.Column('filing_year', sa.Integer(), nullable=True))
    op.add_column('source_documents', sa.Column('accession_number', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_source_documents_accession_number'), 'source_documents', ['accession_number'], unique=False)
    op.add_column('document_chunks', sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))
    op.create_index(op.f('ix_document_chunks_search_vector'), 'document_chunks', ['search_vector'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_search_vector'), table_name='document_chunks')
    op.drop_column('document_chunks', 'search_vector')
    op.drop_index(op.f('ix_source_documents_accession_number'), table_name='source_documents')
    op.drop_column('source_documents', 'accession_number')
    op.drop_column('source_documents', 'filing_year')
    op.drop_column('source_documents', 'filing_type')

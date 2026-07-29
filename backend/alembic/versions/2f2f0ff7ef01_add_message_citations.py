"""add_message_citations

Revision ID: 2f2f0ff7ef01
Revises: c2b7f42f8a59
Create Date: 2026-07-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f2f0ff7ef01'
down_revision = 'c2b7f42f8a59'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'message_citations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('message_id', sa.Uuid(), nullable=False),
        sa.Column('chunk_id', sa.Uuid(), nullable=False),
        sa.Column('source_document_id', sa.Uuid(), nullable=False),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['chunk_id'], ['document_chunks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['chat_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_message_citations_message_id'), 'message_citations', ['message_id'], unique=False)
    op.create_index(op.f('ix_message_citations_chunk_id'), 'message_citations', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_message_citations_source_document_id'), 'message_citations', ['source_document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_message_citations_source_document_id'), table_name='message_citations')
    op.drop_index(op.f('ix_message_citations_chunk_id'), table_name='message_citations')
    op.drop_index(op.f('ix_message_citations_message_id'), table_name='message_citations')
    op.drop_table('message_citations')

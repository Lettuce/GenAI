from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.chats import CitationWrite, add_message_citations
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User


def test_add_message_citations_attaches_valid_rows_only(tmp_path) -> None:
    db_path = tmp_path / 'message-citation-attach-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    SourceDocument.__table__.create(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE document_chunks (
                id CHAR(32) PRIMARY KEY,
                source_document_id CHAR(32) NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT NULL,
                search_vector TEXT NULL,
                page_number INTEGER NULL,
                created_at DATETIME NULL
            )
            """
        )
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)
    MessageCitation.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    message_id = uuid.uuid4()
    document_id = uuid.uuid4()
    valid_chunk_id = uuid.uuid4()
    missing_chunk_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='phase7@example.com'))
        session.add(SourceDocument(id=document_id, company_name='Microsoft'))
        session.connection().exec_driver_sql(
            """
            INSERT INTO document_chunks (id, source_document_id, content, page_number)
            VALUES (?, ?, ?, ?)
            """,
            (valid_chunk_id.hex, document_id.hex, 'Evidence chunk.', 11),
        )
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Thread'))
        session.add(ChatMessage(id=message_id, thread_id=thread_id, role='assistant', content='Answer'))
        session.commit()

    with session_factory() as session:
        persisted = add_message_citations(
            session,
            message_id=message_id,
            citations=[
                CitationWrite(
                    chunk_id=valid_chunk_id,
                    source_document_id=uuid.uuid4(),
                    quote='Valid chunk citation',
                    page_number=11,
                ),
                CitationWrite(
                    chunk_id=missing_chunk_id,
                    source_document_id=document_id,
                    quote='Missing chunk citation',
                    page_number=12,
                ),
            ],
        )

    assert len(persisted) == 1
    assert persisted[0].chunk_id == str(valid_chunk_id)
    assert persisted[0].source_document_id == str(document_id)
from __future__ import annotations

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import chats
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.user import User


def test_add_turn_messages_sets_missing_thread_title_from_first_user_prompt(tmp_path) -> None:
    db_path = tmp_path / 'thread-title-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='titles@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title=None))
        session.commit()

    with session_factory() as session:
        chats.add_turn_messages(
            session,
            thread_id=thread_id,
            user_content='Summarize year-over-year services revenue changes for Apple and Microsoft.',
            assistant_content='Answer text',
        )

    with session_factory() as session:
        thread = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one()

    assert thread.title is not None
    assert thread.title.startswith('Summarize year-over-year services revenue changes')


def test_add_turn_messages_preserves_existing_thread_title(tmp_path) -> None:
    db_path = tmp_path / 'thread-title-preserve-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='titles@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Custom title'))
        session.commit()

    with session_factory() as session:
        chats.add_turn_messages(
            session,
            thread_id=thread_id,
            user_content='A new question that should not overwrite title.',
            assistant_content='Answer text',
        )

    with session_factory() as session:
        thread = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one()

    assert thread.title == 'Custom title'


def test_add_turn_messages_replaces_placeholder_new_chat_title(tmp_path) -> None:
    db_path = tmp_path / 'thread-title-placeholder-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='titles@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='New Chat'))
        session.commit()

    with session_factory() as session:
        chats.add_turn_messages(
            session,
            thread_id=thread_id,
            user_content='Compare fiscal year gross margin trends for Microsoft. ',
            assistant_content='Answer text',
        )

    with session_factory() as session:
        thread = session.execute(select(ChatThread).where(ChatThread.id == thread_id)).scalar_one()

    assert thread.title is not None
    assert thread.title != 'New Chat'
    assert thread.title.startswith('Compare fiscal year gross margin trends for Microsoft.')


def test_update_thread_title_updates_and_clears_title(tmp_path) -> None:
    db_path = tmp_path / 'thread-title-update-test.db'
    engine = create_engine(f'sqlite+pysqlite:///{db_path}', future=True)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    with session_factory() as session:
        session.add(User(id=user_id, email='titles@example.com'))
        session.add(ChatThread(id=thread_id, user_id=user_id, title='Original'))
        session.commit()

    with session_factory() as session:
        updated = chats.update_thread_title(
            session,
            user_id=user_id,
            thread_id=thread_id,
            title='Quarterly Services Summary',
        )
        assert updated is not None
        assert updated.title == 'Quarterly Services Summary'

    with session_factory() as session:
        cleared = chats.update_thread_title(
            session,
            user_id=user_id,
            thread_id=thread_id,
            title='   ',
        )
        assert cleared is not None
        assert cleared.title is None

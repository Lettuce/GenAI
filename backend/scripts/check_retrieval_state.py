from __future__ import annotations

from sqlalchemy import text

from app.database.session import SessionLocal


def main() -> None:
    with SessionLocal() as session:
        print("source_documents", session.execute(text("select count(*) from source_documents")).scalar_one())
        print("document_chunks", session.execute(text("select count(*) from document_chunks")).scalar_one())
        print(
            "chunks_with_embedding",
            session.execute(text("select count(*) from document_chunks where embedding is not null")).scalar_one(),
        )
        print(
            "chunks_with_search_vector",
            session.execute(text("select count(*) from document_chunks where search_vector is not null")).scalar_one(),
        )
        print(
            "lexical_revenue_hits",
            session.execute(
                text("select count(*) from document_chunks where search_vector @@ plainto_tsquery('english', 'revenue')")
            ).scalar_one(),
        )


if __name__ == "__main__":
    main()

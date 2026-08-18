from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import update

from app.database.models.source_document import SourceDocument
from app.database.session import SessionLocal


MANIFEST_PATH = Path(__file__).resolve().parents[2] / "data" / "downloads" / "manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    updated = 0

    with SessionLocal() as session:
        for filing in manifest.get("filings", []):
            accession_number = filing.get("accession_number")
            filing_date_text = filing.get("filing_date")
            if not accession_number or not isinstance(filing_date_text, str):
                continue

            filing_date = date.fromisoformat(filing_date_text)
            result = session.execute(
                update(SourceDocument)
                .where(SourceDocument.accession_number == accession_number)
                .values(filing_date=filing_date, filing_year=filing_date.year)
            )
            updated += result.rowcount or 0

        session.commit()

    print(f"Updated {updated} source document metadata rows")


if __name__ == "__main__":
    main()
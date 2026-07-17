# /// script
# requires-python = ">=3.12"
# ///
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from docling.document_converter import DocumentConverter


DATA_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = DATA_DIR / "downloads"
INPUT_MANIFEST_PATH = DOWNLOADS_DIR / "manifest.json"
MARKDOWN_DIR = DOWNLOADS_DIR / "markdown"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Convert SEC HTML filings in data/downloads to markdown with Docling."
	)
	parser.add_argument(
		"--input-manifest",
		type=Path,
		default=INPUT_MANIFEST_PATH,
		help="Path to the source downloads manifest.",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=MARKDOWN_DIR,
		help="Directory where the markdown tree should be written.",
	)
	parser.add_argument(
		"--limit",
		type=int,
		default=None,
		help="Optional limit for a smaller conversion run.",
	)
	return parser.parse_args()


def convert_downloads_to_markdown(
	input_manifest_path: Path, output_dir: Path, limit: int | None
) -> dict:
	manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
	filings = manifest.get("filings", [])
	if limit is not None:
		filings = filings[:limit]

	if output_dir.exists():
		shutil.rmtree(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	converter = DocumentConverter()
	converted_filings: list[dict[str, str]] = []
	errors: list[dict[str, str]] = []

	for filing in filings:
		source_path = input_manifest_path.parent / Path(filing["local_path"])
		markdown_path = output_dir / Path(filing["local_path"]).with_suffix(".md")

		try:
			result = converter.convert(str(source_path))
			markdown = result.document.export_to_markdown()
			markdown_path.parent.mkdir(parents=True, exist_ok=True)
			markdown_path.write_text(markdown.rstrip() + "\n", encoding="utf-8")
		except Exception as exc:  # noqa: BLE001
			errors.append(
				{
					"local_path": filing["local_path"],
					"error": str(exc),
				}
			)
			print(f"Failed to convert {source_path}: {exc}")
			continue

		converted_filing = dict(filing)
		converted_filing["local_path"] = str(markdown_path.relative_to(output_dir))
		converted_filings.append(converted_filing)
		print(f"Converted {source_path} -> {markdown_path}")

	output_manifest = {
		"source": manifest.get("source", "SEC EDGAR"),
		"generated_at_utc": datetime.now(UTC).isoformat(),
		"form": manifest.get("form", "10-K"),
		"converted_count": len(converted_filings),
		"failed_count": len(errors),
		"filings": converted_filings,
	}
	if errors:
		output_manifest["errors"] = errors

	output_manifest_path = output_dir / "manifest.json"
	output_manifest_path.write_text(
		json.dumps(output_manifest, indent=2) + "\n", encoding="utf-8"
	)

	if errors:
		raise SystemExit(
			f"Converted {len(converted_filings)} filing(s) with {len(errors)} failure(s)."
		)

	return output_manifest


def main() -> None:
	args = parse_args()
	result = convert_downloads_to_markdown(
		args.input_manifest,
		args.output_dir,
		args.limit,
	)
	print(f"Converted {result['converted_count']} filing(s) to {args.output_dir}")
	print(f"Manifest: {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
	main()
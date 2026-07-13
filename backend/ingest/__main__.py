"""CLI for law ingestion (stages 1-2 + verbatim check).

Examples:
    # Preview one chunk without storing (cheap smoke test):
    python -m backend.ingest --start 3 --end 6 --dry-run

    # Ingest a page range, replacing prior rows from this document:
    python -m backend.ingest --start 3 --end 26 --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.config import settings
from backend.db import init_db
from backend.ingest.pipeline import ingest_document


def _default_pdf() -> Path | None:
    pdfs = sorted(settings.laws_dir.glob("*.pdf"))
    return pdfs[0] if pdfs else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Digitize legislation into the knowledge base.")
    parser.add_argument("--pdf", type=Path, default=_default_pdf(), help="Path to the legislation PDF")
    parser.add_argument("--start", type=int, default=1, help="First page (1-based, inclusive)")
    parser.add_argument("--end", type=int, default=None, help="Last page (1-based, inclusive)")
    parser.add_argument("--per-chunk", type=int, default=None, help="Pages per Claude call")
    parser.add_argument("--limit-chunks", type=int, default=None, help="Process only the first N chunks")
    parser.add_argument("--model", type=str, default=None, help="Override the Claude model")
    parser.add_argument("--threshold", type=float, default=None, help="Verbatim match threshold (0-100)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to the database")
    parser.add_argument("--reset", action="store_true", help="Delete prior rows from this document first")
    args = parser.parse_args(argv)

    if args.pdf is None or not args.pdf.exists():
        print(f"error: PDF not found ({args.pdf}). Place it in {settings.laws_dir} or pass --pdf.", file=sys.stderr)
        return 2

    init_db()

    # --limit-chunks is implemented by narrowing the page range.
    end = args.end
    if args.limit_chunks is not None:
        per = args.per_chunk or settings.ingest_chunk_pages
        computed_end = args.start + args.limit_chunks * per - 1
        end = computed_end if end is None else min(end, computed_end)

    report = ingest_document(
        args.pdf,
        start=args.start,
        end=end,
        per_chunk=args.per_chunk,
        model=args.model,
        threshold=args.threshold,
        dry_run=args.dry_run,
        reset=args.reset,
    )

    print("\n=== Ingestion summary ===")
    print(f"Articles returned : {report.total}")
    print(f"Passed verbatim   : {len(report.accepted) + len(report.duplicates)}")
    print(f"Duplicates removed: {len(report.duplicates)}")
    print(f"Rejected          : {len(report.rejected)}")
    print(f"Kept (unique)     : {len(report.accepted)}")
    if report.rejected:
        print("  rejected (paraphrase/fabrication caught):")
        for r in report.rejected:
            print(f"    - [{r.score:5.1f}] {r.article.title[:60]}")
    if args.dry_run:
        print("Storage           : (dry run — nothing written)")
    else:
        print(f"Stored to DB      : {report.stored}")
    u = report.usage
    print(
        f"Tokens            : in={u.input_tokens} out={u.output_tokens} "
        f"cache_read={u.cache_read_input_tokens}"
    )
    print(f"Estimated cost    : ${u.cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

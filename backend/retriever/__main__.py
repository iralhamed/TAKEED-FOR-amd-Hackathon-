"""CLI for the retriever (stage 3).

    # Embed all laws that don't yet have a vector:
    python -m backend.retriever build

    # Re-embed everything (e.g. after changing the embedding model):
    python -m backend.retriever build --all

    # Try a similarity search:
    python -m backend.retriever search "شروط التعاقد مع شركة أجنبية" --top-k 5
"""

from __future__ import annotations

import argparse
import sys

from backend.config import settings
from backend.db import init_db
from backend.retriever.retrieval import embed_pending_laws, reembed_all_laws, search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed laws and run similarity search.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Generate embeddings for laws")
    p_build.add_argument("--all", action="store_true", help="Re-embed all laws, not just pending")

    p_search = sub.add_parser("search", help="Search laws by similarity")
    p_search.add_argument("query", type=str)
    p_search.add_argument("--top-k", type=int, default=None)

    args = parser.parse_args(argv)
    init_db()

    if args.command == "build":
        print("Loading embedding model (first run downloads it)...")
        count = reembed_all_laws() if args.all else embed_pending_laws()
        print(f"Embedded {count} law(s) with '{settings.embedding_model}'.")
        return 0

    if args.command == "search":
        results = search(args.query, top_k=args.top_k)
        if not results:
            print("No embedded laws found. Run `python -m backend.retriever build` first.", file=sys.stderr)
            return 1
        print(f"Top {len(results)} for: {args.query!r}\n" + "=" * 70)
        for rank, r in enumerate(results, 1):
            snippet = r.text.replace("\n", " ")[:110]
            print(f"{rank}. [score {r.score:.3f}] (id={r.law_id}, page {r.page}) {r.title}")
            print(f"   {r.chapter or ''}")
            print(f"   {snippet}...")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

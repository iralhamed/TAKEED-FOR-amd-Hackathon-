"""Ingestion orchestrator: parse -> digitize -> verbatim-check -> store.

Ties stage 1 (parser), stage 2 (Claude digitizer), and anti-hallucination
check #1 (verbatim matcher) together, then persists the articles that pass.
Embeddings (stage 3) are filled in later by the retriever; rows land here with
`embedding = NULL`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz
from sqlalchemy import delete

from backend.config import settings
from backend.db import Law, session_scope
from backend.ingest.digitizer import ArticleDraft, Usage, digitize_chunk
from backend.parser import Page, extract_pages
from backend.validator import best_page_for, normalize_arabic, verify_verbatim

# Two articles whose normalized text is this similar are treated as duplicates.
# High enough that genuinely distinct provisions are never merged.
_DEDUP_SIMILARITY = 95.0


@dataclass
class Chunk:
    pages: list[Page]

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def span(self) -> str:
        return f"{self.pages[0].number}-{self.pages[-1].number}"


@dataclass
class Accepted:
    article: ArticleDraft
    page: int | None
    score: float


@dataclass
class Rejected:
    article: ArticleDraft
    score: float


@dataclass
class IngestReport:
    accepted: list[Accepted] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    duplicates: list[Accepted] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stored: int = 0
    dry_run: bool = False

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected)


def dedupe(accepted: list[Accepted]) -> tuple[list[Accepted], list[Accepted]]:
    """Drop near-duplicate articles by normalized-text similarity (keep first).

    The linking document repeats the same النظام article alongside each related
    لائحة provision; those recur verbatim. Genuinely distinct provisions have
    different text and stay. Returns (kept, dropped).
    """
    kept: list[Accepted] = []
    kept_norms: list[str] = []
    dropped: list[Accepted] = []
    for acc in accepted:
        norm = normalize_arabic(acc.article.text)
        if any(fuzz.ratio(norm, kn) >= _DEDUP_SIMILARITY for kn in kept_norms):
            dropped.append(acc)
        else:
            kept.append(acc)
            kept_norms.append(norm)
    return kept, dropped


def build_chunks(
    pages: list[Page], start: int, end: int | None, per_chunk: int
) -> list[Chunk]:
    """Slice pages [start, end] (1-based, inclusive) into groups of `per_chunk`."""
    end = end or len(pages)
    selected = [p for p in pages if start <= p.number <= end]
    return [
        Chunk(pages=selected[i : i + per_chunk])
        for i in range(0, len(selected), per_chunk)
    ]


def ingest_document(
    path: str | Path,
    *,
    source_label: str | None = None,
    start: int = 1,
    end: int | None = None,
    per_chunk: int | None = None,
    model: str | None = None,
    threshold: float | None = None,
    dry_run: bool = False,
    reset: bool = False,
    progress: bool = True,
) -> IngestReport:
    path = Path(path)
    source_label = source_label or path.name
    per_chunk = per_chunk or settings.ingest_chunk_pages
    threshold = threshold if threshold is not None else settings.verbatim_match_threshold

    pages = extract_pages(path)
    chunks = build_chunks(pages, start, end, per_chunk)
    report = IngestReport(dry_run=dry_run)

    if progress:
        print(
            f"Ingesting {source_label}: pages {start}-{end or len(pages)} "
            f"in {len(chunks)} chunk(s) of up to {per_chunk} pages."
        )

    for idx, chunk in enumerate(chunks, 1):
        result = digitize_chunk(chunk.text, model=model)
        report.usage.add_usage(result.usage)

        kept = 0
        for article in result.articles:
            check = verify_verbatim(article.text, chunk.text, threshold)
            if check.passed:
                page = best_page_for(article.text, chunk.pages)
                report.accepted.append(Accepted(article, page, check.score))
                kept += 1
            else:
                report.rejected.append(Rejected(article, check.score))

        if progress:
            print(
                f"  chunk {idx}/{len(chunks)} (pages {chunk.span}): "
                f"{len(result.articles)} article(s), {kept} passed verbatim check"
            )

    # De-duplicate across all chunks before storing.
    report.accepted, report.duplicates = dedupe(report.accepted)
    if progress and report.duplicates:
        print(f"  removed {len(report.duplicates)} near-duplicate article(s)")

    if not dry_run and report.accepted:
        report.stored = _store(report.accepted, source_label, reset)

    return report


def _store(accepted: list[Accepted], source_label: str, reset: bool) -> int:
    with session_scope() as session:
        if reset:
            session.execute(delete(Law).where(Law.source_document == source_label))
        for acc in accepted:
            session.add(
                Law(
                    title=acc.article.title,
                    text=acc.article.text,
                    chapter=acc.article.chapter or None,
                    page=acc.page,
                    keywords=acc.article.keywords,
                    embedding=None,  # filled in phase 3
                    source_document=source_label,
                )
            )
    return len(accepted)

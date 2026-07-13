"""Anti-hallucination check #1 — verbatim text matching at ingestion.

Before any digitized article enters the knowledge base, we confirm its `text`
field actually appears in the source document, using a deterministic fuzzy
string match (rapidfuzz). No AI call. This catches paraphrasing or invented
text at the cheapest possible point.

Both the candidate and the source are normalized the same way first, so
cosmetic Arabic differences (tatweel/kashida, diacritics, alef/ya variants,
whitespace) don't cause false rejections — while genuine paraphrasing or
fabrication still drives the score down.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from backend.parser import Page

# --- Arabic normalization ---

# Tashkeel (harakat) + superscript alef, and the tatweel/kashida elongation char.
_DIACRITICS = re.compile(r"[ً-ٰٟـ]")
# Alef variants (madda, hamza above/below, wasla) -> bare alef.
_ALEF_VARIANTS = re.compile(r"[آأإٱ]")
_WHITESPACE = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for robust matching.

    - strip tashkeel diacritics and tatweel
    - unify alef variants (أ إ آ ٱ) -> ا and alef-maksura (ى) -> ي
    - collapse all whitespace to single spaces
    """
    text = _DIACRITICS.sub("", text)
    text = _ALEF_VARIANTS.sub("ا", text)
    text = text.replace("ى", "ي")  # ى -> ي
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def verbatim_score(candidate: str, source: str) -> float:
    """Return a 0-100 score for how well `candidate` appears within `source`.

    Uses partial_ratio so a short article matches against a longer source chunk:
    it finds the best-aligning substring of the source.
    """
    cand = normalize_arabic(candidate)
    src = normalize_arabic(source)
    if not cand or not src:
        return 0.0
    return float(fuzz.partial_ratio(cand, src))


@dataclass
class VerbatimResult:
    passed: bool
    score: float
    threshold: float


def verify_verbatim(candidate: str, source: str, threshold: float) -> VerbatimResult:
    score = verbatim_score(candidate, source)
    return VerbatimResult(passed=score >= threshold, score=score, threshold=threshold)


def best_page_for(candidate: str, pages: list[Page]) -> int | None:
    """Deterministically attribute an article to the page it best matches.

    Returns the 1-based page number with the highest verbatim score, or None if
    no pages were supplied.
    """
    best_page: int | None = None
    best_score = -1.0
    for page in pages:
        score = verbatim_score(candidate, page.text)
        if score > best_score:
            best_score = score
            best_page = page.number
    return best_page

"""Stage 1 — PDF text extraction (pure Python, no AI).

Used both for digitizing legislation (phase 2) and for parsing uploaded claims
(phase 4). PyMuPDF handles text-based PDFs directly; scanned pages fall back to
Tesseract OCR (wired in phase 4, when we need it for claims).

Arabic note: PyMuPDF returns text with visual-order RTL artifacts (repositioned
list digits, occasionally decomposed ligatures). We deliberately do NOT try to
"fix" this here — the digitizer sees exactly this text and copies from it, and
the verbatim checker normalizes both sides the same way, so consistency matters
more than cosmetic correctness.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class Page:
    number: int  # 1-based page number
    text: str


def extract_pages(path: str | Path) -> list[Page]:
    """Extract text per page. Returns one Page per PDF page (1-based numbering)."""
    doc = fitz.open(str(path))
    try:
        return [Page(number=i + 1, text=doc[i].get_text()) for i in range(doc.page_count)]
    finally:
        doc.close()


def extract_text(path: str | Path) -> str:
    """Extract the full document text as a single string."""
    return "\n".join(page.text for page in extract_pages(path))


# Minimum characters/page below which we assume the page is scanned (image-only).
_MIN_CHARS_PER_PAGE = 20


def ocr_available() -> bool:
    """True if pytesseract and the tesseract binary are both installed."""
    try:
        import pytesseract  # noqa: F401

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


@dataclass
class ParsedDocument:
    text: str
    used_ocr: bool
    page_count: int


def extract_document(path: str | Path, ocr_lang: str = "ara+eng") -> ParsedDocument:
    """Extract text, falling back to OCR only when the PDF looks scanned.

    Text-based PDFs (the common case) are read directly by PyMuPDF. If the
    embedded text is negligible (scanned images), and Tesseract is available,
    we OCR each page. If Tesseract isn't installed we log a warning and return
    whatever embedded text exists — so the box stays lean until OCR is needed.
    """
    pages = extract_pages(path)
    embedded = "\n".join(p.text for p in pages)

    looks_scanned = len(embedded.strip()) < _MIN_CHARS_PER_PAGE * max(len(pages), 1)
    if not looks_scanned:
        return ParsedDocument(text=embedded, used_ocr=False, page_count=len(pages))

    if not ocr_available():
        import warnings

        warnings.warn(
            "PDF appears scanned but Tesseract is not installed; "
            "returning embedded text only. Install tesseract-ocr + tesseract-ocr-ara "
            "to enable OCR.",
            stacklevel=2,
        )
        return ParsedDocument(text=embedded, used_ocr=False, page_count=len(pages))

    import io

    import pytesseract
    from PIL import Image

    doc = fitz.open(str(path))
    try:
        ocr_pages: list[str] = []
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_pages.append(pytesseract.image_to_string(img, lang=ocr_lang))
    finally:
        doc.close()
    return ParsedDocument(text="\n".join(ocr_pages), used_ocr=True, page_count=len(pages))

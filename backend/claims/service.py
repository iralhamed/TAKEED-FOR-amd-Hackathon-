"""Phase 4 — claim upload and parsing.

Saves an uploaded claim PDF to `uploads/`, extracts its text (OCR fallback for
scanned PDFs), and creates a Claim row in PENDING state. The compliance run
(phase 5) picks it up from there.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import Claim, ClaimStatus
from backend.parser import extract_document

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(filename: str) -> str:
    """Sanitize an uploaded filename and prefix a short unique id to avoid clashes."""
    base = Path(filename).name
    stem = _SAFE_NAME.sub("_", Path(base).stem)[:80] or "claim"
    suffix = Path(base).suffix.lower() or ".pdf"
    return f"{uuid.uuid4().hex[:8]}_{stem}{suffix}"


def save_upload(data: bytes, filename: str) -> Path:
    """Write uploaded bytes to the uploads directory. Returns the stored path."""
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    path = settings.uploads_dir / _safe_filename(filename)
    path.write_bytes(data)
    return path


def create_claim_from_upload(session: Session, data: bytes, filename: str) -> Claim:
    """Save the upload, parse its text, and persist a PENDING Claim row."""
    path = save_upload(data, filename)
    parsed = extract_document(path)

    claim = Claim(
        file=str(path),
        status=ClaimStatus.PENDING,
        parsed_text=parsed.text,
    )
    session.add(claim)
    session.flush()  # assign claim.id
    return claim

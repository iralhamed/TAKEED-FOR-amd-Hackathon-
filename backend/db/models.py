"""ORM models for Ta'akkud.

Three tables mirror the spec:
  - Law        : the digitized, verbatim-verified legislation knowledge base
  - Claim      : an uploaded company claim and its review lifecycle
  - Violation  : one detected inconsistency, linked to the claim and the law it breaches

`keywords` and `embedding` are stored as JSON. For the MVP corpus (tens to a
couple hundred articles) a JSON-encoded float list is plenty fast; retrieval
loads them into a NumPy matrix at query time (phase 3).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimStatus(str, enum.Enum):
    """Lifecycle of a claim. Values map to the Arabic UI labels in the frontend."""

    PENDING = "pending"        # queued, not yet processed
    PROCESSING = "processing"  # "جارٍ الفحص"
    COMPLIANT = "compliant"    # "متوافقة"  🟢
    NON_COMPLIANT = "non_compliant"  # "غير متوافقة"  🔴
    FAILED = "failed"          # parsing/pipeline error


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Law(Base):
    """A single digitized article of legislation (output of stage 2 + 3).

    `text` is the exact, verbatim source text — verified against the source PDF
    with rapidfuzz at ingestion (anti-hallucination check #1). Never edited.
    """

    __tablename__ = "laws"

    law_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "المادة ٤٥"
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)  # "الباب"
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)  # "الصفحة"
    text: Mapped[str] = mapped_column(Text, nullable=False)  # verbatim source text
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    # Provenance: which source document / label this came from (for the verbatim check).
    source_document: Mapped[str | None] = mapped_column(String(512), nullable=True)

    violations: Mapped[list[Violation]] = relationship(back_populates="law")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Law {self.law_id} {self.title!r}>"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, native_enum=False, length=32),
        default=ClaimStatus.PENDING,
        nullable=False,
    )
    file: Mapped[str] = mapped_column(String(512), nullable=False)  # stored upload path
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # Company/vendor name pulled from the claim (best-effort, nullable).
    company_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Raw text extracted from the claim PDF (stage 1 / phase 4).
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured claim data extracted by Claude (phase 5).
    extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Full compliance report produced by Claude (phase 5).
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    violations: Mapped[list[Violation]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Claim {self.id} status={self.status.value}>"


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    law_id: Mapped[int] = mapped_column(
        ForeignKey("laws.law_id"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # "السبب"
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, native_enum=False, length=16),
        default=Severity.MEDIUM,
        nullable=False,
    )

    claim: Mapped[Claim] = relationship(back_populates="violations")
    law: Mapped[Law] = relationship(back_populates="violations")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Violation claim={self.claim_id} law={self.law_id} {self.severity.value}>"

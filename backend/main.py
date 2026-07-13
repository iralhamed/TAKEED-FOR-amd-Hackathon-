"""FastAPI application entrypoint for Ta'akkud.

Phase 1: boots, initializes the database, and exposes a health check plus a
minimal read-only claims listing. Later phases add upload, ingestion, retrieval,
and reporting routers.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.claims import create_claim_from_upload
from backend.db import Claim, Law, get_session, init_db
from backend.report import run_compliance_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Ta'akkud API",
    description="Government claims compliance verification (hackathon MVP)",
    version="0.1.0",
    lifespan=lifespan,
)

# The Next.js frontend runs on a different port during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict:
    """Liveness + DB connectivity check."""
    claim_count = session.scalar(select(func.count()).select_from(Claim))
    return {"status": "ok", "service": "taakkud", "claims": claim_count}


@app.get("/api/claims")
def list_claims(session: Session = Depends(get_session)) -> list[dict]:
    """Recent claims for the home page ('آخر المطالبات'). Newest first."""
    claims = session.scalars(
        select(Claim).order_by(Claim.created_at.desc()).limit(20)
    ).all()
    return [
        {
            "id": c.id,
            "status": c.status.value,
            "file": Path(c.file).name,
            "company_name": c.company_name,
            "created_at": c.created_at.isoformat(),
            "violation_count": len(c.violations),
        }
        for c in claims
    ]


@app.get("/api/laws/stats")
def laws_stats(session: Session = Depends(get_session)) -> dict:
    """Knowledge-base stats for the admin page."""
    laws = session.scalars(select(Law)).all()
    embedded = sum(1 for law in laws if law.embedding)
    sources = sorted({law.source_document for law in laws if law.source_document})
    return {"total": len(laws), "embedded": embedded, "sources": sources}


@app.post("/api/admin/build")
def admin_build() -> dict:
    """Build the knowledge base: embed any laws still missing a vector (stage 3)."""
    from backend.retriever import embed_pending_laws

    count = embed_pending_laws()
    return {"embedded": count}


@app.post("/api/claims/upload")
async def upload_claim(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    """Upload a company claim PDF: save it, parse its text, create a Claim row.

    The compliance check (phase 5) runs as a separate step.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    claim = create_claim_from_upload(session, data, file.filename)
    session.commit()
    return {
        "id": claim.id,
        "status": claim.status.value,
        "file": Path(claim.file).name,
        "parsed_chars": len(claim.parsed_text or ""),
    }


@app.post("/api/claims/{claim_id}/check")
def check_claim(claim_id: int, session: Session = Depends(get_session)) -> dict:
    """Run the compliance check (retrieval + constrained Claude call) for a claim."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")
    if not (claim.parsed_text or "").strip():
        raise HTTPException(status_code=400, detail="Claim has no parsed text to check.")
    report = run_compliance_check(session, claim)
    session.commit()
    return {"id": claim.id, "status": claim.status.value, "report": report}


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: int, session: Session = Depends(get_session)) -> dict:
    """Full claim detail for the report page."""
    claim = session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")
    return {
        "id": claim.id,
        "status": claim.status.value,
        "file": Path(claim.file).name,
        "company_name": claim.company_name,
        "created_at": claim.created_at.isoformat(),
        "parsed_chars": len(claim.parsed_text or ""),
        "extracted": claim.extracted,
        "report": claim.report,
        "violations": [
            {
                "law_id": v.law_id,
                "reason": v.reason,
                "severity": v.severity.value,
            }
            for v in claim.violations
        ],
    }

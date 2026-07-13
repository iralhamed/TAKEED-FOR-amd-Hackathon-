# تأكيد (Ta'akkud) — Government Claims Compliance Verification (Hackathon MVP)

AI-assisted decision-support tool: a government employee uploads a company's
claim (PDF); the system checks it against digitized legislation and reports
possible violations with references to the specific article, chapter, and page.
**It is an assistant, not a decision-maker** — the employee makes the final call.

## Architecture

```
Upload claim PDF ─▶ parse (PyMuPDF, OCR fallback) ─▶ per-paragraph retrieval
   (NumPy cosine over local embeddings) ─▶ ONE constrained Claude call ─▶ report
```

Two anti-hallucination contracts:
1. **Verbatim match at ingestion** — every stored article's text is fuzzy-matched
   (rapidfuzz) against the source PDF before it enters the knowledge base.
2. **ID-constrained citation at output** — Claude's output schema restricts
   `law_id` to an enum of exactly the articles retrieved for that call, so it
   cannot cite anything it wasn't given.

## Stack

- Backend: FastAPI + SQLAlchemy (SQLite). Python 3.12 via `uv`.
- Embeddings: `fastembed` (ONNX) `paraphrase-multilingual-MiniLM-L12-v2`, local/CPU.
- LLM: Claude (`claude-opus-4-8`) — only for one-time law digitization and the
  constrained compliance call.
- Frontend: Next.js (App Router) + Tailwind, Arabic RTL UI.

## Setup

```bash
# Python env (uv installs Python 3.12 automatically)
uv venv --python 3.12 .venv
uv pip install -e .
uv pip install anthropic rapidfuzz fastembed numpy pymupdf fpdf2 uharfbuzz

# API key for digitization + compliance calls
export ANTHROPIC_API_KEY=sk-...

# Frontend deps
cd frontend && npm install && cd ..
```

## One-time knowledge-base build

```bash
# 1. Digitize a page range of legislation (Claude + verbatim check + dedup)
.venv/bin/python -m backend.ingest --start 3 --end 14 --reset

# 2. Generate embeddings for the stored articles
.venv/bin/python -m backend.retriever build
```

## Run

```bash
# Backend (http://localhost:8000)
.venv/bin/uvicorn backend.main:app --port 8000

# Frontend (http://localhost:3000) — in another shell
cd frontend && npm run dev
```

For remote access set `NEXT_PUBLIC_API_BASE` in `frontend/.env.local` to the
server's public URL.

## Sample claim

```bash
.venv/bin/python scripts/make_sample_claim.py   # -> uploads/sample_claim.pdf
```

## Useful CLIs

```bash
# Try retrieval directly
.venv/bin/python -m backend.retriever search "شروط التعاقد مع شركة أجنبية"

# Ingest a wider range later
.venv/bin/python -m backend.ingest --start 3 --end 40 --reset
```

## Notes / constraints

- Runs on a 2 GB VPS. The embedding model is ~650 MB resident and loads lazily.
  Running `next dev` + backend + a live compliance check is near the RAM ceiling;
  add a small swapfile for headroom during the demo.
- Tesseract OCR is only needed for scanned claims; install `tesseract-ocr` +
  `tesseract-ocr-ara` to enable the fallback (not required for text PDFs).

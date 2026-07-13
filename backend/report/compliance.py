"""Stage 4 — compliance check with ID-constrained citation (anti-hallucination #2).

Flow for one claim:
  1. Split the claim text into paragraphs and retrieve the most relevant articles
     for each, then merge — so a multi-issue claim surfaces every relevant law
     despite the embedding model's short input window.
  2. Make ONE Claude call that sees only the claim + those retrieved articles.
  3. The output schema constrains `law_id` to an ENUM of exactly the retrieved
     IDs, so Claude cannot cite an article it wasn't given. A Python check
     re-validates as a backstop.
  4. Titles / chapters / pages in the report come from OUR database, keyed by the
     cited id — never free-texted by the model.
"""

from __future__ import annotations

import json

import anthropic
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import Claim, ClaimStatus, Severity, Violation
from backend.ingest.digitizer import Usage, _get_client
from backend.retriever import RetrievedLaw, search

_MIN_PARAGRAPH_CHARS = 25

_SYSTEM_PROMPT = """\
أنت مساعد لمراجعة الامتثال لدى موظف حكومي سعودي، ضمن نظام المنافسات والمشتريات الحكومية.

ستصلك:
- نص «مطالبة» مقدمة من شركة.
- مجموعة من «المواد النظامية» المسترجعة، لكل مادة معرّف رقمي (id).

مهمتك أداة مساعدة لاتخاذ القرار — ولست جهة قرار. الموظف هو من يتخذ القرار النهائي.

القواعد الصارمة:
1. افحص المطالبة فقط في ضوء المواد المسترجعة المرفقة. لا تعتمد على أي معرفة خارجية أو أي مادة غير مرفقة.
2. كل مخالفة يجب أن تشير إلى معرّف (law_id) من المعرّفات المرفقة حصراً. يُمنع اختراع أرقام مواد أو الاستشهاد بمادة غير مرفقة.
3. لكل مخالفة: حدّد نوعها (type) بإيجاز، والسبب (reason) موضحاً كيف تخالف المطالبة تلك المادة، ودرجة الخطورة (severity)، ونصاً داعماً (evidence) مقتبساً من نص المطالبة.
4. `status` = "non_compliant" إذا وُجدت مخالفة واحدة على الأقل، وإلا "compliant".
5. `recommendation`: صياغة استشارية ليّنة توصي بالمراجعة اليدوية (مثل: "يوصى بإحالة المطالبة للمراجعة اليدوية والتحقق من المستندات")؛ لا تستخدم لغة قرار حاسمة مثل "يُرفض" أو "يُعتمد". القرار للموظف.
6. استخرج ملخص المطالبة (اسم الجهة/الشركة، الموضوع، المبلغ، التاريخ) قدر المتاح؛ اترك الحقل فارغاً إذا لم يُذكر.
7. إذا لم تجد أي مخالفة واضحة في ضوء المواد المرفقة، فاجعل status = "compliant" وقائمة violations فارغة.
"""


def _build_schema(allowed_ids: list[int]) -> dict:
    return {
        "type": "object",
        "properties": {
            "claim_summary": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "subject": {"type": "string"},
                    "amount": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["company_name", "subject", "amount", "date"],
                "additionalProperties": False,
            },
            "status": {"type": "string", "enum": ["compliant", "non_compliant"]},
            "violations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        # Hard constraint: only IDs actually passed in context.
                        "law_id": {"type": "integer", "enum": allowed_ids},
                        "type": {"type": "string"},
                        "reason": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["law_id", "type", "reason", "severity", "evidence"],
                    "additionalProperties": False,
                },
            },
            "recommendation": {"type": "string"},
        },
        "required": ["claim_summary", "status", "violations", "recommendation"],
        "additionalProperties": False,
    }


def _retrieve_for_claim(text: str, top_k: int) -> list[RetrievedLaw]:
    """Retrieve per paragraph and merge by law_id (keep highest score)."""
    paragraphs = [p.strip() for p in text.splitlines() if len(p.strip()) >= _MIN_PARAGRAPH_CHARS]
    if not paragraphs:
        paragraphs = [text]

    best: dict[int, RetrievedLaw] = {}
    for para in paragraphs:
        for hit in search(para, top_k=3):
            if hit.law_id not in best or hit.score > best[hit.law_id].score:
                best[hit.law_id] = hit
    merged = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return merged[:top_k]


def _format_articles(laws: list[RetrievedLaw]) -> str:
    blocks = []
    for law in laws:
        blocks.append(
            f"<article id=\"{law.law_id}\" title=\"{law.title}\" "
            f"chapter=\"{law.chapter or ''}\" page=\"{law.page or ''}\">\n"
            f"{law.text}\n</article>"
        )
    return "\n\n".join(blocks)


def run_compliance_check(
    session: Session, claim: Claim, model: str | None = None
) -> dict:
    """Run the full compliance check for a claim, persist results, return the report."""
    model = model or settings.anthropic_model
    text = claim.parsed_text or ""

    claim.status = ClaimStatus.PROCESSING
    session.flush()

    retrieved = _retrieve_for_claim(text, settings.top_k)
    by_id = {law.law_id: law for law in retrieved}

    if not retrieved:
        report = {
            "status": "compliant",
            "claim_summary": {},
            "violations": [],
            "recommendation": "لا توجد مواد نظامية مسترجعة لمطابقتها؛ يوصى بالمراجعة اليدوية.",
            "retrieved_law_ids": [],
        }
        _persist(session, claim, report, [])
        return report

    schema = _build_schema(sorted(by_id.keys()))
    client = _get_client()

    user_content = (
        "نص المطالبة المقدمة من الشركة:\n"
        f"<claim>\n{text}\n</claim>\n\n"
        "المواد النظامية المسترجعة (استشهد بمعرّفاتها فقط):\n"
        f"{_format_articles(retrieved)}"
    )

    with client.messages.stream(
        model=model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        message = stream.get_final_message()

    usage = Usage()
    usage.add(message.usage)

    raw = next((b.text for b in message.content if b.type == "text"), "{}")
    data = json.loads(raw)

    # Backstop: drop any citation not in the retrieved set (schema should prevent this).
    allowed = set(by_id.keys())
    violations_out = []
    for v in data.get("violations", []):
        if v.get("law_id") in allowed:
            violations_out.append(v)

    status = "non_compliant" if violations_out else "compliant"

    # Enrich each violation with law metadata from OUR database (not the model).
    enriched = []
    for v in violations_out:
        law = by_id[v["law_id"]]
        enriched.append(
            {
                "law_id": law.law_id,
                "title": law.title,
                "chapter": law.chapter,
                "page": law.page,
                "type": v.get("type", ""),
                "reason": v.get("reason", ""),
                "severity": v.get("severity", "medium"),
                "evidence": v.get("evidence", ""),
                "article_text": law.text,
            }
        )

    report = {
        "status": status,
        "claim_summary": data.get("claim_summary", {}),
        "violations": enriched,
        "recommendation": data.get("recommendation", ""),
        "retrieved_law_ids": sorted(allowed),
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": round(usage.cost_usd, 4),
        },
    }

    _persist(session, claim, report, enriched)
    return report


def _persist(session: Session, claim: Claim, report: dict, violations: list[dict]) -> None:
    summary = report.get("claim_summary") or {}
    claim.company_name = summary.get("company_name") or claim.company_name
    claim.extracted = summary or None
    claim.report = report
    claim.status = (
        ClaimStatus.NON_COMPLIANT if report["status"] == "non_compliant" else ClaimStatus.COMPLIANT
    )

    # Replace any prior violations for idempotent re-checks.
    for old in list(claim.violations):
        session.delete(old)
    session.flush()

    for v in violations:
        session.add(
            Violation(
                claim_id=claim.id,
                law_id=v["law_id"],
                reason=v["reason"],
                severity=Severity(v["severity"]),
            )
        )

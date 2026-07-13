"""Generate a realistic synthetic Arabic claim PDF for development/demo.

Stands in for a real company-submitted claim. The scenario deliberately contains
compliance issues that map to articles already in our knowledge base (foreign
contracting without an investment-ministry licence and without checking for
local alternatives; ignoring the local-SME / local-content preference; unequal
treatment of competitors), so the phase-5 compliance check has concrete things
to flag.

Rendered with fpdf2 + HarfBuzz text shaping, which produces properly shaped
right-to-left Arabic *and* a clean logical-order text layer (verified: the
extracted text matches the source), mimicking a real digitally-authored PDF.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "assets" / "fonts" / "Amiri-Regular.ttf"
OUT = ROOT / "uploads" / "sample_claim.pdf"

HEADING = "مطالبة مالية — طلب صرف مستحقات عقد"

FIELDS = [
    "الجهة المتقدمة بالمطالبة: شركة الإنشاءات المتقدمة المحدودة",
    "رقم المطالبة: 2026/457      التاريخ: 1447/12/15هـ",
    "المبلغ الإجمالي للعقد: 4,500,000 ريال",
]

SECTIONS = [
    (
        "موضوع المطالبة",
        "صرف الدفعة الأولى من قيمة عقد تنفيذ أعمال إنشائية لصالح الجهة الحكومية، "
        "بمبلغ إجمالي قدره أربعة ملايين وخمسمائة ألف ريال.",
    ),
    (
        "تفاصيل التعاقد",
        "تم إسناد تنفيذ الأعمال إلى شركة أجنبية غير مرخص لها بموجب نظام الاستثمار "
        "الأجنبي، ولم يتم الحصول على ترخيص من وزارة الاستثمار قبل التعاقد. كما لم "
        "يتم الإعلان في البوابة وموقع الجهة الحكومية للتحقق من عدم وجود أكثر من "
        "شخص محلي مؤهل لتنفيذ الأعمال المطلوبة.",
    ),
    (
        "الأولوية والمحتوى المحلي",
        "لم تُعطَ الأولوية في التعامل للمنشآت الصغيرة والمتوسطة المحلية ولا للمحتوى "
        "المحلي عند الترسية، حيث جرى استبعاد العروض المحلية دون مبرر موثّق.",
    ),
    (
        "إجراءات التنافس",
        "جرى التفاوض مع الشركة الأجنبية بشروط تفضيلية لم تُتَح لبقية المتنافسين، "
        "ودون توفير معلومات موحدة عن الأعمال المطلوبة لجميع الراغبين في التعامل.",
    ),
    (
        "المبلغ المطالب به",
        "إجمالي الدفعة المستحقة: 1,350,000 ريال (مليون وثلاثمائة وخمسون ألف ريال). "
        "نأمل التكرم بالموافقة على صرف المستحقات وفق ما تقدم.",
    ),
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Amiri", "", str(FONT))
    pdf.set_text_shaping(True)

    def line(text: str, h: float) -> None:
        pdf.multi_cell(0, h, text, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Amiri", size=20)
    line(HEADING, 12)
    pdf.ln(3)

    pdf.set_font("Amiri", size=12)
    for field in FIELDS:
        line(field, 8)
    pdf.ln(4)

    for title, body in SECTIONS:
        pdf.set_font("Amiri", size=15)
        line(title, 10)
        pdf.set_font("Amiri", size=12)
        line(body, 8)
        pdf.ln(3)

    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

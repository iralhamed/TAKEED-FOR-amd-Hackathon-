"""Stage 2 — Law digitization with Claude (one-time).

Claude reads a chunk of extracted legislation text and returns structured
articles. It NEVER sees the raw PDF — only the text our parser already
extracted — and it is instructed to copy each article's text *verbatim* from
that input, not to correct or rewrite the Arabic. The verbatim checker
(anti-hallucination #1) enforces this downstream.

Output is constrained to a JSON schema via `output_config.format`, so Claude
cannot free-text around the structure. We stream the response because Arabic
verbatim reproduction can be a large output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from backend.config import settings

# Opus 4.8 pricing, USD per 1M tokens (for the cost estimate we print).
_PRICE_IN_PER_M = 5.0
_PRICE_OUT_PER_M = 25.0
_PRICE_CACHE_READ_PER_M = 0.5

_SYSTEM_PROMPT = """\
أنت مساعد متخصص في رقمنة الأنظمة الحكومية السعودية (نظام المنافسات والمشتريات الحكومية ولائحته التنفيذية).

سيصلك نص مُستخرَج آلياً من ملف PDF. قد يحتوي النص على تشوهات ناتجة عن الاستخراج (ترتيب أرقام غير معتاد، مسافات زائدة، أحرف متقطعة). مهمتك ليست تصحيح النص.

القواعد الصارمة:
1. قسّم النص إلى أحكام مستقلة. كل حكم هو إمّا مادة من (النظام) أو فقرة/حكم من (اللائحة التنفيذية).
2. حقل `text` يجب أن يكون نسخة حرفية (verbatim) مطابقة تماماً لما ورد في النص المُدخَل — انسخ الأحرف كما هي بما في ذلك أي تشوهات. ممنوع إعادة الصياغة أو التلخيص أو الدمج أو إضافة نقاط (...) أو تصحيح الإملاء.
3. `title`: مسمّى الحكم كما يظهر، مع توضيح مصدره، مثل: "المادة الثالثة (النظام)" أو "المادة الثالثة (اللائحة)".
4. `chapter`: عنوان الباب أو الفصل الذي يقع تحته الحكم إن كان ظاهراً، وإلا اتركه فارغاً "".
5. `keywords`: من ٣ إلى ٦ كلمات مفتاحية عربية تلخّص موضوع الحكم (للبحث فقط، وليست جزءاً من النص الحرفي).
6. تجاهل العناوين المجردة وأرقام الصفحات والفهارس؛ استخرج الأحكام الموضوعية فقط.
7. لا تخترع أي نص غير موجود في المُدخَل.
"""

# JSON schema for structured output. additionalProperties:false is required.
_ARTICLES_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "text": {"type": "string"},
                    "chapter": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "text", "chapter", "keywords"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["articles"],
    "additionalProperties": False,
}


@dataclass
class ArticleDraft:
    title: str
    text: str
    chapter: str
    keywords: list[str]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    def add(self, u: anthropic.types.Usage) -> None:
        self.input_tokens += u.input_tokens or 0
        self.output_tokens += u.output_tokens or 0
        self.cache_read_input_tokens += getattr(u, "cache_read_input_tokens", 0) or 0

    def add_usage(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * _PRICE_IN_PER_M
            + self.output_tokens / 1_000_000 * _PRICE_OUT_PER_M
            + self.cache_read_input_tokens / 1_000_000 * _PRICE_CACHE_READ_PER_M
        )


@dataclass
class DigitizeResult:
    articles: list[ArticleDraft] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # settings.anthropic_api_key overrides; otherwise the SDK reads
        # ANTHROPIC_API_KEY / an ant profile from the environment.
        key = settings.anthropic_api_key or None
        _client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    return _client


def digitize_chunk(text: str, model: str | None = None) -> DigitizeResult:
    """Send one chunk of extracted legislation text to Claude for structuring.

    Returns the article drafts plus token usage. Raises on API errors.
    """
    client = _get_client()
    model = model or settings.anthropic_model

    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "disabled"},  # mechanical copy task; keep it cheap
        system=_SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": _ARTICLES_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    "النص المُستخرَج التالي هو جزء من الوثيقة. استخرج منه الأحكام "
                    "بصيغة JSON وفق التعليمات، مع نسخ حقل text حرفياً:\n\n"
                    f"<source>\n{text}\n</source>"
                ),
            }
        ],
    ) as stream:
        message = stream.get_final_message()

    result = DigitizeResult()
    result.usage.add(message.usage)

    raw = next((b.text for b in message.content if b.type == "text"), None)
    if raw is None:
        return result

    data = json.loads(raw)
    for item in data.get("articles", []):
        result.articles.append(
            ArticleDraft(
                title=item.get("title", "").strip(),
                text=item.get("text", ""),
                chapter=(item.get("chapter") or "").strip(),
                keywords=[k for k in item.get("keywords", []) if k],
            )
        )
    return result

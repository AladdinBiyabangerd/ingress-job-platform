"""CV parser (Phase 1.1–1.7): OCR text extract + rules + AI #1 fallback.

Text extract (+ Tesseract for scans) + regex + skill dictionary / techstack
patterns; LLM only when rules confidence is low (plan §5.1). Profile shape
follows plan §5.2.
"""

from __future__ import annotations

from worker.cv_parse.ai_fallback import LOW_CONFIDENCE, maybe_ai_fallback
from worker.cv_parse.quality import assess as assess_quality
from worker.cv_parse.pipeline import PARSER_VERSION, parse_bytes, parse_text
from worker.cv_parse.text import ExtractResult, extract, extract_text, unsupported_reason

__all__ = [
    "LOW_CONFIDENCE",
    "PARSER_VERSION",
    "ExtractResult",
    "assess_quality",
    "extract",
    "extract_text",
    "maybe_ai_fallback",
    "parse_bytes",
    "parse_text",
    "unsupported_reason",
]

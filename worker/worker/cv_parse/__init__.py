"""Rules-only CV parser (Phase 1.1 + OCR text extract).

Text extract (+ Tesseract for scans) + regex + skill dictionary / techstack
patterns. No AI #1. Profile shape follows plan §5.2.
"""

from __future__ import annotations

from worker.cv_parse.pipeline import PARSER_VERSION, parse_bytes, parse_text
from worker.cv_parse.text import ExtractResult, extract, extract_text, unsupported_reason

__all__ = [
    "PARSER_VERSION",
    "ExtractResult",
    "extract",
    "extract_text",
    "parse_bytes",
    "parse_text",
    "unsupported_reason",
]

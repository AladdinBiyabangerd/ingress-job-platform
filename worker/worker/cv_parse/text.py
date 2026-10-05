"""Pull plain text from CV file bytes (PDF / DOCX / images / plain text).

Digital extract first; Tesseract OCR for image uploads and low-text PDFs
(plan §5.1). No AI #1.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from worker.cv_parse.ocr import (
    MIN_DIGITAL_PDF_CHARS,
    ocr_enabled,
    ocr_env_enabled,
    ocr_image_bytes,
    ocr_pdf_bytes,
)

_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")

_TEXT_EXTS = {".txt", ".md", ".text"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif"}
_LEGACY_EXTS = {".doc", ".rtf", ".odt"}


@dataclass(frozen=True)
class ExtractResult:
    text: str
    source: str = ""  # text | pdf | docx | ocr | pdf+ocr
    error: str | None = None


def unsupported_reason(filename: str = "", content_type: str = "") -> str | None:
    """Return a short reason when extraction is not supported, else None."""
    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    if ext == ".doc" or ("msword" in ctype and "openxml" not in ctype):
        return "doc_legacy_not_supported"
    if ext in {".rtf", ".odt"}:
        return "format_not_supported"
    if _is_image(ext, ctype):
        if not ocr_env_enabled():
            return "ocr_disabled"
        if not ocr_enabled():
            return "ocr_unavailable"
        return None
    if ext in _LEGACY_EXTS:
        return "format_not_supported"
    return None


def extract_text(data: bytes, filename: str = "", content_type: str = "") -> str:
    """Extract UTF-8 text from CV bytes. Empty string when nothing readable."""
    return extract(data, filename=filename, content_type=content_type).text


def extract(data: bytes, filename: str = "", content_type: str = "") -> ExtractResult:
    """Extract text and report which path produced it (digital vs OCR)."""
    if not data:
        return ExtractResult(text="", source="", error="empty_file")
    reason = unsupported_reason(filename, content_type)
    if reason:
        return ExtractResult(text="", source="", error=reason)

    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()

    if _is_image(ext, ctype):
        text = _normalize(ocr_image_bytes(data))
        if text:
            return ExtractResult(text=text, source="ocr")
        return ExtractResult(text="", source="ocr", error="ocr_empty")

    if ext in _PDF_EXTS or "pdf" in ctype or data[:4] == b"%PDF":
        return _extract_pdf(data)

    if ext in _DOCX_EXTS or "wordprocessingml" in ctype or data[:2] == b"PK":
        text = _from_docx(data)
        if text:
            return ExtractResult(text=text, source="docx")
        # ZIP that isn't a readable docx — try nothing further.
        if ext in _DOCX_EXTS or "wordprocessingml" in ctype:
            return ExtractResult(text="", source="docx", error="docx_empty")
        # Sniffed PK without docx hint: fall through to text decode below.

    if ext in _TEXT_EXTS or ctype.startswith("text/"):
        text = _normalize(_decode(data))
        return ExtractResult(text=text, source="text", error=None if text else "text_empty")

    if data[:2] == b"PK":
        return ExtractResult(text="", source="docx", error="docx_empty")

    text = _normalize(_decode(data))
    return ExtractResult(text=text, source="text", error=None if text else "text_empty")


def _is_image(ext: str, ctype: str) -> bool:
    return ext in _IMAGE_EXTS or ctype.startswith("image/")


def _extract_pdf(data: bytes) -> ExtractResult:
    digital = _from_pdf(data)
    if len(digital) >= MIN_DIGITAL_PDF_CHARS:
        return ExtractResult(text=digital, source="pdf")
    if not ocr_env_enabled():
        if digital:
            return ExtractResult(text=digital, source="pdf")
        return ExtractResult(text="", source="pdf", error="ocr_disabled")
    if not ocr_enabled():
        if digital:
            return ExtractResult(text=digital, source="pdf")
        return ExtractResult(text="", source="pdf", error="ocr_unavailable")
    ocr_text = _normalize(ocr_pdf_bytes(data))
    if ocr_text:
        source = "pdf+ocr" if digital else "ocr"
        # Prefer OCR when digital extract was too thin.
        return ExtractResult(text=ocr_text, source=source)
    if digital:
        return ExtractResult(text=digital, source="pdf")
    return ExtractResult(text="", source="ocr", error="ocr_empty")


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ").replace("\ufeff", "")
    lines = [_WS.sub(" ", line).rstrip() for line in text.split("\n")]
    return _BLANK.sub("\n\n", "\n".join(lines)).strip()


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            chunk = page.extract_text() or ""
        except Exception:
            chunk = ""
        if chunk.strip():
            parts.append(chunk)
    return _normalize("\n".join(parts))


def _from_docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception:
        return ""
    parts: list[str] = []
    for para in doc.paragraphs:
        line = (para.text or "").strip()
        if line:
            parts.append(line)
    for table in doc.tables:
        for row in table.rows:
            cells = [((cell.text or "").strip()) for cell in row.cells]
            cells = [c for c in cells if c]
            if cells:
                parts.append(" | ".join(cells))
    return _normalize("\n".join(parts))

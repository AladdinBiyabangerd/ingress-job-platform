"""Pull plain text from CV file bytes (PDF / DOCX / plain text). No OCR yet."""

from __future__ import annotations

import io
import re
from pathlib import Path

_WS = re.compile(r"[ \t]+")
_BLANK = re.compile(r"\n{3,}")

_TEXT_EXTS = {".txt", ".md", ".text"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}
# .doc / images / scans need LibreOffice or Tesseract — not in this prototype.
_UNSUPPORTED = {".doc", ".rtf", ".odt", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif"}


def unsupported_reason(filename: str = "", content_type: str = "") -> str | None:
    """Return a short reason when extraction is not supported, else None."""
    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    if ext in _UNSUPPORTED or "image/" in ctype:
        return "ocr_or_legacy_format_not_supported"
    if ext == ".doc" or ("msword" in ctype and "openxml" not in ctype):
        return "doc_legacy_not_supported"
    return None


def extract_text(data: bytes, filename: str = "", content_type: str = "") -> str:
    """Extract UTF-8 text from CV bytes. Empty string when nothing readable."""
    if not data:
        return ""
    reason = unsupported_reason(filename, content_type)
    if reason:
        return ""
    ext = Path(filename or "").suffix.lower()
    ctype = (content_type or "").lower()
    if ext in _PDF_EXTS or "pdf" in ctype:
        return _from_pdf(data)
    if ext in _DOCX_EXTS or "wordprocessingml" in ctype:
        return _from_docx(data)
    if ext in _TEXT_EXTS or ctype.startswith("text/"):
        return _normalize(_decode(data))
    # Sniff: PDF magic, ZIP/DOCX magic, else try decode as text.
    if data[:4] == b"%PDF":
        return _from_pdf(data)
    if data[:2] == b"PK":
        return _from_docx(data)
    return _normalize(_decode(data))


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

    doc = Document(io.BytesIO(data))
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

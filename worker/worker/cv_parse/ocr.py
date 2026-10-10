"""Tesseract OCR for scanned CV images and image-only PDFs (plan §5.1).

Deterministic text extraction only — no AI #1. Soft-fails when Tesseract
or optional deps are missing so rules parsing still works for digital CVs.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from functools import lru_cache

log = logging.getLogger("worker.cv_parse.ocr")

# Below this many extracted chars, treat a PDF as likely scanned / image-only.
MIN_DIGITAL_PDF_CHARS = 40
# Cap pages so a huge scan cannot stall the worker.
MAX_OCR_PAGES = 15
DEFAULT_LANG = "eng"
DEFAULT_SCALE = 2.0


def ocr_env_enabled() -> bool:
    raw = (os.environ.get("CV_OCR_ENABLED") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


@lru_cache(maxsize=1)
def tesseract_available() -> bool:
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_unavailable_reason() -> str | None:
    """Why OCR cannot run right now (None when it can). Never raises."""
    if not ocr_env_enabled():
        return "disabled"
    if shutil.which("tesseract") is None:
        return "tesseract_missing"
    for mod in ("pytesseract", "PIL", "pypdfium2"):
        try:
            __import__(mod)
        except Exception:
            return f"python_dep_missing:{mod}"
    return None if tesseract_available() else "tesseract_unusable"


def ocr_enabled() -> bool:
    return ocr_env_enabled() and tesseract_available()


def ocr_lang() -> str:
    lang = (os.environ.get("CV_OCR_LANG") or DEFAULT_LANG).strip()
    return lang or DEFAULT_LANG


def reset_ocr_cache() -> None:
    """Test helper: clear cached Tesseract probe."""
    tesseract_available.cache_clear()


def ocr_image_bytes(data: bytes, *, lang: str | None = None) -> str:
    """OCR a single image (PNG/JPEG/TIFF/WebP/GIF). Empty string on failure."""
    if not data or not ocr_enabled():
        return ""
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        log.warning("ocr deps missing (pillow/pytesseract)")
        return ""
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img, lang=lang or ocr_lang())
        return (text or "").strip()
    except Exception as exc:
        log.warning("ocr_image_bytes failed: %s", exc)
        return ""


def ocr_pdf_bytes(data: bytes, *, lang: str | None = None) -> str:
    """Rasterize PDF pages and OCR them. Empty string on failure."""
    if not data or not ocr_enabled():
        return ""
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError:
        log.warning("ocr deps missing (pypdfium2/pytesseract)")
        return ""
    try:
        pdf = pdfium.PdfDocument(data)
    except Exception as exc:
        log.warning("ocr_pdf open failed: %s", exc)
        return ""
    parts: list[str] = []
    try:
        page_count = len(pdf)
        limit = min(page_count, MAX_OCR_PAGES)
        scale = _render_scale()
        used_lang = lang or ocr_lang()
        for index in range(limit):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                chunk = pytesseract.image_to_string(pil_image, lang=used_lang) or ""
            except Exception as exc:
                log.warning("ocr_pdf page %s failed: %s", index, exc)
                continue
            if chunk.strip():
                parts.append(chunk.strip())
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return "\n\n".join(parts).strip()


def _render_scale() -> float:
    raw = (os.environ.get("CV_OCR_SCALE") or "").strip()
    if not raw:
        return DEFAULT_SCALE
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_SCALE
    return max(1.0, min(4.0, value))

"""Azerbaijani / Turkish case folding for CV heading and date tokens.

Python's default ``str.lower()`` maps ``I`` → ``i`` and ``İ`` → ``i`` + combining
dot, which breaks aliases like ``bacarıqlar`` and month names like ``iyul``.
"""

from __future__ import annotations

_AZ_MAP = str.maketrans(
    {
        "İ": "i",
        "I": "ı",
        "Ə": "ə",
        "Ö": "ö",
        "Ü": "ü",
        "Ğ": "ğ",
        "Ç": "ç",
        "Ş": "ş",
    }
)


def fold_az(text: str) -> str:
    """Lowercase with AZ/TR capital folding; strip leftover combining dots."""
    if not text:
        return ""
    return text.translate(_AZ_MAP).lower().replace("\u0307", "")

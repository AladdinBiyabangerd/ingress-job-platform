"""PII redaction before any LLM call (plan §10.4 / §11 ai_gateway)."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
_PHONE = re.compile(r"(?:\+|00)?[\d][\d\s\-().]{6,22}\d")
_URL = re.compile(
    r"(?i)\b(?:https?://)?(?:www\.)?(?:linkedin\.com/in/|github\.com/)"
    r"[^\s<>\"']+"
)
# Street-like lines: number + street words, or AZ-style "küç." / "pr." fragments.
_ADDRESS = re.compile(
    r"(?im)^(?=.*\d)(?=.*(?:st\.|street|ave\.|avenue|rd\.|road|blvd|"
    r"küç\.?|kuc\.?|pr\.|prospekt|ул\.|улица|d\.|мкр))\s*.+$"
)


def mask_pii(text: str, *, known: dict | None = None) -> str:
    """Replace name/email/phone/address/profile URLs with placeholders.

    ``known`` may include contact fields already extracted by rules so those
    exact strings are masked even when regex would miss them.
    """
    body = text or ""
    known = known or {}

    for key, token in (
        ("email", "[EMAIL]"),
        ("phone", "[PHONE]"),
        ("full_name", "[NAME]"),
        ("city", "[CITY]"),
    ):
        value = str(known.get(key) or "").strip()
        if value:
            body = re.sub(re.escape(value), token, body, flags=re.IGNORECASE)

    links = known.get("links") if isinstance(known.get("links"), dict) else {}
    for key in ("linkedin", "github", "portfolio"):
        value = str(links.get(key) or "").strip()
        if value:
            body = re.sub(re.escape(value), "[URL]", body, flags=re.IGNORECASE)
            bare = re.sub(r"(?i)^https?://", "", value).rstrip("/")
            if bare:
                body = re.sub(re.escape(bare), "[URL]", body, flags=re.IGNORECASE)

    body = _EMAIL.sub("[EMAIL]", body)
    body = _URL.sub("[URL]", body)
    body = _PHONE.sub("[PHONE]", body)
    body = _ADDRESS.sub("[ADDRESS]", body)
    return body

"""Contact fields: email, phone, LinkedIn / GitHub / portfolio URLs."""

from __future__ import annotations

import re

import phonenumbers

_EMAIL = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
_LINKEDIN = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?linkedin\.com/in/[a-z0-9\-_%]+/?"
)
_GITHUB = re.compile(
    r"(?i)(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9](?:[a-zA-Z0-9\-]|/(?!$)){0,38}"
)
_URL = re.compile(
    r"(?i)\b(?:https?://)?(?:www\.)?[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+(?:/[^\s<>\"']*)?"
)
_NAME_LINE = re.compile(
    r"^[A-ZА-ЯƏÖÜĞÇŞİ][\wА-Яа-яƏəÖöÜüĞğÇçŞşİı'’\-]+"
    r"(?:\s+[A-ZА-ЯƏÖÜĞÇŞİ][\wА-Яа-яƏəÖöÜüĞğÇçŞşİı'’\-]+){0,3}$"
)
_PHONE_CANDIDATE = re.compile(r"(?:\+|00)?[\d][\d\s\-().]{6,22}\d")

_SKIP_HOST = re.compile(
    r"(?i)(?:linkedin\.com|github\.com|gitlab\.com|bitbucket\.org|"
    r"facebook\.com|twitter\.com|x\.com|instagram\.com|mailto:|"
    r"google\.com|schemas\.|w3\.org)"
)


def extract_contact(text: str, *, default_region: str = "AZ") -> dict:
    email = _first(_EMAIL.findall(text))
    phone = _best_phone(text, default_region)
    linkedin = _normalize_url(_first(_LINKEDIN.findall(text)))
    github = _normalize_github(_first(_GITHUB.findall(text)))
    portfolio = _portfolio(text, linkedin, github)
    full_name = _guess_name(text, email)
    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "links": {
            "linkedin": linkedin,
            "github": github,
            "portfolio": portfolio,
        },
        "city": "",
        "country": "",
    }


def _first(items: list[str]) -> str:
    return items[0].strip() if items else ""


def _normalize_url(url: str) -> str:
    url = (url or "").strip().rstrip(".,);")
    if not url:
        return ""
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url


def _normalize_github(url: str) -> str:
    url = _normalize_url(url)
    if not url:
        return ""
    m = re.match(r"(?i)(https?://(?:www\.)?github\.com/[a-zA-Z0-9\-]+)", url)
    return m.group(1) if m else url


def _best_phone(text: str, region: str) -> str:
    best = ""
    best_len = 0
    for raw in _PHONE_CANDIDATE.findall(text):
        candidate = raw.strip()
        if "@" in candidate:
            continue
        parsed = None
        try:
            parsed = phonenumbers.parse(candidate, region)
        except phonenumbers.NumberParseException:
            try:
                parsed = phonenumbers.parse(candidate, None)
            except phonenumbers.NumberParseException:
                continue
        if not phonenumbers.is_possible_number(parsed):
            continue
        if not phonenumbers.is_valid_number(parsed) and not candidate.startswith("+994"):
            digits = re.sub(r"\D", "", candidate)
            if not (digits.startswith("994") and len(digits) >= 12):
                continue
        formatted = phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        if len(formatted) > best_len:
            best = formatted
            best_len = len(formatted)
    return best


def _portfolio(text: str, linkedin: str, github: str) -> str:
    skip = {linkedin.lower(), github.lower()}
    # Strip emails so local-parts / domains are not mistaken for websites.
    cleaned = _EMAIL.sub(" ", text or "")
    for match in _URL.finditer(cleaned):
        raw = match.group(0).rstrip(".,);")
        if _SKIP_HOST.search(raw):
            continue
        # Prefer explicit http(s); bare hosts need a real public TLD.
        if not re.match(r"(?i)^https?://", raw):
            host = raw.split("/", 1)[0].lower()
            if not re.search(
                r"\.(?:com|net|org|io|dev|az|ru|co|me|app|ai|tech|info|xyz)$",
                host,
            ):
                continue
        url = _normalize_url(raw)
        if url.lower() in skip:
            continue
        host = re.sub(r"(?i)^https?://(?:www\.)?", "", url).split("/", 1)[0]
        if "." not in host:
            continue
        return url
    return ""


def _guess_name(text: str, email: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:8]:
        if email and email.lower() in line.lower():
            continue
        if _EMAIL.search(line) or _PHONE_CANDIDATE.fullmatch(line):
            continue
        if _URL.search(line) and " " not in line:
            continue
        if len(line) > 60 or len(line) < 3:
            continue
        if _NAME_LINE.match(line) or (
            " " in line
            and not line.endswith(":")
            and not re.search(r"\d", line)
            and len(line.split()) <= 4
        ):
            low = line.lower()
            if any(
                key in low
                for key in (
                    "experience",
                    "education",
                    "skills",
                    "təcrübə",
                    "təhsil",
                    "bacarıq",
                    "опыт",
                    "образование",
                    "навыки",
                    "curriculum",
                    "resume",
                    "cv",
                )
            ):
                continue
            return line[:120]
    return ""

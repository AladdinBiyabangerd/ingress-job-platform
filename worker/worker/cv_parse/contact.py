"""Contact fields: email, phone, LinkedIn / GitHub / portfolio URLs."""

from __future__ import annotations

import re

import phonenumbers

from worker.cv_parse.sections import _heading_name

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


_LOCATION_LINE = re.compile(
    r"(?i)^\s*([A-Za-zА-Яа-яƏəÖöÜüĞğÇçŞşİı'’\-\s]{2,40})\s*,\s*"
    r"([A-Za-zА-Яа-яƏəÖöÜüĞğÇçŞşİı'’\-\s]{2,40})\s*$"
)


def extract_contact(text: str, *, default_region: str = "AZ") -> dict:
    email = _first(_EMAIL.findall(text))
    phone = _best_phone(text, default_region)
    linkedin = _normalize_url(_first(_LINKEDIN.findall(text)))
    github = _normalize_github(_first(_GITHUB.findall(text)))
    portfolio = _portfolio(text, linkedin, github)
    full_name = _guess_name(text, email)
    city, country = _guess_location(text)
    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "links": {
            "linkedin": linkedin,
            "github": github,
            "portfolio": portfolio,
        },
        "city": city,
        "country": country,
    }


_LOC_REJECT = re.compile(
    r"(?i)\b(university|universitet|college|institute|school|phd|bsc|msc|bachelor|master|"
    r"degree|thesis|engineer|developer|manager|intern|designer|analyst|inc|llc|ltd|corp|"
    r"company|science|engineering|présent|present)\b"
)


def _guess_location(text: str) -> tuple[str, str]:
    """Best-effort city/country from 'City, Country' lines in the header block.

    Only lines above the first section heading count, so education / job rows
    ("PhD Princeton University, Computer Science") are never read as a place.
    """
    from worker.cv_parse.sections import _heading_name

    for raw in (text or "").splitlines()[:14]:
        line = re.sub(r"^[^\w]+", "", raw.strip(), flags=re.UNICODE)  # drop 📍 / bullets
        if line and _heading_name(line):
            break
        if not line or "@" in line or "http" in line.lower() or re.search(r"\d", line):
            continue
        if _LOC_REJECT.search(line) or line.endswith((".", "!", ":")) or len(line) > 50:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and all(2 <= len(p) <= 40 for p in parts[-2:]):
            return parts[-2][:80], parts[-1][:80]
        low = line.lower()
        if any(k in low for k in ("email", "tel", "phone", "telefon", "linkedin", "github", "veb", "сайт")):
            continue
        m = _LOCATION_LINE.match(line)
        if not m:
            continue
        city = re.sub(r"\s+", " ", m.group(1)).strip()[:80]
        country = re.sub(r"\s+", " ", m.group(2)).strip()[:80]
        if city and country and city.lower() != country.lower():
            return city, country
    return "", ""


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
        # "Jane Doe Email: jane@x.com" - keep only the part before the label.
        head = re.split(
            r"(?i)\b(?:e-?mail|mobile|phone|tel|telefon|linkedin|github|web(?:site)?)\s*:", line
        )[0].strip()
        if head and head != line and _NAME_LINE.match(head):
            return head[:120]
        if len(line) < 40 and _heading_name(line):
            continue  # a section heading is never the name
        line = re.sub(r"(?<=[a-zü])(?:RESUME|CV)$", "", line).strip()
        if re.search(r"\s[·•|]\s", line):
            # "Jan Küster · Consultant · Bremen · mail" header strip: first segment is the name.
            first = re.split(r"\s[·•|]\s", line)[0].strip()
            if 3 <= len(first) <= 40 and 1 <= len(first.split()) <= 4 and not re.search(r"[\d@]", first):
                if _NAME_LINE.match(first) or " " in first:
                    return first
        if email and email.lower() in line.lower():
            continue
        if _EMAIL.search(line) or _PHONE_CANDIDATE.fullmatch(line):
            continue
        if _URL.search(line) and " " not in line:
            continue
        line = _collapse_spaced_name(line)
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
                    "developer",
                    "engineer",
                    "разработчик",
                    "инженер",
                )
            ):
                continue
            return line[:120]
    return ""


def _collapse_spaced_name(line: str) -> str:
    """Join PDF letter-spaced names: 'S Ə MA S Ə F Ə ROVA' → 'SƏMA SƏFƏROVA'."""
    parts = line.split()
    if len(parts) < 3:
        return line
    singles = sum(1 for p in parts if len(p) == 1)
    if singles < max(2, len(parts) * 0.4):
        return line
    words: list[str] = []
    buf: list[str] = []
    for part in parts:
        buf.append(part)
        if len(part) > 1:
            words.append("".join(buf))
            buf = []
    if buf:
        if words:
            words[-1] = words[-1] + "".join(buf)
        else:
            words.append("".join(buf))
    return " ".join(words)

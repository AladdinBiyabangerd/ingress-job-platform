"""Layout-agnostic quality score for a rules-parsed CV profile.

The score looks only at the *output* (name, contact, headline, dated jobs with
title/company, education, skills, section coverage, sanity checks) - never at
which template/style the CV came from. ``assess`` returns the score, a list of
issue codes and the set of weak profile parts the AI fallback should repair.
"""

from __future__ import annotations

import os
import re
from datetime import date

from worker.cv_parse.text import looks_garbled

QUALITY_THRESHOLD = 0.65
QUALITY_VERSION = "q1"

# issue code -> weak profile part (what AI may repair)
ISSUE_PART = {
    "name_missing": "contact",
    "name_suspicious": "contact",
    "contact_missing": "contact",
    "city_is_education": "contact",
    "headline_missing": "headline",
    "headline_suspicious": "headline",
    "work_missing": "work_history",
    "work_undated": "work_history",
    "work_garbage_title": "work_history",
    "work_missing_company": "work_history",
    "work_date_order": "work_history",
    "work_future_date": "work_history",
    "work_absurd_date": "work_history",
    "placeholder_text": "",
    "education_missing": "education",
    "skills_thin": "skills",
    "text_too_short": "",
    "text_garbled": "",
}
# Unreadable input: AI cannot recover anything from it, so no AI call is made.
NO_AI = {"text_too_short", "text_garbled"}
# Issues that force the AI regardless of the numeric score.
CRITICAL = {
    "work_missing", "work_garbage_title", "work_date_order", "city_is_education",
    "work_absurd_date", "placeholder_text",
}
ALL_PARTS = ("contact", "headline", "work_history", "education", "skills")
PLACEHOLDER_SCORE_CAP = 0.45

# Template sample text that was never replaced by real data (Lorem ipsum, "Month Year", ...).
_PLACEHOLDER_STRONG = re.compile(r"(?i)lorem ipsum|dolor sit amet|consectetur adipiscing")
_PLACEHOLDER_WEAK = re.compile(
    r"(?i)\b(?:month|mon\.?)\s+(?:year|yyyy|20xx)\b|\b(?:year|yyyy)\s*[–-]\s*(?:year|yyyy)\b|\b20xx\b|"
    r"\bjob title\b|\bposition title\b|\bcompany (?:name|abc)\b|\bname of university\b|"
    r"\bcity,\s*state\b|\b(?:first|your)\s+(?:last|name)\b|\bemail@email\.com\b|\byour[_ ]?(?:id|email|name)\b|"
    r"\bdegree,\s*(?:institution|major)\b|\bsub-?achievement\b|\bresum[eé] title\b"
)
# A 4-digit "year" that no CV date can be (1000-1949 or 2100-2999), e.g. 18xx / 2333.
_ABSURD_YEAR = re.compile(r"(?<!\d)(?:1[0-8]\d{2}|19[0-4]\d|2[1-9]\d{2})(?!\d)")
_DATE_FRAGMENT = re.compile(r"^\W*\d{1,4}\s*[/.\-]\s*\d{1,4}\W*$")


def is_placeholder_text(text: str) -> bool:
    """True when the CV still holds template sample text instead of real data."""
    sample = text or ""
    lines = [ln for ln in sample.splitlines() if ln.strip()]
    if lines and sum(1 for ln in lines if _PLACEHOLDER_STRONG.search(ln)) / len(lines) >= 0.25:
        return True  # a stray "lorem ipsum" bullet is not enough; a quarter of the lines is
    return len(_PLACEHOLDER_WEAK.findall(sample)) >= 4

_DEGREE = re.compile(
    r"(?i)\b(bsc|msc|phd|b\.?s\.?|m\.?s\.?|bachelor|master|bakalavr|magistr|бакалавр|магистр|"
    r"university|universitet|университет|college|institute|faculty)\b"
)
_DATE_LIKE = re.compile(r"(?i)^\W*(\d{4}|(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4})")
_CITY_LIKE = re.compile(r"^[^\W\d_][\w .'’-]+,\s*[A-Za-z .]{2,30}$")
_BULLET = "-•●*–—◦◆▪■▸►·"
_YM = re.compile(r"^(\d{4})-(\d{2})$")


def threshold() -> float:
    raw = os.environ.get("CV_QUALITY_THRESHOLD", "").strip()
    if not raw:
        return QUALITY_THRESHOLD
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return QUALITY_THRESHOLD


def _s(v: object) -> str:
    return str(v or "").strip()


def _garbage_title(title: str, company: str) -> bool:
    t = _s(title)
    if not t or len(t) > 100 or len(t.split()) > 12:
        return True
    if t[0] in _BULLET or _DATE_LIKE.match(t) or _DATE_FRAGMENT.match(t) or _ABSURD_YEAR.search(t):
        return True
    if _DEGREE.search(t) or (_CITY_LIKE.match(t) and len(t.split()) <= 4 and "," in t):
        return True
    if t.endswith(".") and len(t.split()) > 6:
        return True
    return bool(company) and t.lower() == _s(company).lower()


def _ym(v: object) -> tuple[int, int] | None:
    m = _YM.match(_s(v))
    return (int(m.group(1)), int(m.group(2))) if m else None


def assess(profile: dict, text: str = "") -> dict:
    """Return {"score": 0..1, "issues": [...], "weak": [...], "threshold": x, "needs_ai": bool}."""
    issues: list[str] = []
    score = 0.0
    contact = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    meta = profile.get("parse_meta") if isinstance(profile.get("parse_meta"), dict) else {}
    sections = set(meta.get("sections_found") or [])

    if len((text or "").strip()) < 120:
        issues.append("text_too_short")
    elif looks_garbled(text):
        issues.append("text_garbled")
    elif is_placeholder_text(text):
        issues.append("placeholder_text")

    # name (0.10)
    name = _s(contact.get("full_name"))
    if not name:
        issues.append("name_missing")
    elif "@" in name or re.search(r"\d", name) or len(name.split()) > 5 or _DEGREE.search(name):
        issues.append("name_suspicious")
    else:
        score += 0.10

    # contact (0.10)
    if contact.get("email") or contact.get("phone"):
        score += 0.10
    else:
        issues.append("contact_missing")
    city = _s(contact.get("city") or contact.get("location"))
    if city and _DEGREE.search(city):
        issues.append("city_is_education")

    # headline (0.08)
    headline = _s(profile.get("headline"))
    if not headline:
        issues.append("headline_missing")
    elif len(headline) > 100 or _DATE_LIKE.match(headline) or "@" in headline or _DEGREE.search(headline):
        issues.append("headline_suspicious")
    else:
        score += 0.08

    # work (0.35)
    work = [j for j in (profile.get("work_history") or []) if isinstance(j, dict)]
    if not work:
        issues.append("work_missing")
    else:
        good = 0
        absurd = 0
        garbage = no_company = undated = order = future = 0
        today = date.today()
        for job in work:
            ok = True
            if _garbage_title(job.get("title"), job.get("company")):
                garbage += 1
                ok = False
            if not _s(job.get("company")):
                no_company += 1
                ok = False
            start, end = _ym(job.get("start")), _ym(job.get("end"))
            if any(y and not 1950 <= y[0] <= date.today().year + 1 for y in (start, end)) or _ABSURD_YEAR.search(
                f"{_s(job.get('company'))} {_s(job.get('title'))}"
            ):
                absurd += 1
                ok = False
            if not start:
                undated += 1
                ok = False
            else:
                if (start[0], start[1]) > (today.year, today.month):
                    future += 1
                    ok = False
                if end and end < start:
                    order += 1
                    ok = False
            good += ok
        score += 0.35 * (good / len(work))
        for code, n in (
            ("work_absurd_date", absurd),
            ("work_garbage_title", garbage),
            ("work_missing_company", no_company),
            ("work_undated", undated),
            ("work_date_order", order),
            ("work_future_date", future),
        ):
            if n:
                issues.append(code)

    # education (0.12)
    edu = [e for e in (profile.get("education") or []) if isinstance(e, dict)]
    if any(_s(e.get("degree")) or _s(e.get("school")) for e in edu):
        score += 0.12
    else:
        issues.append("education_missing")

    # skills (0.15)
    n_sk = len(profile.get("skills") or [])
    if n_sk >= 6:
        score += 0.15
    elif n_sk >= 3:
        score += 0.10
        issues.append("skills_thin")
    else:
        score += 0.04 if n_sk else 0
        issues.append("skills_thin")

    # section coverage (0.10)
    score += 0.10 * len(sections & {"experience", "education", "skills"}) / 3

    if "placeholder_text" in issues:
        score = min(score, PLACEHOLDER_SCORE_CAP)  # sample text is not a real CV: always low quality
    score = round(max(0.0, min(1.0, score)), 2)
    th = threshold()
    weak = sorted({ISSUE_PART[i] for i in issues if ISSUE_PART.get(i)})
    if "placeholder_text" in issues:
        weak = sorted(ALL_PARTS)
    critical = [i for i in issues if i in CRITICAL]
    unreadable = any(i in NO_AI for i in issues)
    needs_ai = bool((score < th or critical) and (text or "").strip() and not unreadable)
    return {
        "score": score,
        "issues": issues,
        "weak": weak,
        "threshold": th,
        "needs_ai": needs_ai,
        "version": QUALITY_VERSION,
    }

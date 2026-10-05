"""Orchestrate CV → profile JSON (plan §5.2): rules first, AI #1 if low confidence."""

from __future__ import annotations

import re
import sqlite3
from datetime import date

from worker.cv_parse.ai_fallback import maybe_ai_fallback
from worker.cv_parse.contact import extract_contact
from worker.cv_parse.dates import find_ranges, iso_month, merge_years
from worker.cv_parse.sections import split_sections
from worker.cv_parse.text import extract
from worker.techstack import find_stack

PARSER_VERSION = "1.2"

_SENIORITY_PAT = re.compile(
    r"(?i)\b(intern|junior|jr\.?|middle|mid-level|mid\b|senior|sr\.?|lead|principal|staff)\b"
)
_JOB_LINE = re.compile(
    r"(?ix)^\s*(?P<title>.+?)\s+(?:[-–—@|]|at|в|də)\s+(?P<company>.+?)\s*$"
)
_TITLE_COMPANY = re.compile(
    r"(?ix)^\s*(?P<title>[^|,\-–—]{2,80})\s*[,|]\s*(?P<company>.+)$"
)


def parse_bytes(
    data: bytes,
    *,
    filename: str = "",
    content_type: str = "",
    conn: sqlite3.Connection | None = None,
    ai_fallback: bool = True,
) -> dict:
    """Extract text, rules-parse, then optional AI #1 when confidence is low."""
    extracted = extract(data, filename=filename, content_type=content_type)
    profile = parse_text(extracted.text)
    meta = profile.setdefault("parse_meta", {})
    meta["method"] = "rules"
    meta["parser_version"] = PARSER_VERSION
    meta["source"] = "upload"
    if extracted.source:
        meta["text_extract"] = extracted.source
    if extracted.error and not extracted.text:
        meta["confidence"] = 0.0
        meta["error"] = extracted.error
    elif extracted.error:
        meta["extract_warning"] = extracted.error
    if ai_fallback and extracted.text:
        profile = maybe_ai_fallback(profile, extracted.text, conn=conn)
        profile.setdefault("parse_meta", {})["parser_version"] = PARSER_VERSION
    return profile


def parse_text(text: str) -> dict:
    """Rules-only parse of already-extracted CV text → profile JSON."""
    body = (text or "").strip()
    sections = split_sections(body) if body else {}
    contact = extract_contact(body) if body else extract_contact("")
    work_history, dated_jobs = _work_history(sections.get("experience", "") or body)
    total_years = merge_years([(w["start_date"], w["end_date"]) for w in dated_jobs])
    skills = _skills(body, sections, dated_jobs)
    education = _education(sections.get("education", ""))
    languages = _languages(sections.get("languages", ""))
    headline = _headline(body, sections, work_history)
    seniority = _seniority(body, headline, total_years)
    confidence = _confidence(body, sections, contact, dated_jobs, skills)
    return {
        "contact": contact,
        "headline": headline,
        "seniority": seniority,
        "total_years": total_years,
        "work_history": [
            {
                "title": item["title"],
                "company": item["company"],
                "location": item.get("location", ""),
                "start": item["start"],
                "end": item["end"],
                "summary": item.get("summary", ""),
                "skills": item.get("skills", []),
            }
            for item in work_history
        ],
        "skills": skills,
        "languages": languages,
        "education": education,
        "desired_roles": [],
        "preferences": {
            "remote": None,
            "relocation": None,
            "relocation_countries": [],
            "needs_visa_sponsorship": None,
        },
        "salary_expectation": {"min": None, "currency": None, "period": "year"},
        "parse_meta": {
            "method": "rules",
            "confidence": confidence,
            "source": "upload",
            "parser_version": PARSER_VERSION,
            "sections_found": sorted(sections.keys()),
        },
    }


def _headline(text: str, sections: dict[str, str], work: list[dict]) -> str:
    summary = sections.get("summary") or ""
    for line in summary.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 80 and not line.lower().startswith("i am"):
            return line[:120]
    if work and work[0].get("title"):
        return str(work[0]["title"])[:120]
    for line in text.splitlines()[:12]:
        line = line.strip()
        if not line or len(line) > 80:
            continue
        low = line.lower()
        if any(k in low for k in ("@", "http", "linkedin", "github", "tel", "+994")):
            continue
        if re.search(
            r"(?i)\b(developer|engineer|devops|analyst|designer|manager|qa|sre)\b",
            line,
        ):
            return line[:120]
    return ""


def _seniority(text: str, headline: str, total_years: float) -> str:
    sample = f"{headline}\n{text[:2000]}"
    m = _SENIORITY_PAT.search(sample)
    if m:
        token = m.group(1).lower().rstrip(".")
        if token in {"intern"}:
            return "junior"
        if token in {"junior", "jr"}:
            return "junior"
        if token in {"middle", "mid-level", "mid"}:
            return "middle"
        if token in {"senior", "sr"}:
            return "senior"
        if token in {"lead", "principal", "staff"}:
            return "lead"
    if total_years >= 8:
        return "lead"
    if total_years >= 5:
        return "senior"
    if total_years >= 2:
        return "middle"
    if total_years > 0:
        return "junior"
    return ""


def _work_history(experience_text: str) -> tuple[list[dict], list[dict]]:
    if not experience_text.strip():
        return [], []
    blocks = _split_jobs(experience_text)
    history: list[dict] = []
    dated: list[dict] = []
    for block in blocks:
        ranges = find_ranges(block)
        start = end = None
        end_s = None
        if ranges:
            start, end, _start_s, end_s = ranges[0]
        title, company = _title_company(block)
        skills = find_stack(block)
        present = bool(
            end_s
            and re.match(
                r"(?i)present|current|now|hal-hazırda|настоящее",
                end_s,
            )
        )
        item = {
            "title": title,
            "company": company,
            "location": "",
            "start": iso_month(start),
            "end": None if present else iso_month(end),
            "summary": _job_summary(block),
            "skills": skills,
            "start_date": start,
            "end_date": end or date.today(),
            "body": block,
        }
        history.append(item)
        if start and end:
            dated.append(item)
    return history, dated


def _split_jobs(text: str) -> list[str]:
    lines = text.splitlines()
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if find_ranges(line) and current:
            chunks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append(current)
    if len(chunks) <= 1:
        parts = re.split(r"\n\s*\n", text.strip())
        return [p.strip() for p in parts if p.strip()]
    return ["\n".join(c).strip() for c in chunks if "".join(c).strip()]


def _title_company(block: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    for line in lines[:4]:
        if find_ranges(line) and len(line) < 40:
            continue
        m = _JOB_LINE.match(line) or _TITLE_COMPANY.match(line)
        if m:
            return m.group("title").strip()[:120], m.group("company").strip()[:120]
    title = lines[0][:120] if lines else ""
    company = lines[1][:120] if len(lines) > 1 and not find_ranges(lines[1]) else ""
    return title, company


def _job_summary(block: str) -> str:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if not line or find_ranges(line):
            continue
        lines.append(line)
        if len(lines) >= 4:
            break
    return " ".join(lines)[:400]


def _skills(text: str, sections: dict[str, str], jobs: list[dict]) -> list[dict]:
    skills_text = sections.get("skills", "")
    names = find_stack(skills_text) if skills_text else []
    for name in find_stack(text):
        if name not in names:
            names.append(name)
    out: list[dict] = []
    for name in names:
        years = _skill_years(name, jobs)
        out.append(
            {
                "name": name,
                "years": years,
                "level": _level_for_years(years),
                "source": "cv",
            }
        )
    return out


def _skill_years(name: str, jobs: list[dict]) -> float | None:
    ranges: list[tuple[date, date]] = []
    for job in jobs:
        body = job.get("body") or ""
        job_skills = job.get("skills") or []
        if name in job_skills or name.lower() in body.lower():
            start = job.get("start_date")
            end = job.get("end_date")
            if start and end:
                ranges.append((start, end))
    if not ranges:
        return None
    return merge_years(ranges)


def _level_for_years(years: float | None) -> str:
    if years is None:
        return ""
    if years >= 5:
        return "advanced"
    if years >= 2:
        return "intermediate"
    if years > 0:
        return "beginner"
    return ""


def _education(text: str) -> list[dict]:
    if not text.strip():
        return []
    items: list[dict] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        year = None
        for line in lines:
            m = re.search(r"((?:19|20)\d{2})", line)
            if m:
                year = int(m.group(1))
                break
        items.append(
            {
                "degree": lines[0][:120],
                "field": lines[1][:120] if len(lines) > 1 else "",
                "school": lines[2][:120]
                if len(lines) > 2
                else (lines[1][:120] if len(lines) > 1 else ""),
                "year": year,
            }
        )
    return items[:8]


def _languages(text: str) -> list[dict]:
    if not text.strip():
        return []
    code_map = {
        "english": "en",
        "en": "en",
        "azərbaycan": "az",
        "azerbaijani": "az",
        "azerbaijan": "az",
        "az": "az",
        "russian": "ru",
        "ru": "ru",
        "русский": "ru",
        "german": "de",
        "de": "de",
        "deutsch": "de",
        "turkish": "tr",
        "tr": "tr",
        "french": "fr",
        "fr": "fr",
    }
    level_map = {
        "native": "native",
        "ana dili": "native",
        "родной": "native",
        "fluent": "C1",
        "advanced": "C1",
        "c2": "C2",
        "c1": "C1",
        "b2": "B2",
        "b1": "B1",
        "a2": "A2",
        "a1": "A1",
        "intermediate": "B1",
        "basic": "A2",
    }
    out: list[dict] = []
    for raw in re.split(r"[,;\n|/]+", text):
        piece = raw.strip()
        if not piece:
            continue
        low = piece.lower()
        code = ""
        for key, val in code_map.items():
            if re.search(rf"\b{re.escape(key)}\b", low):
                code = val
                break
        if not code:
            continue
        level = ""
        for key, val in level_map.items():
            if key in low:
                level = val
                break
        if not any(item["code"] == code for item in out):
            out.append({"code": code, "level": level})
    return out


def _confidence(
    text: str,
    sections: dict[str, str],
    contact: dict,
    dated_jobs: list[dict],
    skills: list[dict],
) -> float:
    if not text:
        return 0.0
    score = 0.0
    n = len(text)
    if n >= 800:
        score += 0.2
    elif n >= 300:
        score += 0.12
    elif n >= 80:
        score += 0.05
    known = {"experience", "education", "skills", "languages", "summary"}
    found = known.intersection(sections)
    score += min(0.25, 0.06 * len(found))
    if contact.get("email"):
        score += 0.1
    if contact.get("phone"):
        score += 0.05
    if contact.get("links", {}).get("linkedin") or contact.get("links", {}).get("github"):
        score += 0.05
    if len(dated_jobs) >= 2:
        score += 0.2
    elif len(dated_jobs) == 1:
        score += 0.1
    if len(skills) >= 6:
        score += 0.15
    elif len(skills) >= 3:
        score += 0.1
    elif len(skills) >= 1:
        score += 0.05
    return round(min(1.0, score), 2)

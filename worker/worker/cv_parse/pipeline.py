"""Orchestrate CV → profile JSON (plan §5.2): rules first, AI #1 if low confidence."""

from __future__ import annotations

import re
import sqlite3
from datetime import date

from worker.cv_parse.ai_fallback import maybe_ai_fallback
from worker.cv_parse.contact import extract_contact
from worker.cv_parse.dates import find_ranges, iso_month, merge_years
from worker.cv_parse.locale import fold_az
from worker.cv_parse.sections import split_sections
from worker.cv_parse.text import extract
from worker.techstack import find_stack

PARSER_VERSION = "1.6"

# Intern calendar time counts at half weight vs professional roles for total_years /
# skill years. 6 months intern ≠ 6 months senior IC time.
_INTERN_YEAR_WEIGHT = 0.5

_SENIORITY_PAT = re.compile(
    r"(?i)\b(intern|junior|jr\.?|middle|mid-level|mid\b|senior|sr\.?|lead|principal|staff)\b"
)
_SENIORITY_RANK = {
    "intern": 0,
    "junior": 1,
    "middle": 2,
    "senior": 3,
    "lead": 4,
    "principal": 4,
    "staff": 4,
}
_INTERN_HINT = re.compile(
    r"(?i)\b("
    r"intern(?:ship)?|təcrübəçi|tecrubeci|"
    r"staj(?:yer|ı|i)?|стаж[ёе]р(?:ка)?|стажировка"
    r")\b"
)
_JOB_LINE = re.compile(
    r"(?ix)^\s*(?P<title>.+?)\s+(?:[-–—@|]|at|в|də)\s+(?P<company>.+?)\s*$"
)
_TITLE_COMPANY = re.compile(
    r"(?ix)^\s*(?P<title>[^|,\-–—]{2,80})\s*[,|]\s*(?P<company>.+)$"
)
# Company | employment-type | dates  (EN / AZ / RU ATS layouts vary)
_EMPLOYMENT_HINT = re.compile(
    r"(?i)\b("
    r"full[\s-]?time|part[\s-]?time|contract|internship|intern|freelance|remote|"
    r"tam\s*ştat|yarım\s*ştat|müqavilə|"
    r"полная\s*занятость|частичная\s*занятость|контракт|стажировка|"
    r"занятость"
    r")\b"
)
_DEGREE_TOKEN = re.compile(
    r"(?i)^(bsc|ba|b\.?s\.?|msc|ma|m\.?s\.?|phd|bachelor|master|bakalavr|бакалавр|"
    r"magistr|магистр|associate|diploma|diplom)\b"
)
_DEGREE_START = _DEGREE_TOKEN
_EDUCATION_HINT = re.compile(
    r"(?i)\b("
    r"university|universitet(?:i)?|университет|college|institute|institut|"
    r"akademiya|academy|məktəb|school|"
    r"bakalavr|bachelor|magistr|master|phd|təhsil|образование|"
    r"fakültə|faculty"
    r")\b"
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


def _join_wrapped_dates(text: str) -> str:
    """Join soft line-breaks that split a date range (common in PDF extraction).

    Example::

        Февраль 2025 –
        н.в.
    """
    lines = (text or "").splitlines()
    if not lines:
        return ""
    out: list[str] = [lines[0]]
    present_cont = re.compile(
        r"(?i)^(н\.?\s*в\.?|н/в|present|current|now|hazırda|hazirda|indi|"
        r"настоящее(?:\s+время)?)\s*$"
    )
    for line in lines[1:]:
        prev = out[-1].rstrip()
        cur = line.strip()
        if prev and re.search(r"[–—-]\s*$", prev) and present_cont.match(cur):
            out[-1] = prev + " " + cur
            continue
        out.append(line)
    return "\n".join(out)


def parse_text(text: str) -> dict:
    """Rules-only parse of already-extracted CV text → profile JSON."""
    body = _join_wrapped_dates((text or "").strip())
    sections = split_sections(body) if body else {}
    # Re-join inside sections too (PDF wraps often land inside a section body).
    sections = {key: _join_wrapped_dates(val) for key, val in sections.items()}
    contact = extract_contact(body) if body else extract_contact("")
    work_history, dated_jobs = _work_history(sections.get("experience", "") or body)
    pro_years, intern_years, total_years = _experience_years(dated_jobs)
    skills = _skills(body, sections, dated_jobs)
    education = _education(sections.get("education", ""))
    languages = _languages(sections.get("languages", ""))
    headline = _headline(body, sections, work_history)
    summary = _profile_summary(sections)
    seniority = _seniority(body, headline, work_history, pro_years, intern_years)
    confidence = _confidence(body, sections, contact, dated_jobs, skills)
    return {
        "contact": contact,
        "headline": headline,
        "summary": summary,
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
                "employment_type": item.get("employment_type") or "",
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


def _profile_summary(sections: dict[str, str]) -> str:
    """Keep About/Summary section text for the review form (not just headline)."""
    raw = (sections.get("summary") or "").strip()
    if not raw:
        return ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return "\n".join(lines)[:2000]


def _headline(text: str, sections: dict[str, str], work: list[dict]) -> str:
    for line in text.splitlines()[:12]:
        line = line.strip()
        if not line or len(line) > 80:
            continue
        low = line.lower()
        if any(
            k in low
            for k in (
                "@",
                "http",
                "linkedin",
                "github",
                "tel",
                "+994",
                "email",
                "telefon",
                "телефон",
                "veb:",
                "сайт:",
            )
        ):
            continue
        if re.search(
            r"(?i)\b(developer|engineer|devops|analyst|designer|manager|qa|sre|mentor|"
            r"разработчик|инженер)\b",
            line,
        ):
            return line[:120]
    summary = sections.get("summary") or ""
    for line in summary.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 80 and not line.lower().startswith("i am"):
            return line[:120]
    if work and work[0].get("title"):
        return str(work[0]["title"])[:120]
    return ""


def _canonical_seniority(token: str) -> str:
    raw = (token or "").lower().rstrip(".")
    if raw in {"intern"}:
        return "intern"
    if raw in {"junior", "jr"}:
        return "junior"
    if raw in {"middle", "mid-level", "mid"}:
        return "middle"
    if raw in {"senior", "sr"}:
        return "senior"
    if raw in {"lead", "principal", "staff"}:
        return raw if raw in {"lead", "principal", "staff"} else "lead"
    return ""


def _seniority(
    text: str,
    headline: str,
    work: list[dict],
    pro_years: float,
    intern_years: float,
) -> str:
    """Infer seniority from professional roles first; intern-only CVs stay intern."""
    if pro_years <= 0 and intern_years > 0:
        return "intern"

    best = ""
    best_rank = -1

    def consider(level: str) -> None:
        nonlocal best, best_rank
        if not level or level == "intern":
            return
        rank = _SENIORITY_RANK.get(level, -1)
        if rank > best_rank:
            best = level
            best_rank = rank

    for job in work:
        if job.get("is_intern"):
            continue
        consider(_title_seniority(job.get("title") or ""))
    consider(_title_seniority(headline))
    # Highest explicit level in early text (e.g. "Middle …" in summary) wins
    # over an older "Junior …" job title.
    for match in _SENIORITY_PAT.finditer(f"{headline}\n{text[:2000]}"):
        consider(_canonical_seniority(match.group(1)))
    if best:
        return best

    if pro_years >= 8:
        return "lead"
    if pro_years >= 5:
        return "senior"
    if pro_years >= 2:
        return "middle"
    if pro_years > 0:
        return "junior"
    if intern_years > 0:
        return "intern"
    return ""


def _title_seniority(title: str) -> str:
    match = _SENIORITY_PAT.search(title or "")
    if not match:
        return ""
    return _canonical_seniority(match.group(1))


def _is_intern_job(title: str, company: str, block: str) -> bool:
    sample = f"{title}\n{company}\n{(block or '')[:400]}"
    return bool(_INTERN_HINT.search(sample))


def _experience_years(dated_jobs: list[dict]) -> tuple[float, float, float]:
    """Return (professional_years, intern_years, weighted_total_years)."""
    pro = [
        (w["start_date"], w["end_date"])
        for w in dated_jobs
        if w.get("start_date") and w.get("end_date") and not w.get("is_intern")
    ]
    intern = [
        (w["start_date"], w["end_date"])
        for w in dated_jobs
        if w.get("start_date") and w.get("end_date") and w.get("is_intern")
    ]
    pro_years = merge_years(pro)
    intern_years = merge_years(intern)
    total = round(pro_years + intern_years * _INTERN_YEAR_WEIGHT, 2)
    return pro_years, intern_years, total


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
        if _looks_like_education_job(block, title, company):
            continue
        skills = find_stack(block)
        present = bool(
            end_s
            and re.match(
                r"(?i)present|current|now|hal-hazırda|hazırda|hazirda|indi|"
                r"н\.?\s*в\.?|н/в|настоящее",
                end_s,
            )
        )
        is_intern = _is_intern_job(title, company, block)
        item = {
            "title": title,
            "company": company,
            "location": "",
            "start": iso_month(start),
            "end": None if present else iso_month(end),
            "summary": _job_summary(block),
            "skills": skills,
            "employment_type": "internship" if is_intern else "",
            "is_intern": is_intern,
            "start_date": start,
            "end_date": end or date.today(),
            "body": block,
        }
        history.append(item)
        if start and end:
            dated.append(item)
    return history, dated


def _looks_like_education_job(block: str, title: str, company: str) -> bool:
    """Drop education rows that landed in the experience section (2-column PDFs)."""
    sample = f"{title}\n{company}\n{block}"
    if not _EDUCATION_HINT.search(sample):
        return False
    # Real jobs at a university still mention a role; keep those.
    if re.search(
        r"(?i)\b("
        r"developer|engineer|intern|internship|mentor|lecturer|müəllim|"
        r"разработчик|инженер|стажёр|стажер"
        r")\b",
        sample,
    ):
        return False
    return True


def _looks_like_bullet(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if s[0] in {"-", "•", "●", "*", "–", "—"}:
        return True
    # Long prose / duty lines are not job titles.
    return len(s) > 90


def _is_job_meta_line(line: str) -> bool:
    """True for company/meta lines that usually follow a job title."""
    s = line.strip()
    if not s or _looks_like_bullet(s):
        return False
    if find_ranges(s):
        return True
    if "|" in s and _EMPLOYMENT_HINT.search(s):
        return True
    return False


def _split_jobs(text: str) -> list[str]:
    """Split experience into job blocks across common ATS layouts.

    Handles title-then-meta lines (EN/AZ/RU), date-on-same-line jobs, and
    blank-line separated blocks when dates are missing.
    """
    lines = text.splitlines()
    header_idxs: list[int] = []
    for i, line in enumerate(lines):
        if not _is_job_meta_line(line):
            continue
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j >= 0 and not _is_job_meta_line(lines[j]) and not _looks_like_bullet(lines[j]):
            start = j
        else:
            start = i
        if not header_idxs or start > header_idxs[-1]:
            header_idxs.append(start)
        elif start == header_idxs[-1]:
            continue

    if not header_idxs:
        parts = re.split(r"\n\s*\n", text.strip())
        return [p.strip() for p in parts if p.strip()]

    chunks: list[str] = []
    for i, start in enumerate(header_idxs):
        end = header_idxs[i + 1] if i + 1 < len(header_idxs) else len(lines)
        block = "\n".join(lines[start:end]).strip()
        if block:
            chunks.append(block)
    return chunks or [text.strip()]


def _title_company(block: str) -> tuple[str, str]:
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if not lines:
        return "", ""
    # Title on line 1, "Company | type | dates" (or Company — dates) on line 2.
    if len(lines) >= 2 and _is_job_meta_line(lines[1]):
        title = lines[0][:120]
        company_line = lines[1]
        company = company_line.split("|")[0].strip()
        company = re.split(r"\s+[–—-]\s+", company)[0].strip()
        if company and not find_ranges(company):
            return title, company[:120]
    for line in lines[:4]:
        if find_ranges(line) and "|" not in line and len(line) < 40:
            continue
        m = _JOB_LINE.match(line)
        if m:
            return m.group("title").strip()[:120], m.group("company").strip()[:120]
        if "|" in line and not find_ranges(line) and not _EMPLOYMENT_HINT.search(line):
            m = _TITLE_COMPANY.match(line)
            if m:
                return m.group("title").strip()[:120], m.group("company").strip()[:120]
    title = lines[0][:120]
    company = ""
    if len(lines) > 1 and not find_ranges(lines[1]):
        company = lines[1].split("|")[0].strip()[:120]
    return title, company


def _job_summary(block: str) -> str:
    lines = []
    skipped_header = 0
    for line in block.splitlines():
        line = line.strip()
        if not line or find_ranges(line):
            continue
        # Skip title + company header lines.
        if skipped_header < 2 and len(line) <= 90 and not _looks_like_bullet(line):
            skipped_header += 1
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
    pro: list[tuple[date, date]] = []
    intern: list[tuple[date, date]] = []
    for job in jobs:
        body = job.get("body") or ""
        job_skills = job.get("skills") or []
        if name in job_skills or name.lower() in body.lower():
            start = job.get("start_date")
            end = job.get("end_date")
            if start and end:
                if job.get("is_intern"):
                    intern.append((start, end))
                else:
                    pro.append((start, end))
    if not pro and not intern:
        return None
    return round(merge_years(pro) + merge_years(intern) * _INTERN_YEAR_WEIGHT, 2)


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
    body = _join_wrapped_dates(text.strip())
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    # AZ CVs often use "Field | Bakalavr/Magistr" rows paired with school + years.
    pipe_degrees = [_split_degree_line(ln) for ln in lines]
    if any(item[0] for item in pipe_degrees):
        return _education_from_pipe_rows(lines, pipe_degrees)[:8]

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if current and _DEGREE_START.match(line):
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    if not blocks:
        blocks = [lines]

    items: list[dict] = []
    for block_lines in blocks:
        if not block_lines:
            continue
        year = None
        school = ""
        field = ""
        degree = block_lines[0][:120]
        if "," in degree:
            left, right = degree.split(",", 1)
            if _DEGREE_START.match(left.strip()):
                degree = left.strip()[:120]
                field = right.strip()[:120]
        for line in block_lines[1:]:
            clean = re.split(r"\s*\|\s*", line)[0].strip()
            if not school and not find_ranges(clean):
                school = clean[:120]
            m = re.search(r"((?:19|20)\d{2})", line)
            if m and year is None:
                year = int(m.group(1))
        if not school and len(block_lines) > 1:
            school = block_lines[1].split("|")[0].strip()[:120]
        items.append(
            {
                "degree": degree,
                "field": field,
                "school": school,
                "year": year,
            }
        )
    return items[:8]


def _split_degree_line(line: str) -> tuple[str, str]:
    """Return (degree, field) for 'Field | Magistr' / 'BSc, CS' lines."""
    if "|" in line:
        left, right = [p.strip() for p in line.split("|", 1)]
        if _DEGREE_TOKEN.match(right):
            return right[:120], left[:120]
        if _DEGREE_TOKEN.match(left):
            return left[:120], right[:120]
    if "," in line:
        left, right = [p.strip() for p in line.split(",", 1)]
        if _DEGREE_TOKEN.match(left):
            return left[:120], right[:120]
    if _DEGREE_TOKEN.match(line):
        return line[:120], ""
    return "", ""


def _education_from_pipe_rows(
    lines: list[str], pipe_degrees: list[tuple[str, str]]
) -> list[dict]:
    degrees = [(i, deg, field) for i, (deg, field) in enumerate(pipe_degrees) if deg]
    schools: list[tuple[int, str]] = []
    years: list[tuple[int, int]] = []
    for i, line in enumerate(lines):
        if pipe_degrees[i][0]:
            continue
        if find_ranges(line) or re.fullmatch(r"(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}", line):
            m = re.search(r"((?:19|20)\d{2})", line)
            if m:
                years.append((i, int(m.group(1))))
            continue
        if _EDUCATION_HINT.search(line) or len(line) >= 12:
            schools.append((i, line[:120]))
    items: list[dict] = []
    for idx, (_line_i, degree, field) in enumerate(degrees):
        school = schools[idx][1] if idx < len(schools) else (schools[-1][1] if schools else "")
        year = years[idx][1] if idx < len(years) else (years[-1][1] if years else None)
        items.append(
            {
                "degree": degree,
                "field": field,
                "school": school,
                "year": year,
            }
        )
    return items


def _languages(text: str) -> list[dict]:
    if not text.strip():
        return []
    # Longer keys first so "азербайджанский" wins over shorter stems.
    code_map = [
        ("azərbaycan dili", "az"),
        ("азербайджанский", "az"),
        ("azerbaijani", "az"),
        ("azerbaijan", "az"),
        ("azərbaycan", "az"),
        ("английский", "en"),
        ("ingilis", "en"),
        ("english", "en"),
        ("русский", "ru"),
        ("russian", "ru"),
        ("немецкий", "de"),
        ("german", "de"),
        ("deutsch", "de"),
        ("türk dili", "tr"),
        ("turk dili", "tr"),
        ("türkçe", "tr"),
        ("turkish", "tr"),
        ("турецкий", "tr"),
        ("türk", "tr"),
        ("turk", "tr"),
        ("français", "fr"),
        ("french", "fr"),
        ("французский", "fr"),
        ("az", "az"),
        ("en", "en"),
        ("ru", "ru"),
        ("de", "de"),
        ("tr", "tr"),
        ("fr", "fr"),
    ]
    level_map = [
        ("ana dili", "native"),
        ("ana dil", "native"),
        ("родной", "native"),
        ("native", "native"),
        ("выше среднего", "B2"),
        ("yuxarı-orta", "B2"),
        ("yuxari-orta", "B2"),
        ("технический", "B2"),
        ("texniki", "B2"),
        ("fluent", "C1"),
        ("advanced", "C1"),
        ("intermediate", "B1"),
        ("basic", "A2"),
        ("c2", "C2"),
        ("c1", "C1"),
        ("b2", "B2"),
        ("b1", "B1"),
        ("a2", "A2"),
        ("a1", "A1"),
    ]
    out: list[dict] = []
    for raw in re.split(r"[\n;/]+", text):
        piece = raw.strip()
        if not piece:
            continue
        low = fold_az(piece)
        code = ""
        for key, val in code_map:
            if re.search(rf"(?<!\w){re.escape(fold_az(key))}(?!\w)", low):
                code = val
                break
        if not code:
            continue
        level = ""
        for key, val in level_map:
            if fold_az(key) in low:
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

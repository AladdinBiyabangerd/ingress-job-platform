"""Layout normaliser for the experience section.

CV templates place title / company / dates / location in many orders
(title-first, date-first, company+date on one line, header at the top with the
date *after* the bullets, ...). ``normalize_experience`` rewrites any of them
into the canonical block the rule parser already understands::

    Title
    Company | <date range>
    <bullets / body lines>
"""

from __future__ import annotations

import re

from worker.cv_parse.dates import _RANGE, find_ranges
from worker.cv_parse.locale import fold_az

_BULLET_CHARS = "-•●*–—◦◆▪■▸►·"
_ROLE = re.compile(
    r"(?i)(intern|engineer|developer|founder|\bcto\b|\bceo\b|\bcfo\b|\bcoo\b|manager|"
    r"lead\b|director|scientist|researcher|analyst|designer|architect|consultant|"
    r"specialist|officer|assistant|head\b|president|administrator|devops|\bsre\b|\bqa\b|"
    r"tester|professor|lecturer|accountant|teacher|coordinator|executive|associate|"
    r"representative|technician|supervisor|advisor|fellow|member|mentor|student|"
    r"developer|mühəndis|menecer|müəllim|təcrübəçi|разработчик|инженер|менеджер|"
    r"аналитик|дизайнер|стажёр|стажер|директор|руководитель|специалист)"
)
_LOC_TAIL_COMMA = re.compile(r"^(?P<head>.*?),\s*[A-Z][\w .'’-]+,\s*[A-Za-z]{2,3}\.?$")
_LOC_TAIL_SEP = re.compile(
    r"\s+[|–—-]\s*[A-Z][\w .'’-]+,\s*[A-Za-z .]{2,30}$|\s*\|\s*[A-Z][\w .'’-]+$"
)
_LOC_ONLY = re.compile(
    r"^(?:[A-Z][\w .'’-]+,\s*[A-Za-z .]{2,30}|(?:Remote|Hybrid|On-?site|Worldwide)(?:,\s*[A-Za-z .]{2,30})?)$"
)
_DURATION = re.compile(
    r"(?i)^\s*\d+\s*(?:years?|yrs?|months?|mos?|il|ay|год(?:а)?|лет|мес\w*)"
    r"(?:\s+\d+\s*(?:months?|mos?|ay|мес\w*))?\s*$"
)
_STRONG_SEP = re.compile(r"\s+[|–—@]\s+|\s+-\s+|\s+at\s+|\s+в\s+|\s+də\s+")


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").replace("\xad", "-")).strip()


def _is_bullet(line: str) -> bool:
    return bool(line) and line[0] in _BULLET_CHARS and (len(line) == 1 or line[1] in " \t\u00a0" or line[0] in "•●◦◆▪■▸►·")


def _date_span(line: str) -> tuple[int, int, str] | None:
    folded = fold_az(line)
    if len(folded) != len(line):
        return None
    m = _RANGE.search(folded)
    if not m or not find_ranges(line):
        return None
    return m.start(), m.end(), line[m.start() : m.end()]


def _is_anchor(line: str) -> bool:
    if not line or len(line) > 160 or _is_bullet(line) and len(line) > 60:
        return False
    return bool(find_ranges(line))


def _strip_location(text: str) -> str:
    text = text.strip(" |–—-,")
    if text.count(",") >= 3:
        # "Title, Company, City, Country": the last two comma parts are the place.
        text = ",".join(text.split(",")[:-2])
    m = _LOC_TAIL_COMMA.match(text)
    if m:
        text = m.group("head")
    else:
        text = _LOC_TAIL_SEP.sub("", text)
    return text.strip(" |–—-,")


def _header_candidate(line: str) -> bool:
    """Short non-prose line that can be part of a job header."""
    s = line.lstrip(_BULLET_CHARS + " ")
    if not s or len(s) > 90 or find_ranges(s):
        return False
    if _is_bullet(line) and len(s) > 45:
        return False
    if s[-1:] in ".;" or s[0].islower():
        return False
    return True


def _wrapped_bullet_tail(lines: list[str], j: int) -> bool:
    """Long prose line right under a bullet = wrapped bullet text, not a header."""
    if " | " in lines[j] or _ROLE.search(lines[j]):
        return False
    return j > 0 and len(lines[j].split()) >= 6 and (
        _is_bullet(lines[j - 1]) or len(lines[j - 1].split()) >= 6
    )


def _pieces(line: str) -> list[str]:
    line = line.lstrip(_BULLET_CHARS + " ")
    parts = [p.strip() for p in _STRONG_SEP.split(line) if p and p.strip()]
    out: list[str] = []
    for part in parts:
        part = _strip_location(part)
        if not part:
            continue
        if "," in part:
            left, right = [x.strip() for x in part.split(",", 1)]
            if left and right and bool(_ROLE.search(left)) != bool(_ROLE.search(right)):
                out.extend([left, right])
                continue
        out.append(part)
    return out


def _title_company(headers: list[str]) -> tuple[str, str]:
    pieces: list[str] = []
    for h in headers:
        pieces.extend(_pieces(h))
    if not pieces:
        return "", ""
    title = next((p for p in pieces if _ROLE.search(p)), pieces[0])
    others = [p for p in pieces if p != title]
    company = next((p for p in others if not _LOC_ONLY.match(p)), others[0] if others else "")
    return title[:120], company[:120]


def _emit(title: str, company: str, date_text: str, body: list[str]) -> list[str]:
    out = [title or company or "Role", f"{company} | {date_text}" if company else f"| {date_text}"]
    if not title and company:
        out[0] = company
        out[1] = f"| {date_text}"
    return out + body


def _trailing_mode(lines: list[str], anchors: list[int]) -> bool:
    first = anchors[0]
    long_bullets = sum(1 for ln in lines[:first] if _is_bullet(ln) and len(ln) >= 40)
    return long_bullets >= 2


def normalize_experience(text: str) -> str:
    """Rewrite varied experience layouts into title / company|date / body blocks."""
    lines = [clean_line(ln) for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    anchors = [i for i, ln in enumerate(lines) if _is_anchor(ln)]
    if not anchors:
        return "\n".join(lines)
    if _trailing_mode(lines, anchors):
        return "\n".join(_normalize_trailing(lines, anchors))
    return "\n".join(_normalize_leading(lines, anchors))


def _normalize_trailing(lines: list[str], anchors: list[int]) -> list[str]:
    out: list[str] = []
    start = 0
    for idx in anchors:
        span = _date_span(lines[idx])
        date_text = span[2] if span else lines[idx]
        block = lines[start:idx]
        start = idx + 1
        if start < len(lines) and _DURATION.match(lines[start]):
            start += 1
        if not block:
            continue
        header, body = block[0], block[1:]
        if body and _LOC_ONLY.match(body[-1]) and not _is_bullet(body[-1]):
            body = body[:-1]
        title, company = _title_company([header])
        out.extend(_emit(title, company, date_text, body))
    if start < len(lines):
        out.extend(lines[start:])
    return out


def _normalize_leading(lines: list[str], anchors: list[int]) -> list[str]:
    jobs: list[dict] = []
    for pos, idx in enumerate(anchors):
        prev_idx = anchors[pos - 1] if pos else -1
        floor = prev_idx + 1
        span = _date_span(lines[idx])
        date_text = span[2] if span else lines[idx]
        rest = (lines[idx][: span[0]] + " " + lines[idx][span[1] :]) if span else ""
        rest = clean_line(rest).strip(" |–—-,()")
        rest_stripped = _strip_location(rest) if rest else ""
        if rest_stripped and _LOC_ONLY.match(rest_stripped) and not _ROLE.search(rest_stripped):
            rest_stripped = ""  # "Jul 2021 — Jul 2022 London, UK": the tail is just the place
        headers: list[str] = []
        head_start = idx
        before: list[str] = []
        j = idx - 1
        max_before = 1 if rest_stripped else 2
        while (
            j >= floor
            and len(before) < max_before
            and _header_candidate(lines[j])
            and not _wrapped_bullet_tail(lines, j)
        ):
            before.insert(0, lines[j])
            head_start = j
            j -= 1
        has_role_inline = bool(rest_stripped and _ROLE.search(rest_stripped))
        if rest_stripped and has_role_inline and before and any(_ROLE.search(b) for b in before):
            # Both sides carry a role: the inline text belongs to this job, the line above is prior body.
            before, head_start = [], idx
        headers.extend(before)
        if rest_stripped:
            headers.append(rest_stripped)
        end = idx + 1
        if (
            rest_stripped
            and not has_role_inline
            and end < len(lines)
            and _header_candidate(lines[end])
            and not _is_bullet(lines[end])
            and _ROLE.search(lines[end])
        ):
            headers.append(lines[end])
            end += 1
        title, company = _title_company(headers)
        jobs.append(
            {
                "title": title,
                "company": company,
                "date": date_text,
                "head_start": head_start,
                "body_start": end,
            }
        )
    out: list[str] = list(lines[: jobs[0]["head_start"]])
    for pos, job in enumerate(jobs):
        stop = jobs[pos + 1]["head_start"] if pos + 1 < len(jobs) else len(lines)
        body = [ln for ln in lines[job["body_start"] : stop] if not _DURATION.match(ln)]
        out.extend(_emit(job["title"], job["company"], job["date"], body))
    return out

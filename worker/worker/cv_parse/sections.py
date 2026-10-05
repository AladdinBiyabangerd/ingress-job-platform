"""Multilingual CV section heading split (EN / AZ / RU)."""

from __future__ import annotations

import re

# canonical section -> heading aliases (matched as a whole line, optional trailing :)
_HEADINGS: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience",
        "work experience",
        "employment",
        "professional experience",
        "work history",
        "career",
        "təcrübə",
        "iş təcrübəsi",
        "peşəkar təcrübə",
        "опыт",
        "опыт работы",
        "трудовой опыт",
    ),
    "education": (
        "education",
        "academic",
        "təhsil",
        "образование",
        "учеба",
        "учёба",
    ),
    "skills": (
        "skills",
        "technical skills",
        "technologies",
        "tech stack",
        "tools",
        "bacarıqlar",
        "texniki bacarıqlar",
        "навыки",
        "ключевые навыки",
        "технологии",
    ),
    "languages": (
        "languages",
        "language skills",
        "dillər",
        "языки",
    ),
    "summary": (
        "summary",
        "profile",
        "about",
        "about me",
        "objective",
        "haqqında",
        "о себе",
        "резюме",
    ),
    "projects": (
        "projects",
        "personal projects",
        "layihələr",
        "проекты",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "sertifikatlar",
        "сертификаты",
    ),
}

_ALIAS_TO_CANON: dict[str, str] = {}
for _canon, _aliases in _HEADINGS.items():
    for _alias in _aliases:
        _ALIAS_TO_CANON[_alias.lower()] = _canon

_HEADING_RE = re.compile(
    r"^\s*(?P<title>[A-Za-zА-Яа-яƏəÖöÜüĞğÇçŞşİı /&+\-]{2,60})\s*:?\s*$",
    re.UNICODE,
)


def split_sections(text: str) -> dict[str, str]:
    """Split CV text into named sections. Unknown preamble → ``other``."""
    buckets: dict[str, list[str]] = {key: [] for key in _HEADINGS}
    buckets["other"] = []
    current = "other"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if buckets[current] and buckets[current][-1] != "":
                buckets[current].append("")
            continue
        heading = _heading_name(line)
        if heading:
            current = heading
            continue
        buckets[current].append(line)
    return {
        key: "\n".join(lines).strip()
        for key, lines in buckets.items()
        if "".join(lines).strip()
    }


def _heading_name(line: str) -> str | None:
    m = _HEADING_RE.match(line)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group("title")).strip().lower().rstrip(":")
    if title in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[title]
    title = re.sub(r"^(?:[0-9ivx]+\.|[0-9]+)\)?\s*", "", title, flags=re.I).strip()
    return _ALIAS_TO_CANON.get(title)

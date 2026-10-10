"""Multilingual CV section heading split (EN / AZ / RU)."""

from __future__ import annotations

import re

from worker.cv_parse.locale import fold_az

# canonical section -> heading aliases (matched as a whole line, optional trailing :)
_HEADINGS: dict[str, tuple[str, ...]] = {
    "experience": (
        "experience",
        "work experience",
        "employment",
        "professional experience",
        "work history",
        "employment history",
        "relevant experience",
        "internships",
        "career",
        "experiences",
        "work experiences",
        "professional experiences",
        "research experience",
        "academic appointments",
        "appointments",
        "positions held",
        "industry experience",
        "teaching experience",
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
        "academic background",
        "educational background",
        "qualifications",
        "education and training",
        "education & training",
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
        "key skills",
        "core skills",
        "core competencies",
        "competencies",
        "technical expertise",
        "skills & tools",
        "skills and tools",
        "strengths",
        "programming",
        "bacarıqlar",
        "bacariqlar",
        "texniki bacarıqlar",
        "proqramlar",
        "proqram təminatı",
        "навыки",
        "ключевые навыки",
        "технологии",
    ),
    "languages": (
        "languages",
        "language skills",
        "dillər",
        "diller",
        "языки",
    ),
    "summary": (
        "summary",
        "profile",
        "professional summary",
        "career summary",
        "personal statement",
        "about",
        "about me",
        "objective",
        "xülasə",
        "xulase",
        "haqqında",
        "haqqımda",
        "haqqimda",
        "о себе",
        "обо мне",
        "резюме",
    ),
    "projects": (
        "projects",
        "personal projects",
        "layihələr",
        "layiheler",
        "fəaliyyətlər",
        "fealiyyetler",
        "проекты",
    ),
    "certifications": (
        "certifications",
        "certificates",
        "sertifikatlar",
        "сертификаты",
    ),
    # Sections we do not parse; they exist so they end the previous section
    # instead of leaking their lines into experience / skills.
    "awards": ("awards", "honors", "achievements", "mükafatlar", "наградa", "награды"),
    "publications": ("publications", "papers", "nəşrlər", "публикации"),
    "volunteer": ("volunteering", "volunteer experience", "könüllü", "волонтерство"),
    "interests": ("interests", "hobbies", "maraqlar", "хобби", "интересы"),
    "references": ("references", "referanslar", "рекомендации"),
    "additional": ("additional information", "əlavə məlumat", "дополнительно"),
    "coursework": ("coursework", "courses", "kurslar", "курсы"),
    "links": ("links",),
}

_ALIAS_TO_CANON: dict[str, str] = {}
for _canon, _aliases in _HEADINGS.items():
    for _alias in _aliases:
        _ALIAS_TO_CANON[fold_az(_alias)] = _canon

_SPACELESS_TO_CANON: dict[str, str] = {k.replace(" ", ""): v for k, v in _ALIAS_TO_CANON.items()}

_HEADING_RE = re.compile(
    r"^\s*(?P<title>[A-Za-zА-Яа-яƏəÖöÜüĞğÇçŞşİı /&+\-]{2,60})\s*:?\s*$",
    re.UNICODE,
)


_FUZZY_CANDIDATES = sorted(k for k in _ALIAS_TO_CANON if len(k) >= 6)


def _fuzzy_heading(title: str) -> str | None:
    """Typo-tolerant heading match ("WORK EXPERICENCE") for short upper/title-case lines."""
    import difflib

    if len(title) < 6 or len(title) > 32:
        return None
    best = difflib.get_close_matches(title, _FUZZY_CANDIDATES, n=1, cutoff=0.88)
    return _ALIAS_TO_CANON[best[0]] if best else None


_INLINE_HEADING = re.compile(r"^(?P<head>[A-Z][A-Z &/]{3,28}?)\s+(?P<rest>[A-Z][a-z].{6,})$")


def _split_inline_heading(line: str) -> tuple[str, str] | None:
    """"EDUCATION First American University, ..." → ("education", "First American University, ...")."""
    m = _INLINE_HEADING.match(line)
    if not m:
        return None
    canon = _heading_name(m.group("head"))
    return (canon, m.group("rest")) if canon else None


def split_sections(text: str) -> dict[str, str]:
    """Split CV text into named sections. Unknown preamble → ``other``."""
    buckets: dict[str, list[str]] = {key: [] for key in _HEADINGS}
    buckets["other"] = []
    current = "other"
    raw_lines = text.splitlines()
    idx = 0
    while idx < len(raw_lines):
        raw = raw_lines[idx]
        idx += 1
        line = raw.strip()
        if line.isupper() and idx < len(raw_lines):
            # Heading split over two lines: "RESEARCH" / "EXPERIENCE".
            nxt = raw_lines[idx].strip()
            if (
                nxt.isupper()
                and len(line) < 20
                and len(nxt) < 20
                and not _heading_name(line)
                and _heading_name(f"{line} {nxt}")
            ):
                current = _heading_name(f"{line} {nxt}") or current
                idx += 1
                continue
        inline = _split_inline_heading(line) if line and not _heading_name(line) else None
        if inline:
            current = inline[0]
            buckets[current].append(inline[1])
            continue
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
    title = fold_az(re.sub(r"\s+", " ", m.group("title")).strip().rstrip(":"))
    # ASCII capital I folds to dotless ı (AZ rule); ALL-CAPS English headings
    # ("EDUCATION") need the plain-i form too.
    ascii_title = title.replace("ı", "i")
    if title in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[title]
    if ascii_title in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[ascii_title]
    # PDFs that lose word spaces: "WorkExperience".
    if ascii_title.replace(" ", "") in _SPACELESS_TO_CANON and len(ascii_title) <= 40:
        return _SPACELESS_TO_CANON[ascii_title.replace(" ", "")]
    title = ascii_title if ascii_title in _ALIAS_TO_CANON else title
    title = re.sub(r"^(?:[0-9ivx]+\.|[0-9]+)\)?\s*", "", title).strip()
    if title in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[title]
    # Two-column PDFs often emit combined headers: "FƏALİYYƏTLƏR TƏHSİL".
    words = title.split()
    if 1 < len(words) <= 5:
        for word in reversed(words):
            canon = _ALIAS_TO_CANON.get(word) or _ALIAS_TO_CANON.get(word.replace("ı", "i"))
            if canon:
                return canon
        # Also try adjacent bigrams ("iş təcrübəsi", "texniki bacarıqlar").
        for i in range(len(words) - 1, 0, -1):
            bigram = f"{words[i - 1]} {words[i]}"
            canon = _ALIAS_TO_CANON.get(bigram) or _ALIAS_TO_CANON.get(bigram.replace("ı", "i"))
            if canon:
                return canon
    if line_is_caps(m.group("title")):
        return _fuzzy_heading(ascii_title)
    return None


def line_is_caps(title: str) -> bool:
    letters = [c for c in title if c.isalpha()]
    return len(letters) >= 6 and all(c.isupper() for c in letters)

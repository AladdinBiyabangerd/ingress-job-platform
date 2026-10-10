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
    return None

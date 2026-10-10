"""Optional CV *template* recognition (layer a of the parse flow).

The parser never depends on this module. ``detect_template`` looks for a few cheap
signals in the already-extracted text (section labels, date-line shapes, bullet glyphs).
When a known template matches, its ``hints`` can nudge the generic parser (extra
section aliases, noise lines to drop, a forced experience layout). ``parse_text`` runs
the generic parser first and only keeps the hinted result when its quality score is
higher, so a wrong or missing detection can never make a result worse.

Template ids are shared with ``frontend/lib/cv-styles.js`` (names, tips, licences).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_M = re.MULTILINE


@dataclass(frozen=True)
class Signal:
    pattern: str
    min_count: int = 1

    def hits(self, text: str) -> int:
        return len(re.findall(self.pattern, text, _M))


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    signals: tuple[Signal, ...]
    min_signals: int = 1  # how many of ``signals`` must be satisfied
    hints: dict = field(default_factory=dict)


# hints keys: ``strip`` (regexes of noise lines to drop), ``headings`` ({alias: section}),
# ``layout`` ("leading" | "trailing" | "date_first" experience layout).
TEMPLATES: tuple[Template, ...] = (
    Template(
        "vantage_typst", "Typst Vantage",
        (Signal(r"^\s*\d{4} [A-Z][a-z]{2}\.? [—–-] (?:\d{4} [A-Z][a-z]{2}\.?|[Pp]resent)", 2),),
        hints={"layout": "leading"},
    ),
    Template(
        "alta_typst", "Typst AltaCV",
        (Signal(r"^[A-Z][a-z]{2} \d{4} — (?:[A-Z][a-z]{2} \d{4}|Present) .+, [A-Z]{2,}$", 2),),
        hints={"layout": "leading"},
    ),
    Template(
        "arthur_latex", "LaTeX Arthur CV (date column)",
        (Signal(r"^[A-Z][a-z]{2}\. ?\d{4} ?[–-]$", 2),),
        hints={"layout": "date_first"},
    ),
    Template(
        "latexcv_classic", "latexcv Classic",
        (Signal(r"^· ", 3), Signal(r"[A-Za-z)]- .+ \d{4} - (?:present|\d{4})$", 2)),
        min_signals=2,
        hints={"layout": "leading"},
    ),
    Template(
        "latexcv_modern", "latexcv Modern",
        (Signal(r"^\d{4} ?[-/] ?\d{2,4} ?[A-Z]", 3), Signal(r"^(?:Status|Fields|Loves|Tech):", 2)),
        min_signals=2,
    ),
    Template(
        "latexcv_infographics", "latexcv Infographics",
        (
            Signal(r"^SKILLS AND TECHNOLOGIES$"),
            Signal(r"^EXPERIENCE AND EDUCATION$"),
            Signal(r"^ACTVITIES$|^ACTIVITIES$"),
        ),
        min_signals=2,
    ),
    Template(
        "minimal_cv", "Minimal-CV (sidebar labels)",
        (Signal(r"^CONTACT$"), Signal(r"^Address$"), Signal(r"^PERSONAL$"), Signal(r"^Date of Birth$")),
        min_signals=3,
    ),
    Template(
        "academic_xovee", "Academic CV (Xovee latex-cv)",
        (
            Signal(r"ORCID:"),
            Signal(r"^Academic Appointments$"),
            Signal(r"^Research Interests$"),
            Signal(r"^Selected Distinctions$"),
            Signal(r"^Refereed Journal"),
        ),
        min_signals=3,
        hints={"headings": {"academic appointments": "experience"}},
    ),
    Template(
        "rover_base", "Rover Resume (base)",
        (
            Signal(r"^CERTIFICATION & A ?W ?ARDS$"),
            Signal(r"^SKILLS & INTERESTS$"),
            Signal(r"Related Coursework"),
        ),
        min_signals=2,
        hints={"headings": {"skills & interests": "skills", "certification & awards": "certifications"}},
    ),
    Template(
        "rover_fancy", "Rover Resume (fancy)",
        (Signal(r"^[A-Z]{6,}\n.*✉.* \| "), Signal(r"Rover R[ée]sum[ée]")),
        hints={"strip": [r"(?i)^rover r[ée]sum[ée]\s*[–-]\s*page \d+ of \d+$"]},
    ),
    Template(
        "chicv", "chicv (typst)",
        (Signal(r"\d{4}/\d{2} [–-] (?:\d{4}/\d{2}|Present)", 2),),
        hints={"layout": "leading"},
    ),
    Template(
        "simple_resume_cv", "simple-resume-cv (LaTeX)",
        (Signal(r"^■ .+ [A-Z][a-z]{2} \d{4} [–-] ", 2), Signal(r"^● ", 2)),
        min_signals=2,
        hints={"layout": "leading"},
    ),
    Template(
        "resumekit_docx", "ResumeKit (DOCX)",
        (
            Signal(r"^[A-Z][\w &/]+ at [^,\n]+, [A-Z][a-z]+ \d{4} - (?:till date|[Pp]resent|[A-Z][a-z]+ \d{4})$", 2),
        ),
    ),
    Template(
        "personal_data_docx", "Personal-data CV (DOCX, Philippine style)",
        (Signal(r"^PERSONAL DATA$"), Signal(r"^Date of Birth :"), Signal(r"^CAREER OBJECTIVE$")),
        min_signals=2,
    ),
    Template(
        "resume_ng_cn", "resume-ng (Chinese LaTeX)",
        (Signal(r"\(\+86\)\d{3}-\d{4}-\d{4}"), Signal(r"GP ?A: ?\d\.\d+/\d\.\d")),
        min_signals=2,
    ),
)

_BY_ID = {t.id: t for t in TEMPLATES}


def get_template(template_id: str | None) -> Template | None:
    return _BY_ID.get(template_id or "")


def detect_template(text: str) -> dict | None:
    """Best-matching known template for ``text``, or None. Never raises."""
    try:
        sample = (text or "")[:20000]
        best: tuple[float, Template] | None = None
        for tpl in TEMPLATES:
            ok = sum(1 for sig in tpl.signals if sig.hits(sample) >= sig.min_count)
            if ok < tpl.min_signals:
                continue
            score = ok / len(tpl.signals)
            if best is None or score > best[0]:
                best = (score, tpl)
        if best is None:
            return None
        return {"id": best[1].id, "name": best[1].name, "confidence": round(best[0], 2), "hints": best[1].hints}
    except Exception:
        return None


def apply_text_hints(text: str, hints: dict) -> str:
    """Drop template noise lines (page footers, 'last updated' stamps) before parsing."""
    patterns = [re.compile(p) for p in hints.get("strip", [])]
    if not patterns:
        return text
    return "\n".join(ln for ln in text.splitlines() if not any(p.search(ln.strip()) for p in patterns))

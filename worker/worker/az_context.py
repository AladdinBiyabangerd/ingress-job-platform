"""Azerbaijan / Baku mentions in a job ad, classified by context.

Shared by the deterministic pre-check (``worker.eligibility.assess``) and the AI quote
validation (``worker.market_fit.check_quote``) so both layers read a sentence the same way:

* ``positive``  — Azerbaijan / Baku (or a region that clearly includes it) is where the role
  is open: "Remote (Azerbaijan, Georgia)", "We hire in Azerbaijan", a title or location-field
  country list, "Baku office, on-site". Possible eligibility evidence only.
* ``negative``  — the mention sits in a negation / exclusion: "We do not hire from Azerbaijan",
  "excluding Azerbaijan", "Azerbaijan is not supported", "не розглядаються: Азербайджан".
  Restriction evidence.
* ``company``   — a statement about the company, its client, team or office ("Our client is
  based in Baku", "the team is international (Ukraine, Azerbaijan)"). Neutral.

Pure regex, no AI. A unit is the title, the location field, or one sentence / line of the text.
"""

from __future__ import annotations

import re
from typing import Iterable

# Azerbaijan / Baku in Latin, Azerbaijani and Cyrillic spelling.
AZ_NAME = re.compile(
    r"(?i)azerbaijan\w*|azərbaycan\w*|azerbaycan\w*|азербайджан\w*|\bbaku\b|\bbakı\b|\bбаку\b"
)
# Regions that clearly include Azerbaijan (the pre-check's historical set).
AZ_REGION = re.compile(
    r"(?i)\bcis\b(?!\s+(?:benchmarks?|controls?|level|hardening))|caucasus|central\s+asia"
)

# Negation / exclusion words (English + Russian / Ukrainian).
NEGATION = re.compile(
    r"(?i)\b(?:not|no|never|none|nor|unable|cannot|unfortunately|unavailable|ineligible|"
    r"without|excluding|exclude[sd]?|except)\b|n['’]t\b|"
    r"(?<!\w)(?:не|ні|нет|без|крім|окрім|кроме|исключая|за\s+исключением)(?!\w)"
)
# Phrases with a negation word that still read positive.
NEGATION_OK = re.compile(
    r"(?i)\bno\s+matter\b|\bregardless\b|\bnot\s+(?:limited|restricted|tied|bound)\s+to\b|"
    r"\bwithout\s+(?:any\s+)?(?:location|geographic(?:al)?|country|borders?)"
    r"(?:\s+(?:restrictions?|limits?|limitations?|boundaries))?\b|"
    r"\bno\s+(?:location|geographic(?:al)?|country)\s+(?:restrictions?|limits?|limitations?|requirements?)\b|"
    r"\bwithout\s+(?:the\s+)?need\s+to\s+relocate\b"
)
# A negation about something else ("no relocation", "not required: degree") is not about AZ.
_NEGATION_OTHER = re.compile(
    r"(?i)^\W{0,3}(?:\w+\W+){0,2}?(?:relocat\w*|visa|sponsor\w*|equity|travel\w*|on[\s-]?call|experience|"
    r"degree|agenc\w*|recruit\w*|overtime)\b"
)
NEAR_BEFORE = 60  # a negation up to this many characters before the mention
NEAR_AFTER = 30  # "Azerbaijan is not supported": a short tail after the mention

COMPANY_SUBJECT = re.compile(
    r"(?i)\b(?:company|companies|client|clients|customer|customers|partner|partners|operator|team|teams|"
    r"employees|colleagues|workforce|headquarter\w*|offices?|organi[sz]ation|subsidiary|bank|market|markets)\b|"
    r"\bazerbaijani\s+\w+"
)
WORK_WORDING = re.compile(
    r"(?i)\b(?:remote(?:ly)?|hybrid|on[\s-]?site|in[\s-]office|office[\s-]based|work(?:ing)?\s+(?:from|in)|"
    r"hire|hiring|open\s+(?:to|for)|candidates?|applicants?|you|your|location|allowed|eligible|relocat\w*|"
    r"role|position|job|vacanc\w*)\b|дозвол\w*|віддален\w*|удал[её]нн\w*"
)


def company_statement(unit: str) -> bool:
    """A sentence about the company / client / team / office, with no work-place wording."""
    return bool(COMPANY_SUBJECT.search(unit)) and not WORK_WORDING.search(unit)


def _mask_ok(text: str) -> str:
    return NEGATION_OK.sub(lambda m: " " * len(m.group(0)), text)


def negation_near(unit: str, start: int, end: int) -> str:
    """The negation word governing the mention at unit[start:end], or ''."""
    text = _mask_ok(unit)
    for neg in NEGATION.finditer(text):
        if neg.end() <= start:
            if start - neg.end() > NEAR_BEFORE:
                continue
        elif neg.start() >= end:
            if neg.start() - end > NEAR_AFTER:
                continue
            tail = text[neg.end():neg.end() + 25]
            if re.match(r"(?i)exclud|except|крім|окрім|кроме|исключ|за\s", neg.group(0)) and re.search(
                r"[A-ZА-ЯІЇЄ][a-zа-яіїє]", tail
            ) and not AZ_NAME.search(tail):
                continue  # "Azerbaijan, Georgia (except Russia)": the exclusion names another place
        else:
            continue
        if _NEGATION_OTHER.search(text[neg.end():neg.end() + 40]):
            continue  # "no relocation", "not required: degree"
        return neg.group(0).lower()
    return ""


def units(title: str = "", place: str = "", text: str = "") -> list[tuple[str, str]]:
    """(source, unit): the title, the location field, then each sentence / line of the text."""
    out: list[tuple[str, str]] = []
    if (title or "").strip():
        out.append(("title", " ".join(title.split())))
    if (place or "").strip():
        out.append(("location", " ".join(place.split())))
    for line in (text or "").splitlines():
        for part in re.split(r"(?<=[.!?;])\s+", line):
            part = " ".join(part.split())
            if part:
                out.append(("text", part))
    return out


def classify_unit(unit: str) -> list[tuple[str, str]]:
    """[(context, matched name)] for every AZ / region mention in one unit."""
    found: list[tuple[str, str]] = []
    company = company_statement(unit)
    for rx in (AZ_NAME, AZ_REGION):
        for m in rx.finditer(unit):
            if negation_near(unit, m.start(), m.end()):
                found.append(("negative", m.group(0)))
            elif company:
                found.append(("company", m.group(0)))
            else:
                found.append(("positive", m.group(0)))
    return found


def az_mentions(title: str = "", place: str = "", text: str = "",
                extra_positive: Iterable[str] = ()) -> dict[str, list[str]]:
    """{'positive': [unit, …], 'negative': […], 'company': […]} (each unit once, first context wins
    per unit in the order negative > positive > company for that unit's own mentions)."""
    result: dict[str, list[str]] = {"positive": [], "negative": [], "company": []}
    for source, unit in units(title, place, text):
        kinds = {kind for kind, _ in classify_unit(unit)}
        if not kinds:
            continue
        for kind in ("negative", "positive", "company"):
            if kind in kinds:
                label = unit if source == "text" else f"{'Başlıq' if source == 'title' else 'Yer sahəsi'}: {unit}"
                if label not in result[kind]:
                    result[kind].append(label)
    for pin in extra_positive:
        if pin and pin not in result["positive"]:
            result["positive"].append(f"Mənbə ölkəsi: {pin}")
    return result


def quote_az_context(quote: str) -> str:
    """'positive' | 'negative' | 'company' | '' for one AI quote (strongest negative first)."""
    kinds = {kind for kind, _ in classify_unit(" ".join((quote or "").split()))}
    for kind in ("negative", "positive", "company"):
        if kind in kinds:
            return kind
    return ""

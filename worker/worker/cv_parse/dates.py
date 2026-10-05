"""Date-range parsing and overlapping experience merge (years)."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date

from worker.cv_parse.locale import fold_az

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "yan": 1,
    "yanvar": 1,
    "fev": 2,
    "fevral": 2,
    "mart": 3,
    "aprel": 4,
    "iyn": 6,
    "iyun": 6,
    "iyl": 7,
    "iyul": 7,
    "avq": 8,
    "avqust": 8,
    "sen": 9,
    "sentyabr": 9,
    "okt": 10,
    "oktyabr": 10,
    "noy": 11,
    "noyabr": 11,
    "dek": 12,
    "dekabr": 12,
    "янв": 1,
    "январь": 1,
    "января": 1,
    "фев": 2,
    "февраль": 2,
    "февраля": 2,
    "мар": 3,
    "март": 3,
    "марта": 3,
    "апр": 4,
    "апрель": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июн": 6,
    "июнь": 6,
    "июня": 6,
    "июл": 7,
    "июль": 7,
    "июля": 7,
    "авг": 8,
    "август": 8,
    "августа": 8,
    "сен": 9,
    "сентябрь": 9,
    "сентября": 9,
    "окт": 10,
    "октябрь": 10,
    "октября": 10,
    "ноя": 11,
    "ноябрь": 11,
    "ноября": 11,
    "дек": 12,
    "декабрь": 12,
    "декабря": 12,
}

# "н.в." / "нв" = настоящее время (common RU CV abbreviation)
_PRESENT_TOKEN = (
    r"present|current|now|today|hal-hazırda|halhazirda|hazırda|hazirda|indi|"
    r"н\.?\s*в\.?|н/в|"
    r"настоящее(?:\s+время)?|по\s+настоящее(?:\s+время)?|"
    r"по\s+н\.?\s*в\.?|n\/a|tbd"
)

_PRESENT = re.compile(rf"(?i)^(?:{_PRESENT_TOKEN})$")

_MONTH_TOKEN = (
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
    r"january|february|march|april|june|july|august|september|october|november|december|"
    # ASCII capital I folds to ı; accept both iyul and ıyul forms in the token.
    r"yan|yanvar|fev|fevral|mart|aprel|may|iyn|ıyn|iyun|ıyun|iyl|ıyl|iyul|ıyul|"
    r"avq|avqust|sen|sentyabr|"
    r"okt|oktyabr|noy|noyabr|dek|dekabr|"
    r"янв(?:арь|аря)?|фев(?:раль|раля)?|мар(?:та?)?|апр(?:ель|еля)?|мая?|"
    r"июн(?:ь|я)?|июл(?:ь|я)?|авг(?:уста?)?|сен(?:тябрь|тября)?|"
    r"окт(?:ябрь|ября)?|ноя(?:брь|бря)?|дек(?:абрь|абря)?)"
)

# Optional day before month: "16 Fev 2026", "03 İyul 2026"
_DAY_PREFIX = r"(?:(?:0?[1-9]|[12]\d|3[01])\s+)?"
_MONTH_YEAR = rf"(?:{_DAY_PREFIX}{_MONTH_TOKEN}[\s\./\-]+)?(?:19|20)\d{{2}}"

_RANGE = re.compile(
    rf"(?ix)"
    rf"(?P<start>"
    rf"{_MONTH_YEAR}"
    rf"|"
    rf"(?:0?[1-9]|1[0-2])[\./\-](?:19|20)\d{{2}}"
    rf")"
    rf"\s*(?:–|—|-|to|until|через|dək|:)\s*"
    rf"(?P<end>"
    rf"{_PRESENT_TOKEN}|"
    rf"{_MONTH_YEAR}"
    rf"|"
    rf"(?:0?[1-9]|1[0-2])[\./\-](?:19|20)\d{{2}}"
    rf")"
)


def _month_num(token: str) -> int:
    """Resolve month name; map folded ASCII-I (ı) back to dotted i for AZ months."""
    key = fold_az(token or "")
    if not key:
        return 0
    if key in _MONTHS:
        return _MONTHS[key]
    return _MONTHS.get(key.replace("ı", "i"), 0)


def parse_month(token: str, *, end: bool = False) -> date | None:
    """Parse a month/year token into a date (day = 1, or month-end when end=True)."""
    raw = fold_az((token or "").strip())
    if not raw:
        return None
    if _PRESENT.match(raw):
        today = date.today()
        if end:
            return today
        return date(today.year, today.month, 1)
    raw = raw.replace(".", "/").replace("-", " ")
    parts = [p for p in re.split(r"[\s/]+", raw) if p]
    if not parts:
        return None
    year = None
    month = 1
    if len(parts) == 1 and re.fullmatch(r"(?:19|20)\d{2}", parts[0]):
        year = int(parts[0])
        month = 12 if end else 1
    elif len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) <= 2:
        # "16 fev 2026" / "03 iyul 2026"
        if parts[-1].isdigit() and len(parts[-1]) == 4:
            month = _month_num(parts[1])
            year = int(parts[-1])
        else:
            return None
    elif len(parts) >= 2:
        if (
            parts[0].isdigit()
            and len(parts[0]) <= 2
            and parts[-1].isdigit()
            and len(parts[-1]) == 4
            and all(p.isdigit() for p in parts[:-1])
        ):
            month = int(parts[0])
            year = int(parts[-1])
        elif parts[-1].isdigit() and len(parts[-1]) == 4:
            year = int(parts[-1])
            month = _month_num(parts[0])
        else:
            return None
    else:
        return None
    if year is None or not (1 <= month <= 12):
        return None
    day = monthrange(year, month)[1] if end else 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_ranges(text: str) -> list[tuple[date, date, str, str]]:
    """Return (start, end, start_token, end_token) for each range in text."""
    out: list[tuple[date, date, str, str]] = []
    folded = fold_az(text or "")
    for m in _RANGE.finditer(folded):
        start = parse_month(m.group("start"), end=False)
        end = parse_month(m.group("end"), end=True)
        if start and end and end >= start:
            out.append((start, end, m.group("start"), m.group("end")))
    return out


def years_between(start: date, end: date) -> float:
    days = (end - start).days
    if days < 0:
        return 0.0
    return round(days / 365.25, 2)


def merge_years(ranges: list[tuple[date, date]]) -> float:
    """Union length of date ranges in years (overlapping periods merged)."""
    if not ranges:
        return 0.0
    ordered = sorted(ranges, key=lambda r: r[0])
    merged: list[list[date]] = [[ordered[0][0], ordered[0][1]]]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    total = sum(years_between(a, b) for a, b in merged)
    return round(total, 2)


def iso_month(value: date | None) -> str | None:
    if value is None:
        return None
    return f"{value.year:04d}-{value.month:02d}"

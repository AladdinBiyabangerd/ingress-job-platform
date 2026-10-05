"""Parse free-text job salary for trend aggregates (plan §7.1).

Only unambiguous currency + period are accepted (same spirit as frontend/lib/salary.js).
Amounts are annualized in the source currency — no FX conversion.
"""

from __future__ import annotations

import re
from statistics import median
from typing import Any

CODES = (
    "AZN",
    "GBP",
    "EUR",
    "USD",
    "CAD",
    "AUD",
    "NZD",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "HUF",
    "RON",
    "BGN",
    "TRY",
    "UAH",
    "RUB",
    "GEL",
    "KZT",
    "INR",
    "JPY",
    "CNY",
    "KRW",
    "SGD",
    "HKD",
    "AED",
    "SAR",
    "QAR",
    "ILS",
    "ZAR",
    "BRL",
    "MXN",
    "ARS",
    "CLP",
    "COP",
)

_SYMBOLS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"£"), "GBP"),
    (re.compile(r"€"), "EUR"),
    (re.compile(r"₼|\bmanat\b|\bman\.(?=\s|$)", re.I), "AZN"),
    (re.compile(r"₽|\bруб", re.I), "RUB"),
    (re.compile(r"₹"), "INR"),
    (re.compile(r"₩"), "KRW"),
    (re.compile(r"₺"), "TRY"),
    (re.compile(r"₴|\bгрн\b", re.I), "UAH"),
    (re.compile(r"\bUS\$|\bUS\s?dollars?\b", re.I), "USD"),
    (re.compile(r"\bC\$|\bCA\$"), "CAD"),
    (re.compile(r"\bA\$|\bAU\$"), "AUD"),
    (re.compile(r"\bS\$"), "SGD"),
    (re.compile(r"\bR\$"), "BRL"),
)

_PERIODS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "YEAR",
        re.compile(
            r"\bper\s+(?:annum|year)\b|\ba\s+year\b|\bannual(?:ly)?\b|\byearly\b|"
            r"/\s*(?:year|yr|y)\b|\bp\.?\s?a\.?(?=\s|$|[),])|\billik\b|\bв\s+год\b|\bгодов",
            re.I,
        ),
    ),
    (
        "MONTH",
        re.compile(
            r"\bper\s+month\b|\ba\s+month\b|\bmonthly\b|/\s*(?:month|mo|mon)\b|"
            r"\baylıq\b|\bayda\b|\bв\s+месяц\b|\bмес\b|/\s*мес",
            re.I,
        ),
    ),
    (
        "WEEK",
        re.compile(
            r"\bper\s+week\b|\ba\s+week\b|\bweekly\b|/\s*(?:week|wk)\b|"
            r"\bhəftəlik\b|\bв\s+неделю\b",
            re.I,
        ),
    ),
    (
        "DAY",
        re.compile(
            r"\bper\s+day\b|\ba\s+day\b|\bdaily\b|/\s*day\b|\bgünlük\b|\bв\s+день\b",
            re.I,
        ),
    ),
)

# Hourly skipped — too noisy for annual skill medians.
_ANNUAL_FACTOR = {
    "YEAR": 1.0,
    "MONTH": 12.0,
    "WEEK": 52.0,
    "DAY": 260.0,
}

_AMOUNT_RE = re.compile(
    r"(\d{1,3}(?:[ \u00a0,.]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*([kK])?\b"
)


def salary_currency(text: str) -> str:
    raw = str(text or "")
    found: set[str] = set()
    upper = raw.upper()
    for code in CODES:
        if re.search(rf"(^|[^A-Z]){code}([^A-Z]|$)", upper):
            found.add(code)
    for pattern, code in _SYMBOLS:
        if pattern.search(raw):
            found.add(code)
    return next(iter(found)) if len(found) == 1 else ""


def salary_period(text: str) -> str:
    raw = str(text or "")
    found = [unit for unit, pattern in _PERIODS if pattern.search(raw)]
    return found[0] if len(found) == 1 else ""


def _to_number(token: str, suffix: str | None) -> float | None:
    digits = token.replace(" ", "").replace("\u00a0", "")
    if "," in digits and "." in digits:
        digits = (
            digits.replace(",", "")
            if digits.rfind(".") > digits.rfind(",")
            else digits.replace(".", "").replace(",", ".")
        )
    elif re.fullmatch(r"\d{1,3}([,.]\d{3})+", digits):
        digits = re.sub(r"[,.]", "", digits)
    else:
        digits = digits.replace(",", ".")
    try:
        value = float(digits)
    except ValueError:
        return None
    if value <= 0:
        return None
    if suffix and re.search(r"k", suffix, re.I):
        value *= 1000.0
    return value


def salary_amounts(text: str) -> list[float]:
    out: list[float] = []
    for match in _AMOUNT_RE.finditer(str(text or "")):
        value = _to_number(match.group(1), match.group(2))
        if value is not None:
            out.append(value)
    return out


def parse_salary_annual(text: object) -> dict[str, Any] | None:
    """Return annualized mid amount in source currency, or None if ambiguous."""
    raw = str(text or "").strip()
    if not raw:
        return None
    currency = salary_currency(raw)
    period = salary_period(raw)
    if not currency or not period:
        return None
    amounts = salary_amounts(raw)
    if not amounts or len(amounts) > 2:
        return None
    mid = (min(amounts) + max(amounts)) / 2.0 if len(amounts) == 2 else amounts[0]
    factor = _ANNUAL_FACTOR[period]
    annual = mid * factor
    if annual <= 0:
        return None
    return {
        "currency": currency,
        "period": period,
        "mid": mid,
        "annual": annual,
    }


def salary_stats(values: list[float], currency: str) -> dict[str, Any] | None:
    """Median + range for annualized amounts in one currency."""
    cleaned = [float(v) for v in values if isinstance(v, (int, float)) and v > 0]
    if not cleaned or not currency:
        return None
    cleaned.sort()
    return {
        "median": round(float(median(cleaned)), 2),
        "low": round(cleaned[0], 2),
        "high": round(cleaned[-1], 2),
        "currency": currency,
        "n": len(cleaned),
    }


def pick_currency_values(parsed: list[dict[str, Any]]) -> tuple[str, list[float]]:
    """Prefer the currency with the most samples; tie → lexicographic."""
    by_currency: dict[str, list[float]] = {}
    for item in parsed:
        code = str(item.get("currency") or "")
        annual = item.get("annual")
        if not code or not isinstance(annual, (int, float)) or annual <= 0:
            continue
        by_currency.setdefault(code, []).append(float(annual))
    if not by_currency:
        return "", []
    best = max(by_currency.items(), key=lambda kv: (len(kv[1]), kv[0]))
    return best[0], best[1]

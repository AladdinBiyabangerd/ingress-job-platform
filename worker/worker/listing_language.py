"""Detect job listing language from title + body.

Single source for worker ingest/backfill and the API list/filter path.
Body wins over English titles; bilingual / weak scores fall back to en.
"""

from __future__ import annotations

import re
from html import unescape

LANG_FACET_ORDER = ("az", "en", "ru", "tr", "es", "uk", "de", "fr", "pt")
# Cabinet az|ru stay trusted even if body looks different.
TRUSTED_STORED_LANGS = ("az", "ru")
LANGUAGE_SAMPLE_CHARS = 1200
LANG_SCORE_MIN = 3
LANG_SCORE_MARGIN = 2

_AZ_SCHWA = re.compile(r"[əƏ]")
_AZ_HINT = re.compile(r"[ğıİıĞ]")
_AZ_WORDS = re.compile(
    r"\b(və|ilə|üçün|olan|olunan|tələb|mühəndis|əməkdaş|şirkət|elan|işçi|təcrübə)\b",
    re.I,
)
_UK = re.compile(r"[іїєґІЇЄҐ]")
_CYR = re.compile(r"[а-яёА-ЯЁ]")
_TAG = re.compile(r"<[^>]+>")
_MOJIBAKE = re.compile(r"[\u00c2\u00c3\u00e2][\u0080-\u00bf]+")

_LATIN_LANG_MARKERS: tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...] = (
    (
        "de",
        re.compile(
            r"\b(und|der|die|das|dem|den|mit|für|oder|wir|suchen|sind|eine?n?|"
            r"sowie|über|bei|nach|werden|haben|nicht|auch|aufgaben|profil|"
            r"erfahrung|kenntnisse|bewerbung|gmbh)\b",
            re.I,
        ),
        re.compile(r"[äöüßÄÖÜ]"),
    ),
    (
        "fr",
        re.compile(
            r"\b(et|les|des|une|pour|avec|nous|dans|sont|cette|votre|nos|"
            r"être|chez|vous|recherchons|expérience|poste|entreprise)\b",
            re.I,
        ),
        re.compile(r"[àâçéèêëîïôùûœÀÂÇÉÈÊËÎÏÔÙÛŒ]"),
    ),
    (
        "es",
        re.compile(
            r"\b(el|los|las|para|con|una|experiencia|del|por|como|más|trabajo|"
            r"somos|nuestro|nuestra|empresa|puesto|requisitos|buscamos)\b",
            re.I,
        ),
        re.compile(r"[áéíóúñ¿¡ÁÉÍÓÚÑ]"),
    ),
    (
        "pt",
        re.compile(
            r"\b(não|você|vocês|pelo|pela|pelos|pelas|também|trabalho|"
            r"experiência|anos|vaga|procuramos|nosso|nossa|com)\b",
            re.I,
        ),
        re.compile(r"[áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]"),
    ),
    (
        "tr",
        re.compile(
            r"\b(ve|bir|için|ile|olan|olarak|arıyoruz|deneyim|şirket|"
            r"pozisyon|çalışma|hakkında|başvuru|gereksinim|yıl)\b",
            re.I,
        ),
        re.compile(r"[ğüşıöçĞÜŞİÖÇ]"),
    ),
)


def _repair_text(value: str) -> str:
    if not value:
        return ""
    if not any(mark in value for mark in ("\u00c2", "\u00c3", "\u00e2", "\u00a0")):
        return value
    try:
        return value.encode("latin1").decode("utf-8")
    except UnicodeError:
        pass

    def repair_run(match: re.Match[str]) -> str:
        chunk = match.group(0)
        try:
            return chunk.encode("latin1").decode("utf-8")
        except UnicodeError:
            return chunk

    value = _MOJIBAKE.sub(repair_run, value)
    return value.replace("\u00c2", "").replace("\u00a0", " ")


def listing_language(title: str, body: str) -> str:
    """Detect listing language from title + body (body wins over EN titles)."""
    raw = _TAG.sub(" ", unescape(_repair_text(body or "")))
    sample = f"{title or ''}\n{raw[:LANGUAGE_SAMPLE_CHARS]}"
    if _AZ_SCHWA.search(sample) or (_AZ_HINT.search(sample) and _AZ_WORDS.search(sample)):
        return "az"
    if _UK.search(sample):
        return "uk"
    if _CYR.search(sample):
        return "ru"

    scores: dict[str, int] = {}
    for code, words_re, chars_re in _LATIN_LANG_MARKERS:
        word_hits = len(words_re.findall(sample))
        char_hits = len(chars_re.findall(sample)) if chars_re is not None else 0
        score = word_hits + min(char_hits, 4)
        if score:
            scores[code] = score

    if not scores:
        return "en"

    def _rank(item: tuple[str, int]) -> tuple[int, int]:
        code, score = item
        order = LANG_FACET_ORDER.index(code) if code in LANG_FACET_ORDER else 99
        return (score, -order)

    best_code, best_score = max(scores.items(), key=_rank)
    if best_score < LANG_SCORE_MIN:
        return "en"
    second = max((s for c, s in scores.items() if c != best_code), default=0)
    if best_score - second < LANG_SCORE_MARGIN:
        return "en"
    return best_code


def resolve_listing_language(stored: str, title: str, body: str = "") -> str:
    """Trust persisted facet codes; infer only when the column is empty/unknown.

    Cabinet az|ru labels are always trusted. After worker backfill, stored en/de/…
    are authoritative so list/matching stay aligned without body scans.
    """
    code = (stored or "").strip().lower()
    if code in TRUSTED_STORED_LANGS:
        return code
    if code in LANG_FACET_ORDER:
        return code
    return listing_language(title, body)

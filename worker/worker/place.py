"""Normalize place strings before jobs.city is stored (worker ingest)."""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
_PARENS = re.compile(r"\([^)]*\)")
_REMOTE_RE = re.compile(
    r"(?i)^(?:"
    r"remote(?:\b|[\s,/(-].*)?|"
    r"uzaqdan|"
    r"удал[её]нн\w*|"
    r"work[\s-]?from[\s-]?anywhere|"
    r"anywhere(?:\s+in\s+the\s+world)?|"
    r"worldwide|world[\s-]?wide|"
    r"global(?:ly)?|"
    r"distributed|"
    r"location[\s-]?independent|"
    r"telecommute|"
    r"wfh"
    r")$"
)
_CANON = {
    "tokyo": "Tokyo, Japan",
    "amsterdam": "Amsterdam, Netherlands",
    "barcelona": "Barcelona, Spain",
    "leonberg": "Leonberg, Germany",
    "berlin": "Berlin, Germany",
    "london": "London, UK",
    "paris": "Paris, France",
    "munich": "Munich, Germany",
    "munchen": "Munich, Germany",
    "münchen": "Munich, Germany",
    "dublin": "Dublin, Ireland",
    "lisbon": "Lisbon, Portugal",
    "lisboa": "Lisbon, Portugal",
    "warsaw": "Warsaw, Poland",
    "krakow": "Kraków, Poland",
    "kraków": "Kraków, Poland",
    "prague": "Prague, Czechia",
    "vienna": "Vienna, Austria",
    "stockholm": "Stockholm, Sweden",
    "oslo": "Oslo, Norway",
    "copenhagen": "Copenhagen, Denmark",
    "helsinki": "Helsinki, Finland",
    "zurich": "Zurich, Switzerland",
    "zürich": "Zurich, Switzerland",
    "singapore": "Singapore",
    "dubai": "Dubai, UAE",
    "baku": "Bakı",
    "bakı": "Bakı",
    "baki": "Bakı",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def clean_place(value: str) -> str:
    return _WS.sub(" ", str(value or "").replace("\u00a0", " ")).strip(" ,;/|-")


def is_remote_place(value: str) -> bool:
    raw = clean_place(value)
    if not raw:
        return False
    compact = _WS.sub(" ", _PARENS.sub(" ", raw)).strip(" ,;/|-")
    if not compact:
        return True
    if _REMOTE_RE.match(compact):
        return True
    folded = _fold(compact)
    if folded.startswith("remote"):
        return True
    if folded in {"uzaqdan", "удаленно", "удалённо", "worldwide", "world wide", "anywhere"}:
        return True
    if "work from anywhere" in folded or "anywhere in the world" in folded:
        return True
    return False


def place_key(value: str) -> str:
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    head = _WS.sub(" ", _PARENS.sub(" ", raw.split(",", 1)[0])).strip(" ,;/|-")
    if not head:
        return ""
    key = _fold(head)
    if key in {"baku", "baki"}:
        return "bakı"
    if key in {"munchen", "muenchen"}:
        return "münchen"
    if key in {"lisboa"}:
        return "lisbon"
    if key in {"krakow"}:
        return "kraków"
    if key in {"zurich"}:
        return "zürich"
    return key


def normalize_city(value: str) -> str:
    """Storage form: empty for remote labels; canon city when known."""
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    key = place_key(raw)
    if key in _CANON:
        return _CANON[key]
    if "," in raw:
        city, rest = raw.split(",", 1)
        city = city.strip()
        rest = rest.strip()
        if city and rest:
            return f"{city}, {rest}"
    return raw

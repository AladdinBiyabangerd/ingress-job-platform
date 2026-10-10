"""Normalize scraped place strings for facets and filters.

Remote / worldwide variants are not real cities — the board already has a
Remote filter. City names like \"Tokyo\" and \"Tokyo, Japan\" collapse to one key.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

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
# Canonical display for common city keys (after place_key).
_CANON_LABEL = {
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
    text = _WS.sub(" ", str(value or "").replace("\u00a0", " ")).strip(" ,;/|-")
    return text


def is_remote_place(value: str) -> bool:
    """True when the string is a remote/worldwide label, not a city."""
    raw = clean_place(value)
    if not raw:
        return False
    compact = _PARENS.sub(" ", raw)
    compact = _WS.sub(" ", compact).strip(" ,;/|-")
    if not compact:
        return True
    if _REMOTE_RE.match(compact):
        return True
    # "Remote — CET", "Fully Remote / Worldwide", etc.
    folded = _fold(compact)
    if folded.startswith("remote"):
        return True
    if folded in {"uzaqdan", "удаленно", "удалённо", "worldwide", "world wide", "anywhere"}:
        return True
    if "work from anywhere" in folded or "anywhere in the world" in folded:
        return True
    return False


def place_key(value: str) -> str:
    """Stable merge key. Empty for blank/remote places."""
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    head = raw.split(",", 1)[0]
    head = _PARENS.sub(" ", head)
    head = _WS.sub(" ", head).strip(" ,;/|-")
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


def place_label(value: str) -> str:
    """Preferred display label for a stored city string."""
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    key = place_key(raw)
    if key in _CANON_LABEL:
        return _CANON_LABEL[key]
    # Prefer "City, Country" already on the row.
    if "," in raw:
        city, rest = raw.split(",", 1)
        city = city.strip()
        rest = rest.strip()
        if city and rest:
            return f"{city}, {rest}"
    return raw


def pick_label(labels: Counter[str]) -> str:
    """Best display name among raw variants that share a place_key."""
    if not labels:
        return ""
    # Prefer canonical map when any variant maps to a known city.
    for raw in labels:
        key = place_key(raw)
        if key in _CANON_LABEL:
            return _CANON_LABEL[key]
    ranked = sorted(
        labels.items(),
        key=lambda item: (
            0 if "," in item[0] else 1,
            -item[1],
            -len(item[0]),
            item[0].lower(),
        ),
    )
    return place_label(ranked[0][0]) or ranked[0][0]


def aggregate_cities(rows: list[tuple[str, int]], *, limit: int = 24) -> list[dict]:
    """Collapse raw (city, total) rows into facet items."""
    groups: dict[str, dict] = {}
    for raw, total in rows:
        name = clean_place(raw)
        if not name or is_remote_place(name):
            continue
        key = place_key(name)
        if not key:
            continue
        bucket = groups.get(key)
        if bucket is None:
            bucket = {"total": 0, "labels": Counter()}
            groups[key] = bucket
        bucket["total"] += int(total or 0)
        bucket["labels"][name] += int(total or 0)

    items = []
    for key, bucket in groups.items():
        label = pick_label(bucket["labels"])
        if not label:
            continue
        items.append({"name": label, "total": bucket["total"], "key": key})
    items.sort(key=lambda item: (-item["total"], item["name"].lower()))
    return [{"name": item["name"], "total": item["total"]} for item in items[:limit]]


def matching_stored_cities(city_query: str, stored: list[str]) -> list[str]:
    """Raw DB city values that should match a facet selection."""
    wanted = place_key(city_query)
    if not wanted:
        # Exact fallback for odd labels.
        q = clean_place(city_query).casefold()
        return [s for s in stored if clean_place(s).casefold() == q]
    out = []
    for raw in stored:
        if place_key(raw) == wanted:
            out.append(raw)
    # Always include the query itself so exact rows still match.
    q = clean_place(city_query)
    if q and q not in out:
        out.append(q)
    return out

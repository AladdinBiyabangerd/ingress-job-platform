"""Normalize scraped place strings for facets and filters.

Location facets are country-level. City strings like \"Tokyo\" and
\"Tokyo, Japan\" resolve to Japan; remote/worldwide labels are excluded
(the board already has a Remote filter).

Accuracy rule: never invent a country. Prefer an explicit country/region
suffix; fall back to a curated city→country map only for unambiguous hubs.
Unresolved places are omitted from country facets rather than guessed.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.place_data import CANON_LABEL, CITY_COUNTRY, COUNTRY_ALIASES

_WS = re.compile(r"\s+")
_PARENS = re.compile(r"\([^)]*\)")
_SITE_TAIL = re.compile(
    r"(?i)\s*[-–—,/]?\s*\b(?:"
    r"hq|headquarters|head\s*office|office|campus|site|hub|"
    r"area|metro|region|greater|metropolitan"
    r")\b.*$"
)
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

_CANON_LABEL = CANON_LABEL
_CITY_COUNTRY = CITY_COUNTRY
_COUNTRY_ALIASES = COUNTRY_ALIASES

# Spelling variants collapsed before city/country lookup.
_CITY_KEY_ALIASES = {
    "baku": "bakı",
    "baki": "bakı",
    "munchen": "münchen",
    "muenchen": "münchen",
    "munich": "munich",
    "lisboa": "lisbon",
    "krakow": "kraków",
    "zurich": "zürich",
    "dusseldorf": "düsseldorf",
    "duesseldorf": "düsseldorf",
    "koln": "köln",
    "koeln": "köln",
    "cologne": "cologne",
    "nurnberg": "nürnberg",
    "nuernberg": "nürnberg",
    "nuremberg": "nuremberg",
    "geneve": "geneva",
    "genève": "geneva",
    "goteborg": "göteborg",
    "gothenburg": "gothenburg",
    "malmo": "malmö",
    "kobenhavn": "københavn",
    "warszawa": "warsaw",
    "wroclaw": "wrocław",
    "gdansk": "gdańsk",
    "lodz": "łódź",
    "poznan": "poznań",
    "praha": "prague",
    "milano": "milan",
    "roma": "rome",
    "napoli": "naples",
    "torino": "turin",
    "firenze": "florence",
    "venezia": "venice",
    "sevilla": "seville",
    "bruxelles": "brussels",
    "brussel": "brussels",
    "antwerpen": "antwerp",
    "gent": "ghent",
    "den haag": "the hague",
    "kyiv": "kyiv",
    "kiev": "kyiv",
    "bengaluru": "bengaluru",
    "bangalore": "bengaluru",
}

# US state / DC abbreviations and common full names (comma suffix → United States).
_US_REGIONS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il",
    "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt",
    "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri",
    "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "hawaii", "idaho", "illinois",
    "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico",
    "new york", "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee",
    "texas", "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia",
}

_CA_REGIONS = {
    "ab", "bc", "mb", "nb", "nl", "ns", "nt", "nu", "on", "pe", "qc", "sk", "yt",
    "alberta", "british columbia", "manitoba", "new brunswick",
    "newfoundland and labrador", "newfoundland", "nova scotia",
    "northwest territories", "nunavut", "ontario", "prince edward island",
    "quebec", "québec", "saskatchewan", "yukon",
}

_NON_COUNTRY = {
    "emea", "apac", "latam", "amer", "na", "eu", "eea", "cis", "mena",
    "europe", "asia", "africa", "worldwide", "global", "remote", "hybrid",
    "onsite", "on-site", "office", "hq",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


_CANONICAL_COUNTRIES = {_fold(v): v for v in _COUNTRY_ALIASES.values()}


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
    folded = _fold(compact)
    if folded.startswith("remote"):
        return True
    if folded in {"uzaqdan", "удаленно", "удалённо", "worldwide", "world wide", "anywhere"}:
        return True
    if "work from anywhere" in folded or "anywhere in the world" in folded:
        return True
    return False


def _city_head(raw: str) -> str:
    """First city-like token, stripping HQ/Office tails and parentheticals."""
    head = raw.split(",", 1)[0]
    for sep in ("/", "|", ";", " - ", " – ", " — "):
        if sep in head:
            head = head.split(sep, 1)[0]
    head = _PARENS.sub(" ", head)
    head = _SITE_TAIL.sub("", head)
    return _WS.sub(" ", head).strip(" ,;/|-")


def place_key(value: str) -> str:
    """Stable merge key. Empty for blank/remote places."""
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    head = _city_head(raw)
    if not head:
        return ""
    key = _fold(head)
    return _CITY_KEY_ALIASES.get(key, key)


def place_label(value: str) -> str:
    """Preferred display label for a stored city string."""
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""
    key = place_key(raw)
    if key in _CANON_LABEL:
        return _CANON_LABEL[key]
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


def _alias_country(token: str) -> str:
    folded = _fold(clean_place(token))
    if not folded or folded in _NON_COUNTRY:
        return ""
    if folded in _COUNTRY_ALIASES:
        return _COUNTRY_ALIASES[folded]
    return _CANONICAL_COUNTRIES.get(folded, "")


def _suffix_country(token: str) -> str:
    """Resolve a comma-suffix fragment (country name or US/CA subdivision)."""
    part = clean_place(_PARENS.sub(" ", token))
    part = _SITE_TAIL.sub("", part).strip(" ,;/|-")
    if not part:
        return ""
    folded = _fold(part)
    if folded in _NON_COUNTRY:
        return ""
    if folded in _US_REGIONS:
        return "United States"
    if folded in _CA_REGIONS:
        return "Canada"
    resolved = _alias_country(part)
    if resolved:
        return resolved
    bits = [b for b in re.split(r"\s+", part) if b]
    if len(bits) >= 2:
        resolved = _alias_country(" ".join(bits[-2:]))
        if resolved:
            return resolved
    if bits:
        last = bits[-1]
        last_fold = _fold(last)
        if last_fold in _US_REGIONS:
            return "United States"
        if last_fold in _CA_REGIONS:
            return "Canada"
        return _alias_country(last)
    return ""


def country_label(value: str) -> str:
    """Canonical English country for a place string, or '' if unresolved.

    Order of trust:
    1. Curated city map when the city is a known unambiguous hub
       (wins over a conflicting scraped suffix — never put Tokyo under India)
    2. Explicit country / US-CA region after a comma
    3. Whole string is already a known country name
    """
    raw = clean_place(value)
    if not raw or is_remote_place(raw):
        return ""

    key = place_key(raw)
    mapped = _CITY_COUNTRY.get(key, "")

    suffix = ""
    if "," in raw:
        rest = raw.split(",", 1)[1]
        for part in re.split(r"[;/|]", rest):
            resolved = _suffix_country(part)
            if resolved:
                suffix = resolved
                break

    if mapped:
        # Known hub: trust the map. Suffix only used when it agrees (or is US/CA
        # region for US/CA cities). Conflicting suffixes are ignored.
        if not suffix or suffix == mapped:
            return mapped
        return mapped

    if suffix:
        return suffix

    return _alias_country(raw)

def country_key(value: str) -> str:
    """Stable country merge key, or '' when country cannot be resolved."""
    label = country_label(value)
    return _fold(label) if label else ""


def aggregate_cities(rows: list[tuple[str, int]], *, limit: int = 24) -> list[dict]:
    """Collapse raw (city, total) rows into city facet items (legacy helper)."""
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


def aggregate_countries(rows: list[tuple[str, int]], *, limit: int = 24) -> list[dict]:
    """Collapse raw (city, total) rows into country facet items."""
    groups: dict[str, dict] = {}
    for raw, total in rows:
        name = clean_place(raw)
        if not name or is_remote_place(name):
            continue
        label = country_label(name)
        key = _fold(label) if label else ""
        if not key:
            continue
        bucket = groups.get(key)
        if bucket is None:
            bucket = {"total": 0, "label": label}
            groups[key] = bucket
        bucket["total"] += int(total or 0)

    items = [
        {"name": bucket["label"], "total": bucket["total"]}
        for bucket in groups.values()
    ]
    items.sort(key=lambda item: (-item["total"], item["name"].lower()))
    return items[:limit]


def matching_stored_cities(city_query: str, stored: list[str]) -> list[str]:
    """Raw DB city values that should match a facet selection.

    Selection may be a country (Germany) or a legacy city label (Tokyo, Japan).
    """
    q = clean_place(city_query)
    if not q:
        return []

    as_country = _alias_country(q)
    if as_country:
        key = _fold(as_country)
        out = [raw for raw in stored if country_key(raw) == key]
        if q not in out:
            out.append(q)
        return out

    wanted = place_key(q)
    if not wanted:
        folded = q.casefold()
        return [s for s in stored if clean_place(s).casefold() == folded]
    out = [raw for raw in stored if place_key(raw) == wanted]
    if q not in out:
        out.append(q)
    return out

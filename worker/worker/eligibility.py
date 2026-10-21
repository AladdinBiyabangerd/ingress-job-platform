"""Can a candidate based in Azerbaijan take this job? Deterministic pre-check.

Runs before any AI and on already-stored pending ads. It never raises a score;
it only caps the rule / AI publish-fit % and explains why in Azerbaijani, so
the staff queue cannot show 85+ for an ad that Azerbaijan-based candidates
cannot really apply to.

Fields (same names as the market_fit AI schema):
- remote_scope: anywhere | az_listed | region_incl_az | country_locked
  | home_country_hybrid | onsite | unknown
- works_from_az: yes | no | unclear  (permanently, from Azerbaijan)
- relocation: yes | no, relocation_target: country/city or "" when not stated
- visa: yes | no

Azerbaijan / Baku mentions (``worker.az_context``, shared with the AI quote check):

* positive (allowed / hire in / remote from / listed in the title or location list,
  on-site Baku) -> ``works_from_az=yes``, cap 100: only a *candidate*; the AI quotes and
  the moderator decide.
* negative ("do not hire from Azerbaijan", "excluding Azerbaijan", "не розглядаються:
  Азербайджан") -> restriction evidence: ``works_from_az=no``, ``country_locked``, cap
  CAP_AZ_EXCLUDED (15). Never a pre-AI hard reject (cap 10) on the negation alone: the
  regex may misread a sentence, so the AI still checks the ad and the moderator sees why.
  A hard reject still happens when another rule locks the ad on its own.
* both positive and negative -> conflict: ``unclear``, cap CAP_AZ_CONFLICT (84, moderator).
* company / client / team / office statements ("Our client is based in Baku") -> neutral:
  ignored for eligibility, noted in the summary.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

from worker.az_context import AZ_NAME, az_mentions
from worker.techstack import (
    _AZ_EXPLICIT,
    _FOREIGN_GEO_RE,
    _INTL_RELOC,
    _named_foreign_place,
    _plain,
    _positive,
    region_restriction_reason,
    relocation_flag,
    remote_flag,
)

# No rule-only score may reach the 85 auto-approve band.
RULE_MAX = 80
APPROVE_BAND = 85
REASON_MAX = 800

CAP_LOCKED = 10  # cannot work from AZ and no relocation → rejected before AI
CAP_UNCLEAR = 40  # nothing confirms AZ eligibility
CAP_RELOC_UNCONFIRMED = 60  # relocation offered, target country or visa unknown
CAP_RELOC_CONFIRMED = 80  # relocation + visa + target stated (still a human check)
CAP_AZ_EXCLUDED = 15  # Azerbaijan named in a negation / exclusion (AI still checks; no hard reject)
CAP_AZ_CONFLICT = 84  # Azerbaijan both allowed and excluded: moderator decides

SCOPES = ("anywhere", "az_listed", "region_incl_az", "country_locked", "home_country_hybrid", "onsite", "unknown")
TRI = ("yes", "no", "unclear")

_COUNTRY_AZ = {
    "bulgaria": "Bolqarıstan", "united states": "ABŞ", "usa": "ABŞ", "u.s.": "ABŞ",
    "united kingdom": "Böyük Britaniya", "uk": "Böyük Britaniya", "georgia": "Gürcüstan",
    "argentina": "Argentina", "portugal": "Portuqaliya", "spain": "İspaniya",
    "poland": "Polşa", "germany": "Almaniya", "pakistan": "Pakistan", "india": "Hindistan",
    "ukraine": "Ukrayna", "greece": "Yunanıstan", "netherlands": "Niderland",
    "austria": "Avstriya", "romania": "Rumıniya", "turkey": "Türkiyə", "türkiye": "Türkiyə",
    "canada": "Kanada", "france": "Fransa", "italy": "İtaliya", "serbia": "Serbiya",
    "cyprus": "Kipr", "czech republic": "Çexiya", "czechia": "Çexiya", "armenia": "Ermənistan",
    "sofia": "Sofiya (Bolqarıstan)", "ireland": "İrlandiya", "sweden": "İsveç",
    "switzerland": "İsveçrə", "israel": "İsrail", "brazil": "Braziliya", "mexico": "Meksika",
}

# Benefits that are NOT permanent remote work from Azerbaijan.
_ABROAD_DAYS = re.compile(
    r"(?i)(?:up\s+to\s+)?\d{1,3}\s+(?:working\s+)?(?:days?|weeks?)\s+"
    r"(?:a|per|each|every)\s+(?:year|annum)[^\n.]{0,60}?(?:abroad|from\s+anywhere|outside)|"
    r"(?:work(?:ing)?|remotely)\s+(?:remotely\s+)?from\s+abroad\s+(?:for\s+)?(?:up\s+to\s+)?\d{1,3}\s+(?:days?|weeks?)|"
    r"\d{1,3}\s+(?:days?|weeks?)\s+(?:abroad|working\s+abroad|of\s+work\s+from\s+anywhere)|"
    r"(?:work\s+from\s+anywhere|workation)[^\n.]{0,40}\d{1,3}\s+(?:days?|weeks?)"
)
_FLEX_LOCATION = re.compile(
    r"(?i)flexible\s+(?:work(?:ing)?\s+)?(?:location|workplace|place)|"
    r"(?:work|working)\s+from\s+(?:home|the\s+office)\s+or\s+(?:from\s+)?(?:the\s+)?(?:office|home)|"
    r"\bhybrid\b"
)
# "anywhere in Georgia" / "work from anywhere in the U.S." is a country lock, not open.
_ANYWHERE_IN = re.compile(
    r"(?i)\banywhere['\"’”]?\s+(?:with)?in\s+(?:the\s+)?(?!world\b|the\s+world\b)"
    r"(?-i:([A-Z][\w.\-]*(?: [A-Z][\w.\-]*){0,2}))"
)
_OPEN_STRONG = re.compile(
    r"(?i)anywhere\s+in\s+the\s+world|\bworldwide\s+(?:remote|candidates?|applicants?|hiring)\b|"
    r"(?:accepting|hiring|open\s+to)\s+(?:candidates?\s+)?(?:from\s+)?(?:worldwide|any\s+country|all\s+countries)|"
    r"\bremote\s*(?:\(|-|–|:|,)\s*(?:worldwide|world[\s-]?wide|global|anywhere)\b|"
    r"location[\s-]?independent|no\s+location\s+restrict\w*|from\s+any\s+(?:country|location)\b|"
    r"\bemea\b|\beméa\b|\bcaucasus\b|"
    r"\bhire\s+(?:globally|worldwide)\s+regardless\s+of\s+(?:time\s?zones?|location|country)\b|"
    r"(?<![,\w]\s)(?<!anyone,\s)\bwork\s+from\s+anywhere\b['\"’”]?(?!\s+(?:with)?in\b)(?![^\n.]{0,40}\d{1,3}\s+(?:days?|weeks?))"
)
# Local employer / local contract markers (company register ids, statutory leave).
_LOCAL_ENTITY = re.compile(
    r"(?i)\b(?:UIC|EIK|ЕИК|BULSTAT|KRS|NIP|REGON|CUI|CIF|NIF|IČO|ICO|KvK|"
    r"company\s+(?:registration\s+)?(?:no\.?|number))\b[\s.:№#]*\d{6,}"
)
_LOCAL_LEAVE = re.compile(r"(?i)\b\d{2}\s+days\s+paid\s+(?:holiday|leave|vacation)\b")
_VISA = re.compile(
    r"(?i)visa\s+sponsor\w*|sponsor\w*\s+(?:a\s+|your\s+|the\s+|work\s+|employment\s+)?visas?|"
    r"visa\s+(?:support|assistance|help|provided|available|sponsorship)|"
    r"work\s+(?:permit|visa)\s+(?:support|sponsorship|assistance)|\bEU\s+Blue\s+Card\b"
)
_RELOC_TARGET = re.compile(
    r"(?i)relocat\w*\s+(?:to|in)\s+(?:our\s+(?:office|hub)\s+in\s+)?(?:the\s+)?"
    r"([A-Z][\w\-]+(?:[ ,]+[A-Z][\w\-]+){0,2})"
)
_WORKABLE_SLUG = re.compile(r"jobs\.workable\.com/view/[^/]+/([^/?#]+)")


def az_name(place: str) -> str:
    key = (place or "").strip().lower()
    return _COUNTRY_AZ.get(key, (place or "").strip().title() if key else "")


def place_from_source_url(url: str) -> str:
    """Location pin hidden in a Workable job URL slug: …-in-sofia-at-emerchantpay."""
    m = _WORKABLE_SLUG.search(url or "")
    if not m:
        return ""
    slug = unquote(m.group(1)).lower()
    head, sep, _company = slug.rpartition("-at-")
    if not sep:
        return ""
    _title, sep, place = head.rpartition("-in-")
    if not sep:
        return ""
    return place.replace("-", " ").strip()


def _quote(text: str, match: re.Match | None, width: int = 90) -> str:
    if not match:
        return ""
    start = max(0, match.start() - 10)
    snippet = " ".join(text[start: match.end() + 30].split())
    return f"“{snippet[:width]}”"


_GENERIC_UNKNOWN = (
    "Remote yalnız mənbə metadata-sındadır, mətndə yazılmayıb",
    "Mətndə remote və ya relocation açıq yazılmayıb",
    "Remote var, amma hansı ölkədən işləmək olar — göstərilməyib",
)


def _unit_quote(unit: str, width: int = 90) -> str:
    return f"“{' '.join(str(unit or '').split())[:width]}”"


def _first(rx: re.Pattern[str], text: str) -> re.Match | None:
    return rx.search(text or "")


def assess(
    title: str,
    place: str,
    text: str,
    *,
    countries: list[str] | None = None,
    source_remote: bool | None = None,
    source_url: str = "",
    source: str = "",
) -> dict[str, Any]:
    """Deterministic eligibility for an Azerbaijan-based candidate (see module doc)."""
    title = title or ""
    place = place or ""
    body = _plain(text or "")[:15000]
    sample = f"{title}\n{place}\n{body}"
    reasons: list[str] = []
    evidence: list[str] = []

    pins = [c for c in (countries or []) if str(c or "").strip()]
    slug_place = place_from_source_url(source_url)
    if slug_place and not pins:
        pins = [slug_place]
    pins_az = [c for c in pins if _AZ_EXPLICIT.search(str(c))]
    az = az_mentions(title, place, body, extra_positive=[str(c) for c in pins_az])
    az_pos, az_neg, az_company = az["positive"], az["negative"], az["company"]
    az_conflict = bool(az_pos and az_neg)
    az_excluded_only = False

    # ---- relocation / visa -------------------------------------------------
    reloc = relocation_flag(title, place, body)
    visa = bool(_positive(_VISA, sample))
    target = ""
    m = _RELOC_TARGET.search(body)
    if m:
        target = m.group(1).strip(" ,")
    elif reloc and _named_foreign_place(place) and "remote" not in place.lower():
        target = place.strip()[:80]
    if reloc and not target and pins and not pins_az:
        target = ", ".join(az_name(c) for c in pins[:4])

    # ---- remote scope -----------------------------------------------------
    abroad_days = _first(_ABROAD_DAYS, body)
    flex = _first(_FLEX_LOCATION, f"{title}\n{place}\n{body}")
    anywhere_in = None
    for cand in _ANYWHERE_IN.finditer(body):
        if not _AZ_EXPLICIT.search(cand.group(1)):
            anywhere_in = cand
            break
    open_strong = _first(_OPEN_STRONG, sample)
    region_lock = region_restriction_reason(title, place, body, source)
    local_entity = _first(_LOCAL_ENTITY, body)
    local_leave = _first(_LOCAL_LEAVE, body)
    # Explicit remote wording in the ad itself (not the source flag / city field).
    text_remote = remote_flag(title, "", body) and not abroad_days

    if az_conflict:
        scope, works = "az_listed", "unclear"
        reasons.append("Azərbaycan həm iş yeri kimi, həm də inkar/istisna kontekstində çəkilir — moderator yoxlasın")
        evidence.extend([_unit_quote(az_pos[0]), _unit_quote(az_neg[0])])
    elif az_pos:
        named = any(AZ_NAME.search(u) for u in az_pos)
        scope, works = ("az_listed" if named else "region_incl_az"), "yes"
        reasons.append(
            ("Azərbaycan/Bakı iş yeri kimi göstərilib" if named else "Azərbaycanı əhatə edən region göstərilib")
            + " — mümkün uyğunluq, AI sitatı və moderator təsdiqləyir"
        )
        evidence.append(_unit_quote(az_pos[0]))
    elif anywhere_in:
        scope, works = "country_locked", "no"
        where = re.split(r"(?<=\.)\s", anywhere_in.group(1))[0]
        reasons.append(f"Yalnız {az_name(where)} daxilində remote")
        evidence.append(_quote(body, anywhere_in))
    elif region_lock:
        scope, works = "country_locked", "no"
        reasons.append(
            "Müəyyən ölkə/region üzrə iş icazəsi tələb olunur"
            if region_lock == "work_authorization"
            else "Remote yalnız müəyyən region üçün"
        )
    elif pins and not open_strong:
        scope, works = "country_locked", "no"
        names = ", ".join(az_name(c) for c in pins[:4])
        if len(pins) == 1:
            reasons.append(f"Yalnız {names} daxilində remote (mənbədə yeganə yer)")
        else:
            reasons.append(f"Remote yalnız bu ölkələr üçün: {names}")
    elif open_strong and not _named_foreign_place(place):
        scope, works = "anywhere", "yes"
        evidence.append(_quote(sample, open_strong))
    elif abroad_days or (flex and not text_remote):
        scope, works = "home_country_hybrid", "no"
        if abroad_days:
            reasons.append("“İldə X gün xaricdən iş” daimi remote deyil")
            evidence.append(_quote(body, abroad_days))
        if flex:
            reasons.append("“Flexible work location” evdən/ofisdən iş deməkdir, istənilən ölkə deyil")
            evidence.append(_quote(f"{title}\n{place}\n{body}", flex))
    elif _named_foreign_place(place) and not text_remote:
        scope, works = "onsite", "no"
        reasons.append(f"Xaricdə ofis: {place.strip()[:60]}")
    else:
        scope, works = "unknown", "unclear"
        if source_remote and not text_remote:
            reasons.append("Remote yalnız mənbə metadata-sındadır, mətndə yazılmayıb")
        elif not text_remote:
            reasons.append("Mətndə remote və ya relocation açıq yazılmayıb")
        else:
            reasons.append("Remote var, amma hansı ölkədən işləmək olar — göstərilməyib")

    if az_neg and not az_pos:
        # restriction evidence; cap low but never a hard reject on the negation alone
        if works != "no":
            az_excluded_only = True
            # the generic "location not stated" line no longer describes this ad
            reasons[:] = [r for r in reasons if r not in _GENERIC_UNKNOWN]
        scope, works = "country_locked", "no"
        reasons.append("Azərbaycan inkar/istisna kontekstində çəkilir (məhdudiyyət sübutu)")
        evidence.append(_unit_quote(az_neg[0]))
    if az_company and not az_pos and not az_neg:
        reasons.append(
            "Azərbaycan/Bakı yalnız şirkət/müştəri/komanda haqqında cümlədə çəkilir — uyğunluq sübutu deyil: "
            + _unit_quote(az_company[0], 70)
        )

    if (local_entity or local_leave) and works != "yes" and not text_remote:
        bits = []
        if local_entity:
            bits.append(_quote(body, local_entity, 50))
        if local_leave:
            bits.append(_quote(body, local_leave, 50))
        reasons.append("Yerli şirkət/müqavilə əlamətləri: " + ", ".join(bits))
        if works == "yes":
            works = "unclear"

    # ---- cap ---------------------------------------------------------------
    if az_conflict:
        cap = CAP_AZ_CONFLICT
    elif works == "yes":
        cap = 100
    elif reloc:
        if visa and target:
            cap = CAP_RELOC_CONFIRMED
        else:
            cap = CAP_RELOC_UNCONFIRMED
        missing = []
        if not target:
            missing.append("hədəf ölkə")
        if not visa:
            missing.append("viza dəstəyi")
        reasons.append(
            "Relocation var"
            + (f" ({target})" if target else "")
            + (f"; göstərilməyib: {', '.join(missing)} — yeri yoxlayın" if missing else "")
        )
    elif works == "no":
        cap = CAP_AZ_EXCLUDED if az_excluded_only else CAP_LOCKED
    else:
        cap = CAP_UNCLEAR

    return {
        "remote_scope": scope,
        "works_from_az": works,
        "relocation": "yes" if reloc else "no",
        "relocation_target": target,
        "visa": "yes" if visa else "no",
        "cap": cap,
        "reasons": reasons,
        "evidence": [e for e in evidence if e],
    }


_SCOPE_AZ = {
    "anywhere": "istənilən ölkə",
    "az_listed": "Azərbaycan iş yeri kimi göstərilib",
    "region_incl_az": "Azərbaycanı əhatə edən region",
    "country_locked": "ölkəyə bağlı",
    "home_country_hybrid": "ofis ölkəsində hibrid/evdən",
    "onsite": "ofisdə",
    "unknown": "bəlli deyil",
    # market_fit AI enum
    "AZERBAIJAN_EXPLICIT": "Azərbaycan açıq yazılıb",
    "WORLDWIDE": "istənilən ölkə",
    "REGION_INCLUDES_AZERBAIJAN": "Azərbaycanı əhatə edən region",
    "COUNTRY_RESTRICTED": "ölkəyə/regiona bağlı",
    "TEMPORARY_ABROAD_ONLY": "yalnız müvəqqəti xaricdən iş",
    "UNKNOWN": "bəlli deyil",
}
_TRI_AZ = {"yes": "bəli", "no": "xeyr", "unclear": "bəlli deyil"}


def summary(elig: dict[str, Any]) -> str:
    """One Azerbaijani line for the staff queue (structured fields + reasons + quotes)."""
    reloc = "var" if elig.get("relocation") == "yes" else "yox"
    target = str(elig.get("relocation_target") or "")
    if elig.get("relocation") == "yes":
        reloc += f" ({target})" if target else " (ölkə göstərilməyib)"
    parts = [
        f"Remote əhatəsi: {_SCOPE_AZ.get(str(elig.get('remote_scope')), 'bəlli deyil')}",
        f"Azərbaycandan iş: {_TRI_AZ.get(str(elig.get('works_from_az')), 'bəlli deyil')}",
        f"Relocation: {reloc}",
        f"Viza: {'var' if elig.get('visa') == 'yes' else 'yox'}",
    ]
    line = "; ".join(parts)
    reasons = [r for r in elig.get("reasons") or [] if r]
    if reasons:
        line += " — " + "; ".join(reasons)
    quotes = [q for q in elig.get("evidence") or [] if q]
    if quotes:
        line += " · Sübut: " + " ".join(quotes[:3])
    return line[:REASON_MAX]


def cap_score(score: int | None, elig: dict[str, Any], *, rule: bool) -> int | None:
    if score is None:
        return None
    capped = min(int(score), int(elig.get("cap", 100)))
    if rule:
        capped = min(capped, RULE_MAX)
    return max(0, capped)


def is_hard_reject(elig: dict[str, Any]) -> bool:
    return int(elig.get("cap", 100)) <= CAP_LOCKED

"""Staff-queue AI % computed deterministically from the market-fit AI's yes/no checks.

The AI never returns a percentage. It returns booleans (each positive one backed by an
exact quote from the ad), and :func:`staff_percent` turns them into the % shown in the
moderation queue. Edit the constants below to tune the mapping; tests in
``worker/tests/test_fit_mapping.py`` enumerate every flag combination.

Order of evaluation (first match wins; a restriction beats a weaker positive):

==================================================================  =====
Evidence (positive flags need a verified quote)                       %
==================================================================  =====
remote_az_explicit                                                   95
  ... same, but a remote restriction / work-auth rule is also quoted    84
remote_worldwide, remote not blocked                                 90
remote_region_includes_az, remote not blocked                        88
  ... same, but work_authorization_required (named country)          84
relocation + strong visa, candidates not location-restricted         88
relocation + conditional visa                                        70
relocation only, strong visa only, or conditional visa only          70
any restriction, no valid route                                      15
no evidence either way                                               40
==================================================================  =====

* remote is blocked by ``remote_country_restricted``, ``candidate_location_restricted``
  or ``temporary_abroad_only``. When a remote flag and a restriction are both true
  (conflicting quotes) the restriction wins; the AI does not resolve conflicts.
* ``remote_az_explicit`` covers remote from Azerbaijan, Azerbaijan / Baku in the list of
  places the role is open to (title or location field), and hybrid / on-site work in
  Baku or elsewhere in Azerbaijan: a candidate who lives in Azerbaijan can do all of
  them, so on-site Baku is the same 95 route. Company / client / team statements about
  Azerbaijan and negated mentions never set it (quote validation). When the ad also
  quotes a restriction that leaves Azerbaijan out (e.g. the location field lists
  Azerbaijan but the text's country list does not) the conflict is shown and the %
  is capped at AZ_CONFLICT_CAP (84) for a moderator. market-fit-v10: the AI reads
  allowed / excluded country lists by meaning (an exclusion list naming only other
  countries is no restriction); the code does not re-interpret lists and never drops a
  quoted restriction itself, so an AI that still flags one keeps the 84 + conflict.
* ``candidate_location_restricted`` (must already live in / be a citizen of named
  countries) also blocks the relocation and visa routes.
* Visa strength: ``visa_support`` alone never means the candidate certainly qualifies.
  It is *strong* only when ``visa_support_conditional`` is false (no "not every role /
  candidate", "case by case", "where possible", "may sponsor", and not just a general
  company-wide statement). A conditional visa is a weak route (70 at most) and never
  helps reach 85+; the conditional quote is shown to the moderator.
* ``visa_support`` together with ``no_sponsorship_stated`` or
  ``work_authorization_required`` is a *conflict*: both flags and their quotes are
  kept and shown to the moderator (:func:`conflicts`), and the visa route is not
  counted. Neither touches a valid remote-from-AZ route.
* ``text_truncated`` (decided by code from reliable metadata: the prompt cut or a
  source snippet) or ``work_location_unspecified`` caps the result at INFO_CAP (84):
  the missing part may hold a restriction. When only the AI hints at truncation (code
  says complete), ``text_truncated_ai_hint`` is a soft flag: shown to the moderator and,
  conservatively, also capped at 84 (AI_TRUNCATION_HINT_CAP).

85+ is therefore reachable only with quoted remote-from-AZ evidence or relocation + an
unconditional, role-level visa, on a complete ad with a stated work location.
"""

from __future__ import annotations

from typing import Any

SCORE_AZ_EXPLICIT = 95
SCORE_WORLDWIDE = 90
SCORE_REGION_INCL_AZ = 88
SCORE_RELOC_AND_VISA = 88
SCORE_SINGLE_ROUTE = 70  # relocation only / visa only: staff checks target country
SCORE_WEAK_VISA = 70  # conditional / company-wide visa statement: never above this
SCORE_RESTRICTED = 15
SCORE_NO_EVIDENCE = 40
INFO_CAP = 84  # below the 85 approve band
TRUNCATED_CAP = INFO_CAP  # back-compat name
AI_TRUNCATION_HINT_CAP = 84  # AI suspects a cut the code cannot confirm: conservative
AZ_CONFLICT_CAP = 84  # Azerbaijan explicitly allowed, but a restriction is quoted too
AUTH_CONFLICT_CAP = 84  # remote route + "must have the right to work in <country>"

# Order = prompt definition order = JSON example order = schema "required" order.
POSITIVE_FLAGS = (
    "remote_worldwide",
    "remote_region_includes_az",
    "remote_az_explicit",
    "relocation",
    "visa_support",
)
QUALIFIER_FLAGS = ("visa_support_conditional",)
RESTRICTIVE_FLAGS = (
    "remote_country_restricted",
    "candidate_location_restricted",
    "work_authorization_required",
    "temporary_abroad_only",
    "no_sponsorship_stated",
)
INFO_FLAGS = ("text_truncated", "work_location_unspecified")
FLAGS = POSITIVE_FLAGS + QUALIFIER_FLAGS + RESTRICTIVE_FLAGS + INFO_FLAGS

# Flags the AI answers: all of them. For text_truncated the AI answer is only a hint;
# the code value (prompt cut / source snippet) is authoritative.
AI_FLAGS = FLAGS
CODE_DECIDED_FLAGS = ("text_truncated",)
TRUNCATION_HINT = "text_truncated_ai_hint"  # soft flag key (not an AI flag)

# market-fit-v6 names -> v7 names (stored AI answers, cached results, old tests).
LEGACY_FLAGS = {
    "country_restricted": ("remote_country_restricted", "candidate_location_restricted"),
    "text_truncated_or_missing_location": ("work_location_unspecified",),
}


def upgrade_legacy(flags: dict[str, Any]) -> dict[str, Any]:
    """Map v6 flag names onto v7 ones (conservatively: old restriction -> both)."""
    out = dict(flags or {})
    for old, new_names in LEGACY_FLAGS.items():
        if old in out:
            value = out.pop(old)
            for new in new_names:
                out.setdefault(new, value)
    return out


def remote_blocked(f: dict[str, bool]) -> bool:
    return f["remote_country_restricted"] or f["candidate_location_restricted"] or f["temporary_abroad_only"]


# Conflict keys -> Azerbaijani note for the moderator (reason + popover).
CONFLICTS_AZ = {
    "remote_vs_restriction": "remote sübutu ilə məhdudiyyət sübutu ziddiyyətlidir; məhdudiyyət üstün tutuldu",
    "visa_vs_no_sponsorship": "visa_support və no_sponsorship_stated ikisi də doğrudur; viza yolu sayılmadı",
    "visa_vs_work_authorization": "visa_support və work_authorization_required ziddiyyətlidir; viza yolu sayılmadı",
    "move_vs_candidate_location": "relocation/viza ilə namizədin yaşayış tələbi ziddiyyətlidir; tələb üstün tutuldu",
}


def conflicts(flags: dict[str, Any]) -> list[str]:
    """Positive and negative evidence on the same route; every one is shown, none silently resolved."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    remote_pos = f["remote_worldwide"] or f["remote_region_includes_az"] or f["remote_az_explicit"]
    out: list[str] = []
    if remote_pos and (remote_blocked(f) or f["work_authorization_required"]):
        out.append("remote_vs_restriction")
    if f["visa_support"] and f["no_sponsorship_stated"]:
        out.append("visa_vs_no_sponsorship")
    if f["visa_support"] and f["work_authorization_required"]:
        out.append("visa_vs_work_authorization")
    if (f["relocation"] or f["visa_support"]) and f["candidate_location_restricted"]:
        out.append("move_vs_candidate_location")
    return out


def has_conflict(flags: dict[str, Any]) -> bool:
    return bool(conflicts(flags))


def visa_strength(flags: dict[str, Any]) -> str:
    """'strong' | 'weak' | '' (no usable visa route). Conflicts and residence rules count first."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    if not f["visa_support"] or f["no_sponsorship_stated"] or f["work_authorization_required"]:
        return ""
    if f["candidate_location_restricted"]:
        return ""
    return "weak" if f["visa_support_conditional"] else "strong"


def staff_percent(flags: dict[str, Any]) -> tuple[int, str]:
    """Pure mapping: verified flags -> (staff %, route key). See module docstring."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    blocked = remote_blocked(f)
    restricted = blocked or f["work_authorization_required"]
    visa = visa_strength(f)  # conflicts: visa not counted (surfaced by conflicts())
    reloc = f["relocation"] and not f["candidate_location_restricted"]

    if f["remote_az_explicit"]:
        score, route = SCORE_AZ_EXPLICIT, "remote_az_explicit"
    elif f["remote_worldwide"] and not blocked:
        score, route = SCORE_WORLDWIDE, "remote_worldwide"
    elif f["remote_region_includes_az"] and not blocked:
        score, route = SCORE_REGION_INCL_AZ, "remote_region_includes_az"
    elif reloc and visa == "strong":
        score, route = SCORE_RELOC_AND_VISA, "relocation+visa_support"
    elif reloc and visa == "weak":
        score, route = SCORE_WEAK_VISA, "relocation+visa_conditional"
    elif reloc:
        score, route = SCORE_SINGLE_ROUTE, "relocation"
    elif visa == "strong":
        score, route = SCORE_SINGLE_ROUTE, "visa_support"
    elif visa == "weak":
        score, route = SCORE_WEAK_VISA, "visa_conditional"
    elif restricted:
        score, route = SCORE_RESTRICTED, "restricted"
    else:
        score, route = SCORE_NO_EVIDENCE, "no_evidence"
    if route == "remote_az_explicit" and (blocked or f["work_authorization_required"]):
        score = min(score, AZ_CONFLICT_CAP)
    if route in ("remote_worldwide", "remote_region_includes_az") and f["work_authorization_required"]:
        score = min(score, AUTH_CONFLICT_CAP)
    if f["text_truncated"] or f["work_location_unspecified"]:
        score = min(score, INFO_CAP)
    if flags.get(TRUNCATION_HINT) and not f["text_truncated"]:
        score = min(score, AI_TRUNCATION_HINT_CAP)
    return score, route


REMOTE_ROUTES = ("remote_az_explicit", "remote_worldwide", "remote_region_includes_az")

# Why the visa evidence did / did not count (shown in the popover and the reason).
VISA_NOTES_AZ = {
    "weak": "viza şərtlidir: zəif yol, maks. 70%, 85+ vermir",
    "remote_route": "viza şərti nəzərə alınmır: remote yol (Azərbaycandan iş) vizadan asılı deyil",
    "no_sponsorship": "viza sayılmır: elan həm də sponsorluq olmadığını yazır (ziddiyyət)",
    "work_authorization": "viza sayılmır: konkret ölkədə hazır iş icazəsi tələb olunur (ziddiyyət)",
    "candidate_location": "viza sayılmır: namizəd müəyyən ölkədə yaşamalıdır",
}


def visa_note(flags: dict[str, Any], route: str = "") -> str:
    """'' or a VISA_NOTES_AZ key explaining how the visa evidence was used."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    if not f["visa_support"]:
        return ""
    if f["no_sponsorship_stated"]:
        return "no_sponsorship"
    if f["work_authorization_required"]:
        return "work_authorization"
    if f["candidate_location_restricted"]:
        return "candidate_location"
    if route in REMOTE_ROUTES:
        return "remote_route" if f["visa_support_conditional"] else ""
    return "weak" if f["visa_support_conditional"] else ""


def is_suitable(route: str) -> bool:
    """A valid route exists (staff may still check 70% relocation/visa-only ads)."""
    return route not in ("restricted", "no_evidence")

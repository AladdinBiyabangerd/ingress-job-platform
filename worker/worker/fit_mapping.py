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
remote_worldwide, remote not blocked                                 90
remote_region_includes_az, remote not blocked                        88
  ... same, but work_authorization_required (named country)          84
relocation + visa_support, candidates not location-restricted        88
relocation only, or visa_support only  (manual check)                70
any restriction, no valid route                                      15
no evidence either way                                               40
==================================================================  =====

* remote is blocked by ``remote_country_restricted``, ``candidate_location_restricted``
  or ``temporary_abroad_only``. When a remote flag and a restriction are both true
  (conflicting quotes) the restriction wins; the AI does not resolve conflicts.
* ``candidate_location_restricted`` (must already live in / be a citizen of named
  countries) also blocks the relocation and visa routes.
* ``visa_support`` is cancelled by ``no_sponsorship_stated`` or
  ``work_authorization_required``. Neither touches a valid remote-from-AZ route.
* ``text_truncated`` (set by code, not the AI) or ``work_location_unspecified`` caps
  the result at INFO_CAP (84): the missing part may hold a restriction.

85+ is therefore reachable only with quoted remote-from-AZ evidence or relocation+visa,
on a complete ad with a stated work location.
"""

from __future__ import annotations

from typing import Any

SCORE_AZ_EXPLICIT = 95
SCORE_WORLDWIDE = 90
SCORE_REGION_INCL_AZ = 88
SCORE_RELOC_AND_VISA = 88
SCORE_SINGLE_ROUTE = 70  # relocation only / visa only: staff checks target country
SCORE_RESTRICTED = 15
SCORE_NO_EVIDENCE = 40
INFO_CAP = 84  # below the 85 approve band
TRUNCATED_CAP = INFO_CAP  # back-compat name
AUTH_CONFLICT_CAP = 84  # remote route + "must have the right to work in <country>"

POSITIVE_FLAGS = (
    "remote_az_explicit",
    "remote_worldwide",
    "remote_region_includes_az",
    "relocation",
    "visa_support",
)
RESTRICTIVE_FLAGS = (
    "remote_country_restricted",
    "candidate_location_restricted",
    "work_authorization_required",
    "temporary_abroad_only",
    "no_sponsorship_stated",
)
INFO_FLAGS = ("text_truncated", "work_location_unspecified")
FLAGS = POSITIVE_FLAGS + RESTRICTIVE_FLAGS + INFO_FLAGS

# Flags the AI answers (text_truncated is decided by code from prompt_ad_text).
AI_FLAGS = tuple(name for name in FLAGS if name != "text_truncated")

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


def has_conflict(flags: dict[str, Any]) -> bool:
    """Positive and negative evidence on the same route (moderator should look)."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    remote_pos = f["remote_worldwide"] or f["remote_region_includes_az"] or f["remote_az_explicit"]
    any_restriction = remote_blocked(f) or f["work_authorization_required"]
    visa_conflict = f["visa_support"] and (f["no_sponsorship_stated"] or f["work_authorization_required"])
    reloc_conflict = (f["relocation"] or f["visa_support"]) and f["candidate_location_restricted"]
    return (remote_pos and any_restriction) or visa_conflict or reloc_conflict


def staff_percent(flags: dict[str, Any]) -> tuple[int, str]:
    """Pure mapping: verified flags -> (staff %, route key). See module docstring."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    blocked = remote_blocked(f)
    restricted = blocked or f["work_authorization_required"]
    visa = f["visa_support"] and not (f["no_sponsorship_stated"] or f["work_authorization_required"])
    movable = not f["candidate_location_restricted"]
    reloc = f["relocation"] and movable
    visa = visa and movable

    if f["remote_az_explicit"]:
        score, route = SCORE_AZ_EXPLICIT, "remote_az_explicit"
    elif f["remote_worldwide"] and not blocked:
        score, route = SCORE_WORLDWIDE, "remote_worldwide"
    elif f["remote_region_includes_az"] and not blocked:
        score, route = SCORE_REGION_INCL_AZ, "remote_region_includes_az"
    elif reloc and visa:
        score, route = SCORE_RELOC_AND_VISA, "relocation+visa_support"
    elif reloc:
        score, route = SCORE_SINGLE_ROUTE, "relocation"
    elif visa:
        score, route = SCORE_SINGLE_ROUTE, "visa_support"
    elif restricted:
        score, route = SCORE_RESTRICTED, "restricted"
    else:
        score, route = SCORE_NO_EVIDENCE, "no_evidence"
    if route in ("remote_worldwide", "remote_region_includes_az") and f["work_authorization_required"]:
        score = min(score, AUTH_CONFLICT_CAP)
    if f["text_truncated"] or f["work_location_unspecified"]:
        score = min(score, INFO_CAP)
    return score, route


def is_suitable(route: str) -> bool:
    """A valid route exists (staff may still check 70% relocation/visa-only ads)."""
    return route not in ("restricted", "no_evidence")

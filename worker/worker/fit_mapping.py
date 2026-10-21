"""Staff-queue AI % computed deterministically from the market-fit AI's yes/no checks.

The AI never returns a percentage. It returns booleans (each positive one backed by an
exact quote from the ad), and :func:`staff_percent` turns them into the % shown in the
moderation queue. Edit the constants below to tune the mapping; tests in
``worker/tests/test_fit_mapping.py`` enumerate every flag combination.

Order of evaluation (first match wins; a restriction beats a weaker positive):

==============================================================  =====
Evidence (positive flags need a verified quote)                   %
==============================================================  =====
remote_az_explicit                                               95
remote_worldwide, not restricted                                 90
remote_region_includes_az, not restricted                        88
relocation + visa_support (and no "no sponsorship")              88
relocation only, or visa_support only  (manual check)            70
country_restricted or temporary_abroad_only, no valid route      15
no evidence either way                                           40
==============================================================  =====

``restricted`` = country_restricted or temporary_abroad_only. A visa_support flag
contradicted by no_sponsorship_stated is dropped. When text_truncated_or_missing_location
is true the result is capped at TRUNCATED_CAP (the missing part may hold a restriction).
85+ is therefore reachable only with quoted remote-from-AZ evidence or relocation+visa.
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
TRUNCATED_CAP = 84  # below the 85 approve band

POSITIVE_FLAGS = (
    "remote_az_explicit",
    "remote_worldwide",
    "remote_region_includes_az",
    "relocation",
    "visa_support",
)
RESTRICTIVE_FLAGS = ("country_restricted", "temporary_abroad_only", "no_sponsorship_stated")
INFO_FLAGS = ("text_truncated_or_missing_location",)
FLAGS = POSITIVE_FLAGS + RESTRICTIVE_FLAGS + INFO_FLAGS


def staff_percent(flags: dict[str, Any]) -> tuple[int, str]:
    """Pure mapping: verified flags -> (staff %, route key). See module docstring."""
    f = {name: bool(flags.get(name)) for name in FLAGS}
    restricted = f["country_restricted"] or f["temporary_abroad_only"]
    visa = f["visa_support"] and not f["no_sponsorship_stated"]
    reloc = f["relocation"]

    if f["remote_az_explicit"]:
        score, route = SCORE_AZ_EXPLICIT, "remote_az_explicit"
    elif f["remote_worldwide"] and not restricted:
        score, route = SCORE_WORLDWIDE, "remote_worldwide"
    elif f["remote_region_includes_az"] and not restricted:
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
    if f["text_truncated_or_missing_location"]:
        score = min(score, TRUNCATED_CAP)
    return score, route


def is_suitable(route: str) -> bool:
    """A valid route exists (staff may still check 70% relocation/visa-only ads)."""
    return route not in ("restricted", "no_evidence")

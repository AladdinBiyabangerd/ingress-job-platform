"""Hunt-style match score + confidence (For-you / matches).

Unknown dimensions contribute 0 to score and do not inflate confidence.
Silence (missing salary/visa/years) is never treated as a positive match.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCORING_VERSION = "hunt-ingress-v2"

# For-you list gates (plan).
MIN_SCORE = 0.33
MIN_CONFIDENCE = 0.35

# Dimension weights (sum = 100).
DIM_WEIGHTS: dict[str, float] = {
    "tech_skill_fit": 20.0,
    "role_seniority_fit": 15.0,
    "preference_fit": 10.0,
    "salary_fit": 10.0,
    "work_authorization_fit": 10.0,
    "freshness": 7.5,
    "data_completeness": 7.5,
    "experience_fit": 20.0,
}

TOTAL_WEIGHT = sum(DIM_WEIGHTS.values())

SENIORITY_RANK = {
    "intern": 0,
    "junior": 1,
    "middle": 2,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
    "staff": 5,
}

_TITLE_YEARS = re.compile(
    r"(?i)(?:at\s+least\s+|minimum\s+|min\.?\s*)?(\d{1,2})\+?\s*(?:\+|plus)?\s*"
    r"(?:years?|yrs?|illə|il\b|лет|года|год)"
)


def _ensure_worker_path() -> None:
    try:
        import worker.salary_parse  # noqa: F401
        return
    except ImportError:
        pass
    repo_worker = Path(__file__).resolve().parents[2] / "worker"
    if repo_worker.is_dir() and str(repo_worker) not in sys.path:
        sys.path.insert(0, str(repo_worker))


def compute_score(raw: dict[str, float | None]) -> dict[str, Any]:
    """Hunt arithmetic: unknown → 0 on score, omitted from confidence numerator."""
    known_weight = 0.0
    weighted = 0.0
    dimensions: list[dict[str, Any]] = []
    for name, weight in DIM_WEIGHTS.items():
        value = raw.get(name)
        if value is None:
            dimensions.append(
                {
                    "name": name,
                    "weight": weight,
                    "value": None,
                    "status": "unknown",
                }
            )
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            dimensions.append(
                {
                    "name": name,
                    "weight": weight,
                    "value": None,
                    "status": "unknown",
                }
            )
            continue
        v = max(0.0, min(1.0, v))
        known_weight += weight
        weighted += weight * v
        dimensions.append(
            {
                "name": name,
                "weight": weight,
                "value": round(v, 4),
                "status": "known",
            }
        )

    score = round(weighted / TOTAL_WEIGHT, 4) if TOTAL_WEIGHT else 0.0
    confidence = round(known_weight / TOTAL_WEIGHT, 4) if TOTAL_WEIGHT else 0.0
    return {
        "score": score,
        "confidence": confidence,
        "score_pct": int(round(score * 100)),
        "confidence_pct": int(round(confidence * 100)),
        "dimensions": dimensions,
        "scoring_version": SCORING_VERSION,
        "known_weight": known_weight,
    }


def tech_skill_fit(skill_overlap: float | None, *, job_has_skills: bool) -> float | None:
    if not job_has_skills:
        return None
    if skill_overlap is None:
        return None
    return max(0.0, min(1.0, float(skill_overlap)))


def role_seniority_fit(candidate: str | None, job_level: str | None) -> float | None:
    if not candidate or not job_level:
        return None
    c = SENIORITY_RANK.get(str(candidate).strip().lower())
    j = SENIORITY_RANK.get(str(job_level).strip().lower())
    if c is None or j is None:
        return None
    diff = abs(c - j)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.6
    if diff == 2:
        return 0.3
    return 0.1


def preference_fit(prefs: dict | None, *, remote: bool, relocation: bool) -> float | None:
    """Explicit prefs only. Empty prefs → unknown (not a fake 0.5)."""
    if not isinstance(prefs, dict):
        return None
    parts: list[float] = []
    want_remote = prefs.get("remote")
    if want_remote is True:
        parts.append(1.0 if remote else 0.25)
    elif want_remote is False:
        parts.append(1.0 if not remote else 0.4)

    want_reloc = prefs.get("relocation")
    if want_reloc is True:
        parts.append(1.0 if relocation else 0.3)
    elif want_reloc is False:
        parts.append(1.0 if not relocation else 0.5)

    if not parts:
        return None
    return round(sum(parts) / len(parts), 4)


def work_authorization_fit(prefs: dict | None, *, relocation: bool) -> float | None:
    """Visa/reloc only when the candidate explicitly needs sponsorship."""
    if not isinstance(prefs, dict):
        return None
    needs = prefs.get("needs_visa_sponsorship")
    if needs is True:
        return 1.0 if relocation else 0.15
    # False or unset: not a confirmed work-auth signal → unknown.
    return None


def freshness_fit(created_at: str | None) -> float | None:
    raw = (created_at or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            created = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        else:
            created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    age_days = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 86400.0
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.7
    if age_days <= 90:
        return 0.4
    return 0.2


def data_completeness_fit(job: dict[str, Any], job_skills: list) -> float:
    """Objective job-field fullness — always known."""
    checks = [
        bool(str(job.get("title") or "").strip()),
        bool(str(job.get("company") or "").strip()),
        bool(str(job.get("city") or "").strip()),
        bool(str(job.get("language") or "").strip()),
        bool(str(job.get("category") or "").strip()),
        bool(str(job.get("salary") or "").strip()),
        bool(str(job.get("created_at") or "").strip()),
        bool(job_skills),
    ]
    if not checks:
        return 0.0
    return round(sum(1 for x in checks if x) / len(checks), 4)


def _annualize_expectation(expectation: dict) -> tuple[float, str] | None:
    raw_min = expectation.get("min")
    try:
        amount = float(raw_min) if raw_min is not None else None
    except (TypeError, ValueError):
        amount = None
    if amount is None or amount <= 0:
        return None
    currency = str(expectation.get("currency") or "").strip().upper()
    if not currency:
        return None
    period = str(expectation.get("period") or "year").strip().lower()
    if period in {"month", "monthly", "ay", "aylıq"}:
        annual = amount * 12.0
    elif period in {"week", "weekly"}:
        annual = amount * 52.0
    elif period in {"day", "daily"}:
        annual = amount * 260.0
    else:
        annual = amount
    return annual, currency


def salary_fit(expectation: dict | None, job_salary: str | None) -> float | None:
    """Both sides must parse in the same currency; else unknown (no FX guess)."""
    if not isinstance(expectation, dict):
        return None
    cand = _annualize_expectation(expectation)
    if cand is None:
        return None
    cand_annual, cand_currency = cand
    _ensure_worker_path()
    try:
        from worker.salary_parse import parse_salary_annual
    except ImportError:
        return None
    parsed = parse_salary_annual(job_salary or "")
    if not parsed:
        return None
    job_currency = str(parsed.get("currency") or "").strip().upper()
    job_annual = parsed.get("annual")
    if not job_currency or job_currency != cand_currency:
        return None
    try:
        job_val = float(job_annual)
    except (TypeError, ValueError):
        return None
    if job_val <= 0:
        return None
    ratio = job_val / cand_annual
    if ratio >= 0.95:
        return 1.0
    if ratio >= 0.8:
        return 0.7
    if ratio >= 0.65:
        return 0.4
    return 0.15


def _job_years_required(job: dict[str, Any]) -> float | None:
    """Only explicit years in title (or optional years_required field). No weak proxies."""
    raw = job.get("years_required")
    if isinstance(raw, (int, float)) and float(raw) > 0:
        return float(raw)
    title = str(job.get("title") or "")
    match = _TITLE_YEARS.search(title)
    if not match:
        return None
    try:
        years = float(match.group(1))
    except (TypeError, ValueError):
        return None
    if years <= 0 or years > 40:
        return None
    return years


def experience_fit(
    total_years: float | None,
    job: dict[str, Any],
    *,
    work_history: list | None = None,
) -> float | None:
    """Confirmed candidate years vs explicit job years only; else unknown."""
    try:
        cand = float(total_years) if total_years is not None else None
    except (TypeError, ValueError):
        cand = None
    if cand is None or cand < 0:
        # Confirmed work_history length is still a weak proxy — do not invent.
        if not work_history:
            return None
        return None
    required = _job_years_required(job)
    if required is None:
        return None
    if cand >= required:
        return 1.0
    if cand >= required * 0.75:
        return 0.6
    if cand >= required * 0.5:
        return 0.3
    return 0.1


def passes_list_gates(score: float, confidence: float) -> bool:
    return score >= MIN_SCORE and confidence >= MIN_CONFIDENCE

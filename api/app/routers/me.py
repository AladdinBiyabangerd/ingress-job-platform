"""Candidate /me routes: roles, matches, feedback, export/delete (plan §6 / §10.3 / §13.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.matching import (
    FEEDBACK_REASONS,
    FEEDBACK_VOTES,
    MAX_LIMIT as MATCH_MAX_LIMIT,
    list_matches,
    save_match_feedback,
)
from app.me_data import build_export_zip, delete_my_data
from app.role_suggestions import MAX_LIMIT as ROLE_MAX_LIMIT, suggest_roles
from app.skill_gap import MAX_TOP as SKILL_GAP_MAX_TOP, skill_gap

router = APIRouter(prefix="/api/v1/me", tags=["me"])


class MatchFeedbackBody(BaseModel):
    vote: str = Field(..., min_length=2, max_length=8)
    reason: str = Field(default="", max_length=40)


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Namizəd hesabı tələb edir")


@router.get("/roles")
def get_roles(
    limit: int | None = Query(default=None, ge=1, le=ROLE_MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    return suggest_roles(user_id=user.subject, limit=limit, lang=lang)


@router.get("/matches")
def get_matches(
    limit: int | None = Query(default=None, ge=1, le=MATCH_MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Structured job matches (plan §6.2). AI #2 re-rank off on SQLite."""
    _require_candidate(user)
    return list_matches(user_id=user.subject, limit=limit, lang=lang)


@router.post("/matches/{job_id}/feedback")
def post_match_feedback(
    job_id: int,
    body: MatchFeedbackBody,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """👍 / 👎 on a recommendation (plan §6.3)."""
    _require_candidate(user)
    vote = (body.vote or "").strip().lower()
    reason = (body.reason or "").strip().lower()
    if vote not in FEEDBACK_VOTES:
        raise HTTPException(status_code=400, detail="vote must be up or down")
    if vote == "down" and reason and reason not in FEEDBACK_REASONS:
        raise HTTPException(
            status_code=400,
            detail="reason must be location, seniority, technology, salary, or empty",
        )
    try:
        return save_match_feedback(
            user_id=user.subject,
            job_id=job_id,
            vote=vote,
            reason=reason,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Matching razılığı tələb olunur") from None
    except LookupError:
        raise HTTPException(status_code=404, detail="Elan tapılmadı") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/skill-gap")
def get_skill_gap(
    role: str | None = Query(default=None, max_length=120),
    top: int | None = Query(default=None, ge=1, le=SKILL_GAP_MAX_TOP),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Skill gap vs target role signature skills (plan §7.2)."""
    _require_candidate(user)
    return skill_gap(user_id=user.subject, role=role, top=top, lang=lang)


@router.get("/export")
def export_my_data(user: VerifiedAccess = Depends(current_user)) -> Response:
    """ZIP: export.json + original CV files.

    Plan path GET /api/me collides with account GET /api/v1/me → /export.
    """
    _require_candidate(user)
    payload = build_export_zip(user_id=user.subject)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="ingress-job-export.zip"',
        },
    )


@router.delete("")
@router.delete("/")
def delete_me(user: VerifiedAccess = Depends(current_user)) -> dict:
    """Hard-delete profile/skills/CV/email prefs; audit keeps a pseudonym."""
    _require_candidate(user)
    return delete_my_data(user_id=user.subject)

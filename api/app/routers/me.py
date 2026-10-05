"""Candidate /me routes: roles, data export, hard-delete (plan §6.1 / §10.3 / §13.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.me_data import build_export_zip, delete_my_data
from app.role_suggestions import MAX_LIMIT, suggest_roles

router = APIRouter(prefix="/api/v1/me", tags=["me"])


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Namizəd hesabı tələb edir")


@router.get("/roles")
def get_roles(
    limit: int | None = Query(default=None, ge=1, le=MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    return suggest_roles(user_id=user.subject, limit=limit, lang=lang)


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

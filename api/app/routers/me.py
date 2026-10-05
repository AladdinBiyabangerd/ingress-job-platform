"""GET /api/v1/me/roles — deterministic role suggestions (plan §6.1 / §13.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.role_suggestions import MAX_LIMIT, suggest_roles

router = APIRouter(prefix="/api/v1/me", tags=["me"])


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Rol təklifləri namizəd hesabı tələb edir")


@router.get("/roles")
def get_roles(
    limit: int | None = Query(default=None, ge=1, le=MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    return suggest_roles(user_id=user.subject, limit=limit, lang=lang)

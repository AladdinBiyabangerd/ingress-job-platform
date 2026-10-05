"""GET/PUT /api/v1/consents — candidate privacy consents (plan §13.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.consents import CONSENT_KINDS, VISIBILITY_LEVELS, read_consents, write_consents

router = APIRouter(prefix="/api/v1", tags=["consents"])


class ConsentsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matching: bool | None = None
    emails: bool | None = None
    recruiter_visibility: bool | None = None
    visibility: str | None = Field(default=None, max_length=20)


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Razılıqlar namizəd hesabı tələb edir")


@router.get("/consents")
def get_consents(
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    return read_consents(user_id=user.subject, lang=lang)


@router.put("/consents")
def put_consents(
    body: ConsentsIn,
    request: Request,
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    grants: dict[str, bool] = {}
    for kind in CONSENT_KINDS:
        value = getattr(body, kind)
        if value is not None:
            grants[kind] = bool(value)
    visibility = body.visibility
    if visibility is not None and visibility not in VISIBILITY_LEVELS:
        raise HTTPException(status_code=422, detail="Görünmə səviyyəsi yanlışdır")
    if not grants and visibility is None:
        raise HTTPException(status_code=422, detail="Yenilənəcək razılıq yoxdur")
    try:
        return write_consents(
            user_id=user.subject,
            grants=grants,
            visibility=visibility,
            request=request,
            lang=lang,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Razılıq məlumatı yanlışdır") from exc

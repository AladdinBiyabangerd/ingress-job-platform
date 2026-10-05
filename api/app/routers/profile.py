"""GET/PUT /api/v1/profile — structured CV profile review (plan §13.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.cv_profile import SENIORITY_VALUES, read_profile, save_profile

router = APIRouter(prefix="/api/v1", tags=["profile"])


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    headline: str | None = Field(default=None, max_length=200)
    seniority: str | None = Field(default=None, max_length=40)
    total_years: float | None = None
    profile: dict[str, Any] | None = None


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Profil namizəd hesabı tələb edir")


@router.get("/profile")
def get_profile(user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_candidate(user)
    return read_profile(user_id=user.subject)


@router.put("/profile")
def put_profile(body: ProfileIn, user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_candidate(user)
    if body.seniority is not None:
        value = body.seniority.strip().lower()
        if value and value not in SENIORITY_VALUES:
            raise HTTPException(status_code=422, detail="Seniority yanlışdır")
    if body.total_years is not None and (body.total_years < 0 or body.total_years > 60):
        raise HTTPException(status_code=422, detail="Təcrübə ili yanlışdır")
    if (
        not body.confirm
        and body.profile is None
        and body.headline is None
        and body.seniority is None
        and body.total_years is None
    ):
        raise HTTPException(status_code=422, detail="Yenilənəcək profil yoxdur")
    try:
        return save_profile(
            user_id=user.subject,
            data=body.profile,
            headline=body.headline,
            seniority=body.seniority,
            total_years=body.total_years,
            confirm=body.confirm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Profil məlumatı yanlışdır") from exc

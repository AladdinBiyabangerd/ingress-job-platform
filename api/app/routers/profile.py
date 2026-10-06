"""GET/PUT/DELETE /api/v1/profile — structured CV profile review (plan §13.1).

POST /api/v1/profile/cv — upload CV for parse without a job application.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.cabinet_store import CabinetError
from app.cv_profile import (
    SENIORITY_VALUES,
    cancel_open_parse,
    clear_profile,
    read_profile,
    save_profile,
    upload_profile_cv,
)

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
    payload = read_profile(user_id=user.subject)
    if payload.get("parse_status") in ("pending", "processing"):
        from app.cv_parse_jobs import schedule_parse_cv_drain

        schedule_parse_cv_drain()
    return payload


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


@router.delete("/profile")
def delete_profile(user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_candidate(user)
    try:
        return clear_profile(user_id=user.subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Profili sıfırlamaq olmadı") from exc


@router.post("/profile/cv/cancel")
def post_profile_cv_cancel(user: VerifiedAccess = Depends(current_user)) -> dict:
    """Cancel a stuck pending/processing CV parse without wiping the profile."""
    _require_candidate(user)
    try:
        return cancel_open_parse(user_id=user.subject)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="CV təhlilini ləğv etmək olmadı") from exc


@router.post("/profile/cv")
async def post_profile_cv(request: Request, user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_candidate(user)
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in ctype:
        raise HTTPException(status_code=422, detail="CV faylı PDF, DOC və ya DOCX olmalıdır və 5 MB-dan böyük ola bilməz")
    form = await request.form()
    try:
        upload = form.get("cv")
        if upload is None or not getattr(upload, "filename", None):
            raise HTTPException(status_code=422, detail="CV faylı PDF, DOC və ya DOCX olmalıdır və 5 MB-dan böyük ola bilməz")
        data = await upload.read()
        try:
            return upload_profile_cv(user_id=user.subject, filename=upload.filename or "", data=data)
        except CabinetError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    finally:
        await form.close()

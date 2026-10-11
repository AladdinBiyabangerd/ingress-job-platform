"""Owner cabinet: write, list, edit, and close ads. No public source URLs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.account import VerifiedAccess, current_user
from app.applications import DecisionIn, list_for_owner, set_status
from app.apply_form import FormError, FormIn, coerce_form
from app.cabinet_store import (
    JOB_TYPES,
    LANGS,
    CabinetError,
    close_ad,
    count_ads_created_since,
    create_ad,
    list_owned,
    update_ad,
)
from app.product_features import employer_posting_enabled
from app.profiles import profile_for
from app.rate_limit import check_rate, client_ip, dep_user, raise_slow_down
from app.turnstile import require_turnstile_token

router = APIRouter(prefix="/api/v1/cabinet", tags=["cabinet"])

_REQUIRED = "Başlıq, şirkət, şəhər və ya uzaqdan, və mətn doldurulmalıdır"


def _require_employer_posting() -> None:
    if not employer_posting_enabled():
        raise HTTPException(status_code=404, detail="Tapılmadı")


class AdIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=140)
    company: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=80)
    remote: bool = False
    text: str = Field(max_length=8000)
    language: str = Field(max_length=8)
    salary: str = Field(default="", max_length=120)
    job_type: str = Field(default="", max_length=16)
    form: FormIn | None = None
    turnstile_token: str | None = Field(default=None, max_length=2048)


def _clean(value: str, limit: int) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[:limit]


def _caller(user: VerifiedAccess) -> tuple[bool, bool]:
    staff = "job:staff" in user.scopes
    employer = "job:employer" in user.scopes
    if not staff and not employer:
        raise HTTPException(status_code=403, detail="Elan yerləşdirmək işəgötürən hesabı tələb edir")
    if not staff:
        profile = profile_for(user.subject)
        if not profile["complete"]:
            raise HTTPException(status_code=403, detail="Şirkət profili tamamlanmalıdır")
    return staff, employer


def _fields(body: AdIn, user: VerifiedAccess, *, staff: bool) -> dict:
    if staff:
        company = _clean(body.company, 120)
    else:
        company = profile_for(user.subject)["company_name"].strip()
    title = _clean(body.title, 140)
    remote = bool(body.remote)
    city = "" if remote else _clean(body.city, 80)
    text = _clean(body.text, 8000)
    language = _clean(body.language, 8).lower()
    salary = _clean(body.salary, 120)
    job_type = _clean(body.job_type, 16).lower()
    if language not in LANGS or job_type not in JOB_TYPES:
        raise HTTPException(status_code=422, detail=_REQUIRED)
    if not title or not company or not text or not (city or remote):
        raise HTTPException(status_code=422, detail=_REQUIRED)
    return {
        "title": title,
        "company": company,
        "city": city,
        "remote": remote,
        "text": text,
        "language": language,
        "salary": salary,
        "job_type": job_type,
    }


def _attach_form(fields: dict, body: AdIn, *, missing: str) -> dict:
    try:
        form = coerce_form(None if body.form is None else body.form.model_dump(), missing=missing)
    except FormError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    if form is not None:
        fields = {**fields, "form": form}
    return fields


def _run(action):
    try:
        return action()
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.get("/jobs")
def read_mine(user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_employer_posting()
    _caller(user)
    return {"items": list_owned(user.subject)}


def _cabinet_max_ads_per_day() -> int:
    raw = (os.environ.get("CABINET_MAX_ADS_PER_DAY") or "30").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


@router.post("/jobs", status_code=201)
def write_ad(
    body: AdIn,
    request: Request,
    user: VerifiedAccess = Depends(current_user),
    _rl=dep_user("cabinet_create"),
) -> dict:
    _require_employer_posting()
    staff, _employer = _caller(user)
    require_turnstile_token(body.turnstile_token, remoteip=client_ip(request))
    check_rate("cabinet_create_day", user.subject)
    if not staff:
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        if count_ads_created_since(user.subject, since) >= _cabinet_max_ads_per_day():
            raise_slow_down("rateLimit.postPause", 3600)
    fields = _attach_form(_fields(body, user, staff=staff), body, missing="default")
    return _run(lambda: create_ad(user.subject, fields, staff=staff))


@router.patch("/jobs/{job_id}")
def edit_ad(job_id: int, body: AdIn, user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_employer_posting()
    staff, _employer = _caller(user)
    fields = _attach_form(_fields(body, user, staff=staff), body, missing="keep")
    return _run(lambda: update_ad(user.subject, job_id, fields, staff=staff))


@router.post("/jobs/{job_id}/close")
def close_mine(job_id: int, user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_employer_posting()
    _caller(user)
    return _run(lambda: close_ad(user.subject, job_id))


@router.get("/applications")
def read_applications(user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_employer_posting()
    _caller(user)
    return {"items": list_for_owner(user.subject)}


@router.patch("/applications/{application_id}")
def decide_application(
    application_id: int,
    body: DecisionIn,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_employer_posting()
    _caller(user)
    return _run(
        lambda: set_status(
            application_id,
            subject=user.subject,
            staff=False,
            status=body.status,
            reason=body.reason,
        )
    )

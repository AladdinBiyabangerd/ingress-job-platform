"""Staff moderation of company ads. Only job:staff. No public source URLs."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.account import VerifiedAccess, current_user
from app.applications import DecisionIn, list_all, set_status
from app.apply_form import FormError, FormIn, coerce_form
from app.cabinet_store import (
    JOB_TYPES,
    LANGS,
    CabinetError,
    approve_ad,
    create_sourced_ad,
    get_moderation,
    list_moderation,
    reject_ad,
    staff_close_ad,
    staff_update_ad,
)
from app.crawled_admin import get_crawled, list_crawled, merge_crawled, set_crawled_hidden, update_crawled

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_REQUIRED = "Başlıq, şirkət, şəhər və ya uzaqdan, və mətn doldurulmalıdır"
_STAFF_ONLY = "Moderasiya yalnız əməkdaş hesabı üçündür"
_URL = "Orijinal ünvan http və ya https olmalıdır"
_REASON = "Rədd səbəbi yazılmalıdır"


class AdIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=140)
    company: str = Field(max_length=120)
    city: str = Field(default="", max_length=80)
    remote: bool = False
    text: str = Field(max_length=8000)
    language: str = Field(max_length=8)
    salary: str = Field(default="", max_length=120)
    job_type: str = Field(default="", max_length=16)
    form: FormIn | None = None


class ManualIn(AdIn):
    source_url: str = Field(max_length=500)


class CrawledIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=140)
    company: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=80)
    remote: bool = False
    text: str = Field(default="", max_length=8000)
    language: str = Field(default="", max_length=8)
    salary: str = Field(default="", max_length=120)
    job_type: str = Field(default="", max_length=16)


class MergeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keep_id: int
    hide_id: int


class AiFlagsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flags: dict[str, bool]


def require_staff(user: VerifiedAccess = Depends(current_user)) -> VerifiedAccess:
    if "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail=_STAFF_ONLY)
    return user


def _clean(value: str, limit: int) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[:limit]


def _fields(body: AdIn) -> dict:
    remote = bool(body.remote)
    city = "" if remote else _clean(body.city, 80)
    language = _clean(body.language, 8).lower()
    job_type = _clean(body.job_type, 16).lower()
    title = _clean(body.title, 140)
    company = _clean(body.company, 120)
    text = _clean(body.text, 8000)
    salary = _clean(body.salary, 120)
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


def _source_url(value: str) -> str:
    text = (value or "").strip()
    if not text or len(text) > 500 or any(char.isspace() for char in text):
        raise HTTPException(status_code=422, detail=_URL)
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        raise HTTPException(status_code=422, detail=_URL)
    return text


def _crawled_fields(body: CrawledIn) -> dict:
    remote = bool(body.remote)
    city = "" if remote else _clean(body.city, 80)
    language = _clean(body.language, 8).lower()
    job_type = _clean(body.job_type, 16).lower()
    title = _clean(body.title, 140)
    if language not in LANGS | {""} or job_type not in JOB_TYPES or not title:
        raise HTTPException(status_code=422, detail=_REQUIRED)
    return {
        "title": title,
        "company": _clean(body.company, 120),
        "city": city,
        "remote": remote,
        "text": _clean(body.text, 8000),
        "language": language,
        "salary": _clean(body.salary, 120),
        "job_type": job_type,
    }


def _run(action):
    try:
        return action()
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.get("/jobs")
def read_queue(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    return {"items": list_moderation()}


@router.get("/jobs/{job_id}")
def read_job(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: get_moderation(job_id))


@router.post("/jobs", status_code=201)
def manual_ad(body: ManualIn, user: VerifiedAccess = Depends(require_staff)) -> dict:
    fields = _attach_form(_fields(body), body, missing="default")
    url = _source_url(body.source_url)
    saved = _run(lambda: create_sourced_ad(user.subject, fields, url))
    if "source_url" in saved:
        saved = {key: value for key, value in saved.items() if key != "source_url"}
    return saved


@router.patch("/jobs/{job_id}")
def edit_ad(job_id: int, body: AdIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    fields = _attach_form(_fields(body), body, missing="keep")
    return _run(lambda: staff_update_ad(job_id, fields))


@router.post("/jobs/{job_id}/approve")
def approve(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: approve_ad(job_id))


@router.post("/jobs/{job_id}/reject")
async def reject(job_id: int, request: Request, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    reason = ""
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=_REASON) from exc
        if not isinstance(payload, dict) or any(key != "reason" for key in payload):
            raise HTTPException(status_code=422, detail=_REASON)
        raw = payload.get("reason")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            raise HTTPException(status_code=422, detail=_REASON)
        reason = raw
    return _run(lambda: reject_ad(job_id, reason))


@router.post("/jobs/{job_id}/close")
def close(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: staff_close_ad(job_id))


@router.get("/crawled")
def read_crawled(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    return {"items": list_crawled()}


@router.get("/crawled/{job_id}")
def read_one_crawled(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: get_crawled(job_id))


@router.patch("/crawled/{job_id}")
def edit_crawled(job_id: int, body: CrawledIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: update_crawled(job_id, _crawled_fields(body)))


@router.post("/crawled/merge")
def merge(body: MergeIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: merge_crawled(body.keep_id, body.hide_id))


@router.post("/crawled/{job_id}/hide")
def hide_crawled(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: set_crawled_hidden(job_id, True))


@router.post("/crawled/{job_id}/show")
def show_crawled(job_id: int, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: set_crawled_hidden(job_id, False))


@router.get("/applications")
def read_applications(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    return {"items": list_all()}


@router.patch("/applications/{application_id}")
def decide_application(
    application_id: int,
    body: DecisionIn,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    return _run(
        lambda: set_status(
            application_id,
            subject=_user.subject,
            staff=True,
            status=body.status,
            reason=body.reason,
        )
    )


@router.get("/ai-flags")
def read_ai_flags(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.ai_flags import effective_flags, key_configured
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return {"key_configured": key_configured(), "flags": effective_flags(conn)}
        finally:
            conn.close()


@router.put("/ai-flags")
def write_ai_flags(body: AiFlagsIn, user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.ai_flags import FlagError, key_configured, set_flags
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            flags = set_flags(conn, body.flags, updated_by=user.subject)
        except FlagError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        finally:
            conn.close()
    return {"key_configured": key_configured(), "flags": flags}

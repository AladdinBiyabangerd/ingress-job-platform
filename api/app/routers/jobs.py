"""Public read of collected jobs. Apply and the original URL need a candidate."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.account import VerifiedAccess, current_user
from app.applications import create_application
from app.cabinet_store import CabinetError
from app.sqlite_jobs import (
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    SORTS,
    WHENS,
    apply_target,
    get_job,
    published_source_url,
    query_jobs,
)

router = APIRouter(prefix="/api/v1", tags=["jobs"])

_CANDIDATE = "Bu keçid namizəd hesabı tələb edir"
_MESSAGE = "Qısa müraciət yazılmalıdır"
_FORM = "Müraciət forması düzgün deyil"
_APPLY_KEYS = {"message", "phone", "email", "answers"}


def _candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail=_CANDIDATE)


def _bool_flag(value: bool | None) -> bool:
    return bool(value)


@router.get("/jobs")
def read_jobs(
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    q: str = Query("", max_length=120),
    company: str = Query("", max_length=120),
    remote: bool = Query(False),
    relocation: bool = Query(False),
    when: str = Query("any"),
    sort: str = Query("newest"),
    language: list[str] | None = Query(None),
    category: list[str] | None = Query(None),
    stack: list[str] | None = Query(None),
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
) -> dict:
    return query_jobs(
        page=page,
        per_page=per_page,
        q=q.strip(),
        company=company.strip(),
        remote=_bool_flag(remote),
        relocation=_bool_flag(relocation),
        when=when if when in WHENS else "any",
        sort=sort if sort in SORTS else "newest",
        languages=language,
        categories=category,
        stacks=stack,
        salary_min=salary_min,
        salary_max=salary_max,
    )


@router.get("/jobs/{job_id}")
def read_job(job_id: int) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    return job


@router.get("/jobs/{job_id}/original")
def original(job_id: int, user: VerifiedAccess = Depends(current_user)) -> dict:
    _candidate(user)
    url = published_source_url(job_id)
    if not url:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    return {"url": url}


def _text_field(value, detail: str = _FORM) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=detail)
    return value


def _answers(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=_FORM) from exc
    if not isinstance(value, list):
        raise HTTPException(status_code=422, detail=_FORM)
    cleaned = []
    for item in value:
        if not isinstance(item, dict) or any(key not in {"id", "answer"} for key in item):
            raise HTTPException(status_code=422, detail=_FORM)
        qid = item.get("id")
        answer = item.get("answer")
        if not isinstance(qid, str) or not isinstance(answer, str):
            raise HTTPException(status_code=422, detail=_FORM)
        cleaned.append({"id": qid, "answer": answer})
    return cleaned


async def _application_body(request: Request) -> tuple[dict, tuple[str, bytes] | None]:
    ctype = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ctype:
        form = await request.form()
        try:
            upload = form.get("cv")
            cv = None
            if upload is not None and getattr(upload, "filename", None):
                data = await upload.read()
                cv = (upload.filename or "", data)
            return {
                "message": _text_field(form.get("message")),
                "phone": _text_field(form.get("phone")),
                "email": _text_field(form.get("email")),
                "answers": _answers(form.get("answers")),
            }, cv
        finally:
            await form.close()
    if "application/json" in ctype:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=_MESSAGE) from exc
        if not isinstance(payload, dict) or any(key not in _APPLY_KEYS for key in payload):
            raise HTTPException(status_code=422, detail=_FORM if isinstance(payload, dict) else _MESSAGE)
        return {
            "message": _text_field(payload.get("message"), _MESSAGE),
            "phone": _text_field(payload.get("phone")),
            "email": _text_field(payload.get("email")),
            "answers": _answers(payload.get("answers")),
        }, None
    raise HTTPException(status_code=422, detail=_MESSAGE)


@router.post("/jobs/{job_id}/apply")
async def apply(job_id: int, request: Request, user: VerifiedAccess = Depends(current_user)) -> dict:
    _candidate(user)
    target = apply_target(job_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    if target["kind"] == "external":
        return {"url": target["url"]}
    fields, cv = await _application_body(request)
    try:
        return create_application(user.subject, job_id, fields, cv)
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

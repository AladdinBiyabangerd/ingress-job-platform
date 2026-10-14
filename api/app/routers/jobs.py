"""Public read of collected jobs. Apply and the original URL need a candidate."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.account import VerifiedAccess, current_user
from app.applications import create_application
from app.cabinet_store import CabinetError
from app.original_opens import record_original_open
from app.rate_limit import dep_ip, dep_user
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
    city: str = Query("", max_length=80),
    remote: bool = Query(False),
    relocation: bool = Query(False),
    onsite: bool = Query(False),
    viewed: bool = Query(False),
    when: str = Query("any"),
    sort: str = Query("newest"),
    language: list[str] | None = Query(None),
    category: list[str] | None = Query(None),
    stack: list[str] | None = Query(None),
    salary_min: int | None = Query(None, ge=0),
    salary_max: int | None = Query(None, ge=0),
    authorization: str | None = Header(default=None),
    _rl=dep_ip("public_read"),
) -> dict:
    viewed_user_id = None
    if _bool_flag(viewed):
        # Viewed filter is per-candidate; guests get an empty board, not 401,
        # so the public list proxy can stay unauthenticated.
        if authorization and authorization.lower().startswith("bearer "):
            try:
                viewed_user_id = current_user(authorization).subject
            except HTTPException:
                viewed_user_id = ""
        else:
            viewed_user_id = ""
    return query_jobs(
        page=page,
        per_page=per_page,
        q=q.strip(),
        company=company.strip(),
        city=city.strip(),
        remote=_bool_flag(remote),
        relocation=_bool_flag(relocation),
        onsite=_bool_flag(onsite),
        when=when if when in WHENS else "any",
        sort=sort if sort in SORTS else "newest",
        languages=language,
        categories=category,
        stacks=stack,
        salary_min=salary_min,
        salary_max=salary_max,
        viewed_user_id=viewed_user_id,
    )


@router.get("/categories")
def read_categories(_rl=dep_ip("public_read")) -> dict:
    """Active job categories in display order, with published-job counts."""
    from app.job_categories import active_rows, public_item
    from app.sqlite_jobs import query_jobs as _query

    totals = {}
    try:
        facets = _query(page=1, per_page=1).get("facets") or {}
        totals = {item["name"]: item["total"] for item in facets.get("categories") or []}
    except Exception:  # noqa: BLE001 - no jobs database yet
        totals = {}
    return {"items": [public_item(row, totals.get(row["slug"], 0)) for row in active_rows()]}


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
    record_original_open(user_id=user.subject, job_id=job_id)
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
async def apply(
    job_id: int,
    request: Request,
    user: VerifiedAccess = Depends(current_user),
    _rl=dep_user("apply_cv"),
) -> dict:
    _candidate(user)
    target = apply_target(job_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    if target["kind"] == "external":
        record_original_open(user_id=user.subject, job_id=job_id)
        return {"url": target["url"]}
    fields, cv = await _application_body(request)
    try:
        return create_application(user.subject, job_id, fields, cv)
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

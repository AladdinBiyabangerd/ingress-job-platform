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
    approve_ads,
    approve_ads_by_threshold,
    backfill_moderation_confidence,
    create_sourced_ad,
    get_moderation,
    list_moderation,
    reject_ad,
    reject_ads_by_threshold,
    staff_close_ad,
    staff_update_ad,
)
from app.crawl_rejects_admin import (
    clear_crawl_rejects,
    list_crawl_rejects,
    publish_crawl_rejects_by_threshold,
)
from app.job_tidy_admin import list_untidy_jobs
from app.job_tidy_jobs import cancel_tidy_job, get_tidy_job, start_tidy_job
from app.market_fit_recheck_jobs import cancel_recheck_job, get_recheck_job, start_recheck_job
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


class BulkApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(default_factory=list, max_length=200)


class ThresholdApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: str = Field(pattern="^(ai|rule)$")
    op: str = Field(pattern="^(gte|lte)$")
    threshold: int = Field(ge=0, le=100)
    status: str = Field(default="pending", pattern="^(pending|rejected)$")


class ThresholdRejectIn(BaseModel):
    """Queue «Faizə uyğun rədd et»: pending ads only."""

    model_config = ConfigDict(extra="forbid")

    score: str = Field(pattern="^(ai|rule)$")
    op: str = Field(pattern="^(gte|lte)$")
    threshold: int = Field(ge=0, le=100)
    reason: str = Field(default="", max_length=400)


class RecheckThresholdIn(BaseModel):
    """Queue threshold panel: every pending ad with AI/rule op+percent (no cap)."""

    model_config = ConfigDict(extra="forbid")

    score: str = Field(pattern="^(ai|rule)$")
    op: str = Field(pattern="^(gte|lte)$")
    threshold: int = Field(ge=0, le=100)


class RecheckListFilterIn(BaseModel):
    """Same fields as the staff list filter bar (frontend/lib/admin-list-filter.js)."""

    model_config = ConfigDict(extra="forbid")

    ai_op: str = Field(default="gte", pattern="^(gte|lte)$")
    ai_value: int | None = Field(default=None, ge=0, le=100)
    rule_op: str = Field(default="gte", pattern="^(gte|lte)$")
    rule_value: int | None = Field(default=None, ge=0, le=100)
    source: str = Field(default="", max_length=200)


class RecheckMarketFitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(default_factory=list, max_length=2000)
    scope: str = Field(default="queue", pattern="^(queue|crawled|crawl_rejects)$")
    # True = ask the AI again (skip cached answer); capped per run.
    fresh: bool = False
    # Used only when ids is empty: pending queue ads matching this filter.
    filter: RecheckListFilterIn | None = None
    limit: int | None = Field(default=None, ge=1, le=200)
    # Used only when ids is empty (queue): all matching pending ads, limit ignored.
    threshold: RecheckThresholdIn | None = None


class JobTidyRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(default_factory=list, max_length=2000)


class CrawlRejectThresholdIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: str = Field(pattern="^(ai|rule)$")
    op: str = Field(pattern="^(gte|lte)$")
    threshold: int = Field(ge=0, le=100)


class CrawlRejectClearIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[str] = Field(default_factory=list, max_length=500)


class BackfillConfidenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_limit: int = Field(default=40, ge=0, le=50)


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


@router.post("/jobs/approve-bulk")
def approve_bulk(body: BulkApproveIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: approve_ads(body.ids))


@router.post("/jobs/approve-threshold")
def approve_threshold(body: ThresholdApproveIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(
        lambda: approve_ads_by_threshold(
            score=body.score,
            op=body.op,
            threshold=body.threshold,
            status=body.status,
        )
    )


@router.post("/jobs/reject-threshold")
def reject_threshold(body: ThresholdRejectIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(
        lambda: reject_ads_by_threshold(
            score=body.score,
            op=body.op,
            threshold=body.threshold,
            reason=body.reason,
        )
    )


@router.post("/jobs/recheck-market-fit")
def recheck_fit(body: RecheckMarketFitIn, user: VerifiedAccess = Depends(require_staff)) -> dict:
    """Start async recheck; poll GET .../recheck-market-fit/{job_id} for progress."""
    return _run(
        lambda: start_recheck_job(
            body.ids,
            scope=body.scope,
            created_by=user.subject,
            fresh=body.fresh,
            list_filter=body.filter.model_dump() if body.filter is not None else None,
            limit=body.limit,
            threshold=body.threshold.model_dump() if body.threshold is not None else None,
        )
    )


@router.get("/jobs/recheck-market-fit/{job_id}")
def recheck_fit_status(job_id: str, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: get_recheck_job(job_id))


@router.post("/jobs/recheck-market-fit/{job_id}/cancel")
def recheck_fit_cancel(job_id: str, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    """Stop remaining AI checks; already-written results are kept."""
    return _run(lambda: cancel_recheck_job(job_id))


@router.get("/job-tidy")
def read_untidy(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    return {"items": list_untidy_jobs()}


@router.post("/job-tidy/run")
def tidy_run(body: JobTidyRunIn, user: VerifiedAccess = Depends(require_staff)) -> dict:
    """Start async job_tidy; poll GET .../job-tidy/run/{job_id} for progress."""
    return _run(lambda: start_tidy_job(body.ids, created_by=user.subject))


@router.get("/job-tidy/run/{job_id}")
def tidy_run_status(job_id: str, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    return _run(lambda: get_tidy_job(job_id))


@router.post("/job-tidy/run/{job_id}/cancel")
def tidy_run_cancel(job_id: str, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    """Stop remaining tidy work; already-saved cleaned_text is kept."""
    return _run(lambda: cancel_tidy_job(job_id))


@router.post("/jobs/backfill-confidence")
def backfill_confidence(
    body: BackfillConfidenceIn,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    return _run(lambda: backfill_moderation_confidence(ai_limit=body.ai_limit))


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


@router.get("/notification-log")
def read_notification_log(
    user: str = "",
    days: int = 30,
    limit: int = 200,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    """Per-user email / in-app / push delivery log with skip reasons (staff)."""
    from app.cabinet_store import _LOCK, _connect
    from app.notification_log import build_notification_log

    query = (user or "").strip()[:255]
    with _LOCK:
        conn = _connect()
        try:
            payload = build_notification_log(conn, user=query, days=days, limit=limit)
            conn.commit()
            return payload
        finally:
            conn.close()


@router.get("/ops-status")
def read_ops_status(
    days: int = 7,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    """Live AI provider/feature status + crawl funnel for staff ops."""
    from app.cabinet_store import _LOCK, _connect
    from app.ops_status import build_ops_status

    with _LOCK:
        conn = _connect()
        try:
            return build_ops_status(conn, days=days)
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


# ---- crawl_rejects (URL skip list) ----------------------------------------


@router.get("/crawl-rejects")
def read_crawl_rejects(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    return {"items": list_crawl_rejects()}


@router.post("/crawl-rejects/publish-threshold")
def publish_crawl_rejects_threshold(
    body: CrawlRejectThresholdIn,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    return _run(
        lambda: publish_crawl_rejects_by_threshold(
            score=body.score,
            op=body.op,
            threshold=body.threshold,
        )
    )


@router.post("/crawl-rejects/clear")
def clear_crawl_reject_urls(
    body: CrawlRejectClearIn,
    _user: VerifiedAccess = Depends(require_staff),
) -> dict:
    return _run(lambda: clear_crawl_rejects(body.urls))


# ---- job categories (job_categories table) --------------------------------


class CategoryFieldsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_az: str | None = Field(default=None, max_length=60)
    name_en: str | None = Field(default=None, max_length=60)
    name_ru: str | None = Field(default=None, max_length=60)
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    priority: int | None = Field(default=None, ge=0, le=100000)
    stack_rank: int | None = Field(default=None, ge=0, le=100000)
    active: bool | None = None
    title_pattern: str | None = Field(default=None, max_length=2000)
    aliases: list[str] | None = Field(default=None, max_length=200)
    stack_names: list[str] | None = Field(default=None, max_length=200)


class CategoryCreateIn(CategoryFieldsIn):
    slug: str = Field(min_length=1, max_length=40)


class CategoryOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slugs: list[str] = Field(max_length=200)


def _cat(action):
    from app.job_categories import CategoryError

    try:
        return action()
    except CategoryError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.get("/categories")
def read_categories_admin(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.job_categories import staff_list

    return {"items": staff_list()}


@router.post("/categories")
def create_category(body: CategoryCreateIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.job_categories import create

    fields = body.model_dump(exclude={"slug"}, exclude_none=True)
    return _cat(lambda: create(body.slug, fields))


@router.put("/categories/order")
def reorder_categories(body: CategoryOrderIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.job_categories import reorder

    return {"items": _cat(lambda: reorder(body.slugs))}


@router.post("/categories/recategorise")
def recategorise_jobs(_user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.job_categories import recategorise

    return _cat(recategorise)


@router.patch("/categories/{slug:path}")
def update_category(slug: str, body: CategoryFieldsIn, _user: VerifiedAccess = Depends(require_staff)) -> dict:
    from app.job_categories import update

    return _cat(lambda: update(slug, body.model_dump(exclude_none=True)))

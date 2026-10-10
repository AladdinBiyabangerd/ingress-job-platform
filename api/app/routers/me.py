"""Candidate /me routes: roles, matches, feedback, export/delete (plan §6 / §10.3 / §13.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.cabinet_store import CabinetError
from app.job_analyze import analyze_job
from app.job_apply_draft import create_apply_draft
from app.job_tailored_cv import create_tailored_cv
from app.matching import (
    FEEDBACK_REASONS,
    FEEDBACK_VOTES,
    MAX_LIMIT as MATCH_MAX_LIMIT,
    list_matches,
    save_match_feedback,
)
from app.me_data import build_export_zip, delete_my_data
from app.role_suggestions import MAX_LIMIT as ROLE_MAX_LIMIT, suggest_roles
from app.saved_jobs import (
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    list_saved,
    list_saved_ids,
    save_job,
    unsave_job,
)
from app.product_features import recommendations_enabled, roadmap_enabled
from app.skill_gap import MAX_TOP as SKILL_GAP_MAX_TOP, skill_gap

router = APIRouter(prefix="/api/v1/me", tags=["me"])


def _run(action):
    try:
        return action()
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


class MatchFeedbackBody(BaseModel):
    vote: str = Field(..., min_length=2, max_length=8)
    reason: str = Field(default="", max_length=40)


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Namizəd hesabı tələb edir")


def _require_recommendations() -> None:
    if not recommendations_enabled():
        raise HTTPException(status_code=404, detail="Tapılmadı")


def _require_roadmap() -> None:
    if not roadmap_enabled():
        raise HTTPException(status_code=404, detail="Tapılmadı")


@router.get("/saved-jobs/ids")
def get_saved_job_ids(user: VerifiedAccess = Depends(current_user)) -> dict:
    return {"ids": list_saved_ids(user_id=user.subject)}


@router.get("/saved-jobs")
def get_saved_jobs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    return list_saved(user_id=user.subject, page=page, per_page=per_page)


@router.post("/saved-jobs/{job_id}")
def post_saved_job(job_id: int, user: VerifiedAccess = Depends(current_user)) -> JSONResponse:
    result = _run(lambda: save_job(user_id=user.subject, job_id=job_id))
    created = bool(result.pop("created", False))
    return JSONResponse(
        {"job_id": result["job_id"], "saved_at": result["saved_at"]},
        status_code=201 if created else 200,
    )


@router.delete("/saved-jobs/{job_id}", status_code=204)
def delete_saved_job(job_id: int, user: VerifiedAccess = Depends(current_user)) -> Response:
    _run(lambda: unsave_job(user_id=user.subject, job_id=job_id))
    return Response(status_code=204)


@router.get("/roles")
def get_roles(
    limit: int | None = Query(default=None, ge=1, le=ROLE_MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    return suggest_roles(user_id=user.subject, limit=limit, lang=lang)


@router.get("/matches")
def get_matches(
    limit: int | None = Query(default=None, ge=1, le=MATCH_MAX_LIMIT),
    lang: str | None = Query(default=None, max_length=8),
    role: str | None = Query(default=None, max_length=120),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Structured job matches (plan §6.2). Optional role= scopes to signature skills."""
    _require_recommendations()
    _require_candidate(user)
    return list_matches(user_id=user.subject, limit=limit, lang=lang, role=role)


@router.get("/jobs/{job_id}/analyze")
def get_job_analyze(
    job_id: int,
    lang: str | None = Query(default=None, max_length=8),
    refresh: int | None = Query(default=None, ge=0, le=1),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Job-detail fit analysis. Independent of recommendations hub flag."""
    _require_candidate(user)
    payload = analyze_job(
        user_id=user.subject,
        job_id=job_id,
        lang=lang,
        refresh=bool(refresh),
    )
    if payload.get("gate") == "job_not_found":
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    return payload


class ApplyDraftBody(BaseModel):
    refresh: bool = False


class TailoredCvBody(BaseModel):
    refresh: bool = False


@router.post("/jobs/{job_id}/apply-draft")
def post_job_apply_draft(
    job_id: int,
    body: ApplyDraftBody = ApplyDraftBody(),
    lang: str | None = Query(default=None, max_length=8),
    refresh: int | None = Query(default=None, ge=0, le=1),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Hunt-style apply message draft for job detail. Independent of recommendations hub."""
    _require_candidate(user)
    want_refresh = bool(refresh) or bool(body.refresh)
    payload = create_apply_draft(
        user_id=user.subject,
        job_id=job_id,
        lang=lang,
        refresh=want_refresh,
    )
    if payload.get("status") == "job_not_found":
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    return payload


@router.post("/jobs/{job_id}/tailored-cv")
def post_job_tailored_cv(
    job_id: int,
    body: TailoredCvBody = TailoredCvBody(),
    lang: str | None = Query(default=None, max_length=8),
    refresh: int | None = Query(default=None, ge=0, le=1),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Job-tailored ATS CV draft from confirmed profile facts. Independent of recommendations hub."""
    _require_candidate(user)
    want_refresh = bool(refresh) or bool(body.refresh)
    payload = create_tailored_cv(
        user_id=user.subject,
        job_id=job_id,
        lang=lang,
        refresh=want_refresh,
    )
    if payload.get("status") == "job_not_found":
        raise HTTPException(status_code=404, detail="Elan tapılmadı")
    return payload


@router.post("/matches/{job_id}/feedback")
def post_match_feedback(
    job_id: int,
    body: MatchFeedbackBody,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """👍 / 👎 on a recommendation (plan §6.3)."""
    _require_recommendations()
    _require_candidate(user)
    vote = (body.vote or "").strip().lower()
    reason = (body.reason or "").strip().lower()
    if vote not in FEEDBACK_VOTES:
        raise HTTPException(status_code=400, detail="vote must be up or down")
    if vote == "down" and reason and reason not in FEEDBACK_REASONS:
        raise HTTPException(
            status_code=400,
            detail="reason must be location, seniority, technology, salary, or empty",
        )
    try:
        return save_match_feedback(
            user_id=user.subject,
            job_id=job_id,
            vote=vote,
            reason=reason,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Matching razılığı tələb olunur") from None
    except LookupError:
        raise HTTPException(status_code=404, detail="Elan tapılmadı") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/skill-gap")
def get_skill_gap(
    role: str | None = Query(default=None, max_length=120),
    top: int | None = Query(default=None, ge=1, le=SKILL_GAP_MAX_TOP),
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Skill gap vs target role signature skills (plan §7.2)."""
    _require_recommendations()
    _require_candidate(user)
    return skill_gap(user_id=user.subject, role=role, top=top, lang=lang)


@router.get("/insights")
def get_insights(
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Growth hub: weekly coach, near-miss jobs, Academy/roadmap (engagement Phase 4)."""
    _require_roadmap()
    _require_candidate(user)
    from app.cabinet_store import _LOCK, _connect, ensure_schema
    from app.engagement import insights_payload

    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            return insights_payload(conn, user_id=user.subject, lang=lang)
        finally:
            conn.close()


class PushSubscriptionBody(BaseModel):
    endpoint: str = Field(..., min_length=8, max_length=2048)
    keys: dict[str, str] = Field(default_factory=dict)


class PushSubscriptionDeleteBody(BaseModel):
    endpoint: str = Field(..., min_length=8, max_length=2048)


@router.get("/push-vapid-key")
def get_push_vapid_key(user: VerifiedAccess = Depends(current_user)) -> dict:
    """Public VAPID key for Web Push subscribe (engagement Phase 5)."""
    _require_candidate(user)
    from app.push import vapid_configured, vapid_missing_names, vapid_public_key

    if not vapid_configured():
        missing = vapid_missing_names()
        # Visible in Railway request logs without leaking secret values.
        print(f"push-vapid-key 503 missing={','.join(missing) or '(unknown)'}", flush=True)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "web_push_not_configured",
                "missing": missing,
            },
        )
    return {"publicKey": vapid_public_key()}


@router.post("/push-subscription", status_code=201)
def post_push_subscription(
    body: PushSubscriptionBody,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Store or refresh a browser push subscription."""
    _require_candidate(user)
    from app.cabinet_store import _LOCK, _connect, ensure_schema
    from app.push import upsert_subscription

    keys = body.keys if isinstance(body.keys, dict) else {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            try:
                stored = upsert_subscription(
                    conn,
                    user_id=user.subject,
                    endpoint=body.endpoint,
                    p256dh=p256dh,
                    auth=auth,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            conn.commit()
            return stored
        finally:
            conn.close()


@router.delete("/push-subscription")
def delete_push_subscription(
    body: PushSubscriptionDeleteBody,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    """Remove a browser push subscription for the current user."""
    _require_candidate(user)
    from app.cabinet_store import _LOCK, _connect, ensure_schema
    from app.push import delete_subscription

    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            removed = delete_subscription(
                conn, user_id=user.subject, endpoint=body.endpoint
            )
            conn.commit()
            return {"deleted": removed}
        finally:
            conn.close()


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
